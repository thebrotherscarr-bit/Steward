package flow

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"atlas/line/internal/play"
)

// stubEngine answers from a canned map; every call is recorded.
type stubEngine struct {
	answers map[string]string
	calls   []string
}

func (s *stubEngine) Ask(_ context.Context, question, _ string) (string, error) {
	s.calls = append(s.calls, "ask:"+question)
	if a, ok := s.answers[question]; ok {
		return a, nil
	}
	return "stub-answer", nil
}

func (s *stubEngine) RunPrompt(name string, _ int, vars map[string]string, _ string) (play.Run, error) {
	s.calls = append(s.calls, "prompt:"+name)
	return play.Run{Output: "stub-prompt:" + name}, nil
}

func (s *stubEngine) SeatAsk(seat, question, _, _ string) (play.Run, error) {
	s.calls = append(s.calls, "seat:"+seat)
	return play.Run{Output: "stub-seat:" + seat + ":" + question}, nil
}

func (s *stubEngine) Turn(_ context.Context, objective, feed, method string) (string, error) {
	s.calls = append(s.calls, "run:"+objective)
	return "stub-run:" + objective, nil
}

func (s *stubEngine) Recall(_, question string) (string, error) {
	s.calls = append(s.calls, "memory:"+question)
	return "stub-memory", nil
}

func branchSpec() Spec {
	return Spec{Name: "branch", BudgetS: 600,
		Nodes: []Node{
			{Name: "a", Kind: "ask", Question: "Q"},
			{Name: "e", Kind: "eval", Ref: "a", Expected: "yes"},
			{Name: "b", Kind: "ask", Question: "B {{out_a}}"},
			{Name: "c", Kind: "ask", Question: "C"},
		},
		Edges: []Edge{
			{From: "a", To: "e", When: "always"},
			{From: "e", To: "b", When: "pass"},
			{From: "e", To: "c", When: "fail"},
		}}
}

