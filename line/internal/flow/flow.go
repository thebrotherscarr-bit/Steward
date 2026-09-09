// Package flow is N2's workflow builder: versioned DAG specs with measured
// runs, REVIEW gates, eval branches, compare and replay.
//
// Specs live in <home>/flows/<name>.json — {name, version, budget_s,
// nodes, edges}; history folds as <name>.v<k>.json, never rewritten.
// Node kinds are a closed set: ask | prompt | seat | memory | eval | gate |
// run -- `run` drives a whole Manjuel turn (the council), the others one voice.
// Branches declare parallelism but run sequentially in topo order — one
// rack queue, no interleaved output, the queue visible in the waterfall.
// There is no verb here that finishes a task, lands a memory, or closes a
// gate on the operator's behalf: gate nodes pause, the hand resumes with
// continue|stop, evals only steer edges.
package flow

import (
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
)

// NameRe pins the flow/node name law (cutter holds the same pattern).
var NameRe = regexp.MustCompile(`^[a-z0-9][a-z0-9_-]{0,63}$`)

// RunRe pins the run-id shape law (cutter holds the same pattern).
var RunRe = regexp.MustCompile(`^f-\d{8}-\d{6}-[0-9a-f]{8}$`)

// Kinds is the closed node set. Anything else is refused by name.
var Kinds = map[string]bool{
	"ask": true, "prompt": true, "seat": true,
	"memory": true, "eval": true, "gate": true,
	// `run` is the whole council, not one voice: the objective goes through
	// Manjuel, so the law gate stamps it, the Router runs the tools, the dedup
	// refuses a repeat and the recompose puts every failure in the answer. An
	// `ask` node reaches a bare model; a `run` node reaches the estate.
	"run": true,
}

// Verdicts. COMPLETE means every reached node came back ok; the rest name
// exactly how a run stopped. No verdict here finishes anyone's task.
const (
	VerdictComplete = "COMPLETE"
	VerdictPaused   = "PAUSED"
	VerdictFail     = "FAIL"
	VerdictOverTime = "OUT_OF_TIME"
	VerdictStopped  = "STOPPED"
)

// Node is one step: kind plus the fields its kind reads.
type Node struct {
	Name     string            `json:"name"`
	Kind     string            `json:"kind"`
	Voice    string            `json:"voice,omitempty"`
	Question string            `json:"question,omitempty"`
	Prompt   string            `json:"prompt,omitempty"`
	Version  int               `json:"version,omitempty"`
	Vars     map[string]string `json:"vars,omitempty"`
	Seat     string            `json:"seat,omitempty"`
	Method   string            `json:"method,omitempty"`
	Ref      string            `json:"node,omitempty"`
	Expected string            `json:"expected,omitempty"`
	Title    string            `json:"title,omitempty"`
}

// Edge steers: always fires from a fired source; pass/fail follow the
// source's check outcome (eval score, gate choice).
type Edge struct {
	From string `json:"from"`
	To   string `json:"to"`
	When string `json:"when"`
}

// Spec is one versioned workflow.
type Spec struct {
	Name    string `json:"name"`
	Version int    `json:"version"`
	BudgetS int    `json:"budget_s"`
	Nodes   []Node `json:"nodes"`
	Edges   []Edge `json:"edges"`
}

func flowsDir(home string) string { return filepath.Join(home, "flows") }
func specPath(home, name string, v int) string {
	if v <= 0 {
		return filepath.Join(flowsDir(home), name+".json")
	}
	return filepath.Join(flowsDir(home), fmt.Sprintf("%s.v%d.json", name, v))
}
func runsPath(home string) string { return filepath.Join(flowsDir(home), "runs.jsonl") }

// RunID mints f-YYYYMMDD-HHMMSS-<8hex>.
func RunID() (string, error) {
	var b [4]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return fmt.Sprintf("f-%s-%s", time.Now().UTC().Format("20060102-150405"), hex.EncodeToString(b[:])), nil
}

// Receipt binds one node outcome (cutter reproduces this byte-for-byte).
func Receipt(run, node, output, ts string) string {
	h := sha256.Sum256([]byte(run + "\n" + node + "\n" + output + "\n" + ts))
	return hex.EncodeToString(h[:])
}

// OverBudget is pure: wall milliseconds summed past the ceiling in seconds.
func OverBudget(elapsedMs []int64, budgetS int) bool {
	var sum int64
	for _, e := range elapsedMs {
		sum += e
	}
	return sum > int64(budgetS)*1000
}

