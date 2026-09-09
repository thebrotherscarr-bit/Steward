package engine

import (
	"os"
	"path/filepath"
	"testing"
)

// I8: this package had no tests at all. SittingOpen is pure and it is the
// guard that stands between a second engine and a forked ledger, so it is
// where coverage starts.
func ledger(t *testing.T, body string) string {
	t.Helper()
	g := t.TempDir()
	if err := os.MkdirAll(filepath.Join(g, "sessions"), 0o755); err != nil {
		t.Fatal(err)
	}
	if body != "" {
		if err := os.WriteFile(filepath.Join(g, "sessions", "sessions.jsonl"),
			[]byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return g
}

func TestSittingOpen(t *testing.T) {
	cases := []struct {
		name string
		body string
		open bool
	}{
		{"no ledger at all is not an open sitting", "", false},
		{"a closed last line is not open",
			`{"n":1,"started":"a","ended":"b"}` + "\n", false},
		{"an empty ended IS open",
			`{"n":99,"started":"2026-09-09T06:36:55","ended":""}` + "\n", true},
		{"a missing ended IS open",
			`{"n":7,"started":"x"}` + "\n", true},
		{"only the LAST line decides",
			`{"n":1,"started":"a","ended":""}` + "\n" +
				`{"n":2,"started":"b","ended":"c"}` + "\n", false},
		{"trailing blank lines are skipped",
			`{"n":3,"started":"a","ended":"b"}` + "\n\n\n", false},
		{"CRLF is the ruling and must parse",
			`{"n":4,"started":"a","ended":""}` + "\r\n", true},
		// C5: the whole point. A killed engine leaves a half-written line, and
		// reporting that as "no sitting" invites a second engine into a world
		// whose record is already damaged.
		{"a corrupt last line REFUSES rather than inviting a second engine",
			`{"n":5,"started":"a","ended":"b"}` + "\n" + `{"n":6,"star`, true},
		{"garbage refuses", "not json at all\n", true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			_, _, open := SittingOpen(ledger(t, c.body))
			if open != c.open {
				t.Fatalf("open = %v, want %v", open, c.open)
			}
		})
	}
}

func TestSittingOpenNamesTheSitting(t *testing.T) {
	n, started, open := SittingOpen(ledger(t,
		`{"n":99,"started":"2026-09-09T06:36:55","ended":""}`+"\n"))
	if !open || int(n) != 99 || started != "2026-09-09T06:36:55" {
		t.Fatalf("got (%v,%q,%v); the refusal must be able to NAME the sitting",
			n, started, open)
	}
}

func TestSplitCommand(t *testing.T) {
	for _, c := range []struct {
		in   string
		want []string
	}{
		{`python manjuel.py`, []string{"python", "manjuel.py"}},
		{`"C:\Program Files\py.exe" x.py`, []string{`C:\Program Files\py.exe`, "x.py"}},
		{`  python   x.py  `, []string{"python", "x.py"}},
		{``, nil},
	} {
		got := splitCommand(c.in)
		if len(got) != len(c.want) {
			t.Fatalf("%q -> %v, want %v", c.in, got, c.want)
		}
		for i := range got {
			if got[i] != c.want[i] {
				t.Fatalf("%q -> %v, want %v", c.in, got, c.want)
			}
		}
	}
}

func TestOpenRefusesWithoutACommand(t *testing.T) {
	if _, err := Open("w", t.TempDir(), "  "); err == nil {
		t.Fatal("an unwired engine must refuse, not spawn")
	}
}

func TestOpenRefusesAWorldBeingSatIn(t *testing.T) {
	g := ledger(t, `{"n":12,"started":"now","ended":""}`+"\n")
	_, err := Open("research", g, "python manjuel.py")
	if err == nil {
		t.Fatal("a world with an open sitting must be refused")
	}
	// the refusal has to name it, or the operator cannot act on it
	for _, want := range []string{"research", "12"} {
		if !contains(err.Error(), want) {
			t.Fatalf("refusal %q does not name %q", err, want)
		}
	}
}

func TestOpenNeverCreatesAWorld(t *testing.T) {
	missing := filepath.Join(t.TempDir(), "nope")
	if _, err := Open("w", missing, "python manjuel.py"); err == nil {
		t.Fatal("a missing ground must refuse")
	}
	if _, err := os.Stat(missing); !os.IsNotExist(err) {
		t.Fatal("a world was created; SITTING LAW 4 says a hand never invents one")
	}
}

func TestRingBufferKeepsTheTail(t *testing.T) {
	r := newRing(8)
	r.Write([]byte("0123456789abcdef"))
	if got := r.String(); got != "9abcdef" && got != "89abcdef" {
		t.Fatalf("ring kept %q; it must keep the TAIL, which is where the error is", got)
	}
}

func contains(s, sub string) bool {
	return len(sub) == 0 || (len(s) >= len(sub) && indexOf(s, sub) >= 0)
}

func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}
