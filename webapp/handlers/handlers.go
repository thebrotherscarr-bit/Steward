package handlers

import (
	"atlas/webapp/agents"
	"atlas/webapp/db"
	"atlas/webapp/evals"
	"atlas/webapp/messaging"
	"atlas/webapp/search"
	"atlas/webapp/traces"
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"

	_ "embed"
)

// THE GLASS WAS REPORTING A LITERAL (2026-09-12). Two places said `0.1.3` by
// hand: /health's `version` field and the Prometheus line
// `atlas_server_info{server="atlas-webapp",version="..."}`. A version a
// monitoring system scrapes is the last one anybody re-reads, so it is the
// worst place for a number nobody bumps. Beside the code that reports it, the
// way each command in `line` keeps its own.
//
//go:embed VERSION
var versionFile string

// Version is what this build answers when asked, read from disk at compile
// time rather than typed into two unrelated functions.
func Version() string { return strings.TrimSpace(versionFile) }

type Handlers struct {
	store     *traces.Store
	agents    *agents.Registry
	evals     *evals.Engine
	search    *search.Engine
	messaging *messaging.Bus
	clients   []chan event
	clientMu  sync.Mutex
	wsClients map[*wsConn]bool
	wsMu      sync.Mutex
	authOn    bool
	service   string
	sessions  *sessionStore
}

type event struct {
	Type string      `json:"type"`
	Data interface{} `json:"data"`
}

func New(store *traces.Store, agentReg *agents.Registry, evalEngine *evals.Engine, searchEngine *search.Engine, msgBus *messaging.Bus) *Handlers {
	return &Handlers{
		store:     store,
		agents:    agentReg,
		evals:     evalEngine,
		search:    searchEngine,
		messaging: msgBus,
	}
}

func (h *Handlers) broadcast(typ string, data interface{}) {
	h.clientMu.Lock()
	defer h.clientMu.Unlock()
	for _, ch := range h.clients {
		select {
		case ch <- event{Type: typ, Data: data}:
		default:
		}
	}
	go h.wsBroadcast(typ, data)
}

func jsonResp(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(data)
}

