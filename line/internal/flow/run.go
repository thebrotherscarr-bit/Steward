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
	// Turn puts one objective through Manjuel itself -- the council, the law
	// gate, the one Router. THE LINE supplies this; the bare prodEngine below
	// refuses it, because a flow that silently downgraded a `run` to an `ask`
	// would be answering with a model where the estate was asked.
	Turn(ctx context.Context, objective, feed, method string) (string, error)
	Ask(ctx context.Context, question, voice string) (string, error)
	RunPrompt(name string, version int, vars map[string]string, voice string) (play.Run, error)
	SeatAsk(seat, question, voice, method string) (play.Run, error)
	Recall(voice, question string) (string, error)
}

// prodEngine is the live wire: guard, route, ask and witness via play.
type prodEngine struct{ home string }

// Turn refuses on the bare engine. THE LINE overrides it with one that
// reaches the world's Manjuel process; without that override a `run` node has
// no council to reach and must say so rather than answer anyway.
func (p prodEngine) Turn(ctx context.Context, objective, feed, method string) (string, error) {
	return "", fmt.Errorf("refused: this flow has no engine wired, so a `run` " +
		"node has no council to put its objective through. Fire the flow through " +
		"THE LINE (flow_run), with atlas-mcp started with --manjuel")
}

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
		vars := buildVars(inputs, outText)
		if nd.Kind == "gate" {
			if resumeGate == name {
				// Resumed: the hand said continue. The gate stands
				// fired, steers pass-edges, writes nothing more.
				firedSet[name] = true
				outputs[name] = true
				outText[name] = "continue"
				continue
			}
			// The title is RENDERED. A gate the operator walks back to hours
			// later must be able to quote what the run actually produced --
			// "{{work}}" -- or he is deciding blind on a static string.
			// A bad reference does not lose the pause; it shows itself.
			title := nd.Title
			if t, err := play.Render(title, vars); err == nil {
				title = t
			} else {
				title = title + "  [title unrendered: " + err.Error() + "]"
			}
			appendLog(home, map[string]any{
				"run": run, "ts": nowUTC(), "kind": "node",
				"node": name, "nkind": "gate", "status": "paused",
				"title": title,
			})
			r := finishRun(run, VerdictPaused, total, outputs, outText)
			r.PausedNode = name
			return r, nil
		}
		start := time.Now()
		outcome, pok, status, rerr := execNode(ctx, eng, nd, vars, byName)
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
func execNode(ctx context.Context, eng Engine, nd Node, vars map[string]string,
	byName map[string]Node) (string, bool, string, error) {
	switch nd.Kind {
	case "run":
		obj, err := play.Render(nd.Question, vars)
		if err != nil {
			return "", false, "fail", err
		}
		out, err := eng.Turn(ctx, obj, "", nd.Method)
		if err != nil {
			return "", false, "fail", err
		}
		return out, true, "ok", nil
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
		// THE EXPECTATION IS TEMPLATED TOO (2026-09-12). Until now `expected`
		// was a literal, so a check could only ever hold a node to something
		// written when the flow was FOLDED. That is enough for liveness -- is
		// `RAN:` in there -- and cannot express correctness, because what a
		// correct run prints is a fact about THIS run's request.
		//
		// Rendering it here lets a check score against a var the run was
		// FIRED with, which is the whole point: the hand states what correct
		// output looks like and the machine measures it. A model that both
		// states the expectation and writes the code can agree with itself,
		// and agreeing with itself is the disease.
		//
		// `play.Render` refuses a missing var rather than guessing, so a flow
		// that templates an expectation nobody supplied fails HERE instead of
		// scoring against an empty string -- which `scoreNode` refuses anyway.
		want, rerr := play.Render(nd.Expected, vars)
		if rerr != nil {
			return "", false, "fail", rerr
		}
		// NO EVIDENCE IS NOT A VERDICT (2026-09-12). A `run` node puts its
		// objective through the council, and the council may come back having
		// called NO TOOL AT ALL -- one did, in 5.6 seconds, with no verdict
		// block and nothing but prose. Judging that answer is judging a seat's
		// account of work nobody watched happen.
		//
		// IT CANNOT PASS, and that is the point rather than a nicety. The
		// marker a check hunts is a string, and a seat can WRITE the string
		// without anything having run -- the same laundering that made a
		// pasted `RAN:` pass earlier today. Requiring the block means the
		// evidence was machine-emitted from the tool results, not typed.
		//
		// ONLY FOR `run` NODES. An `ask`, `prompt` or `memory` node holds no
		// tools by definition, so demanding tool evidence there would refuse
		// every honest eval over a voice -- `branchSpec`'s does exactly that
		// and must keep working.
		if byName[nd.Ref].Kind == "run" {
			ev, ok := evidenceOf(got)
			if !ok {
				return "fail: NO EVIDENCE -- `" + nd.Ref + "` is a run node that " +
					"called no tool, so nothing in its answer shows what the work " +
					"did. Nothing was judged; expected " + nd.MatchMode() + " " +
					quoted(want), false, "ok", nil
			}
			// AND THE PROSE IS NOT SCORED AT ALL (2026-09-12). Requiring the
			// block proved that something RAN; it did not prove the marker came
			// from what ran. Twice in one day it did not:
			//
			//   an objective naming `FIB6: 8` put that string in the brief, the
			//   brief put it in this node's objective, and the seat quoted it;
			//
			//   and the seat reported the failure ACCURATELY -- "printed
			//   FIB6: 0, which is not the expected output of FIB6: 8" -- so a
			//   substring check found the marker inside the clause saying it
			//   did NOT match.
			//
			// Prose quotes requirements and prose negates them. So the answer
			// stays what a person reads at the gate, and the check reads only
			// the machine's lines.
			got = ev
		}
		// `equals` stays play.Score, which is also what scores prompt-eval
		// datasets -- loosening it there would have rescored saved runs.
		// `contains` is asked for explicitly, per node, and is the test the
		// builder's own label has always described.
		if scoreNode(nd, want, got) {
			return "pass", true, "ok", nil
		}
		// The RENDERED want, not the template: "expected contains {{expect}}"
		// tells a reader nothing about why the run was refused.
		return "fail: expected " + nd.MatchMode() + " " + quoted(want), false, "ok", nil
	}
	return "", false, "fail", fmt.Errorf("refused: unknown kind %q", nd.Kind)
}

