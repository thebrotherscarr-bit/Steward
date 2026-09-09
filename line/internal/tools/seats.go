package tools

import (
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"atlas/line/internal/tenant"
)

// seats reads the world's own seat declarations and the pipelines they stand
// in -- from agents/*.md and pipelines.md, which ARE the source of truth.
//
// WHY THIS EXISTS. The Agents page listed the webapp's own SQLite table, which
// nothing writes: `{"agents":[],"count":0}` on a ground holding fourteen
// declared seats. Same fault the dashboard had before P0-11 and the Evals cards
// had this morning -- a page counting its own store instead of asking the
// record.
//
// A SHAPE, NOT A SCHEMA, and that is what makes reading it here safe. The core
// parses a declaration with two regexes (manjuel/registry.py):
//
//	_HEADING_RE  ^##[ \t]+(name)
//	_FIELD_RE    ^[-*] \*\*(key)\*\* :? (value)
//
// Neither names a field. So this reads the same shape and returns WHATEVER
// keys a declaration carries -- Model Target, When, Timeout, Wakes On, or one
// added tomorrow. Encoding the field list here is what would drift from the
// core; reading the shape cannot.
//
// pipelines.md is read the same way, with the core's own step rule, so a seat
// knows which pipelines it stands in and where.
func toolSeats(t tenant.Tenant, _ map[string]any) (string, error) {
	out := map[string]any{"world": t.Name}

	dir := filepath.Join(t.Home, "agents")
	entries, err := os.ReadDir(dir)
	if err != nil {
		out["seats_error"] = readable(err)
		b, _ := json.MarshalIndent(out, "", " ")
		return string(b), nil
	}

	// Which pipelines name which seat, in what order. Read first so each seat
	// can carry its own standing.
	stands := map[string][]map[string]any{}
	if b, err := os.ReadFile(filepath.Join(t.Home, "pipelines.md")); err == nil {
		pipeline := ""
		step := 0
		for _, line := range strings.Split(string(b), "\n") {
			line = strings.TrimRight(line, "\r")
			if m := pipeHeadRe.FindStringSubmatch(line); m != nil {
				pipeline, step = strings.TrimSpace(m[1]), 0
				continue
			}
			if pipeline == "" {
				continue
			}
			m := stepRe.FindStringSubmatch(line)
			if m == nil {
				continue
			}
			seat := strings.TrimSpace(m[1])
			if seat == "" {
				continue
			}
			step++
			row := map[string]any{"pipeline": pipeline, "step": step}
			if note := strings.TrimSpace(m[2]); note != "" {
				row["note"] = note
				if w := whenRe.FindStringSubmatch(note); w != nil {
					row["when"] = w[1]
				}
			}
			stands[strings.ToLower(seat)] = append(stands[strings.ToLower(seat)], row)
		}
	} else {
		out["pipelines_error"] = readable(err)
	}

	seats := []map[string]any{}
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(strings.ToLower(e.Name()), ".md") {
			continue
		}
		raw, err := os.ReadFile(filepath.Join(dir, e.Name()))
		if err != nil {
			seats = append(seats, map[string]any{
				"file": e.Name(), "error": readable(err)})
			continue
		}
		seats = append(seats, readSeat(e.Name(), string(raw), stands))
	}
	sort.Slice(seats, func(i, j int) bool {
		return strings.ToLower(str(seats[i], "name")) < strings.ToLower(str(seats[j], "name"))
	})
	out["seats"] = seats

	b, err := json.MarshalIndent(out, "", " ")
	if err != nil {
		return "", err
	}
	return string(b), nil
}

// The core's own rules, in manjuel/registry.py's words. None of them names a
// field, so none of them can drift when a declaration gains one.
var (
	headRe     = regexp.MustCompile(`(?m)^##[ \t]+(.+?)[ \t]*$`)
	fieldRe    = regexp.MustCompile(`(?m)^[ \t]*[-*][ \t]*\*\*([^*]+?)\*\*[ \t]*:?[ \t]*(.*?)[ \t]*$`)
	pipeHeadRe = regexp.MustCompile(`^##[ \t]+Pipeline[ \t]*:?[ \t]+(.+?)[ \t]*$`)
	stepRe     = regexp.MustCompile(`^[ \t]*(?:\d+[.)]|[-*])[ \t]+([^(\n]+?)[ \t]*(?:\(([^)]*)\))?[ \t]*$`)
	whenRe     = regexp.MustCompile(`(?i)when[ \t]*:[ \t]*([A-Za-z0-9_\-]+)`)
)

func readSeat(file, raw string, stands map[string][]map[string]any) map[string]any {
	seat := map[string]any{"file": file}

	name := strings.TrimSuffix(file, filepath.Ext(file))
	if m := headRe.FindStringSubmatch(raw); m != nil {
		name = strings.TrimSpace(m[1])
	}
	seat["name"] = name

	// EVERY declared field, whatever it is called. The prompt is everything
	// after the field that opens it -- the core's own shape, where a field
	// with an empty value and a body beneath it is the body's heading.
	fields := map[string]string{}
	order := []string{}
	promptFrom := -1
	for _, m := range fieldRe.FindAllStringSubmatchIndex(raw, -1) {
		// The core cleans a key the same way (registry.py's _clean_key:
		// strip, rstrip ":", strip, lower). The colon lives INSIDE the bold
		// markers in this estate's files -- "**Model Target:**" -- so without
		// this the page would label every field with a trailing colon.
		key := strings.TrimSpace(strings.TrimSuffix(strings.TrimSpace(raw[m[2]:m[3]]), ":"))
		val := strings.TrimSpace(raw[m[4]:m[5]])
		if _, seen := fields[key]; !seen {
			order = append(order, key)
		}
		fields[key] = val
		if val == "" && strings.EqualFold(key, "System Prompt") {
			promptFrom = m[1]
		}
	}
	if promptFrom >= 0 && promptFrom < len(raw) {
		body := strings.TrimSpace(raw[promptFrom:])
		seat["prompt"] = body
		seat["prompt_chars"] = len(body)
		delete(fields, "System Prompt")
	}
	seat["fields"] = fields
	seat["field_order"] = order
	seat["stands_in"] = stands[strings.ToLower(name)]
	return seat
}

func str(m map[string]any, k string) string {
	s, _ := m[k].(string)
	return s
}
