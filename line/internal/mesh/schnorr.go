// Package mesh is THE MESH: the `.us` messaging protocol (SPEC_US_MESH,
// stone B2). It opens with signing: secp256k1 Schnorr hand-rolled in Go
// (zero crates, stdlib only), byte-for-byte compatible with the estate's
// `jesster.py` — Go stdlib has no secp256k1 and no Schnorr, so there is no
// other lawful way. Acceptance is differential (B2-07): the golden vectors
// in tests/fixtures/schnorr_vectors.json are cut from the Python oracle,
// and this package must byte-match them in both directions.
package mesh

import (
	"crypto/sha256"
	"errors"
	"math/big"
)

var (
	// secp256k1 field and order, the world's constants (jesster.py _P/_N).
	pField = hexInt("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F")
	curveN = hexInt("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141")
	gx     = hexInt("79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798")
	gy     = hexInt("483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8")

	big0 = big.NewInt(0)
	big1 = big.NewInt(1)
	big2 = big.NewInt(2)
	big3 = big.NewInt(3)
)

func hexInt(s string) *big.Int {
	n, ok := new(big.Int).SetString(s, 16)
	if !ok {
		panic("mesh: bad curve constant")
	}
	return n
}

// point is affine secp256k1; inf marks the point at infinity.
type point struct {
	x, y *big.Int
	inf  bool
}

func inf() point { return point{inf: true} }

func mod(a *big.Int) *big.Int {
	n := new(big.Int).Mod(a, pField)
	if n.Sign() < 0 {
		n.Add(n, pField)
	}
	return n
}

func inv(a *big.Int) *big.Int {
	return new(big.Int).Exp(a, new(big.Int).Sub(pField, big2), pField)
}

// dbl follows jesster.py _dbl, in affine form.
func dbl(pt point) point {
	if pt.inf || pt.y.Sign() == 0 {
		return inf()
	}
	// s = 3x^2 / 2y
	s := mod(new(big.Int).Mul(mod(new(big.Int).Mul(big3, new(big.Int).Mul(pt.x, pt.x))),
		inv(mod(new(big.Int).Mul(big2, pt.y)))))
	x3 := mod(new(big.Int).Sub(new(big.Int).Mul(s, s), new(big.Int).Mul(big2, pt.x)))
	y3 := mod(new(big.Int).Sub(new(big.Int).Mul(s, new(big.Int).Sub(pt.x, x3)), pt.y))
	return point{x: x3, y: y3}
}

// add follows jesster.py _add, in affine form.
func add(p1, p2 point) point {
	if p1.inf {
		return p2
	}
	if p2.inf {
		return p1
	}
	if p1.x.Cmp(p2.x) == 0 {
		if p1.y.Cmp(p2.y) == 0 {
			return dbl(p1)
		}
		return inf()
	}
	s := mod(new(big.Int).Mul(mod(new(big.Int).Sub(p2.y, p1.y)),
		inv(mod(new(big.Int).Sub(p2.x, p1.x)))))
	x3 := mod(new(big.Int).Sub(new(big.Int).Sub(new(big.Int).Mul(s, s), p1.x), p2.x))
	y3 := mod(new(big.Int).Sub(new(big.Int).Mul(s, new(big.Int).Sub(p1.x, x3)), p1.y))
	return point{x: x3, y: y3}
}

// mul is double-and-add (jesster.py _mul, MSB-first equivalent).
func mul(k *big.Int, pt point) point {
	kk := new(big.Int).Mod(k, curveN)
	if kk.Sign() == 0 || pt.inf {
		return inf()
	}
	acc := inf()
	for i := kk.BitLen() - 1; i >= 0; i-- {
		acc = dbl(acc)
		if kk.Bit(i) == 1 {
			acc = add(acc, pt)
		}
	}
	return acc
}

func generator() point { return point{x: new(big.Int).Set(gx), y: new(big.Int).Set(gy)} }

