// Package orient assembles the orientation pack per tenant: standing law +
// LINE + ROAD + LOG TAIL, capped at the 60k law. Port of the Rust
// orient_home (A2-04), generalized over tenants and manifest-aware: a missing
// component is named honestly rather than refusing the whole pack.
package orient

import (
	"fmt"
	"os"
	"strings"

	"atlas/line/internal/tenant"
)

const Cap = 60_000

const StandingLaw = `== ATLAS ORIENTATION ==
state = fold(record): nothing is deleted; append and supersede.
Propose, never dispose: can_approve is false in every declaration,
and approval lives in the operator's hand alone.
Prove hermetic on temp ground; leave your toll in SEAT_LOG.md.

`

func readCapped(path string, maxChars int) (string, bool) {
	b, err := os.ReadFile(path)
	if err != nil {
		return "", false
	}
	s := string(b)
	r := []rune(s)
	if len(r) > maxChars {
		r = r[:maxChars]
	}
	return string(r), true
}

func tailLines(text string, n int) string {
	lines := strings.Split(strings.TrimRight(text, "\r\n"), "\n")
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	return strings.Join(lines, "\n")
}

// ForTenant assembles the pack for one carried tenant, degrading gracefully
// when a component document is absent (named honestly, not refused).
func ForTenant(t tenant.Tenant) (string, error) {
	var b strings.Builder
	b.WriteString(StandingLaw)

	// THE LINE: who sits here.
	line, ok := readCapped(t.LinePath(), 4_000)
	if ok {
		fmt.Fprintf(&b, "-- LINE (%s) --\n%s\n\n", t.Name, line)
	} else {
		fmt.Fprintf(&b, "-- LINE (%s) --\n[no line document carried for %q]\n\n", t.Name, t.Name)
	}

	// THE ROAD: what is next.
	var roadText string
	for _, cand := range t.RoadCandidates() {
		if txt, ok := readCapped(cand, 4_000); ok {
			roadText = txt
			break
		}
	}
	if roadText != "" {
		fmt.Fprintf(&b, "-- ROAD --\n%s\n\n", roadText)
	} else {
		fmt.Fprintf(&b, "-- ROAD --\n[no road document carried for %q]\n\n", t.Name)
	}

	// THE LOG TAIL: what the last seats landed.
	logPath := t.LogPath()
	if logPath != "" {
		if fi, err := os.Stat(logPath); err == nil {
			if fi.IsDir() {
				entries, derr := os.ReadDir(logPath)
				if derr == nil && len(entries) > 0 {
					names := make([]string, 0, len(entries))
					for _, e := range entries {
						if !e.IsDir() {
							names = append(names, e.Name())
						}
					}
					sortStrings(names)
					fmt.Fprintf(&b, "-- LOG TAIL (%s/) --\n%s\n", filepathBase(logPath),
						strings.Join(names, "\n"))
				} else {
					fmt.Fprintf(&b, "-- LOG TAIL --\n[handoffs dir %s empty]\n", logPath)
				}
			} else {
				if raw, ok := readCapped(logPath, 40_000); ok {
					fmt.Fprintf(&b, "-- LOG TAIL --\n%s\n", tailLines(raw, 40))
				}
			}
		} else {
			fmt.Fprintf(&b, "-- LOG TAIL --\n[no handoffs carried for %q]\n", t.Name)
		}
	} else {
		fmt.Fprintf(&b, "-- LOG TAIL --\n[no handoffs configured for %q]\n", t.Name)
	}

	out := b.String()
	if r := []rune(out); len(r) > Cap {
		out = string(r[:Cap]) + "\n\n[truncated at the 60000-character law]\n"
	}
	return out, nil
}

func filepathBase(p string) string {
	if i := strings.LastIndexAny(p, `/\`); i >= 0 {
		return p[i+1:]
	}
	return p
}

func sortStrings(s []string) {
	for i := 1; i < len(s); i++ {
		for j := i; j > 0 && s[j] < s[j-1]; j-- {
			s[j], s[j-1] = s[j-1], s[j]
		}
	}
}
