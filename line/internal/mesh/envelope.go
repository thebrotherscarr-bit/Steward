// Envelope: the links-chain entry shape, byte-compatible with the estate.
//
// One message = one chain entry: body {ts, kind, payload, prev, actor} hashed
// as sha256(prev || canon(body)) where canon is Python's
// json.dumps(body, sort_keys=True, ensure_ascii=False) — separators ", " and
// ": ", short escapes, raw UTF-8. sig/pub ride OUTSIDE the hashed keys, so an
// old entry never breaks under a signature (links.py:17-21). The message
// signed is the entry hash HEX STRING (links.py:309), verified live against
// the estate's own signed entries (see mesh_test.go, forge fixture).
package mesh

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"time"
)

// Genesis is the first prev, per links.py.
const Genesis = "0000000000000000000000000000000000000000000000000000000000000000"

// WrapSize closes a Merkle wrap every 40 links. Nobody chooses it.
const WrapSize = 40

// Kinds the mesh admits. Forbidden verbs (approve/ascend/merge/...) are not
// kinds and appear nowhere — absent by construction, as in B1.
var lawfulKinds = map[string]bool{
	"mesh": true, "cite": true, "head": true,
	"reconcile": true, "breach_attempt": true,
}

func lawfulKind(k string) bool { return lawfulKinds[k] }

// Payload is the seven-key mesh payload (SPEC_US_MESH §1).
type Payload struct {
	N     int64
	Chan  string
	To    string
	Ct    string
	Mode  string
	Cites []string
	Mark  string
}

// Entry is a full chain line: five hashed keys plus sig/pub outside.
type Entry struct {
	TS      string
	Kind    string
	Payload Payload
	Prev    string
	Actor   string
	Hash    string
	Sig     string // hex of 96B Schnorr, outside the hash
	Pub     string // hex of 64B key, outside the hash
}

// bodyMap renders the hashed five keys for canon.
func (e *Entry) bodyMap() map[string]any {
	cites := make([]any, len(e.Payload.Cites))
	for i, c := range e.Payload.Cites {
		cites[i] = c
	}
	return map[string]any{
		"ts":   e.TS,
		"kind": e.Kind,
		"payload": map[string]any{
			"n": e.Payload.N, "chan": e.Payload.Chan, "to": e.Payload.To,
			"ct": e.Payload.Ct, "mode": e.Payload.Mode,
			"cites": cites, "mark": e.Payload.Mark,
		},
		"prev":  e.Prev,
		"actor": e.Actor,
	}
}

// Canon writes Python json.dumps(v, sort_keys=True, ensure_ascii=False).
// Only the mesh value shapes are admitted: string, integer (json.Number with
// integer syntax), bool, nil, list, object. Floats are REFUSED outright —
// parity with canon.rs CanonRefused::Float: a chain must never depend on
// float formatting.
func Canon(v any) (string, error) {
	var sb strings.Builder
	if err := canonValue(&sb, v); err != nil {
		return "", err
	}
	return sb.String(), nil
}

func canonValue(sb *strings.Builder, v any) error {
	switch t := v.(type) {
	case string:
		canonString(sb, t)
	case json.Number:
		s := t.String()
		if !isIntegerSyntax(s) {
			return fmt.Errorf("canon refuses non-integer number %q", s)
		}
		sb.WriteString(s)
	case int64:
		fmt.Fprintf(sb, "%d", t)
	case int:
		fmt.Fprintf(sb, "%d", t)
	case bool:
		if t {
			sb.WriteString("true")
		} else {
			sb.WriteString("false")
		}
	case nil:
		sb.WriteString("null")
	case []any:
		sb.WriteByte('[')
		for i, e := range t {
			if i > 0 {
				sb.WriteString(", ")
			}
			if err := canonValue(sb, e); err != nil {
				return err
			}
		}
		sb.WriteByte(']')
	case map[string]any:
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		sb.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				sb.WriteString(", ")
			}
			canonString(sb, k)
			sb.WriteString(": ")
			if err := canonValue(sb, t[k]); err != nil {
				return err
			}
		}
		sb.WriteByte('}')
	default:
		return fmt.Errorf("canon refuses %T (floats and exotic shapes never hash)", v)
	}
	return nil
}

func isIntegerSyntax(s string) bool {
	if s == "" {
		return false
	}
	i := 0
	if s[0] == '-' {
		i = 1
	}
	if i >= len(s) {
		return false
	}
	for ; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

// canonString quotes exactly like CPython with ensure_ascii=False: short
// escapes, \u00xx for other C0 controls, raw UTF-8 otherwise.
func canonString(sb *strings.Builder, s string) {
	sb.WriteByte('"')
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch c {
		case '"':
			sb.WriteString("\\\"")
		case '\\':
			sb.WriteString("\\\\")
		case '\n':
			sb.WriteString("\\n")
		case '\r':
			sb.WriteString("\\r")
		case '\t':
			sb.WriteString("\\t")
		case 0x08:
			sb.WriteString("\\b")
		case 0x0c:
			sb.WriteString("\\f")
		default:
			if c < 0x20 {
				fmt.Fprintf(sb, "\\u%04x", c)
			} else {
				sb.WriteByte(c)
			}
		}
	}
	sb.WriteByte('"')
}

