// Ask prove: routing from the folded goldens, the answer shape, and a
// stub door asked end to end with a witnessed ledger line.
package rack

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func loadAskGolden(t *testing.T) map[string]any {
	t.Helper()
	b, err := os.ReadFile(filepath.Join("..", "..", "..", "tests", "fixtures", "rack_ask.json"))
	if err != nil {
		t.Fatalf("ask golden missing: %s", err)
	}
	var g map[string]any
	if err := json.Unmarshal(b, &g); err != nil {
		t.Fatalf("ask golden unparsable: %s", err)
	}
	return g
}

func speakingOf(caps []any) bool {
	for _, c := range caps {
		if s, _ := c.(string); s == "embedding" {
			return false
		}
	}
	return true
}

func TestRouteMatchesGolden(t *testing.T) {
	g := loadAskGolden(t)
	tags, err := os.ReadFile(filepath.Join("..", "..", "..", "tests", "fixtures", "rack_tags.json"))
	if err != nil {
		t.Fatal(err)
	}
	voices, err := ParseTags(tags)
	if err != nil {
		t.Fatal(err)
	}
	// Rebuild ladder order exactly as Route does.
	byTier := map[string][]string{}
	for _, v := range voices {
		byTier[TierOf(v.Size)] = append(byTier[TierOf(v.Size)], v.Name)
	}
	var ladder []string
	for _, tier := range []string{"scout", "voice", "mind"} {
		names := byTier[tier]
		sortStrings(names)
		ladder = append(ladder, names...)
	}
	shows := g["shows"].(map[string]any)
	var want string
	for _, n := range ladder {
		caps, _ := shows[n].(map[string]any)["capabilities"].([]any)
		if speakingOf(caps) {
			want = n
			break
		}
	}
	if want != g["default_route"].(string) {
		t.Fatalf("default route: computed %q, golden %q", want, g["default_route"])
	}
}

func TestAnswerShapeParses(t *testing.T) {
	g := loadAskGolden(t)
	answer := g["answer"].(map[string]any)
	model, _ := answer["model"].(string)
	resp, _ := answer["response"].(string)
	done, _ := answer["done"].(bool)
	if model == "" || strings.TrimSpace(resp) == "" || !done {
		t.Fatalf("golden answer shape unusable: %v", answer)
	}
}

func TestAskEndToEndStubbed(t *testing.T) {
	tags, _ := os.ReadFile(filepath.Join("..", "..", "..", "tests", "fixtures", "rack_tags.json"))
	g := loadAskGolden(t)
	answerBody, _ := json.Marshal(g["answer"])
	showsBody, _ := json.Marshal(g["shows"])
	var shows map[string]any
	_ = json.Unmarshal(showsBody, &shows)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/tags":
			w.Write(tags)
		case "/api/show":
			var req struct {
				Model string `json:"model"`
			}
			_ = json.NewDecoder(r.Body).Decode(&req)
			doc, _ := json.Marshal(shows[req.Model])
			w.Write(doc)
		case "/api/generate":
			w.Write(answerBody)
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	voices, err := List(srv.URL)
	if err != nil {
		t.Fatal(err)
	}
	voice, err := Route(srv.URL, "", voices)
	if err != nil {
		t.Fatal(err)
	}
	if voice != g["default_route"].(string) {
		t.Fatalf("stub routed %q, want %q", voice, g["default_route"])
	}
	ans, err := Ask(srv.URL, voice, "say it")
	if err != nil {
		t.Fatal(err)
	}
	wantAns, _ := g["answer"].(map[string]any)["response"].(string)
	if ans != wantAns {
		t.Fatalf("answer passthrough broke: %q", ans)
	}
	home := t.TempDir()
	path, err := Witness(home, voice, "say it", ans)
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := os.ReadFile(path)
	var rec map[string]any
	lines := strings.Split(strings.TrimRight(string(raw), "\n"), "\n")
	if len(lines) != 1 {
		t.Fatalf("ledger holds %d lines, want 1", len(lines))
	}
	if err := json.Unmarshal([]byte(lines[0]), &rec); err != nil {
		t.Fatal(err)
	}
	for _, k := range []string{"ts", "kind", "voice", "question", "answer"} {
		if _, ok := rec[k]; !ok {
			t.Fatalf("witness record missing %q", k)
		}
	}
	if rec["kind"] != "rack_ask" || rec["voice"] != voice || rec["question"] != "say it" || rec["answer"] != wantAns {
		t.Fatalf("witness record wrong: %v", rec)
	}

	// Unknown voices refused by name; embedding voices with the reason.
	if _, err := Route(srv.URL, "stranger", voices); err == nil ||
		!strings.Contains(err.Error(), "stranger") {
		t.Fatalf("stranger not refused by name: %v", err)
	}
	embedder, _ := g["embedder"].(string)
	if _, err := Route(srv.URL, embedder, voices); err == nil ||
		!strings.Contains(err.Error(), "embedding") {
		t.Fatalf("embedder not refused with reason: %v", err)
	}
}
