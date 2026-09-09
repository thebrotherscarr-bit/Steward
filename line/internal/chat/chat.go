// Package chat is N1's conversational layer over the rack: sessions with
// receipts, guard-first sends, streaming asks, and honest isolation.
//
// The record is one append-only file per tenant home: state/chat.jsonl.
// Lines are {kind:chat_open} and {kind:chat_turn}; turns carry n (per
// session, 1..N), the CLEANED question, the whole answer, and receipt =
// sha256(session \n question \n answer \n ts), pinned by
// tools/cut_chat_vectors.py. Guard-blocked sends write NOTHING — no turn,
// no witness. Thinking is never stored and never returned: only the final
// answer reaches the record.
package chat

import (
	"bufio"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"atlas/line/internal/guard"
	"atlas/line/internal/rack"
)

// SessionRe pins the session shape law (cutter holds the same pattern).
var SessionRe = regexp.MustCompile(`^c-\d{8}-\d{6}-[0-9a-f]{8}$`)

// Turn is one witnessed exchange.
type Turn struct {
	N        int      `json:"n"`
	Session  string   `json:"session"`
	TS       string   `json:"ts"`
	Actor    string   `json:"actor"`
	Voice    string   `json:"voice"`
	Question string   `json:"question"`
	Answer   string   `json:"answer"`
	Receipt  string   `json:"receipt"`
	Flags    []string `json:"flags"`
}

func chatPath(home string) string { return filepath.Join(home, "state", "chat.jsonl") }

// SessionID mints c-YYYYMMDD-HHMMSS-<8hex> from wall clock + crypto/rand.
func SessionID() (string, error) {
	var b [4]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return fmt.Sprintf("c-%s-%s",
		time.Now().UTC().Format("20060102-150405"),
		hex.EncodeToString(b[:])), nil
}

// Receipt binds a turn: session, cleaned question, whole answer, timestamp.
func Receipt(session, question, answer, ts string) string {
	h := sha256.Sum256([]byte(session + "\n" + question + "\n" + answer + "\n" + ts))
	return hex.EncodeToString(h[:])
}

func checkSession(session string) error {
	if !SessionRe.MatchString(session) {
		return fmt.Errorf("refused: session %q breaks the shape law (c-YYYYMMDD-HHMMSS-hex8)", session)
	}
	return nil
}

// Start opens a session: one append-only line, under the caller's lock.
func Start(home, actor, voice string) (string, error) {
	session, err := SessionID()
	if err != nil {
		return "", err
	}
	if err := os.MkdirAll(filepath.Join(home, "state"), 0o755); err != nil {
		return "", err
	}
	rec := map[string]any{
		"ts":      time.Now().UTC().Format(time.RFC3339),
		"kind":    "chat_open",
		"session": session,
		"actor":   actor,
		"voice":   voice,
	}
	if err := appendLine(home, rec); err != nil {
		return "", err
	}
	return session, nil
}

// flights tracks in-flight sends per session so chat_cancel ends the
// Ollama stream immediately. Cancel never touches the record.
var (
	flightsMu sync.Mutex
	flights   = map[string]context.CancelFunc{}
)

// Cancel ends an in-flight send; a quiet session is an honest no-op.
func Cancel(session string) string {
	flightsMu.Lock()
	cancel, ok := flights[session]
	flightsMu.Unlock()
	if !ok {
		return fmt.Sprintf("session %s has nothing in flight — nothing cancelled, nothing claimed", session)
	}
	cancel()
	return fmt.Sprintf("session %s cancelled — the stream ends, no partial answer is kept", session)
}

// Send is SendCtx over a background context bounded by the rack timeout.
func Send(home, session, actor, voice, question string) (Turn, error) {
	return SendCtx(context.Background(), home, session, actor, voice, question, nil)
}

// SendStream is SendCtx with per-token forwarding to onToken.
func SendStream(ctx context.Context, home, session, actor, voice, question string, onToken func(string)) (Turn, error) {
	return SendCtx(ctx, home, session, actor, voice, question, onToken)
}

