// Ask: route a question to a lawful local voice and witness the answer.
//
// Routing contract v1 (shared with tools/cut_rack_ask_vectors.py):
//  1. an explicit voice must name a ladder voice, else refused by name; an
//     embedding voice named explicitly is refused with the reason;
//  2. by default, the first ladder voice (tier scout/voice/mind, name
//     ascending) whose /api/show capabilities lack "embedding". None
//     speaking -> refused, named.
//
// The ask goes to /api/generate (stream:false) on the loopback door only.
// The answer is witnessed to <home>/state/rack_ledger.jsonl — the record
// F1-01's envelopes will cite. Citations themselves ride next, not here.
package rack

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// askTimeout bounds one local weighing. Generous like ask_steward: small
// reasoning voices think a while, and a timeout is a refusal, not a guess.
const askTimeout = 600 * time.Second

// Capabilities asks the door what a voice can do (chat/completion/vision/
// embedding). Facts, not inference.
func Capabilities(host, model string) ([]string, error) {
	body, _ := json.Marshal(map[string]any{"model": model})
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Post(host+"/api/show", "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("voice %q does not answer for its capabilities: %s", model, err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if err != nil {
		return nil, err
	}
	var doc struct {
		Capabilities []string `json:"capabilities"`
		Error        string   `json:"error"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil, fmt.Errorf("voice %q speaks unparsably: %s", model, err)
	}
	if doc.Error != "" {
		return nil, fmt.Errorf("voice %q refused: %s", model, doc.Error)
	}
	return doc.Capabilities, nil
}

// Speaking reports whether a voice speaks (not an embedding-only model).
func Speaking(caps []string) bool {
	for _, c := range caps {
		if c == "embedding" {
			return false
		}
	}
	return true
}

// Route picks the voice: explicit by name, or the first speaking ladder
// voice. Tiers order scout/voice/mind (Ladder's grouping); names ascend.
func Route(host, want string, voices []Voice) (string, error) {
	byTier := map[string][]Voice{}
	for _, v := range voices {
		t := TierOf(v.Size)
		byTier[t] = append(byTier[t], v)
	}
	var ladder []string
	for _, tier := range []string{"scout", "voice", "mind"} {
		names := []string{}
		for _, v := range byTier[tier] {
			names = append(names, v.Name)
		}
		sortStrings(names)
		ladder = append(ladder, names...)
	}
	onLadder := func(name string) bool {
		for _, n := range ladder {
			if n == name {
				return true
			}
		}
		return false
	}
	if want != "" {
		if !onLadder(want) {
			return "", fmt.Errorf("refused: voice %q is not on the rack — nothing fabricated", want)
		}
		caps, err := Capabilities(host, want)
		if err != nil {
			return "", err
		}
		if !Speaking(caps) {
			return "", fmt.Errorf("refused: voice %q is an embedding model, not a speaking voice", want)
		}
		return want, nil
	}
	for _, name := range ladder {
		caps, err := Capabilities(host, name)
		if err != nil {
			continue
		}
		if Speaking(caps) {
			return name, nil
		}
	}
	return "", fmt.Errorf("refused: no speaking voice on the rack")
}

// Ask puts one question to one voice. The answer must arrive whole
// (done:true) and non-empty, or it is a refusal — never a guess, never a
// truncation passed off as whole.
func Ask(host, model, question string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), askTimeout)
	defer cancel()
	return AskCtx(ctx, host, model, question)
}

// AskCtx is Ask with the caller's context: cancel ends the Ollama stream
// the way a closed door ends a conversation — immediately, honestly.
func AskCtx(ctx context.Context, host, model, question string) (string, error) {
	ans, _, err := askStream(ctx, host, model, question, false, nil)
	return ans, err
}

// AskStream sends with stream:true, forwarding each response token to
// onToken (nil = no forwarding). The whole-answer discipline holds:
// unfinished or empty is a refusal, and nothing partial is returned.
func AskStream(ctx context.Context, host, model, question string, onToken func(string)) (string, error) {
	ans, _, err := askStream(ctx, host, model, question, true, onToken)
	return ans, err
}

// Detail carries what the door reports about one answer: token counts and
// durations where Ollama states them, wall time always measured locally.
type Detail struct {
	EvalCount      int64
	EvalDurationMs int64
	WallMs         int64
}

// AskDetail is Ask with telemetry: the answer plus what it cost.
func AskDetail(ctx context.Context, host, model, question string) (string, Detail, error) {
	start := time.Now()
	ans, det, err := askStream(ctx, host, model, question, false, nil)
	det.WallMs = time.Since(start).Milliseconds()
	return ans, det, err
}

func askStream(ctx context.Context, host, model, question string, stream bool, onToken func(string)) (string, Detail, error) {
	var zero Detail
	question = strings.TrimSpace(question)
	if question == "" {
		return "", zero, fmt.Errorf("rack_ask needs a question — no voice is asked nothing")
	}
	body, _ := json.Marshal(map[string]any{
		"model": model, "prompt": question, "stream": stream,
	})
	req, err := http.NewRequestWithContext(ctx, "POST", host+"/api/generate", bytes.NewReader(body))
	if err != nil {
		return "", zero, err
	}
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: 0} // the context bounds the call, not the clock alone
	resp, err := client.Do(req)
	if err != nil {
		return "", zero, fmt.Errorf("voice %q did not answer: %s", model, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		raw, _ := io.ReadAll(io.LimitReader(resp.Body, 4<<10))
		return "", zero, fmt.Errorf("voice %q refused (door %d): %s", model, resp.StatusCode, strings.TrimSpace(string(raw)))
	}
	if !stream {
		raw, err := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
		if err != nil {
			return "", zero, err
		}
		return finishAnswer(model, raw)
	}
	return finishStream(model, resp.Body, onToken)
}

// finishAnswer judges one whole (stream:false) answer by the standing
// discipline: done, non-empty, or refused. Telemetry rides along where
// the door states it (eval_count, eval_duration in ns).
func finishAnswer(model string, raw []byte) (string, Detail, error) {
	var zero Detail
	var doc struct {
		Model        string `json:"model"`
		Response     string `json:"response"`
		Done         bool   `json:"done"`
		Error        string `json:"error"`
		EvalCount    int64  `json:"eval_count"`
		EvalDuration int64  `json:"eval_duration"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		return "", zero, fmt.Errorf("voice %q spoke unparsably: %s", model, err)
	}
	if doc.Error != "" {
		return "", zero, fmt.Errorf("voice %q refused: %s", model, doc.Error)
	}
	if !doc.Done {
		return "", zero, fmt.Errorf("voice %q left the answer unfinished — refused, not truncated", model)
	}
	if strings.TrimSpace(doc.Response) == "" {
		return "", zero, fmt.Errorf("voice %q said nothing — refused", model)
	}
	return doc.Response, Detail{EvalCount: doc.EvalCount, EvalDurationMs: doc.EvalDuration / 1e6}, nil
}

