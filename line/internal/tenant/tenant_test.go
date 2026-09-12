// The first strokes on the tenant model.
//
// WHY THIS FILE DID NOT EXIST UNTIL 2026-09-11. This package is 288 lines and
// had zero tests, and it is the multi-tenant core -- the thing that makes the
// door "one server, ALL projects" (the genesis law, 2026-08-25) rather than a
// single-folder harness. ADR-006 measured it: the two things that define the
// door as a product, the protocol layer and the tenant model, were the two
// least tested things in it.
//
// The promise these strokes hold the registry to:
//   - an unknown project refuses BY NAME and hands a stranger no context
//   - a name is a name however it was typed: case and surrounding space
//     cannot make two tenants out of one, or one out of two
//   - the default is deterministic, so an unnamed call lands somewhere
//     predictable rather than wherever the map happened to iterate
//   - Home is absolute, because every wall check downstream is a prefix test
//
// Hermetic: temp directories only, nothing read from the real estate.
package tenant

import (
	"path/filepath"
	"strings"
	"testing"
)

// ---- refusing a stranger --------------------------------------------------

// AN UNKNOWN PROJECT REFUSES BY NAME. The enrollment law carried into
// transport: a caller naming a project that is not carried learns that, and
// learns nothing else. It must not fall through to the default and quietly
// act on the wrong ground.
func TestAnUnknownProjectRefusesByName(t *testing.T) {
	r := NewRegistry()
	if err := r.Add("carried", t.TempDir()); err != nil {
		t.Fatal(err)
	}

	got, err := r.Resolve("stranger")
	if err == nil {
		t.Fatalf("an unknown project resolved to %q instead of refusing", got.Name)
	}
	if !strings.Contains(err.Error(), "stranger") {
		t.Errorf("the refusal must name what it did not know; got %q", err)
	}
	if got.Home != "" {
		t.Errorf("a refused resolve handed back a Home (%q); a stranger gets no context", got.Home)
	}
}

// AN EMPTY REGISTRY REFUSES TOO, rather than resolving to a zero Tenant whose
// Home is "" -- which downstream is the filesystem root.
func TestAnEmptyRegistryRefusesEvenTheDefault(t *testing.T) {
	r := NewRegistry()
	if _, err := r.Resolve(""); err == nil {
		t.Error("an empty registry resolved the default instead of refusing")
	}
	if _, err := r.Default(); err == nil {
		t.Error("an empty registry named a default it does not have")
	}
}

// ---- a name is a name -----------------------------------------------------

// CASE AND SPACE CANNOT FORK A TENANT. If they could, "Research" and
// "research" would be two grounds with one ledger between them.
func TestANameIsTheSameNameHoweverItWasTyped(t *testing.T) {
	home := t.TempDir()
	r := NewRegistry()
	if err := r.Add("Research", home); err != nil {
		t.Fatal(err)
	}
	for _, spelling := range []string{"research", "RESEARCH", "  Research  ", "ReSeArCh"} {
		got, err := r.Resolve(spelling)
		if err != nil {
			t.Errorf("Resolve(%q) refused a tenant that is carried: %v", spelling, err)
			continue
		}
		if got.Name != "research" {
			t.Errorf("Resolve(%q).Name = %q, want the lowercased key", spelling, got.Name)
		}
	}
	if !r.Has("RESEARCH") {
		t.Error("Has is case-sensitive; it must not be")
	}
	if len(r.Names()) != 1 {
		t.Errorf("one tenant added under several spellings became %v", r.Names())
	}
}

// RE-ADDING A NAME REPLACES IT AND DOES NOT DUPLICATE IT in the order, or
// muster would count the same ground twice.
func TestReAddingANameReplacesRatherThanDuplicates(t *testing.T) {
	first, second := t.TempDir(), t.TempDir()
	r := NewRegistry()
	if err := r.Add("w", first); err != nil {
		t.Fatal(err)
	}
	if err := r.Add("w", second); err != nil {
		t.Fatal(err)
	}
	if n := r.Names(); len(n) != 1 {
		t.Fatalf("re-adding a name produced %v", n)
	}
	got, err := r.Resolve("w")
	if err != nil {
		t.Fatal(err)
	}
	if got.Home != second {
		t.Errorf("Home = %q, want the second Add to win (%q)", got.Home, second)
	}
}

// ADD REFUSES A HALF-DECLARATION. A tenant with no name or no path is not a
// tenant, and accepting one puts a Home of "" into the registry.
func TestAddRefusesAHalfDeclaration(t *testing.T) {
	r := NewRegistry()
	if err := r.Add("", t.TempDir()); err == nil {
		t.Error("a nameless tenant was accepted")
	}
	if err := r.Add("named", ""); err == nil {
		t.Error("a tenant with no path was accepted")
	}
	if n := r.Names(); len(n) != 0 {
		t.Errorf("a refused Add still registered something: %v", n)
	}
}

// ---- home is absolute -----------------------------------------------------

// HOME IS ABSOLUTE, ALWAYS. Every wall check downstream is a prefix test
// against it, and a relative Home makes that test depend on the process's
// working directory -- which is exactly the class of bug that put a world
// outside the estate on the dashboard on the same day these strokes were
// written.
func TestHomeIsMadeAbsoluteOnTheWayIn(t *testing.T) {
	r := NewRegistry()
	if err := r.Add("rel", "."); err != nil {
		t.Fatal(err)
	}
	got, err := r.Resolve("rel")
	if err != nil {
		t.Fatal(err)
	}
	if !filepath.IsAbs(got.Home) {
		t.Errorf("Home = %q, which is not absolute. Every wall check is a "+
			"prefix test against this.", got.Home)
	}
}

// ---- the default ----------------------------------------------------------

