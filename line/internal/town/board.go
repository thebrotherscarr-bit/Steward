// Board: the task ledger one beat works. Tasks append as REVIEW and stay
// REVIEW — the board has no verb that moves them further. The operator's
// hand acts outside this package (and outside every CLI verb here); the
// prove replays his move as raw bytes, never through an API, because no
// such API exists.
package town

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// Task is one board row.
type Task struct {
	ID      string `json:"id"`
	SeedKey string `json:"seed_key"`
	Title   string `json:"title"`
	Source  string `json:"source"`
	Status  string `json:"status"`
}

// Board persists tasks.jsonl under dir (created on first seed).
type Board struct {
	dir string
}

// OpenBoard opens (never creates) the board ground.
func OpenBoard(dir string) *Board { return &Board{dir: dir} }

func (b *Board) path() string { return filepath.Join(b.dir, "tasks.jsonl") }

// Fold reads every task ever posted, whatever its status now.
func (b *Board) Fold() ([]Task, error) {
	var out []Task
	err := readJSONL(b.path(), func(m map[string]any) {
		out = append(out, Task{
			ID: strField(m, "id"), SeedKey: strField(m, "seed_key"),
			Title: strField(m, "title"), Source: strField(m, "source"),
			Status: strField(m, "status"),
		})
	})
	return out, err
}

// KnownKeys is every seed_key ever posted — the full-history dedup set.
func (b *Board) KnownKeys() (map[string]bool, error) {
	tasks, err := b.Fold()
	if err != nil {
		return nil, err
	}
	known := map[string]bool{}
	for _, t := range tasks {
		if t.SeedKey != "" {
			known[t.SeedKey] = true
		}
	}
	return known, nil
}

// Seed posts fresh decisions as estate work. Returns the posted tasks.
func (b *Board) Seed(decisions []Decision) ([]Task, error) {
	tasks, err := b.Fold()
	if err != nil {
		return nil, err
	}
	next := len(tasks) + 1
	var posted []Task
	for _, d := range decisions {
		t := Task{
			ID: fmt.Sprintf("T%04d", next), SeedKey: d.Key,
			Title: d.Title, Source: "estate", Status: StatusReview,
		}
		next++
		line, err := json.Marshal(t)
		if err != nil {
			return nil, err
		}
		if err := appendBoardLine(b.path(), string(line)); err != nil {
			return nil, err
		}
		posted = append(posted, t)
	}
	return posted, nil
}

func appendBoardLine(path, line string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.WriteString(line + "\n")
	return err
}

// Check works one trade task read-only: re-read current status, report what
// is seen. Unknown keys are held, never guessed at. The returned note always
// ends at REVIEW — there is no code path here that marks a task done.
func Check(ops string, t Task) (held bool, note string) {
	key := t.SeedKey
	if !strings.HasPrefix(key, "trade:") {
		return true, fmt.Sprintf("held: no instructions for %q — refused, not guessed at", key)
	}
	if strings.HasPrefix(key, "trade:wo:") {
		var wid int64
		_, _ = fmt.Sscanf(key, "trade:wo:%d", &wid)
		for _, w := range OpenWorkOrders(ops) {
			if w.ID == wid {
				vendor := w.Vendor
				if vendor == "" {
					vendor = "unassigned"
				}
				return false, fmt.Sprintf(
					"trade chain intact; work order #%d still open: %s — %s (vendor: %s) [observed]. closing it is the operator's action.",
					wid, w.Property, w.Issue, vendor)
			}
		}
		return false, fmt.Sprintf(
			"trade chain intact; work order #%d is no longer open — closing already recorded [observed].", wid)
	}
	if strings.HasPrefix(key, "trade:patrol:") {
		slug := strings.TrimPrefix(key, "trade:patrol:")
		name := slug
		for _, p := range Properties(ops) {
			if Slug(p) == slug {
				name = p
				break
			}
		}
		when := "never"
		if t, ok := LastInspections(ops)[lower(name)]; ok {
			when = t.In(time.Local).Format("2006-01-02")
		}
		return false, fmt.Sprintf(
			"roster holds %s; last visit to %s: %s [observed]. the visit itself is a person's job.",
			name, name, when)
	}
	return true, fmt.Sprintf("held: unknown trade task key: %s", key)
}

// Beat runs one scheduling cycle over the ops ground against the board:
// draft what is new, work what is unworked, file every return at REVIEW.
// Worked task ids append to worked.jsonl (fold law: the board is only ever
// appended), so a second cycle doubles nothing — matching the oracle, where
// filed counts newly-worked tasks.
type Report struct {
	Issued int      // newly posted this cycle
	Filed  int      // worked this cycle
	Worked []string // notes from tasks worked this cycle
	Held   []string // notes from held tasks
}

func Beat(opsDir, boardDir string, now time.Time) (Report, error) {
	var rep Report
	b := OpenBoard(boardDir)
	known, err := b.KnownKeys()
	if err != nil {
		return rep, err
	}
	fresh := Candidates(opsDir, known, now)
	posted, err := b.Seed(fresh)
	if err != nil {
		return rep, err
	}
	rep.Issued = len(posted)
	worked, err := b.WorkedIDs()
	if err != nil {
		return rep, err
	}
	tasks, err := b.Fold()
	if err != nil {
		return rep, err
	}
	for _, t := range tasks {
		if t.Status != StatusReview || !strings.HasPrefix(t.SeedKey, "trade:") {
			continue
		}
		if worked[t.ID] {
			continue
		}
		held, note := Check(opsDir, t)
		if held {
			rep.Held = append(rep.Held, note)
			continue
		}
		if err := b.MarkWorked(t.ID); err != nil {
			return rep, err
		}
		rep.Worked = append(rep.Worked, note)
		rep.Filed++
	}
	sort.Strings(rep.Worked)
	sort.Strings(rep.Held)
	return rep, nil
}

// WorkedIDs reads the worked set: task ids already worked to REVIEW.
func (b *Board) WorkedIDs() (map[string]bool, error) {
	out := map[string]bool{}
	err := readJSONL(filepath.Join(b.dir, "worked.jsonl"), func(m map[string]any) {
		if id := strField(m, "id"); id != "" {
			out[id] = true
		}
	})
	return out, err
}

// MarkWorked records one task worked (append-only).
func (b *Board) MarkWorked(id string) error {
	line, err := json.Marshal(map[string]string{"id": id})
	if err != nil {
		return err
	}
	return appendBoardLine(filepath.Join(b.dir, "worked.jsonl"), string(line))
}
