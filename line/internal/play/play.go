// Package play is N4's playground: a versioned prompt registry with
// measured runs, single-seat asks, A/B compares and exact-match evals.
//
// Prompts live in <home>/prompts/<name>.md — a --- fence carrying name,
// version and description, then a body with {{var}} slots. New saves fold:
// the old latest is kept whole as <name>.v<k>.md, never rewritten.
// Runs append to <home>/prompts/runs.jsonl with receipt =
// sha256(kind \n prompt \n version \n input \n output \n ts), pinned by
// tools/cut_playground_vectors.py. Missing vars refuse; unknown seats are
// refused by name; a named model is stamped measurement, not configuration.
package play

import (
	"bufio"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"

	"atlas/line/internal/guard"
	"atlas/line/internal/rack"
)

// NameRe pins the prompt-name law (cutter holds the same pattern).
var NameRe = regexp.MustCompile(`^[a-z0-9][a-z0-9_-]{0,63}$`)

// SeatRe parses "@seat rest..." addressing (cutter holds the same pattern).
var SeatRe = regexp.MustCompile(`^@([A-Za-z0-9_-]+)\s+([\s\S]+)$`)

// Prompt is one versioned template.
type Prompt struct {
	Name        string
	Version     int
	Description string
	Body        string
}

// Run is one witnessed measurement.
type Run struct {
	ID        string `json:"id"`
	TS        string `json:"ts"`
	Kind      string `json:"kind"`
	Prompt    string `json:"prompt"`
	Version   int    `json:"version"`
	Seat      string `json:"seat,omitempty"`
	Voice     string `json:"voice"`
	Override  bool   `json:"override"`
	Method    string `json:"method,omitempty"`
	Input     string `json:"input"`
	Output    string `json:"output"`
	Receipt   string `json:"receipt"`
	LatencyMs int64  `json:"latency_ms"`
	EvalCount int64  `json:"eval_count"`
	Score     *bool  `json:"score,omitempty"`
}

func promptsDir(home string) string   { return filepath.Join(home, "prompts") }
func manifestPath(home string) string { return filepath.Join(promptsDir(home), "manifest.json") }
func runsPath(home string) string     { return filepath.Join(promptsDir(home), "runs.jsonl") }

// Receipt binds a run (cutter reproduces this byte-for-byte).
func Receipt(kind, prompt string, version int, input, output, ts string) string {
	h := sha256.Sum256([]byte(fmt.Sprintf("%s\n%s\n%d\n%s\n%s\n%s", kind, prompt, version, input, output, ts)))
	return hex.EncodeToString(h[:])
}

// ParseSeat splits "@seat question" or refuses (no @, no seat).
func ParseSeat(raw string) (seat, question string, err error) {
	m := SeatRe.FindStringSubmatch(strings.TrimSpace(raw))
	if m == nil {
		return "", "", fmt.Errorf("refused: seat_ask needs @seat addressing (e.g. \"@manjuel what holds\")")
	}
	return m[1], m[2], nil
}

// Render substitutes {{var}} slots verbatim; a missing var refuses by name.
func Render(body string, vars map[string]string) (string, error) {
	var missing []string
	re := regexp.MustCompile(`\{\{\s*([A-Za-z0-9_]+)\s*\}\}`)
	out := re.ReplaceAllStringFunc(body, func(m string) string {
		key := strings.TrimSpace(m[2 : len(m)-2])
		if v, ok := vars[key]; ok {
			return v
		}
		missing = append(missing, key)
		return m
	})
	if len(missing) > 0 {
		sort.Strings(missing)
		return "", fmt.Errorf("refused: missing var: %s — nothing is guessed", strings.Join(dedup(missing), ", "))
	}
	return out, nil
}

func dedup(s []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, v := range s {
		if !seen[v] {
			seen[v] = true
			out = append(out, v)
		}
	}
	return out
}

// Score is exact match after trim+casefold; anything else fails honestly.
func Score(expected, got string) bool {
	return strings.EqualFold(strings.TrimSpace(expected), strings.TrimSpace(got))
}

// Save folds a new version: the old latest is kept as <name>.v<k>.md.
func Save(home, name, body, description string) (Prompt, error) {
	if !NameRe.MatchString(name) {
		return Prompt{}, fmt.Errorf("refused: prompt name %q breaks the name law (lowercase, digits, - _, max 64)", name)
	}
	if strings.TrimSpace(body) == "" {
		return Prompt{}, fmt.Errorf("refused: prompt body is empty — nothing is stored")
	}
	if err := os.MkdirAll(promptsDir(home), 0o755); err != nil {
		return Prompt{}, err
	}
	latest := 0
	if cur, err := Get(home, name, 0); err == nil {
		latest = cur.Version
		// Fold the old latest whole before replacing it.
		old, _ := os.ReadFile(promptPath(home, name, 0))
		if err := os.WriteFile(promptPath(home, name, latest), old, 0o644); err != nil {
			return Prompt{}, err
		}
	}
	p := Prompt{Name: name, Version: latest + 1, Description: strings.TrimSpace(description), Body: body}
	if err := os.WriteFile(promptPath(home, name, 0), []byte(renderFile(p)), 0o644); err != nil {
		return Prompt{}, err
	}
	if err := saveManifest(home); err != nil {
		return Prompt{}, err
	}
	return p, nil
}

