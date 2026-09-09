// Package auth is N6's gate: API keys with scoped tenants, an iterated
// HMAC-SHA256 KDF (bcrypt would be a dependency; the count and domain are
// pinned by tools/cut_auth_vectors.py), and an append-only audit line per
// create/revoke. Plaintext keys exist once — at creation, in the answer —
// and never again: only hash+salt persist. Revocation folds (flagged,
// never deleted). An empty store creates freely: the first key is the
// operator's own hand; afterwards creation names an existing key.
package auth

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"time"
)

// KeyRe pins the key shape law; KidRe the public handle law.
var KeyRe = regexp.MustCompile(`^atl_[0-9a-f]{32}$`)
var KidRe = regexp.MustCompile(`^k-[0-9a-f]{8}$`)

// Iters and Domain pin the KDF (cutter reproduces this byte-for-byte).
const Iters = 210000
const Domain = "atlas-auth-v1"

// Key is one stored credential (hash only — the secret never persists).
type Key struct {
	ID       string   `json:"id"`
	Name     string   `json:"name"`
	Hash     string   `json:"hash"`
	Salt     string   `json:"salt"`
	Tenants  []string `json:"tenants"`
	Created  string   `json:"created"`
	Revoked  string   `json:"revoked,omitempty"`
}

type store struct {
	Keys []Key `json:"keys"`
}

func authPath(home string) string { return filepath.Join(home, "state", "auth.json") }
func auditPath(home string) string { return filepath.Join(home, "state", "auth_audit.jsonl") }

// KDF stretches a key with its salt: HMAC-SHA256 keyed by salt over the
// domain-bound key, iterated. Deterministic; verified by recompute.
func KDF(keyHex, saltHex string) (string, error) {
	salt, err := hex.DecodeString(saltHex)
	if err != nil {
		return "", err
	}
	mac := hmac.New(sha256.New, salt)
	mac.Write([]byte(Domain + keyHex))
	sum := mac.Sum(nil)
	for i := 1; i < Iters; i++ {
		mac = hmac.New(sha256.New, salt)
		mac.Write(sum)
		sum = mac.Sum(nil)
	}
	return hex.EncodeToString(sum), nil
}

func randHex(n int) (string, error) {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

func load(home string) (store, error) {
	var s store
	b, err := os.ReadFile(authPath(home))
	if err != nil {
		if os.IsNotExist(err) {
			return s, nil
		}
		return s, err
	}
	if err := json.Unmarshal(b, &s); err != nil {
		return s, err
	}
	return s, nil
}

func save(home string, s store) error {
	if err := os.MkdirAll(filepath.Join(home, "state"), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	tmp := authPath(home) + ".tmp"
	if err := os.WriteFile(tmp, append(b, '\n'), 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, authPath(home))
}

func audit(home, action, kid, tenant, by string) error {
	if err := os.MkdirAll(filepath.Join(home, "state"), 0o755); err != nil {
		return err
	}
	b, err := json.Marshal(map[string]any{
		"ts": time.Now().UTC().Format(time.RFC3339), "action": action,
		"key_id": kid, "tenant": tenant, "by": by,
	})
	if err != nil {
		return err
	}
	f, err := os.OpenFile(auditPath(home), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.WriteString(string(b) + "\n")
	return err
}

// Empty reports whether a store holds no keys (bootstrap open).
func Empty(home string) bool {
	s, err := load(home)
	if err != nil {
		return true
	}
	for _, k := range s.Keys {
		if k.Revoked == "" {
			return false
		}
	}
	return true
}

// Create mints a key. Plaintext returns once, in this answer, never again.
func Create(home, name string, tenants []string, by string) (string, Key, error) {
	var zero Key
	if name == "" {
		return "", zero, fmt.Errorf("auth needs a name for the key — unnamed keys are not minted")
	}
	secret, err := randHex(16)
	if err != nil {
		return "", zero, err
	}
	kid, err := randHex(4)
	if err != nil {
		return "", zero, err
	}
	salt, err := randHex(16)
	if err != nil {
		return "", zero, err
	}
	key := "atl_" + secret
	hash, err := KDF(key, salt)
	if err != nil {
		return "", zero, err
	}
	s, err := load(home)
	if err != nil {
		return "", zero, err
	}
	rec := Key{ID: "k-" + kid, Name: name, Hash: hash, Salt: salt,
		Tenants: append([]string{}, tenants...),
		Created: time.Now().UTC().Format(time.RFC3339)}
	s.Keys = append(s.Keys, rec)
	if err := save(home, s); err != nil {
		return "", zero, err
	}
	_ = audit(home, "create", rec.ID, stringsJoin(tenants), by)
	return key, rec, nil
}

// Verify recomputes every live key and compares constant-time.
func Verify(home, key string) (Key, error) {
	var zero Key
	if !KeyRe.MatchString(key) {
		return zero, fmt.Errorf("refused: not a key")
	}
	s, err := load(home)
	if err != nil {
		return zero, err
	}
	for _, k := range s.Keys {
		if k.Revoked != "" {
			continue
		}
		hash, err := KDF(key, k.Salt)
		if err != nil {
			continue
		}
		if len(hash) == len(k.Hash) && subtle.ConstantTimeCompare([]byte(hash), []byte(k.Hash)) == 1 {
			return k, nil
		}
	}
	return zero, fmt.Errorf("refused: unknown or revoked key")
}

// List returns live keys with hashes withheld (presence, never secrets).
func List(home string) []Key {
	s, err := load(home)
	if err != nil {
		return nil
	}
	var out []Key
	for _, k := range s.Keys {
		if k.Revoked != "" {
			continue
		}
		k.Hash, k.Salt = "", ""
		out = append(out, k)
	}
	return out
}

// Revoke folds a key (flagged, kept for the audit trail).
func Revoke(home, id, by string) error {
	s, err := load(home)
	if err != nil {
		return err
	}
	for i, k := range s.Keys {
		if k.ID == id && k.Revoked == "" {
			s.Keys[i].Revoked = time.Now().UTC().Format(time.RFC3339)
			if err := save(home, s); err != nil {
				return err
			}
			return audit(home, "revoke", id, stringsJoin(k.Tenants), by)
		}
	}
	return fmt.Errorf("refused: no live key %q", id)
}

// ScopeOK reports whether a key's tenants carry the requested project.
// "*" carries every tenant (the operator's key).
func ScopeOK(tenants []string, request string) bool {
	for _, t := range tenants {
		if t == "*" || t == request {
			return true
		}
	}
	return false
}

func stringsJoin(ss []string) string {
	out := ""
	for i, s := range ss {
		if i > 0 {
			out += ","
		}
		out += s
	}
	return out
}
