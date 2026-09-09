// Open: the expanded context bundle at a depth (F1 step 3, small).
//
// Depth 1 is the voice card (folded door facts). Depth 2 adds the ladder
// and recent ledger lines (capped, truncated by rule). Depth 3 adds the
// project's get_in_line pack (rendered by the tool layer, reused here).
// Read-only: this package opens files for reading and parses door answers.
// Unknown voices are refused by name; depths outside 1-3 are refused; an
// absent ledger is named, never an error.
package rack

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// VoiceCard renders one voice from folded door facts. Capabilities sort
// ascending so API order never leaks into the bundle.
func VoiceCard(name, tier string, size int64, family string, caps []string) string {
	sorted := append([]string(nil), caps...)
	sortStrings(sorted)
	var b strings.Builder
	fmt.Fprintf(&b, "VOICE %s\n", name)
	fmt.Fprintf(&b, "  tier: %s · size: %.1fGB · family: %s\n", tier, float64(size)/1e9, family)
	fmt.Fprintf(&b, "  capabilities: %s", strings.Join(sorted, ", "))
	return b.String()
}

// MemoryLines renders up to the last 5 witness lines, or names the absence.
// Answers over 200 runes truncate with their remainder counted.
func MemoryLines(lines []string) string {
	if len(lines) == 0 {
		return "  (no ledger yet)"
	}
	if len(lines) > 5 {
		lines = lines[len(lines)-5:]
	}
	var b strings.Builder
	for i, ln := range lines {
		var e struct {
			TS       string `json:"ts"`
			Voice    string `json:"voice"`
			Question string `json:"question"`
			Answer   string `json:"answer"`
		}
		if err := json.Unmarshal([]byte(ln), &e); err != nil {
			continue
		}
		if i > 0 {
			b.WriteByte('\n')
		}
		fmt.Fprintf(&b, "  [%s] %s :: %s => %s", e.TS, e.Voice, e.Question, Shorten(e.Answer))
	}
	if b.Len() == 0 {
		return "  (no ledger yet)"
	}
	return b.String()
}

// Shorten caps an answer at 200 runes, counting the remainder.
func Shorten(answer string) string {
	r := []rune(answer)
	if len(r) <= 200 {
		return answer
	}
	return string(r[:200]) + fmt.Sprintf("… (+%d more)", len(r)-200)
}

// ReadLedger reads the witness lines (missing file reads as absent).
func ReadLedger(home string) ([]string, error) {
	b, err := os.ReadFile(filepath.Join(home, "state", "rack_ledger.jsonl"))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	var out []string
	for _, ln := range strings.Split(string(b), "\n") {
		if strings.TrimSpace(ln) != "" {
			out = append(out, ln)
		}
	}
	return out, nil
}

// Bundle assembles the bundle: header, card, and per depth the ladder +
// memory (2) and the ground pack (3). Depth outside 1-3 is refused.
func Bundle(project, voice string, tier string, size int64, family string,
	caps []string, ladderText string, ledger []string, groundPack string, depth int) (string, error) {
	if depth < 1 || depth > 3 {
		return "", fmt.Errorf("refused: depth is 1, 2, or 3 — not %d", depth)
	}
	var b strings.Builder
	fmt.Fprintf(&b, "CONTEXT BUNDLE — %s at depth %d (%s)\n\n", voice, depth, project)
	b.WriteString(VoiceCard(voice, tier, size, family, caps))
	if depth >= 2 {
		b.WriteString("\nLADDER\n\n")
		b.WriteString(strings.TrimRight(ladderText, "\n"))
		b.WriteString("\nMEMORY (last 5)\n")
		b.WriteString(MemoryLines(ledger))
	}
	if depth >= 3 {
		b.WriteString("\nGROUND\n\n")
		b.WriteString(groundPack)
	}
	b.WriteByte('\n')
	return b.String(), nil
}
