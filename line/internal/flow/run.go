// Runner: one run at a time per home, branches sequential in topo order,
// gates pausing for the hand, evals steering edges, the wall clock summed
// against the spec budget. Cancel ends the run; a late whole answer may
// still witness (receipted, never partial, never invented).
package flow

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
	"sync"
	"time"

	"atlas/line/internal/play"
	"atlas/line/internal/rack"
)

// Engine carries out single measurements. Production wires rack + play;
// tests stub it with canned answers.
type Engine interface {
	Ask(ctx context.Context, question, voice string) (string, error)
	RunPrompt(name string, version int, vars map[string]string, voice string) (play.Run, error)
	SeatAsk(seat, question, voice, method string) (play.Run, error)
	Recall(voice, question string) (string, error)
}

// prodEngine is the live wire: guard, route, ask and witness via play.
type prodEngine struct{ home string }

func (p prodEngine) Ask(ctx context.Context, question, voice string) (string, error) {
	ans, _, _, err := play.Measure(ctx, p.home, question, voice)
	return ans, err
}

func (p prodEngine) RunPrompt(name string, version int, vars map[string]string, voice string) (play.Run, error) {
	return play.RunPrompt(p.home, name, version, vars, voice)
}

func (p prodEngine) SeatAsk(seat, question, voice, method string) (play.Run, error) {
	return play.SeatAsk(p.home, seat, question, voice, method)
}

func (p prodEngine) Recall(voice, question string) (string, error) {
	return rack.Recall(p.home, voice, question)
}

// Production returns the live engine for a home.
func Production(home string) Engine { return prodEngine{home: home} }

// Result is how one run stands when the runner returns.
type Result struct {
	Run        string
	Verdict    string
	PausedNode string
	Fired      []string
	ElapsedMs  int64
}

// flights tracks live runs so flow_cancel ends the stream honestly.
var (
	flightsMu sync.Mutex
	flights   = map[string]context.CancelFunc{}
)

// Cancel ends a live run; a quiet run is an honest no-op.
func Cancel(run string) string {
	flightsMu.Lock()
	cancel, ok := flights[run]
	flightsMu.Unlock()
	if !ok {
		return fmt.Sprintf("run %s has nothing live — nothing cancelled, nothing claimed", run)
	}
	cancel()
	return fmt.Sprintf("run %s cancelled — reached nodes stand, the rest never fire", run)
}

// Run validates, fires every reachable node, and writes the log.
func Run(home string, eng Engine, s Spec, inputs map[string]string) (Result, error) {
	order, err := Validate(s)
	if err != nil {
		return Result{}, err
	}
	run, err := RunID()
	if err != nil {
		return Result{}, err
	}
	if inputs == nil {
		inputs = map[string]string{}
	}
	appendLog(home, map[string]any{
		"run": run, "flow": s.Name, "version": s.Version,
		"ts": nowUTC(), "kind": "start", "inputs": inputs,
		"budget_s": s.BudgetS, "spec": s,
	})
	return runFrom(home, eng, s, order, inputs, run, nil, nil, nil, nil, "")
}

// specFromStart recovers the fired spec from the run's own start line —
// the transcript is already a complete replay script, no registry needed.
// A saved registry copy is the fallback for old runs.
func specFromStart(home string, start map[string]any) (Spec, error) {
	if raw, ok := start["spec"]; ok {
		b, _ := json.Marshal(raw)
		var s Spec
		if err := json.Unmarshal(b, &s); err == nil && s.Name != "" {
			return s, nil
		}
	}
	flowName, _ := start["flow"].(string)
	version := 0
	if v, ok := start["version"].(float64); ok {
		version = int(v)
	}
	return Get(home, flowName, version)
}

