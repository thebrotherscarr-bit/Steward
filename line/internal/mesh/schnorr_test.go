// Differential prove for B2-07: every golden cut from jesster.py must hold
// in Go. Sign-equality is the byte-match (Go signs exactly what Python
// signed); verify-accept/refuse proves the equation agrees, edges included.
package mesh

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"math/big"
	"os"
	"path/filepath"
	"strconv"
	"testing"
)

func sha256Of(b []byte) [32]byte { return sha256.Sum256(b) }

func itoa(n int64) string { return strconv.FormatInt(n, 10) }

type acceptCase struct {
	Priv     int64  `json:"priv"`
	Pub      string `json:"pub"`
	Msg      string `json:"msg"`
	Sig      string `json:"sig"`
	Verified bool   `json:"verified"`
}

type vector struct {
	ID     string         `json:"id"`
	OK     bool           `json:"ok"`
	Detail string         `json:"detail"`
	Priv   int64          `json:"priv"`
	Msg    string         `json:"msg"`
	Sig    string         `json:"sig"`
	Cases  []acceptCase   `json:"cases"`
	Cert   map[string]any `json:"cert"`
}

type goldens struct {
	Oracle struct {
		Sha256 string `json:"sha256"`
	} `json:"oracle"`
	Vectors []vector `json:"vectors"`
}

func loadGoldens(t *testing.T) goldens {
	t.Helper()
	p := filepath.Join("..", "..", "..", "tests", "fixtures", "schnorr_vectors.json")
	b, err := os.ReadFile(p)
	if err != nil {
		t.Fatalf("goldens missing: %s", err)
	}
	var g goldens
	if err := json.Unmarshal(b, &g); err != nil {
		t.Fatalf("goldens unparsable: %s", err)
	}
	byID := map[string]vector{}
	for _, v := range g.Vectors {
		byID[v.ID] = v
		if !v.OK {
			t.Fatalf("golden %q was cut failing — the oracle disagrees with itself", v.ID)
		}
	}
	if len(byID) != 9 {
		t.Fatalf("want 9 schnorr goldens, have %d", len(byID))
	}
	return g
}

func unhex(t *testing.T, s string) []byte {
	t.Helper()
	b, err := hex.DecodeString(s)
	if err != nil {
		t.Fatalf("bad hex in goldens: %s", err)
	}
	return b
}

func TestDifferential(t *testing.T) {
	g := loadGoldens(t)
	byID := map[string]vector{}
	for _, v := range g.Vectors {
		byID[v.ID] = v
	}

	// Determinism + byte-match: Go signs exactly the Python bytes.
	det := byID["determinism"]
	got := Sign(big.NewInt(det.Priv), unhex(t, det.Msg))
	if hex.EncodeToString(got) != det.Sig {
		t.Fatalf("determinism byte-mismatch:\n go %x\n py %s", got, det.Sig)
	}

	// Accept: every Python case verifies in Go, and Go re-signs identical bytes.
	acc := byID["verify-accept"]
	for i, c := range acc.Cases {
		pub, msg, sig := unhex(t, c.Pub), unhex(t, c.Msg), unhex(t, c.Sig)
		if !Verify(pub, msg, sig) {
			t.Fatalf("case %d (priv %d) rejected by Go, accepted by Python", i, c.Priv)
		}
		if resig := Sign(big.NewInt(c.Priv), msg); !bytes.Equal(resig, sig) {
			t.Fatalf("case %d (priv %d) sign byte-mismatch", i, c.Priv)
		}
		// Mark weld (B2-03): sha256(pub)[:16] hex — the identity half.
		h := sha256Of(pub)
		if Mark(pub) != hex.EncodeToString(h[:8]) {
			t.Fatalf("case %d (priv %d) mark unwelded", i, c.Priv)
		}
	}

	// Refusal edges: Go must refuse everything Python refuses.
	base := acc.Cases[1]
	pubB, msgB, sigB := unhex(t, base.Pub), unhex(t, base.Msg), unhex(t, base.Sig)
	if Verify(pubB, []byte("a different message"), sigB) {
		t.Fatal("wrong-message accepted")
	}
	flip := append([]byte(nil), sigB...)
	flip[10] ^= 0x01
	if Verify(pubB, msgB, flip) {
		t.Fatal("flipped-sig accepted")
	}
	n, _ := new(big.Int).SetString("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16)
	badS := append(append([]byte(nil), sigB[:64]...), pad32(n.Bytes())...)
	if Verify(pubB, msgB, badS) {
		t.Fatal("s-gte-n accepted")
	}
	if Verify(pubB, msgB, sigB[:95]) {
		t.Fatal("bad-length accepted")
	}
	if Verify(bytes.Repeat([]byte{0}, 64), msgB, sigB) {
		t.Fatal("infinity-pub accepted")
	}
	off := append(pad32(big.NewInt(1).Bytes()), pad32(big.NewInt(1).Bytes())...)
	if Verify(off, msgB, sigB) {
		t.Fatal("off-curve-pub accepted")
	}

	// Certify: identity vouches for the session under Go verify too;
	// the tampered session key fails under Go as it does in Python.
	// Python body: b"JESSTER|session|v%d|%s|%s" % (epoch, ipub, spub).
	cert := byID["certify"].Cert
	ipub := unhex(t, cert["identity_pub"].(string))
	spub := unhex(t, cert["session_pub"].(string))
	sig := unhex(t, cert["sig"].(string))
	epoch := int64(cert["epoch"].(float64))
	head := append([]byte("JESSTER|session|v"+itoa(epoch)+"|"), ipub...)
	head = append(head, '|')
	if !Verify(ipub, append(head, spub...), sig) {
		t.Fatal("certify body rejected")
	}
	tampered := append([]byte(nil), spub...)
	tampered[len(tampered)-1] ^= 0x01
	if Verify(ipub, append(head, tampered...), sig) {
		t.Fatal("tampered cert accepted")
	}
}
