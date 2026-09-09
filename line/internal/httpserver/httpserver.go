// Package httpserver exposes the MCP tool surface over HTTP.
// POST /rpc accepts newline-delimited JSON-RPC 2.0 (same as stdio).
// GET  /health returns server status.
// GET  /tools lists available tools.
// GET  / serves the GUI SPA from the static directory.
// Loopback by default; wider bind is the operator's call.
package httpserver

import (
	"bufio"
	"embed"
	"encoding/json"
	"fmt"
	"io/fs"
	"net/http"

	"atlas/line/internal/protocol"
	"atlas/line/internal/tenant"
	"atlas/line/internal/tools"
)

//go:embed static/index.html static/css/* static/js/*
var staticFiles embed.FS

type Server struct {
	info         protocol.ServerInfo
	instructions string
	tools        *tools.Registry
	tenants      *tenant.Registry
	auth         Auth
	m            *metrics
}

type toolsRequest struct {
	Jsonrpc string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Method  string          `json:"method"`
	Params  struct {
		Name      string         `json:"name"`
		Arguments map[string]any `json:"arguments"`
	} `json:"params"`
}

// New creates an HTTP server wrapping the MCP tool surface.
func New(info protocol.ServerInfo, instructions string, reg *tools.Registry, tenants *tenant.Registry, auth Auth) *Server {
	return &Server{info: info, instructions: instructions, tools: reg, tenants: tenants, auth: auth, m: newMetrics()}
}

// ListenAndServe starts the HTTP server on the given bind address.
func (s *Server) ListenAndServe(addr string) error {
	srv := &http.Server{Addr: addr, Handler: s.Handler()}
	return srv.ListenAndServe()
}

