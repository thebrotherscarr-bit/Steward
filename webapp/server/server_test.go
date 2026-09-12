// The first strokes on the glass's front door.
//
// `webapp` had one test function in ~2,800 lines. This package holds the
// session gate and the cache validators, and neither had a statement of what
// it promises.
//
// WHAT CANNOT BE REACHED FROM HERE, said plainly rather than worked around:
// the route table is built inside `ListenAndServe`, which then binds a port,
// so the mux itself is not testable without refactoring that function. The two
// things that decide whether a request is ANSWERED AT ALL -- `gated` and
// `etags` -- are both reachable, and they are what these strokes hold.
package server

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"testing/fstest"

	"atlas/webapp/agents"
	"atlas/webapp/db"
	"atlas/webapp/evals"
	"atlas/webapp/handlers"
	"atlas/webapp/messaging"
	"atlas/webapp/search"
	"atlas/webapp/traces"
)

func newHandlers(t *testing.T) *handlers.Handlers {
	t.Helper()
	database, err := db.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	store := traces.NewStore(database)
	reg := agents.NewRegistry(database)
	return handlers.New(store, reg, evals.NewEngine(database, store),
		search.NewEngine(store, reg), messaging.NewBus())
}

// ok is the handler the gate wraps; it records that the request got through.
func ok(hit *bool) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		*hit = true
		w.WriteHeader(http.StatusOK)
	})
}

func TestEveryEmbeddedFileGetsAQuotedValidator(t *testing.T) {
	fsys := fstest.MapFS{
		"index.html":  {Data: []byte("<html>")},
		"js/home.js":  {Data: []byte("console.log(1)")},
		"js/same.js":  {Data: []byte("console.log(1)")},
		"css/app.css": {Data: []byte("body{}")},
	}
	tags := etags(fsys)

	if len(tags) != 4 {
		t.Fatalf("want a tag per file, got %d: %v", len(tags), tags)
	}
	for path, tag := range tags {
		// AN ETAG MUST BE QUOTED. An unquoted one is not a valid entity-tag
		// and a browser is free to ignore it, which puts us back where
		// 2026-09-09 started: a tab holding stale bytes across four rebuilds.
		if !strings.HasPrefix(tag, `"`) || !strings.HasSuffix(tag, `"`) {
			t.Fatalf("%s: tag %s is not quoted", path, tag)
		}
	}
	// SAME BYTES, SAME TAG -- it is a content hash, not a path hash, so a
	// rebuild that does not change a file does not bust its cache.
	if tags["js/home.js"] != tags["js/same.js"] {
		t.Fatal("identical bytes must hash to the same tag")
	}
	// and different bytes differ, which is what ends the 304 after a rebuild
	if tags["index.html"] == tags["css/app.css"] {
		t.Fatal("different bytes must hash differently")
	}

	// a directory is not a file and gets no tag
	nested := fstest.MapFS{"a/b/c.js": {Data: []byte("x")}}
	if n := len(etags(nested)); n != 1 {
		t.Fatalf("directories must not be tagged: %v", etags(nested))
	}
}

func TestWithAuthOffTheGateIsInert(t *testing.T) {
	// THIS IS PRODUCTION TODAY. `ConfigureAuth` has no caller anywhere in the
	// module, so `authOn` is false for the life of every process and this is
	// the only path a real request takes. Pinned as the fact it is.
	s := &Server{handlers: newHandlers(t)}
	for _, path := range []string{"/api/traces", "/ws", "/metrics", "/", "/records"} {
		hit := false
		w := httptest.NewRecorder()
		s.gated(ok(&hit)).ServeHTTP(w, httptest.NewRequest("GET", path, nil))
		if !hit {
			t.Fatalf("auth off: %s was gated, and nothing should be", path)
		}
	}
}