// Serialize: 64 bytes x || y (jesster.py _ser; uncompressed on purpose).
func ser(pt point) []byte {
	out := make([]byte, 64)
	if pt.inf {
		return out // callers treat zero as infinity; never a valid key
	}
	xb := pt.x.Bytes()
	yb := pt.y.Bytes()
	copy(out[32-len(xb):32], xb)
	copy(out[64-len(yb):], yb)
	return out
}

func deser(b []byte) (point, error) {
	if len(b) != 64 {
		return inf(), errors.New("a point is 64 bytes")
	}
	x := new(big.Int).SetBytes(b[:32])
	y := new(big.Int).SetBytes(b[32:])
	if x.Sign() == 0 && y.Sign() == 0 {
		return inf(), nil
	}
	return point{x: x, y: y}, nil
}

// OnCurve reports y^2 == x^3 + 7 (mod p) — jesster.py on_curve.
func OnCurve(pt point) bool {
	if pt.inf {
		return false
	}
	x, y := pt.x, pt.y
	lhs := mod(new(big.Int).Mul(y, y))
	rhs := mod(new(big.Int).Add(mod(new(big.Int).Mul(mod(new(big.Int).Mul(x, x)), x)), big.NewInt(7)))
	return lhs.Cmp(rhs) == 0
}

func hashParts(parts ...[]byte) []byte {
	h := sha256.New()
	for _, p := range parts {
		h.Write(p)
	}
	return h.Sum(nil)
}

func modN(b []byte) *big.Int {
	return new(big.Int).Mod(new(big.Int).SetBytes(b), curveN)
}

// Pub returns the verifying key for a private scalar (jesster identity/session).
func Pub(priv *big.Int) []byte {
	d := new(big.Int).Mod(priv, curveN)
	if d.Sign() == 0 {
		d = big.NewInt(1)
	}
	return ser(mul(d, generator()))
}

// Mark is sha256(pub)[:16] — the weld inside payload (jesster.py mark).
func Mark(pub []byte) string {
	h := sha256.Sum256(pub)
	const hexd = "0123456789abcdef"
	out := make([]byte, 16)
	for i := 0; i < 8; i++ {
		out[2*i] = hexd[h[i]>>4]
		out[2*i+1] = hexd[h[i]&0xf]
	}
	return string(out)
}

// Sign is deterministic Schnorr: sig = R(64) || s(32), jesster.py sign.
func Sign(priv *big.Int, message []byte) []byte {
	d := new(big.Int).Mod(priv, curveN)
	if d.Sign() == 0 {
		d = big.NewInt(1)
	}
	dbytes := pad32(d.Bytes())
	k := modN(hashParts([]byte("JESSTER|nonce|"), dbytes, []byte("|"), message))
	if k.Sign() == 0 {
		k = big.NewInt(1)
	}
	rb := ser(mul(k, generator()))
	pb := ser(mul(d, generator()))
	e := modN(hashParts([]byte("JESSTER|chal|"), rb, pb, message))
	s := new(big.Int).Mod(new(big.Int).Add(k, new(big.Int).Mul(e, d)), curveN)
	return append(rb, pad32(s.Bytes())...)
}

// Verify checks s*G == R + e*P, jesster.py verify. Anything malformed is
// false, never an error — a bad hand is a refusal, not a crash.
func Verify(pub, message, sig []byte) bool {
	if len(sig) != 96 || len(pub) != 64 {
		return false
	}
	R, err := deser(sig[:64])
	if err != nil || !OnCurve(R) {
		return false
	}
	P, err := deser(pub)
	if err != nil || !OnCurve(P) {
		return false
	}
	s := new(big.Int).SetBytes(sig[64:])
	if s.Cmp(curveN) >= 0 {
		return false
	}
	e := modN(hashParts([]byte("JESSTER|chal|"), sig[:64], pub, message))
	left := mul(s, generator())
	right := add(R, mul(e, P))
	if left.inf || right.inf {
		return left.inf && right.inf
	}
	return left.x.Cmp(right.x) == 0 && left.y.Cmp(right.y) == 0
}

func pad32(b []byte) []byte {
	if len(b) >= 32 {
		return b[len(b)-32:]
	}
	out := make([]byte, 32)
	copy(out[32-len(b):], b)
	return out
}
