// Metrics (N6): Prometheus-text counters for the SaaS lineup. Hand-rolled
// exposition (no client library): atlas_http_requests{path} plus uptime
// and version gauges. Paths are route shapes, never query strings —
// session ids, keys and prompts stay out of cardinality.
package handlers

import (
	"fmt"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"
)

var (
	metricMu    sync.Mutex
	metricHits  = map[string]int64{}
	metricStart = time.Now()
)

// Count records one request by route shape.
func (h *Handlers) Count(route string) {
	if i := strings.Index(route, "?"); i >= 0 {
		route = route[:i]
	}
	metricMu.Lock()
	metricHits[route]++
	metricMu.Unlock()
}

// Metrics exposes the counters.
func (h *Handlers) Metrics(w http.ResponseWriter, r *http.Request) {
	metricMu.Lock()
	defer metricMu.Unlock()
	keys := []string{}
	for k := range metricHits {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var b strings.Builder
	b.WriteString("# HELP atlas_http_requests requests by route\n# TYPE atlas_http_requests counter\n")
	for _, k := range keys {
		fmt.Fprintf(&b, "atlas_http_requests{route=%q} %d\n", k, metricHits[k])
	}
	fmt.Fprintf(&b, "# HELP atlas_uptime_seconds webapp uptime\n# TYPE atlas_uptime_seconds gauge\n")
	fmt.Fprintf(&b, "atlas_uptime_seconds %d\n", int64(time.Since(metricStart).Seconds()))
	b.WriteString("# HELP atlas_server_info build info\n# TYPE atlas_server_info gauge\n")
	b.WriteString("atlas_server_info{server=\"atlas-webapp\",version=\"0.1.2\"} 1\n")
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	fmt.Fprint(w, b.String())
}