// runFrom continues a run with carried state (empty for a fresh run).
// resumeGate names the gate being resumed with a continue choice.
func runFrom(home string, eng Engine, s Spec, order []string, inputs map[string]string,
	run string, outputs, pass map[string]bool, outText map[string]string,
	elapsed []int64, resumeGate string) (Result, error) {
	if outputs == nil {
		outputs = map[string]bool{}
	}
	if pass == nil {
		pass = map[string]bool{}
	}
	if outText == nil {
		outText = map[string]string{}
	}
	budget := s.BudgetS
	if budget <= 0 {
		budget = 600
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(budget)*time.Second)
	flightsMu.Lock()
	flights[run] = cancel
	flightsMu.Unlock()
	defer func() {
		cancel()
		flightsMu.Lock()
		delete(flights, run)
		flightsMu.Unlock()
	}()
	byName := map[string]Node{}
	for _, n := range s.Nodes {
		byName[n.Name] = n
	}
	firedSet := map[string]bool{}
	for name := range outputs {
		firedSet[name] = true
	}
	resumed := resumeGate != ""
	if resumed {
		pass[resumeGate] = true
		appendLog(home, map[string]any{
			"run": run, "ts": nowUTC(), "kind": "resumed",
			"node": resumeGate, "decision": "continue",
		})
	}
	var total int64
	for _, e := range elapsed {
		total += e
	}
	for _, name := range order {
		if firedSet[name] {
			continue
		}
		if err := ctx.Err(); err != nil {
			return finishRun(run, VerdictOverTime, total, outputs, outText),
				appendStopped(home, run, VerdictOverTime, total)
		}
		if OverBudget(elapsed, budget) {
			return finishRun(run, VerdictOverTime, total, outputs, outText),
				appendStopped(home, run, VerdictOverTime, total)
		}
		if !fires(name, order[0], s.Edges, firedSet, pass) {
			continue
		}
		nd := byName[name]
		if nd.Kind == "gate" {
			if resumeGate == name {
				// Resumed: the hand said continue. The gate stands
				// fired, steers pass-edges, writes nothing more.
				firedSet[name] = true
				outputs[name] = true
				outText[name] = "continue"
				continue
			}
			appendLog(home, map[string]any{
				"run": run, "ts": nowUTC(), "kind": "node",
				"node": name, "nkind": "gate", "status": "paused",
				"title": nd.Title,
			})
			r := finishRun(run, VerdictPaused, total, outputs, outText)
			r.PausedNode = name
			return r, nil
		}
		vars := buildVars(inputs, outText)
		start := time.Now()
		outcome, pok, status, rerr := execNode(ctx, eng, nd, vars)
		ms := time.Since(start).Milliseconds()
		elapsed = append(elapsed, ms)
		total += ms
		ts := nowUTC()
		if rerr != nil {
			appendLog(home, map[string]any{
				"run": run, "ts": ts, "kind": "node", "node": name,
				"nkind": nd.Kind, "status": "fail", "error": rerr.Error(),
				"latency_ms": ms,
			})
			return finishRun(run, VerdictFail, total, outputs, outText),
				appendStopped(home, run, VerdictFail, total)
		}
		receipt := ""
		if outcome != "" {
			receipt = Receipt(run, name, outcome, ts)
		}
		entry := map[string]any{
			"run": run, "ts": ts, "kind": "node", "node": name,
			"nkind": nd.Kind, "status": status, "latency_ms": ms,
		}
		if outcome != "" {
			entry["output"] = outcome
			entry["receipt"] = receipt
		}
		appendLog(home, entry)
		firedSet[name] = true
		outputs[name] = true
		outText[name] = outcome
		if nd.Kind == "eval" || nd.Kind == "gate" {
			pass[name] = pok
		} else {
			pass[name] = true
		}
		if nd.Kind == "eval" && !pok {
			if !hasFailEdge(s.Edges, name) {
				return finishRun(run, VerdictFail, total, outputs, outText),
					appendStopped(home, run, VerdictFail, total)
			}
		}
	}
	markSkipped(home, run, order, firedSet)
	return finishRun(run, VerdictComplete, total, outputs, outText),
		appendStopped(home, run, VerdictComplete, total)
}

// fires reports whether a node has a live in-edge (the start always fires).
func fires(name, start string, edges []Edge, fired map[string]bool, pass map[string]bool) bool {
	if name == start {
		return true
	}
	for _, e := range edges {
		if e.To != name || !fired[e.From] {
			continue
		}
		switch e.When {
		case "", "always":
			return true
		case "pass":
			if pass[e.From] {
				return true
			}
		case "fail":
			if !pass[e.From] {
				return true
			}
		}
	}
	return false
}

func hasFailEdge(edges []Edge, from string) bool {
	for _, e := range edges {
		if e.From == from && e.When == "fail" {
			return true
		}
	}
	return false
}