// HashEntry computes sha256(prev || canon(body)), hex — links.py:94-96.
func HashEntry(prev string, body map[string]any) (string, error) {
	c, err := Canon(body)
	if err != nil {
		return "", err
	}
	h := sha256.Sum256([]byte(prev + c))
	return hex.EncodeToString(h[:]), nil
}

// NowTS stamps UTC RFC3339, the mesh envelope's clock.
func NowTS() string { return time.Now().UTC().Format(time.RFC3339) }

// lineJSON renders the stored line: entry keys plus hash/sig/pub.
func (e *Entry) lineJSON() (string, error) {
	cites := make([]any, len(e.Payload.Cites))
	for i, c := range e.Payload.Cites {
		cites[i] = c
	}
	m := map[string]any{
		"ts": e.TS, "kind": e.Kind,
		"payload": map[string]any{
			"n": e.Payload.N, "chan": e.Payload.Chan, "to": e.Payload.To,
			"ct": e.Payload.Ct, "mode": e.Payload.Mode,
			"cites": cites, "mark": e.Payload.Mark,
		},
		"prev": e.Prev, "actor": e.Actor, "hash": e.Hash,
	}
	if e.Sig != "" {
		m["sig"] = e.Sig
		m["pub"] = e.Pub
	}
	b, err := json.Marshal(m)
	if err != nil {
		return "", err
	}
	return string(b), nil
}

// ParseLine reads one stored line (numbers via json.Number: integers survive).
func ParseLine(line string) (*Entry, error) {
	dec := json.NewDecoder(bytes.NewBufferString(line))
	dec.UseNumber()
	var m map[string]any
	if err := dec.Decode(&m); err != nil {
		return nil, fmt.Errorf("line is not JSON: %s", err)
	}
	str := func(k string) string {
		s, _ := m[k].(string)
		return s
	}
	pm, _ := m["payload"].(map[string]any)
	num := func(k string) int64 {
		if n, ok := pm[k].(json.Number); ok {
			var v int64
			fmt.Sscan(n.String(), &v)
			return v
		}
		return 0
	}
	var cites []string
	if cl, ok := pm["cites"].([]any); ok {
		for _, c := range cl {
			if s, ok := c.(string); ok {
				cites = append(cites, s)
			}
		}
	}
	pstr := func(k string) string {
		s, _ := pm[k].(string)
		return s
	}
	return &Entry{
		TS: str("ts"), Kind: str("kind"),
		Payload: Payload{N: num("n"), Chan: pstr("chan"), To: pstr("to"),
			Ct: pstr("ct"), Mode: pstr("mode"), Cites: cites, Mark: pstr("mark")},
		Prev: str("prev"), Actor: str("actor"),
		Hash: str("hash"), Sig: str("sig"), Pub: str("pub"),
	}, nil
}

// VerifyEntry rewalks one entry against its running prev: weld continuity,
// hash match, then signature over the hash hex string. It returns nil when
// the entry is sound, else the named break.
func VerifyEntry(e *Entry, wantPrev string) error {
	if e.Prev != wantPrev {
		return fmt.Errorf("TAMPER at n=%d: weld breaks (prev %q, chain holds %q)",
			e.Payload.N, abbrev(e.Prev), abbrev(wantPrev))
	}
	h, err := HashEntry(e.Prev, e.bodyMap())
	if err != nil {
		return fmt.Errorf("TAMPER at n=%d: body unhashable: %s", e.Payload.N, err)
	}
	if h != e.Hash {
		return fmt.Errorf("FLIP at n=%d: hash mismatch, weld holds", e.Payload.N)
	}
	if e.Sig == "" || e.Pub == "" {
		return fmt.Errorf("FORGERY at n=%d: unsigned entry", e.Payload.N)
	}
	sig, err1 := hex.DecodeString(e.Sig)
	pub, err2 := hex.DecodeString(e.Pub)
	if err1 != nil || err2 != nil || !Verify(pub, []byte(e.Hash), sig) {
		return fmt.Errorf("FORGERY at n=%d: signature does not verify", e.Payload.N)
	}
	if Mark(pub) != e.Payload.Mark {
		return fmt.Errorf("FORGERY at n=%d: mark unwelded from key", e.Payload.N)
	}
	return nil
}

func abbrev(s string) string {
	if len(s) > 12 {
		return s[:12]
	}
	return s
}
