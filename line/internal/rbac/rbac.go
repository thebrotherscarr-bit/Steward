// Package rbac provides role-based access control for Atlas tenants.
//
// Roles are scoped to tenants: each tenant defines its own role hierarchy
// and permission set. The operator's role is absolute — approval lives in
// the hand alone, and rbac never grants it.
package rbac

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Role is a named set of permissions within a tenant.
type Role struct {
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Permissions map[string]string `json:"permissions"` // tool → allow/deny
	Implies     []string          `json:"implies,omitempty"` // roles this role includes
}

// Policy defines the RBAC policy for a tenant.
type Policy struct {
	Roles  map[string]Role `json:"roles"`
	Assign map[string]string `json:"assign"` // agent_id → role_name
}

// DefaultPolicy returns the default Atlas RBAC policy:
// - operator: full access (but can_approve is still structurally false)
// - steward: read + edit atlas, deny bash/net
// - agent: read-only
// - guest: deny all
func DefaultPolicy() Policy {
	return Policy{
		Roles: map[string]Role{
			"operator": {
				Name:        "operator",
				Description: "the hand; holds the gate",
				Permissions: map[string]string{
					"read":  "allow",
					"edit":  "allow",
					"bash":  "deny",
					"net":   "deny",
					"tools": "allow",
				},
			},
			"steward": {
				Name:        "steward",
				Description: "plans, specs, keeps THE_ROAD",
				Permissions: map[string]string{
					"read":  "allow",
					"edit":  "allow",
					"bash":  "deny",
					"net":   "deny",
					"tools": "allow",
				},
				Implies: []string{"agent"},
			},
			"agent": {
				Name:        "agent",
				Description: "a declared seat with limited scope",
				Permissions: map[string]string{
					"read":  "allow",
					"edit":  "deny",
					"bash":  "deny",
					"net":   "deny",
					"tools": "allow",
				},
			},
			"guest": {
				Name:        "guest",
				Description: "unauthenticated; deny all",
				Permissions: map[string]string{
					"read":  "deny",
					"edit":  "deny",
					"bash":  "deny",
					"net":   "deny",
					"tools": "deny",
				},
			},
		},
		Assign: map[string]string{},
	}
}

// LoadPolicy reads a tenant's RBAC policy from <home>/rbac.json.
// If absent, returns the default policy.
func LoadPolicy(home string) Policy {
	p := DefaultPolicy()
	path := filepath.Join(home, "rbac.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return p
	}
	var got Policy
	if err := json.Unmarshal(data, &got); err != nil {
		return p
	}
	// Merge: custom roles override defaults, absent roles keep defaults
	if got.Roles != nil {
		for k, v := range got.Roles {
			p.Roles[k] = v
		}
	}
	if got.Assign != nil {
		for k, v := range got.Assign {
			p.Assign[k] = v
		}
	}
	return p
}

// Can checks if an agent has permission for a tool under a policy.
// Returns (allowed, role_name, reason).
func Can(p Policy, agentID, toolName string) (bool, string, string) {
	roleName, ok := p.Assign[agentID]
	if !ok {
		return false, "guest", fmt.Sprintf("agent %q has no assigned role", agentID)
	}
	role, ok := p.Roles[roleName]
	if !ok {
		return false, "guest", fmt.Sprintf("role %q not found in policy", roleName)
	}
	// Check direct permission
	if perm, ok := role.Permissions[toolName]; ok {
		if perm == "allow" {
			return true, roleName, ""
		}
		if perm == "deny" {
			return false, roleName, fmt.Sprintf("role %q denies tool %q", roleName, toolName)
		}
	}
	// Check wildcard
	if perm, ok := role.Permissions["*"]; ok {
		if perm == "allow" {
			return true, roleName, ""
		}
		if perm == "deny" {
			return false, roleName, fmt.Sprintf("role %q denies all tools", roleName)
		}
	}
	// Check implied roles (breadth-first)
	visited := map[string]bool{roleName: true}
	queue := append([]string{}, role.Implies...)
	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]
		if visited[current] {
			continue
		}
		visited[current] = true
		r, ok := p.Roles[current]
		if !ok {
			continue
		}
		if perm, ok := r.Permissions[toolName]; ok {
			if perm == "allow" {
				return true, current, ""
			}
			if perm == "deny" {
				return false, current, fmt.Sprintf("implied role %q denies tool %q", current, toolName)
			}
		}
		queue = append(queue, r.Implies...)
	}
	return false, roleName, fmt.Sprintf("role %q has no permission for tool %q", roleName, toolName)
}

// AssignAgent assigns a role to an agent in the policy.
func AssignAgent(p *Policy, agentID, roleName string) error {
	if _, ok := p.Roles[roleName]; !ok {
		return fmt.Errorf("role %q does not exist", roleName)
	}
	p.Assign[strings.ToLower(agentID)] = roleName
	return nil
}

// SavePolicy writes the RBAC policy to <home>/rbac.json.
func SavePolicy(home string, p Policy) error {
	data, err := json.MarshalIndent(p, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(home, "rbac.json"), data, 0644)
}
