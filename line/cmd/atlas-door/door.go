// Door: the page's whole mind. Reads fold the books; writes go only
// through `atlas trade`; the badge comes from the chains themselves.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"html"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
)

// Door carries the ops ground, the atlas binary, and the one-writer lock.
// The oracle is single-threaded on purpose (one chain, one writer); here a
// mutex holds the same law around every POST.
type Door struct {
	ops      string
	atlasBin string
	mu       sync.Mutex
}

// NewDoor builds the door. Empty atlasBin resolves at call time.
func NewDoor(ops, atlasBin string) *Door {
	return &Door{ops: ops, atlasBin: atlasBin}
}

func findAtlas() string {
	if v := os.Getenv("ATLAS_BIN"); v != "" {
		return v
	}
	if exe, err := exec.LookPath("atlas"); err == nil {
		return exe
	}
	name := "atlas"
	if os.PathSeparator == '\\' {
		name = "atlas.exe"
	}
	// Built tree: walk up from the caller's working directory (covers `go
	// run` from the module, `go test` from the package dir, and repo root).
	for _, c := range []string{
		filepath.Join("target", "debug", name),
		filepath.Join("..", "target", "debug", name),
		filepath.Join("..", "..", "target", "debug", name),
		filepath.Join("..", "..", "..", "target", "debug", name),
	} {
		if _, err := os.Stat(c); err == nil {
			return c
		}
	}
	return "atlas"
}

// trade shells one grammar through the Rust spine.
func (d *Door) trade(skill, arg string) (string, error) {
	bin := d.atlasBin
	if bin == "" {
		bin = findAtlas()
	}
	cmd := exec.Command(bin, "trade", skill, arg, "--ops", d.ops)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("trade %s refused: %s", skill, strings.TrimSpace(stderr.String()))
	}
	return strings.TrimRight(stdout.String(), "\n"), nil
}

// --- reading ---------------------------------------------------------------

func readJSONL(path string) []map[string]any {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var out []map[string]any
	for _, ln := range strings.Split(string(b), "\n") {
		if strings.TrimSpace(ln) == "" {
			continue
		}
		var m map[string]any
		if err := json.Unmarshal([]byte(ln), &m); err == nil {
			out = append(out, m)
		}
	}
	return out
}

func strField(m map[string]any, k string) string {
	s, _ := m[k].(string)
	return s
}

// Badge rewalks the three chains. Whole iff every line says intact and none
// says BROKEN — the oracle's exact rule.
func (d *Door) badge() (bool, []string) {
	lines := []string{}
	for _, skill := range []string{"property", "workorder", "inspect"} {
		out, err := d.trade(skill, "verify")
		if err != nil {
			lines = append(lines, skill+" verify refused: "+err.Error())
			continue
		}
		lines = append(lines, out)
	}
	whole := true
	for _, l := range lines {
		if !strings.Contains(l, "intact") || strings.Contains(l, "BROKEN") {
			whole = false
		}
	}
	return whole, lines
}

// WorkOrder is one row parsed from `list all` (documented assumption: names
// carry no " — "; the prove covers the standard names).
type WorkOrder struct {
	ID     int64
	Status string
	Prop   string
	Issue  string
	Vendor string
	Cost   string
}

func parseWOList(out string) []WorkOrder {
	var rows []WorkOrder
	for _, ln := range strings.Split(out, "\n") {
		ln = strings.TrimSpace(ln)
		if !strings.HasPrefix(ln, "#") {
			continue
		}
		// "#2 [open] Red Rock Loop — gate hinge (vendor: Marco, $0.00)"
		rest := ln[1:]
		sp := strings.Index(rest, " ")
		if sp < 0 {
			continue
		}
		id, err := strconv.ParseInt(rest[:sp], 10, 64)
		if err != nil {
			continue
		}
		rest = rest[sp+1:]
		if !strings.HasPrefix(rest, "[") {
			continue
		}
		eb := strings.Index(rest, "]")
		if eb < 0 {
			continue
		}
		status := rest[1:eb]
		rest = strings.TrimSpace(rest[eb+1:])
		parts := strings.SplitN(rest, " — ", 2)
		if len(parts) != 2 {
			continue
		}
		prop, tail := parts[0], parts[1]
		vi := strings.LastIndex(tail, " (vendor: ")
		if vi < 0 {
			continue
		}
		issue, vrest := tail[:vi], tail[vi+len(" (vendor: "):]
		vrest = strings.TrimSuffix(vrest, ")")
		vp := strings.SplitN(vrest, ", $", 2)
		vendor := vp[0]
		cost := ""
		if len(vp) == 2 {
			cost = vp[1]
		}
		rows = append(rows, WorkOrder{id, status, prop, issue, vendor, cost})
	}
	return rows
}

func (d *Door) woRows() []WorkOrder {
	out, err := d.trade("workorder", "list all")
	if err != nil {
		return nil
	}
	return parseWOList(out)
}