// Validate judges a spec: names, kinds, refs, one start, full reach, no
// cycles. It returns the deterministic fire order (Kahn, name-sorted).
func Validate(s Spec) ([]string, error) {
	if !NameRe.MatchString(s.Name) {
		return nil, fmt.Errorf("refused: flow name %q breaks the name law", s.Name)
	}
	if len(s.Nodes) == 0 {
		return nil, fmt.Errorf("refused: flow %q carries no nodes", s.Name)
	}
	byName := map[string]Node{}
	for _, n := range s.Nodes {
		if !NameRe.MatchString(n.Name) {
			return nil, fmt.Errorf("refused: node name %q breaks the name law", n.Name)
		}
		if byName[n.Name].Name != "" {
			return nil, fmt.Errorf("refused: duplicate node name %q", n.Name)
		}
		if !Kinds[n.Kind] {
			return nil, fmt.Errorf("refused: node %q carries unknown kind %q", n.Name, n.Kind)
		}
		if n.Kind == "run" && strings.TrimSpace(n.Question) == "" {
			return nil, fmt.Errorf("refused: run node %q has no objective", n.Name)
		}
		if n.Kind == "eval" && strings.TrimSpace(n.Ref) == "" {
			return nil, fmt.Errorf("refused: eval node %q names no node to check", n.Name)
		}
		byName[n.Name] = n
	}
	for _, n := range s.Nodes {
		if n.Kind == "eval" {
			if _, ok := byName[n.Ref]; !ok {
				return nil, fmt.Errorf("refused: eval node %q checks unknown node %q", n.Name, n.Ref)
			}
		}
	}
	incoming := map[string]int{}
	adj := map[string][]Edge{}
	for name := range byName {
		incoming[name] = 0
	}
	for _, e := range s.Edges {
		if _, ok := byName[e.From]; !ok {
			return nil, fmt.Errorf("refused: edge from unknown node %q", e.From)
		}
		if _, ok := byName[e.To]; !ok {
			return nil, fmt.Errorf("refused: edge to unknown node %q", e.To)
		}
		switch e.When {
		case "", "always":
			e.When = "always"
		case "pass", "fail":
		default:
			return nil, fmt.Errorf("refused: edge %s->%s carries bad when %q", e.From, e.To, e.When)
		}
		if e.When == "fail" && byName[e.From].Kind != "eval" && byName[e.From].Kind != "gate" {
			return nil, fmt.Errorf("refused: fail-edges leave eval/gate nodes only (%s is %s)",
				e.From, byName[e.From].Kind)
		}
		incoming[e.To]++
		adj[e.From] = append(adj[e.From], e)
	}
	var starts []string
	for name, n := range incoming {
		if n == 0 {
			starts = append(starts, name)
		}
	}
	sort.Strings(starts)
	if len(starts) != 1 {
		return nil, fmt.Errorf("refused: want exactly one start, got %d", len(starts))
	}
	ready := append([]string{}, starts...)
	var order []string
	indeg := map[string]int{}
	for k, v := range incoming {
		indeg[k] = v
	}
	for len(ready) > 0 {
		n := ready[0]
		ready = ready[1:]
		order = append(order, n)
		out := append([]Edge{}, adj[n]...)
		sort.Slice(out, func(i, j int) bool { return out[i].To < out[j].To })
		for _, e := range out {
			indeg[e.To]--
			if indeg[e.To] == 0 {
				ready = append(ready, e.To)
			}
		}
		sort.Strings(ready)
	}
	if len(order) != len(byName) {
		return nil, fmt.Errorf("refused: cycle or unreachable node in flow %q", s.Name)
	}
	return order, nil
}

// Save folds a new spec version; history kept whole.
func Save(home string, s Spec) (Spec, error) {
	if !NameRe.MatchString(s.Name) {
		return Spec{}, fmt.Errorf("refused: flow name %q breaks the name law", s.Name)
	}
	if _, err := Validate(s); err != nil {
		return Spec{}, err
	}
	if err := os.MkdirAll(flowsDir(home), 0o755); err != nil {
		return Spec{}, err
	}
	latest := 0
	if cur, err := Get(home, s.Name, 0); err == nil {
		latest = cur.Version
		old, _ := os.ReadFile(specPath(home, s.Name, 0))
		if err := os.WriteFile(specPath(home, s.Name, latest), old, 0o644); err != nil {
			return Spec{}, err
		}
	}
	s.Version = latest + 1
	if s.BudgetS <= 0 {
		s.BudgetS = 600
	}
	b, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return Spec{}, err
	}
	if err := os.WriteFile(specPath(home, s.Name, 0), append(b, '\n'), 0o644); err != nil {
		return Spec{}, err
	}
	return s, nil
}

// Get reads version v (0 = latest); absence denied honestly.
func Get(home, name string, v int) (Spec, error) {
	if !NameRe.MatchString(name) {
		return Spec{}, fmt.Errorf("refused: flow name %q breaks the name law", name)
	}
	if v > 0 {
		if cur, err := Get(home, name, 0); err == nil && cur.Version == v {
			return cur, nil
		}
		raw, err := os.ReadFile(specPath(home, name, v))
		if err != nil {
			return Spec{}, fmt.Errorf("no such flow version: %s v%d — try flow_list", name, v)
		}
		var s Spec
		if err := json.Unmarshal(raw, &s); err != nil {
			return Spec{}, fmt.Errorf("flow %s v%d is corrupt: %s", name, v, err)
		}
		return s, nil
	}
	raw, err := os.ReadFile(specPath(home, name, 0))
	if err != nil {
		return Spec{}, fmt.Errorf("no such flow: %s — try flow_list", name)
	}
	var s Spec
	if err := json.Unmarshal(raw, &s); err != nil {
		return Spec{}, fmt.Errorf("flow %s is corrupt: %s", name, err)
	}
	return s, nil
}

// List names every flow with its latest version.
func List(home string) ([]Spec, error) {
	entries, err := os.ReadDir(flowsDir(home))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	var out []Spec
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		base := strings.TrimSuffix(e.Name(), ".json")
		if !NameRe.MatchString(base) {
			continue
		}
		s, err := Get(home, base, 0)
		if err != nil {
			continue
		}
		out = append(out, s)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out, nil
}
