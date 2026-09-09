// Sessions (N6): cookie sessions over MCP-verified API keys. The webapp
// holds no user keys — login proves possession once against the tenant's
// own store (auth_verify), then a random session token maps to
// (tenant, key_id) server-side for 12h. Local rows stamp the session
// tenant; pre-auth rows (tenant "") stay visible to all, documented as
// history the operator purges by deleting. Off by default: ATLAS_AUTH=1
// closes the door, and every /api + /ws below goes through it except the
// login door, health, and the HMAC-guarded platform hooks.
package handlers

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"atlas/webapp/db"
)

// Session is one login: no secrets, just pointers back to the key.
type Session struct {
	Token   string   `json:"token"`
	Tenant  string   `json:"tenant"`
	Tenants []string `json:"tenants"`
	KeyID   string   `json:"key_id"`
	Expiry  time.Time `json:"expiry"`
}

type sessionStore struct {
	mu       sync.Mutex
	path     string
	sessions map[string]Session
}

func newSessionStore(path string) *sessionStore {
	s := &sessionStore{path: path, sessions: map[string]Session{}}
	if b, err := os.ReadFile(path); err == nil {
		var list []Session
		if json.Unmarshal(b, &list) == nil {
			for _, sess := range list {
				if time.Now().Before(sess.Expiry) {
					s.sessions[sess.Token] = sess
				}
			}
		}
	}
	return s
}

func (s *sessionStore) persist() {
	list := []Session{}
	for _, sess := range s.sessions {
		if time.Now().Before(sess.Expiry) {
			list = append(list, sess)
		}
	}
	b, _ := json.MarshalIndent(list, "", "  ")
	os.MkdirAll(filepath.Dir(s.path), 0o755)
	os.WriteFile(s.path, append(b, '\n'), 0o600)
}

func (s *sessionStore) create(tenant string, tenants []string, keyID string) Session {
	tok := make([]byte, 32)
	_, _ = rand.Read(tok)
	sess := Session{
		Token: hex.EncodeToString(tok), Tenant: tenant,
		Tenants: tenants, KeyID: keyID,
		Expiry: time.Now().Add(12 * time.Hour),
	}
	s.mu.Lock()
	s.sessions[sess.Token] = sess
	s.mu.Unlock()
	s.persist()
	return sess
}

func (s *sessionStore) get(token string) (Session, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, ok := s.sessions[token]
	if !ok || time.Now().After(sess.Expiry) {
		delete(s.sessions, token)
		return Session{}, false
	}
	return sess, true
}

func (s *sessionStore) drop(token string) {
	s.mu.Lock()
	delete(s.sessions, token)
	s.mu.Unlock()
	s.persist()
}

// ConfigureAuth closes the door: on=true demands sessions, service is the
// same-computer wire to MCP, sessionPath persists logins across restarts.
func (h *Handlers) ConfigureAuth(on bool, service, sessionPath string) {
	h.authOn = on
	h.service = service
	if sessionPath == "" {
		sessionPath = "data/sessions.json"
	}
	h.sessions = newSessionStore(sessionPath)
}

// AuthOn reports whether the door is closed (for the server wrapper).
func (h *Handlers) AuthOn() bool { return h.authOn }

// Session resolves the request's session for the server wrapper.
func (h *Handlers) Session(r *http.Request) (*Session, bool) { return h.sessionOf(r) }

// sessionOf resolves the request's session. Auth off: (nil, true) — the
// computer is the operator's and stays open. Auth on: cookie or refusal.
func (h *Handlers) sessionOf(r *http.Request) (*Session, bool) {
	if !h.authOn {
		return nil, true
	}
	c, err := r.Cookie("atlas_session")
	if err != nil {
		return nil, false
	}
	sess, ok := h.sessions.get(c.Value)
	if !ok {
		return nil, false
	}
	return &sess, true
}

// tenantOf stamps and filters local rows: "" when open (all visible),
// else the session tenant (legacy "" rows stay visible as history).
func (h *Handlers) tenantOf(r *http.Request) string {
	sess, ok := h.sessionOf(r)
	if !ok || sess == nil {
		return ""
	}
	return sess.Tenant
}

// visible reports whether a local row shows for a session tenant.
func visible(rowTenant, sessTenant string) bool {
	if sessTenant == "" {
		return true
	}
	return rowTenant == "" || rowTenant == sessTenant
}

func setSessionCookie(w http.ResponseWriter, token string) {
	http.SetCookie(w, &http.Cookie{
		Name: "atlas_session", Value: token, Path: "/",
		MaxAge: 12 * 3600, HttpOnly: true, SameSite: http.SameSiteLaxMode,
	})
}

func clearSessionCookie(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{Name: "atlas_session", Path: "/", MaxAge: -1})
}