// auditReceipts maps work-order id -> last audit hash (the chain witness).
func (d *Door) auditReceipts() map[int64]string {
	out := map[int64]string{}
	for _, m := range readJSONL(filepath.Join(d.ops, "workorders_audit.jsonl")) {
		ev, _ := m["event"].(map[string]any)
		if ev == nil {
			continue
		}
		id, _ := ev["id"].(float64)
		if h, ok := m["hash"].(string); ok {
			out[int64(id)] = h
		}
	}
	return out
}

type hit struct {
	kind, text, receipt string
}

// Search answers with receipt lines: roster, work, visits. Nothing found is
// said plainly — the record does not guess.
func (d *Door) search(q string) []hit {
	var hits []hit
	ql := strings.ToLower(q)
	for _, m := range readJSONL(filepath.Join(d.ops, "properties.jsonl")) {
		name, notes := strField(m, "name"), strField(m, "notes")
		if strings.Contains(strings.ToLower(name+" "+notes), ql) {
			text := name + " — since " + strField(m, "ts")[:10]
			if notes != "" {
				text += " · " + notes
			}
			hits = append(hits, hit{"property", text, strField(m, "hash")[:12]})
		}
	}
	receipts := d.auditReceipts()
	for _, r := range d.woRows() {
		if !strings.Contains(strings.ToLower(r.Prop+" "+r.Issue+" "+r.Vendor), ql) {
			continue
		}
		vendor := r.Vendor
		if vendor == "" {
			vendor = "unassigned"
		}
		cost := ""
		if r.Status == "done" {
			cost = ", $" + r.Cost
		}
		text := fmt.Sprintf("#%d [%s] %s — %s (vendor: %s%s)",
			r.ID, r.Status, r.Prop, r.Issue, vendor, cost)
		receipt := ""
		if h, ok := receipts[r.ID]; ok && len(h) >= 12 {
			receipt = h[:12]
		}
		hits = append(hits, hit{"work order", text, receipt})
	}
	for _, m := range readJSONL(filepath.Join(d.ops, "inspections.jsonl")) {
		prop, notes := strField(m, "property"), strField(m, "notes")
		checks, _ := m["checks"].(map[string]any)
		var parts []string
		for k, v := range checks {
			parts = append(parts, k+" "+fmt.Sprint(v))
		}
		sort.Strings(parts)
		hay := prop + " " + notes + " " + strings.Join(parts, " ")
		if !strings.Contains(strings.ToLower(hay), ql) {
			continue
		}
		var fails []string
		for k, v := range checks {
			if s, ok := v.(string); ok && isFail(s) {
				fails = append(fails, k)
			}
		}
		sort.Strings(fails)
		verdict := "all pass"
		if len(fails) > 0 {
			verdict = "FAILED: " + strings.Join(fails, ", ")
		}
		text := strField(m, "ts")[:16] + " " + prop + " — " + verdict
		if notes != "" {
			text += " · " + notes
		}
		ts := strField(m, "ts")
		if len(ts) >= 16 {
			text = ts[:16] + " " + prop + " — " + verdict
			if notes != "" {
				text += " · " + notes
			}
		}
		h := strField(m, "hash")
		if len(h) > 12 {
			h = h[:12]
		}
		hits = append(hits, hit{"visit", text, "verified " + h})
	}
	return hits
}

func isFail(s string) bool {
	switch strings.ToLower(s) {
	case "fail", "failed", "no":
		return true
	}
	return false
}

// --- writing (through the skills' own hands, witnessed by the chain) --------

func (d *Door) logVisit(prop, checks, notes, crew string) (string, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	if notes != "" && crew != "" {
		notes = notes + " — by " + crew
	} else if crew != "" {
		notes = "by " + crew
	}
	return d.trade("inspect", fmt.Sprintf("log %s | %s | %s", prop, checks, notes))
}

func (d *Door) openWork(prop, issue, vendor string) (string, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	return d.trade("workorder", fmt.Sprintf("add %s | %s | %s", prop, issue, vendor))
}

// --- the page ---------------------------------------------------------------

