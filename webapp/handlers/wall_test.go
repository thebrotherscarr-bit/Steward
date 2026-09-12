// THE GLASS'S TENANT WALL, which nothing had ever stated.
//
// `webapp` had one test function in ~2,800 lines (ws_test.go) and this is the
// part that decides whether one workspace can read another's rows. ADR-006
// made the same measurement about the door; its protocol and tenant layers got
// first strokes 2026-09-11 and the glass did not.
//
// Every check here is a property the code already has. The point is that it is
// now SAID, so a change to `visible` is a decision somebody made rather than a
// leak nobody noticed.
package handlers

import (
	"encoding/json"
	"net/http/httptest"
	"testing"

	"atlas/webapp/agents"
	"atlas/webapp/db"
	"atlas/webapp/evals"
	"atlas/webapp/messaging"
	"atlas/webapp/search"
	"atlas/webapp/traces"
)

func TestVisibleIsTheWholeWall(t *testing.T) {
	// NO SESSION TENANT SEES EVERYTHING. That is the auth-off case, and it is
	// why `visible` cannot be read as "deny by default": with auth off there
	// is no tenant to compare against and the glass is a local tool.
	if !visible("research", "") {
		t.Fatal("with no session tenant, every row must show")
	}

	// a tenant sees its own
	if !visible("research", "research") {
		t.Fatal("a tenant must see its own rows")
	}

	// AND NOT ANOTHER'S. This is the line that matters.
	if visible("atlas", "research") {
		t.Fatal("research saw an atlas row")
	}

	// AN UNTENANTED ROW IS VISIBLE TO EVERY TENANT, and that is deliberate:
	// rows written before auth was turned on carry no tenant, and hiding them
	// from everyone would blank the glass on the day auth goes on. It is also
	// the widest thing this function does, so it is pinned rather than
	// assumed.
	if !visible("", "research") {
		t.Fatal("a row with no tenant must still show")
	}
	if !visible("", "atlas") {
		t.Fatal("an untenanted row shows for every tenant, by design")
	}
}

func TestTheFiltersDropAnotherTenantsRows(t *testing.T) {
	tr := []db.Trace{
		{ID: "mine", Tenant: "research"},
		{ID: "theirs", Tenant: "atlas"},
		{ID: "shared", Tenant: ""},
	}
	got := filterTraces(tr, "research")
	if len(got) != 2 {
		t.Fatalf("want mine + shared, got %d: %+v", len(got), got)
	}
	for _, x := range got {
		if x.ID == "theirs" {
			t.Fatal("filterTraces leaked another tenant's row")
		}
	}

	ev := []db.Eval{{ID: "mine", Tenant: "research"}, {ID: "theirs", Tenant: "atlas"}}
	if e := filterEvals(ev, "research"); len(e) != 1 || e[0].ID != "mine" {
		t.Fatalf("filterEvals leaked: %+v", e)
	}

	ag := []db.Agent{{ID: "mine", Tenant: "research"}, {ID: "theirs", Tenant: "atlas"}}
	if a := filterAgents(ag, "research"); len(a) != 1 || a[0].ID != "mine" {
		t.Fatalf("filterAgents leaked: %+v", a)
	}

	// EMPTY IN, EMPTY OUT -- never nil. These faces marshal straight to JSON,
	// and a nil slice becomes `null` where the page expects `[]`.
	if out := filterTraces(nil, "research"); out == nil {
		t.Fatal("filterTraces returned nil; the page would get null, not []")
	}
	if out := filterEvals(nil, "research"); out == nil {
		t.Fatal("filterEvals returned nil")
	}
	if out := filterAgents(nil, "research"); out == nil {
		t.Fatal("filterAgents returned nil")
	}
}

// newTestHandlers builds a Handlers over a temp store. Nothing here touches
// the real estate.
func newTestHandlers(t *testing.T) *Handlers {
	t.Helper()
	database, err := db.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	store := traces.NewStore(database)
	reg := agents.NewRegistry(database)
	ev := evals.NewEngine(database, store)
	se := search.NewEngine(store, reg)
	bus := messaging.NewBus()
	return New(store, reg, ev, se, bus)
}

func TestHealthHidesCardinalityUnderAuth(t *testing.T) {
	h := newTestHandlers(t)

	// AUTH OFF: the counts are there, because the glass is a local tool and
	// they are the fastest thing on the dashboard.
	w := httptest.NewRecorder()
	h.Health(w, httptest.NewRequest("GET", "/api/health", nil))
	var off map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &off); err != nil {
		t.Fatal(err)
	}
	for _, k := range []string{"agents", "traces", "evals"} {
		if _, ok := off[k]; !ok {
			t.Fatalf("auth off: %q should be reported: %v", k, off)
		}
	}
	if off["version"] == "" || off["version"] == nil {
		t.Fatal("health must carry the version, and it is read from VERSION")
	}

	// AUTH ON: they are GONE. Counts are global rows, so one workspace must
	// never learn another's cardinality from an unauthenticated health probe.
	h.authOn = true
	w2 := httptest.NewRecorder()
	h.Health(w2, httptest.NewRequest("GET", "/api/health", nil))
	var on map[string]any
	if err := json.Unmarshal(w2.Body.Bytes(), &on); err != nil {
		t.Fatal(err)
	}
	for _, k := range []string{"agents", "traces", "evals"} {
		if _, ok := on[k]; ok {
			t.Fatalf("auth on: %q leaked a global count: %v", k, on)
		}
	}
	// and it still answers, with the facts that are nobody's secret
	if on["status"] != "ok" {
		t.Fatalf("health stopped answering under auth: %v", on)
	}
	if on["auth"] != true {
		t.Fatalf("health must say auth is on: %v", on)
	}
}

func TestTenantOfIsEmptyWithNoSession(t *testing.T) {
	h := newTestHandlers(t)
	r := httptest.NewRequest("GET", "/api/traces", nil)

	// auth off: sessionOf returns (nil, true), so the tenant is "" and
	// `visible` shows everything -- the local-tool case, stated.
	if got := h.tenantOf(r); got != "" {
		t.Fatalf("auth off tenant = %q, want empty", got)
	}

	// auth on with NO cookie: still empty. That is the sharp edge -- an empty
	// tenant means "see everything" in `visible`, so a face that forgets to
	// demand a session shows every row. The faces that matter check
	// `sessionOf` and refuse first; this pins why they have to.
	h.authOn = true
	if got := h.tenantOf(r); got != "" {
		t.Fatalf("auth on, no cookie: tenant = %q, want empty", got)
	}
	if _, ok := h.sessionOf(r); ok {
		t.Fatal("auth on with no cookie must not resolve a session")
	}
}
