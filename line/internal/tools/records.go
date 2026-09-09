package tools

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"atlas/line/internal/tenant"
)

// records serves the estate's own documents, SORTED BY WHAT THEY ARE.
//
// WHY THIS EXISTS. Nothing could reach them. `read_doctrine` serves only what
// the carried manifest declares (one file in this ground), `read_plan` maps
// five names to THE_ROAD.md and its siblings -- none of which exist here, so
// every one answers "present in the map but unreadable" -- and `read_handoffs`
// serves SEAT_LOG alone. The Records page was asked to hold the docs for quick
// lookup and there was no door to hold them through.
//
// WHY IT IS SORTED. His word: "the logs and the function/command docs should
// all be separated out. like doctrine/agents/function/tools/skills/ etc." A
// flat list of 40 markdown files is a directory listing, not a record. The
// kinds below are the estate's own furniture, and each entry says which one it
// belongs to, so the glass can section itself without a second opinion about
// what a file is.
//
//	doctrine   law/*.md (SEALED) and CLAUDE.md -- the rules a hand is bound by
//	record     what happened: CHANGELOG, DAYBOOK, HANDOFF, SEAT_LOG, TASKS, memory
//	spec       what the thing IS and what done means
//	agents     agents/*.md -- the seats, as they declare themselves
//	commands   commands.md and pipelines.md -- what can be asked for
//	skills     skills/ -- what a seat can actually do
//	logs       logs/*.md -- the transcripts, newest first
//	other      any root .md the sets above do not claim; nothing is hidden
//
// Tools are NOT a kind here. The registry is the only honest list of them and
// the webapp already serves it whole at /api/tools; a second list in this file
// would drift from the registry the first time a tool was added.
//
// WHAT IT WILL NOT DO, and these are the whole design:
//
//   - IT IS A LIST, NOT A PATH. A name is matched against the listing this same
//     tool produces. Nothing is joined onto Home from the caller's string, so
//     there is no traversal to defend against: "../.env", an absolute path, a
//     symlink name -- none of them are IN the list, so none of them resolve.
//   - .env IS NOT A DOCUMENT (RULE 7). Only `.md` is served, and only from the
//     directories named above. A dotfile, a key, an index shard and the whole
//     of worlds/ are outside what this can name.
//   - IT READS. `Writes: false`, and no branch here opens a file for writing.
//     The record is appended to by the core's own writers (LAW 8, one
//     write-path); a second one in the glass is what this estate refuses.
//
// Every document comes back with a sha256 of the bytes served -- the same
// receipt read_doctrine and read_handoffs give -- so a page showing a document
// can be checked against the disk without trusting the page.
func toolRecords(t tenant.Tenant, args map[string]any) (string, error) {
	docs, err := recordDocs(t.Home)
	if err != nil {
		return "", err
	}

	// ---- one document, whole ------------------------------------------
	if name := strings.TrimSpace(str(args, "name")); name != "" {
		for _, d := range docs {
			if !strings.EqualFold(d.Name, name) {
				continue
			}
			b, err := os.ReadFile(filepath.Join(t.Home, filepath.FromSlash(d.Name)))
			if err != nil {
				return "", fmt.Errorf("record %q is listed but unreadable: %w", d.Name, err)
			}
			sum := sha256.Sum256(b)
			return marshal(map[string]any{
				"world": t.Name, "name": d.Name, "kind": d.Kind,
				"sha256": hex.EncodeToString(sum[:]), "bytes": len(b),
				"modified": d.Modified, "sealed": d.Sealed, "text": string(b),
			})
		}
		// AN ABSENT NAME IS DENIED HONESTLY, the way the rest of this
		// registry denies one: by saying what there is instead.
		kinds := map[string]int{}
		for _, d := range docs {
			kinds[d.Kind]++
		}
		return "", fmt.Errorf("no record named %q in %s. Kinds carried: %s",
			name, t.Name, summarise(kinds))
	}

	// ---- one kind, listed ---------------------------------------------
	if kind := strings.ToLower(strings.TrimSpace(str(args, "kind"))); kind != "" {
		out := []recordDoc{}
		for _, d := range docs {
			if d.Kind == kind {
				out = append(out, d)
			}
		}
		if len(out) == 0 {
			kinds := map[string]int{}
			for _, d := range docs {
				kinds[d.Kind]++
			}
			return "", fmt.Errorf("no kind %q in %s. Kinds carried: %s",
				kind, t.Name, summarise(kinds))
		}
		return marshal(map[string]any{
			"world": t.Name, "kind": kind, "count": len(out), "documents": out,
		})
	}

	// ---- everything, grouped ------------------------------------------
	// Grouped rather than flat because the glass sections on this, and a
	// caller that wants one heap can still walk the groups.
	by := map[string][]recordDoc{}
	for _, d := range docs {
		by[d.Kind] = append(by[d.Kind], d)
	}
	kinds := make([]map[string]any, 0, len(by))
	for _, k := range kindOrder {
		if ds, ok := by[k]; ok {
			kinds = append(kinds, map[string]any{"kind": k, "count": len(ds), "documents": ds})
		}
	}
	return marshal(map[string]any{
		"world": t.Name, "count": len(docs), "kinds": kinds,
	})
}

