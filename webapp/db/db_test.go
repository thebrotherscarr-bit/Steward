// The first strokes on the glass's store.
//
// WHY THIS FILE DID NOT EXIST UNTIL 2026-09-12. The `webapp` module is ~2,800
// lines over eight packages and had ONE test function in all of it, in
// handlers/ws_test.go. ADR-006 made the same measurement about the door -- the
// protocol layer and the tenant model were its two least-tested things, and
// both were given first strokes on 2026-09-11. The glass never had that pass,
// and the operator named it the one thing to fix before field testing.
//
// This package is where every trace, eval, agent and message actually lives.
// Nothing here was a bug; what was missing was any statement of what it
// PROMISES, so the blast radius of a change was discoverable only by suffering
// it.
//
// Hermetic: temp directories only, nothing read from the real estate.
package db

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestARoundTripSurvivesReopening(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "store")
	d, err := Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	d.AddTrace(Trace{ID: "t1", AgentID: "a1", Tool: "run_python", Tenant: "research"})
	d.AddEval(Eval{ID: "e1", TraceID: "t1", Name: "verdict", Passed: true})
	d.UpsertAgent(Agent{ID: "a1", Office: "Router"})
	d.AddMessage(Message{ID: "m1", Channel: "ops", Content: "hi"})
	d.SetKey("mcp_url", "http://127.0.0.1:8090")
	if err := d.Close(); err != nil {
		t.Fatal(err)
	}

	// A NEW HANDLE ON THE SAME DIRECTORY IS THE WHOLE PROMISE. Every write
	// above calls Save(); if any of them did not, this is where it shows.
	again, err := Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	if got := again.GetTrace("t1"); got == nil || got.Tool != "run_python" {
		t.Fatalf("trace did not survive: %+v", got)
	}
	if got := again.GetTrace("t1"); got.Tenant != "research" {
		t.Fatalf("the tenant did not survive, and it is what the wall reads: %+v", got)
	}
	if e := again.GetEvals("t1"); len(e) != 1 || !e[0].Passed {
		t.Fatalf("eval did not survive: %+v", e)
	}
	if a := again.GetAgent("a1"); a == nil || a.Office != "Router" {
		t.Fatalf("agent did not survive: %+v", a)
	}
	if m := again.GetMessages("ops", 10); len(m) != 1 {
		t.Fatalf("message did not survive: %+v", m)
	}
	if again.GetKey("mcp_url") == "" {
		t.Fatal("the key did not survive, and the glass finds the door by it")
	}
	// AND A KEY NOBODY SET IS EMPTY, not a zero value that reads as a setting
	if again.GetKey("never_set") != "" {
		t.Fatal("an unset key must answer empty")
	}
}

func TestTheSaveIsAtomicAndLeavesNoScratch(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "store")
	d, _ := Open(dir)
	d.AddTrace(Trace{ID: "t1"})

	// tmp-then-rename, so a reader never sees a half-written store. The scratch
	// file must not be left behind either: `store.json.tmp` sitting in the
	// directory is how a later reader learns a write died midway.
	if _, err := os.Stat(filepath.Join(dir, "store.json")); err != nil {
		t.Fatalf("no store written: %v", err)
	}
	if _, err := os.Stat(filepath.Join(dir, "store.json.tmp")); err == nil {
		t.Fatal("the scratch file was left behind")
	}
	// and it is real JSON a person can read, not an opaque blob
	raw, err := os.ReadFile(filepath.Join(dir, "store.json"))
	if err != nil {
		t.Fatal(err)
	}
	var fd fileData
	if err := json.Unmarshal(raw, &fd); err != nil {
		t.Fatalf("the store is not readable JSON: %v", err)
	}
}

func TestNewestFirstAndTheLimitHolds(t *testing.T) {
	d, _ := Open(filepath.Join(t.TempDir(), "store"))
	for _, id := range []string{"t1", "t2", "t3"} {
		d.AddTrace(Trace{ID: id, AgentID: "a1", CreatedAt: time.Now()})
	}
	d.AddTrace(Trace{ID: "other", AgentID: "a2"})

	all := d.GetTraces("", 0)
	if len(all) != 4 {
		t.Fatalf("want 4 traces, got %d", len(all))
	}
	// NEWEST FIRST. A trace log read oldest-first shows a stale top on every
	// page, which is the one thing the page is for.
	if all[0].ID != "other" {
		t.Fatalf("newest must lead: %s", all[0].ID)
	}
	if got := d.GetTraces("a1", 2); len(got) != 2 || got[0].ID != "t3" {
		t.Fatalf("limit + order broke: %d %+v", len(got), got)
	}
	// filtering by agent must not leak another agent's rows
	for _, tr := range d.GetTraces("a1", 0) {
		if tr.AgentID != "a1" {
			t.Fatalf("agent filter leaked %s", tr.AgentID)
		}
	}
	// a trace nobody wrote is absent, not a zero value
	if d.GetTrace("ghost") != nil {
		t.Fatal("a missing trace must be nil, never an empty Trace")
	}
}

func TestUpsertReplacesRatherThanDuplicates(t *testing.T) {
	d, _ := Open(filepath.Join(t.TempDir(), "store"))
	d.UpsertAgent(Agent{ID: "a1", Office: "Router", Role: "route"})
	d.UpsertAgent(Agent{ID: "a1", Office: "Router", Role: "READ ONLY"})
	d.UpsertAgent(Agent{ID: "a2", Office: "Steward"})

	if n := len(d.GetAgents()); n != 2 {
		t.Fatalf("upsert duplicated: %d agents", n)
	}
	if a := d.GetAgent("a1"); a.Role != "READ ONLY" {
		t.Fatalf("upsert did not replace: %+v", a)
	}
}

func TestGetAgentsHandsBackACopy(t *testing.T) {
	d, _ := Open(filepath.Join(t.TempDir(), "store"))
	d.UpsertAgent(Agent{ID: "a1", Office: "Router"})

	got := d.GetAgents()
	got[0].Office = "TAMPERED"

	// A caller that mutates the slice it was handed must not reach the store.
	// `GetAgents` copies on purpose; nothing said so until now.
	if a := d.GetAgent("a1"); a.Office != "Router" {
		t.Fatalf("a caller's write reached the store: %+v", a)
	}
}

// AND THE HONEST LIMIT, NAMED RATHER THAN FOUND LATER. `load()` ignores a
// store.json it cannot read: no error, no log, an empty database. That is a
// deliberate choice for a missing file and it is the SAME path for a corrupt
// one, so a damaged store comes up silently empty rather than refusing to
// start. This stroke does not call that right -- it pins it, so a change is a
// decision instead of a surprise.
func TestACorruptStoreComesUpEmptyAndSaysNothing(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "store")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "store.json"),
		[]byte("{not json at all"), 0o644); err != nil {
		t.Fatal(err)
	}
	d, err := Open(dir)
	if err != nil {
		t.Fatalf("Open refused a corrupt store: %v", err)
	}
	if n := len(d.GetTraces("", 0)); n != 0 {
		t.Fatalf("want an empty store, got %d traces", n)
	}
	// and a write over it succeeds, which is how the corruption becomes
	// permanent -- the old bytes are gone after the first Save
	d.AddTrace(Trace{ID: "t1"})
	if d.GetTrace("t1") == nil {
		t.Fatal("a write after a corrupt load must still work")
	}
}
