// Gate (N6): bearer keys on the HTTP door. Off by default — loopback is
// the operator's own computer and stays open. On (--auth), /rpc and
// /chat/stream demand Authorization: Bearer, except the login door
// (auth_verify) which must stay reachable to earn a key. The same-computer
// service wire (--auth-service / ATLAS_SERVICE) carries full access for
// the webapp beside it; tenant keys carry only their tenants, checked
// per call against the named project (or the default when unnamed).
package httpserver

import (
	"fmt"
	"sort"
	"strings"
	"sync"

	"atlas/line/internal/auth"
)

// Auth configures the gate.
type Auth struct {
	On      bool
	Service string
}

type credential struct {
	ok      bool
	service bool
	tenants []string
	keyID   string
}

// metrics counts the door's traffic for /metrics.
type metrics struct {
	mu    sync.Mutex
	calls map[string]int64
	errs  int64
}

func newMetrics() *metrics { return &metrics{calls: map[string]int64{}} }

func (m *metrics) inc(tool string) {
	m.mu.Lock()
	m.calls[tool]++
	m.mu.Unlock()
}

func (m *metrics) err() {
	m.mu.Lock()
	m.errs++
	m.mu.Unlock()
}

func (m *metrics) render(server, version string) string {
	m.mu.Lock()
	defer m.mu.Unlock()
	var b strings.Builder
	fmt.Fprintf(&b, "# HELP atlas_rpc_calls tool calls by name\n# TYPE atlas_rpc_calls counter\n")
	names := []string{}
	for n := range m.calls {
		names = append(names, n)
	}
	sort.Strings(names)
	for _, n := range names {
		fmt.Fprintf(&b, "atlas_rpc_calls{tool=%q} %d\n", n, m.calls[n])
	}
	fmt.Fprintf(&b, "# HELP atlas_rpc_errors refused calls\n# TYPE atlas_rpc_errors counter\n")
	fmt.Fprintf(&b, "atlas_rpc_errors %d\n", m.errs)
	fmt.Fprintf(&b, "atlas_server_info{server=%q,version=%q} 1\n", server, version)
	return b.String()
}

func bearer(authHeader string) string {
	if authHeader == "" {
		return ""
	}
	parts := strings.SplitN(authHeader, " ", 2)
	if len(parts) != 2 || !strings.EqualFold(parts[0], "bearer") {
		return ""
	}
	return strings.TrimSpace(parts[1])
}

// credentialFor resolves a bearer token: the service wire first, then
// every carried tenant's store (short-circuit on first verify).
func (s *Server) credentialFor(token string) credential {
	if token == "" {
		return credential{}
	}
	if s.auth.Service != "" && subtleEqual(token, s.auth.Service) {
		return credential{ok: true, service: true, tenants: []string{"*"}}
	}
	for _, name := range s.tenants.Names() {
		tn, err := s.tenants.Resolve(name)
		if err != nil {
			continue
		}
		rec, err := auth.Verify(tn.Home, token)
		if err != nil {
			continue
		}
		return credential{ok: true, tenants: append([]string{tn.Name}, rec.Tenants...), keyID: rec.ID}
	}
	return credential{}
}

func subtleEqual(a, b string) bool {
	if len(a) != len(b) {
		return false
	}
	var v byte
	for i := range a {
		v |= a[i] ^ b[i]
	}
	return v == 0
}

// projectForScope resolves the named project (or the default) for a call.
func (s *Server) projectForScope(args map[string]any) string {
	if p, _ := args["project"].(string); strings.TrimSpace(p) != "" {
		tn, err := s.tenants.Resolve(p)
		if err != nil {
			return ""
		}
		return tn.Name
	}
	def, err := s.tenants.Default()
	if err != nil {
		return ""
	}
	return def
}

// gateCall judges one tools/call: the login door stays open, everything
// else needs a bearer whose tenants carry the named project.
func (s *Server) gateCall(toolName string, args map[string]any, cred credential) error {
	if !s.auth.On {
		return nil
	}
	if toolName == "auth_verify" {
		return nil
	}
	if !cred.ok {
		return fmt.Errorf("401: a bearer key rides Authorization — strangers get nothing")
	}
	if cred.service {
		return nil
	}
	project := s.projectForScope(args)
	if project == "" {
		return fmt.Errorf("403: unknown project — not a carried tenant")
	}
	if !auth.ScopeOK(cred.tenants, project) {
		return fmt.Errorf("403: key %s does not carry project %q", cred.keyID, project)
	}
	return nil
}