// SendCtx guards first (blocked writes nothing), routes, asks, witnesses
// to the rack ledger, then appends the turn. Whole-answer discipline:
// unfinished or empty is a refusal and the record never sees it.
func SendCtx(ctx context.Context, home, session, actor, voice, question string, onToken func(string)) (Turn, error) {
	var zero Turn
	if err := checkSession(session); err != nil {
		return zero, err
	}
	question = strings.TrimSpace(question)
	if question == "" {
		return zero, fmt.Errorf("chat_send needs a question — no voice is asked nothing")
	}
	clean, flags, blocked, reason := guard.Pipeline(question)
	if blocked {
		return zero, fmt.Errorf("refused: %s", reason)
	}
	host, err := rack.Host()
	if err != nil {
		return zero, err
	}
	voices, err := rack.List(host)
	if err != nil {
		return zero, err
	}
	routed, err := rack.Route(host, strings.TrimSpace(voice), voices)
	if err != nil {
		return zero, err
	}
	ctx, cancel := context.WithTimeout(ctx, 600*time.Second)
	flightsMu.Lock()
	flights[session] = cancel
	flightsMu.Unlock()
	defer func() {
		cancel()
		flightsMu.Lock()
		delete(flights, session)
		flightsMu.Unlock()
	}()
	answer, err := rack.AskStream(ctx, host, routed, clean, onToken)
	if err != nil {
		return zero, err
	}
	if _, err := rack.WitnessV(home, routed, clean, answer, flags); err != nil {
		return zero, err
	}
	turn := Turn{
		N:        nextN(home, session),
		Session:  session,
		TS:       time.Now().UTC().Format(time.RFC3339),
		Actor:    actor,
		Voice:    routed,
		Question: clean,
		Answer:   answer,
		Flags:    flags,
	}
	if turn.Flags == nil {
		turn.Flags = []string{}
	}
	turn.Receipt = Receipt(session, clean, answer, turn.TS)
	rec := map[string]any{
		"ts": turn.TS, "kind": "chat_turn", "n": turn.N,
		"session": session, "actor": actor, "voice": routed,
		"question": clean, "answer": answer,
		"receipt": turn.Receipt, "flags": turn.Flags,
	}
	if err := appendLine(home, rec); err != nil {
		return zero, err
	}
	return turn, nil
}

// List reads one session's turns (empty session = latest session's turns).
// Sessions never see each other — isolation is structural.
func List(home, session string, last int) ([]Turn, error) {
	if session != "" {
		if err := checkSession(session); err != nil {
			return nil, err
		}
	}
	turns, err := readTurns(home, session)
	if err != nil {
		return nil, err
	}
	if last > 0 && len(turns) > last {
		turns = turns[len(turns)-last:]
	}
	return turns, nil
}

// Sessions lists every opened session id in first-seen order.
func Sessions(home string) ([]string, error) {
	f, err := os.Open(chatPath(home))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	defer f.Close()
	var out []string
	seen := map[string]bool{}
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 1<<20), 16<<20)
	for sc.Scan() {
		var doc struct {
			Kind    string `json:"kind"`
			Session string `json:"session"`
		}
		if json.Unmarshal(sc.Bytes(), &doc) != nil {
			continue
		}
		if doc.Session == "" || seen[doc.Session] {
			continue
		}
		seen[doc.Session] = true
		out = append(out, doc.Session)
	}
	return out, sc.Err()
}

func nextN(home, session string) int {
	turns, err := readTurns(home, session)
	if err != nil {
		return 1
	}
	return len(turns) + 1
}

func readTurns(home, session string) ([]Turn, error) {
	f, err := os.Open(chatPath(home))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	defer f.Close()
	var out []Turn
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 1<<20), 16<<20)
	for sc.Scan() {
		var doc struct {
			Kind     string   `json:"kind"`
			N        int      `json:"n"`
			Session  string   `json:"session"`
			TS       string   `json:"ts"`
			Actor    string   `json:"actor"`
			Voice    string   `json:"voice"`
			Question string   `json:"question"`
			Answer   string   `json:"answer"`
			Receipt  string   `json:"receipt"`
			Flags    []string `json:"flags"`
		}
		if json.Unmarshal(sc.Bytes(), &doc) != nil {
			continue
		}
		if doc.Kind != "chat_turn" {
			continue
		}
		if session != "" && doc.Session != session {
			continue
		}
		out = append(out, Turn{
			N: doc.N, Session: doc.Session, TS: doc.TS,
			Actor: doc.Actor, Voice: doc.Voice,
			Question: doc.Question, Answer: doc.Answer,
			Receipt: doc.Receipt, Flags: doc.Flags,
		})
	}
	return out, sc.Err()
}

func appendLine(home string, rec map[string]any) error {
	b, err := json.Marshal(rec)
	if err != nil {
		return err
	}
	f, err := os.OpenFile(chatPath(home), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.WriteString(string(b) + "\n")
	return err
}
