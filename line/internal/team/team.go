// Package team is N5's bridge to the outside: Discord, Slack and WhatsApp
// in both directions, with papers checked at every crossing.
//
// Outbound runs the guard first (injection refuses with no POST, PII sends
// redacted with its marker), then POSTs a platform-shaped payload to the
// operator's own webhook/Cloud URL. Inbound verifies an HMAC shared secret
// in constant time, parses the platform envelope, dedupes by external id,
// and appends — wrong signatures store nothing, replays store once.
// Everything lands in <home>/state/team.jsonl with receipt =
// sha256(direction \n platform \n channel \n agent \n content \n ts),
// pinned by tools/cut_teamchat_vectors.py.
//
// Secrets live ONLY in <home>/state/chat_secrets.json (0600, operator-
// placed, never served, never logged): per-platform webhook URLs, the
// WhatsApp Cloud token + phone id, and the inbound hook secret. No tool
// writes secrets; status reports connected:true/false and nothing more.
// Egress to someone else's server happens here and only here, and only to
// a URL the operator pasted — the named N5 conflict, fenced by allowlist.
package team

import (
	"bufio"
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"atlas/line/internal/guard"
)

// Platforms is the closed set. Anything else is refused by name.
var Platforms = map[string]bool{"discord": true, "slack": true, "whatsapp": true}

// ChannelRe pins the channel shape law (cutter holds the same pattern).
var ChannelRe = regexp.MustCompile(`^[a-z0-9][a-z0-9_-]{0,63}$`)

// Secrets are operator-placed and never leave this package except as
// presence booleans.
type Secrets struct {
	HookSecret      string `json:"hook_secret,omitempty"`
	DiscordWebhook  string `json:"discord_webhook,omitempty"`
	SlackWebhook    string `json:"slack_webhook,omitempty"`
	WhatsappToken   string `json:"whatsapp_token,omitempty"`
	WhatsappPhoneID string `json:"whatsapp_phone_id,omitempty"`
}

// Message is one crossing, either direction.
type Message struct {
	TS         string `json:"ts"`
	Direction  string `json:"direction"`
	Platform   string `json:"platform"`
	Channel    string `json:"channel"`
	Agent      string `json:"agent"`
	Content    string `json:"content"`
	ExternalID string `json:"external_id,omitempty"`
	Receipt    string `json:"receipt"`
}

func teamPath(home string) string   { return filepath.Join(home, "state", "team.jsonl") }
func secretsPath(home string) string { return filepath.Join(home, "state", "chat_secrets.json") }

// Receipt binds a crossing (cutter reproduces this byte-for-byte).
func Receipt(direction, platform, channel, agent, content, ts string) string {
	h := sha256.Sum256([]byte(strings.Join([]string{
		direction, platform, channel, agent, content, ts}, "\n")))
	return hex.EncodeToString(h[:])
}

// LoadSecrets reads the operator-placed file; absence is honest emptiness.
func LoadSecrets(home string) Secrets {
	var s Secrets
	b, err := os.ReadFile(secretsPath(home))
	if err != nil {
		return s
	}
	_ = json.Unmarshal(b, &s)
	return s
}

// Sign computes "sha256="+hex(hmac(secret, body)) for webhook envelopes.
func Sign(secret string, body []byte) string {
	m := hmac.New(sha256.New, []byte(secret))
	m.Write(body)
	return "sha256=" + hex.EncodeToString(m.Sum(nil))
}

// Verify compares in constant time; length leaks nothing, timing neither.
func Verify(secret string, body []byte, signature string) bool {
	if secret == "" || signature == "" {
		return false
	}
	want := Sign(secret, body)
	if len(want) != len(signature) {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(want), []byte(signature)) == 1
}

// Payload builds the platform-shaped outbound body (cutter pins each).
func Payload(platform, text string) ([]byte, error) {
	var doc any
	switch platform {
	case "discord":
		doc = map[string]any{"content": text, "username": "atlas"}
	case "slack":
		doc = map[string]any{"text": text}
	case "whatsapp":
		doc = map[string]any{"messaging_product": "whatsapp", "text": map[string]any{"body": text}}
	default:
		return nil, fmt.Errorf("refused: unknown platform %q — discord|slack|whatsapp only", platform)
	}
	return json.Marshal(doc)
}

func checkCrossing(platform, channel string) error {
	if !Platforms[platform] {
		return fmt.Errorf("refused: unknown platform %q — discord|slack|whatsapp only", platform)
	}
	if !ChannelRe.MatchString(channel) {
		return fmt.Errorf("refused: channel %q breaks the channel law", channel)
	}
	return nil
}