// scoreNode makes the test the eval node asked for.
//
// AN EMPTY `expected` NEVER PASSES, and `contains` is the reason it has to be
// said out loud: every string contains "". A check that passes on a blank
// field is a green light nobody set, which is worse than no check at all.
//
// AND `contains` IS CASE-SENSITIVE, WHICH IS THE WHOLE DIFFERENCE BETWEEN THE
// TWO MODES. Measured 2026-09-12, on the first run after `contains` landed:
// the check looked for "RAN" in a `run` node's prose, the script had actually
// died of a SyntaxError, and the check passed anyway -- because the delivery
// said "the tools that actually RAN this turn were...". Lowercase `ran` is an
// ordinary English word, so a case-blind search for it finds English rather
// than a verdict. A word-boundary test would not have helped; that match WAS a
// whole word.
//
// `equals` compares a whole answer to a whole expected value, where case is
// noise, so it stays case-blind (and stays play.Score, which also scores
// prompt-eval datasets). `contains` hunts a MARKER inside prose -- `RAN:`,
// `FAILED`, `PASS` -- and in machine output the case IS the marker. Anything
// looser reports a pass on a failure, which is the one lie a gate must not
// tell.
// evidenceOf returns the machine's own lines from a `run` node's answer -- the
// text after the verdict marker -- and whether there were any.
//
// THE LAST MARKER WINS. `appendVerdicts` strips seat-written markers before
// writing its own, so there should only ever be one; taking the last is the
// belt to that braces, and it costs nothing.
func evidenceOf(answer string) (string, bool) {
	i := strings.LastIndex(answer, play.ToolVerdictHead)
	if i < 0 {
		return "", false
	}
	return strings.TrimSpace(answer[i+len(play.ToolVerdictHead):]), true
}

// `want` is passed in ALREADY RENDERED. The caller owns the templating so
// that this stays one question -- does this answer satisfy this expectation --
// and cannot silently score a template against prose.
func scoreNode(nd Node, want, got string) bool {
	want = strings.TrimSpace(want)
	if want == "" {
		return false
	}
	if nd.MatchMode() == "contains" {
		return strings.Contains(got, want)
	}
	return play.Score(want, got)
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
			// The WHY, not just the word. A waterfall that says "fail" and
			// keeps the reason in the JSONL costs the operator a shell and a
			// grep to learn the engine simply was not open.
			if e, _ := l["error"].(string); e != "" {
				fmt.Fprintf(&b, "      why: %s\n", e)
			}
			// A gate is the whole point of walking away. Coming back, the
			// question has to be ON the waterfall -- whole, untruncated, with
			// the exact command that answers it. It is what he is deciding on.
			if t, _ := l["title"].(string); t != "" {
				for _, ln := range strings.Split(strings.TrimRight(t, "\n"), "\n") {
					fmt.Fprintf(&b, "      %s\n", ln)
				}
				fmt.Fprintf(&b, "      -> flow_resume run=%s decision=continue|stop\n", run)
			}
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
