// Package trust persists cross-tenant tool delegations (N0 hygiene).
//
// The wall law holds: a trust grant is recorded in the CALLER's home at
// state/trust.json — everything about a project stays inside its home.
// Enforcement (Call consulting the store on cross-project hops) lands in
// N6 SaaS; N0 proves persistence + honest listing, never fabrication.
package trust

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// Grant is one delegation: from-project's actor may (or may not) invoke
// tool on to-project's ground.
type Grant struct {
	From   string `json:"from"`
	To     string `json:"to"`
	Tool   string `json:"tool"`
	Action string `json:"action"` // allow | deny
	TS     string `json:"ts"`
}

// Store is the persisted set.
type Store struct {
	Grants []Grant `json:"grants"`
}

func path(home string) string { return filepath.Join(home, "state", "trust.json") }

// Load reads the store; absence is an honest empty, never an error.
func Load(home string) Store {
	var s Store
	b, err := os.ReadFile(path(home))
	if err != nil {
		return s
	}
	_ = json.Unmarshal(b, &s)
	return s
}

// Save writes the store atomically (temp + rename) inside the home.
func Save(home string, s Store) error {
	if err := os.MkdirAll(filepath.Join(home, "state"), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	tmp := path(home) + ".tmp"
	if err := os.WriteFile(tmp, append(b, '\n'), 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path(home))
}

// Upsert records one grant, replacing any prior same from/to/tool triple.
func Upsert(home string, g Grant) (Store, error) {
	s := Load(home)
	if g.TS == "" {
		g.TS = time.Now().UTC().Format(time.RFC3339)
	}
	kept := s.Grants[:0]
	for _, e := range s.Grants {
		if e.From == g.From && e.To == g.To && e.Tool == g.Tool {
			continue
		}
		kept = append(kept, e)
	}
	s.Grants = append(kept, g)
	sort.Slice(s.Grants, func(i, j int) bool {
		if s.Grants[i].From != s.Grants[j].From {
			return s.Grants[i].From < s.Grants[j].From
		}
		if s.Grants[i].To != s.Grants[j].To {
			return s.Grants[i].To < s.Grants[j].To
		}
		return s.Grants[i].Tool < s.Grants[j].Tool
	})
	if err := Save(home, s); err != nil {
		return s, err
	}
	return s, nil
}

// Render lists the store honestly; empty names the absence.
func Render(home string) string {
	s := Load(home)
	if len(s.Grants) == 0 {
		return "TRUST — no delegations recorded (empty is honest, never fabricated)."
	}
	var b strings.Builder
	fmt.Fprintf(&b, "TRUST — %d delegation(s):\n", len(s.Grants))
	for _, g := range s.Grants {
		fmt.Fprintf(&b, "  %s %s: %s → %s (%s)\n", strings.ToUpper(g.Action), g.Tool, g.From, g.To, g.TS)
	}
	return b.String()
}