// Get reads version v (0 = latest); absent names/versions denied honestly.
// The latest always lives in <name>.md; history lives in <name>.v<k>.md.
func Get(home, name string, v int) (Prompt, error) {
	if !NameRe.MatchString(name) {
		return Prompt{}, fmt.Errorf("refused: prompt name %q breaks the name law", name)
	}
	if v > 0 {
		if cur, err := Get(home, name, 0); err == nil && cur.Version == v {
			return cur, nil
		}
		raw, err := os.ReadFile(promptPath(home, name, v))
		if err != nil {
			return Prompt{}, fmt.Errorf("no such prompt version: %s v%d — try prompt_list", name, v)
		}
		return parseFile(name, string(raw))
	}
	raw, err := os.ReadFile(promptPath(home, name, 0))
	if err != nil {
		return Prompt{}, fmt.Errorf("no such prompt: %s — try prompt_list", name)
	}
	return parseFile(name, string(raw))
}

// List names every prompt with its latest version.
func List(home string) ([]Prompt, error) {
	entries, err := os.ReadDir(promptsDir(home))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	var out []Prompt
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".md") {
			continue
		}
		base := strings.TrimSuffix(e.Name(), ".md")
		if !NameRe.MatchString(base) {
			continue // versioned history files carry dots; latest only
		}
		p, err := Get(home, base, 0)
		if err != nil {
			continue
		}
		out = append(out, p)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out, nil
}

// Versions lists every kept version number for a prompt, ascending.
func Versions(home, name string) ([]int, error) {
	cur, err := Get(home, name, 0)
	if err != nil {
		return nil, err
	}
	out := []int{cur.Version}
	for v := 1; v < cur.Version; v++ {
		if _, err := os.Stat(promptPath(home, name, v)); err == nil {
			out = append(out, v)
		}
	}
	sort.Ints(out)
	return out, nil
}

func promptPath(home, name string, v int) string {
	if v <= 0 {
		return filepath.Join(promptsDir(home), name+".md")
	}
	return filepath.Join(promptsDir(home), fmt.Sprintf("%s.v%d.md", name, v))
}

func renderFile(p Prompt) string {
	return fmt.Sprintf("---\nname: %s\nversion: %d\ndescription: %s\n---\n%s",
		p.Name, p.Version, p.Description, p.Body)
}

func parseFile(name, raw string) (Prompt, error) {
	parts := strings.SplitN(raw, "---\n", 3)
	if len(parts) != 3 || strings.TrimSpace(parts[0]) != "" {
		return Prompt{}, fmt.Errorf("prompt %q breaks the file law: --- fence, header, ---, body", name)
	}
	p := Prompt{Name: name, Body: parts[2]}
	for _, line := range strings.Split(parts[1], "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		kv := strings.SplitN(line, ":", 2)
		if len(kv) != 2 {
			continue
		}
		switch strings.TrimSpace(kv[0]) {
		case "version":
			fmt.Sscanf(strings.TrimSpace(kv[1]), "%d", &p.Version)
		case "description":
			p.Description = strings.TrimSpace(kv[1])
		}
	}
	if p.Version <= 0 {
		return Prompt{}, fmt.Errorf("prompt %q carries no version — nothing is trusted", name)
	}
	return p, nil
}

