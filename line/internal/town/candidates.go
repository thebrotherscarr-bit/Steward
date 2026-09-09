// Candidates: what the trade needs this cycle (trade_tasks.candidates,
// ported decision-for-decision).
//
//   * each OPEN work order   -> "trade:wo:<id>"
//   * each overdue property  -> "trade:patrol:<slug>:<YYYY-MM>" (the month is
//     part of the key, so patrols recur naturally)
//
// known holds every seed_key already in the board history, any status —
// those are skipped, so handled work is never re-posted. `now` is passed
// in (never wall-clock inside): hermetic cycles, hermetic proves.
package town

import (
	"fmt"
	"strings"
	"time"
)

// Decision is one drafted task: its stable key and its plain title.
type Decision struct {
	Key   string
	Title string
}

// Slug mirrors trade_tasks._slug: [^a-z0-9]+ -> "-", trimmed.
func Slug(name string) string {
	var sb strings.Builder
	dash := false
	for _, r := range lower(name) {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			sb.WriteRune(r)
			dash = false
		} else if !dash {
			sb.WriteRune('-')
			dash = true
		}
	}
	s := sb.String()
	s = strings.Trim(s, "-")
	if s == "" {
		return "unnamed"
	}
	return s
}

// Candidates drafts this cycle's tasks over the ops ground.
func Candidates(ops string, known map[string]bool, now time.Time) []Decision {
	var out []Decision
	for _, w := range OpenWorkOrders(ops) {
		key := fmt.Sprintf("trade:wo:%d", w.ID)
		if known[key] {
			continue
		}
		vendor := w.Vendor
		if vendor == "" {
			vendor = "unassigned"
		}
		out = append(out, Decision{key, fmt.Sprintf(
			"work order #%d: %s \u2014 %s (vendor: %s)",
			w.ID, w.Property, w.Issue, vendor)})
	}
	month := now.In(time.Local).Format("2006-01")
	seen := LastInspections(ops)
	for _, prop := range Properties(ops) {
		if t, ok := seen[lower(prop)]; ok && now.Sub(t) < PatrolDays*24*time.Hour {
			continue
		}
		key := fmt.Sprintf("trade:patrol:%s:%s", Slug(prop), month)
		if known[key] {
			continue
		}
		when := "never"
		if t, ok := seen[lower(prop)]; ok {
			when = t.In(time.Local).Format("2006-01-02")
		}
		out = append(out, Decision{key, fmt.Sprintf(
			"inspection due: %s (last visit: %s)", prop, when)})
	}
	return out
}
