// THE WALK DOES NOT LEAVE THE ESTATE.
//
// Detection carries the ground it is standing in and, one level up, that
// ground's neighbours -- SEE THE TOWN. When the ground is the top of its own
// tree, that level up is somebody's desktop, and the neighbours are whatever
// happens to be sitting there.
//
// It cost twice. 2026-09-11: `Desktop\Archive` rode in and the dashboard read
// its git state, 83,303 changed files. 2026-09-12: the archive was refused by
// name and `manjuel` and `neiro_recovery` rode in the same way. Two names on a
// list would have been a list waiting for a third folder, so the rule here is a
// boundary: a neighbour is carried only when it sits inside a tenant the
// command line actually named.
package main

import (
	"path/filepath"
	"testing"
)

func TestInsideNamedIsTheEstateBoundary(t *testing.T) {
	base := t.TempDir()
	research := filepath.Join(base, "Desktop", "Research")
	named := map[string]string{
		"research": research,
		"atlas":    filepath.Join(research, "atlas"),
	}

	inside := []string{
		research,
		filepath.Join(research, "atlas"),
		filepath.Join(research, "atlas", "line"),
		filepath.Join(research, "skills"),
	}
	for _, p := range inside {
		if !insideNamed(p, named) {
			t.Fatalf("insideNamed(%q) = false; it is inside a named tenant", p)
		}
	}

	// the two that rode in on 2026-09-12, and the one that rode in the day
	// before -- all of them desktop neighbours, none of them named
	outside := []string{
		filepath.Join(base, "Desktop", "manjuel"),
		filepath.Join(base, "Desktop", "neiro_recovery"),
		filepath.Join(base, "Desktop", "Archive"),
		filepath.Join(base, "Desktop"),
		base,
	}
	for _, p := range outside {
		if insideNamed(p, named) {
			t.Fatalf("insideNamed(%q) = true; nothing named covers it", p)
		}
	}

	// A PREFIX IS NOT A PARENT. `Research_old` shares every byte of
	// `Research` and is a different tree; a bare HasPrefix says yes.
	for _, p := range []string{research + "_old", research + "2", research + "-backup"} {
		if insideNamed(p, named) {
			t.Fatalf("insideNamed(%q) = true; a shared prefix is not containment", p)
		}
	}

	// and nothing is inside an empty estate
	if insideNamed(research, map[string]string{}) {
		t.Fatal("insideNamed said yes with no tenant named at all")
	}
}