func TestBranchPass(t *testing.T) {
	home := t.TempDir()
	eng := &stubEngine{answers: map[string]string{"Q": "yes", "B yes": "b-out"}}
	res, err := Run(home, eng, branchSpec(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if res.Verdict != VerdictComplete {
		t.Fatalf("verdict = %s", res.Verdict)
	}
	if strings.Join(res.Fired, ",") != "a,b,e" {
		t.Fatalf("fired = %v (c must stay silent)", res.Fired)
	}
}

func TestBranchFail(t *testing.T) {
	home := t.TempDir()
	eng := &stubEngine{answers: map[string]string{"Q": "no", "C": "c-out"}}
	res, err := Run(home, eng, branchSpec(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if res.Verdict != VerdictComplete {
		t.Fatalf("verdict = %s", res.Verdict)
	}
	if strings.Join(res.Fired, ",") != "a,c,e" {
		t.Fatalf("fired = %v (b must stay silent)", res.Fired)
	}
}

func TestEvalFailNoBranch(t *testing.T) {
	home := t.TempDir()
	eng := &stubEngine{answers: map[string]string{"Q": "no"}}
	s := Spec{Name: "strict", Nodes: []Node{
		{Name: "a", Kind: "ask", Question: "Q"},
		{Name: "e", Kind: "eval", Ref: "a", Expected: "yes"},
	}, Edges: []Edge{{From: "a", To: "e"}}}
	res, err := Run(home, eng, s, nil)
	if err != nil {
		t.Fatal(err)
	}
	if res.Verdict != VerdictFail {
		t.Fatalf("verdict = %s, want FAIL", res.Verdict)
	}
}

func gateSpec() Spec {
	return Spec{Name: "gated", BudgetS: 600,
		Nodes: []Node{
			{Name: "a", Kind: "ask", Question: "Q"},
			{Name: "g", Kind: "gate", Title: "human review"},
			{Name: "b", Kind: "ask", Question: "B"},
		},
		Edges: []Edge{
			{From: "a", To: "g", When: "always"},
			{From: "g", To: "b", When: "pass"},
			{From: "g", To: "c", When: "fail"},
		}}
}

func TestGatePausesAndResumes(t *testing.T) {
	home := t.TempDir()
	eng := &stubEngine{answers: map[string]string{}}
	// gate spec needs its fail target to exist for validation
	s := gateSpec()
	s.Nodes = append(s.Nodes, Node{Name: "c", Kind: "ask", Question: "C"})
	res, err := Run(home, eng, s, nil)
	if err != nil {
		t.Fatal(err)
	}
	if res.Verdict != VerdictPaused {
		t.Fatalf("verdict = %s, want PAUSED", res.Verdict)
	}
	st, err := Status(home, res.Run)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(st, "PAUSED") || !strings.Contains(st, "budget") {
		t.Fatalf("waterfall must name PAUSED + budget:\n%s", st)
	}
	res2, err := Resume(home, eng, res.Run, "continue")
	if err != nil {
		t.Fatal(err)
	}
	if res2.Verdict != VerdictComplete {
		t.Fatalf("after continue verdict = %s", res2.Verdict)
	}
	if strings.Join(res2.Fired, ",") != "a,b,g" {
		t.Fatalf("fired after resume = %v", res2.Fired)
	}
}

func TestGateStop(t *testing.T) {
	home := t.TempDir()
	eng := &stubEngine{}
	s := Spec{Name: "stopper", Nodes: []Node{
		{Name: "a", Kind: "ask", Question: "Q"},
		{Name: "g", Kind: "gate", Title: "t"},
	}, Edges: []Edge{{From: "a", To: "g"}}}
	res, err := Run(home, eng, s, nil)
	if err != nil {
		t.Fatal(err)
	}
	res2, err := Resume(home, eng, res.Run, "stop")
	if err != nil {
		t.Fatal(err)
	}
	if res2.Verdict != VerdictStopped {
		t.Fatalf("verdict = %s, want STOPPED", res2.Verdict)
	}
	if _, err := Resume(home, eng, res.Run, "continue"); err == nil {
		t.Fatal("a stopped run must not resume")
	}
}

func TestMissingVarFailsNode(t *testing.T) {
	home := t.TempDir()
	eng := &stubEngine{}
	s := Spec{Name: "varless", Nodes: []Node{
		{Name: "a", Kind: "ask", Question: "Hi {{who}}"},
	}, Edges: []Edge{}}
	res, err := Run(home, eng, s, nil)
	if err != nil {
		t.Fatal(err)
	}
	if res.Verdict != VerdictFail {
		t.Fatalf("verdict = %s, want FAIL on missing var", res.Verdict)
	}
	if len(eng.calls) != 0 {
		t.Fatal("a failed render must never reach a voice")
	}
}

func TestDownstreamTemplating(t *testing.T) {
	home := t.TempDir()
	eng := &stubEngine{answers: map[string]string{"Q": "yes", "B yes": "b-out"}}
	if _, err := Run(home, eng, branchSpec(), nil); err != nil {
		t.Fatal(err)
	}
	found := false
	for _, c := range eng.calls {
		if c == "ask:B yes" {
			found = true
		}
	}
	if !found {
		t.Fatalf("downstream must render {{out_a}}: %v", eng.calls)
	}
}

func TestCompareAndReplay(t *testing.T) {
	home := t.TempDir()
	eng := &stubEngine{answers: map[string]string{"Q": "same"}}
	s := Spec{Name: "twice", Nodes: []Node{{Name: "a", Kind: "ask", Question: "Q"}},
		Edges: []Edge{}}
	r1, err := Run(home, eng, s, map[string]string{"in": "1"})
	if err != nil {
		t.Fatal(err)
	}
	eng2 := &stubEngine{answers: map[string]string{"Q": "different"}}
	r2, err := Run(home, eng2, s, map[string]string{"in": "1"})
	if err != nil {
		t.Fatal(err)
	}
	out, err := Compare(home, r1.Run, r2.Run)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "DIFFER") {
		t.Fatalf("compare must name the difference:\n%s", out)
	}
	r3, err := Replay(home, eng, r1.Run)
	if err != nil {
		t.Fatal(err)
	}
	if r3.Run == r1.Run || r3.Verdict != VerdictComplete {
		t.Fatalf("replay must fire fresh: %+v", r3)
	}
	if _, err := Status(home, r3.Run); err != nil {
		t.Fatal(err)
	}
	if _, err := Compare(home, r1.Run, "f-20260909-120000-deadbeef"); err == nil {
		t.Fatal("compare with a ghost run must refuse")
	}
}

func TestRunIsolation(t *testing.T) {
	home := t.TempDir()
	eng := &stubEngine{}
	s := Spec{Name: "iso", Nodes: []Node{{Name: "a", Kind: "ask", Question: "Q"}},
		Edges: []Edge{}}
	r1, _ := Run(home, eng, s, nil)
	r2, _ := Run(home, eng, s, nil)
	if r1.Run == r2.Run {
		t.Fatal("run ids must be unique")
	}
	o1, _ := nodeOutputs(home, r1.Run)
	o2, _ := nodeOutputs(home, r2.Run)
	if len(o1) != 1 || len(o2) != 1 {
		t.Fatal("runs must not share outputs")
	}
}

// TestNoFinishPath is the kept static self-check for this package: no
// verb here finishes, lands, closes, merges or pushes anything — gates
// pause, evals steer, the hand moves. Concat-split literals are joined
// before matching so the check cannot be dodged by string-splitting.
func TestNoFinishPath(t *testing.T) {
	files, err := filepath.Glob("*.go")
	if err != nil {
		t.Fatal(err)
	}
	for _, f := range files {
		if strings.HasSuffix(f, "_test.go") {
			continue
		}
		src, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		flat := strings.ReplaceAll(string(src), "\"+\"", "")
		flat = strings.ReplaceAll(flat, "\" + \"", "")
		lowered := strings.ToLower(flat)
		for _, bad := range []string{"approve(", "ascend(", "resolve(",
			"promote(", "reject(", "\"done\"", "approved"} {
			if strings.Contains(lowered, bad) {
				t.Fatalf("%s: forbidden path %q", f, bad)
			}
		}
	}
}

// THE PASS BRANCH THAT HAD NEVER BEEN REACHABLE (2026-09-12).
//
// `play.Score` is exact match after trim and casefold, and it also scores
// prompt-eval datasets -- so it could not be loosened without rescoring saved
// runs. Meanwhile the builder's label for this field read "what the answer
// should carry", which is `contains` in words. The coder flow believed the
// label: it checked a `run` node, whose answer is the council's prose, for
// "RAN". `verify` came back "RAN: fizz_buzz.py" over correct FizzBuzz and the
// check failed anyway, every time, since the flow was first folded.
func TestEvalMatchModes(t *testing.T) {
	answer := "RAN: fizz_buzz.py\n--- stdout ---\n1\n2\nFizz"

	// contains: the test the label always described
	if !scoreNode(Node{Kind: "eval", Expected: "RAN", Match: "contains"}, answer) {
		t.Fatal("contains did not find RAN in an answer that carries it")
	}
	if !scoreNode(Node{Kind: "eval", Expected: "RAN", Match: "CONTAINS"}, answer) {
		t.Fatal("the MODE is case-blind even though the needle is not")
	}
	if scoreNode(Node{Kind: "eval", Expected: "FAILED", Match: "contains"}, answer) {
		t.Fatal("contains passed on a string the answer does not carry")
	}

	// THE PASS THAT WAS A LIE, measured 2026-09-12 on the first live run after
	// `contains` landed. calculate_sum.py died of a SyntaxError, run_python
	// said so, and the check passed anyway -- because the delivery contained
	// the English word "ran". A word-boundary test would not have caught it:
	// that match WAS a whole word. Case is what separates a verdict from prose.
	failed := `FAILED (exit 1): calculate_sum.py
--- stderr ---
SyntaxError: invalid syntax

The tools that actually ran this turn were write_file, run_python.`
	if scoreNode(Node{Kind: "eval", Expected: "RAN", Match: "contains"}, failed) {
		t.Fatal("a FAILED run scored as a pass; a gate must not tell that lie")
	}
	if !scoreNode(Node{Kind: "eval", Expected: "FAILED", Match: "contains"}, failed) {
		t.Fatal("contains could not find the verdict that is actually there")
	}
	// and the verdict token run_python really emits, on a real success
	if !scoreNode(Node{Kind: "eval", Expected: "RAN:", Match: "contains"}, answer) {
		t.Fatal("contains missed the RAN: verdict line run_python emits")
	}
	if scoreNode(Node{Kind: "eval", Expected: "RAN:", Match: "contains"}, failed) {
		t.Fatal("RAN: matched a run that failed")
	}

	// equals: UNCHANGED, which is the whole reason the mode exists
	if scoreNode(Node{Kind: "eval", Expected: "RAN"}, answer) {
		t.Fatal("an unmarked eval stopped being exact match; saved specs moved")
	}
	if !scoreNode(Node{Kind: "eval", Expected: " ran "}, "RAN") {
		t.Fatal("equals must still trim and casefold, as play.Score does")
	}

	// AN EMPTY EXPECTED NEVER PASSES -- every string contains ""
	for _, m := range []string{"", "equals", "contains"} {
		if scoreNode(Node{Kind: "eval", Expected: "  ", Match: m}, answer) {
			t.Fatalf("match %q passed on a blank expected; that is a green light nobody set", m)
		}
	}
}

func TestValidateGuardsTheMatchMode(t *testing.T) {
	spec := func(n Node) Spec {
		return Spec{Name: "m", Nodes: []Node{{Name: "a", Kind: "ask", Question: "Q"}, n},
			Edges: []Edge{{From: "a", To: "e", When: "always"}}}
	}
	if _, err := Validate(spec(Node{Name: "e", Kind: "eval", Ref: "a", Expected: "x", Match: "roughly"})); err == nil {
		t.Fatal("Validate accepted an unknown match mode")
	} else if !strings.Contains(err.Error(), "equals, contains") {
		t.Fatalf("the refusal must name the set: %v", err)
	}
	// a mode on something with no answer to test is a field that means nothing
	s := Spec{Name: "m", Nodes: []Node{{Name: "a", Kind: "ask", Question: "Q", Match: "contains"}}}
	if _, err := Validate(s); err == nil {
		t.Fatal("Validate accepted `match` on an ask node")
	}
	// and both real modes pass validation
	for _, m := range []string{"", "equals", "contains"} {
		if _, err := Validate(spec(Node{Name: "e", Kind: "eval", Ref: "a", Expected: "x", Match: m})); err != nil {
			t.Fatalf("Validate refused match %q: %v", m, err)
		}
	}
}
