// Flow faces (N2): town beat/status plus the full DAG lifecycle — all
// through MCP /rpc. The webapp draws and displays; validation, firing,
// gates and receipts live in the LINE's flow package. Whole answers only:
// runs complete, pause, or fail before the page renders them.
package handlers

import (
	"encoding/json"
	"net/http"
	"strings"
)

// TownBeat proxies town_beat and announces the cycle.
func (h *Handlers) TownBeat(w http.ResponseWriter, r *http.Request) {
	text, err := h.rpcCallAs(r, "town_beat", map[string]any{})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	h.broadcast("town_beat", map[string]string{"text": text})
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}

// TownStatus proxies town_status.
func (h *Handlers) TownStatus(w http.ResponseWriter, r *http.Request) {
	text, err := h.rpcCallAs(r, "town_status", map[string]any{})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	jsonResp(w, map[string]string{"text": text})
}

// FlowSave proxies flow_save and announces the fold.
func (h *Handlers) FlowSave(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Name string `json:"name"`
		Spec string `json:"spec"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if strings.TrimSpace(body.Name) == "" || strings.TrimSpace(body.Spec) == "" {
		jsonErr(w, 400, "name and spec are required")
		return
	}
	text, err := h.rpcCallAs(r, "flow_save", map[string]any{"name": body.Name, "spec": body.Spec})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	h.broadcast("flow_saved", map[string]string{"text": text})
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}

// FlowGet proxies flow_get.
func (h *Handlers) FlowGet(w http.ResponseWriter, r *http.Request) {
	text, err := h.rpcCallAs(r, "flow_get", map[string]any{
		"name": r.URL.Query().Get("name"), "version": qVersion(r, "version")})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	jsonResp(w, map[string]string{"spec": text})
}

// FlowList proxies flow_list.
func (h *Handlers) FlowList(w http.ResponseWriter, r *http.Request) {
	text, err := h.rpcCallAs(r, "flow_list", map[string]any{})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	jsonResp(w, map[string]string{"flows": text})
}

// FlowRun proxies flow_run and announces the verdict.
func (h *Handlers) FlowRun(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Name    string  `json:"name"`
		Inputs  string  `json:"inputs"`
		Version float64 `json:"version"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if strings.TrimSpace(body.Name) == "" {
		jsonErr(w, 400, "name is required")
		return
	}
	text, err := h.rpcCallAs(r, "flow_run", map[string]any{
		"name": body.Name, "inputs": body.Inputs, "version": body.Version})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	h.broadcast("flow_ran", map[string]string{"text": text})
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}

// FlowResume proxies flow_resume (continue|stop) and announces the move.
func (h *Handlers) FlowResume(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Run      string `json:"run"`
		Decision string `json:"decision"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if strings.TrimSpace(body.Run) == "" {
		jsonErr(w, 400, "run is required")
		return
	}
	text, err := h.rpcCallAs(r, "flow_resume", map[string]any{
		"run": body.Run, "decision": body.Decision})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	h.broadcast("flow_resumed", map[string]string{"text": text})
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}

// FlowStatus proxies flow_status.
func (h *Handlers) FlowStatus(w http.ResponseWriter, r *http.Request) {
	text, err := h.rpcCallAs(r, "flow_status", map[string]any{"run": r.URL.Query().Get("run")})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	jsonResp(w, map[string]string{"status": text})
}

// FlowCompare proxies flow_compare.
func (h *Handlers) FlowCompare(w http.ResponseWriter, r *http.Request) {
	var body struct {
		RunA string `json:"runa"`
		RunB string `json:"runb"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	text, err := h.rpcCallAs(r, "flow_compare", map[string]any{"runa": body.RunA, "runb": body.RunB})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}

// FlowReplay proxies flow_replay and announces the fresh run.
func (h *Handlers) FlowReplay(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Run string `json:"run"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	text, err := h.rpcCallAs(r, "flow_replay", map[string]any{"run": body.Run})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	h.broadcast("flow_replayed", map[string]string{"text": text})
	jsonResp(w, map[string]string{"status": "ok", "text": text})
}

// FlowRuns proxies flow_runs.
func (h *Handlers) FlowRuns(w http.ResponseWriter, r *http.Request) {
	text, err := h.rpcCallAs(r, "flow_runs", map[string]any{"flow": r.URL.Query().Get("flow")})
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	jsonResp(w, map[string]string{"runs": text})
}
