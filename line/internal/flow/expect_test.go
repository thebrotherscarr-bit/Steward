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
