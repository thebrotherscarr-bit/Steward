// Package town is the D1 port of Steward's town.py + trade_tasks.py: the
// beat that drafts REVIEW-gated trade tasks, the board they land on, flow
// jitter, and the static no-approve self-check.
//
// ADAPT, stated once: the oracle reads work orders from sqlite; Go's
// standard library has no sqlite, so the port reads the JSONL face
// (workorders.jsonl / properties.jsonl / inspections.jsonl, same logical
// rows the cutter mirrors). D2's trade-skill parity owns the sqlite books;
// this package never writes the ops ground — it reads it, drafts, and every
// result stops at REVIEW.
package town

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

// PatrolDays mirrors trade_tasks.PATROL_DAYS: unvisited this long is due.
const PatrolDays = 30

// Statuses: there is exactly one. review is the operator's gate; closing,
// visiting, and clearing are the operator's hand, never this package's.
// The static self-check (TestNoApprovePath) fails the build if another
// status literal ever lands here.
const StatusReview = "review"

// WorkOrder is one row of the ops workorders.jsonl face.
type WorkOrder struct {
	ID       int64  `json:"id"`
	Property string `json:"property"`
	Issue    string `json:"issue"`
	Vendor   string `json:"vendor"`
	Status   string `json:"status"`
}

// Inspection is one row of inspections.jsonl. TS is "%Y-%m-%dT%H:%M:%S"
// wall-clock local, exactly as the oracle parses it (mktime/strptime).
type Inspection struct {
	TS       string `json:"ts"`
	Property string `json:"property"`
}

func readJSONL(path string, out func(map[string]any)) error {
	f, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil // missing book reads as empty, never an error
		}
		return err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1024*1024), 1024*1024)
	for sc.Scan() {
		line := sc.Text()
		if len(trimSpace(line)) == 0 {
			continue
		}
		var m map[string]any
		if err := json.Unmarshal([]byte(line), &m); err != nil {
			continue // a bad line is skipped, like the oracle's ValueError pass
		}
		out(m)
	}
	return sc.Err()
}

func trimSpace(s string) string {
	i, j := 0, len(s)
	for i < j && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r') {
		i++
	}
	for j > i && (s[j-1] == ' ' || s[j-1] == '\t' || s[j-1] == '\n' || s[j-1] == '\r') {
		j--
	}
	return s[i:j]
}

func strField(m map[string]any, k string) string {
	s, _ := m[k].(string)
	return s
}

func numField(m map[string]any, k string) int64 {
	switch n := m[k].(type) {
	case float64:
		return int64(n)
	case json.Number:
		var v int64
		for _, c := range n.String() {
			if c < '0' || c > '9' {
				return 0
			}
		}
		for _, c := range n.String() {
			v = v*10 + int64(c-'0')
		}
		return v
	}
	return 0
}

// OpenWorkOrders reads every open work order, by id — the JSONL face of the
// oracle's `SELECT ... WHERE status='open' ORDER BY id`.
func OpenWorkOrders(ops string) []WorkOrder {
	var out []WorkOrder
	_ = readJSONL(filepath.Join(ops, "workorders.jsonl"), func(m map[string]any) {
		if strField(m, "status") != "open" {
			return
		}
		out = append(out, WorkOrder{
			ID: numField(m, "id"), Property: strField(m, "property"),
			Issue: strField(m, "issue"), Vendor: strField(m, "vendor"),
			Status: strField(m, "status"),
		})
	})
	// Insertion order is id order on a well-kept book; sort to be sure.
	for i := 1; i < len(out); i++ {
		for j := i; j > 0 && out[j-1].ID > out[j].ID; j-- {
			out[j-1], out[j] = out[j], out[j-1]
		}
	}
	return out
}

// Properties reads enrolled property names from the roster face.
func Properties(ops string) []string {
	var out []string
	_ = readJSONL(filepath.Join(ops, "properties.jsonl"), func(m map[string]any) {
		if n := strField(m, "name"); n != "" {
			out = append(out, n)
		}
	})
	return out
}

const inspectionLayout = "2006-01-02T15:04:05"

// LastInspections folds {lowercased property: latest epoch}, skipping what
// does not parse — the oracle's strptime guard, kept.
func LastInspections(ops string) map[string]time.Time {
	last := map[string]time.Time{}
	_ = readJSONL(filepath.Join(ops, "inspections.jsonl"), func(m map[string]any) {
		t, err := time.ParseInLocation(inspectionLayout, strField(m, "ts"), time.Local)
		if err != nil {
			return
		}
		k := lower(strField(m, "property"))
		if k == "" {
			return
		}
		if prev, ok := last[k]; !ok || t.After(prev) {
			last[k] = t
		}
	})
	return last
}

func lower(s string) string {
	b := []byte(s)
	for i, c := range b {
		if c >= 'A' && c <= 'Z' {
			b[i] = c + ('a' - 'A')
		}
	}
	return string(b)
}
