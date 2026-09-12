// THE CHECK THAT SCORED LIVENESS AND CALLED IT CORRECTNESS.
//
// EARNED 2026-09-12, by firing the coder flow at a real task. The objective
// said: "it must REFUSE any string carrying a plus build tag INSTEAD OF
// STRIPPING OR DEFAULTING IT." The coder wrote `version_str.split('+')[0]` --
// it stripped, the one behaviour the objective named and forbade -- and the
// flow went GREEN, because `check` asked whether `run_python` said `RAN:` and
// it had. The delivery even wrote both halves of the contradiction in one
// sentence: "It refuses to process any string carrying a plus build tag,
// effectively ignoring it."
//
// A flow that goes green on wrong code is worse than one that goes red: the
// green is the thing a reader trusts, and it launders wrong work to a gate.
//
// `expected` was a literal, so a check could only hold a node to something
// written when the flow was FOLDED. That is enough for liveness and cannot
// express correctness, because what a correct run prints is a fact about THIS
// request. Rendering it lets the check score against a var the run was FIRED
// with -- the HAND states what correct output is, and the machine measures.
package flow

import (
	"strings"
	"testing"

	"atlas/line/internal/play"
)

// expectSpec: a node answers, and an eval holds it to an expectation supplied
// at fire time rather than folded into the spec.
func expectSpec() Spec {
	return Spec{Name: "expect", BudgetS: 600,
		Nodes: []Node{
			{Name: "a", Kind: "ask", Question: "Q"},
			{Name: "v", Kind: "eval", Ref: "a", Match: "contains", Expected: "{{expect}}"},
			{Name: "ok", Kind: "ask", Question: "OK"},
			{Name: "no", Kind: "ask", Question: "NO"},
		},
		Edges: []Edge{
			{From: "a", To: "v", When: "always"},
			{From: "v", To: "ok", When: "pass"},
			{From: "v", To: "no", When: "fail"},
		}}
}

func TestExpectationComesFromTheFiring(t *testing.T) {
	// the hand's expectation is MET
	eng := &stubEngine{answers: map[string]string{"Q": "RAN: x.py\nRefused: build tag"}}
	res, err := Run(t.TempDir(), eng, expectSpec(), map[string]string{"expect": "Refused"})
	if err != nil {
		t.Fatal(err)
	}
	if strings.Join(res.Fired, ",") != "a,ok,v" {
		t.Fatalf("a met expectation must take the pass edge: %v", res.Fired)
	}

	// THE RUN THAT STARTED THIS: it RAN, and it did the wrong thing.
	// Liveness would pass. Correctness must not.
	eng2 := &stubEngine{answers: map[string]string{"Q": "RAN: x.py\n0.1.2"}}
	res2, err := Run(t.TempDir(), eng2, expectSpec(), map[string]string{"expect": "Refused"})
	if err != nil {
		t.Fatal(err)
	}
	if strings.Join(res2.Fired, ",") != "a,no,v" {
		t.Fatalf("code that ran and was WRONG must take the fail edge: %v", res2.Fired)
	}
}