func saveManifest(home string) error {
	list, err := List(home)
	if err != nil {
		return err
	}
	doc := map[string]any{}
	for _, p := range list {
		vers, _ := Versions(home, p.Name)
		doc[p.Name] = map[string]any{"latest": p.Version, "versions": vers}
	}
	b, err := json.MarshalIndent(map[string]any{"prompts": doc}, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(manifestPath(home), append(b, '\n'), 0o644)
}

// RunID mints r-YYYYMMDD-HHMMSS-<8hex>.
func RunID() (string, error) {
	var b [4]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return fmt.Sprintf("r-%s-%s", time.Now().UTC().Format("20060102-150405"), hex.EncodeToString(b[:])), nil
}

// Measure guards, routes, asks with telemetry, and witnesses to the rack
// ledger: one measurement, fully receipted. The flow runner builds on it.
func Measure(ctx context.Context, home, question, voice string) (answer, routed string, det rack.Detail, err error) {
	return askMeasured(ctx, home, question, voice)
}

// askMeasured guards, routes, asks with telemetry, and witnesses to the
// rack ledger. One measurement, fully receipted.
func askMeasured(ctx context.Context, home, question, voice string) (answer string, routed string, det rack.Detail, err error) {
	clean, flags, blocked, reason := guard.Pipeline(question)
	if blocked {
		return "", "", rack.Detail{}, fmt.Errorf("refused: %s", reason)
	}
	host, err := rack.Host()
	if err != nil {
		return "", "", rack.Detail{}, err
	}
	voices, err := rack.List(host)
	if err != nil {
		return "", "", rack.Detail{}, err
	}
	routed, err = rack.Route(host, strings.TrimSpace(voice), voices)
	if err != nil {
		return "", "", rack.Detail{}, err
	}
	answer, det, err = rack.AskDetail(ctx, host, routed, clean)
	if err != nil {
		return "", "", rack.Detail{}, err
	}
	if _, err := rack.WitnessV(home, routed, clean, answer, flags); err != nil {
		return "", "", rack.Detail{}, err
	}
	return answer, routed, det, nil
}

func appendRun(home string, r Run) error {
	if err := os.MkdirAll(promptsDir(home), 0o755); err != nil {
		return err
	}
	b, err := json.Marshal(r)
	if err != nil {
		return err
	}
	f, err := os.OpenFile(runsPath(home), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.WriteString(string(b) + "\n")
	return err
}

// RunPrompt renders prompt v with vars and measures one answer.
func RunPrompt(home, name string, v int, vars map[string]string, voice string) (Run, error) {
	p, err := Get(home, name, v)
	if err != nil {
		return Run{}, err
	}
	rendered, err := Render(p.Body, vars)
	if err != nil {
		return Run{}, err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 600*time.Second)
	defer cancel()
	answer, routed, det, err := askMeasured(ctx, home, rendered, voice)
	if err != nil {
		return Run{}, err
	}
	id, err := RunID()
	if err != nil {
		return Run{}, err
	}
	input := canonicalVars(vars)
	ts := time.Now().UTC().Format(time.RFC3339)
	r := Run{
		ID: id, TS: ts, Kind: "prompt_run", Prompt: name, Version: p.Version,
		Voice: routed, Override: strings.TrimSpace(voice) != "",
		Input: input, Output: answer,
		Receipt:   Receipt("prompt_run", name, p.Version, input, answer, ts),
		LatencyMs: det.WallMs, EvalCount: det.EvalCount,
	}
	if err := appendRun(home, r); err != nil {
		return Run{}, err
	}
	return r, nil
}

// SeatAsk addresses one declared seat: its declaration rides as context
// (truncated honestly), the method runs once and is never stored beyond
// the run record, the model is a measurement.
func SeatAsk(home, seat, question, voice, method string) (Run, error) {
	seat = strings.TrimSpace(seat)
	question = strings.TrimSpace(question)
	if seat == "" {
		var err error
		seat, question, err = ParseSeat(question)
		if err != nil {
			return Run{}, err
		}
	}
	if question == "" {
		return Run{}, fmt.Errorf("seat_ask needs a question — no seat is asked nothing")
	}
	decl, err := os.ReadFile(filepath.Join(home, "agents", seat+".us"))
	if err != nil {
		return Run{}, fmt.Errorf("refused: seat %q is not declared — enroll first, nothing fabricated", seat)
	}
	ctxText := truncateRunes(string(decl), 2000)
	composed := "You are @" + seat + " of the atlas household.\n" + ctxText
	if strings.TrimSpace(method) != "" {
		composed += "\nMethod (one run only, spent after): " + strings.TrimSpace(method)
	}
	composed += "\n\n" + question
	ctx, cancel := context.WithTimeout(context.Background(), 600*time.Second)
	defer cancel()
	answer, routed, det, err := askMeasured(ctx, home, composed, voice)
	if err != nil {
		return Run{}, err
	}
	id, err := RunID()
	if err != nil {
		return Run{}, err
	}
	ts := time.Now().UTC().Format(time.RFC3339)
	r := Run{
		ID: id, TS: ts, Kind: "seat_ask", Seat: seat,
		Voice: routed, Override: true, Method: strings.TrimSpace(method),
		Input: question, Output: answer,
		Receipt:   Receipt("seat_ask", seat, 0, question, answer, ts),
		LatencyMs: det.WallMs, EvalCount: det.EvalCount,
	}
	if err := appendRun(home, r); err != nil {
		return Run{}, err
	}
	return r, nil
}

// EvalCase is one dataset row: template vars plus the expected answer.
type EvalCase struct {
	Input    map[string]string `json:"input"`
	Expected string            `json:"expected"`
}

// EvalReport scores a prompt version over a dataset, case by case.
type EvalReport struct {
	Prompt  string     `json:"prompt"`
	Version int        `json:"version"`
	Pass    int        `json:"pass"`
	Total   int        `json:"total"`
	Cases   []EvalCase `json:"cases"`
	Got     []string   `json:"got"`
	Results []bool     `json:"results"`
}

// EvalPrompt runs every dataset case and scores exact-match. The dataset
// lives at <home>/evals/<dataset>.json — absent names denied honestly.
func EvalPrompt(home, name string, v int, dataset, voice string) (EvalReport, error) {
	p, err := Get(home, name, v)
	if err != nil {
		return EvalReport{}, err
	}
	raw, err := os.ReadFile(filepath.Join(home, "evals", dataset+".json"))
	if err != nil {
		return EvalReport{}, fmt.Errorf("no such dataset %q — try evals/<name>.json", dataset)
	}
	var cases []EvalCase
	if err := json.Unmarshal(raw, &cases); err != nil || len(cases) == 0 {
		return EvalReport{}, fmt.Errorf("dataset %q is empty or unparsable — nothing is scored", dataset)
	}
	if len(cases) > 100 {
		return EvalReport{}, fmt.Errorf("refused: datasets cap at 100 cases")
	}
	rep := EvalReport{Prompt: name, Version: p.Version, Total: len(cases)}
	for _, c := range cases {
		rendered, err := Render(p.Body, c.Input)
		if err != nil {
			return EvalReport{}, fmt.Errorf("case input %v: %s", c.Input, err)
		}
		ctx, cancel := context.WithTimeout(context.Background(), 600*time.Second)
		answer, routed, det, aerr := askMeasured(ctx, home, rendered, voice)
		cancel()
		if aerr != nil {
			return EvalReport{}, aerr
		}
		pass := Score(c.Expected, answer)
		id, _ := RunID()
		ts := time.Now().UTC().Format(time.RFC3339)
		_ = routed
		_ = appendRun(home, Run{
			ID: id, TS: ts, Kind: "prompt_eval_case", Prompt: name, Version: p.Version,
			Voice: routed, Override: strings.TrimSpace(voice) != "",
			Input: canonicalVars(c.Input), Output: answer,
			Receipt:   Receipt("prompt_eval_case", name, p.Version, canonicalVars(c.Input), answer, ts),
			LatencyMs: det.WallMs, EvalCount: det.EvalCount, Score: &pass,
		})
		rep.Got = append(rep.Got, answer)
		rep.Results = append(rep.Results, pass)
		rep.Cases = append(rep.Cases, c)
		if pass {
			rep.Pass++
		}
	}
	return rep, nil
}

// Compare runs two versions over the same vars and reports honestly.
type CompareReport struct {
	Prompt string `json:"prompt"`
	VerA   int    `json:"verA"`
	VerB   int    `json:"verB"`
	OutA   string `json:"outA"`
	OutB   string `json:"outB"`
	Same   bool   `json:"same"`
	RunA   string `json:"runA"`
	RunB   string `json:"runB"`
}

// ComparePrompt renders both versions, measures both, and diffs by receipt.
func ComparePrompt(home, name string, verA, verB int, vars map[string]string, voice string) (CompareReport, error) {
	ra, err := RunPrompt(home, name, verA, vars, voice)
	if err != nil {
		return CompareReport{}, fmt.Errorf("version A: %s", err)
	}
	rb, err := RunPrompt(home, name, verB, vars, voice)
	if err != nil {
		return CompareReport{}, fmt.Errorf("version B: %s", err)
	}
	return CompareReport{
		Prompt: name, VerA: ra.Version, VerB: rb.Version,
		OutA: ra.Output, OutB: rb.Output, Same: ra.Output == rb.Output,
		RunA: ra.Receipt, RunB: rb.Receipt,
	}, nil
}

// Runs reads the run ledger, newest last, capped.
func Runs(home string, last int) ([]Run, error) {
	f, err := os.Open(runsPath(home))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	defer f.Close()
	var out []Run
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 1<<20), 16<<20)
	for sc.Scan() {
		var r Run
		if json.Unmarshal(sc.Bytes(), &r) != nil {
			continue
		}
		out = append(out, r)
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	if last > 0 && len(out) > last {
		out = out[len(out)-last:]
	}
	return out, nil
}

func canonicalVars(vars map[string]string) string {
	keys := make([]string, 0, len(vars))
	for k := range vars {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	parts := make([]string, 0, len(keys))
	for _, k := range keys {
		parts = append(parts, k+"="+vars[k])
	}
	return strings.Join(parts, ",")
}

func truncateRunes(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n])
}
