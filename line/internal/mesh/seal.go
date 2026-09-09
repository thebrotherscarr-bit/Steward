// Seal: confidentiality by default (SPEC_US_MESH §5).
//
// The chain carries ct + commitment, never plaintext or salt. The salt lives
// in the deciphering ledger beside the estate; the reveal recomputes
// H(salt || plaintext) and compares.
//
// HONESTY CLAUSE (read before trusting): the ct stream cipher below is
// hand-rolled SHA-256-CTR-shaped keystream, stdlib-only by standing law. Like
// jesster's hand-rolled Schnorr it is auditable end to end and NOT a validated
// module. The seam is Seal/Open: a certified backend replaces this pair and
// nothing else. The COMMITMENT (salted SHA-256) is standard and carries the
// verifiable-seal property regardless of the cipher.
package mesh

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"math/big"
	"os"
	"strings"
)

// Modes: sealed hides, open states.
const (
	ModeSealed = "sealed"
	ModeOpen   = "open"
)

// KeyFromEnv loads one actor's 32-byte key from the process environment
// (MESH_KEY_<ACTOR>, 64 hex chars). Keys live in a local .env, never the repo,
// never on disk otherwise. Absent or malformed is an honest refusal — there
// is no default key, and a silently weak key is worse than none.
func KeyFromEnv(actor string) ([]byte, error) {
	name := "MESH_KEY_" + envName(actor)
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return nil, fmt.Errorf("no key for actor %q in process env (%s unset): "+
			"the backend is keyed per agent — key it before posting sealed", actor, name)
	}
	k, err := hex.DecodeString(raw)
	if err != nil || len(k) != 32 {
		return nil, fmt.Errorf("key for actor %q malformed (%s must be 64 hex chars)", actor, name)
	}
	return k, nil
}

func envName(actor string) string {
	var sb strings.Builder
	for _, r := range strings.ToUpper(actor) {
		if (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') {
			sb.WriteRune(r)
		} else {
			sb.WriteByte('_')
		}
	}
	return sb.String()
}

// SealKey derives the encryption key from the actor's env secret
// (domain-separated from the signing scalar).
func SealKey(secret []byte) []byte {
	h := sha256.New()
	h.Write([]byte("MESH|seal|"))
	h.Write(secret)
	return h.Sum(nil)
}

// PubForSecret derives the enrollment pub for a 32-byte env secret — the
// operator flow: pick a secret, publish its pub via mesh_enroll, keep the
// secret in the local .env as MESH_KEY_<actor>. The secret itself never
// leaves the operator's hand.
func PubForSecret(secret []byte) (string, error) {
	if len(secret) != 32 {
		return "", fmt.Errorf("a mesh secret is 32 bytes")
	}
	sh := sha256.New()
	sh.Write([]byte("MESH|sign|"))
	sh.Write(secret)
	sc := modN(sh.Sum(nil))
	return hex.EncodeToString(Pub(new(big.Int).SetBytes(sc.Bytes()))), nil
}
func keystream(key, salt []byte, n int) []byte {
	out := make([]byte, 0, n)
	var ctr uint64
	for len(out) < n {
		var cb [8]byte
		binary.BigEndian.PutUint64(cb[:], ctr)
		h := sha256.New()
		h.Write(key)
		h.Write(salt)
		h.Write(cb[:])
		out = append(out, h.Sum(nil)...)
		ctr++
	}
	return out[:n]
}

func xorStream(key, salt, in []byte) []byte {
	ks := keystream(key, salt, len(in))
	out := make([]byte, len(in))
	for i := range in {
		out[i] = in[i] ^ ks[i]
	}
	return out
}

// Seal encrypts and commits: salt (32B random) + ct hex + commitment
// H(salt || plaintext). The salt goes to the deciphering ledger, never the
// chain.
func Seal(key, plaintext []byte) (saltHex, ctHex, commitment string, err error) {
	salt := make([]byte, 32)
	if _, err = rand.Read(salt); err != nil {
		return "", "", "", fmt.Errorf("no randomness to seal with: %s", err)
	}
	ct := xorStream(key, salt, plaintext)
	commit := sha256.Sum256(append(append([]byte(nil), salt...), plaintext...))
	return hex.EncodeToString(salt), hex.EncodeToString(ct),
		hex.EncodeToString(commit[:]), nil
}

// Open decrypts and VERIFIES the commitment. A mismatch is a refusal, not
// best-effort plaintext.
func Open(key []byte, saltHex, ctHex, commitment string) ([]byte, error) {
	salt, err1 := hex.DecodeString(saltHex)
	ct, err2 := hex.DecodeString(ctHex)
	if err1 != nil || err2 != nil || len(salt) != 32 {
		return nil, fmt.Errorf("sealed envelope malformed: salt/ct not 32B/hex")
	}
	pt := xorStream(key, salt, ct)
	commit := sha256.Sum256(append(append([]byte(nil), salt...), pt...))
	if hex.EncodeToString(commit[:]) != commitment {
		return nil, fmt.Errorf("REFUSED: commitment mismatch — the reveal does not verify")
	}
	return pt, nil
}

// CommitOf recomputes H(salt || plaintext) for ledger-side checks.
func CommitOf(salt, plaintext []byte) string {
	h := sha256.Sum256(append(append([]byte(nil), salt...), plaintext...))
	return hex.EncodeToString(h[:])
}
