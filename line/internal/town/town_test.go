// Town prove: oracle goldens drive the port, behaviors match the river,
// and the static self-check holds the gate. Hermetic: temp grounds, fixed
// clock, seeded jitter.
package town

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

type townGoldens struct {
	Vectors []struct {
		ID        string     `json:"id"`
		OK        bool       `json:"ok"`
		Decisions [][]string `json:"decisions"`
	} `json:"vectors"`
	Inputs struct {
		Mirror struct {
			Workorders  []map[string]any `json:"workorders"`
			Properties  []map[string]any `json:"properties"`
			Inspections []map[string]any `json:"inspections"`
		} `json:"mirror"`
	} `json:"inputs"`
}

func loadGoldens(t *testing.T) townGoldens {
	t.Helper()
	b, err := os.ReadFile(filepath.Join("..", "..", "..", "tests", "fixtures", "town_vectors.json"))
	if err != nil {
		t.Fatalf("goldens missing: %s", err)
	}
	var g townGoldens
	if err := json.Unmarshal(b, &g); err != nil {
		t.Fatalf("goldens unparsable: %s", err)
	}
	byID := map[string]bool{}
	for _, v := range g.Vectors {
		byID[v.ID] = true
		if !v.OK {
			t.Fatalf("golden %q cut failing", v.ID)
		}
	}
	for _, id := range []string{"draft", "dedup", "recur", "closed"} {
		if !byID[id] {
			t.Fatalf("golden %q absent", id)
		}
	}
	return g
}

// fixedNow is the cutter's mid-month noon local: same box, same month key.
func fixedNow() time.Time { return time.Date(2026, 9, 15, 12, 0, 0, 0, time.Local) }
func nextMonth() time.Time {
	return time.Date(2026, 10, 15, 12, 0, 0, 0, time.Local)
}

