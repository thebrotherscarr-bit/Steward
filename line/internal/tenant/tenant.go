// Package tenant holds the multi-tenant registry: one MCP serving ALL of
// the estate. Genesis law (operator, 2026-08-25): no single-seat worldview
// -- every project is a first-class tenant, and every tool call names its
// ground.
//
// 2026-08-27 addition: a per-tenant record-map manifest. Each project ground
// may carry a line.manifest.json mapping logical record keys (line/road/state/
// log/doctrine/plans/wall) to paths relative to Home. An absent manifest (or
// an absent key) falls back to the rigid default contract used by
// atlas/Steward-style grounds, so tools degrade honestly instead of assuming
// one layout.
package tenant

import (
	"atlas/line/internal/ground"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"atlas/line/internal/rbac"
)

// Manifest maps logical record keys to paths relative to Home.
type Manifest struct {
	Line     string            `json:"line"`
	Road     string            `json:"road"`
	State    string            `json:"state"`
	Log      string            `json:"log"`
	Doctrine []string          `json:"doctrine"`
	Plans    map[string]string `json:"plans"`
	Wall     string            `json:"wall"`
}

// DefaultManifest is the rigid contract: Home/<file> for each logical key.
func DefaultManifest() Manifest {
	return Manifest{
		Line:     "AGENTS.md",
		Road:     "THE_ROAD.md",
		State:    "STATE_OF_BUILD.md",
		Log:      "SEAT_LOG.md",
		Doctrine: []string{"doctrine", "foundation"},
		Wall:     ".",
	}
}

// LoadManifest reads <Home>/line.manifest.json if present; else default.
// A partial manifest keeps its set keys and fills the rest from default, so
// tenants override only what they need.
func LoadManifest(home string) Manifest {
	m := DefaultManifest()
	p := filepath.Join(home, "line.manifest.json")
	b, err := os.ReadFile(p)
	if err != nil {
		return m
	}
	var got Manifest
	if json.Unmarshal(b, &got) != nil {
		return m
	}
	if got.Line == "" {
		got.Line = m.Line
	}
	if got.Road == "" {
		got.Road = m.Road
	}
	if got.State == "" {
		got.State = m.State
	}
	if got.Log == "" {
		got.Log = m.Log
	}
	if len(got.Doctrine) == 0 {
		got.Doctrine = m.Doctrine
	}
	if got.Plans == nil {
		got.Plans = m.Plans
	}
	if got.Wall == "" {
		got.Wall = m.Wall
	}
	return got
}

// Tenant is one project ground the server carries.
type Tenant struct {
	Name     string
	Home     string
	Manifest Manifest
	Engine   string      // command that wakes this project's ask_steward engine
	Policy   rbac.Policy // RBAC policy for this tenant
}

func (t Tenant) resolve(rel string) string {
	if rel == "" {
		return ""
	}
	if filepath.IsAbs(rel) {
		return rel
	}
	return filepath.Join(t.Home, rel)
}

// LinePath / LogPath / RoadCandidates kept for orient compatibility, now
// manifest-driven.
func (t Tenant) LinePath() string  { return t.resolve(t.Manifest.Line) }
func (t Tenant) LogPath() string   { return t.resolve(t.Manifest.Log) }
func (t Tenant) RoadPath() string  { return t.resolve(t.Manifest.Road) }
func (t Tenant) StatePath() string { return t.resolve(t.Manifest.State) }

func (t Tenant) RoadCandidates() []string {
	cands := []string{}
	if t.Manifest.Road != "" {
		cands = append(cands, t.resolve(t.Manifest.Road))
	}
	if t.Manifest.State != "" {
		cands = append(cands, t.resolve(t.Manifest.State))
	}
	return cands
}

// DoctrineDirs returns resolved absolute doctrine directories.
func (t Tenant) DoctrineDirs() []string {
	out := []string{}
	for _, d := range t.Manifest.Doctrine {
		out = append(out, t.resolve(d))
	}
	return out
}