// execNode runs one node: templates rendered, measurement taken, evals
// scored. Gate nodes never reach here (they pause in the loop).
func execNode(ctx context.Context, eng Engine, nd Node, vars map[string]string) (string, bool, string, error) {
	switch nd.Kind {
	case "ask":
		q, err := play.Render(nd.Question, vars)
		if err != nil {
			return "", false, "fail", err
		}
		ans, err := eng.Ask(ctx, q, nd.Voice)
		if err != nil {
			return "", false, "fail", err
		}
		return ans, true, "ok", nil
	case "prompt":
		pvars := map[string]string{}
		for k, v := range nd.Vars {
			rv, err := play.Render(v, vars)
			if err != nil {
				return "", false, "fail", err
			}
			pvars[k] = rv
		}
		r, err := eng.RunPrompt(nd.Prompt, nd.Version, pvars, nd.Voice)
		if err != nil {
			return "", false, "fail", err
		}
		return r.Output, true, "ok", nil
	case "seat":
		q, err := play.Render(nd.Question, vars)
		if err != nil {
			return "", false, "fail", err
		}
		seat := nd.Seat
		if seat == "" {
			var perr error
			seat, q, perr = play.ParseSeat(q)
			if perr != nil {
				return "", false, "fail", perr
			}
		}
		r, err := eng.SeatAsk(seat, q, nd.Voice, nd.Method)
		if err != nil {
			return "", false, "fail", err
		}
		return r.Output, true, "ok", nil
	case "memory":
		q, err := play.Render(nd.Question, vars)
		if err != nil {
			return "", false, "fail", err
		}
		ans, err := eng.Recall(nd.Voice, q)
		if err != nil {
			return "", false, "fail", err
		}
		return ans, true, "ok", nil
	case "eval":
		got, ok := vars["out_"+nd.Ref]
		if !ok {
			return "", false, "fail", fmt.Errorf("eval node checks node %q with no output yet", nd.Ref)
		}
		if play.Score(nd.Expected, got) {
			return "pass", true, "ok", nil
		}
		return "fail: expected " + quoted(nd.Expected), false, "ok", nil
	}
	return "", false, "fail", fmt.Errorf("refused: unknown kind %q", nd.Kind)
}

func quoted(s string) string {
	b, _ := json.Marshal(s)
	return string(b)
}

func buildVars(inputs, outText map[string]string) map[string]string {
	vars := map[string]string{}
	for k, v := range inputs {
		vars[k] = v
	}
	for k, v := range outText {
		vars["out_"+k] = v
	}
	return vars
}

func finishRun(run, verdict string, total int64, outputs map[string]bool, outText map[string]string) Result {
	fired := []string{}
	for name := range outputs {
		fired = append(fired, name)
	}
	sort.Strings(fired)
	_ = outText
	return Result{Run: run, Verdict: verdict, Fired: fired, ElapsedMs: total}
}

func appendStopped(home, run, verdict string, total int64) error {
	return appendLog(home, map[string]any{
		"run": run, "ts": nowUTC(), "kind": "stopped",
		"verdict": verdict, "elapsed_ms": total,
	})
}

func markSkipped(home, run string, order []string, fired map[string]bool) {
	for _, name := range order {
		if !fired[name] {
			appendLog(home, map[string]any{
				"run": run, "ts": nowUTC(), "kind": "node",
				"node": name, "status": "skipped",
			})
		}
	}
}

func appendLog(home string, rec map[string]any) error {
	if err := os.MkdirAll(flowsDir(home), 0o755); err != nil {
		return err
	}
	b, err := json.Marshal(rec)
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

func nowUTC() string { return time.Now().UTC().Format(time.RFC3339) }

// runLog reads every line for one run, in file order.
func runLog(home, run string) ([]map[string]any, error) {
	f, err := os.Open(runsPath(home))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("no such run: %s", run)
		}
		return nil, err
	}
	defer f.Close()
	var out []map[string]any
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 1<<20), 16<<20)
	for sc.Scan() {
		var doc map[string]any
		if json.Unmarshal(sc.Bytes(), &doc) != nil {
			continue
		}
		if doc["run"] == run {
			out = append(out, doc)
		}
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("no such run: %s", run)
	}
	return out, nil
}

