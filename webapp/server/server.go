package server

import (
	"atlas/webapp/handlers"
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"fmt"
	"io/fs"
	"net/http"
	"strings"
)

type Server struct {
	handlers *handlers.Handlers
	port     string
	static   embed.FS
}

func New(h *handlers.Handlers, port string, static embed.FS) *Server {
	return &Server{handlers: h, port: port, static: static}
}

// etags hashes every embedded file ONCE, at startup. The bytes cannot change
// while the process runs -- they are compiled into it -- so a tag computed here
// is correct for the life of the binary, and a rebuild produces a different
// binary with different tags.
func etags(root fs.FS) map[string]string {
	out := map[string]string{}
	_ = fs.WalkDir(root, ".", func(path string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return nil
		}
		b, err := fs.ReadFile(root, path)
		if err != nil {
			return nil
		}
		sum := sha256.Sum256(b)
		out[path] = `"` + hex.EncodeToString(sum[:16]) + `"`
		return nil
	})
	return out
}

func (s *Server) ListenAndServe() error {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /api/health", s.handlers.Health)
	mux.HandleFunc("GET /api/agents", s.handlers.ListAgents)
	mux.HandleFunc("GET /api/agents/{id}", s.handlers.GetAgent)
	mux.HandleFunc("POST /api/agents", s.handlers.UpsertAgent)
	mux.HandleFunc("GET /api/traces", s.handlers.ListTraces)
	mux.HandleFunc("GET /api/traces/{id}", s.handlers.GetTrace)
	mux.HandleFunc("POST /api/traces", s.handlers.AddTrace)
	mux.HandleFunc("GET /api/evals", s.handlers.ListEvals)
	mux.HandleFunc("POST /api/evals", s.handlers.AddEval)
	mux.HandleFunc("POST /api/tools/call", s.handlers.CallTool)
	mux.HandleFunc("GET /api/tools", s.handlers.ListTools)
	mux.HandleFunc("GET /api/search", s.handlers.Search)
	mux.HandleFunc("GET /api/messages", s.handlers.ListMessages)
	mux.HandleFunc("POST /api/messages/send", s.handlers.SendMessage)
	mux.HandleFunc("GET /api/settings/{key}", s.handlers.GetSetting)
	mux.HandleFunc("POST /api/settings/{key}", s.handlers.SetSetting)
	mux.HandleFunc("GET /api/events", s.handlers.SSE)
	mux.HandleFunc("GET /api/chat/sessions", s.handlers.ListSessions)
	mux.HandleFunc("GET /api/chat/session", s.handlers.GetSession)
	mux.HandleFunc("POST /api/chat/start", s.handlers.StartSession)
	mux.HandleFunc("POST /api/chat/send", s.handlers.SendChat)
	mux.HandleFunc("GET /api/chat/stream", s.handlers.StreamChat)
	// The council, not a voice: one Manjuel turn with every engine event live.
	mux.HandleFunc("GET /api/council/stream", s.handlers.StreamCouncil)
	mux.HandleFunc("GET /api/council/state", s.handlers.CouncilState)
	mux.HandleFunc("GET /api/council/listen", s.handlers.ListenCouncil)
	mux.HandleFunc("GET /ws", s.handlers.WS)
	mux.HandleFunc("GET /api/prompts", s.handlers.ListPrompts)
	mux.HandleFunc("GET /api/prompts/get", s.handlers.GetPrompt)
	mux.HandleFunc("POST /api/prompts/save", s.handlers.SavePrompt)
	mux.HandleFunc("POST /api/prompts/run", s.handlers.RunPrompt)
	mux.HandleFunc("POST /api/prompts/compare", s.handlers.ComparePrompts)
	mux.HandleFunc("POST /api/prompts/eval", s.handlers.EvalPrompt)
	mux.HandleFunc("POST /api/seat/ask", s.handlers.SeatAsk)
	mux.HandleFunc("POST /api/town/beat", s.handlers.TownBeat)
	mux.HandleFunc("GET /api/town/status", s.handlers.TownStatus)
	mux.HandleFunc("GET /api/flows", s.handlers.FlowList)
	mux.HandleFunc("GET /api/flows/get", s.handlers.FlowGet)
	mux.HandleFunc("POST /api/flows/save", s.handlers.FlowSave)
	mux.HandleFunc("POST /api/flows/run", s.handlers.FlowRun)
	mux.HandleFunc("POST /api/flows/resume", s.handlers.FlowResume)
	mux.HandleFunc("GET /api/flows/status", s.handlers.FlowStatus)
	mux.HandleFunc("POST /api/flows/compare", s.handlers.FlowCompare)
	mux.HandleFunc("POST /api/flows/replay", s.handlers.FlowReplay)
	mux.HandleFunc("GET /api/flows/runs", s.handlers.FlowRuns)
	mux.HandleFunc("POST /api/team/send", s.handlers.TeamSend)
	mux.HandleFunc("GET /api/team/history", s.handlers.TeamHistory)
	mux.HandleFunc("GET /api/team/status", s.handlers.TeamStatus)
	mux.HandleFunc("POST /hooks/{platform}", s.handlers.TeamHook)
	mux.HandleFunc("POST /api/login", s.handlers.Login)
	mux.HandleFunc("POST /api/logout", s.handlers.Logout)
	mux.HandleFunc("GET /api/me", s.handlers.Me)
	mux.HandleFunc("POST /api/workspace/switch", s.handlers.SwitchWorkspace)
	mux.HandleFunc("GET /metrics", s.handlers.Metrics)

	staticFS, _ := fs.Sub(s.static, "static")
	fileServer := http.FileServer(http.FS(staticFS))

	// EVERY STATIC FILE CARRIES A VALIDATOR, so a rebuilt binary reaches a tab
	// that is already open.
	//
	// Measured 2026-09-09: `curl -D -` on /js/home.js returned 200 with
	// Content-Length and NOTHING ELSE -- no ETag, no Last-Modified, no
	// Cache-Control. An embed.FS reports the zero time as ModTime, so
	// http.FileServer emits no Last-Modified, and it never emits an ETag. A
	// response with no validator and no freshness header may be cached
	// heuristically and served without ever revalidating, which is how one
	// open tab kept the same bytes across four rebuilds while a freshly
	// navigated one saw every change.
	//
	// `no-cache` is not `no-store`: the browser still caches and still sends
	// If-None-Match, and an unchanged file still answers 304 with no body. It
	// simply may not serve a stale copy WITHOUT ASKING. A rebuild changes the
	// bytes, which changes the tag, which ends the 304.
	tags := etags(staticFS)

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/health" || len(r.URL.Path) > 4 && r.URL.Path[:5] == "/api/" {
			http.NotFound(w, r)
			return
		}
		serve := func(path string) {
			if tag, ok := tags[path]; ok {
				// http.ServeContent reads the ETag off this header and does the
				// If-None-Match comparison itself, so there is no second copy of
				// the conditional-request logic here.
				w.Header().Set("Etag", tag)
			}
			w.Header().Set("Cache-Control", "no-cache")
			fileServer.ServeHTTP(w, r)
		}
		name := strings.TrimPrefix(r.URL.Path, "/")
		if _, err := staticFS.(fs.ReadFileFS).ReadFile(name); err == nil {
			serve(name)
			return
		}
		// Every unknown path is the single-page app's own routing (/records,
		// /evals, ...), answered with index.html and ITS tag.
		r.URL.Path = "/"
		serve("index.html")
	})

	return http.ListenAndServe(":"+s.port, s.gated(mux))
}

// gated wraps the mux: the session gate (ATLAS_AUTH=1) plus request
// counting for /metrics. Open paths: login, health, platform hooks, and
// the static face (the login page itself must load ungated).
func (s *Server) gated(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		s.handlers.Count(r.Method + " " + r.URL.Path)
		path := r.URL.Path
		if s.handlers.AuthOn() {
			open := path == "/api/login" || path == "/api/health" ||
				strings.HasPrefix(path, "/hooks/") ||
				(!strings.HasPrefix(path, "/api/") && !strings.HasPrefix(path, "/ws") && path != "/metrics")
			if !open {
				if _, ok := s.handlers.Session(r); !ok {
					if strings.HasPrefix(path, "/api/") {
						w.Header().Set("Content-Type", "application/json")
						w.WriteHeader(http.StatusUnauthorized)
						fmt.Fprint(w, `{"error":"login required"}`)
						return
					}
					http.Redirect(w, r, "/login", http.StatusFound)
					return
				}
			}
		}
		next.ServeHTTP(w, r)
	})
}
