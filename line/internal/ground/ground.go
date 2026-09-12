// Package ground finds which ground a session was opened in, and who its
// neighbours are, WITHOUT being told.
//
// THE RULING THAT CAUSED THIS (operator, 2026-08-27): "I want something for
// each module that whenever I open an opencode session anywhere on my computer
// it reads the dir, finds the agent file, finds the .us, connects up to a
// central db and can speak to the town and see what is going on... this is a
// single folder harness, that is fucking useless to me."
//
// Before this package, atlas-mcp carried only the grounds named on its own
// command line (--tenant name=path) and refused everything else BY NAME. That
// made every tree need its own opencode.jsonc: a harness, not a door.
//
// The 2026-08-27 per-tree MCP ruling stands on its reason, not its letter. The
// bug it fixed was that ONE globally-mounted server injected Steward 1.0's wall
// into every session in every tree. Detection fixes that at the root: the
// server serves the law of the ground you are STANDING IN, so being registered
// globally stops being wrong. Per-tree config becomes unnecessary rather than
// forbidden.
//
// A ground is a directory carrying either:
//   - a .us\ directory holding a `kind: "module"` declaration (the name comes
//     from its id -- the ground names itself), or
//   - an AGENTS.md (the name falls back to the directory's own name)
//
// Detection walks UP from the working directory, so a session opened deep in a
// tree still resolves to that tree's ground. Nearest wins.
//
// Stdlib only, per the atlas law. Nothing here writes.
package ground

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

// Found is one detected ground.
type Found struct {
	Name string // lowercased; from the .us module id, else the dir name
	Home string // absolute
	Via  string // ".us" or "AGENTS.md" -- how it was recognised
}

// maxWalk bounds the climb so a detached or malformed path cannot spin.
const maxWalk = 64

// idFromUsDir reads <dir>\.us\*.us and returns the id of the first block whose
// kind is "module". Returns "" when there is no such declaration -- an absent
// or unreadable file is not an error here, it is simply not a ground marker.
func idFromUsDir(dir string) string {
	usDir := filepath.Join(dir, ".us")
	entries, err := os.ReadDir(usDir)
	if err != nil {
		return ""
	}
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(strings.ToLower(e.Name()), ".us") {
			continue
		}
		b, err := os.ReadFile(filepath.Join(usDir, e.Name()))
		if err != nil {
			continue
		}
		if id := moduleIDFromDoc(string(b)); id != "" {
			return id
		}
	}
	return ""
}

// moduleIDFromDoc pulls the id out of the first fenced JSON block declaring
// kind "module". A .us document is prose carrying fenced JSON (SPEC_US); this
// reads only what it needs and never rewrites anything.
func moduleIDFromDoc(text string) string {
	rest := text
	for {
		i := strings.Index(rest, "```")
		if i < 0 {
			return ""
		}
		rest = rest[i+3:]
		// skip the fence tag (json / us / json us) to the end of that line
		nl := strings.IndexByte(rest, '\n')
		if nl < 0 {
			return ""
		}
		rest = rest[nl+1:]
		j := strings.Index(rest, "```")
		if j < 0 {
			return ""
		}
		body := rest[:j]
		rest = rest[j+3:]
		var blk struct {
			Kind string `json:"kind"`
			ID   string `json:"id"`
		}
		if json.Unmarshal([]byte(body), &blk) != nil {
			continue
		}
		if blk.Kind == "module" && blk.ID != "" {
			return strings.ToLower(blk.ID)
		}
	}
}

// hasAgentsFile reports whether dir carries an AGENTS.md (or CLAUDE.md).
func hasAgentsFile(dir string) bool {
	for _, n := range []string{"AGENTS.md", "CLAUDE.md"} {
		if st, err := os.Stat(filepath.Join(dir, n)); err == nil && !st.IsDir() {
			return true
		}
	}
	return false
}

