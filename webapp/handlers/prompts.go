// Prompt faces (N4): registry, measured runs, compares and evals — all
// through MCP /rpc. The webapp owns no playground logic; versions fold,
// runs measure and evals score in the LINE's play package. Whole answers
// only: compares and evals need complete outputs to judge honestly.
package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
)

func qVersion(r *http.Request, key string) float64 {
	n, _ := strconv.Atoi(r.URL.Query().Get(key))
	return float64(n)
}

// ListPrompts proxies prompt_list.
func (h *Handlers) ListPrompts(w http.ResponseWriter, r *http.Request) {
	text, err := h.rpcCallAs(r, "prompt_list", map[string]any{})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	jsonResp(w, map[string]string{"prompts": text})
}

// GetPrompt proxies prompt_get.
func (h *Handlers) GetPrompt(w http.ResponseWriter, r *http.Request) {
	text, err := h.rpcCallAs(r, "prompt_get", map[string]any{
		"name": r.URL.Query().Get("name"), "version": qVersion(r, "version")})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	jsonResp(w, map[string]string{"prompt": text})
}

// SavePrompt proxies prompt_save and announces the fold.
func (h *Handlers) SavePrompt(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Name        string `json:"name"`
		Body        string `json:"body"`
		Description string `json:"description"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if strings.TrimSpace(body.Name) == "" || strings.TrimSpace(body.Body) == "" {
		jsonErr(w, 400, "name and body are required")
		return
	}
	text, err := h.rpcCallAs(r, "prompt_save", map[string]any{
		"name": body.Name, "body": body.Body, "description": body.Description})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	h.broadcast("prompt_saved", map[string]string{"text": text})
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}

// RunPrompt proxies prompt_run and announces the measurement.
func (h *Handlers) RunPrompt(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Name    string  `json:"name"`
		Vars    string  `json:"vars"`
		Version float64 `json:"version"`
		Voice   string  `json:"voice"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if strings.TrimSpace(body.Name) == "" {
		jsonErr(w, 400, "name is required")
		return
	}
	text, err := h.rpcCallAs(r, "prompt_run", map[string]any{
		"name": body.Name, "vars": body.Vars,
		"version": body.Version, "voice": body.Voice})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	h.broadcast("prompt_ran", map[string]string{"text": text})
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}

// ComparePrompts proxies prompt_compare.
func (h *Handlers) ComparePrompts(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Name  string  `json:"name"`
		VerA  float64 `json:"vera"`
		VerB  float64 `json:"verb"`
		Vars  string  `json:"vars"`
		Voice string  `json:"voice"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if strings.TrimSpace(body.Name) == "" {
		jsonErr(w, 400, "name is required")
		return
	}
	text, err := h.rpcCallAs(r, "prompt_compare", map[string]any{
		"name": body.Name, "vera": body.VerA, "verb": body.VerB,
		"vars": body.Vars, "voice": body.Voice})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	h.broadcast("prompt_compared", map[string]string{"text": text})
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}

// EvalPrompt proxies prompt_eval and announces the score.
func (h *Handlers) EvalPrompt(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Name    string  `json:"name"`
		Dataset string  `json:"dataset"`
		Version float64 `json:"version"`
		Voice   string  `json:"voice"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if strings.TrimSpace(body.Name) == "" || strings.TrimSpace(body.Dataset) == "" {
		jsonErr(w, 400, "name and dataset are required")
		return
	}
	text, err := h.rpcCallAs(r, "prompt_eval", map[string]any{
		"name": body.Name, "dataset": body.Dataset,
		"version": body.Version, "voice": body.Voice})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	h.broadcast("prompt_evaled", map[string]string{"text": text})
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}

// SeatAsk proxies seat_ask and announces the single answer.
func (h *Handlers) SeatAsk(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Question string `json:"question"`
		Seat     string `json:"seat"`
		Voice    string `json:"voice"`
		Method   string `json:"method"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if strings.TrimSpace(body.Question) == "" {
		jsonErr(w, 400, "question is required")
		return
	}
	text, err := h.rpcCallAs(r, "seat_ask", map[string]any{
		"question": body.Question, "seat": body.Seat,
		"voice": body.Voice, "method": body.Method})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	h.broadcast("seat_answered", map[string]string{"text": text})
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}