// Login proves a key once against its tenant store, then mints a session.
func (h *Handlers) Login(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Tenant string `json:"tenant"`
		Key    string `json:"key"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	if strings.TrimSpace(body.Tenant) == "" || strings.TrimSpace(body.Key) == "" {
		jsonErr(w, 400, "tenant and key are required")
		return
	}
	text, err := h.rpcCall("auth_verify", map[string]any{
		"project": body.Tenant, "key": body.Key})
	if err != nil {
		jsonErr(w, 401, "refused: not a key for that tenant")
		return
	}
	// "VERIFIED <kid> on <tenant> · tenants [a,b]"
	kid, tenants := parseVerified(text, body.Tenant)
	sess := h.sessions.create(body.Tenant, tenants, kid)
	setSessionCookie(w, sess.Token)
	jsonResp(w, map[string]any{
		"status": "ok", "tenant": sess.Tenant,
		"tenants": sess.Tenants, "key_id": sess.KeyID,
	})
}

func parseVerified(text, tenant string) (string, []string) {
	kid := ""
	tenants := []string{tenant}
	fields := strings.Fields(text)
	if len(fields) >= 2 && fields[0] == "VERIFIED" {
		kid = fields[1]
	}
	if i := strings.Index(text, "tenants ["); i >= 0 {
		rest := text[i+len("tenants ["):]
		if j := strings.Index(rest, "]"); j >= 0 {
			for _, t := range strings.Split(rest[:j], ",") {
				if t = strings.TrimSpace(t); t != "" {
					tenants = appendUnique(tenants, t)
				}
			}
		}
	}
	return kid, tenants
}

func appendUnique(ss []string, s string) []string {
	for _, e := range ss {
		if e == s {
			return ss
		}
	}
	return append(ss, s)
}

// Logout drops the session server-side and clears the cookie.
func (h *Handlers) Logout(w http.ResponseWriter, r *http.Request) {
	if c, err := r.Cookie("atlas_session"); err == nil {
		h.sessions.drop(c.Value)
	}
	clearSessionCookie(w)
	jsonResp(w, map[string]string{"status": "ok"})
}

// Me reports the session (tenant + workspaces, never secrets).
func (h *Handlers) Me(w http.ResponseWriter, r *http.Request) {
	sess, ok := h.sessionOf(r)
	if !ok || (h.authOn && sess == nil) {
		jsonErr(w, 401, "login required")
		return
	}
	if sess == nil {
		jsonResp(w, map[string]any{"auth": false})
		return
	}
	jsonResp(w, map[string]any{
		"auth": true, "tenant": sess.Tenant,
		"tenants": sess.Tenants, "key_id": sess.KeyID,
	})
}

// rpcCallAs proxies with the session tenant forced: isolation first, the
// caller never names another workspace. Auth off: straight through.
func (h *Handlers) rpcCallAs(r *http.Request, tool string, args map[string]any) (string, error) {
	if h.authOn {
		sess, ok := h.sessionOf(r)
		if !ok || sess == nil {
			return "", fmt.Errorf("login required")
		}
		args["project"] = sess.Tenant
	}
	return h.rpcCall(tool, args)
}

// Local-row filters: auth off shows all; auth on shows the session tenant
// plus pre-auth ("") history rows.
func filterTraces(in []db.Trace, tenant string) []db.Trace {
	out := []db.Trace{}
	for _, t := range in {
		if visible(t.Tenant, tenant) {
			out = append(out, t)
		}
	}
	return out
}

func filterEvals(in []db.Eval, tenant string) []db.Eval {
	out := []db.Eval{}
	for _, e := range in {
		if visible(e.Tenant, tenant) {
			out = append(out, e)
		}
	}
	return out
}

func filterAgents(in []db.Agent, tenant string) []db.Agent {
	out := []db.Agent{}
	for _, a := range in {
		if visible(a.Tenant, tenant) {
			out = append(out, a)
		}
	}
	return out
}

func filterMessages(in []db.Message, tenant string) []db.Message {
	out := []db.Message{}
	for _, m := range in {
		if visible(m.Tenant, tenant) {
			out = append(out, m)
		}
	}
	return out
}

// SwitchWorkspace moves the session within its own key scope.
func (h *Handlers) SwitchWorkspace(w http.ResponseWriter, r *http.Request) {
	sess, ok := h.sessionOf(r)
	if !ok || sess == nil {
		jsonErr(w, 401, "login required")
		return
	}
	var body struct {
		Tenant string `json:"tenant"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, 400, "invalid json")
		return
	}
	want := strings.TrimSpace(body.Tenant)
	allowed := false
	for _, t := range sess.Tenants {
		if t == "*" || t == want {
			allowed = true
		}
	}
	if !allowed {
		jsonErr(w, 403, "that workspace is outside this key's scope")
		return
	}
	updated := *sess
	updated.Tenant = want
	h.sessions.mu.Lock()
	h.sessions.sessions[sess.Token] = updated
	h.sessions.mu.Unlock()
	h.sessions.persist()
	jsonResp(w, map[string]any{"status": "ok", "tenant": want})
}