// Resume carries a paused run on: stop ends it STOPPED, continue fires on
// past the gate. Anything not paused is refused honestly.
func Resume(home string, eng Engine, run, decision string) (Result, error) {
	if decision != "continue" && decision != "stop" {
		return Result{}, fmt.Errorf("refused: resume decides continue|stop, got %q", decision)
	}
	lines, err := runLog(home, run)
	if err != nil {
		return Result{}, err
	}
	var start map[string]any
	paused := ""
	resumedAlready := false
	stopped := false
	for _, l := range lines {
		switch l["kind"] {
		case "start":
			start = l
		case "node":
			if l["status"] == "paused" {
				if name, _ := l["node"].(string); name != "" {
					paused = name
				}
			}
		case "resumed":
			resumedAlready = true
		case "stopped":
			stopped = true
		}
	}
	if start == nil {
		return Result{}, fmt.Errorf("run %s carries no start — nothing to resume", run)
	}
	if stopped || (paused != "" && resumedAlready) || paused == "" {
		return Result{}, fmt.Errorf("run %s is not paused — only paused runs resume", run)
	}
	if decision == "stop" {
		appendLog(home, map[string]any{
			"run": run, "ts": nowUTC(), "kind": "resumed",
			"node": paused, "decision": "stop",
		})
		var total int64
		for _, l := range lines {
			if ms, ok := l["latency_ms"].(float64); ok {
				total += int64(ms)
			}
		}
		return Result{Run: run, Verdict: VerdictStopped, PausedNode: paused},
			appendStopped(home, run, VerdictStopped, total)
	}
	s, err := specFromStart(home, start)
	if err != nil {
		return Result{}, err
	}
	order, err := Validate(s)
	if err != nil {
		return Result{}, err
	}
	inputs := map[string]string{}
	if m, ok := start["inputs"].(map[string]any); ok {
		for k, v := range m {
			inputs[k] = fmt.Sprintf("%v", v)
		}
	}
	outputs := map[string]bool{}
	outText := map[string]string{}
	pass := map[string]bool{}
	var elapsed []int64
	for _, l := range lines {
		if l["kind"] != "node" {
			continue
		}
		name, _ := l["node"].(string)
		status, _ := l["status"].(string)
		if status == "ok" {
			outputs[name] = true
			if o, _ := l["output"].(string); o != "" {
				outText[name] = o
			}
			pass[name] = true
			if ms, ok := l["latency_ms"].(float64); ok {
				elapsed = append(elapsed, int64(ms))
			}
		}
	}
	// The gate below fires once, then stands fired; runFrom skips it next.
	return runFrom(home, eng, s, order, inputs, run, outputs, pass, outText, elapsed, paused)
}

// Status renders the waterfall: nodes in fire order with elapsed, the
// budget bar, and exactly how the run stands.
func Status(home, run string) (string, error) {
	lines, err := runLog(home, run)
	if err != nil {
		return "", err
	}
	budget := 600
	flowName := ""
	for _, l := range lines {
		if l["kind"] == "start" {
			flowName, _ = l["flow"].(string)
			if b, ok := l["budget_s"].(float64); ok && b > 0 {
				budget = int(b)
			}
		}
	}
	var b strings.Builder
	fmt.Fprintf(&b, "RUN %s · flow %s · budget %ds\n", run, flowName, budget)
	var total int64
	verdict := ""
	for _, l := range lines {
		switch l["kind"] {
		case "node":
			node, _ := l["node"].(string)
			status, _ := l["status"].(string)
			ms := int64(0)
			if v, ok := l["latency_ms"].(float64); ok {
				ms = int64(v)
				total += ms
			}
			extra := ""
			if r, _ := l["receipt"].(string); r != "" && len(r) >= 16 {
				extra = " · receipt " + r[:16]
			}
			fmt.Fprintf(&b, "  %-14s %-8s %6dms%s\n", node, status, ms, extra)
		case "stopped":
			verdict, _ = l["verdict"].(string)
		}
	}
	// A paused run carries its verdict in the absence of stopped.
	if verdict == "" {
		for _, l := range lines {
			if l["kind"] == "node" && l["status"] == "paused" {
				verdict = VerdictPaused
			}
		}
	}
	bar := budgetBar(total, int64(budget)*1000)
	fmt.Fprintf(&b, "  elapsed %dms / %ds %s\n  verdict: %s\n", total, budget, bar, verdict)
	return b.String(), nil
}

func budgetBar(elapsed, ceiling int64) string {
	const width = 20
	filled := 0
	if ceiling > 0 {
		filled = int(elapsed * width / ceiling)
		if filled > width {
			filled = width
		}
	}
	return "[" + strings.Repeat("#", filled) + strings.Repeat("-", width-filled) + "]"
}

// CompareRow holds two runs' shared nodes side by side.
type CompareRow struct {
	Node string
	OutA string
	OutB string
	Same bool
}

