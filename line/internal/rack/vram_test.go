package rack

import (
	"encoding/json"
	"os"
	"path/filepath"
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

func TestVramGoldens(t *testing.T) {
	raw := findFixture(t, "rack_plan.json")
	var doc struct {
		Constants struct {
			VramBudget    int64            `json:"vram_budget"`
			GraphOverhead int64            `json:"graph_overhead"`
			KvPerToken    map[string]int64 `json:"kv_per_token"`
			CtxDefault    int              `json:"ctx_default"`
		} `json:"constants"`
		Vectors []struct {
			Name    string   `json:"name"`
			Models  []Voice  `json:"models"`
			Verdict string   `json:"verdict"`
			Total   int64    `json:"total"`
			Evict   []string `json:"evict"`
		} `json:"vectors"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	if doc.Constants.VramBudget != VramBudget || doc.Constants.GraphOverhead != GraphOverhead || doc.Constants.CtxDefault != CtxDefault {
		t.Fatalf("planner constants drifted: %+v", doc.Constants)
	}
	if len(doc.Vectors) != 12 {
		t.Fatalf("want 12 vectors, got %d", len(doc.Vectors))
	}
	for _, v := range doc.Vectors {
		got := Plan(v.Models)
		if got.Verdict != v.Verdict || got.Total != v.Total || strings.Join(got.Evict, ",") != strings.Join(v.Evict, ",") {
			t.Errorf("%s: want %s/%d/%v got %s/%d/%v",
				v.Name, v.Verdict, v.Total, v.Evict, got.Verdict, got.Total, got.Evict)
		}
		if out := RenderPlan(v.Models, got); !strings.Contains(out, v.Verdict) {
			t.Errorf("%s: render missing verdict", v.Name)
		}
	}
}
