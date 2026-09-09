// Command atlas-town is D1 Town: the beat that drafts REVIEW-gated trade
// tasks, flow with randomized cadence, story, look, and a shipped prove
// battery (SPEC_COMMANDS). Temp grounds in prove; the operator's live `beat`
// is the review gate.
//
// Verbs are beat/flow/story/look/prove. There is no resolve verb: closing,
// visiting, and clearing are the operator's hand, and they are absent here
// by construction, as approve/ascend are absent from THE LINE.
package main

import (
	_ "embed"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"atlas/line/internal/mesh"
	"atlas/line/internal/town"
)

//go:embed VERSION
var versionFile string

// Version answers --version with the stone tag.
func Version() string { return strings.TrimSpace(versionFile) }

const describe = "atlas-town — D1 Town: beat (one draft-and-work cycle), flow " +
	"(the beat running, randomized cadence), story (the mesh chronicle), look " +
	"(verdict + what is due), prove. Every return stops at REVIEW."

func homeDir(explicit string) string {
	if explicit != "" {
		return explicit
	}
	if h := os.Getenv("ATLAS_HOME"); h != "" {
		return h
	}
	return "."
}

func main() {
	os.Exit(run())
}

func run() int {
	fs := flag.NewFlagSet("atlas-town", flag.ContinueOnError)
	showProve := fs.Bool("prove", false, "run the shipped prove battery")
	showDesc := fs.Bool("describe", false, "describe this binary")
	showVer := fs.Bool("version", false, "print the stone-tagged version")
	home := fs.String("home", "", "atlas home (holds state/ops, state/board, state/mesh)")
	rounds := fs.Int("rounds", 0, "flow rounds (0 = run until interrupted)")
	if err := fs.Parse(os.Args[1:]); err != nil {
		return 2
	}
	if *showVer {
		fmt.Println(Version())
		return 0
	}
	if *showDesc {
		fmt.Println(describe)
		return 0
	}
	if *showProve {
		return runProve()
	}
	args := fs.Args()
	cmd := "beat"
	if len(args) > 0 {
		cmd = args[0]
	}
	rest := []string{}
	if len(args) > 1 {
		rest = args[1:]
	}
	h := homeDir(*home)
	switch cmd {
	case "beat":
		return cmdBeat(h)
	case "flow":
		return cmdFlow(h, rest, *rounds)
	case "story":
		return cmdStory(h, rest)
	case "look":
		return cmdLook(h)
	case "prove":
		return runProve()
	default:
		fmt.Println("atlas-town — beat | flow [min max] | story [hours] | look | prove")
		return 2
	}
}

func cmdBeat(h string) int {
	rep, err := town.Beat(opsDir(h), boardDir(h), time.Now())
	if err != nil {
		fmt.Printf("beat refused: %s\n", err)
		return 1
	}
	fmt.Printf("beat: issued %d, filed %d\n", rep.Issued, rep.Filed)
	for _, w := range rep.Worked {
		fmt.Printf("      · %s\n", firstLine(w))
	}
	for _, held := range rep.Held {
		fmt.Printf("      · held: %s\n", firstLine(held))
	}
	if rep.Issued == 0 && rep.Filed == 0 {
		fmt.Println("      a quiet town is an honest finding.")
	}
	return 0
}

func cmdFlow(h string, rest []string, rounds int) int {
	lo, hi := 300.0, 300.0
	if len(rest) > 0 {
		if _, err := fmt.Sscan(rest[0], &lo); err != nil {
			fmt.Printf("flow: bad min %q\n", rest[0])
			return 2
		}
		hi = lo
	}
	if len(rest) > 1 {
		if _, err := fmt.Sscan(rest[1], &hi); err != nil {
			fmt.Printf("flow: bad max %q\n", rest[1])
			return 2
		}
	}
	if hi < lo {
		fmt.Println("flow: the window is backwards; give min then max.")
		return 2
	}
	n := 0
	for {
		if err := func() int { return cmdBeat(h) }(); err != 0 {
			return err
		}
		n++
		if rounds > 0 && n >= rounds {
			return 0
		}
		pause, err := town.LiveDraw(lo, hi)
		if err != nil {
			fmt.Printf("flow refused: %s\n", err)
			return 1
		}
		time.Sleep(time.Duration(pause * float64(time.Second)))
	}
}

func cmdStory(h string, rest []string) int {
	hours := 24.0
	if len(rest) > 0 {
		if _, err := fmt.Sscan(rest[0], &hours); err != nil {
			fmt.Printf("story: bad hours %q\n", rest[0])
			return 2
		}
	}
	cutoff := time.Now().Add(-time.Duration(hours * float64(time.Hour)))
	results, err := mesh.Read(meshDir(h), "", 0, false)
	if err != nil {
		fmt.Printf("story refused: %s\n", err)
		return 1
	}
	shown := 0
	for _, r := range results {
		t, err := time.Parse(time.RFC3339, r.Entry.TS)
		if err != nil || t.Before(cutoff) {
			continue
		}
		face := r.Plaintext
		if face == "" {
			face = "(sealed)"
		}
		fmt.Printf("  %s  [%s/%s]  %s\n", r.Entry.TS, r.Entry.Kind, r.Entry.Actor, firstLine(face))
		shown++
	}
	if shown == 0 {
		fmt.Println("  the chronicle holds nothing for the window — a quiet town is an honest finding.")
	}
	return 0
}

func cmdLook(h string) int {
	v, err := mesh.Chain(meshDir(h))
	if err != nil {
		fmt.Printf("look refused: %s\n", err)
		return 1
	}
	fmt.Printf("mesh: %s — %s\n", v.Overall, v.Detail)
	wos := town.OpenWorkOrders(opsDir(h))
	fmt.Printf("open work orders: %d\n", len(wos))
	due := town.Candidates(opsDir(h), mustKnown(boardDir(h)), time.Now())
	for _, d := range due {
		fmt.Printf("  due: %s — %s\n", d.Key, d.Title)
	}
	if len(due) == 0 {
		fmt.Println("  nothing due — the ground is quiet.")
	}
	return 0
}

func mustKnown(board string) map[string]bool {
	known, err := town.OpenBoard(board).KnownKeys()
	if err != nil {
		return map[string]bool{}
	}
	return known
}

func opsDir(h string) string   { return filepath.Join(h, "state", "ops") }
func boardDir(h string) string { return filepath.Join(h, "state", "board") }
func meshDir(h string) string  { return filepath.Join(h, "state", "mesh") }

func firstLine(s string) string {
	if i := strings.Index(s, "\n"); i >= 0 {
		return s[:i]
	}
	if len(s) > 120 {
		return s[:120]
	}
	return s
}
