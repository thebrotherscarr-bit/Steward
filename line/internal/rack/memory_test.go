// Envelope prove: golden renders byte-exact, refusals pinned, bounds held.
package rack

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestEnvelopeGoldens(t *testing.T) {
	home := filepath.Join("..", "..", "..", "tests", "fixtures", "rack_open_ground")
	cases := []struct {
		file, voice, question string
	}{
		{"memory_q_word.txt", "", "say the word"},
		{"memory_voice_llama.txt", "llama3.2:latest", ""},
		{"memory_latest.txt", "", ""},
	}
	for _, c := range cases {
		got, err := Recall(home, c.voice, c.question)
		if err != nil {
			t.Fatalf("%s: %s", c.file, err)
		}
		want, err := os.ReadFile(filepath.Join("..", "..", "..", "tests", "fixtures", c.file))
		if err != nil {
			t.Fatal(err)
		}
		if got != string(want) {
			t.Fatalf("%s mismatch:\n go %q\n py %q", c.file, got, want)
		}
	}
}

func TestEnvelopeRefusals(t *testing.T) {
	home := filepath.Join("..", "..", "..", "tests", "fixtures", "rack_open_ground")
	if _, err := Recall(home, "", "no such thing"); err == nil ||
		!strings.Contains(err.Error(), "no cited memory for") {
		t.Fatalf("unmatched query not refused: %v", err)
	}
	empty := t.TempDir()
	if _, err := Recall(empty, "", ""); err == nil ||
		!strings.Contains(err.Error(), "ledger is empty") {
		t.Fatalf("empty ledger not refused: %v", err)
	}
}

func TestEnvelopeBounds(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "state"), 0o755); err != nil {
		t.Fatal(err)
	}
	var lines []string
	for i := 0; i < 8; i++ {
		lines = append(lines, `{"ts":"2026-01-0`+string(rune('1'+i))+`T00:00:00Z",`+
			`"kind":"rack_ask","voice":"v","question":"q`+string(rune('a'+i))+`","answer":"a"}`)
	}
	if err := os.WriteFile(filepath.Join(dir, "state", "rack_ledger.jsonl"),
		[]byte(strings.Join(lines, "\n")+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	got, err := Recall(dir, "", "")
	if err != nil {
		t.Fatal(err)
	}
	// Empty filters return the latest single, never the whole book.
	if !strings.Contains(got, `"latest" (1 cited)`) || strings.Contains(got, "(+52 more)") {
		t.Fatalf("latest bound broke:\n%s", got)
	}
	got, err = Recall(dir, "v", "")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(got, "(8 cited)") || !strings.Contains(got, "(+3 earlier, narrow the query)") {
		t.Fatalf("five-cap bound broke:\n%s", got)
	}
}
