package server

import (
	"atlas/webapp/handlers"
	"embed"
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

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/health" || len(r.URL.Path) > 4 && r.URL.Path[:5] == "/api/" {
			http.NotFound(w, r)
			return
		}
		f, err := staticFS.(fs.ReadFileFS).ReadFile(r.URL.Path[1:])
		if err == nil {
			_ = f
			fileServer.ServeHTTP(w, r)
			return
		}
		r.URL.Path = "/"
		fileServer.ServeHTTP(w, r)
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
