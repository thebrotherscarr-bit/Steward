// Chat streaming face (N1): GET /chat/stream sends Server-Sent Events.
// Tokens stream as `event: token`; the witnessed whole answer closes as
// `event: done` with its receipt; refusals arrive as `event: refused`.
// The handler owns no logic — guard, route, ask, witness and append all
// live in the chat package behind the one-writer lock, shared with the
// tools/call face. Strangers are refused by name before anything streams.
package httpserver

import (
	"encoding/json"
	"fmt"
	"net/http"

	"atlas/line/internal/tools"
)

func (s *Server) handleChatStream(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	args := map[string]any{
		"session":  q.Get("session"),
		"question": q.Get("question"),
		"actor":    q.Get("actor"),
		"voice":    q.Get("voice"),
		"project":  q.Get("project"),
	}
	if s.auth.On {
		cred := s.credentialFor(bearer(r.Header.Get("Authorization")))
		if err := s.gateCall("chat_send", args, cred); err != nil {
			s.m.err()
			http.Error(w, err.Error(), http.StatusUnauthorized)
			return
		}
	}
	s.m.inc("chat/stream")
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

	emit := func(ev string, data any) {
		b, _ := json.Marshal(data)
		fmt.Fprintf(w, "event: %s\ndata: %s\n\n", ev, string(b))
		flusher.Flush()
	}
	notify := r.Context().Done()
	done := make(chan struct{})
	var out string
	var callErr error
	go func() {
		defer close(done)
		out, callErr = tools.ChatSendStream(s.tools, tn, args, func(tok string) {
			emit("token", map[string]any{"token": tok})
		})
	}()
	select {
	case <-done:
	case <-notify:
		// The browser went away mid-turn: the send keeps its own
		// counsel (whole or nothing, witnessed or not).
		return
	}
	if callErr != nil {
		emit("refused", map[string]any{"error": callErr.Error()})
		return
	}
	emit("done", map[string]any{"text": out})
}
