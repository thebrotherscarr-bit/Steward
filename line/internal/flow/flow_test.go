package flow

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

type goldenDoc struct {
	NameRe string   `json:"name_re"`
	RunRe  string   `json:"run_re"`
	Kinds  []string `json:"kinds"`
	Topo   struct {
		Order []string `json:"order"`
	} `json:"topo_linear"`
	BranchPass map[string]any `json:"branch_pass"`
	BranchFail map[string]any `json:"branch_fail"`
	GatePauses map[string]any `json:"gate_pauses"`
	Receipt    struct {
		Run     string `json:"run"`
		Node    string `json:"node"`
		Output  string `json:"output"`
		TS      string `json:"ts"`
		Receipt string `json:"receipt"`
	} `json:"receipt_example"`
	Budget []struct {
		Elapsed []int64 `json:"elapsed_ms"`
		Budget  int     `json:"budget_s"`
		Over    bool    `json:"over"`
	} `json:"budget_cases"`
	Refusals []struct {
		Why  string `json:"why"`
		Spec Spec   `json:"spec"`
	} `json:"refusals"`
}

func loadGoldens(t *testing.T) goldenDoc {
	t.Helper()
	var doc goldenDoc
	if err := json.Unmarshal(findFixture(t, "flow_vectors.json"), &doc); err != nil {
		t.Fatal(err)
	}
	return doc
}

func TestFlowContract(t *testing.T) {
	doc := loadGoldens(t)
	if NameRe.String() != doc.NameRe {
		t.Fatalf("name law drifted: code %q vs golden %q", NameRe.String(), doc.NameRe)
	}
	if RunRe.String() != doc.RunRe {
		t.Fatalf("run law drifted: code %q vs golden %q", RunRe.String(), doc.RunRe)
	}
	for _, k := range doc.Kinds {
		if !Kinds[k] {
			t.Errorf("golden kind missing in code: %q", k)
		}
	}
	for k := range Kinds {
		found := false
		for _, gk := range doc.Kinds {
			if gk == k {
				found = true
			}
		}
		if !found {
			t.Errorf("code kind missing in goldens: %q", k)
		}
	}
	ex := doc.Receipt
	if r := Receipt(ex.Run, ex.Node, ex.Output, ex.TS); r != ex.Receipt {
		t.Errorf("receipt drifted: want %s got %s", ex.Receipt, r)
	}
	for _, b := range doc.Budget {
		if OverBudget(b.Elapsed, b.Budget) != b.Over {
			t.Errorf("budget mispinned: %+v", b)
		}
	}
	for _, r := range doc.Refusals {
		r.Spec.Name = "probe"
		if _, err := Validate(r.Spec); err == nil {
			t.Errorf("refusal hole: %s", r.Why)
		}
	}
	for i := 0; i < 4; i++ {
		id, err := RunID()
		if err != nil {
			t.Fatal(err)
		}
		if !RunRe.MatchString(id) {
			t.Fatalf("run id breaks shape: %q", id)
		}
	}
}

func TestTopoGolden(t *testing.T) {
	doc := loadGoldens(t)
	linear := Spec{Name: "linear",
		Nodes: []Node{{Name: "a", Kind: "ask"}, {Name: "b", Kind: "ask"}},
		Edges: []Edge{{From: "a", To: "b", When: "always"}},
	}
	order, err := Validate(linear)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Join(order, ",") != strings.Join(doc.Topo.Order, ",") {
		t.Fatalf("topo drifted: %v vs %v", order, doc.Topo.Order)
	}
}

func TestSpecFold(t *testing.T) {
	home := t.TempDir()
	s := Spec{Name: "demo", Nodes: []Node{{Name: "a", Kind: "ask", Question: "hi"}},
		Edges: []Edge{}}
	saved, err := Save(home, s)
	if err != nil {
		t.Fatal(err)
	}
	if saved.Version != 1 {
		t.Fatalf("first save is v1, got v%d", saved.Version)
	}
	s.Nodes = append(s.Nodes, Node{Name: "b", Kind: "ask", Question: "yo"})
	s.Edges = []Edge{{From: "a", To: "b", When: "always"}}
	saved, err = Save(home, s)
	if err != nil {
		t.Fatal(err)
	}
	if saved.Version != 2 {
		t.Fatalf("second save is v2, got v%d", saved.Version)
	}
	v1, err := Get(home, "demo", 1)
	if err != nil || len(v1.Nodes) != 1 {
		t.Fatalf("v1 must survive the fold: %+v %v", v1, err)
	}
	if _, err := Get(home, "demo", 9); err == nil {
		t.Fatal("absent version denied honestly")
	}
	if _, err := Get(home, "ghost", 0); err == nil {
		t.Fatal("absent flow denied honestly")
	}
	list, _ := List(home)
	if len(list) != 1 {
		t.Fatalf("list must name the flow: %+v", list)
	}
}