// Compare walks two runs' node outputs; same spec or not, outputs judge.
func Compare(home, runA, runB string) (string, error) {
	outA, err := nodeOutputs(home, runA)
	if err != nil {
		return "", err
	}
	outB, err := nodeOutputs(home, runB)
	if err != nil {
		return "", err
	}
	names := map[string]bool{}
	for n := range outA {
		names[n] = true
	}
	for n := range outB {
		names[n] = true
	}
	var sorted []string
	for n := range names {
		sorted = append(sorted, n)
	}
	sort.Strings(sorted)
	var b strings.Builder
	fmt.Fprintf(&b, "COMPARE %s vs %s\n", runA, runB)
	for _, n := range sorted {
		a, oka := outA[n]
		bb, okb := outB[n]
		switch {
		case !oka:
			fmt.Fprintf(&b, "  %-14s only in B\n", n)
		case !okb:
			fmt.Fprintf(&b, "  %-14s only in A\n", n)
		case a == bb:
			fmt.Fprintf(&b, "  %-14s IDENTICAL\n", n)
		default:
			fmt.Fprintf(&b, "  %-14s DIFFER\n    A: %s\n    B: %s\n", n,
				truncate(a, 200), truncate(bb, 200))
		}
	}
	return b.String(), nil
}

func nodeOutputs(home, run string) (map[string]string, error) {
	lines, err := runLog(home, run)
	if err != nil {
		return nil, err
	}
	out := map[string]string{}
	for _, l := range lines {
		if l["kind"] != "node" || l["status"] != "ok" {
			continue
		}
		name, _ := l["node"].(string)
		o, _ := l["output"].(string)
		out[name] = o
	}
	return out, nil
}

// Replay re-fires a run's spec and inputs under a fresh run id, stamped
// with its origin. The transcript is already a complete replay script.
func Replay(home string, eng Engine, run string) (Result, error) {
	lines, err := runLog(home, run)
	if err != nil {
		return Result{}, err
	}
	var start map[string]any
	for _, l := range lines {
		if l["kind"] == "start" {
			start = l
			break
		}
	}
	if start == nil {
		return Result{}, fmt.Errorf("run %s carries no start — nothing to replay", run)
	}
	s, err := specFromStart(home, start)
	if err != nil {
		return Result{}, err
	}
	order, err := Validate(s)
	if err != nil {
		return Result{}, err
	}
	inputs := map[string]string{}
	if m, ok := start["inputs"].(map[string]any); ok {
		for k, v := range m {
			inputs[k] = fmt.Sprintf("%v", v)
		}
	}
	fresh, err := RunID()
	if err != nil {
		return Result{}, err
	}
	appendLog(home, map[string]any{
		"run": fresh, "flow": s.Name, "version": s.Version,
		"ts": nowUTC(), "kind": "start", "inputs": inputs,
		"budget_s": s.BudgetS, "replay_of": run,
	})
	return runFrom(home, eng, s, order, inputs, fresh, nil, nil, nil, nil, "")
}

// ListRuns names runs for a flow (empty flow = all), newest last.
func ListRuns(home, flow string, last int) (string, error) {
	f, err := os.Open(runsPath(home))
	if err != nil {
		if os.IsNotExist(err) {
			return "no runs yet — fire one with flow_run", nil
		}
		return "", err
	}
	defer f.Close()
	type row struct {
		run     string
		flow    string
		verdict string
		ts      string
	}
	byRun := map[string]*row{}
	var orderRuns []string
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 1<<20), 16<<20)
	for sc.Scan() {
		var doc map[string]any
		if json.Unmarshal(sc.Bytes(), &doc) != nil {
			continue
		}
		id, _ := doc["run"].(string)
		if id == "" {
			continue
		}
		r, ok := byRun[id]
		if !ok {
			r = &row{run: id}
			byRun[id] = r
			orderRuns = append(orderRuns, id)
		}
		switch doc["kind"] {
		case "start":
			r.flow, _ = doc["flow"].(string)
			r.ts, _ = doc["ts"].(string)
		case "stopped":
			r.verdict, _ = doc["verdict"].(string)
		case "node":
			if doc["status"] == "paused" && r.verdict == "" {
				r.verdict = VerdictPaused
			}
		}
	}
	var b strings.Builder
	n := 0
	for _, id := range orderRuns {
		r := byRun[id]
		if flow != "" && r.flow != flow {
			continue
		}
		fmt.Fprintf(&b, "  %s · flow %s · %s · %s\n", r.run, r.flow, r.verdict, r.ts)
		n++
	}
	if n == 0 {
		return "no runs yet — fire one with flow_run", nil
	}
	_ = last
	return fmt.Sprintf("RUNS — %d:\n%s", n, b.String()), nil
}

func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n])
}