// AN EXPLICIT DEFAULT WINS over every fallback. --default-project is the
// operator's word and nothing may outrank it.
func TestAnExplicitDefaultWins(t *testing.T) {
	r := NewRegistry()
	for _, n := range []string{"first", "neiro", "atlas", "chosen"} {
		if err := r.Add(n, t.TempDir()); err != nil {
			t.Fatal(err)
		}
	}
	if err := r.SetDefault("chosen"); err != nil {
		t.Fatal(err)
	}
	got, err := r.Default()
	if err != nil {
		t.Fatal(err)
	}
	if got != "chosen" {
		t.Errorf("Default() = %q; the operator said chosen and that outranks "+
			"neiro, atlas and registration order", got)
	}
	// And an unnamed Resolve lands there.
	tn, err := r.Resolve("")
	if err != nil {
		t.Fatal(err)
	}
	if tn.Name != "chosen" {
		t.Errorf("an unnamed call landed on %q, not the declared default", tn.Name)
	}
}

// WITHOUT AN EXPLICIT DEFAULT THE ORDER IS DECLARED, NOT ACCIDENTAL:
// neiro (the only auto-carry tenant), else atlas, else first registered.
// A map iteration would make this different on every boot.
func TestTheFallbackDefaultIsDeclaredAndNotAccidental(t *testing.T) {
	cases := []struct {
		name  string
		carry []string
		want  string
	}{
		{"neiro outranks everything", []string{"zeta", "atlas", "neiro"}, "neiro"},
		{"atlas is next", []string{"zeta", "atlas"}, "atlas"},
		{"otherwise the first registered", []string{"zeta", "yankee"}, "zeta"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			r := NewRegistry()
			for _, n := range c.carry {
				if err := r.Add(n, t.TempDir()); err != nil {
					t.Fatal(err)
				}
			}
			got, err := r.Default()
			if err != nil {
				t.Fatal(err)
			}
			if got != c.want {
				t.Errorf("Default() = %q, want %q", got, c.want)
			}
		})
	}
}

// SETDEFAULT REFUSES A TENANT THAT IS NOT CARRIED, by name. Accepting one
// would leave the door pointing at nothing on every unnamed call.
func TestSetDefaultRefusesAnUncarriedTenant(t *testing.T) {
	r := NewRegistry()
	if err := r.Add("here", t.TempDir()); err != nil {
		t.Fatal(err)
	}
	err := r.SetDefault("elsewhere")
	if err == nil {
		t.Fatal("SetDefault accepted a tenant that is not carried")
	}
	if !strings.Contains(err.Error(), "elsewhere") {
		t.Errorf("the refusal must name it; got %q", err)
	}
	if got, _ := r.Default(); got != "here" {
		t.Errorf("a refused SetDefault moved the default to %q", got)
	}
}

// ---- order ----------------------------------------------------------------

// NAMES COMES BACK IN REGISTRATION ORDER, because muster prints it and a list
// that reshuffles between boots cannot be read against intent -- which is the
// same lesson the door's own boot line learned on 2026-09-11.
func TestNamesKeepsRegistrationOrder(t *testing.T) {
	r := NewRegistry()
	want := []string{"one", "two", "three", "four"}
	for _, n := range want {
		if err := r.Add(n, t.TempDir()); err != nil {
			t.Fatal(err)
		}
	}
	got := r.Names()
	if len(got) != len(want) {
		t.Fatalf("Names() = %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("Names() = %v, want %v (registration order)", got, want)
		}
	}
	// And the slice handed out is a copy: a caller that sorts it must not
	// reorder the registry underneath muster.
	got[0] = "mutated"
	if r.Names()[0] != "one" {
		t.Error("Names() handed out the registry's own slice; a caller mutating " +
			"it changed the registration order")
	}
}

// SETENGINE REFUSES AN UNCARRIED TENANT rather than silently wiring nothing.
func TestSetEngineRefusesAnUncarriedTenant(t *testing.T) {
	r := NewRegistry()
	if err := r.SetEngine("ghost", "python x.py"); err == nil {
		t.Error("wired an engine for a tenant that is not carried")
	}
}

// THE ARCHIVE IS NOT A TENANT, BY ANY ROAD (2026-09-12). The walk in `ground`
// refuses to FIND it; this refuses to CARRY it when something hands it over
// directly. Detection was the road it actually came in by, twice, and a rule
// that guards only the road it was broken on is a rule with a way around it.
func TestTheArchiveIsNeverCarried(t *testing.T) {
	r := NewRegistry()
	base := t.TempDir()

	// by name, whatever path it is given
	if err := r.Add("archive", filepath.Join(base, "somewhere")); err == nil {
		t.Fatal("registry carried a tenant named archive")
	} else if !strings.Contains(err.Error(), "RULE 1") {
		t.Fatalf("the refusal must say why: %v", err)
	}
	// by path, whatever name it is given
	if err := r.Add("notes", filepath.Join(base, "Desktop", "Archive")); err == nil {
		t.Fatal("registry carried the archive under another name")
	}
	// and anything inside it
	if err := r.Add("module", filepath.Join(base, "Archive", "module")); err == nil {
		t.Fatal("registry carried a world inside the archive")
	}
	if len(r.Names()) != 0 {
		t.Fatalf("a refused tenant must leave no trace: %v", r.Names())
	}

	// AND THE WAY THAT MUST NOT FIRE -- a real world still lands
	if err := r.Add("research", filepath.Join(base, "Research")); err != nil {
		t.Fatalf("a real tenant was refused: %v", err)
	}
	if err := r.Add("archived", filepath.Join(base, "archived")); err != nil {
		t.Fatalf("`archived` is not `archive`: %v", err)
	}
	if got := r.Names(); len(got) != 2 {
		t.Fatalf("expected the two real worlds, got %v", got)
	}
}
