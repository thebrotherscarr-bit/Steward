// Package main is atlas-door: one plain page over loopback (D2-02/D2-03),
// ported behavior-for-behavior from Steward's door.py.
//
// One page: a search box, the answer with receipts, open work, recent
// visits, one badge (green whole / red naming the break), and two forms so
// the crew can log a visit or open a work order one-thumbed. Writes go only
// through `atlas trade` (SPEC_SEAM subprocess contract, like verify_chain);
// reads fold the JSONL books directly, with work-order status/cost/vendor
// parsed from `list all` (sqlite stays behind the Rust seam by law).
//
// Two stated substitutions, both named for the gate:
//  1. The oracle binds all interfaces (shop wifi); atlas-door binds
//     LOOPBACK by default. --bind 0.0.0.0 is the operator's network
//     decision, never the binary's.
//  2. Search receipts for work orders are audit-seal hashes (the chain
//     witness), where the oracle shows the opened date. Stronger receipt,
//     same line.
package main

import (
	_ "embed"
	"flag"
	"fmt"
	"os"
	"strings"
)

//go:embed VERSION
var versionFile string

// Version answers --version with the stone tag.
func Version() string { return strings.TrimSpace(versionFile) }

const describe = "atlas-door — D2 door: search the trade record with receipts, " +
	"badge green/red from the chains themselves, crew forms write chained " +
	"entries. Serves loopback; never sends."

func main() {
	os.Exit(run())
}

func run() int {
	fs := flag.NewFlagSet("atlas-door", flag.ContinueOnError)
	showProve := fs.Bool("prove", false, "run the shipped prove battery")
	showDesc := fs.Bool("describe", false, "describe this binary")
	showVer := fs.Bool("version", false, "print the stone-tagged version")
	port := fs.Int("port", 8080, "port to serve (SPEC_COMMANDS: never moves at cutover)")
	bind := fs.String("bind", "127.0.0.1", "interface to bind (loopback default; wider is the operator's call)")
	ops := fs.String("ops", "state/ops", "trade ops ground")
	atlasBin := fs.String("atlas-bin", "", "atlas binary (default: built tree or PATH)")
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
	if fs.NArg() > 0 && fs.Arg(0) == "prove" {
		return runProve()
	}
	bin := *atlasBin
	if bin == "" {
		bin = findAtlas()
	}
	d := NewDoor(*ops, bin)
	return serve(*bind, *port, d)
}
