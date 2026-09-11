// atlas-mcp -- THE LINE: the multi-tenant MCP door to the whole estate.
//
// Genesis law (operator, 2026-08-25): one server, ALL projects. Tenants
// are carried by name; every tool call names its ground; unknown projects
// refuse by name.
//
// 2026-08-27: neiro is the ONLY auto-carry tenant (Home from NEIRO_HOME, or
// the documented default). atlas is NOT auto-carried -- its tenant identity
// is deferred to the build plan. Every other tenant (manjuel, agents, an
// atlas tenant when defined) is added by tag: --tenant name=path, and an
// engine wired with --engine name=cmd.
package main

import (
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"

	_ "embed"

	"atlas/line/internal/ground"
	"atlas/line/internal/httpserver"
	"atlas/line/internal/protocol"
	"atlas/line/internal/tenant"
	"atlas/line/internal/tools"
)

//go:embed VERSION
var versionFile string

func Version() string { return strings.TrimSpace(versionFile) }

const INSTRUCTIONS = `You are a seat at the atlas household. state = fold(record):
nothing is deleted; append and supersede. Propose, never dispose —
can_approve is false in every declaration, and approval lives in the
operator's hand alone. This server carries MANY projects: name the project
you mean on every call; strangers get nothing.`

// neiroDefaultHome is the documented fallback when NEIRO_HOME is unset. The
// operator sets NEIRO_HOME to the estate ground that carries neiro's record;
// an empty default means neiro is only carried when NEIRO_HOME is provided.
const neiroDefaultHome = ""

