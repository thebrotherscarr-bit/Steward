// Package vram is N3's planner: VRAM arithmetic pinned by
// tools/cut_rack_plan_vectors.py. The fixture file is the oracle; this
// package must reproduce every vector. No live Ollama here — pure math.
package rack

import (
	"fmt"
	"sort"
	"strings"
)

// Planner v1 contract (byte-pinned with the cutter — change both or neither).
const (
	VramBudget    = int64(15_000_000_000)
	GraphOverhead = int64(1_500_000_000)
	CtxDefault    = 4096
)

var kvPerToken = map[string]int64{
	"scout": 200_000,
	"voice": 500_000,
	"mind":  1_000_000,
}

// Footprint sizes one resident model: weights + graph + KV cache.
func Footprint(size int64) int64 {
	tier := TierOf(size)
	kv, ok := kvPerToken[tier]
	if !ok {
		kv = kvPerToken["voice"]
	}
	return size + GraphOverhead + int64(CtxDefault)*kv
}

// PlanVerdict is FITS (fits the card) or OVER (evictions needed).
type PlanVerdict struct {
	Verdict string
	Total   int64
	Budget  int64
	Evict   []string
}

// Plan sums footprints vs the budget; evictions largest-first.
func Plan(models []Voice) PlanVerdict {
	type fp struct {
		name string
		n    int64
	}
	var fps []fp
	var total int64
	for _, m := range models {
		n := Footprint(m.Size)
		fps = append(fps, fp{m.Name, n})
		total += n
	}
	if total <= VramBudget {
		return PlanVerdict{"FITS", total, VramBudget, nil}
	}
	sort.Slice(fps, func(i, j int) bool { return fps[i].n > fps[j].n })
	var evict []string
	var freed int64
	for _, f := range fps {
		freed += f.n
		evict = append(evict, f.name)
		if total-freed <= VramBudget {
			break
		}
	}
	return PlanVerdict{"OVER", total, VramBudget, evict}
}

// RenderPlan prints the verdict deterministically (GB with 2 decimals).
func RenderPlan(models []Voice, v PlanVerdict) string {
	var b strings.Builder
	fmt.Fprintf(&b, "VRAM PLAN — %s · total %.2fGB / budget %.2fGB\n",
		v.Verdict, float64(v.Total)/1e9, float64(v.Budget)/1e9)
	rows := append([]Voice(nil), models...)
	sort.Slice(rows, func(i, j int) bool { return rows[i].Name < rows[j].Name })
	for _, m := range rows {
		fmt.Fprintf(&b, "  - %s · %.2fGB weights · tier %s · footprint %.2fGB\n",
			m.Name, float64(m.Size)/1e9, TierOf(m.Size), float64(Footprint(m.Size))/1e9)
	}
	if v.Verdict == "OVER" {
		fmt.Fprintf(&b, "  evict to fit: %s\n", strings.Join(v.Evict, ", "))
	}
	return b.String()
}
