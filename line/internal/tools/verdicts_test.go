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

	// ONCE ONLY. The core may recompose these itself one day.
	if twice := appendVerdicts(out, []any{"run_python: RAN: calc.py"}); twice != out {
		t.Fatal("the news reached the gate twice")
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