func writeOps(t *testing.T, dir string, wo, props, insp []map[string]any) string {
	t.Helper()
	ops := filepath.Join(dir, "ops")
	if err := os.MkdirAll(ops, 0o755); err != nil {
		t.Fatal(err)
	}
	dump := func(name string, rows []map[string]any) {
		var sb strings.Builder
		for _, r := range rows {
			b, err := json.Marshal(r)
			if err != nil {
				t.Fatal(err)
			}
			sb.Write(b)
			sb.WriteByte('\n')
		}
		if err := os.WriteFile(filepath.Join(ops, name), []byte(sb.String()), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	dump("workorders.jsonl", wo)
	dump("properties.jsonl", props)
	dump("inspections.jsonl", insp)
	return ops
}

func decisionsOf(ds []Decision) [][]string {
	var out [][]string
	for _, d := range ds {
		out = append(out, []string{d.Key, d.Title})
	}
	return out
}

func equalDecisions(a, b [][]string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if len(a[i]) != 2 || len(b[i]) != 2 || a[i][0] != b[i][0] || a[i][1] != b[i][1] {
			return false
		}
	}
	return true
}

func TestGoldenDraft(t *testing.T) {
	g := loadGoldens(t)
	dir := t.TempDir()
	ops := writeOps(t, dir, g.Inputs.Mirror.Workorders, g.Inputs.Mirror.Properties, g.Inputs.Mirror.Inspections)
	got := decisionsOf(Candidates(ops, map[string]bool{}, fixedNow()))
	if !equalDecisions(got, g.Vectors[0].Decisions) {
		t.Fatalf("draft mismatch:\n go %q\n py %q", got, g.Vectors[0].Decisions)
	}
}

func TestGoldenRecurAndDedup(t *testing.T) {
	g := loadGoldens(t)
	dir := t.TempDir()
	ops := writeOps(t, dir, g.Inputs.Mirror.Workorders, g.Inputs.Mirror.Properties, g.Inputs.Mirror.Inspections)
	got := decisionsOf(Candidates(ops, map[string]bool{}, nextMonth()))
	if !equalDecisions(got, g.Vectors[2].Decisions) {
		t.Fatalf("recur mismatch:\n go %q\n py %q", got, g.Vectors[2].Decisions)
	}
	known := map[string]bool{}
	for _, d := range g.Vectors[0].Decisions {
		known[d[0]] = true
	}
	if rest := Candidates(ops, known, fixedNow()); len(rest) != 0 {
		t.Fatalf("dedup failed: %d re-drafted", len(rest))
	}
}

func TestGoldenClosed(t *testing.T) {
	dir := t.TempDir()
	fresh := fixedNow().Add(-24 * time.Hour).In(time.Local).Format(inspectionLayout)
	ops := writeOps(t, dir,
		[]map[string]any{{"id": 1.0, "property": "Alpha House", "issue": "old job", "vendor": "Dale", "status": "done"}},
		[]map[string]any{{"name": "Alpha House"}},
		[]map[string]any{{"ts": fresh, "property": "Alpha House"}})
	if got := Candidates(ops, map[string]bool{}, fixedNow()); len(got) != 0 {
		t.Fatalf("quiet ground drafted %d", len(got))
	}
}

func TestBeatFilesAtReview(t *testing.T) {
	g := loadGoldens(t)
	dir := t.TempDir()
	ops := writeOps(t, dir, g.Inputs.Mirror.Workorders, g.Inputs.Mirror.Properties, g.Inputs.Mirror.Inspections)
	board := filepath.Join(dir, "board")
	rep, err := Beat(ops, board, fixedNow())
	if err != nil {
		t.Fatal(err)
	}
	if rep.Issued != 3 || rep.Filed != 3 {
		t.Fatalf("want issued=3 filed=3, got %+v", rep)
	}
	b := OpenBoard(board)
	tasks, err := b.Fold()
	if err != nil {
		t.Fatal(err)
	}
	for _, task := range tasks {
		if task.Status != StatusReview || task.Source != "estate" {
			t.Fatalf("task not REVIEW estate work: %+v", task)
		}
	}
	// Notes name what was seen, plainly.
	joined := strings.Join(rep.Worked, "\n")
	for _, want := range []string{"still open", "last visit"} {
		if !strings.Contains(joined, want) {
			t.Fatalf("notes miss %q:\n%s", want, joined)
		}
	}
	// A second cycle doubles nothing.
	rep2, err := Beat(ops, board, fixedNow())
	if err != nil {
		t.Fatal(err)
	}
	if rep2.Issued != 0 || rep2.Filed != 0 {
		t.Fatalf("second cycle doubled: %+v", rep2)
	}
	// The operator's replayed hand (raw bytes, no API — none exists):
	// a done task stays handled.
	done, _ := json.Marshal(map[string]string{
		"id": "T0001", "seed_key": "trade:wo:1", "title": "x",
		"source": "estate", "status": "done"})
	f, err := os.OpenFile(filepath.Join(board, "tasks.jsonl"), os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		t.Fatal(err)
	}
	_, _ = f.WriteString(string(done) + "\n")
	_ = f.Close()
	known, err := b.KnownKeys()
	if err != nil {
		t.Fatal(err)
	}
	for _, d := range Candidates(ops, known, fixedNow()) {
		if d.Key == "trade:wo:1" {
			t.Fatal("handled task re-drafted")
		}
	}
}

func TestJitterStats(t *testing.T) {
	draws := SeededDraws(7, 2000, 2, 10)
	for _, d := range draws {
		if d < 2 || d > 10 {
			t.Fatalf("draw out of window: %f", d)
		}
	}
	seen := map[float64]bool{}
	sum := 0.0
	for _, d := range draws {
		seen[d] = true
		sum += d
	}
	if len(seen) < 100 {
		t.Fatalf("draws do not vary: %d distinct", len(seen))
	}
	if mean := sum / float64(len(draws)); mean < 4.8 || mean > 7.2 {
		t.Fatalf("mean %f far from window mid 6", mean)
	}
	for i := 0; i < 20; i++ {
		d, err := LiveDraw(2, 10)
		if err != nil || d < 2 || d > 10 {
			t.Fatalf("live draw out of window: %f %v", d, err)
		}
	}
	if _, err := LiveDraw(10, 2); err == nil {
		t.Fatal("backwards window accepted")
	}
}

// TestNoApprovePath is the kept static self-check: no status but review,
// no approve/ascend path, in non-test sources. Concatenated literals
// ("appr"+"ove(") are joined before matching, so the check cannot be
// dodged by string-splitting — the oracle's own trick, turned around.
func TestNoApprovePath(t *testing.T) {
	files, err := filepath.Glob("*.go")
	if err != nil {
		t.Fatal(err)
	}
	for _, f := range files {
		if strings.HasSuffix(f, "_test.go") {
			continue
		}
		src, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		flat := strings.ReplaceAll(string(src), "\"+\"", "")
		flat = strings.ReplaceAll(flat, "\" + \"", "")
		lowered := strings.ToLower(flat)
		for _, bad := range []string{"approve(", "ascend(", "\"done\"", "\"approved\"", "statusdone", ".status ="} {
			if strings.Contains(lowered, bad) {
				t.Fatalf("%s: forbidden path %q", f, bad)
			}
		}
		// The only Status: value in the package: writes must name
		// StatusReview; reads (strField) and the field declaration pass.
		for i, line := range strings.Split(flat, "\n") {
			if strings.Contains(line, "Status:") && !strings.Contains(line, "Status: StatusReview") &&
				!strings.Contains(line, "Status string") && !strings.Contains(line, "strField") {
				t.Fatalf("%s:%d: non-review status: %s", f, i+1, strings.TrimSpace(line))
			}
		}
	}
}
