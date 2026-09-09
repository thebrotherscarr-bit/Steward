package chat

import (
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

func findFixture(t *testing.T, name string) []byte {
	t.Helper()
	for _, c := range []string{
		filepath.Join("tests", "fixtures", name),
		filepath.Join("..", "tests", "fixtures", name),
		filepath.Join("..", "..", "tests", "fixtures", name),
		filepath.Join("..", "..", "..", "tests", "fixtures", name),
	} {
		if b, err := os.ReadFile(c); err == nil {
			return b
		}
	}
	t.Fatalf("fixture %s not found from here", name)
	return nil
}

func TestChatContract(t *testing.T) {
	raw := findFixture(t, "chat_vectors.json")
	var doc struct {
		SessionRe string `json:"session_re"`
		Receipt   struct {
			Session  string `json:"session"`
			Question string `json:"question"`
			Answer   string `json:"answer"`
			TS       string `json:"ts"`
			Receipt  string `json:"receipt"`
		} `json:"receipt_example"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	re, err := regexp.Compile(doc.SessionRe)
	if err != nil {
		t.Fatal(err)
	}
	// Our shape law compiles to the cutter's pattern and our receipt
	// reproduces the pinned example.
	if SessionRe.String() != doc.SessionRe {
		t.Fatalf("session law drifted: code %q vs golden %q", SessionRe.String(), doc.SessionRe)
	}
	if got := Receipt(doc.Receipt.Session, doc.Receipt.Question, doc.Receipt.Answer, doc.Receipt.TS); got != doc.Receipt.Receipt {
		t.Fatalf("receipt drifted: want %s got %s", doc.Receipt.Receipt, got)
	}
	// Fresh session ids hold the shape.
	for i := 0; i < 8; i++ {
		s, err := SessionID()
		if err != nil {
			t.Fatal(err)
		}
		if !re.MatchString(s) {
			t.Fatalf("minted session breaks shape: %q", s)
		}
	}
	// Malformed sessions refused before any I/O.
	if _, err := List(t.TempDir(), "nope", 0); err == nil {
		t.Fatal("malformed session must be refused")
	}
}

func TestChatIsolation(t *testing.T) {
	home := t.TempDir()
	a, err := Start(home, "alice", "")
	if err != nil {
		t.Fatal(err)
	}
	b, err := Start(home, "bob", "")
	if err != nil {
		t.Fatal(err)
	}
	// Writes are done by hand here (no Ollama in unit tests); isolation
	// is what this stroke proves: sessions never see each other.
	rec := func(session, q, ans string, n int) map[string]any {
		ts := "2026-09-09T12:00:00Z"
		return map[string]any{
			"ts": ts, "kind": "chat_turn", "n": n, "session": session,
			"actor": "t", "voice": "v", "question": q, "answer": ans,
			"receipt": Receipt(session, q, ans, ts), "flags": []string{},
		}
	}
	for i, q := range []string{"qa1", "qa2"} {
		if err := appendLine(home, rec(a, q, "aa", i+1)); err != nil {
			t.Fatal(err)
		}
	}
	if err := appendLine(home, rec(b, "qb1", "ab", 1)); err != nil {
		t.Fatal(err)
	}
	ta, _ := List(home, a, 0)
	tb, _ := List(home, b, 0)
	if len(ta) != 2 || len(tb) != 1 {
		t.Fatalf("cross-talk: a=%d b=%d", len(ta), len(tb))
	}
	if ta[0].N != 1 || ta[1].N != 2 || tb[0].N != 1 {
		t.Fatal("turn numbering must be per-session 1..N")
	}
	for _, tn := range append(ta, tb...) {
		if want := Receipt(tn.Session, tn.Question, tn.Answer, tn.TS); want != tn.Receipt {
			t.Fatalf("receipt does not verify for n=%d", tn.N)
		}
	}
	if got := Cancel("c-20260909-120000-deadbeef"); !strings.Contains(got, "nothing in flight") {
		t.Fatalf("quiet cancel must be honest: %q", got)
	}
}