// Detect walks up from start and returns the nearest ground. ok is false when
// the climb reaches the filesystem root without finding one -- a caller must
// degrade honestly rather than invent a ground.
// Barred reports a home THE LINE will not carry, whatever names it and
// however it was found.
//
// RULE 1 of the estate, and the only absolute one about a PLACE:
// `Desktop\Archive` is OUTSIDE the ground, and the archive never leaves this
// machine. On 2026-09-11 the sibling walk below carried it in, because it has
// an AGENTS.md like any other world -- and the dashboard read its git state,
// 83,303 changed files, before anyone knew it was there. The boot line was
// made to NAME what it carries that day so the next one would be visible. It
// was visible the next day, on the same walk, at 83,302. Being visible is not
// the same as being refused, so this is the refusal.
//
// BY NAME, AND THAT IS THE POINT. A path test would bind this to one machine's
// layout and would miss a copy, a mount or a move; `archive` is the estate's
// word for this place wherever it sits, and a world that wants carrying does
// not get to be called that. Checked at the walk AND at the registry, because
// a rule with one door is a rule with a way around it.
//
// EVERY SEGMENT, not just the last. A `.us` module sitting INSIDE the archive
// is still inside the archive, and Detect walking up from it would have found
// the module before it ever reached the barred parent.
func Barred(home string) bool {
	p := filepath.Clean(home)
	for {
		if strings.EqualFold(filepath.Base(p), "archive") {
			return true
		}
		parent := filepath.Dir(p)
		if parent == p {
			return false
		}
		p = parent
	}
}

func Detect(start string) (Found, bool) {
	dir, err := filepath.Abs(start)
	if err != nil {
		return Found{}, false
	}
	for i := 0; i < maxWalk; i++ {
		if Barred(dir) {
			return Found{}, false
		}
		if id := idFromUsDir(dir); id != "" {
			return Found{Name: id, Home: dir, Via: ".us"}, true
		}
		if hasAgentsFile(dir) {
			return Found{
				Name: strings.ToLower(filepath.Base(dir)),
				Home: dir,
				Via:  "AGENTS.md",
			}, true
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return Found{}, false
		}
		dir = parent
	}
	return Found{}, false
}

// Siblings scans one level under root and returns every directory that is
// itself a ground, plus root when root is one. This is how a seat standing in
// any single ground can still SEE THE TOWN: the door carries them all, and
// muster/state_matrix answer across them instead of across whatever one launch
// happened to name.
//
// One level only, deliberately. A deep walk of the Archive descends vendored
// trees and folded attics, and the attic is history, not claim.
func Siblings(root string) []Found {
	out := []Found{}
	abs, err := filepath.Abs(root)
	if err != nil {
		return out
	}
	if Barred(abs) {
		return out
	}
	if id := idFromUsDir(abs); id != "" {
		out = append(out, Found{Name: id, Home: abs, Via: ".us"})
	} else if hasAgentsFile(abs) {
		out = append(out, Found{Name: strings.ToLower(filepath.Base(abs)), Home: abs, Via: "AGENTS.md"})
	}
	entries, err := os.ReadDir(abs)
	if err != nil {
		return out
	}
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		n := e.Name()
		if strings.HasPrefix(n, ".") || skipDir(n) {
			continue
		}
		d := filepath.Join(abs, n)
		if Barred(d) {
			continue
		}
		if id := idFromUsDir(d); id != "" {
			out = append(out, Found{Name: id, Home: d, Via: ".us"})
			continue
		}
		if hasAgentsFile(d) {
			out = append(out, Found{Name: strings.ToLower(n), Home: d, Via: "AGENTS.md"})
		}
	}
	return out
}

// skipDir names the directories that are never grounds. The attic is history
// kept by law (fold, never delete); a tool that walks it measures its own
// process. node_modules and the rest are vendored, not ours.
func skipDir(n string) bool {
	switch strings.ToLower(n) {
	case "attic", "folded", "node_modules", "target", "__pycache__",
		".venv", "venv", ".git":
		return true
	}
	return false
}