func jsonErr(w http.ResponseWriter, code int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

func (h *Handlers) Health(w http.ResponseWriter, r *http.Request) {
	// Counts are global rows: under auth they stay out of health so one
	// workspace never learns another's cardinality. Details live behind
	// the tenant-filtered list faces.
	resp := map[string]interface{}{
		"status":  "ok",
		"version": Version(),
		"time":    time.Now().UTC(),
		"auth":    h.authOn,
	}
	if !h.authOn {
		resp["agents"] = len(h.agents.List())
		resp["traces"] = h.store.Count()
		resp["evals"] = h.evals.Count()
	}
	jsonResp(w, resp)
}

func (h *Handlers) ListAgents(w http.ResponseWriter, r *http.Request) {
	agents := filterAgents(h.agents.List(), h.tenantOf(r))
	jsonResp(w, map[string]interface{}{
		"agents": agents,
		"count":  len(agents),
	})
}

func (h *Handlers) GetAgent(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	a := h.agents.Get(id)
	if a == nil || !visible(a.Tenant, h.tenantOf(r)) {
		jsonErr(w, 404, "agent not found")
		return
	}
	traces := filterTraces(h.store.ListByAgent(id, 50), h.tenantOf(r))
	jsonResp(w, map[string]interface{}{
		"agent":  a,
		"traces": traces,
		"recent": len(traces),
	})
}

func (h *Handlers) UpsertAgent(w http.ResponseWriter, r *http.Request) {
	var a db.Agent
	if err := json.NewDecoder(r.Body).Decode(&a); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if a.ID == "" {
		jsonErr(w, 400, "id is required")
		return
	}
	a.Tenant = h.tenantOf(r)
	h.agents.Upsert(a)
	h.broadcast("agent_upserted", a)
	jsonResp(w, map[string]string{"status": "ok", "id": a.ID})
}

func (h *Handlers) ListTraces(w http.ResponseWriter, r *http.Request) {
	agentID := r.URL.Query().Get("agent")
	limit := 100
	tr := filterTraces(h.store.List(agentID, limit), h.tenantOf(r))
	jsonResp(w, map[string]interface{}{
		"traces": tr,
		"count":  len(tr),
	})
}

func (h *Handlers) GetTrace(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	t := h.store.Get(id)
	if t == nil || !visible(t.Tenant, h.tenantOf(r)) {
		jsonErr(w, 404, "trace not found")
		return
	}
	evalList := filterEvals(h.evals.ListByTrace(id), h.tenantOf(r))
	jsonResp(w, map[string]interface{}{
		"trace": t,
		"evals": evalList,
	})
}

func (h *Handlers) AddTrace(w http.ResponseWriter, r *http.Request) {
	var t db.Trace
	if err := json.NewDecoder(r.Body).Decode(&t); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if t.Tool == "" {
		jsonErr(w, 400, "tool is required")
		return
	}
	if t.ID == "" {
		t.ID = fmt.Sprintf("t-%d", time.Now().UnixNano())
	}
	t.CreatedAt = time.Now().UTC()
	if t.Hash == "" {
		hash := sha256.Sum256([]byte(t.AgentID + t.Tool + t.Input + t.Output))
		t.Hash = fmt.Sprintf("%x", hash)
	}
	if t.Status == "" {
		t.Status = "ok"
	}
	t.Tenant = h.tenantOf(r)
	h.store.Add(t)
	h.broadcast("trace_added", t)
	jsonResp(w, map[string]string{"status": "ok", "id": t.ID, "hash": t.Hash})
}

func (h *Handlers) ListEvals(w http.ResponseWriter, r *http.Request) {
	traceID := r.URL.Query().Get("trace")
	e := filterEvals(h.evals.ListByTrace(traceID), h.tenantOf(r))
	jsonResp(w, map[string]interface{}{
		"evals": e,
		"count": len(e),
	})
}

func (h *Handlers) AddEval(w http.ResponseWriter, r *http.Request) {
	var e db.Eval
	if err := json.NewDecoder(r.Body).Decode(&e); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if e.Name == "" {
		jsonErr(w, 400, "name is required")
		return
	}
	if e.ID == "" {
		e.ID = fmt.Sprintf("e-%d", time.Now().UnixNano())
	}
	e.CreatedAt = time.Now().UTC()
	e.Tenant = h.tenantOf(r)
	h.evals.Add(e)
	h.broadcast("eval_added", e)
	jsonResp(w, map[string]string{"status": "ok", "id": e.ID})
}

func (h *Handlers) ListTools(w http.ResponseWriter, r *http.Request) {
	mcpURL := h.store.GetSetting("mcp_url")
	if mcpURL == "" {
		mcpURL = "http://127.0.0.1:8090"
	}
	resp, err := http.Get(mcpURL + "/tools")
	if err != nil {
		jsonErr(w, 502, fmt.Sprintf("mcp unreachable: %v", err))
		return
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		jsonErr(w, 502, "failed to read mcp response")
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(body)
}

func (h *Handlers) CallTool(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Tool    string         `json:"tool"`
		Args    map[string]any `json:"args"`
		AgentID string         `json:"agent_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if req.Tool == "" {
		jsonErr(w, 400, "tool is required")
		return
	}

	start := time.Now()
	mcpURL := h.store.GetSetting("mcp_url")
	if mcpURL == "" {
		mcpURL = "http://127.0.0.1:8090"
	}
	if req.Args == nil {
		req.Args = map[string]any{}
	}
	var sessTenant string
	if h.authOn {
		sess, ok := h.sessionOf(r)
		if !ok || sess == nil {
			jsonErr(w, 401, "login required")
			return
		}
		sessTenant = sess.Tenant
		req.Args["project"] = sess.Tenant
	}

	rpcPayload, _ := json.Marshal(map[string]any{
		"jsonrpc": "2.0",
		"id":      1,
		"method":  "tools/call",
		"params": map[string]any{
			"name":      req.Tool,
			"arguments": req.Args,
		},
	})
	rpcReq, err := http.NewRequest("POST", mcpURL+"/rpc", bytes.NewReader(rpcPayload))
	if err != nil {
		jsonErr(w, 502, err.Error())
		return
	}
	rpcReq.Header.Set("Content-Type", "application/json")
	if h.service != "" {
		rpcReq.Header.Set("Authorization", "Bearer "+h.service)
	}
	resp, err := http.DefaultClient.Do(rpcReq)
	var output string
	if err != nil {
		output = fmt.Sprintf("mcp error: %v", err)
	} else {
		defer resp.Body.Close()
		body, err := io.ReadAll(resp.Body)
		if err != nil {
			output = fmt.Sprintf("mcp read error: %v", err)
		} else {
			output = string(body)
		}
	}
	duration := time.Since(start).Milliseconds()

	hash := sha256.Sum256([]byte(req.Tool + fmt.Sprintf("%v", req.Args) + output))
	trace := db.Trace{
		ID:         fmt.Sprintf("t-%d", time.Now().UnixNano()),
		AgentID:    req.AgentID,
		Tool:       req.Tool,
		Input:      fmt.Sprintf("%v", req.Args),
		Output:     output,
		Hash:       fmt.Sprintf("%x", hash),
		Status:     "ok",
		DurationMs: duration,
		CreatedAt:  time.Now().UTC(),
		Tenant:     sessTenant,
	}
	h.store.Add(trace)
	h.broadcast("trace_added", trace)

	jsonResp(w, map[string]interface{}{
		"output":      output,
		"hash":        trace.Hash,
		"trace_id":    trace.ID,
		"duration_ms": duration,
	})
}

func (h *Handlers) Search(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	results := h.search.Query(q)
	tenant := h.tenantOf(r)
	if tenant != "" {
		kept := results[:0]
		for _, res := range results {
			var rowTenant string
			switch d := res.Data.(type) {
			case db.Agent:
				rowTenant = d.Tenant
			case db.Trace:
				rowTenant = d.Tenant
			}
			if visible(rowTenant, tenant) {
				kept = append(kept, res)
			}
		}
		results = kept
	}
	if results == nil {
		results = []search.Result{}
	}
	jsonResp(w, map[string]interface{}{
		"results": results,
		"count":   len(results),
		"query":   q,
	})
}

func (h *Handlers) ListMessages(w http.ResponseWriter, r *http.Request) {
	channel := r.URL.Query().Get("channel")
	msgs := filterMessages(h.messaging.List(channel, 100), h.tenantOf(r))
	jsonResp(w, map[string]interface{}{
		"messages": msgs,
		"count":    len(msgs),
	})
}

func (h *Handlers) SendMessage(w http.ResponseWriter, r *http.Request) {
	var msg struct {
		Channel  string `json:"channel"`
		Platform string `json:"platform"`
		AgentID  string `json:"agent_id"`
		Content  string `json:"content"`
	}
	if err := json.NewDecoder(r.Body).Decode(&msg); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if msg.Channel == "" || msg.Content == "" {
		jsonErr(w, 400, "channel and content are required")
		return
	}
	m := db.Message{
		ID:        fmt.Sprintf("m-%d", time.Now().UnixNano()),
		Channel:   msg.Channel,
		Platform:  msg.Platform,
		AgentID:   msg.AgentID,
		Content:   msg.Content,
		Direction: "outbound",
		CreatedAt: time.Now().UTC(),
		Tenant:    h.tenantOf(r),
	}
	h.messaging.Send(m)
	h.broadcast("message_sent", m)
	jsonResp(w, map[string]string{"status": "ok", "id": m.ID})
}

func (h *Handlers) GetSetting(w http.ResponseWriter, r *http.Request) {
	key := r.PathValue("key")
	val := h.store.GetSetting(key)
	jsonResp(w, map[string]string{"key": key, "value": val})
}

func (h *Handlers) SetSetting(w http.ResponseWriter, r *http.Request) {
	key := r.PathValue("key")
	var body struct {
		Value string `json:"value"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	h.store.SetSetting(key, body.Value)
	jsonResp(w, map[string]string{"status": "ok"})
}

func (h *Handlers) SSE(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	flusher, ok := w.(http.Flusher)
	if !ok {
		return
	}

	// DEEP ENOUGH FOR A TURN'S TOKENS. broadcast() drops on a full channel
	// rather than blocking -- correct, since one slow watcher must never
	// hold up a turn -- but at 32 that made dropping the NORMAL case: a
	// council turn puts hundreds of token events on this bus in seconds,
	// and a watcher would lose nearly all of them, seeing a tool card and
	// then silence. The events are small JSON; the depth costs nothing and
	// the drop stays as the backstop it was meant to be.
	ch := make(chan event, 512)
	h.clientMu.Lock()
	h.clients = append(h.clients, ch)
	h.clientMu.Unlock()

	defer func() {
		h.clientMu.Lock()
		for i, c := range h.clients {
			if c == ch {
				h.clients = append(h.clients[:i], h.clients[i+1:]...)
				break
			}
		}
		h.clientMu.Unlock()
	}()

	notify := r.Context().Done()
	for {
		select {
		case e := <-ch:
			// THE TYPE GOES ON THE WIRE. This marshalled e.Data alone, so the
			// `type` the whole bus is keyed on never reached a browser -- and
			// App.onEvent, which switches on e.type for eleven different events,
			// had therefore never fired once. The struct already carries
			// `json:"type"` and `json:"data"` and the client already reads
			// e.type; only this line disagreed with both.
			//
			// DRAINED IN BATCHES, FLUSHED ONCE. A flush per event cannot keep up
			// with a token stream, and a writer that falls behind is exactly what
			// fills the channel and starts the dropping. Everything already
			// queued is written before the flush.
			batch := []event{e}
			for len(batch) < 256 {
				select {
				case more := <-ch:
					batch = append(batch, more)
				default:
					goto write
				}
			}
		write:
			for _, ev := range batch {
				data, _ := json.Marshal(ev)
				fmt.Fprintf(w, "data: %s\n\n", string(data))
			}
			flusher.Flush()
		case <-notify:
			return
		case <-time.After(30 * time.Second):
			fmt.Fprintf(w, ":\n\n")
			flusher.Flush()
		}
	}
}
