// Memory: F1-01 envelopes — every answer carries citations or is refused.
//
// An envelope wraps witness records (the rack ledger rack_ask keeps) as
// cited answers. Filters AND: voice exact, question case-insensitive
// substring. Empty filters return the latest single. No match — or an empty
// ledger — is a refusal with the pinned words, never an invented answer and
// never an uncited one.
package rack

import (
	"encoding/json"
	"fmt"
	"strings"
)

// witness is one ledger line (shape shared with Witness).
type witness struct {
	TS       string `json:"ts"`
	Voice    string `json:"voice"`
	Question string `json:"question"`
	Answer   string `json:"answer"`
}

func parseWitnesses(lines []string) []witness {
	var out []witness
	for _, ln := range lines {
		var w witness
		if err := json.Unmarshal([]byte(ln), &w); err != nil {
			continue
		}
		out = append(out, w)
	}
	return out
}

// Envelope renders matched witnesses. Latest 5 at most, the remainder
// counted, never silently dropped.
func Envelope(query string, found []witness) string {
	var b strings.Builder
	fmt.Fprintf(&b, "ENVELOPE — %q (%d cited)\n", query, len(found))
	shown := found
	extra := ""
	if len(found) > 5 {
		shown = found[len(found)-5:]
		extra = fmt.Sprintf("\n  (+%d earlier, narrow the query)", len(found)-5)
	}
	for i, w := range shown {
		if i > 0 {
			b.WriteString("\n\n")
		}
		fmt.Fprintf(&b, "  text: %s\n  citations:\n    - [%s] %s :: %s",
			w.Answer, w.TS, w.Voice, w.Question)
	}
	b.WriteString(extra + "\n")
	return b.String()
}

// Recall matches the ledger and renders, or refuses with pinned words.
func Recall(home, voice, question string) (string, error) {
	lines, err := ReadLedger(home)
	if err != nil {
		return "", err
	}
	if len(parseWitnesses(lines)) == 0 {
		return "", fmt.Errorf("refused: the ledger is empty — no cited memory.")
	}
	if voice == "" && question == "" {
		all := parseWitnesses(lines)
		return Envelope("latest", all[len(all)-1:]), nil
	}
	var found []witness
	for _, w := range parseWitnesses(lines) {
		if voice != "" && w.Voice != voice {
			continue
		}
		if question != "" && !strings.Contains(strings.ToLower(w.Question), strings.ToLower(question)) {
			continue
		}
		found = append(found, w)
	}
	if len(found) == 0 {
		q := question
		if q == "" {
			q = voice
		}
		return "", fmt.Errorf("refused: no cited memory for %q — never invented, never uncited.", q)
	}
	return Envelope(questionOr(voice, question), found), nil
}

func questionOr(voice, question string) string {
	if question != "" {
		return question
	}
	return voice
}