func main() {
	var (
		prove     = flag.Bool("prove", false, "hermetic strokes; exit 0 = green")
		describe  = flag.Bool("describe", false, "what this is")
		showVer   = flag.Bool("version", false, "print the stone-tagged version")
		atlasBin  = flag.String("atlas-bin", "atlas", "path to the Rust spine binary")
		defaultPj = flag.String("default-project", "", "default tenant name")
		httpAddr  = flag.String("http", "", "HTTP bind address (e.g. :8090); empty = stdio mode")
		authOn    = flag.Bool("auth", false, "demand bearer keys on /rpc + /chat/stream (N6)")
		authSvc   = flag.String("auth-service", "", "same-computer service wire (or ATLAS_SERVICE)")
		coreCmd   = flag.String("manjuel", "", "the command that runs Manjuel, e.g. `python C:\\...\\manjuel.py`; --headless --ground are appended by THE LINE")
	)
	tenants := map[string]string{}
	flag.Func("tenant", "carry a project as name=path (repeatable)", func(v string) error {
		parts := strings.SplitN(v, "=", 2)
		if len(parts) != 2 {
			return fmt.Errorf("--tenant wants name=path")
		}
		tenants[strings.ToLower(parts[0])] = parts[1]
		return nil
	})
	engineMap := map[string]string{}
	flag.Func("engine", "wire an ask_steward engine for a tenant: name=cmd (repeatable)", func(v string) error {
		parts := strings.SplitN(v, "=", 2)
		if len(parts) != 2 {
			return fmt.Errorf("--engine wants name=cmd")
		}
		engineMap[strings.ToLower(parts[0])] = parts[1]
		return nil
	})
	flag.Parse()
	if flag.NArg() > 0 {
		fatal(fmt.Errorf("%q is not a landed command", flag.Arg(0)))
	}

	if *showVer {
		fmt.Println(Version())
		return
	}

	if *describe {
		fmt.Println("atlas-mcp " + Version() + " - THE LINE: multi-tenant MCP door; " +
			"all of the estate, every project first-class")
		return
	}

	reg := tenant.NewRegistry()
	for _, k := range sortedKeys(tenants) {
		if err := reg.Add(k, tenants[k]); err != nil {
			fatal(err)
		}
	}

	// neiro is the only auto-carry tenant.
	neiroHome := os.Getenv("NEIRO_HOME")
	if neiroHome == "" {
		neiroHome = neiroDefaultHome
	}
	if neiroHome != "" {
		if !reg.Has("neiro") {
			if err := reg.Add("neiro", neiroHome); err != nil {
				fatal(err)
			}
		}
	} else {
		fmt.Fprintln(os.Stderr, "note: NEIRO_HOME not set -- neiro tenant not auto-carried")
	}

	// GROUND DETECTION (operator, 2026-08-27: "whenever I open an opencode
	// session anywhere on my computer it reads the dir, finds the agent file,
	// finds the .us"). The door is registered ONCE, globally; it learns where
	// it is standing instead of being told. A tenant named on the command line
	// still wins -- explicit beats detected, always.
	//
	// The per-tree MCP ruling of the same day stands on its reason: the bug was
	// one global server injecting Steward 1.0's wall everywhere. Detection
	// removes that at the root, because the law served is the law of the ground
	// the seat is actually in.
	if wd, err := os.Getwd(); err == nil {
		if here, ok := ground.Detect(wd); ok {
			if !reg.Has(here.Name) {
				if err := reg.Add(here.Name, here.Home); err != nil {
					fatal(err)
				}
			}
			// SEE THE TOWN. Carry the detected ground's neighbours too, so
			// muster and state_matrix answer across the estate from wherever
			// the seat opened -- not across whatever one launch happened to
			// name. One level up, one level across; the attic is skipped
			// because folded copies are history, not claim.
			for _, sib := range ground.Siblings(filepath.Dir(here.Home)) {
				if !reg.Has(sib.Name) {
					if err := reg.Add(sib.Name, sib.Home); err != nil {
						fatal(err)
					}
				}
			}
			// The ground underfoot answers unnamed calls, unless the operator
			// pinned one with --default-project.
			if *defaultPj == "" {
				if err := reg.SetDefault(here.Name); err != nil {
					fatal(err)
				}
			}
			// NAME THEM. This said "carried %d" and nothing else, and a count
			// cannot be checked against intent — two is two whether the two
			// are the ones you meant or not.
			//
			// Earned 2026-09-11. The door was started from the ground root, so
			// Detect resolved the ground to `research` and Siblings() read the
			// parent of THAT -- the desktop -- carrying every neighbour with an
			// AGENTS.md. A world outside the estate rode in, the dashboard read
			// its git state, and the first anyone knew was a badge reading
			// 83,303. Every line needed to catch that at boot was already here
			// except the names.
			fmt.Fprintf(os.Stderr,
				"ground: %s (%s via %s); carrying %d: %s\n",
				here.Name, here.Home, here.Via,
				len(reg.Names()), strings.Join(reg.Names(), ", "))
		} else {
			fmt.Fprintln(os.Stderr,
				"note: no ground detected from the working directory "+
					"(no .us module declaration, no AGENTS.md up the tree)")
		}
	}

	// Wire engines (ask_steward) for tagged tenants.
	for name, cmd := range engineMap {
		if err := reg.SetEngine(name, cmd); err != nil {
			fatal(err)
		}
	}

	if *defaultPj != "" {
		if err := reg.SetDefault(*defaultPj); err != nil {
			fatal(err)
		}
	}

	if *prove {
		os.Exit(runProve())
	}

	surface := tools.Build(reg, tools.Options{AtlasBin: *atlasBin, CoreCmd: *coreCmd})

	// EVERY ENGINE IS REAPED ON THE WAY DOWN. An orphan holds its world's
	// sitting open, and an open sitting is what RULE 9 forbids editing under
	// and what the release gate refuses a tag over (SPEC_CONTROL_CENTER 12.3).
	stopping := make(chan os.Signal, 1)
	signal.Notify(stopping, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-stopping
		fmt.Fprintln(os.Stderr, "reaping open engines before exit...")
		tools.Engines().CloseAll()
		os.Exit(0)
	}()
	defer tools.Engines().CloseAll()

	if *httpAddr != "" {
		svc := *authSvc
		if svc == "" {
			svc = os.Getenv("ATLAS_SERVICE")
		}
		srv := httpserver.New(
			protocol.ServerInfo{Name: "atlas-mcp", Version: Version()},
			INSTRUCTIONS, surface, reg,
			httpserver.Auth{On: *authOn, Service: svc},
		)
		fmt.Fprintf(os.Stderr, "atlas-mcp %s listening on %s (auth=%v)\n", Version(), *httpAddr, *authOn)
		if err := srv.ListenAndServe(*httpAddr); err != nil {
			fatal(err)
		}
		return
	}

	err := protocol.Serve(os.Stdin, os.Stdout,
		protocol.ServerInfo{Name: "atlas-mcp", Version: Version()},
		INSTRUCTIONS, surface, reg)
	if err != nil && err != io.EOF {
		fatal(err)
	}
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, "refused:", err)
	os.Exit(2)
}

func sortedKeys(m map[string]string) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	for i := 1; i < len(out); i++ {
		for j := i; j > 0 && out[j] < out[j-1]; j-- {
			out[j], out[j-1] = out[j-1], out[j]
		}
	}
	return out
}