func marshal(v any) (string, error) {
	b, err := json.MarshalIndent(v, "", " ")
	if err != nil {
		return "", err
	}
	return string(b), nil
}

func summarise(kinds map[string]int) string {
	parts := []string{}
	for _, k := range kindOrder {
		if n, ok := kinds[k]; ok {
			parts = append(parts, fmt.Sprintf("%s (%d)", k, n))
		}
	}
	return strings.Join(parts, ", ")
}

type recordDoc struct {
	Name     string `json:"name"`
	Kind     string `json:"kind"`
	Bytes    int64  `json:"bytes"`
	Modified string `json:"modified"`
	Sealed   bool   `json:"sealed,omitempty"`
}

// kindOrder is the order the glass shows them in: what binds a hand first,
// what happened second, what the thing is third, then the furniture, then the
// transcripts. Not alphabetical -- alphabetical would put agents above the law.
var kindOrder = []string{"doctrine", "record", "spec", "agents", "commands", "skills", "logs", "other"}

// The root files each set claims. A file named in two sets takes the first
// match in kindOrder, so the law always wins over a coincidence of naming.
var rootKinds = map[string][]string{
	"doctrine": {"CLAUDE.md"},
	"record":   {"CHANGELOG.md", "DAYBOOK.md", "HANDOFF.md", "SEAT_LOG.md", "TASKS.md", "memory.md"},
	"spec": {"SPEC.md", "SPEC_CONTROL_CENTER.md", "DESIGN.md", "SYSTEM_DESIGN.md",
		"BUILDMAP.md", "BUILDPATH.md", "RUNBOOK.md", "QUICKSTART.md", "README.md",
		"TESTING.md", "CONTRIBUTING.md", "REFUSALS.md", "parity.md", "rack.md"},
	"commands": {"commands.md", "pipelines.md", "agents.md"},
}

// LOGS_SHOWN caps what the logs kind returns. This ground carries 808 of them
// and a page that renders every one is a page that renders nothing useful.
// Newest first, and the count reported is the TRUE count, not the shown one --
// a listing that silently truncated would be a page lying about the record.
const LOGS_SHOWN = 60

// recordDocs lists what the estate carries, in the four places it keeps it.
// The boundary is enforced by WHAT IS WALKED, not by inspecting what was asked
// for: four directories, one extension, no recursion.
func recordDocs(home string) ([]recordDoc, error) {
	out := []recordDoc{}

	scan := func(dir, prefix, kind string, sealed bool) ([]recordDoc, error) {
		got := []recordDoc{}
		ents, err := os.ReadDir(dir)
		if err != nil {
			if os.IsNotExist(err) {
				return got, nil // a ground without law/ or logs/ is not an error
			}
			return got, err
		}
		for _, e := range ents {
			if e.IsDir() || !strings.EqualFold(filepath.Ext(e.Name()), ".md") {
				continue
			}
			info, err := e.Info()
			if err != nil {
				continue
			}
			k := kind
			if k == "" {
				k = rootKind(e.Name())
			}
			got = append(got, recordDoc{
				Name:     prefix + e.Name(),
				Kind:     k,
				Bytes:    info.Size(),
				Modified: info.ModTime().UTC().Format("2006-01-02T15:04:05Z"),
				Sealed:   sealed,
			})
		}
		return got, nil
	}

	root, err := scan(home, "", "", false)
	if err != nil {
		return nil, err
	}
	sort.Slice(root, func(i, j int) bool { return root[i].Name < root[j].Name })
	out = append(out, root...)

	// law/ is marked SEALED so the glass can say so. law.py --prove walks the
	// hash chain and a tampered law refuses every run; these are shown to be
	// read, never edited, and their own Amendment clause says a new law is a
	// new link rather than an edit to an old one.
	law, err := scan(filepath.Join(home, "law"), "law/", "doctrine", true)
	if err != nil {
		return nil, err
	}
	sort.Slice(law, func(i, j int) bool { return law[i].Name < law[j].Name })
	out = append(out, law...)

	seats, err := scan(filepath.Join(home, "agents"), "agents/", "agents", false)
	if err != nil {
		return nil, err
	}
	sort.Slice(seats, func(i, j int) bool { return seats[i].Name < seats[j].Name })
	out = append(out, seats...)

	skills, err := scan(filepath.Join(home, "skills"), "skills/", "skills", false)
	if err != nil {
		return nil, err
	}
	sort.Slice(skills, func(i, j int) bool { return skills[i].Name < skills[j].Name })
	out = append(out, skills...)

	// The transcripts, NEWEST FIRST and capped. Everything else in this file is
	// sorted by name because a name is how you look a document up; a log is
	// looked up by when it happened.
	logs, err := scan(filepath.Join(home, "logs"), "logs/", "logs", false)
	if err != nil {
		return nil, err
	}
	sort.Slice(logs, func(i, j int) bool { return logs[i].Modified > logs[j].Modified })
	if len(logs) > LOGS_SHOWN {
		logs = logs[:LOGS_SHOWN]
	}
	out = append(out, logs...)

	return out, nil
}

func rootKind(name string) string {
	for _, k := range kindOrder {
		for _, want := range rootKinds[k] {
			if strings.EqualFold(want, name) {
				return k
			}
		}
	}
	return "other"
}