func TestAnExpectationNobodySuppliedIsRefused(t *testing.T) {
	// play.Render refuses a missing var rather than guessing, and an eval is
	// no exception: scoring against an empty string would pass every answer
	// under `contains`, which is a green light nobody set.
	eng := &stubEngine{answers: map[string]string{"Q": "anything at all"}}
	res, err := Run(t.TempDir(), eng, expectSpec(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if res.Verdict != VerdictFail {
		t.Fatalf("verdict = %s, want FAIL when the expectation was never given", res.Verdict)
	}
	for _, f := range res.Fired {
		if f == "ok" {
			t.Fatal("a run with no expectation reached the pass edge")
		}
	}
}

func TestTheFailMessageNamesTheRenderedWant(t *testing.T) {
	// "expected contains {{expect}}" tells a reader nothing about why a run
	// was refused. The rendered value is what belongs in the record.
	eng := &stubEngine{answers: map[string]string{"Q": "0.1.2"}}
	home := t.TempDir()
	res, err := Run(home, eng, expectSpec(), map[string]string{"expect": "Refused"})
	if err != nil {
		t.Fatal(err)
	}
	out, err := nodeOutputs(home, res.Run)
	if err != nil {
		t.Fatal(err)
	}
	got := out["v"]
	if !strings.Contains(got, "Refused") {
		t.Fatalf("the refusal must carry the RENDERED want: %q", got)
	}
	if strings.Contains(got, "{{") {
		t.Fatalf("the refusal leaked the template: %q", got)
	}
}

// AND A FOLDED LITERAL STILL WORKS. Every spec written before this carries a
// plain `expected` and must score exactly as it did.
func TestAFoldedLiteralExpectationIsUnchanged(t *testing.T) {
	eng := &stubEngine{answers: map[string]string{"Q": "yes", "B yes": "b"}}
	res, err := Run(t.TempDir(), eng, branchSpec(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Join(res.Fired, ",") != "a,b,e" {
		t.Fatalf("a literal expectation moved: %v", res.Fired)
	}
}

// NO EVIDENCE IS NOT A VERDICT.
//
// EARNED 2026-09-12, on the run right after the correctness check landed. A
// `verify` node came back in 5.6 SECONDS with no verdict block at all -- it
// called no tool -- and the eval failed it for want of proof. That is the
// right edge to take and the WRONG THING TO RECORD: failing because the work
// was wrong and failing because nobody watched the work are not the same
// fact, and a reader at the gate cannot tell them apart from "fail: expected
// contains X".
//
// And the pass side matters more. The marker a check hunts is a STRING, and a
// seat can write the string without anything having run -- the same
// laundering that made a pasted `RAN:` pass earlier the same day. Requiring
// the block means the evidence was machine-emitted from tool results.
func evidenceSpec() Spec {
	return Spec{Name: "evidence", BudgetS: 600,
		Nodes: []Node{
			{Name: "work", Kind: "run", Question: "do the thing"},
			{Name: "judge", Kind: "eval", Ref: "work", Match: "contains", Expected: "RAN:"},
			{Name: "ok", Kind: "ask", Question: "OK"},
			{Name: "no", Kind: "ask", Question: "NO"},
		},
		Edges: []Edge{
			{From: "work", To: "judge", When: "always"},
			{From: "judge", To: "ok", When: "pass"},
			{From: "judge", To: "no", When: "fail"},
		}}
}

func TestARunNodeThatCalledNoToolCannotBeJudged(t *testing.T) {
	home := t.TempDir()
	// the 5.6-second turn: prose, no verdict block
	eng := &stubEngine{answers: map[string]string{
		"do the thing": "I ran it and it printed RAN: fine.",
	}}
	res, err := Run(home, eng, evidenceSpec(), nil)
	if err != nil {
		t.Fatal(err)
	}
	// IT MUST NOT PASS even though the answer literally contains "RAN:" --
	// a seat wrote that, nothing produced it.
	if strings.Join(res.Fired, ",") != "judge,no,work" {
		t.Fatalf("an unwitnessed answer must take the fail edge: %v", res.Fired)
	}
	out, err := nodeOutputs(home, res.Run)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out["judge"], "NO EVIDENCE") {
		t.Fatalf("the record must say WHY it could not judge: %q", out["judge"])
	}
	if !strings.Contains(out["judge"], "called no tool") {
		t.Fatalf("and name the reason plainly: %q", out["judge"])
	}
}

func TestEvidenceLetsTheJudgementStand(t *testing.T) {
	home := t.TempDir()
	// the same answer, with the machine's own block under it
	eng := &stubEngine{answers: map[string]string{
		"do the thing": "it worked\n\n" + play.ToolVerdictHead +
			"\n  run_python: RAN: probe.py",
	}}
	res, err := Run(home, eng, evidenceSpec(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Join(res.Fired, ",") != "judge,ok,work" {
		t.Fatalf("a witnessed answer must be judged on its merits: %v", res.Fired)
	}

	// and evidence does not excuse being WRONG
	eng2 := &stubEngine{answers: map[string]string{
		"do the thing": "it broke\n\n" + play.ToolVerdictHead +
			"\n  run_python: FAILED (exit 1): probe.py",
	}}
	res2, err := Run(t.TempDir(), eng2, evidenceSpec(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Join(res2.Fired, ",") != "judge,no,work" {
		t.Fatalf("witnessed-and-wrong must still fail: %v", res2.Fired)
	}
}

// AND THE RULE IS ONLY FOR `run` NODES. An ask, prompt or memory node holds no
// tools by definition; demanding tool evidence there would refuse every honest
// eval over a voice.
func TestAVoiceIsJudgedWithoutToolEvidence(t *testing.T) {
	eng := &stubEngine{answers: map[string]string{"Q": "yes", "B yes": "b"}}
	res, err := Run(t.TempDir(), eng, branchSpec(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Join(res.Fired, ",") != "a,b,e" {
		t.Fatalf("an eval over an `ask` node must not need a verdict block: %v", res.Fired)
	}
}

// PROSE IS NOT SCORED AT ALL, AND THIS IS THE RUN THAT PROVED IT HAD TO BE.
//
// 2026-09-12. The objective said the script must print `FIB6: 8`. The coder
// wrote a fibonacci that never sets fib_sequence[1], so it printed `FIB6: 0`.
// The seat reported that ACCURATELY -- "printed `FIB6: 0`, which is not the
// expected output of `FIB6: 8`" -- and a `contains "FIB6: 8"` check found the
// marker INSIDE THE CLAUSE SAYING IT DID NOT MATCH. The verdict passed on a
// sentence reporting the failure.
//
// The marker also arrives by a second road: naming it in the objective puts
// it in the brief, the brief puts it in this node's objective, and the seat
// quotes it back. Requiring the verdict block did not stop either -- the
// block was present, because run_python really had run. Evidence that
// SOMETHING ran is not evidence that the marker came from what ran.
//
// So the answer stays what a person reads at the gate, and the check reads
// only the machine's lines.
func TestTheVerdictScoresEvidenceAndNotProse(t *testing.T) {
	home := t.TempDir()
	// the real shape of that answer: the requirement quoted, the failure
	// reported honestly, and the machine's line carrying what actually ran
	answer := "The run_python tool executed fibonacci.py and printed " +
		"`FIB6: 0`, which is not the expected output of `FIB6: 8`.\n\n" +
		play.ToolVerdictHead + "\n  run_python: RAN: fibonacci.py\n    FIB6: 0"

	eng := &stubEngine{answers: map[string]string{"do the thing": answer}}
	s := evidenceSpec()
	s.Nodes[1].Expected = "FIB6: 8"
	res, err := Run(home, eng, s, nil)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Join(res.Fired, ",") != "judge,no,work" {
		t.Fatalf("the marker was quoted in prose, not printed -- must FAIL: %v", res.Fired)
	}

	// and the same answer with the RIGHT output passes, so the rule did not
	// simply become a refusal of everything
	ok := "It printed the sixth fibonacci number.\n\n" +
		play.ToolVerdictHead + "\n  run_python: RAN: fibonacci.py\n    FIB6: 8"
	eng2 := &stubEngine{answers: map[string]string{"do the thing": ok}}
	res2, err := Run(t.TempDir(), eng2, s, nil)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Join(res2.Fired, ",") != "judge,ok,work" {
		t.Fatalf("evidence carrying the marker must PASS: %v", res2.Fired)
	}
}

// THE OTHER ROAD: the objective itself carrying the marker. A seat that quotes
// its own instructions must not thereby satisfy them.
func TestAnObjectiveCannotSatisfyItself(t *testing.T) {
	// the seat echoes the requirement and the tool printed something else
	answer := "As instructed I will make it print FIB6: 8.\n\n" +
		play.ToolVerdictHead + "\n  run_python: RAN: fibonacci.py\n    FIB6: 0"
	eng := &stubEngine{answers: map[string]string{"do the thing": answer}}
	s := evidenceSpec()
	s.Nodes[1].Expected = "FIB6: 8"
	res, err := Run(t.TempDir(), eng, s, nil)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Join(res.Fired, ",") != "judge,no,work" {
		t.Fatalf("an echoed requirement must not pass as a result: %v", res.Fired)
	}
}