// finishStream assembles one stream:true answer, forwarding tokens as they
// arrive. The same discipline holds at the end: unfinished or empty is a
// refusal and nothing partial escapes. The closing summary object carries
// the telemetry when the door sends it.
func finishStream(model string, body io.Reader, onToken func(string)) (string, Detail, error) {
	var det Detail
	var b strings.Builder
	done := false
	sc := bufio.NewScanner(body)
	sc.Buffer(make([]byte, 0, 64<<10), 8<<20)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var doc struct {
			Response     string `json:"response"`
			Done         bool   `json:"done"`
			Error        string `json:"error"`
			EvalCount    int64  `json:"eval_count"`
			EvalDuration int64  `json:"eval_duration"`
		}
		if err := json.Unmarshal([]byte(line), &doc); err != nil {
			return "", det, fmt.Errorf("voice %q streamed unparsably: %s", model, err)
		}
		if doc.Error != "" {
			return "", det, fmt.Errorf("voice %q refused mid-stream: %s", model, doc.Error)
		}
		if doc.Response != "" {
			b.WriteString(doc.Response)
			if onToken != nil {
				onToken(doc.Response)
			}
		}
		if doc.EvalCount > 0 {
			det.EvalCount = doc.EvalCount
		}
		if doc.EvalDuration > 0 {
			det.EvalDurationMs = doc.EvalDuration / 1e6
		}
		if doc.Done {
			done = true
		}
	}
	if err := sc.Err(); err != nil {
		return "", det, fmt.Errorf("voice %q broke the stream: %s", model, err)
	}
	if !done {
		return "", det, fmt.Errorf("voice %q left the answer unfinished — refused, not truncated", model)
	}
	if strings.TrimSpace(b.String()) == "" {
		return "", det, fmt.Errorf("voice %q said nothing — refused", model)
	}
	return b.String(), det, nil
}

// Witness appends one routed ask to the rack ledger (testimony for F1-01's
// envelopes to cite). Sole writer discipline rides the tool layer's ask
// lock, like remember.
func Witness(home, voice, question, answer string) (string, error) {
	return WitnessV(home, voice, question, answer, nil)
}

// WitnessV carries scan flags as well (empty when clean — uniform schema).
func WitnessV(home, voice, question, answer string, flags []string) (string, error) {
	dir := filepath.Join(home, "state")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	if flags == nil {
		flags = []string{}
	}
	rec := map[string]any{
		"ts":       time.Now().UTC().Format(time.RFC3339),
		"kind":     "rack_ask",
		"voice":    voice,
		"question": question,
		"answer":   answer,
		"flags":    flags,
	}
	b, err := json.Marshal(rec)
	if err != nil {
		return "", err
	}
	line := string(b) + "\n"
	path := filepath.Join(dir, "rack_ledger.jsonl")
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return "", err
	}
	defer f.Close()
	if _, err := f.WriteString(line); err != nil {
		return "", err
	}
	return path, nil
}

func sortStrings(s []string) {
	for i := 1; i < len(s); i++ {
		for j := i; j > 0 && s[j-1] > s[j]; j-- {
			s[j-1], s[j] = s[j], s[j-1]
		}
	}
}
