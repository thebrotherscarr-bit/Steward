// Package rack is F1's local-voice layer: the rack_* tools over THE LINE,
// backed by loopback Ollama models and nothing else. No hosted inference,
// no API keys, no egress — a non-loopback host is refused outright (the
// mesh egress law, kept).
//
// Step 1 (small): List + Ladder. Ask/Open stay honestly refusing until
// their turn (see tools.go).
package rack

import (
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"sort"
	"strings"
	"time"
)

// Tiers by model bytes (v1 contract, shared with tools/cut_rack_vectors.py).
const (
	ScoutMax = 3_000_000_000
	VoiceMax = 8_000_000_000
)

// Voice is one lawful local voice.
type Voice struct {
	Name   string
	Size   int64
	Family string
}

// TierOf buckets a voice: scout (small/fast), voice (working), mind (heavy).
func TierOf(size int64) string {
	if size <= ScoutMax {
		return "scout"
	}
	if size <= VoiceMax {
		return "voice"
	}
	return "mind"
}

// Host resolves the Ollama door: OLLAMA_HOST or loopback default. Anything
// not loopback is refused — the rack never reaches outward.
//
// Two normalizations, both witnessed: a bare host:port gains http://
// (Ollama itself exports OLLAMA_HOST=0.0.0.0:11434 as its bind address),
// and 0.0.0.0/:: count as this-host — dialing them reaches loopback, never
// outward, exactly like 127.0.0.1.
func Host() (string, error) {
	raw := strings.TrimSpace(os.Getenv("OLLAMA_HOST"))
	if raw == "" {
		raw = "http://127.0.0.1:11434"
	}
	if !strings.Contains(raw, "://") {
		raw = "http://" + raw
	}
	u, err := url.Parse(raw)
	if err != nil || u.Hostname() == "" {
		return "", fmt.Errorf("refused: OLLAMA_HOST %q is not a door", raw)
	}
	host := u.Hostname()
	if host == "127.0.0.1" || host == "::1" || host == "0.0.0.0" || host == "::" ||
		strings.EqualFold(host, "localhost") {
		return strings.TrimRight(raw, "/"), nil
	}
	if ip := net.ParseIP(host); ip != nil && ip.IsLoopback() {
		return strings.TrimRight(raw, "/"), nil
	}
	return "", fmt.Errorf("refused: OLLAMA_HOST %q is not loopback — the rack never reaches outward", host)
}

// List asks the loopback door for /api/tags and returns the voices.
func List(host string) ([]Voice, error) {
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(host + "/api/tags")
	if err != nil {
		return nil, fmt.Errorf("the rack is silent (%s): %s", host, err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if err != nil {
		return nil, err
	}
	return ParseTags(body)
}

// ParseTags reads one /api/tags document (shared by List and the tests,
// so the golden fold and the live door parse identically).
func ParseTags(body []byte) ([]Voice, error) {
	var doc struct {
		Models []struct {
			Name    string `json:"name"`
			Size    int64  `json:"size"`
			Details struct {
				Family string `json:"family"`
			} `json:"details"`
		} `json:"models"`
	}
	if err := json.Unmarshal(body, &doc); err != nil {
		return nil, fmt.Errorf("the rack spoke unparsably: %s", err)
	}
	var out []Voice
	for _, m := range doc.Models {
		family := m.Details.Family
		if family == "" {
			family = "-"
		}
		out = append(out, Voice{Name: m.Name, Size: m.Size, Family: family})
	}
	return out, nil
}

// Ladder renders voices in tier order (scout/voice/mind), name ascending
// within — byte-exact with the golden cutter. No role inference in v1:
// the ladder shows, never guesses.
func Ladder(voices []Voice) string {
	groups := map[string][]Voice{}
	for _, v := range voices {
		t := TierOf(v.Size)
		groups[t] = append(groups[t], v)
	}
	for _, g := range groups {
		sort.Slice(g, func(i, j int) bool { return g[i].Name < g[j].Name })
	}
	var b strings.Builder
	fmt.Fprintf(&b, "THE RACK — lawful local voices (%d), loopback only\n", len(voices))
	caps := map[string]string{"scout": "≤3GB", "voice": "≤8GB", "mind": ">8GB"}
	for _, tier := range []string{"scout", "voice", "mind"} {
		g, ok := groups[tier]
		if !ok {
			continue
		}
		fmt.Fprintf(&b, "  %s (%s):\n", tier, caps[tier])
		for _, v := range g {
			fmt.Fprintf(&b, "    - %s · %.1fGB · %s\n", v.Name, float64(v.Size)/1e9, v.Family)
		}
	}
	return b.String()
}
