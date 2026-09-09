package play

import (
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
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

func TestPlayContract(t *testing.T) {
	raw := findFixture(t, "playground_vectors.json")
	var doc struct {
		NameRe  string   `json:"name_re"`
		Good    []string `json:"good_names"`
		Bad     []string `json:"bad_names"`
		Render  struct {
			Body string            `json:"body"`
			Vars map[string]string `json:"vars"`
			Want string            `json:"want"`
		} `json:"render"`
		Receipt struct {
			Kind    string `json:"kind"`
			Prompt  string `json:"prompt"`
			Version int    `json:"version"`
			Input   string `json:"input"`
			Output  string `json:"output"`
			TS      string `json:"ts"`
			Receipt string `json:"receipt"`
		} `json:"receipt_example"`
		Seat struct {
			Re      string `json:"re"`
			Cases   []struct {
				Raw      string `json:"raw"`
				Seat     string `json:"seat"`
				Question string `json:"question"`
			} `json:"cases"`
			Refused []string `json:"refused"`
		} `json:"seat_shape"`
		Pairs []struct {
			Expected string `json:"expected"`
			Got      string `json:"got"`
			Pass     bool   `json:"pass"`
		} `json:"eval_pairs"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	if NameRe.String() != doc.NameRe {
		t.Fatalf("name law drifted: code %q vs golden %q", NameRe.String(), doc.NameRe)
	}
	if SeatRe.String() != doc.Seat.Re {
		t.Fatalf("seat shape drifted: code %q vs golden %q", SeatRe.String(), doc.Seat.Re)
	}
	_ = regexp.MustCompile(doc.NameRe) // the golden compiles too
	for _, n := range doc.Good {
		if !NameRe.MatchString(n) {
			t.Errorf("good name refused: %q", n)
		}
	}
	for _, n := range doc.Bad {
		if NameRe.MatchString(n) {
			t.Errorf("bad name admitted: %q", n)
		}
	}
	got, err := Render(doc.Render.Body, doc.Render.Vars)
	if err != nil || got != doc.Render.Want {
		t.Errorf("render = %q, %v; want %q", got, err, doc.Render.Want)
	}
	if _, err := Render("Hello {{role}}.", map[string]string{}); err == nil {
		t.Error("missing var must refuse")
	}
	ex := doc.Receipt
	if r := Receipt(ex.Kind, ex.Prompt, ex.Version, ex.Input, ex.Output, ex.TS); r != ex.Receipt {
		t.Errorf("receipt drifted: want %s got %s", ex.Receipt, r)
	}
	for _, c := range doc.Seat.Cases {
		s, q, err := ParseSeat(c.Raw)
		if err != nil || s != c.Seat || q != c.Question {
			t.Errorf("seat misparsed %q: %q %q %v", c.Raw, s, q, err)
		}
	}
	for _, r := range doc.Seat.Refused {
		if _, _, err := ParseSeat(r); err == nil {
			t.Errorf("seat shape admitted %q", r)
		}
	}
	for _, p := range doc.Pairs {
		if Score(p.Expected, p.Got) != p.Pass {
			t.Errorf("eval misscored %+v", p)
		}
	}
}

func TestPromptFold(t *testing.T) {
	home := t.TempDir()
	if _, err := Save(home, "BAD NAME", "body", ""); err == nil {
		t.Fatal("bad name must refuse")
	}
	p1, err := Save(home, "hello", "Hello {{name}}.", "greeter")
	if err != nil {
		t.Fatal(err)
	}
	if p1.Version != 1 {
		t.Fatalf("first save is v1, got v%d", p1.Version)
	}
	p2, err := Save(home, "hello", "Hi {{name}}!", "greeter")
	if err != nil {
		t.Fatal(err)
	}
	if p2.Version != 2 {
		t.Fatalf("second save is v2, got v%d", p2.Version)
	}
	// The old latest folds whole, never rewritten.
	old, err := Get(home, "hello", 1)
	if err != nil || old.Body != "Hello {{name}}." {
		t.Fatalf("v1 must survive the fold: %+v %v", old, err)
	}
	cur, _ := Get(home, "hello", 0)
	if cur.Body != "Hi {{name}}!" {
		t.Fatalf("latest must be v2: %q", cur.Body)
	}
	if _, err := Get(home, "hello", 9); err == nil {
		t.Fatal("absent version denied honestly")
	}
	list, _ := List(home)
	if len(list) != 1 || list[0].Name != "hello" {
		t.Fatalf("list must name the prompt: %+v", list)
	}
}