// endpoint resolves where a send POSTs: the operator's URL, https except
// loopback (tests and local doors speak plain http to themselves).
func endpoint(home, platform string) (string, string, error) {
	s := LoadSecrets(home)
	var raw, token string
	switch platform {
	case "discord":
		raw = s.DiscordWebhook
	case "slack":
		raw = s.SlackWebhook
	case "whatsapp":
		if s.WhatsappToken == "" || s.WhatsappPhoneID == "" {
			return "", "", fmt.Errorf("refused: whatsapp needs token + phone id in chat_secrets.json — nothing is sent unconfigured")
		}
		raw = "https://graph.facebook.com/v21.0/" + s.WhatsappPhoneID + "/messages"
		token = s.WhatsappToken
	}
	if raw == "" {
		return "", "", fmt.Errorf("refused: %s has no webhook in chat_secrets.json — connect it first, nothing sent", platform)
	}
	u, err := url.Parse(raw)
	if err != nil || u.Host == "" {
		return "", "", fmt.Errorf("refused: %s webhook is not a URL", platform)
	}
	if u.Scheme != "https" && !isLoopback(u.Hostname()) {
		return "", "", fmt.Errorf("refused: %s webhook must be https (loopback excepted)", platform)
	}
	return raw, token, nil
}

func isLoopback(host string) bool {
	return host == "127.0.0.1" || host == "::1" || strings.EqualFold(host, "localhost")
}

var sendClient = &http.Client{Timeout: 30 * time.Second}

// Send guards, POSTs, and witnesses one outbound crossing.
func Send(home, platform, channel, agent, content string) (Message, error) {
	var zero Message
	platform = strings.ToLower(strings.TrimSpace(platform))
	channel = strings.TrimSpace(channel)
	content = strings.TrimSpace(content)
	if err := checkCrossing(platform, channel); err != nil {
		return zero, err
	}
	if content == "" {
		return zero, fmt.Errorf("team_send needs content — silence is not sent")
	}
	clean, flags, blocked, reason := guard.Pipeline(content)
	if blocked {
		return zero, fmt.Errorf("refused: %s", reason)
	}
	endpointURL, token, err := endpoint(home, platform)
	if err != nil {
		return zero, err
	}
	body, err := Payload(platform, clean)
	if err != nil {
		return zero, err
	}
	req, err := http.NewRequest("POST", endpointURL, bytes.NewReader(body))
	if err != nil {
		return zero, err
	}
	req.Header.Set("Content-Type", "application/json")
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	resp, err := sendClient.Do(req)
	if err != nil {
		return zero, fmt.Errorf("%s did not answer: %s", platform, err)
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, io.LimitReader(resp.Body, 64<<10))
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return zero, fmt.Errorf("%s refused the send (door %d) — nothing witnessed", platform, resp.StatusCode)
	}
	_ = flags
	ts := nowUTC()
	m := Message{TS: ts, Direction: "outbound", Platform: platform,
		Channel: channel, Agent: agent, Content: clean}
	m.Receipt = Receipt(m.Direction, m.Platform, m.Channel, m.Agent, m.Content, m.TS)
	if err := appendMessage(home, m); err != nil {
		return zero, err
	}
	return m, nil
}

// Ingest verifies, parses, dedupes and witnesses one inbound envelope.
// It returns the message, whether it was a duplicate, and — for Slack URL
// verification only — a challenge to echo (nothing stored, ever).
func Ingest(home, platform string, raw []byte, signature string) (Message, bool, string, error) {
	var zero Message
	platform = strings.ToLower(strings.TrimSpace(platform))
	if !Platforms[platform] {
		return zero, false, "", fmt.Errorf("refused: unknown platform %q", platform)
	}
	s := LoadSecrets(home)
	if !Verify(s.HookSecret, raw, signature) {
		return zero, false, "", fmt.Errorf("refused: bad webhook signature — nothing stored, nothing claimed")
	}
	parsed, challenge, err := parseInbound(platform, raw)
	if err != nil {
		return zero, false, "", err
	}
	if challenge != "" {
		return zero, false, challenge, nil
	}
	dup, err := seenExternal(home, platform, parsed.ExternalID)
	if err != nil {
		return zero, false, "", err
	}
	if dup {
		return parsed, true, "", nil
	}
	parsed.TS = nowUTC()
	parsed.Receipt = Receipt(parsed.Direction, parsed.Platform, parsed.Channel, parsed.Agent, parsed.Content, parsed.TS)
	if err := appendMessage(home, parsed); err != nil {
		return zero, false, "", err
	}
	return parsed, false, "", nil
}

