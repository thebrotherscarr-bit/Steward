// The COUNCIL, proxied. /api/chat/stream reaches a MODEL -- one voice, one
// rack.Ask. These reach the ESTATE: the objective goes into the world's own
// Manjuel process, so the sealed law gate stamps it, the one Router runs the
// tools, the dedup refuses a repeat and the recompose puts every failure in the
// delivery. The webapp owns no council logic and never will; it proxies the
// LINE's /run/stream byte-for-byte, exactly as StreamChat proxies /chat/stream.
package handlers

import (
	"bufio"
	"fmt"
	"io"
	"net/http"
	"strings"
)

// StreamCouncil proxies GET /run/stream. Two forms, both the operator's:
//
//	?objective=...  fire a turn
//	?answer=...     answer what the council asked (the gate on the wire)
//
// Nothing here supplies a default for the answer form. If the council stopped
// to ask, the reply is his (RULE 6).
func (h *Handlers) StreamCouncil(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	req, err := http.NewRequest("GET", h.mcpURL()+"/run/stream", nil)
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	qq := req.URL.Query()
	if q.Has("answer") {
		qq.Set("answer", q.Get("answer"))
	} else {
		qq.Set("objective", q.Get("objective"))
		qq.Set("feed", q.Get("feed"))
		qq.Set("method", q.Get("method"))
	}
	if err := h.scopeProject(r, qq, q.Get("project")); err != nil {
		jsonErr(w, 401, err.Error())
		return
	}
	req.URL.RawQuery = qq.Encode()
	h.pipeSSE(w, r, req)
}

// ListenCouncil proxies GET /run/listen: one spoken turn, captured by the
// core's own whisper on this machine. No audio touches this process, the
// browser or the network -- the engine holds the microphone.
func (h *Handlers) ListenCouncil(w http.ResponseWriter, r *http.Request) {
	req, err := http.NewRequest("GET", h.mcpURL()+"/run/listen", nil)
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	qq := req.URL.Query()
	if v := r.URL.Query().Get("seconds"); v != "" {
		qq.Set("seconds", v)
	}
	if err := h.scopeProject(r, qq, r.URL.Query().Get("project")); err != nil {
		jsonErr(w, 401, err.Error())
		return
	}
	req.URL.RawQuery = qq.Encode()
	h.pipeSSE(w, r, req)
}

// CouncilState proxies GET /run/state: is an engine standing on this world, and
// is it waiting on an answer? The glass asks before it offers a send box, so a
// refusal is a disabled control with a reason rather than a turn that fails.
func (h *Handlers) CouncilState(w http.ResponseWriter, r *http.Request) {
	req, err := http.NewRequest("GET", h.mcpURL()+"/run/state", nil)
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	qq := req.URL.Query()
	if err := h.scopeProject(r, qq, r.URL.Query().Get("project")); err != nil {
		jsonErr(w, 401, err.Error())
		return
	}
	req.URL.RawQuery = qq.Encode()
	if h.service != "" {
		req.Header.Set("Authorization", "Bearer "+h.service)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		jsonErr(w, 502, fmt.Sprintf("mcp unreachable: %v", err))
		return
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 64<<10))
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	w.Write(body)
}

// scopeProject pins the call to the caller's own world when the gate is on. A
// logged-in caller may never name another tenant's ground on the query string.
func (h *Handlers) scopeProject(r *http.Request, qq map[string][]string, asked string) error {
	set := func(v string) {
		if v != "" {
			qq["project"] = []string{v}
		}
	}
	if !h.authOn {
		set(asked)
		return nil
	}
	sess, ok := h.sessionOf(r)
	if !ok || sess == nil {
		return fmt.Errorf("login required")
	}
	set(sess.Tenant)
	return nil
}

// pipeSSE streams the MCP door's event-stream through to the browser line by
// line. Shared by every SSE proxy so there is one place where the flush, the
// disconnect and the buffer bound are decided.
func (h *Handlers) pipeSSE(w http.ResponseWriter, r *http.Request, req *http.Request) {
	if h.service != "" {
		req.Header.Set("Authorization", "Bearer "+h.service)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		jsonErr(w, 502, fmt.Sprintf("mcp unreachable: %v", err))
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		raw, _ := io.ReadAll(io.LimitReader(resp.Body, 4<<10))
		jsonErr(w, 502, strings.TrimSpace(string(raw)))
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	flusher, ok := w.(http.Flusher)
	if !ok {
		return
	}
	sc := bufio.NewScanner(resp.Body)
	sc.Buffer(make([]byte, 0, 1<<20), 8<<20)
	notify := r.Context().Done()
	lines := make(chan string, 64)
	go func() {
		defer close(lines)
		for sc.Scan() {
			select {
			case lines <- sc.Text():
			case <-notify:
				return
			}
		}
	}()
	for {
		select {
		case l, ok := <-lines:
			if !ok {
				return
			}
			fmt.Fprintf(w, "%s\n", l)
			flusher.Flush()
		case <-notify:
			return
		}
	}
}
