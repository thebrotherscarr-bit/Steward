// The first strokes on ground detection.
//
// WHY THIS FILE DID NOT EXIST UNTIL 2026-09-11. This package is 200 lines and
// had zero tests, and on 2026-09-11 it carried a world from OUTSIDE the estate
// onto the operator's dashboard: the door was launched from the ground root, so
// Detect resolved to the core ground and Siblings() read the parent of THAT --
// the desktop -- adopting every neighbour holding an AGENTS.md. Nobody noticed
// until a sidebar badge read 83,303.
//
// Nothing here was a bug. Detect and Siblings both did exactly what they were
// written to do. What was missing was any stroke stating what that IS, so the
// blast radius of a launch directory was discoverable only by suffering it.
//
// Every stroke below builds its own tree in a temp dir. Nothing reads the real
// estate, and nothing here writes outside what it made.
package ground

import (
	"os"
	"path/filepath"
	"testing"
)

// mk makes dir under root and returns its path.
func mk(t *testing.T, root string, parts ...string) string {
	t.Helper()
	p := filepath.Join(append([]string{root}, parts...)...)
	if err := os.MkdirAll(p, 0o755); err != nil {
		t.Fatal(err)
	}
	return p
}

// markAgents puts an AGENTS.md in dir, making it a ground by the second rule.
func markAgents(t *testing.T, dir string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(dir, "AGENTS.md"), []byte("# ground\n"), 0o644); err != nil {
		t.Fatal(err)
	}
}

// markUs puts a .us module declaration in dir, making it a ground by the first
// rule -- the one where the ground NAMES ITSELF rather than taking its
// directory's name.
func markUs(t *testing.T, dir, id string) {
	t.Helper()
	usDir := filepath.Join(dir, ".us")
	if err := os.MkdirAll(usDir, 0o755); err != nil {
		t.Fatal(err)
	}
	doc := "prose above the fence\n\n```json\n{\"kind\":\"module\",\"id\":\"" + id + "\"}\n```\n"
	if err := os.WriteFile(filepath.Join(usDir, "mod.us"), []byte(doc), 0o644); err != nil {
		t.Fatal(err)
	}
}

// ---- Detect --------------------------------------------------------------

// NEAREST WINS, and that single fact is the whole control over what the door
// carries. From a directory with two grounds above it, Detect must stop at the
// closer one -- because Siblings is then handed the parent of THAT, and the
// difference between the two answers is the difference between carrying a
// sibling and carrying the whole desktop.
func TestDetectStopsAtTheNearestGround(t *testing.T) {
	root := t.TempDir()
	outer := mk(t, root, "outer")
	inner := mk(t, root, "outer", "inner")
	deep := mk(t, root, "outer", "inner", "a", "b")
	markAgents(t, outer)
	markAgents(t, inner)

	got, ok := Detect(deep)
	if !ok {
		t.Fatal("no ground detected from a directory two grounds deep")
	}
	if got.Home != inner {
		t.Errorf("Detect climbed past the nearer ground.\n  got:  %s\n  want: %s\n"+
			"Nearest must win: Siblings is handed the parent of whatever this "+
			"returns, so climbing one level too far widens the scan by a whole "+
			"directory.", got.Home, inner)
	}
	if got.Name != "inner" {
		t.Errorf("Name = %q, want the directory's own name %q", got.Name, "inner")
	}
	if got.Via != "AGENTS.md" {
		t.Errorf("Via = %q, want AGENTS.md", got.Via)
	}
}

// A .us DECLARATION OUTRANKS THE DIRECTORY NAME, because a module that names
// itself is making a claim and a folder name is an accident of where it sits.
func TestAUsModuleNamesItselfAndOutranksTheFolderName(t *testing.T) {
	root := t.TempDir()
	dir := mk(t, root, "some-folder-name")
	markUs(t, dir, "TheRealName")
	markAgents(t, dir) // both markers present; .us must win

	got, ok := Detect(dir)
	if !ok {
		t.Fatal("a .us module was not detected as a ground")
	}
	if got.Name != "therealname" {
		t.Errorf("Name = %q, want the lowercased module id %q", got.Name, "therealname")
	}
	if got.Via != ".us" {
		t.Errorf("Via = %q; .us must outrank AGENTS.md when both are present", got.Via)
	}
}