func (d *Door) page(q, msg string) string {
	whole, chainLines := d.badge()
	e := html.EscapeString
	badge := `<span class="badge ok">record proves whole ✓</span>`
	if !whole {
		var broken []string
		for _, l := range chainLines {
			if strings.Contains(l, "BROKEN") {
				broken = append(broken, l)
			}
		}
		badge = `<span class="badge bad">RECORD BROKEN — ` + e(strings.Join(broken, "; ")) + `</span>`
	}
	var sb strings.Builder
	sb.WriteString(`<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Steward</title><style>
body{font-family:system-ui,sans-serif;margin:0;padding:12px;max-width:640px;
     margin:auto;background:#fafaf7;color:#222}
h1{font-size:1.1rem;display:flex;justify-content:space-between;align-items:center}
h2{font-size:.95rem;border-bottom:1px solid #ddd;padding-bottom:4px;margin-top:22px}
.badge{font-size:.72rem;padding:3px 8px;border-radius:10px;font-weight:600}
.ok{background:#e2f2e2;color:#1a6b1a}.bad{background:#fbe3e3;color:#a11}
input,textarea,select,button{font-size:1rem;padding:10px;margin:4px 0;width:100%;
     box-sizing:border-box;border:1px solid #ccc;border-radius:6px}
button{background:#2b5c8a;color:#fff;border:0;font-weight:600}
li{margin:8px 0;line-height:1.35}.r{color:#777;font-size:.78rem;display:block}
.msg{background:#e8f0e8;padding:8px 12px;border-radius:6px;font-size:.9rem}
details{margin:10px 0}summary{font-weight:600;padding:6px 0;cursor:pointer}
ul{padding-left:18px}</style></head><body>`)
	fmt.Fprintf(&sb, "<h1>Steward — the record %s</h1>", badge)
	if msg != "" {
		fmt.Fprintf(&sb, `<p class="msg">%s</p>`, e(msg))
	}
	fmt.Fprintf(&sb, `<form action="/ask" method="get">`+
		`<input name="q" placeholder="ask the record" value="%s"></form>`, e(q))
	if q != "" {
		hits := d.search(q)
		fmt.Fprintf(&sb, "<h2>THE ANSWER — %d hit(s) for “%s”</h2>", len(hits), e(q))
		if len(hits) == 0 {
			sb.WriteString("<p>nothing on file for that. The record does not guess.</p>")
		}
		sb.WriteString("<ul>")
		for _, h := range hits {
			fmt.Fprintf(&sb, `<li><b>%s</b> · %s<span class="r">%s</span></li>`,
				e(h.kind), e(h.text), e(h.receipt))
		}
		sb.WriteString("</ul>")
	}
	sb.WriteString("<h2>OPEN WORK</h2><ul>")
	opened := 0
	for _, r := range d.woRows() {
		if r.Status != "open" {
			continue
		}
		opened++
		vendor := r.Vendor
		if vendor == "" {
			vendor = "unassigned"
		}
		fmt.Fprintf(&sb, "<li>#%d %s — %s (vendor: %s)</li>",
			r.ID, e(r.Prop), e(r.Issue), e(vendor))
	}
	if opened == 0 {
		sb.WriteString("<li>nothing open.</li>")
	}
	sb.WriteString("</ul><h2>RECENT VISITS</h2><ul>")
	visits := readJSONL(filepath.Join(d.ops, "inspections.jsonl"))
	if len(visits) == 0 {
		sb.WriteString("<li>no visits on file.</li>")
	}
	for i := len(visits) - 1; i >= 0 && len(visits)-1-i < 5; i-- {
		m := visits[i]
		checks, _ := m["checks"].(map[string]any)
		var fails []string
		for k, v := range checks {
			if s, ok := v.(string); ok && isFail(s) {
				fails = append(fails, k)
			}
		}
		sort.Strings(fails)
		verdict := "all pass"
		if len(fails) > 0 {
			verdict = "<b>FAILED: " + e(strings.Join(fails, ", ")) + "</b>"
		}
		notes := ""
		if n := strField(m, "notes"); n != "" {
			notes = " · " + e(n)
		}
		h := strField(m, "hash")
		if len(h) > 12 {
			h = h[:12]
		}
		ts := strField(m, "ts")
		if len(ts) >= 16 {
			ts = ts[:16]
		}
		fmt.Fprintf(&sb, "<li>%s — %s — %s%s<span class=\"r\">verified %s</span></li>",
			e(ts), e(strField(m, "property")), verdict, notes, e(h))
	}
	sb.WriteString("</ul>")
	names := []string{}
	seen := map[string]bool{}
	for _, m := range readJSONL(filepath.Join(d.ops, "properties.jsonl")) {
		if n := strField(m, "name"); n != "" && !seen[n] {
			seen[n] = true
			names = append(names, n)
		}
	}
	options := ""
	for _, n := range names {
		options += "<option>" + e(n) + "</option>"
	}
	sb.WriteString(`
<details><summary>log a visit</summary>
<form action="/log" method="post">
<select name="prop" required>` + options + `</select>
<input name="checks" placeholder="water heater=pass ; drain=fail" required>
<input name="notes" placeholder="notes (what was found, what was done)">
<input name="crew" placeholder="your name">
<button>log it — sealed and witnessed</button></form></details>
<details><summary>open a work order</summary>
<form action="/work" method="post">
<select name="prop" required>` + options + `</select>
<input name="issue" placeholder="what needs doing" required>
<input name="vendor" placeholder="vendor (optional)">
<button>open it — sealed and witnessed</button></form></details>
</body></html>`)
	return sb.String()
}

// badgeText is the script-readable badge: GREEN whole / RED naming breaks.
func (d *Door) badgeText() string {
	whole, lines := d.badge()
	if whole {
		return "GREEN record proves whole"
	}
	var broken []string
	for _, l := range lines {
		if strings.Contains(l, "BROKEN") {
			broken = append(broken, l)
		}
	}
	return "RED " + strings.Join(broken, "; ")
}