func parseInbound(platform string, raw []byte) (Message, string, error) {
	var zero Message
	switch platform {
	case "discord":
		var doc struct {
			ID        string `json:"id"`
			ChannelID string `json:"channel_id"`
			Author    struct {
				Username string `json:"username"`
			} `json:"author"`
			Content string `json:"content"`
		}
		if err := json.Unmarshal(raw, &doc); err != nil {
			return zero, "", fmt.Errorf("discord spoke unparsably — nothing stored")
		}
		if doc.ID == "" || strings.TrimSpace(doc.Content) == "" {
			return zero, "", fmt.Errorf("discord envelope carries no message — nothing stored")
		}
		ch := strings.TrimSpace(doc.ChannelID)
		if ch == "" {
			ch = "general"
		}
		return Message{Direction: "inbound", Platform: "discord", Channel: ch,
			Agent: doc.Author.Username, Content: doc.Content, ExternalID: doc.ID}, "", nil
	case "slack":
		var doc struct {
			Type      string `json:"type"`
			Challenge string `json:"challenge"`
			EventID   string `json:"event_id"`
			Event     struct {
				User    string `json:"user"`
				Channel string `json:"channel"`
				Text    string `json:"text"`
				TS      string `json:"ts"`
			} `json:"event"`
		}
		if err := json.Unmarshal(raw, &doc); err != nil {
			return zero, "", fmt.Errorf("slack spoke unparsably — nothing stored")
		}
		if doc.Type == "url_verification" {
			return zero, doc.Challenge, nil
		}
		if strings.TrimSpace(doc.Event.Text) == "" {
			return zero, "", fmt.Errorf("slack envelope carries no message — nothing stored")
		}
		ext := doc.EventID
		if ext == "" {
			ext = doc.Event.TS
		}
		ch := strings.TrimSpace(doc.Event.Channel)
		if ch == "" {
			ch = "general"
		}
		return Message{Direction: "inbound", Platform: "slack", Channel: ch,
			Agent: doc.Event.User, Content: doc.Event.Text, ExternalID: ext}, "", nil
	case "whatsapp":
		var doc struct {
			Messages []struct {
				ID   string `json:"id"`
				From string `json:"from"`
				Text struct {
					Body string `json:"body"`
				} `json:"text"`
			} `json:"messages"`
		}
		if err := json.Unmarshal(raw, &doc); err != nil {
			return zero, "", fmt.Errorf("whatsapp spoke unparsably — nothing stored")
		}
		if len(doc.Messages) == 0 {
			return zero, "", fmt.Errorf("whatsapp envelope carries no message (statuses are not messages) — nothing stored")
		}
		m := doc.Messages[0]
		if strings.TrimSpace(m.Text.Body) == "" {
			return zero, "", fmt.Errorf("whatsapp message carries no text — nothing stored")
		}
		return Message{Direction: "inbound", Platform: "whatsapp", Channel: "general",
			Agent: m.From, Content: m.Text.Body, ExternalID: m.ID}, "", nil
	}
	return zero, "", fmt.Errorf("refused: unknown platform %q", platform)
}

// History reads crossings, filtered, newest last, capped.
func History(home, channel, platform string, last int) ([]Message, error) {
	f, err := os.Open(teamPath(home))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	defer f.Close()
	var out []Message
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 1<<20), 16<<20)
	for sc.Scan() {
		var m Message
		if json.Unmarshal(sc.Bytes(), &m) != nil {
			continue
		}
		if channel != "" && m.Channel != channel {
			continue
		}
		if platform != "" && m.Platform != platform {
			continue
		}
		out = append(out, m)
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	if last > 0 && len(out) > last {
		out = out[len(out)-last:]
	}
	return out, nil
}

// Presence is the whole status: connected booleans and last-send stamps.
// Secrets never appear here — presence is all any caller learns.
type Presence struct {
	Platform  string `json:"platform"`
	Connected bool   `json:"connected"`
	LastSend  string `json:"last_send,omitempty"`
}

// Status reports presence per platform.
func Status(home string) []Presence {
	s := LoadSecrets(home)
	connected := map[string]bool{
		"discord":  s.DiscordWebhook != "",
		"slack":    s.SlackWebhook != "",
		"whatsapp": s.WhatsappToken != "" && s.WhatsappPhoneID != "",
	}
	last := map[string]string{}
	if hist, err := History(home, "", "", 0); err == nil {
		for _, m := range hist {
			if m.Direction == "outbound" {
				last[m.Platform] = m.TS
			}
		}
	}
	out := []Presence{}
	for _, p := range []string{"discord", "slack", "whatsapp"} {
		out = append(out, Presence{Platform: p, Connected: connected[p], LastSend: last[p]})
	}
	return out
}

func seenExternal(home, platform, ext string) (bool, error) {
	if ext == "" {
		return false, nil
	}
	hist, err := History(home, "", platform, 0)
	if err != nil {
		return false, err
	}
	for _, m := range hist {
		if m.ExternalID == ext {
			return true, nil
		}
	}
	return false, nil
}

func appendMessage(home string, m Message) error {
	if err := os.MkdirAll(filepath.Join(home, "state"), 0o755); err != nil {
		return err
	}
	b, err := json.Marshal(m)
	if err != nil {
		return err
	}
	f, err := os.OpenFile(teamPath(home), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.WriteString(string(b) + "\n")
	return err
}

func nowUTC() string { return time.Now().UTC().Format(time.RFC3339) }
