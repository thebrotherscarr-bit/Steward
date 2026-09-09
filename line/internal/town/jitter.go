// Jitter: flow's randomized cadence (town.py _draw, ported).
//
// Live draws come from crypto/rand — the SystemRandom grade the oracle
// insists on (never a seeded PRNG at runtime). Seeded draws exist for one
// purpose: hermetic prove statistics. A backwards window is refused.
package town

import (
	"crypto/rand"
	"encoding/binary"
	"fmt"
	"math"
	mrand "math/rand"
)

// LiveDraw returns one pause in [lo, hi] from OS entropy.
func LiveDraw(lo, hi float64) (float64, error) {
	if hi < lo {
		return 0, fmt.Errorf("the window is backwards; give min then max")
	}
	if hi == lo {
		return lo, nil
	}
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		return 0, fmt.Errorf("no OS entropy to draw from: %s", err)
	}
	u := float64(binary.BigEndian.Uint64(b[:])) / float64(math.MaxUint64)
	return lo + u*(hi-lo), nil
}

// SeededDraws returns n draws from a seeded source — prove statistics only.
func SeededDraws(seed int64, n int, lo, hi float64) []float64 {
	r := mrand.New(mrand.NewSource(seed))
	out := make([]float64, n)
	for i := range out {
		out[i] = lo + r.Float64()*(hi-lo)
	}
	return out
}