// NO GROUND IS AN ANSWER. A caller must be able to tell "I found nothing" from
// "I found something", or it will invent a ground and serve the wrong law.
func TestDetectRefusesRatherThanInventingAGround(t *testing.T) {
	root := t.TempDir()
	bare := mk(t, root, "nothing", "here")
	if got, ok := Detect(bare); ok {
		// A temp dir can sit under a real tree that carries a marker, so this
		// only fails if what came back is INSIDE the temp root.
		if len(got.Home) >= len(root) && got.Home[:len(root)] == root {
			t.Errorf("invented a ground at %s from a tree with no markers", got.Home)
		}
	}
}

// ---- Siblings ------------------------------------------------------------

// SIBLINGS SCANS ONE LEVEL AND NOT ONE INCH FURTHER. This is the stroke that
// pins the blast radius. A grandchild ground must NOT be carried: if the scan
// ever went deep, pointing the door at a home directory would adopt every
// project on the machine.
func TestSiblingsScansExactlyOneLevel(t *testing.T) {
	root := t.TempDir()
	a := mk(t, root, "alpha")
	b := mk(t, root, "beta")
	deep := mk(t, root, "beta", "gamma")
	markAgents(t, a)
	markAgents(t, b)
	markAgents(t, deep) // one level too far; must not appear

	names := map[string]bool{}
	for _, f := range Siblings(root) {
		names[f.Name] = true
	}
	if !names["alpha"] || !names["beta"] {
		t.Errorf("the two direct children were not both carried: %v", names)
	}
	if names["gamma"] {
		t.Error("a GRANDCHILD ground was carried. Siblings is one level by " +
			"design -- a deep walk turns any parent directory into the whole " +
			"machine's project list.")
	}
}

// ROOT ITSELF IS CARRIED WHEN ROOT IS A GROUND, and is not when it is not.
// The door hands Siblings the PARENT of the detected ground, so this decides
// whether that parent rides in alongside its children.
func TestSiblingsCarriesRootOnlyWhenRootIsItselfAGround(t *testing.T) {
	root := t.TempDir()
	mk(t, root, "child")
	markAgents(t, filepath.Join(root, "child"))

	for _, f := range Siblings(root) {
		if f.Home == root {
			t.Fatalf("root was carried while holding no marker: %v", f)
		}
	}

	markAgents(t, root)
	found := false
	for _, f := range Siblings(root) {
		if f.Home == root {
			found = true
		}
	}
	if !found {
		t.Error("root holds a marker and was not carried")
	}
}

// THE ATTIC IS HISTORY, NOT CLAIM, and vendored trees are not ours. A tool
// that walks them measures its own process. skipDir is the list; this is the
// stroke that keeps it honest.
func TestSiblingsSkipsTheAtticAndTheVendoredTrees(t *testing.T) {
	root := t.TempDir()
	for _, n := range []string{"attic", "folded", "node_modules", "target",
		"__pycache__", ".venv", "venv", "keepme"} {
		d := mk(t, root, n)
		markAgents(t, d)
	}
	// A dot-directory is skipped by the prefix rule, not by skipDir.
	dot := mk(t, root, ".hidden")
	markAgents(t, dot)

	got := map[string]bool{}
	for _, f := range Siblings(root) {
		got[f.Name] = true
	}
	if !got["keepme"] {
		t.Fatalf("an ordinary ground was skipped: %v", got)
	}
	for _, n := range []string{"attic", "folded", "node_modules", "target",
		"__pycache__", ".venv", "venv", ".hidden"} {
		if got[n] {
			t.Errorf("%q was carried; it is never a ground", n)
		}
	}
}

// A DIRECTORY WITH NO MARKER IS NOT A GROUND. Without this, Siblings would
// carry every folder beside the one you launched from.
func TestSiblingsCarriesOnlyMarkedDirectories(t *testing.T) {
	root := t.TempDir()
	mk(t, root, "plain-one")
	mk(t, root, "plain-two")
	marked := mk(t, root, "marked")
	markAgents(t, marked)

	got := Siblings(root)
	if len(got) != 1 {
		t.Fatalf("carried %d grounds, want 1: %v", len(got), got)
	}
	if got[0].Name != "marked" {
		t.Errorf("carried %q, want marked", got[0].Name)
	}
}

// AN UNREADABLE ROOT IS EMPTY, NOT A PANIC. The door calls this at boot; a
// crash here takes the whole server with it.
func TestSiblingsOfSomethingUnreadableIsEmpty(t *testing.T) {
	if got := Siblings(filepath.Join(t.TempDir(), "does", "not", "exist")); len(got) != 0 {
		t.Errorf("expected nothing from a path that does not exist, got %v", got)
	}
}