// PlanPath resolves a plan name to an absolute file via the manifest's plans
// map, then the built-in atlas map, then plans/<which> or <which> within Home.
// Returns "" when no such plan exists (honest denial).
func (t Tenant) PlanPath(which string) string {
	which = strings.ToLower(strings.TrimSpace(which))
	if which == "" {
		return ""
	}
	if p, ok := t.Manifest.Plans[which]; ok {
		return t.resolve(p)
	}
	builtin := map[string]string{
		"road":       "THE_ROAD.md",
		"state":      "STATE_OF_BUILD.md",
		"catalog":    "THE_CATALOG.md",
		"acceptance": "ACCEPTANCE.md",
		"charter":    "CHARTER.md",
	}
	if f, ok := builtin[which]; ok {
		return t.resolve(f)
	}
	for _, cand := range []string{filepath.Join("plans", which), which} {
		p := t.resolve(cand)
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}

// WallRoot is the permission root: everything about a project stays inside.
func (t Tenant) WallRoot() string {
	return t.resolve(t.Manifest.Wall)
}

// Registry is the set of tenants this server carries.
type Registry struct {
	order         []string
	byName        map[string]Tenant
	defaultTenant string
}

func NewRegistry() *Registry {
	return &Registry{byName: map[string]Tenant{}}
}

// Add registers (or replaces) a tenant. First-added stays the default unless
// the operator sets one. The manifest and RBAC policy are loaded from Home at add time.
func (r *Registry) Add(name, home string) error {
	if name == "" || home == "" {
		return fmt.Errorf("tenant needs both name and path")
	}
	abs, err := filepath.Abs(home)
	if err != nil {
		return err
	}
	// THE ARCHIVE IS NOT A TENANT, BY ANY ROAD (2026-09-12). The walk in
	// `ground` refuses to find it; this refuses to carry it even when
	// something hands it over directly -- an explicit --tenant tag included.
	// Detection was the road it actually came in by, twice; a rule that only
	// guards the road it was broken on is a rule with a way around it.
	if ground.Barred(abs) || ground.Barred(name) {
		return fmt.Errorf("refused: THE LINE does not carry %q as %q. RULE 1: "+
			"the archive is outside the estate -- never served, never indexed, "+
			"never read from here, and never by a flag", abs, name)
	}
	key := strings.ToLower(name)
	if _, seen := r.byName[key]; !seen {
		r.order = append(r.order, key)
	}
	r.byName[key] = Tenant{
		Name:     key,
		Home:     abs,
		Manifest: LoadManifest(abs),
		Policy:   rbac.LoadPolicy(abs),
	}
	return nil
}

// Has reports whether a tenant is registered (case-insensitive).
func (r *Registry) Has(name string) bool {
	_, ok := r.byName[strings.ToLower(strings.TrimSpace(name))]
	return ok
}

// SetEngine wires the ask_steward engine command for a tenant.
func (r *Registry) SetEngine(name, cmd string) error {
	key := strings.ToLower(strings.TrimSpace(name))
	t, ok := r.byName[key]
	if !ok {
		return fmt.Errorf("cannot set engine for unknown tenant %q", name)
	}
	t.Engine = cmd
	r.byName[key] = t
	return nil
}

func (r *Registry) SetDefault(name string) error {
	key := strings.ToLower(name)
	if _, ok := r.byName[key]; !ok {
		return fmt.Errorf("default tenant %q is not registered", name)
	}
	r.defaultTenant = key
	return nil
}

// Default returns the default tenant name: explicit default, else neiro
// (the only auto-carry tenant), else atlas if present, else first registered.
func (r *Registry) Default() (string, error) {
	if r.defaultTenant != "" {
		return r.defaultTenant, nil
	}
	for _, k := range r.order {
		if k == "neiro" {
			return k, nil
		}
	}
	for _, k := range r.order {
		if k == "atlas" {
			return k, nil
		}
	}
	if len(r.order) > 0 {
		return r.order[0], nil
	}
	return "", fmt.Errorf("no tenants registered")
}

// Resolve finds a tenant by name; an unknown project refuses BY NAME --
// strangers get no context (the enrollment law, carried into transport).
func (r *Registry) Resolve(project string) (Tenant, error) {
	key := strings.ToLower(strings.TrimSpace(project))
	if key == "" {
		key, _ = r.Default()
	}
	t, ok := r.byName[key]
	if !ok {
		return Tenant{}, fmt.Errorf("unknown project %q: not a carried tenant", project)
	}
	return t, nil
}

// Names lists carried projects in registration order (for muster/tools list).
func (r *Registry) Names() []string {
	out := make([]string, len(r.order))
	copy(out, r.order)
	return out
}

// CheckRBAC checks if an agent has permission for a tool on a tenant.
// Returns (allowed, role, reason). If no policy is set, allows all (open mode).
func (t Tenant) CheckRBAC(agentID, toolName string) (bool, string, string) {
	// If no roles are assigned, open mode — allow everything
	if len(t.Policy.Assign) == 0 {
		return true, "", ""
	}
	return rbac.Can(t.Policy, agentID, toolName)
}

// AssignRole assigns a role to an agent in this tenant's policy.
func (t *Tenant) AssignRole(agentID, roleName string) error {
	return rbac.AssignAgent(&t.Policy, agentID, roleName)
}

// SavePolicy saves this tenant's RBAC policy to disk.
func (t Tenant) SavePolicy() error {
	return rbac.SavePolicy(t.Home, t.Policy)
}
