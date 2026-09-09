// Shipped prove battery for atlas-town (SPEC_COMMANDS: every binary
// answers --prove). Temp grounds only.
//
// The decision bytes below mirror tests/fixtures/town_vectors.json (cut from
// trade_tasks.candidates); the package tests pin those bytes exactly, while
// these strokes prove the live paths — drafting, posting, REVIEW filing,
// dedup, jitter — on temp ground.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"atlas/line/internal/town"
)

type stroke struct {
	name string
	ok   bool
	det  string
}

// mirrorRows is the golden fixture's logical ground, inlined so --prove runs
// anywhere (town_vectors.json pins these same bytes through the package tests).
func mirrorRows() (wo, props, insp []map[string]any) {
	wo = []map[string]any{
		{"id": 1.0, "property": "Alpha House", "issue": "leaking valve", "vendor": "Dale", "status": "open"},
		{"id": 2.0, "property": "Alpha House", "issue": "finished job", "vendor": "Dale", "status": "done"},
	}
	props = []map[string]any{{"name": "Alpha House"}, {"name": "Beta House"}}
	insp = []map[string]any{{"ts": "2026-01-15T10:00:00", "property": "Alpha House"}}
	return wo, props, insp
}

func writeOpsRows(ops string, wo, props, insp []map[string]any) error {
	dump := func(name string, rows []map[string]any) error {
		var sb strings.Builder
		for _, r := range rows {
			b, err := json.Marshal(r)
			if err != nil {
				return err
			}
			sb.Write(b)
			sb.WriteByte('\n')
		}
		return os.WriteFile(filepath.Join(ops, name), []byte(sb.String()), 0o644)
	}
	if err := os.MkdirAll(ops, 0o755); err != nil {
		return err
	}
	if err := dump("workorders.jsonl", wo); err != nil {
		return err
	}
	if err := dump("properties.jsonl", props); err != nil {
		return err
	}
	return dump("inspections.jsonl", insp)
}

func runProve() int {
	strokes := []stroke{}
	check := func(name string, ok bool, det ...any) {
		d := ""
		if len(det) > 0 {
			d = fmt.Sprint(det...)
		}
		strokes = append(strokes, stroke{name, ok, d})
	}

	root, err := os.MkdirTemp("", "atlas_town_prove_")
	if err != nil {
		fmt.Printf("prove refused: %s\n", err)
		return 1
	}
	defer os.RemoveAll(root)
	ops := filepath.Join(root, "state", "ops")
	board := filepath.Join(root, "state", "board")
	wo, props, insp := mirrorRows()
	if err := writeOpsRows(ops, wo, props, insp); err != nil {
		fmt.Printf("prove refused: %s\n", err)
		return 1
	}
	now := time.Date(2026, 9, 15, 12, 0, 0, 0, time.Local)

	// 1. drafting finds the open order and the overdue properties, by key.
	got := town.Candidates(ops, map[string]bool{}, now)
	keys := []string{}
	for _, d := range got {
		keys = append(keys, d.Key)
	}
	check("drafting finds open WO + overdue patrols by key",
		strings.Join(keys, ",") == "trade:wo:1,trade:patrol:alpha-house:2026-09,trade:patrol:beta-house:2026-09",
		strings.Join(keys, "; "))
	check("titles name the need plainly",
		len(got) == 3 && strings.Contains(got[0].Title, "work order #1") &&
			strings.Contains(got[2].Title, "never"))

	// 2. a beat posts estate work and files every return at REVIEW.
	rep, err := town.Beat(ops, board, now)
	check("a beat issues and files", err == nil && rep.Issued == 3 && rep.Filed == 3)
	b := town.OpenBoard(board)
	tasks, _ := b.Fold()
	allReview := len(tasks) == 3
	for _, t := range tasks {
		allReview = allReview && t.Status == town.StatusReview && t.Source == "estate"
	}
	check("every return stops at REVIEW", allReview)
	check("checks report chain and last visit",
		strings.Contains(strings.Join(rep.Worked, "\n"), "still open") &&
			strings.Contains(strings.Join(rep.Worked, "\n"), "last visit"))

	// 3. full-history dedup: a second cycle doubles nothing.
	rep2, err := town.Beat(ops, board, now)
	check("a second cycle doubles nothing", err == nil && rep2.Issued == 0 && rep2.Filed == 0)

	// 4. the operator's replayed hand (raw bytes — no API exists): a done
	// task stays handled.
	f, _ := os.OpenFile(filepath.Join(board, "tasks.jsonl"), os.O_APPEND|os.O_WRONLY, 0o644)
	_, _ = f.WriteString("{\"id\":\"T0001\",\"seed_key\":\"trade:wo:1\",\"title\":\"x\",\"source\":\"estate\",\"status\":\"done\"}\n")
	_ = f.Close()
	known, _ := b.KnownKeys()
	redraft := town.Candidates(ops, known, now)
	stillWO := false
	for _, d := range redraft {
		if d.Key == "trade:wo:1" {
			stillWO = true
		}
	}
	check("a handled task stays handled", !stillWO)

	// 5. unknown kinds held, never guessed at.
	held, _ := town.Check(ops, town.Task{ID: "T9998", SeedKey: "made:up"})
	check("unknown task kinds are held", held)

	// 6. closed ground drafts nothing.
	ops2 := filepath.Join(root, "state2", "ops")
	fresh := now.Add(-24 * time.Hour).In(time.Local).Format("2006-01-02T15:04:05")
	_ = writeOpsRows(ops2,
		[]map[string]any{{"id": 1.0, "property": "Alpha House", "issue": "old", "vendor": "Dale", "status": "done"}},
		[]map[string]any{{"name": "Alpha House"}},
		[]map[string]any{{"ts": fresh, "property": "Alpha House"}})
	check("a quiet ground drafts nothing",
		len(town.Candidates(ops2, map[string]bool{}, now)) == 0)

	// 7. jitter: seeded stats + live window + backwards refusal.
	draws := town.SeededDraws(7, 1000, 2, 10)
	inWin, distinct, sum := true, map[float64]bool{}, 0.0
	for _, d := range draws {
		if d < 2 || d > 10 {
			inWin = false
		}
		distinct[d] = true
		sum += d
	}
	mean := sum / float64(len(draws))
	check("seeded pauses stay in-window, vary, center mid",
		inWin && len(distinct) > 50 && mean > 4.8 && mean < 7.2)
	liveOK := true
	for i := 0; i < 10; i++ {
		if d, err := town.LiveDraw(2, 10); err != nil || d < 2 || d > 10 {
			liveOK = false
		}
	}
	_, backErr := town.LiveDraw(10, 2)
	check("live draws stay in-window; backwards refused", liveOK && backErr != nil)

	width := 0
	for _, s := range strokes {
		if len(s.name) > width {
			width = len(s.name)
		}
	}
	allOk := true
	fmt.Println("\n  THE TOWN -- prove (temp ground; nothing passes REVIEW)")
	for _, s := range strokes {
		status := "PASS"
		if !s.ok {
			status = "FAIL"
			allOk = false
		}
		fmt.Printf("    [%s]  %-*s   %s\n", status, width, s.name, s.det)
	}
	fmt.Println()
	if allOk {
		fmt.Println("  PROVEN. The beat walks, and nothing in it can pass the operator's gate.")
		return 0
	}
	fmt.Println("  A stroke failed. The town does not run on a claim it cannot show.")
	return 1
}
