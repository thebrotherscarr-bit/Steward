package httpserver

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"atlas/line/internal/engine"
	"atlas/line/internal/tools"
)

// GET /run/stream — one council turn, over SSE, as it happens.
//
// This is the modern chat surface, and it is deliberately NOT a second chat
// implementation. /chat/stream reaches a MODEL (chat_send -> rack.Ask). This
// reaches the COUNCIL: the objective goes into the world's own Manjuel process,
// so the sealed law gate stamps it, the one Router runs the tools, the dedup
// refuses a repeat and the recompose puts every failure in the delivery. The
// browser is shown the engine's OWN events, unedited and in order -- there is
// no place in this handler where a seat's prose could be mistaken for a fact
// about what ran (LAW 5).
//
// Query: project, objective  (or) project, answer
// The `answer` form is the gate crossing the wire. Nothing here defaults it.
//
// EVERY engine event rides ONE frame name -- `event: engine` -- with the
// engine's own kind inside the payload. This is deliberate and was earned:
// EventSource fires only listeners it was given a name for and has no
// wildcard, so a per-kind frame name means a client silently loses every
// event added to the core after that client was written. On a surface whose
// whole claim is "this is what actually ran", a dropped event is
// indistinguishable from nothing having happened. One name, and the client
// dispatches on the kind it reads.
//
// This handler's own three frames are named apart -- stream_open,
// stream_end, stream_error -- so they can never be mistaken for the core's
// `refused`, which is a real terminal event with a different meaning.
func (s *Server) handleRunStream(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	objective := q.Get("objective")
	answer := q.Get("answer")
	hasAnswer := q.Has("answer")

	if s.auth.On {
		name := "run_start"
		args := map[string]any{"project": q.Get("project"), "objective": objective}
		if hasAnswer {
			name, args = "run_answer", map[string]any{"project": q.Get("project"), "text": answer}
		}
		cred := s.credentialFor(bearer(r.Header.Get("Authorization")))
		if err := s.gateCall(name, args, cred); err != nil {
			s.m.err()
			http.Error(w, err.Error(), http.StatusUnauthorized)
			return
		}
	}
	s.m.inc("run/stream")

	tn, err := s.tenants.Resolve(q.Get("project"))
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming unsupported", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")

	// The sink runs on the engine's pump goroutine; `frames` hands each event
	// to THIS goroutine, which owns the socket. Writing to an http.ResponseWriter
	// from two goroutines is a data race, and a raced SSE stream is a garbled
	// record of what the council did.
	frames := make(chan engine.Event, 256)
	done := make(chan struct{})

	var res engine.Result
	var callErr error
	go func() {
		defer close(done)
		defer close(frames)
		sink := func(ev engine.Event) { frames <- ev }
		if hasAnswer {
			res, callErr = tools.AnswerStream(tn, answer, sink)
			return
		}
		res, callErr = tools.RunStream(tn, objective, q.Get("feed"), q.Get("method"), sink)
	}()

	emit := func(kind string, data any) {
		b, _ := json.Marshal(data)
		fmt.Fprintf(w, "event: %s\ndata: %s\n\n", kind, string(b))
		flusher.Flush()
	}
	emit("stream_open", map[string]any{"world": tn.Name, "objective": objective, "answering": hasAnswer})

	gone := r.Context().Done()
	for {
		select {
		case ev, ok := <-frames:
			if !ok {
				frames = nil
				continue
			}
			emit("engine", ev)
		case <-done:
			// Drain whatever the sink queued before the turn ended: a delivery
			// event that never reached the glass is a turn the operator cannot
			// see the result of.
			//
			// GUARDED, and it was not: `frames` is set to nil above when the
			// channel closes, and ranging a NIL channel blocks forever. That
			// deadlocked this handler after every turn whose events all arrived
			// before `done` -- stream_end was never sent, the goroutine leaked,
			// and the glass showed a finished answer under a running spinner.
			// nil here means already drained and closed, so there is nothing to
			// lose by skipping it.
			if frames != nil {
				for ev := range frames {
					emit("engine", ev)
				}
			}
			if callErr != nil {
				emit("stream_error", map[string]any{"error": callErr.Error()})
				return
			}
			emit("stream_end", map[string]any{
				"waiting": res.Waiting,
				"tokens":  res.Tokens,
				"dropped": res.Dropped,
			})
			return
		case <-gone:
			// The browser closed the tab. The turn keeps running inside the
			// engine and its transcript still lands -- a closed glass does not
			// cancel the council's work, and only run_cancel does that.
			return
		}
	}
}

// GET /run/listen — one spoken turn, over SSE.
//
// SSE rather than a plain request because a capture lasts as long as the
// operator takes to speak, and voice.py's own progress lines ("listening --
// speak; the turn ends when you go quiet", then "2.3s heard -- transcribing")
// are what make a mic button feel alive instead of frozen. They ride the same
// `engine` frame as every other event.
//
// The turn ends with `heard`, carrying the text. NOTHING IS RUN: the glass puts
// those words in the box for him to read and send.
func (s *Server) handleRunListen(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	if s.auth.On {
		cred := s.credentialFor(bearer(r.Header.Get("Authorization")))
		if err := s.gateCall("run_start", map[string]any{"project": q.Get("project")}, cred); err != nil {
			s.m.err()
			http.Error(w, err.Error(), http.StatusUnauthorized)
			return
		}
	}
	s.m.inc("run/listen")
	tn, err := s.tenants.Resolve(q.Get("project"))
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming unsupported", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")

	seconds := 0
	if v, err := strconv.Atoi(q.Get("seconds")); err == nil {
		seconds = v
	}

	frames := make(chan engine.Event, 64)
	done := make(chan struct{})
	var said string
	var callErr error
	go func() {
		defer close(done)
		defer close(frames)
		said, callErr = tools.ListenStream(tn, seconds, func(ev engine.Event) { frames <- ev })
	}()

	emit := func(kind string, data any) {
		b, _ := json.Marshal(data)
		fmt.Fprintf(w, "event: %s\ndata: %s\n\n", kind, string(b))
		flusher.Flush()
	}
	emit("stream_open", map[string]any{"world": tn.Name, "listening": true})

	gone := r.Context().Done()
	for {
		select {
		case ev, ok := <-frames:
			if !ok {
				frames = nil
				continue
			}
			emit("engine", ev)
		case <-done:
			// Guarded: frames is nil once drained and closed, and ranging a
			// nil channel blocks forever (the fault that deadlocked
			// /run/stream after every turn).
			if frames != nil {
				for ev := range frames {
					emit("engine", ev)
				}
			}
			if callErr != nil {
				emit("stream_error", map[string]any{"error": callErr.Error()})
				return
			}
			emit("stream_end", map[string]any{"heard": said})
			return
		case <-gone:
			// He closed the tab mid-capture. The engine finishes the capture
			// and drops the text on the floor; nothing was run, so nothing is
			// half-done.
			return
		}
	}
}

// GET /run/state — is there an engine standing on this world, and is it waiting
// on the operator? The glass asks before it offers a send box, so a refusal is
// a disabled control with a reason rather than a turn that fails.
func (s *Server) handleRunState(w http.ResponseWriter, r *http.Request) {
	s.m.inc("run/state")
	tn, err := s.tenants.Resolve(r.URL.Query().Get("project"))
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	b, _ := json.Marshal(tools.Facts(tn))
	w.Write(b)
}