func TestWithAuthOnTheGateRefusesTheRightThings(t *testing.T) {
	// THE MECHANISM WORKS; NOTHING TURNS IT ON. Configured by hand here, which
	// is the only way it can be configured -- see the finding above. If the
	// wiring lands, this stroke is what says the gate was already right.
	h := newHandlers(t)
	h.ConfigureAuth(true, "", t.TempDir()+"/sessions.json")
	s := &Server{handlers: h}

	// OPEN, because the login page and a health probe must work ungated, and
	// a platform hook is authenticated by its own signature, not a cookie.
	for _, path := range []string{"/api/login", "/api/health", "/hooks/slack"} {
		hit := false
		w := httptest.NewRecorder()
		s.gated(ok(&hit)).ServeHTTP(w, httptest.NewRequest("POST", path, nil))
		if !hit {
			t.Fatalf("auth on: %s must stay open", path)
		}
	}

	// THE STATIC FACE IS OPEN TOO -- the login page itself has to load, and it
	// is served by the catch-all, not by an /api route.
	hit := false
	w := httptest.NewRecorder()
	s.gated(ok(&hit)).ServeHTTP(w, httptest.NewRequest("GET", "/login", nil))
	if !hit {
		t.Fatal("auth on: the login page must load ungated")
	}

	// AN API CALL WITH NO SESSION IS REFUSED IN JSON, not redirected -- a
	// fetch() that follows a 302 to an HTML page reports a parse error, and
	// the page then shows nothing rather than "login required".
	hit = false
	w = httptest.NewRecorder()
	s.gated(ok(&hit)).ServeHTTP(w, httptest.NewRequest("GET", "/api/traces", nil))
	if hit {
		t.Fatal("auth on: /api/traces reached the handler with no session")
	}
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("want 401, got %d", w.Code)
	}
	if ct := w.Header().Get("Content-Type"); ct != "application/json" {
		t.Fatalf("want a JSON refusal, got %q", ct)
	}
	if !strings.Contains(w.Body.String(), "login required") {
		t.Fatalf("the refusal must say what to do: %q", w.Body.String())
	}

	// /metrics AND /ws ARE NOT OPEN. Metrics carry global counts and the
	// socket carries live engine events; both are behind the gate.
	for _, path := range []string{"/metrics", "/ws"} {
		hit = false
		w = httptest.NewRecorder()
		s.gated(ok(&hit)).ServeHTTP(w, httptest.NewRequest("GET", path, nil))
		if hit {
			t.Fatalf("auth on: %s reached the handler with no session", path)
		}
	}

	// a page request redirects to the login page rather than 401-ing a human
	hit = false
	w = httptest.NewRecorder()
	s.gated(ok(&hit)).ServeHTTP(w, httptest.NewRequest("GET", "/ws/thing", nil))
	if hit {
		t.Fatal("auth on: a /ws path reached the handler")
	}
	if w.Code != http.StatusFound {
		t.Fatalf("a non-api path wants a redirect, got %d", w.Code)
	}
	if loc := w.Header().Get("Location"); loc != "/login" {
		t.Fatalf("redirect went to %q, want /login", loc)
	}
}

func TestTheGateCountsEveryRequestIncludingRefusedOnes(t *testing.T) {
	// /metrics is fed from here, and a refused request is still traffic. A
	// counter that only saw successes would hide exactly the burst a person
	// most wants to see.
	h := newHandlers(t)
	h.ConfigureAuth(true, "", t.TempDir()+"/sessions.json")
	s := &Server{handlers: h}

	hit := false
	w := httptest.NewRecorder()
	s.gated(ok(&hit)).ServeHTTP(w, httptest.NewRequest("GET", "/api/traces", nil))
	if hit || w.Code != http.StatusUnauthorized {
		t.Fatal("premise: that request should have been refused")
	}

	m := httptest.NewRecorder()
	h.Metrics(m, httptest.NewRequest("GET", "/metrics", nil))
	if !strings.Contains(m.Body.String(), "GET /api/traces") {
		t.Fatalf("the refused request was not counted:\n%s", m.Body.String())
	}
}
