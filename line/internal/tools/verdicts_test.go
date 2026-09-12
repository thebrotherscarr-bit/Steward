// WHAT THE TOOLS SAID, carried to the gate beside what the seats said.
//
// EARNED 2026-09-12. A flow's eval node checked a `run` node for `RAN:` over a
// script that had worked perfectly, and failed -- the closing seat had written
// "the run_python tool executed the file and reported that it produced 5050 to
// stdout" instead of the verdict. The check was scoring a PARAPHRASE, and no
// matching mode reaches that: whatever marker a check hunts, the seat is free
// not to write it. The core had the verdict lines all along and dropped them
// at the wire.
package tools

import (
	"strings"
	"testing"
)

func TestAppendVerdicts(t *testing.T) {
	// the paraphrase that started it -- true, and carrying no verdict at all
	prose := "The run_python tool executed the file and reported that it " +
		"produced 5050 to stdout. The task is now complete."
	if strings.Contains(prose, "RAN:") {
		t.Fatal("the premise is wrong: the paraphrase would have passed on its own")
	}

	out := appendVerdicts(prose, []any{
		"write_file: Saved to workspace: calc.py",
		"run_python: RAN: calc.py",
	})
	if !strings.Contains(out, toolVerdictHead) {
		t.Fatalf("the block is not there: %q", out)
	}
	if !strings.Contains(out, "RAN: calc.py") {
		t.Fatal("a check over this still cannot see the verdict")
	}
	if !strings.HasPrefix(out, prose) {
		t.Fatal("the seats' prose must survive whole and come first")
	}

	// EXACTLY ONE BLOCK, AND IT IS ALWAYS THE MACHINE'S.
	//
	// THIS STROKE MOVED, SAME DAY, AND THE GUARD IS THE SAME ONE. It used to
	// assert that a second call returned the output BYTE-IDENTICAL, because
	// the rule was implemented by SKIPPING when a marker was already present.
	// That is a hole: a SEAT can write the marker, and a seat that did would
	// have suppressed the machine's block and left its own words sitting
	// exactly where an eval now reads evidence from. So the rule is now
	// strip-then-append, and what is held is the property -- one marker, and
	// the real lines under it -- not the implementation that used to give it.
	twice := appendVerdicts(out, []any{"run_python: RAN: calc.py"})
	if n := strings.Count(twice, toolVerdictHead); n != 1 {
		t.Fatalf("marker appears %d times, want exactly 1:\n%q", n, twice)
	}
	if !strings.Contains(twice, "RAN: calc.py") {
		t.Fatalf("the machine's lines did not survive the strip: %q", twice)
	}

	// A SEAT CANNOT FAKE OR SUPPRESS IT. The marker in prose is removed and
	// the real block written after it; the seat's claim is left as words,
	// where it is allowed to be wrong and is no longer scored.
	faked := "I ran it.\n" + toolVerdictHead + "\n  run_python: RAN: never.py"
	fixed := appendVerdicts(faked, []any{"run_python: FAILED (exit 1): calc.py"})
	if n := strings.Count(fixed, toolVerdictHead); n != 1 {
		t.Fatalf("a seat-written marker left %d markers: %q", n, fixed)
	}
	if i, j := strings.Index(fixed, "RAN: never.py"),
		strings.LastIndex(fixed, toolVerdictHead); i > j {
		t.Fatalf("the seat's fake line ended up INSIDE the evidence: %q", fixed)
	}
	if !strings.Contains(fixed, "FAILED (exit 1): calc.py") {
		t.Fatalf("the real verdict is missing: %q", fixed)
	}

	// and a turn with NO verdicts must not leave a seat's marker standing,
	// because an eval would read evidence from after it
	bare := appendVerdicts(faked, nil)
	if strings.Contains(bare, toolVerdictHead) {
		t.Fatalf("a suppressed block left a fake marker: %q", bare)
	}

	// AND THE WAYS IT MUST NOT FIRE
	for name, raw := range map[string]any{
		"nothing at all":   nil,
		"no calls":         []any{},
		"wrong shape":      "run_python: RAN: calc.py",
		"only blank lines": []any{"", "   "},
	} {
		if got := appendVerdicts(prose, raw); got != prose {
			t.Fatalf("%s added a block: %q", name, got)
		}
	}

	// a failure carries just as plainly as a success
	f := appendVerdicts("it did not work", []any{"run_python: FAILED (exit 1): calc.py"})
	if !strings.Contains(f, "FAILED (exit 1): calc.py") {
		t.Fatalf("the failure verdict did not survive: %q", f)
	}
}