// Handler exposes the mux for embedding and hermetic tests.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", s.handleHealth)
	mux.HandleFunc("GET /tools", s.handleTools)
	mux.HandleFunc("POST /rpc", s.handleRPC)
	mux.HandleFunc("GET /chat/stream", s.handleChatStream)
	// The COUNCIL, not a voice: one Manjuel turn with every engine event as
	// it happens. /chat/stream reaches a model; this reaches the estate.
	mux.HandleFunc("GET /run/stream", s.handleRunStream)
	mux.HandleFunc("GET /run/state", s.handleRunState)
	mux.HandleFunc("GET /run/listen", s.handleRunListen)
	mux.HandleFunc("GET /metrics", s.handleMetrics)

	// Serve static files from embedded filesystem
	staticFS, err := fs.Sub(staticFiles, "static")
	if err != nil {
		broken := http.NewServeMux()
		broken.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
			http.Error(w, "static fs unavailable", http.StatusInternalServerError)
		})
		return broken
	}
	fileServer := http.FileServer(http.FS(staticFS))

	// SPA: serve index.html for root and unknown paths
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path
		// API endpoints take priority
		if path == "/health" || path == "/tools" || path == "/rpc" || path == "/chat/stream" ||
			path == "/run/stream" || path == "/run/state" ||
			path == "/run/listen" || path == "/metrics" {
			http.NotFound(w, r)
			return
		}
		// Try to serve the file directly
		f, err := staticFS.Open(path[1:]) // strip leading /
		if err == nil {
			f.Close()
			fileServer.ServeHTTP(w, r)
			return
		}
		// Fall back to index.html for SPA routing
		r.URL.Path = "/"
		fileServer.ServeHTTP(w, r)
	})

	return mux
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.Handler().ServeHTTP(w, r)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	s.m.inc("health")
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"status":"ok","server":%q,"version":%q,"auth":%v}`,
		s.info.Name, s.info.Version, s.auth.On)
}

func (s *Server) handleMetrics(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	fmt.Fprint(w, s.m.render(s.info.Name, s.info.Version))
}

func (s *Server) handleTools(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	list := []map[string]any{}
	for _, t := range s.tools.All() {
		props := map[string]any{}
		required := []string{}
		for _, a := range t.Args {
			name := trimOptional(a)
			desc := "the ground this call names"
			if endsWithOptional(a) {
				desc += "; OPTIONAL -- omit for default tenant"
			} else {
				required = append(required, name)
			}
			props[name] = map[string]any{
				"type":        "string",
				"description": desc,
			}
		}
		list = append(list, map[string]any{
			"name":        t.Name,
			"description": t.Description,
			"inputSchema": map[string]any{
				"type":       "object",
				"properties": props,
				"required":   required,
			},
		})
	}
	b, _ := json.Marshal(map[string]any{"tools": list})
	w.Write(b)
}

func (s *Server) handleRPC(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	cred := credential{}
	if s.auth.On {
		cred = s.credentialFor(bearer(r.Header.Get("Authorization")))
	}
	scanner := bufio.NewScanner(r.Body)
	scanner.Buffer(make([]byte, 0, 1<<20), 16<<20)

	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}
		resp := s.handleGated(line, cred)
		if resp == nil {
			continue
		}
		b, _ := json.Marshal(resp)
		w.Write(b)
		w.Write([]byte("\n"))
	}
}

// handleGated judges the gate before the tool: the login door stays open,
// strangers get 401, out-of-scope keys get 403. Gate off: straight through.
func (s *Server) handleGated(line []byte, cred credential) any {
	if !s.auth.On {
		return s.handle(line)
	}
	var peek struct {
		ID     json.RawMessage `json:"id"`
		Method string          `json:"method"`
		Params struct {
			Name      string         `json:"name"`
			Arguments map[string]any `json:"arguments"`
		} `json:"params"`
	}
	if err := json.Unmarshal(line, &peek); err != nil {
		return errResponse(nil, -32700, "parse error")
	}
	if peek.Method == "tools/call" {
		if err := s.gateCall(peek.Params.Name, peek.Params.Arguments, cred); err != nil {
			s.m.err()
			msg := err.Error()
			code := -32600
			if len(msg) >= 3 && msg[:3] == "401" {
				code = -32001
			} else if len(msg) >= 3 && msg[:3] == "403" {
				code = -32003
			}
			return errResponse(peek.ID, code, msg)
		}
		s.m.inc(peek.Params.Name)
	} else {
		s.m.inc(peek.Method)
	}
	return s.handle(line)
}

func (s *Server) handle(line []byte) any {
	var req toolsRequest
	if err := json.Unmarshal(line, &req); err != nil {
		return errResponse(nil, -32700, "parse error")
	}
	switch req.Method {
	case "initialize":
		return resultResponse(req.ID, map[string]any{
			"protocolVersion": "2025-06-18",
			"capabilities":    map[string]any{"tools": map[string]any{}},
			"serverInfo": map[string]any{
				"name":    s.info.Name,
				"version": s.info.Version,
			},
			"instructions": s.instructions,
		})
	case "notifications/initialized", "initialized":
		return nil
	case "tools/list":
		list := []map[string]any{}
		for _, t := range s.tools.All() {
			props := map[string]any{}
			required := []string{}
			for _, a := range t.Args {
				name := trimOptional(a)
				desc := "the ground this call names"
				if endsWithOptional(a) {
					desc += "; OPTIONAL -- omit for default tenant"
				} else {
					required = append(required, name)
				}
				props[name] = map[string]any{
					"type":        "string",
					"description": desc,
				}
			}
			list = append(list, map[string]any{
				"name":        t.Name,
				"description": t.Description,
				"inputSchema": map[string]any{
					"type":       "object",
					"properties": props,
					"required":   required,
				},
			})
		}
		return resultResponse(req.ID, map[string]any{"tools": list})
	case "tools/call":
		if _, ok := s.tools.Get(req.Params.Name); !ok {
			return errResponse(req.ID, -32602,
				fmt.Sprintf("unknown tool %q", req.Params.Name))
		}
		out, err := s.tools.Call(s.tenants, req.Params.Name, req.Params.Arguments)
		if err != nil {
			return resultResponse(req.ID, map[string]any{
				"isError": true,
				"content": []map[string]any{{"type": "text", "text": err.Error()}},
			})
		}
		return resultResponse(req.ID, map[string]any{
			"content": []map[string]any{{"type": "text", "text": out}},
		})
	default:
		return errResponse(req.ID, -32601, fmt.Sprintf("unknown method %q", req.Method))
	}
}

func endsWithOptional(a string) bool {
	n := len(a)
	return n > 1 && a[n-1] == '?' && a[n-2] == '?'
}

func trimOptional(a string) string {
	for len(a) > 0 && a[len(a)-1] == '?' {
		a = a[:len(a)-1]
	}
	return a
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

func resultResponse(id json.RawMessage, result any) map[string]any {
	var idVal any
	if len(id) > 0 {
		_ = json.Unmarshal(id, &idVal)
	}
	return map[string]any{"jsonrpc": "2.0", "id": idVal, "result": result}
}

func errResponse(id json.RawMessage, code int, msg string) map[string]any {
	var idVal any
	if len(id) > 0 {
		_ = json.Unmarshal(id, &idVal)
	}
	return map[string]any{
		"jsonrpc": "2.0",
		"id":      idVal,
		"error":   rpcError{Code: code, Message: msg},
	}
}
