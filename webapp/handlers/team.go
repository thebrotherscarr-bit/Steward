// Team faces (N5): send/history/status through MCP /rpc plus the inbound
// webhook door. The webapp holds no secrets and owns no bridge logic —
// HMAC verification, parsing, dedupe and the record all live in the
// LINE's team package; this face reads bodies, forwards, and announces.
package handlers

import (
	"encoding/json"
	"io"
	"net/http"
	"strconv"
	"strings"
)

// TeamSend proxies team_send (guarded, receipted) and announces it.
func (h *Handlers) TeamSend(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Platform string `json:"platform"`
		Channel  string `json:"channel"`
		Content  string `json:"content"`
		Actor    string `json:"actor"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if strings.TrimSpace(body.Platform) == "" || strings.TrimSpace(body.Content) == "" {
		jsonErr(w, 400, "platform and content are required")
		return
	}
	text, err := h.rpcCallAs(r, "team_send", map[string]any{
		"platform": body.Platform, "channel": body.Channel,
		"content": body.Content, "actor": body.Actor})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	h.broadcast("message_sent", map[string]string{"text": text})
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}

// TeamHistory proxies team_history.
func (h *Handlers) TeamHistory(w http.ResponseWriter, r *http.Request) {
	last := 0
	if n, err := strconv.Atoi(r.URL.Query().Get("last")); err == nil {
		last = n
	}
	text, err := h.rpcCallAs(r, "team_history", map[string]any{
		"channel": r.URL.Query().Get("channel"),
		"platform": r.URL.Query().Get("platform"), "last": last})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	jsonResp(w, map[string]string{"history": text})
}

// TeamStatus proxies team_status (presence only — secrets never surface).
func (h *Handlers) TeamStatus(w http.ResponseWriter, r *http.Request) {
	text, err := h.rpcCallAs(r, "team_status", map[string]any{})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	jsonResp(w, map[string]string{"status": text})
}

// TeamHook is the inbound door: POST /hooks/:platform with the raw
// platform envelope and X-Atlas-Signature. Verification happens in the
// LINE; challenges echo, duplicates report, bad signatures refuse.
func (h *Handlers) TeamHook(w http.ResponseWriter, r *http.Request) {
	platform := r.PathValue("platform")
	raw, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if err != nil {
		jsonErr(w, 400, "unreadable body")
		return
	}
	text, err := h.rpcCall("team_ingest", map[string]any{
		"platform": platform, "body": string(raw),
		"signature": r.Header.Get("X-Atlas-Signature")})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	if strings.HasPrefix(text, "CHALLENGE ") {
		jsonResp(w, map[string]string{"challenge": strings.TrimPrefix(text, "CHALLENGE ")})
		return
	}
	h.broadcast("message_received", map[string]string{"text": text})
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}
