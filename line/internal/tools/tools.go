// Package tools defines the atlas-mcp surface. Genesis law: MULTI-TENANT —
// every tool takes an optional "project" argument naming its ground; the
// default tenant serves when absent. Forbidden verbs (approve, ascend,
// merge, commit, push, delete, reject, promote) are absent BY CONSTRUCTION:
// they appear nowhere in this table.
//
// 2026-08-27: the eight B1 read/ask/write tools are landed (manifest-
// resolved); the rack trio (rack_list/rack_ask/rack_open) stays honestly
// refusing until F1. ask_steward + remember serialize under one ask lock so
// concurrent calls never write a tenant's one hash chain at once.
package tools

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"atlas/line/internal/auth"
	"atlas/line/internal/chat"
	"atlas/line/internal/engine"
	"atlas/line/internal/flow"
	"atlas/line/internal/guard"
	"atlas/line/internal/mesh"
	"atlas/line/internal/orient"
	"atlas/line/internal/play"
	"atlas/line/internal/rack"
	"atlas/line/internal/team"
	"atlas/line/internal/tenant"
	"atlas/line/internal/town"
	"atlas/line/internal/trust"
	"atlas/line/internal/vc"
)

// ErrUnknownTool marks a name off the lawful surface.
var ErrUnknownTool = errors.New("unknown tool")

// askLock serializes the two writing tools (ask_steward wakes a tenant's
// engine which writes that project's ledger; remember appends to the memory
// file). One writer at a time, one chain.
var askLock sync.Mutex

type Fn func(t tenant.Tenant, args map[string]any) (string, error)

// Tier is what a tool needs BEYOND a tenant's directory. ADR-006 accepted
// 2026-09-11: the door is a product, and a product publishes what it requires.
//
// The zero value is TierCore, so a tool is CORE unless it says otherwise. That
// is deliberate — 75 of 78 tools are CORE, and making the common case free
// keeps the declaration honest instead of ceremonial. A tool that claims CORE
// and then reaches for the engine or the spine is caught by
// TestEveryCoreToolStandsAlone, not by a reviewer's memory.
type Tier int

const (
	// TierCore needs nothing but a directory. It must answer, or refuse for
	// a reason of its own, against ANY tenant on ANY machine — no engine
	// wired, no Rust binary built, no manjuel layout present.
	TierCore Tier = iota
	// TierSpine shells the Rust binary. May refuse when it is unbuilt, but
	// must name the binary and how to build it.
	TierSpine
	// TierEngine needs a Manjuel process wired with --manjuel. May refuse
	// when it is unwired, but must name the missing flag.
	TierEngine
)

func (t Tier) String() string {
	switch t {
	case TierSpine:
		return "spine"
	case TierEngine:
		return "engine"
	default:
		return "core"
	}
}

type Tool struct {
	Name        string
	Description string
	Writes      bool
	// Tier is what this tool needs beyond a directory. Zero value is core.
	Tier Tier
	Args []string
	Fn   Fn
}

type Registry struct {
	order  []string
	byName map[string]Tool
}

func (r *Registry) add(t Tool) {
	if _, dup := r.byName[t.Name]; !dup {
		r.order = append(r.order, t.Name)
	}
	r.byName[t.Name] = t
}

func (r *Registry) Get(name string) (Tool, bool) {
	t, ok := r.byName[name]
	return t, ok
}

func (r *Registry) Names() []string {
	out := make([]string, len(r.order))
	copy(out, r.order)
	return out
}

func (r *Registry) All() []Tool {
	out := make([]Tool, 0, len(r.order))
	for _, n := range r.order {
		out = append(out, r.byName[n])
	}
	return out
}

// Call resolves the PROJECT ARGUMENT against the tenant registry, then runs
// the named tool on that ground. Unknown tools and unknown projects refuse
// by name -- strangers get nothing. RBAC is checked when a policy is set;
// open mode (no policy) allows all.
func (r *Registry) Call(reg *tenant.Registry, name string, args map[string]any) (string, error) {
	t, ok := r.byName[name]
	if !ok {
		return "", fmt.Errorf("%w: %q", ErrUnknownTool, name)
	}
	project := ""
	if p, ok := args["project"].(string); ok {
		project = p
	}
	tn, err := reg.Resolve(project)
	if err != nil {
		return "", err
	}
	// RBAC check: if the tenant has a policy with assignments, check permission
	actor, _ := args["actor"].(string)
	if actor != "" {
		allowed, role, reason := tn.CheckRBAC(actor, name)
		if !allowed {
			return "", fmt.Errorf("rbac: agent %q (role %q) denied tool %q: %s", actor, role, name, reason)
		}
	}
	return t.Fn(tn, args)
}

// Options for tool constructors that shell out to the Rust spine.
type Options struct {
	AtlasBin string
	// CoreCmd runs Manjuel, e.g. `python C:\...\manjuel.py`. THE LINE appends
	// --headless --ground itself, so no call can point the door at a world it
	// was not given. Empty means the glass can read the record but not run a
	// turn, and env_open says so rather than failing obscurely.
	CoreCmd string
}

// findAtlas resolves the Rust spine. In order: an explicit path that is not
// the placeholder, then ATLAS_BIN, then PATH, then the built tree walked up
// from the tenant's own home AND from the process working directory — which
// between them cover `go run` from the module, `go test` from a package dir,
// a binary launched from the repo root, and a door whose cwd is the tenant.
// Returns "atlas" unchanged when nothing is found, so the refusal a caller
// sees still names the thing it could not run.
func findAtlas(flagVal, home string) string {
	if flagVal != "" && flagVal != "atlas" {
		return flagVal
	}
	if v := os.Getenv("ATLAS_BIN"); v != "" {
		return v
	}
	if exe, err := exec.LookPath("atlas"); err == nil {
		return exe
	}
	name := "atlas"
	if os.PathSeparator == '\\' {
		name = "atlas.exe"
	}
	// THE BINARY'S OWN LOCATION IS THE ROOT THAT ACTUALLY WORKS. A first cut
	// walked up from the tenant home and from cwd; for atlas-mcp the tenant
	// home is the CORE ground, and the spine lives DOWN from there in
	// atlas/target/, so the walk climbed past Desktop and found nothing.
	// atlas-mcp.exe sits at <repo>/line/, and the spine it needs is built at
	// <repo>/target/ -- two levels up and back down, which this walk covers.
	roots := []string{}
	if exe, err := os.Executable(); err == nil {
		roots = append(roots, filepath.Dir(exe))
	}
	// ABSOLUTE, NOT ".". filepath.Dir(".") is "." — so a relative root breaks
	// out of the walk below on its first step and never climbs at all. The
	// door never noticed because its own executable path walks fine; a TEST
	// binary lives in a build temp dir, so this root was the only one that
	// could reach the tree, and it was the one that did nothing. Found
	// 2026-09-11 by the first stroke written against it.
	if wd, err := os.Getwd(); err == nil {
		roots = append(roots, wd)
	}
	roots = append(roots, home)
	for _, root := range roots {
		if root == "" {
			continue
		}
		dir := root
		for i := 0; i < 5; i++ {
			for _, profile := range []string{"release", "debug"} {
				c := filepath.Join(dir, "target", profile, name)
				if st, err := os.Stat(c); err == nil && !st.IsDir() {
					if abs, err := filepath.Abs(c); err == nil {
						return abs
					}
					return c
				}
			}
			parent := filepath.Dir(dir)
			if parent == dir {
				break
			}
			dir = parent
		}
	}
	return "atlas"
}

// engines is THE LINE's supervisor: one Manjuel process per open world.
// Deliberately NOT under askLock -- that mutex is global across every tenant,
// and a 600-second turn beneath it would freeze every tool on every world
// (SPEC_CONTROL_CENTER 4.6). One process per world already is the invariant.
var engines = engine.NewRegistry()

// Engines lets the door reap every world on its way down. An orphaned engine
// holds its world's sitting open, and an open sitting is what RULE 9 forbids
// editing under and what the release gate refuses a tag over.
func Engines() *engine.Registry { return engines }

// Build wires the lawful surface onto a tenant registry. Landed tools run
// for real; later-stone tools refuse honestly rather than fabricate.
func Build(reg *tenant.Registry, opts Options) *Registry {
	r := &Registry{byName: map[string]Tool{}}

	str := func(args map[string]any, key string) string {
		if v, ok := args[key].(string); ok {
			return v
		}
		return ""
	}

	r.add(Tool{
		Name: "get_in_line", Writes: false,
		Description: "standing law + line + road + log-tail for a carried project",
		Args:        []string{"project?"},
		Fn: func(t tenant.Tenant, _ map[string]any) (string, error) {
			return orientForTenant(t)
		},
	})

	r.add(Tool{
		Name: "verify_chain", Writes: false, Tier: TierSpine,
		Description: "chain verdict via the Rust spine: EMPTY|INTACT|FLIP|TAMPER",
		Args:        []string{"path", "project?"},
		Fn: func(t tenant.Tenant, args map[string]any) (string, error) {
			path := str(args, "path")
			if path == "" {
				return "", fmt.Errorf("verify_chain needs a path")
			}
			// RESOLVED HERE, not taken on faith from the flag. `--atlas-bin`
			// defaults to the bare word "atlas", and on any machine where the
			// Rust spine has been built but not installed on PATH -- which is
			// every fresh clone -- exec fails with `"atlas": not found in
			// %PATH%` and verify_chain is dead on arrival. atlas-door already
			// walked the built tree for it; atlas-mcp never did, so the same
			// estate answered differently depending on which door you came
			// through. findAtlas() is that walk, moved to the one place that
			// actually shells the binary so every caller gets it.
			bin := findAtlas(opts.AtlasBin, t.Home)
			// Through the one spawn contract (ADR-006 item 5). This seam had NO
			// TIMEOUT — a wedged Rust binary hung the tool call, and through it
			// the door, forever. ESTATE LAW 7 is bounded everything; it is bounded
			// now, and the spine's own words still come back whole because a
			// refusal that names only its exit status is the thing ADR-006 item 1
			// was written to stop.
			res := spawn(bin, []string{"chain", "verify", path},
				spawnOpts{Dir: t.Home, Timeout: 30 * time.Second})
			return res.Combined, res.Err
		},
	})

	r.add(Tool{
		Name: "muster", Writes: false,
		Description: "declared projects roll call",
		Fn: func(_ tenant.Tenant, _ map[string]any) (string, error) {
			names := reg.Names()
			out := fmt.Sprintf("%d carried projects:", len(names))
			for _, n := range names {
				out += "\n  " + n
			}
			return out, nil
		},
	})

	r.add(Tool{
		Name: "read_handoffs", Writes: false,
		Description: "SEAT_LOG (or the manifest 'log' path) whole, with sha256 receipt(s)",
		Args:        []string{"project?"},
		Fn:          toolReadHandoffs,
	})

	r.add(Tool{
		Name: "list_doctrine", Writes: false,
		Description: "carried doctrine by name, read-only; absent name denied honestly",
		Args:        []string{"project?"},
		Fn:          toolListDoctrine,
	})

	r.add(Tool{
		Name: "read_doctrine", Writes: false,
		Description: "one document whole with sha256 receipt; absent name denied honestly",
		Args:        []string{"name", "project?"},
		Fn:          toolReadDoctrine,
	})

	r.add(Tool{
		Name: "check_the_wall", Writes: false,
		Description: "judge a path before acting; quote the law on refusal",
		Args:        []string{"path", "project?"},
		Fn:          toolCheckWall,
	})

	r.add(Tool{
		Name: "git", Writes: false,
		Description: "the world's repository as it stands now: branch, head, dirty counts, upstream, and whether remote operations are walled",
		Args:        []string{"project?"},
		Fn:          toolGit,
	})

	r.add(Tool{
		Name: "git_diff", Writes: false,
		Description: "what actually changed: one file's change served whole, or the whole tree's; a file git has never seen comes back as its contents, said plainly",
		Args:        []string{"file?", "project?"},
		Fn:          toolGitDiff,
	})

	// The verbs that CHANGE a repository (gitctl.go). Nothing here fires on
	// its own: these are the buttons on the operator's glass, and RULE 6
	// leaves the hand on the button his.
	r.add(Tool{
		Name: "git_commit", Writes: true,
		Description: "save this world's work: stages everything (or only the files named, one per line) and records it under a message you write",
		Args:        []string{"message", "files?", "project?"},
		Fn:          toolGitCommit,
	})

	r.add(Tool{
		Name: "git_push", Writes: true,
		Description: "send saved work to the remote; refuses by name while the estate's wall is shut, and says so when it binds a branch to origin for the first time",
		Args:        []string{"project?"},
		Fn:          toolGitPush,
	})

	r.add(Tool{
		Name: "git_pull", Writes: true,
		Description: "fetch and catch up, fast-forward only; refuses over unsaved work, and refuses to join two histories that both moved",
		Args:        []string{"project?"},
		Fn:          toolGitPull,
	})

	r.add(Tool{
		Name: "git_branch", Writes: true,
		Description: "the lines of work: list them (which one you are on, which is the main line, which have been sent), or open, switch to, or close one",
		Args:        []string{"action?", "name?", "project?"},
		Fn:          toolGitBranch,
	})

	r.add(Tool{
		Name: "git_remote", Writes: false,
		Description: "where this world sends: each remote by name, its host, and whether the estate's wall is open",
		Args:        []string{"project?"},
		Fn:          toolGitRemote,
	})

	r.add(Tool{
		Name: "records", Writes: false,
		Description: "the estate's own documents sorted by what they are (doctrine, record, spec, agents, commands, skills, logs); a kind listed, or one document served whole with a sha256 receipt",
		Args:        []string{"kind?", "name?", "project?"},
		Fn:          toolRecords,
	})

	r.add(Tool{
		Name: "seats", Writes: false,
		Description: "the world's own seat declarations and the pipelines they stand in, from agents/ and pipelines.md",
		Args:        []string{"project?"},
		Fn:          toolSeats,
	})

	r.add(Tool{
		Name: "proofs", Writes: false,
		Description: "what this world has PROVED, from its own record: the suites' stamp, every live standup, the parity history",
		Args:        []string{"project?"},
		Fn:          toolProofs,
	})

	r.add(Tool{
		Name: "state_matrix", Writes: false,
		Description: "state = fold(record) index of the named project",
		Args:        []string{"project?"},
		Fn:          toolStateMatrix,
	})

	r.add(Tool{
		Name: "read_plan", Writes: false,
		Description: "HLD/LLD/road documents by name; absent name denied honestly",
		Args:        []string{"which", "project?"},
		Fn:          toolReadPlan,
	})

	r.add(Tool{
		Name: "ask_steward", Writes: true, Tier: TierEngine,
		Description: "the weighed ruling with receipts, never raw model output; one-shot under the ask lock",
		Args:        []string{"question", "project?"},
		Fn:          toolAskSteward,
	})

	r.add(Tool{
		Name: "remember", Writes: true,
		Description: "sole write tool; testimony stamped generated; staged for operator ascend",
		Args:        []string{"text", "project?"},
		Fn:          toolRemember,
	})

	// THE MESH (B2): the `.us` messaging protocol over THE LINE. Every tool
	// names its ground; chan defaults to the caller's project and anything
	// else is refused by name (the wall). Writes serialize under the ask
	// lock — one pen per actor, one head per channel.
	r.add(Tool{
		Name: "mesh_enroll", Writes: true,
		Description: "bind a mesh voice: actor -> verifying key (B2)",
		Args:        []string{"member", "pub", "project?"},
		Fn:          toolMeshEnroll,
	})

	r.add(Tool{
		Name: "mesh_post", Writes: true,
		Description: "post one signed message on the channel chain (B2)",
		Args:        []string{"actor", "text", "to", "project?", "chan?", "mode?", "kind?", "cites?"},
		Fn:          toolMeshPost,
	})

	r.add(Tool{
		Name: "mesh_read", Writes: false,
		Description: "read the channel-head index or one actor's chain (B2)",
		Args:        []string{"project?", "actor?", "last?", "reveal?"},
		Fn:          toolMeshRead,
	})

	r.add(Tool{
		Name: "mesh_chain", Writes: false,
		Description: "rewalk every pen plus the head: EMPTY|INTACT|FLIP|TAMPER|FORGERY (B2)",
		Args:        []string{"project?"},
		Fn:          toolMeshChain,
	})

	r.add(Tool{
		Name: "mesh_cite", Writes: true,
		Description: "cite chain hashes by a signed cite entry (B2)",
		Args:        []string{"actor", "targets", "text", "project?", "to?"},
		Fn:          toolMeshCite,
	})

	// F1 step 1 (small): rack_list is REAL — the live tier ladder of lawful
	// local voices (loopback Ollama). rack_ask/rack_open stay refusing below.
	r.add(Tool{
		Name: "rack_list", Writes: false,
		Description: "live tier ladder of lawful local voices (F1)",
		Args:        []string{"project?"},
		Fn:          toolRackList,
	})

	// F1 step 2 (small): rack_ask is REAL — one question, routed to a
	// lawful local voice, witnessed to the rack ledger under the ask lock.
	r.add(Tool{
		Name: "rack_ask", Writes: true,
		Description: "routed ask, witnessed to the ledger (F1)",
		Args:        []string{"question", "voice?", "project?"},
		Fn:          toolRackAsk,
	})

	// F1 step 3 (small): rack_open is REAL — the expanded context bundle
	// at a depth. The rack trio is awake; nothing on the surface refuses
	// honestly anymore (forbidden verbs stay absent by construction).
	r.add(Tool{
		Name: "rack_open", Writes: false,
		Description: "expanded context bundle at a depth (F1)",
		Args:        []string{"project?", "voice?", "depth?"},
		Fn:          toolRackOpen,
	})

	// F1-01 (small): memory is REAL — cited answers from the rack ledger,
	// or a refusal with pinned words. Read-only.
	r.add(Tool{
		Name: "memory", Writes: false,
		Description: "cited answers from local memory, or refusal (F1-01)",
		Args:        []string{"project?", "voice?", "question?"},
		Fn:          toolMemory,
	})

	// N3 model hosting: planner + management over loopback Ollama only.
	r.add(Tool{
		Name: "rack_plan", Writes: false,
		Description: "VRAM fit check for a model set before it runs (N3)",
		Args:        []string{"models?", "voices?", "project?"},
		Fn:          toolRackPlan,
	})
	r.add(Tool{
		Name: "rack_pull", Writes: true,
		Description: "pull a model into the loopback rack behind confirm (N3)",
		Args:        []string{"model", "confirm?", "project?"},
		Fn:          toolRackPull,
	})
	r.add(Tool{
		Name: "rack_warm", Writes: false,
		Description: "verify a voice is present and report its footprint (N3)",
		Args:        []string{"voice", "project?"},
		Fn:          toolRackWarm,
	})
	r.add(Tool{
		Name: "rack_sync", Writes: false,
		Description: "re-list the loopback rack with a sync receipt (N3)",
		Args:        []string{"project?"},
		Fn:          toolRackSync,
	})

	// N1 chat: sessions with receipts over the rack. Guard runs first
	// (blocked sends write nothing); sends serialize under the ask lock.
	r.add(Tool{
		Name: "chat_start", Writes: true,
		Description: "open a chat session with a receipted id (N1)",
		Args:        []string{"actor?", "voice?", "project?"},
		Fn:          toolChatStart,
	})
	r.add(Tool{
		Name: "chat_send", Writes: true,
		Description: "ask in a session; whole witnessed answer or refusal (N1)",
		Args:        []string{"session", "question", "actor?", "voice?", "project?"},
		Fn:          toolChatSend,
	})
	r.add(Tool{
		Name: "chat_list", Writes: false,
		Description: "read one session's turns, isolated by session (N1)",
		Args:        []string{"session?", "last?", "project?"},
		Fn:          toolChatList,
	})
	r.add(Tool{
		Name: "chat_cancel", Writes: false,
		Description: "end an in-flight send; no partial answer is kept (N1)",
		Args:        []string{"session", "project?"},
		Fn:          toolChatCancel,
	})
	r.add(Tool{
		Name: "chat_sessions", Writes: false,
		Description: "list opened chat sessions in first-seen order (N1)",
		Args:        []string{"project?"},
		Fn:          toolChatSessions,
	})

	// N4 playground: versioned prompts, measured runs, single-seat asks.
	// Runs serialize under the ask lock; missing vars, unknown seats and
	// absent datasets are refused by name, never guessed.
	r.add(Tool{
		Name: "prompt_save", Writes: true,
		Description: "fold a new prompt version; history kept whole (N4)",
		Args:        []string{"name", "body", "description?", "project?"},
		Fn:          toolPromptSave,
	})
	r.add(Tool{
		Name: "prompt_get", Writes: false,
		Description: "read one prompt version with receipt (N4)",
		Args:        []string{"name", "version?", "project?"},
		Fn:          toolPromptGet,
	})
	r.add(Tool{
		Name: "prompt_list", Writes: false,
		Description: "list prompts with latest versions (N4)",
		Args:        []string{"project?"},
		Fn:          toolPromptList,
	})
	r.add(Tool{
		Name: "prompt_run", Writes: true,
		Description: "render a prompt and measure one answer (N4)",
		Args:        []string{"name", "vars?", "version?", "voice?", "project?"},
		Fn:          toolPromptRun,
	})
	r.add(Tool{
		Name: "prompt_compare", Writes: true,
		Description: "run two versions over the same input, diff honestly (N4)",
		Args:        []string{"name", "vera", "verb", "vars?", "voice?", "project?"},
		Fn:          toolPromptCompare,
	})
	r.add(Tool{
		Name: "prompt_eval", Writes: true,
		Description: "score a prompt over a dataset, exact-match (N4)",
		Args:        []string{"name", "dataset", "version?", "voice?", "project?"},
		Fn:          toolPromptEval,
	})
	r.add(Tool{
		Name: "seat_ask", Writes: true,
		Description: "@seat single-seat ask; model is a measurement (N4)",
		Args:        []string{"question", "seat?", "voice?", "method?", "project?"},
		Fn:          toolSeatAsk,
	})

	// N2 town: the beat walks over the tenant's own ops ground, filing
	// REVIEW tasks the operator's hand moves. Quiet grounds stay quiet.
	r.add(Tool{
		Name: "town_beat", Writes: true,
		Description: "run one town scheduling cycle on this ground (N2)",
		Args:        []string{"project?"},
		Fn:          toolTownBeat,
	})
	r.add(Tool{
		Name: "town_status", Writes: false,
		Description: "read the board: tasks, worked set, open orders (N2)",
		Args:        []string{"project?"},
		Fn:          toolTownStatus,
	})

	// N2 flows: versioned DAG specs with measured runs, gates that pause
	// for the hand, evals that steer edges. Runs serialize under the ask
	// lock — branches declare parallelism, the queue runs them one by one.
	r.add(Tool{
		Name: "flow_save", Writes: true,
		Description: "fold a new flow spec version; history kept whole (N2)",
		Args:        []string{"name", "spec", "project?"},
		Fn:          toolFlowSave,
	})
	r.add(Tool{
		Name: "flow_get", Writes: false,
		Description: "read one flow spec version (N2)",
		Args:        []string{"name", "version?", "project?"},
		Fn:          toolFlowGet,
	})
	r.add(Tool{
		Name: "flow_list", Writes: false,
		Description: "list flows with latest versions (N2)",
		Args:        []string{"project?"},
		Fn:          toolFlowList,
	})
	r.add(Tool{
		Name: "flow_run", Writes: true,
		Description: "fire a flow; gates pause, evals steer, budget binds (N2)",
		Args:        []string{"name", "inputs?", "version?", "project?"},
		Fn:          toolFlowRun,
	})
	r.add(Tool{
		Name: "flow_resume", Writes: true,
		Description: "carry a paused run on with continue|stop (N2)",
		Args:        []string{"run", "decision", "project?"},
		Fn:          toolFlowResume,
	})
	r.add(Tool{
		Name: "flow_cancel", Writes: false,
		Description: "end a live run; reached nodes stand (N2)",
		Args:        []string{"run", "project?"},
		Fn:          toolFlowCancel,
	})
	r.add(Tool{
		Name: "flow_status", Writes: false,
		Description: "waterfall: nodes, elapsed, budget bar, verdict (N2)",
		Args:        []string{"run", "project?"},
		Fn:          toolFlowStatus,
	})
	r.add(Tool{
		Name: "flow_compare", Writes: false,
		Description: "two runs side by side, node by node (N2)",
		Args:        []string{"runa", "runb", "project?"},
		Fn:          toolFlowCompare,
	})
	r.add(Tool{
		Name: "flow_replay", Writes: true,
		Description: "re-fire a run's spec and inputs under a fresh id (N2)",
		Args:        []string{"run", "project?"},
		Fn:          toolFlowReplay,
	})
	r.add(Tool{
		Name: "flow_runs", Writes: false,
		Description: "list runs for a flow, newest last (N2)",
		Args:        []string{"flow?", "project?"},
		Fn:          toolFlowRuns,
	})

	// N5 team chat: the two-way bridge. Outbound runs the guard and POSTs
	// to the operator's own URLs; inbound verifies the shared secret and
	// dedupes. Secrets never appear in any answer — presence only.
	r.add(Tool{
		Name: "team_send", Writes: true,
		Description: "send one guarded message to discord|slack|whatsapp (N5)",
		Args:        []string{"platform", "channel", "content", "actor?", "project?"},
		Fn:          toolTeamSend,
	})
	r.add(Tool{
		Name: "team_status", Writes: false,
		Description: "platform presence + last sends, never secrets (N5)",
		Args:        []string{"project?"},
		Fn:          toolTeamStatus,
	})
	r.add(Tool{
		Name: "team_history", Writes: false,
		Description: "read the bridge record, filtered, newest last (N5)",
		Args:        []string{"channel?", "platform?", "last?", "project?"},
		Fn:          toolTeamHistory,
	})
	r.add(Tool{
		Name: "team_ingest", Writes: true,
		Description: "verify + store one inbound platform envelope (N5)",
		Args:        []string{"platform", "body", "signature", "project?"},
		Fn:          toolTeamIngest,
	})

	// N6 auth: scoped API keys per tenant. Bootstrap is open on an empty
	// store (the first key is the operator's hand); afterwards creation
	// and revocation name an existing key — sensitive moves re-prove
	// possession, like sudo. Plaintext returns once, at creation.
	r.add(Tool{
		Name: "auth_key_create", Writes: true,
		Description: "mint a scoped API key; plaintext returns once (N6)",
		Args:        []string{"name", "tenants?", "key?", "project?"},
		Fn:          toolAuthCreate,
	})
	r.add(Tool{
		Name: "auth_key_list", Writes: false,
		Description: "list live keys with hashes withheld (N6)",
		Args:        []string{"project?"},
		Fn:          toolAuthList,
	})
	r.add(Tool{
		Name: "auth_key_revoke", Writes: true,
		Description: "fold a key: flagged, kept for audit (N6)",
		Args:        []string{"id", "key?", "project?"},
		Fn:          toolAuthRevoke,
	})
	r.add(Tool{
		Name: "auth_verify", Writes: false,
		Description: "check a key against a tenant store; the login door (N6)",
		Args:        []string{"key", "project?"},
		Fn:          toolAuthVerify,
	})
	r.add(Tool{
		Name: "tenant_trust_list", Writes: false,
		Description: "read recorded cross-tenant delegations (N6)",
		Args:        []string{"project?"},
		Fn:          toolTrustList,
	})

	// Phase 3: .us → W3C Verifiable Credential adapter.
	r.add(Tool{
		Name: "us_to_vc", Writes: false,
		Description: "convert a .us declaration to a W3C Verifiable Credential",
		Args:        []string{"path", "project?"},
		Fn: func(t tenant.Tenant, args map[string]any) (string, error) {
			usPath := str(args, "path")
			if usPath == "" {
				return "", fmt.Errorf("us_to_vc needs a path to a .us file")
			}
			return toolUsToVC(t, usPath)
		},
	})

	// Phase 3.2: Multi-tenancy RBAC tools. N0: tenant_list enumerates
	// the registry (open mode vs assigned counts); trust persists.
	r.add(Tool{
		Name: "tenant_list", Writes: false,
		Description: "list all registered tenants and their roles",
		Args:        []string{"project?"},
		Fn: func(t tenant.Tenant, _ map[string]any) (string, error) {
			return toolTenantListReg(reg, t)
		},
	})

	r.add(Tool{
		Name: "tenant_rbac_assign", Writes: true,
		Description: "assign a role to an agent in a tenant's RBAC policy",
		Args:        []string{"actor", "role", "project?"},
		Fn:          toolTenantRBACAssign,
	})

	r.add(Tool{
		Name: "tenant_rbac_check", Writes: false,
		Description: "check if an agent has permission for a tool under a tenant's RBAC policy",
		Args:        []string{"actor", "tool", "project?"},
		Fn:          toolTenantRBACCheck,
	})

	r.add(Tool{
		Name: "tenant_trust", Writes: true,
		Description: "grant or revoke cross-tenant trust (delegation of specific tools)",
		Args:        []string{"from_project", "to_project", "tool", "action", "project?"},
		Fn: func(t tenant.Tenant, args map[string]any) (string, error) {
			askLock.Lock()
			defer askLock.Unlock()
			return toolTenantTrustReg(reg, t, args)
		},
	})

	// ── THE SEAM: the council, not just a voice ──────────────────────
	// chat_* reaches a MODEL. These reach the ENGINE, so the law gate, the
	// one Router, the dedup, the claim check and the recompose all apply --
	// because the run happens inside Manjuel, not beside it.
	r.add(Tool{
		Name: "env_open", Writes: true, Tier: TierEngine,
		Description: "open the Manjuel engine inside a world; refuses a world already being sat in",
		Args:        []string{"project?"},
		Fn: func(t tenant.Tenant, _ map[string]any) (string, error) {
			e, err := engines.Open(t.Name, t.Home, opts.CoreCmd)
			if err != nil {
				return "", err
			}
			o := e.Opened()
			return fmt.Sprintf(
				"OPENED %s · sitting %s · session %s\n  %s\n  rack %s · pipeline %s\n  seats: %s",
				t.Name, o.Str("sitting"), o.Str("session"), o.Str("git"),
				map[bool]string{true: "reachable", false: "UNREACHABLE"}[o["rack_ok"] == true],
				o.Str("pipeline"), truncateRunes(o.Str("seats"), 300)), nil
		},
	})

	r.add(Tool{
		Name: "env_close", Writes: true, Tier: TierEngine,
		Description: "close the world's sitting properly and reap its engine",
		Args:        []string{"project?"},
		Fn: func(t tenant.Tenant, _ map[string]any) (string, error) {
			tollPaid, err := engines.CloseOne(t.Home)
			if err != nil {
				return "", err
			}
			if !tollPaid {
				return fmt.Sprintf("CLOSED %s -- BUT THE ENGINE HAD TO BE KILLED after "+
					"%ds. The toll may not have been paid and `ended` may not have been "+
					"written; check the world's sessions.jsonl before opening it again.",
					t.Name, int(engine.ShutdownGrace.Seconds())), nil
			}
			return fmt.Sprintf("CLOSED %s -- the sitting is tolled and the engine reaped", t.Name), nil
		},
	})

	r.add(Tool{
		Name: "env_list", Writes: false,
		Description: "which worlds have an engine open, and which are being sat in elsewhere",
		Fn: func(_ tenant.Tenant, _ map[string]any) (string, error) {
			var b strings.Builder
			open := engines.List()
			fmt.Fprintf(&b, "%d engine(s) open:\n", len(open))
			for _, e := range open {
				pend := ""
				if p := e.Pending(); p != nil {
					pend = " · WAITING ON AN ANSWER: " + truncateRunes(p.Str("prompt"), 90)
				}
				fmt.Fprintf(&b, "  %s · sitting %s%s\n", e.Name, e.Opened().Str("sitting"), pend)
			}
			b.WriteString("\ncarried worlds:\n")
			for _, name := range reg.Names() {
				tn, err := reg.Resolve(name)
				if err != nil {
					continue
				}
				state := "closed"
				if _, ok := engines.Get(tn.Home); ok {
					state = "engine open here"
				} else if n, started, sat := engine.SittingOpen(tn.Home); sat {
					state = fmt.Sprintf("sat in elsewhere (sitting %d, %s)", int(n), started)
				}
				fmt.Fprintf(&b, "  %-16s %s\n", name, state)
			}
			return b.String(), nil
		},
	})

	r.add(Tool{
		Name: "run_start", Writes: true, Tier: TierEngine,
		Description: "run one objective through the council; the delivery with what actually ran",
		Args:        []string{"objective", "project?", "feed?", "method?"},
		Fn: func(t tenant.Tenant, args map[string]any) (string, error) {
			objective := strings.TrimSpace(str(args, "objective"))
			if objective == "" {
				return "", fmt.Errorf("run_start needs an objective")
			}
			e, ok := engines.Get(t.Home)
			if !ok {
				return "", fmt.Errorf("no engine is open on %q -- env_open first", t.Name)
			}
			res, err := e.Run(objective, str(args, "feed"), str(args, "method"), nil)
			if err != nil {
				return "", err
			}
			return renderRun(t.Name, objective, res), nil
		},
	})

	r.add(Tool{
		Name: "run_answer", Writes: true, Tier: TierEngine,
		Description: "answer what the run asked; the gate crossing the wire, never a default",
		Args:        []string{"text", "project?"},
		Fn: func(t tenant.Tenant, args map[string]any) (string, error) {
			e, ok := engines.Get(t.Home)
			if !ok {
				return "", fmt.Errorf("no engine is open on %q", t.Name)
			}
			res, err := e.Answer(str(args, "text"), nil)
			if err != nil {
				return "", err
			}
			return renderRun(t.Name, "(answered)", res), nil
		},
	})

	r.add(Tool{
		Name: "run_cancel", Writes: false, Tier: TierEngine,
		Description: "interrupt the turn in flight; the sitting stays open",
		Args:        []string{"project?"},
		Fn: func(t tenant.Tenant, _ map[string]any) (string, error) {
			e, ok := engines.Get(t.Home)
			if !ok {
				return "", fmt.Errorf("no engine is open on %q", t.Name)
			}
			if err := e.Cancel(); err != nil {
				return "", err
			}
			return "CANCELLED -- the turn was interrupted; the sitting stands", nil
		},
	})

	return r
}

// renderRun reports the turn off the engine's OWN events -- elapsed, tools,
// failures, out-of-time, the notes the gate wrote -- never off a seat's prose
// (LAW 5). A run that stopped on a question says so and quotes it.
func renderRun(world, objective string, res engine.Result) string {
	var b strings.Builder
	f := res.Final
	if res.Waiting {
		fmt.Fprintf(&b, "WAITING on %q\n\n  %s\n\nAnswer with run_answer. "+
			"Nothing is assumed on your behalf (RULE 6).", world, f.Str("prompt"))
		return b.String()
	}
	switch f.Kind() {
	case "delivery":
		fmt.Fprintf(&b, "%s · %s · %ss\n\n%s\n",
			world, f.Str("pipeline"), f.Str("elapsed"), f.Str("text"))
		fmt.Fprintf(&b, "\n--- what actually ran ---\n")
		for _, ev := range res.Events {
			if ev.Kind() == "tool_result" {
				mark := "ok"
				if ev["failed"] == true {
					mark = "FAILED"
				}
				fmt.Fprintf(&b, "  tool %-18s %s\n", ev.Str("action"), mark)
			}
		}
		if s, ok := f["steps"].([]any); ok {
			for _, raw := range s {
				st, _ := raw.(map[string]any)
				fmt.Fprintf(&b, "  seat %-18s %vs%s\n", st["seat"], st["elapsed"],
					map[bool]string{true: " SKIPPED", false: ""}[st["skipped"] == true])
			}
		}
		for _, k := range []string{"failures", "out_of_time"} {
			if v, ok := f[k].([]any); ok && len(v) > 0 {
				fmt.Fprintf(&b, "  %s: %v\n", k, v)
			}
		}
		if n, ok := f["notes"].([]any); ok {
			for _, note := range n {
				fmt.Fprintf(&b, "  note: %v\n", note)
			}
		}
		fmt.Fprintf(&b, "  transcript: %s · %d tokens streamed\n",
			f.Str("transcript"), res.Tokens)
	default:
		fmt.Fprintf(&b, "%s: %s\n%s", strings.ToUpper(f.Kind()), f.Str("text"), objective)
	}
	return b.String()
}

// toolRackList ladders the lawful local voices. Silence from the door is
// an honest empty with the reason — never fabricated voices.
func toolRackList(t tenant.Tenant, _ map[string]any) (string, error) {
	host, err := rack.Host()
	if err != nil {
		return "", err
	}
	voices, err := rack.List(host)
	if err != nil {
		return "THE RACK — " + err.Error() + ": nothing fabricated.", nil
	}
	return rack.Ladder(voices), nil
}

// toolRackAsk routes one question to a lawful local voice and witnesses
// the answer to the rack ledger — under the ask lock, one writer. The
// guard pipeline runs first: injections refuse (never routed, never
// witnessed), PII redacts before voice and ledger, poison flags ride the
// witness and the answer wrapper.
func toolRackAsk(t tenant.Tenant, args map[string]any) (string, error) {
	question, _ := args["question"].(string)
	question = strings.TrimSpace(question)
	if question == "" {
		return "", fmt.Errorf("rack_ask needs a question — no voice is asked nothing")
	}
	clean, flags, blocked, reason := guard.Pipeline(question)
	if blocked {
		return "", fmt.Errorf("refused: %s", reason)
	}
	voice, _ := args["voice"].(string)
	host, err := rack.Host()
	if err != nil {
		return "", err
	}
	askLock.Lock()
	defer askLock.Unlock()
	voices, err := rack.List(host)
	if err != nil {
		return "", err
	}
	routed, err := rack.Route(host, strings.TrimSpace(voice), voices)
	if err != nil {
		return "", err
	}
	answer, err := rack.Ask(host, routed, clean)
	if err != nil {
		return "", err
	}
	path, err := rack.WitnessV(t.Home, routed, clean, answer, flags)
	if err != nil {
		return "", err
	}
	if len(flags) > 0 {
		return fmt.Sprintf("voice %s answered (witnessed %s) [flags: %s]:\n%s",
			routed, path, strings.Join(flags, ", "), answer), nil
	}
	return fmt.Sprintf("voice %s answered (witnessed %s):\n%s", routed, path, answer), nil
}

// toolRackOpen bundles what a voice needs: card, ladder + memory, ground.
// Read-only. Unknown voices refused by name; depths outside 1-3 refused.
func toolRackOpen(t tenant.Tenant, args map[string]any) (string, error) {
	depth := 1
	switch n := args["depth"].(type) {
	case float64:
		if n != float64(int(n)) {
			return "", fmt.Errorf("refused: depth is 1, 2, or 3")
		}
		depth = int(n)
	case int:
		depth = n
	case nil:
		depth = 1
	default:
		return "", fmt.Errorf("refused: depth is 1, 2, or 3")
	}
	voice, _ := args["voice"].(string)
	host, err := rack.Host()
	if err != nil {
		return "", err
	}
	voices, err := rack.List(host)
	if err != nil {
		return "", err
	}
	name := strings.TrimSpace(voice)
	if name == "" {
		var rerr error
		name, rerr = rack.Route(host, "", voices)
		if rerr != nil {
			return "", rerr
		}
	} else {
		found := false
		for _, v := range voices {
			if v.Name == name {
				found = true
				break
			}
		}
		if !found {
			return "", fmt.Errorf("refused: voice %q is not on the rack — nothing fabricated", name)
		}
	}
	var card rack.Voice
	for _, v := range voices {
		if v.Name == name {
			card = v
		}
	}
	caps, err := rack.Capabilities(host, name)
	if err != nil {
		return "", err
	}
	ledger, err := rack.ReadLedger(t.Home)
	if err != nil {
		return "", err
	}
	ground := ""
	if depth == 3 {
		ground, err = orientForTenant(t)
		if err != nil {
			return "", err
		}
	}
	return rack.Bundle(t.Name, name, rack.TierOf(card.Size), card.Size, card.Family,
		caps, rack.Ladder(voices), ledger, ground, depth)
}

// toolMemory recalls cited answers, or refuses with pinned words.
func toolMemory(t tenant.Tenant, args map[string]any) (string, error) {
	voice, _ := args["voice"].(string)
	question, _ := args["question"].(string)
	return rack.Recall(t.Home, strings.TrimSpace(voice), strings.TrimSpace(question))
}

// --- N3 model hosting -------------------------------------------------------
// Pure planner + loopback management. Pulls stay behind MANJUEL_RACK_PULL
// + explicit confirm; everything refuses non-loopback before dialing.

func toolRackPlan(t tenant.Tenant, args map[string]any) (string, error) {
	_ = t
	if raw, _ := args["models"].(string); strings.TrimSpace(raw) != "" {
		var doc []struct {
			Name string `json:"name"`
			Size int64  `json:"size"`
		}
		if err := json.Unmarshal([]byte(raw), &doc); err != nil {
			return "", fmt.Errorf("rack_plan models must be JSON [{name,size}]: %s", err)
		}
		if len(doc) > 64 {
			return "", fmt.Errorf("refused: rack_plan caps at 64 models")
		}
		models := make([]rack.Voice, 0, len(doc))
		for _, m := range doc {
			if strings.TrimSpace(m.Name) == "" || m.Size < 0 {
				return "", fmt.Errorf("refused: model needs a name and a non-negative size")
			}
			models = append(models, rack.Voice{Name: m.Name, Size: m.Size})
		}
		return rack.RenderPlan(models, rack.Plan(models)), nil
	}
	voicesArg, _ := args["voices"].(string)
	host, err := rack.Host()
	if err != nil {
		return "", err
	}
	all, err := rack.List(host)
	if err != nil {
		return "", err
	}
	if strings.TrimSpace(voicesArg) == "" {
		return rack.RenderPlan(all, rack.Plan(all)), nil
	}
	want := map[string]bool{}
	for _, s := range strings.Split(voicesArg, ",") {
		if s = strings.TrimSpace(s); s != "" {
			want[s] = true
		}
	}
	var models []rack.Voice
	for _, v := range all {
		if want[v.Name] {
			models = append(models, v)
			delete(want, v.Name)
		}
	}
	for missing := range want {
		return "", fmt.Errorf("refused: voice %q is not on the rack — nothing fabricated", missing)
	}
	return rack.RenderPlan(models, rack.Plan(models)), nil
}

func toolRackPull(t tenant.Tenant, args map[string]any) (string, error) {
	_ = t
	model, _ := args["model"].(string)
	model = strings.TrimSpace(model)
	if model == "" {
		return "", fmt.Errorf("rack_pull needs a model name")
	}
	confirm, _ := args["confirm"].(bool)
	if !confirm {
		return "", fmt.Errorf("refused: rack_pull needs confirm=true — downloads are the operator's hand")
	}
	// ONE READING with the core: MANJUEL_RACK_PULL, the CHAINKIT_ twin, the
	// ground's .env, and the core's truthiness. This read CHAINKIT_RACK_PULL
	// == "1" while manjuel/skills.py read MANJUEL_RACK_PULL in
	// ("1","true","yes","on"), so the documented name opened the core's wall
	// and left this one shut.
	if !dial(t.Home, "RACK_PULL") {
		return "", fmt.Errorf("refused: rack_pull needs MANJUEL_RACK_PULL=1 -- in the environment, or in this world's .env")
	}
	host, err := rack.Host()
	if err != nil {
		return "", err
	}
	askLock.Lock()
	defer askLock.Unlock()
	body, _ := json.Marshal(map[string]any{"model": model, "stream": false})
	client := &http.Client{Timeout: 30 * time.Minute}
	resp, err := client.Post(host+"/api/pull", "application/json", bytes.NewReader(body))
	if err != nil {
		return "", fmt.Errorf("pull failed for %q: %s", model, err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode >= 300 {
		return "", fmt.Errorf("pull refused for %q (status %d): %s", model, resp.StatusCode, truncateRunes(string(raw), 300))
	}
	return fmt.Sprintf("PULLED %q into the loopback rack.\n%s", model, truncateRunes(string(raw), 500)), nil
}

func toolRackWarm(t tenant.Tenant, args map[string]any) (string, error) {
	_ = t
	voice, _ := args["voice"].(string)
	voice = strings.TrimSpace(voice)
	if voice == "" {
		return "", fmt.Errorf("rack_warm needs a voice")
	}
	host, err := rack.Host()
	if err != nil {
		return "", err
	}
	all, err := rack.List(host)
	if err != nil {
		return "", err
	}
	for _, v := range all {
		if v.Name == voice {
			caps, cerr := rack.Capabilities(host, voice)
			note := ""
			if cerr != nil {
				note = " (capabilities silent: " + truncateRunes(cerr.Error(), 120) + ")"
			} else if !rack.Speaking(caps) {
				note = " (embedding-only: routes refuse it, warmth is storage)"
			}
			return fmt.Sprintf("WARM %q · tier %s · %.2fGB · footprint %.2fGB%s",
				v.Name, rack.TierOf(v.Size), float64(v.Size)/1e9,
				float64(rack.Footprint(v.Size))/1e9, note), nil
		}
	}
	return "", fmt.Errorf("refused: voice %q is not on the rack — nothing fabricated", voice)
}

func toolRackSync(t tenant.Tenant, args map[string]any) (string, error) {
	_ = args
	host, err := rack.Host()
	if err != nil {
		return "", err
	}
	voices, err := rack.List(host)
	if err != nil {
		return "THE RACK — " + err.Error() + ": nothing fabricated.", nil
	}
	return rack.Ladder(voices) + fmt.Sprintf("\nSYNCED %d voices.", len(voices)), nil
}

// --- N1 chat ---------------------------------------------------------------

func toolChatStart(t tenant.Tenant, args map[string]any) (string, error) {
	actor, _ := args["actor"].(string)
	voice, _ := args["voice"].(string)
	askLock.Lock()
	defer askLock.Unlock()
	session, err := chat.Start(t.Home, strings.TrimSpace(actor), strings.TrimSpace(voice))
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("SESSION %s opened on %q — every turn carries a receipt", session, t.Name), nil
}

func toolChatSend(t tenant.Tenant, args map[string]any) (string, error) {
	session, _ := args["session"].(string)
	question, _ := args["question"].(string)
	actor, _ := args["actor"].(string)
	voice, _ := args["voice"].(string)
	if strings.TrimSpace(session) == "" {
		return "", fmt.Errorf("chat_send needs a session — open one with chat_start")
	}
	askLock.Lock()
	defer askLock.Unlock()
	turn, err := chat.Send(t.Home, strings.TrimSpace(session), strings.TrimSpace(actor), strings.TrimSpace(voice), question)
	if err != nil {
		return "", err
	}
	return FormatTurn(turn), nil
}

// ChatSendStream is the streaming face of chat_send for the HTTP door:
// same guard-first + one-writer discipline, tokens forwarded as they
// arrive. The SSE handler owns no logic — the chat package does.
func ChatSendStream(reg *Registry, t tenant.Tenant, args map[string]any, onToken func(string)) (string, error) {
	session, _ := args["session"].(string)
	question, _ := args["question"].(string)
	actor, _ := args["actor"].(string)
	voice, _ := args["voice"].(string)
	_ = reg
	if strings.TrimSpace(session) == "" {
		return "", fmt.Errorf("chat_send needs a session — open one with chat_start")
	}
	askLock.Lock()
	defer askLock.Unlock()
	turn, err := chat.SendStream(context.Background(), t.Home, strings.TrimSpace(session), strings.TrimSpace(actor), strings.TrimSpace(voice), question, onToken)
	if err != nil {
		return "", err
	}
	return FormatTurn(turn), nil
}

// FormatTurn renders one witnessed turn with its receipt.
func FormatTurn(turn chat.Turn) string {
	out := fmt.Sprintf("n=%d voice %s answered · receipt %s\n%s",
		turn.N, turn.Voice, turn.Receipt, turn.Answer)
	if len(turn.Flags) > 0 {
		out += fmt.Sprintf("\n[flags: %s]", strings.Join(turn.Flags, ", "))
	}
	return out
}

func toolChatList(t tenant.Tenant, args map[string]any) (string, error) {
	session, _ := args["session"].(string)
	last := 0
	switch n := args["last"].(type) {
	case float64:
		last = int(n)
	case int:
		last = n
	}
	turns, err := chat.List(t.Home, strings.TrimSpace(session), last)
	if err != nil {
		return "", err
	}
	if len(turns) == 0 {
		return fmt.Sprintf("session %q holds nothing yet — silence is honest", strings.TrimSpace(session)), nil
	}
	var b strings.Builder
	for _, tn := range turns {
		fmt.Fprintf(&b, "n=%d %s · %s · receipt %s\n  Q: %s\n  A: %s\n",
			tn.N, tn.Voice, tn.TS, tn.Receipt,
			truncateRunes(tn.Question, 200), truncateRunes(tn.Answer, 500))
	}
	return b.String(), nil
}

func toolChatCancel(t tenant.Tenant, args map[string]any) (string, error) {
	_ = t
	session, _ := args["session"].(string)
	if strings.TrimSpace(session) == "" {
		return "", fmt.Errorf("chat_cancel needs a session")
	}
	return chat.Cancel(strings.TrimSpace(session)), nil
}

func toolChatSessions(t tenant.Tenant, _ map[string]any) (string, error) {
	sessions, err := chat.Sessions(t.Home)
	if err != nil {
		return "", err
	}
	if len(sessions) == 0 {
		return "no sessions yet — open one with chat_start", nil
	}
	var b strings.Builder
	fmt.Fprintf(&b, "SESSIONS — %d opened:\n", len(sessions))
	for _, s := range sessions {
		turns, _ := chat.List(t.Home, s, 1)
		last := "no turns yet"
		if len(turns) > 0 {
			last = fmt.Sprintf("n=%d · %s · receipt %s",
				turns[len(turns)-1].N, turns[len(turns)-1].TS, turns[len(turns)-1].Receipt[:16])
		}
		fmt.Fprintf(&b, "  %s · %s\n", s, last)
	}
	return b.String(), nil
}

// --- N4 playground ----------------------------------------------------------

func playVars(args map[string]any) (map[string]string, error) {
	raw, _ := args["vars"].(string)
	if strings.TrimSpace(raw) == "" {
		return map[string]string{}, nil
	}
	var doc map[string]any
	if err := json.Unmarshal([]byte(raw), &doc); err != nil {
		return nil, fmt.Errorf("prompt vars must be a JSON object: %s", err)
	}
	out := map[string]string{}
	for k, v := range doc {
		out[k] = fmt.Sprintf("%v", v)
	}
	return out, nil
}

func playVersion(args map[string]any, key string) int {
	switch n := args[key].(type) {
	case float64:
		return int(n)
	case int:
		return n
	}
	return 0
}

func toolPromptSave(t tenant.Tenant, args map[string]any) (string, error) {
	name, _ := args["name"].(string)
	body, _ := args["body"].(string)
	desc, _ := args["description"].(string)
	askLock.Lock()
	defer askLock.Unlock()
	p, err := play.Save(t.Home, strings.TrimSpace(name), body, desc)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("SAVED %s v%d — history folds whole, nothing rewritten", p.Name, p.Version), nil
}

func toolPromptGet(t tenant.Tenant, args map[string]any) (string, error) {
	name, _ := args["name"].(string)
	p, err := play.Get(t.Home, strings.TrimSpace(name), playVersion(args, "version"))
	if err != nil {
		return "", err
	}
	sha := sha256Bytes([]byte(p.Body))
	return fmt.Sprintf("%s v%d · sha256 %s\n%s\n\n%s", p.Name, p.Version, sha, p.Description, p.Body), nil
}

func toolPromptList(t tenant.Tenant, _ map[string]any) (string, error) {
	list, err := play.List(t.Home)
	if err != nil {
		return "", err
	}
	if len(list) == 0 {
		return "no prompts yet — save one with prompt_save", nil
	}
	var b strings.Builder
	fmt.Fprintf(&b, "PROMPTS — %d template(s):\n", len(list))
	for _, p := range list {
		vers, _ := play.Versions(t.Home, p.Name)
		fmt.Fprintf(&b, "  - %s v%d (kept: %v) — %s\n", p.Name, p.Version, vers, p.Description)
	}
	return b.String(), nil
}

func runFace(r play.Run) string {
	stamp := ""
	if r.Override {
		stamp = " · measurement, not configuration"
	}
	out := fmt.Sprintf("RUN %s · %s v%d · voice %s · %dms",
		r.ID, r.Prompt, r.Version, r.Voice, r.LatencyMs)
	if r.EvalCount > 0 {
		out += fmt.Sprintf(" · %d tokens", r.EvalCount)
	}
	out += stamp + fmt.Sprintf(" · receipt %s\n%s", r.Receipt, r.Output)
	return out
}

func toolPromptRun(t tenant.Tenant, args map[string]any) (string, error) {
	name, _ := args["name"].(string)
	voice, _ := args["voice"].(string)
	vars, err := playVars(args)
	if err != nil {
		return "", err
	}
	askLock.Lock()
	defer askLock.Unlock()
	r, err := play.RunPrompt(t.Home, strings.TrimSpace(name), playVersion(args, "version"), vars, strings.TrimSpace(voice))
	if err != nil {
		return "", err
	}
	return runFace(r), nil
}

func toolPromptCompare(t tenant.Tenant, args map[string]any) (string, error) {
	name, _ := args["name"].(string)
	voice, _ := args["voice"].(string)
	vars, err := playVars(args)
	if err != nil {
		return "", err
	}
	askLock.Lock()
	defer askLock.Unlock()
	rep, err := play.ComparePrompt(t.Home, strings.TrimSpace(name),
		playVersion(args, "vera"), playVersion(args, "verb"), vars, strings.TrimSpace(voice))
	if err != nil {
		return "", err
	}
	verdict := "DIFFER"
	if rep.Same {
		verdict = "IDENTICAL"
	}
	return fmt.Sprintf("COMPARE %s v%d vs v%d: %s\n--- A (receipt %s)\n%s\n--- B (receipt %s)\n%s",
		rep.Prompt, rep.VerA, rep.VerB, verdict, rep.RunA, rep.OutA, rep.RunB, rep.OutB), nil
}

func toolPromptEval(t tenant.Tenant, args map[string]any) (string, error) {
	name, _ := args["name"].(string)
	dataset, _ := args["dataset"].(string)
	voice, _ := args["voice"].(string)
	if strings.TrimSpace(dataset) == "" {
		return "", fmt.Errorf("prompt_eval needs a dataset — evals/<name>.json")
	}
	askLock.Lock()
	defer askLock.Unlock()
	rep, err := play.EvalPrompt(t.Home, strings.TrimSpace(name), playVersion(args, "version"), strings.TrimSpace(dataset), strings.TrimSpace(voice))
	if err != nil {
		return "", err
	}
	var b strings.Builder
	fmt.Fprintf(&b, "EVAL %s v%d over %q: %d/%d pass\n", rep.Prompt, rep.Version, dataset, rep.Pass, rep.Total)
	for i := range rep.Cases {
		mark := "FAIL"
		if rep.Results[i] {
			mark = "PASS"
		}
		fmt.Fprintf(&b, "  [%s] expected %q got %q\n", mark, rep.Cases[i].Expected, truncateRunes(rep.Got[i], 120))
	}
	return b.String(), nil
}

func toolSeatAsk(t tenant.Tenant, args map[string]any) (string, error) {
	question, _ := args["question"].(string)
	seat, _ := args["seat"].(string)
	voice, _ := args["voice"].(string)
	method, _ := args["method"].(string)
	askLock.Lock()
	defer askLock.Unlock()
	r, err := play.SeatAsk(t.Home, strings.TrimSpace(seat), question, strings.TrimSpace(voice), method)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("SEAT @%s · voice %s · %dms · measurement, not configuration · receipt %s\n%s",
		r.Seat, r.Voice, r.LatencyMs, r.Receipt, r.Output), nil
}

// --- N2 town + flows ------------------------------------------------------

func townDirs(t tenant.Tenant) (ops, board string) {
	return filepath.Join(t.Home, "ops"), filepath.Join(t.Home, "state", "town")
}

func toolTownBeat(t tenant.Tenant, _ map[string]any) (string, error) {
	ops, board := townDirs(t)
	askLock.Lock()
	defer askLock.Unlock()
	rep, err := town.Beat(ops, board, time.Now())
	if err != nil {
		return "", err
	}
	var b strings.Builder
	fmt.Fprintf(&b, "BEAT on %q: issued %d · filed %d · held %d — every filing REVIEW\n",
		t.Name, rep.Issued, rep.Filed, len(rep.Held))
	for _, n := range rep.Worked {
		fmt.Fprintf(&b, "  worked: %s\n", truncateRunes(n, 200))
	}
	for _, n := range rep.Held {
		fmt.Fprintf(&b, "  held: %s\n", truncateRunes(n, 200))
	}
	return b.String(), nil
}

func toolTownStatus(t tenant.Tenant, _ map[string]any) (string, error) {
	ops, board := townDirs(t)
	b := town.OpenBoard(board)
	tasks, err := b.Fold()
	if err != nil {
		return "", err
	}
	worked, err := b.WorkedIDs()
	if err != nil {
		return "", err
	}
	byStatus := map[string]int{}
	for _, task := range tasks {
		byStatus[task.Status]++
	}
	var sb strings.Builder
	fmt.Fprintf(&sb, "TOWN on %q: %d tasks (%d worked) · %d open orders\n",
		t.Name, len(tasks), len(worked), len(town.OpenWorkOrders(ops)))
	statuses := []string{}
	for s := range byStatus {
		statuses = append(statuses, s)
	}
	sort.Strings(statuses)
	for _, s := range statuses {
		fmt.Fprintf(&sb, "  %s: %d\n", s, byStatus[s])
	}
	for _, task := range tasks {
		if task.Status == town.StatusReview && !worked[task.ID] {
			fmt.Fprintf(&sb, "  REVIEW %s %s — %s\n", task.ID, task.SeedKey, truncateRunes(task.Title, 120))
		}
	}
	return sb.String(), nil
}

func flowFace(r flow.Result) string {
	out := fmt.Sprintf("RUN %s: %s · fired %d · %dms",
		r.Run, r.Verdict, len(r.Fired), r.ElapsedMs)
	if r.Verdict == flow.VerdictPaused {
		out += " — resume with flow_resume continue|stop; nothing moves until the hand says so"
	}
	return out
}

func toolFlowSave(t tenant.Tenant, args map[string]any) (string, error) {
	name, _ := args["name"].(string)
	raw, _ := args["spec"].(string)
	if strings.TrimSpace(name) == "" || strings.TrimSpace(raw) == "" {
		return "", fmt.Errorf("flow_save needs a name and a spec JSON {nodes, edges, budget_s?}")
	}
	var doc struct {
		Nodes   []flow.Node `json:"nodes"`
		Edges   []flow.Edge `json:"edges"`
		BudgetS int         `json:"budget_s"`
	}
	if err := json.Unmarshal([]byte(raw), &doc); err != nil {
		return "", fmt.Errorf("flow spec must be JSON: %s", err)
	}
	askLock.Lock()
	defer askLock.Unlock()
	s, err := flow.Save(t.Home, flow.Spec{Name: strings.TrimSpace(name),
		Nodes: doc.Nodes, Edges: doc.Edges, BudgetS: doc.BudgetS})
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("SAVED flow %s v%d — history folds whole, nothing rewritten", s.Name, s.Version), nil
}

func toolFlowGet(t tenant.Tenant, args map[string]any) (string, error) {
	name, _ := args["name"].(string)
	s, err := flow.Get(t.Home, strings.TrimSpace(name), playVersion(args, "version"))
	if err != nil {
		return "", err
	}
	b, _ := json.MarshalIndent(s, "", "  ")
	return string(b), nil
}

func toolFlowList(t tenant.Tenant, _ map[string]any) (string, error) {
	list, err := flow.List(t.Home)
	if err != nil {
		return "", err
	}
	if len(list) == 0 {
		return "no flows yet — fold one with flow_save", nil
	}
	var b strings.Builder
	fmt.Fprintf(&b, "FLOWS — %d:\n", len(list))
	for _, s := range list {
		fmt.Fprintf(&b, "  - %s v%d · %d nodes · budget %ds\n", s.Name, s.Version, len(s.Nodes), s.BudgetS)
	}
	return b.String(), nil
}

// flowInputs reads `inputs` in either shape a caller can honestly send: an
// object (a client building arguments as a map) or a JSON string (a shell).
// Anything else is REFUSED BY NAME rather than quietly becoming {} -- a flow
// that drops its inputs fails on a missing var and blames the spec.
func flowInputs(args map[string]any) (map[string]string, error) {
	v, present := args["inputs"]
	if !present || v == nil {
		return map[string]string{}, nil
	}
	var doc map[string]any
	switch t := v.(type) {
	case map[string]any:
		doc = t
	case string:
		if strings.TrimSpace(t) == "" {
			return map[string]string{}, nil
		}
		if err := json.Unmarshal([]byte(t), &doc); err != nil {
			return nil, fmt.Errorf("flow inputs must be a JSON object: %s", err)
		}
	default:
		return nil, fmt.Errorf("flow inputs must be a JSON object or a JSON "+
			"object as a string; got %T -- refused rather than run with none", v)
	}
	out := map[string]string{}
	for k, val := range doc {
		if sv, ok := val.(string); ok {
			out[k] = sv
			continue
		}
		out[k] = fmt.Sprintf("%v", val)
	}
	return out, nil
}

// councilEngine is flow's Engine with a real Turn: a `run` node puts its
// objective through the world's own Manjuel process, so a workflow gets the
// law gate, the Router and the recompose rather than a bare voice.
type councilEngine struct {
	flow.Engine
	home string
}

func (c councilEngine) Turn(ctx context.Context, objective, feed, method string) (string, error) {
	e, ok := engines.Get(c.home)
	if !ok {
		return "", fmt.Errorf("no engine is open on this world -- env_open first, " +
			"then fire the flow. A `run` node will not start one behind your back")
	}
	res, err := e.Run(objective, feed, method, nil)
	if err != nil {
		return "", err
	}
	if res.Waiting {
		return "", fmt.Errorf("the turn stopped on a question: %q. A flow cannot "+
			"answer it -- the gate is yours (RULE 6). Answer with run_answer, then "+
			"resume the flow", res.Final.Str("prompt"))
	}
	f := res.Final
	out := f.Str("text")
	// The core recomposes its own failure list into the delivery. Append only
	// when it did not -- the news must reach the gate exactly once (LAW 5:
	// what ran is reported from events, and reported once).
	if fails, ok := f["failures"].([]any); ok && len(fails) > 0 &&
		!strings.Contains(out, "NOT EVERYTHING RAN") {
		out += fmt.Sprintf("\n\nNOT EVERYTHING RAN: %v", fails)
	}
	return out, nil
}

func council(home string) flow.Engine { return councilEngine{flow.Production(home), home} }

func toolFlowRun(t tenant.Tenant, args map[string]any) (string, error) {
	name, _ := args["name"].(string)
	inputs, err := flowInputs(args)
	if err != nil {
		return "", err
	}
	s, err := flow.Get(t.Home, strings.TrimSpace(name), playVersion(args, "version"))
	if err != nil {
		return "", err
	}
	askLock.Lock()
	defer askLock.Unlock()
	res, err := flow.Run(t.Home, council(t.Home), s, inputs)
	if err != nil {
		return "", err
	}
	out := flowFace(res)
	st, serr := flow.Status(t.Home, res.Run)
	if serr == nil {
		out += "\n" + st
	}
	return out, nil
}

func toolFlowResume(t tenant.Tenant, args map[string]any) (string, error) {
	run, _ := args["run"].(string)
	decision, _ := args["decision"].(string)
	if strings.TrimSpace(run) == "" {
		return "", fmt.Errorf("flow_resume needs a run — see flow_runs")
	}
	askLock.Lock()
	defer askLock.Unlock()
	res, err := flow.Resume(t.Home, council(t.Home), strings.TrimSpace(run), strings.TrimSpace(decision))
	if err != nil {
		return "", err
	}
	out := flowFace(res)
	st, serr := flow.Status(t.Home, res.Run)
	if serr == nil {
		out += "\n" + st
	}
	return out, nil
}

func toolFlowCancel(t tenant.Tenant, args map[string]any) (string, error) {
	_ = t
	run, _ := args["run"].(string)
	if strings.TrimSpace(run) == "" {
		return "", fmt.Errorf("flow_cancel needs a run")
	}
	return flow.Cancel(strings.TrimSpace(run)), nil
}

func toolFlowStatus(t tenant.Tenant, args map[string]any) (string, error) {
	run, _ := args["run"].(string)
	return flow.Status(t.Home, strings.TrimSpace(run))
}

func toolFlowCompare(t tenant.Tenant, args map[string]any) (string, error) {
	a, _ := args["runa"].(string)
	b, _ := args["runb"].(string)
	return flow.Compare(t.Home, strings.TrimSpace(a), strings.TrimSpace(b))
}

func toolFlowReplay(t tenant.Tenant, args map[string]any) (string, error) {
	run, _ := args["run"].(string)
	if strings.TrimSpace(run) == "" {
		return "", fmt.Errorf("flow_replay needs a run — see flow_runs")
	}
	askLock.Lock()
	defer askLock.Unlock()
	res, err := flow.Replay(t.Home, council(t.Home), strings.TrimSpace(run))
	if err != nil {
		return "", err
	}
	out := flowFace(res) + " · replay — same spec, same inputs, fresh id"
	st, serr := flow.Status(t.Home, res.Run)
	if serr == nil {
		out += "\n" + st
	}
	return out, nil
}

func toolFlowRuns(t tenant.Tenant, args map[string]any) (string, error) {
	f, _ := args["flow"].(string)
	return flow.ListRuns(t.Home, strings.TrimSpace(f), 0)
}

// --- N5 team chat ----------------------------------------------------------

func toolTeamSend(t tenant.Tenant, args map[string]any) (string, error) {
	platform, _ := args["platform"].(string)
	channel, _ := args["channel"].(string)
	content, _ := args["content"].(string)
	actor, _ := args["actor"].(string)
	askLock.Lock()
	defer askLock.Unlock()
	m, err := team.Send(t.Home, platform, channel, strings.TrimSpace(actor), content)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("SENT %s/%s · receipt %s", m.Platform, m.Channel, m.Receipt), nil
}

func toolTeamStatus(t tenant.Tenant, _ map[string]any) (string, error) {
	pres := team.Status(t.Home)
	var b strings.Builder
	fmt.Fprintf(&b, "TEAM BRIDGE on %q:\n", t.Name)
	for _, p := range pres {
		state := "disconnected"
		if p.Connected {
			state = "connected"
		}
		last := "never"
		if p.LastSend != "" {
			last = p.LastSend
		}
		fmt.Fprintf(&b, "  - %s: %s · last send %s\n", p.Platform, state, last)
	}
	return b.String(), nil
}

func toolTeamHistory(t tenant.Tenant, args map[string]any) (string, error) {
	channel, _ := args["channel"].(string)
	platform, _ := args["platform"].(string)
	last := 0
	switch n := args["last"].(type) {
	case float64:
		last = int(n)
	case int:
		last = n
	}
	hist, err := team.History(t.Home, strings.TrimSpace(channel), strings.TrimSpace(platform), last)
	if err != nil {
		return "", err
	}
	if len(hist) == 0 {
		return "the bridge holds nothing yet — silence is honest", nil
	}
	var b strings.Builder
	for _, m := range hist {
		fmt.Fprintf(&b, "%s %s/%s · %s · receipt %s\n  %s\n",
			m.Direction, m.Platform, m.Channel, m.TS, m.Receipt, truncateRunes(m.Content, 300))
	}
	return b.String(), nil
}

func toolTeamIngest(t tenant.Tenant, args map[string]any) (string, error) {
	platform, _ := args["platform"].(string)
	body, _ := args["body"].(string)
	signature, _ := args["signature"].(string)
	askLock.Lock()
	defer askLock.Unlock()
	m, dup, challenge, err := team.Ingest(t.Home, platform, []byte(body), signature)
	if err != nil {
		return "", err
	}
	if challenge != "" {
		return fmt.Sprintf("CHALLENGE %s", challenge), nil
	}
	if dup {
		return "duplicate delivery — already stored, never twice", nil
	}
	return fmt.Sprintf("INGESTED %s/%s · receipt %s", m.Platform, m.Channel, m.Receipt), nil
}

// --- N6 auth ---------------------------------------------------------------
// The gate behind the gate: keys are scoped to tenants, plaintext shows
// once, the audit line remembers every mint and fold.

func authTenants(args map[string]any) []string {
	raw, _ := args["tenants"].(string)
	var out []string
	for _, s := range strings.Split(raw, ",") {
		if s = strings.TrimSpace(strings.ToLower(s)); s != "" {
			out = append(out, s)
		}
	}
	return out
}

// authExisting enforces re-proof: on a non-empty store the caller names a
// live key. The bootstrap hand (empty store) passes freely.
func authExisting(t tenant.Tenant, args map[string]any) error {
	if auth.Empty(t.Home) {
		return nil
	}
	key, _ := args["key"].(string)
	if _, err := auth.Verify(t.Home, strings.TrimSpace(key)); err != nil {
		return fmt.Errorf("refused: key management names a live key — possession re-proved, like sudo")
	}
	return nil
}

func toolAuthCreate(t tenant.Tenant, args map[string]any) (string, error) {
	name, _ := args["name"].(string)
	if err := authExisting(t, args); err != nil {
		return "", err
	}
	tenants := authTenants(args)
	if len(tenants) == 0 {
		tenants = []string{t.Name}
	}
	askLock.Lock()
	defer askLock.Unlock()
	key, rec, err := auth.Create(t.Home, strings.TrimSpace(name), tenants, "mcp")
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("MINTED %s for %q on %q — copy it now, it never shows again\n%s",
		rec.ID, rec.Name, t.Name, key), nil
}

func toolAuthList(t tenant.Tenant, _ map[string]any) (string, error) {
	list := auth.List(t.Home)
	if len(list) == 0 {
		return "no live keys — the gate stands open (bootstrap)", nil
	}
	var b strings.Builder
	fmt.Fprintf(&b, "KEYS on %q — %d live:\n", t.Name, len(list))
	for _, k := range list {
		fmt.Fprintf(&b, "  %s %q · tenants [%s] · minted %s\n",
			k.ID, k.Name, strings.Join(k.Tenants, ","), k.Created)
	}
	return b.String(), nil
}

func toolAuthRevoke(t tenant.Tenant, args map[string]any) (string, error) {
	id, _ := args["id"].(string)
	if strings.TrimSpace(id) == "" {
		return "", fmt.Errorf("auth_key_revoke needs an id — see auth_key_list")
	}
	if err := authExisting(t, args); err != nil {
		return "", err
	}
	askLock.Lock()
	defer askLock.Unlock()
	if err := auth.Revoke(t.Home, strings.TrimSpace(id), "mcp"); err != nil {
		return "", err
	}
	return fmt.Sprintf("REVOKED %s on %q — folded, kept for audit", strings.TrimSpace(id), t.Name), nil
}

func toolAuthVerify(t tenant.Tenant, args map[string]any) (string, error) {
	key, _ := args["key"].(string)
	rec, err := auth.Verify(t.Home, strings.TrimSpace(key))
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("VERIFIED %s on %q · tenants [%s]", rec.ID, t.Name, strings.Join(rec.Tenants, ",")), nil
}

func toolTrustList(t tenant.Tenant, _ map[string]any) (string, error) {
	return trust.Render(t.Home), nil
}

// --- receipts ---------------------------------------------------------------
func sha256File(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func sha256Bytes(b []byte) string {
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:])
}

// --- helpers ----------------------------------------------------------------

func orientForTenant(t tenant.Tenant) (string, error) {
	return orient.ForTenant(t)
}

func truncateRunes(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n])
}

func firstLines(s string, n int) string {
	lines := strings.Split(strings.TrimRight(s, "\r\n"), "\n")
	if len(lines) > n {
		lines = lines[:n]
	}
	return strings.Join(lines, "\n")
}

// splitCommand splits a command string into fields, honoring single and
// double quotes so paths with spaces survive.
func splitCommand(s string) []string {
	var out []string
	var cur bytes.Buffer
	inQuote := false
	quoteChar := byte(0)
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case inQuote:
			if c == quoteChar {
				inQuote = false
			} else {
				cur.WriteByte(c)
			}
		default:
			switch c {
			case '"', '\'':
				inQuote = true
				quoteChar = c
			case ' ', '\t':
				if cur.Len() > 0 {
					out = append(out, cur.String())
					cur.Reset()
				}
			default:
				cur.WriteByte(c)
			}
		}
	}
	if cur.Len() > 0 {
		out = append(out, cur.String())
	}
	return out
}

// --- the landed tools -------------------------------------------------------

func toolReadHandoffs(t tenant.Tenant, _ map[string]any) (string, error) {
	logPath := t.LogPath()
	if logPath == "" {
		return "", fmt.Errorf("no handoffs path configured for project %q", t.Name)
	}
	fi, err := os.Stat(logPath)
	if err != nil {
		return "", fmt.Errorf("handoffs missing for %q: %s", t.Name, logPath)
	}
	var b strings.Builder
	if fi.IsDir() {
		entries, err := os.ReadDir(logPath)
		if err != nil {
			return "", err
		}
		names := make([]string, 0, len(entries))
		for _, e := range entries {
			if !e.IsDir() {
				names = append(names, e.Name())
			}
		}
		sort.Strings(names)
		for _, n := range names {
			fp := filepath.Join(logPath, n)
			body, err := os.ReadFile(fp)
			if err != nil {
				continue
			}
			sha, _ := sha256File(fp)
			fmt.Fprintf(&b, "%s · sha256 %s\n\n%s\n\n", n, sha, string(body))
		}
	} else {
		body, err := os.ReadFile(logPath)
		if err != nil {
			return "", err
		}
		sha, _ := sha256File(logPath)
		fmt.Fprintf(&b, "%s · sha256 %s\n\n%s\n", filepath.Base(logPath), sha, string(body))
	}
	return b.String(), nil
}

func toolListDoctrine(t tenant.Tenant, _ map[string]any) (string, error) {
	var b strings.Builder
	found := 0
	for _, dir := range t.DoctrineDirs() {
		entries, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		for _, e := range entries {
			if e.IsDir() {
				continue
			}
			fmt.Fprintf(&b, "  %s\n", e.Name())
			found++
		}
	}
	if found == 0 {
		return fmt.Sprintf("The hold is empty — no doctrine carried for project %q.", t.Name), nil
	}
	return fmt.Sprintf("THE CARRIED LAW — %d documents, read-only:\n%s", found, b.String()), nil
}

const doctrineCap = 60_000

func toolReadDoctrine(t tenant.Tenant, args map[string]any) (string, error) {
	name, _ := args["name"].(string)
	name = strings.TrimSpace(name)
	if name == "" {
		return "", fmt.Errorf("read_doctrine needs a name — try list_doctrine first")
	}
	want := strings.ToLower(name)
	wantBase := strings.ToLower(strings.TrimSuffix(name, filepath.Ext(name)))
	for _, dir := range t.DoctrineDirs() {
		entries, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		for _, e := range entries {
			if e.IsDir() {
				continue
			}
			base := strings.ToLower(e.Name())
			baseNoExt := strings.ToLower(strings.TrimSuffix(e.Name(), filepath.Ext(e.Name())))
			if base == want || base == want+".md" || baseNoExt == wantBase {
				fp := filepath.Join(dir, e.Name())
				body, err := os.ReadFile(fp)
				if err != nil {
					continue
				}
				sha, _ := sha256File(fp)
				text := string(body)
				if len([]rune(text)) > doctrineCap {
					text = truncateRunes(text, doctrineCap) +
						fmt.Sprintf("\n\n[truncated honestly at %d characters — the whole document is on disk under sha256 %s]", doctrineCap, sha)
				}
				return fmt.Sprintf("%s (%s) · sha256 %s\n\n%s", e.Name(), filepath.Base(dir), sha, text), nil
			}
		}
	}
	return "", fmt.Errorf("No such document in the hold for %q: %s. An absent name is denied honestly — try list_doctrine.", t.Name, name)
}

// WallLaw is quoted when a path falls outside a tenant's home.
const WallLaw = `THE WALL — everything about a project stays inside its home. ` +
	`"Scope is a wall, not a suggestion" (the Servant's Law, Article I). ` +
	`Do not touch, read, or list ground outside it.`

func toolCheckWall(t tenant.Tenant, args map[string]any) (string, error) {
	raw, _ := args["path"].(string)
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "", fmt.Errorf("check_the_wall needs a path")
	}
	root := t.WallRoot()
	target := raw
	if !filepath.IsAbs(target) {
		target = filepath.Join(root, raw)
	}
	absTarget, err := filepath.Abs(target)
	if err != nil {
		return "", err
	}
	absRoot, err := filepath.Abs(root)
	if err != nil {
		return "", err
	}
	inside := absTarget == absRoot || strings.HasPrefix(absTarget, absRoot+string(filepath.Separator))
	if inside {
		return fmt.Sprintf("INSIDE the wall: %s\nWithin %q — a seat may work here under the standing law.", absTarget, t.Name), nil
	}
	return fmt.Sprintf("REFUSED — outside the wall: %s\n\"%s\" Prepare a packet instead; only the operator lands work outside.", absTarget, WallLaw), nil
}

func toolStateMatrix(t tenant.Tenant, _ map[string]any) (string, error) {
	type row struct {
		Key     string `json:"key"`
		Present bool   `json:"present"`
		Bytes   int    `json:"bytes"`
		Head    string `json:"head,omitempty"`
	}
	paths := map[string]string{}
	if p := t.RoadPath(); p != "" {
		paths["road"] = p
	}
	if p := t.StatePath(); p != "" {
		paths["state"] = p
	}
	if p := t.LogPath(); p != "" {
		paths["log"] = p
	}
	rows := []row{}
	plain := strings.Builder{}
	plain.WriteString("THE MATRIX — state = fold(record)\n")
	for _, k := range []string{"road", "state", "log"} {
		p, ok := paths[k]
		present := false
		n := 0
		head := ""
		if ok {
			if b, err := os.ReadFile(p); err == nil {
				present = true
				n = len(b)
				head = firstLines(string(b), 3)
			}
		}
		rows = append(rows, row{Key: k, Present: present, Bytes: n, Head: head})
		status := "absent"
		if present {
			status = fmt.Sprintf("%d bytes", n)
		}
		fmt.Fprintf(&plain, "  %-6s %s\n", k, status)
	}
	plain.WriteString("\n  (folded from the named project's record; absence named honestly.)\n")
	js, _ := json.MarshalIndent(map[string]any{
		"project":  t.Name,
		"equation": "state = fold(record)",
		"rows":     rows,
	}, "", "  ")
	plain.WriteString("\n")
	plain.WriteString(string(js))
	return plain.String(), nil
}

const askTimeout = 600 * time.Second

// readonlyGroundMarkers name the operator's read-only source grounds that
// atlas folds but must never bootstrap or forward into. manjuel's
// Steward().awaken() writes to secondbrain/.../state — triggering it from the
// MCP would violate the read-only law (AGENTS / STOP). The guard inspects the
// engine command only; the question text is never a path.
var readonlyGroundMarkers = []string{
	`\estate\`, `/estate/`,
	`\secondbrain\`, `/secondbrain/`,
	"manjuel.py", `manjuel\core`, `manjuel/core`,
}

// touchesReadonlyGround reports whether a command string would reach a
// read-only source ground. It matches the known ground markers, and also
// resolves any path token to an absolute path and checks ancestry, so a
// relative "../secondbrain/manjuel.py" is caught too.
func touchesReadonlyGround(cmd string) bool {
	low := strings.ToLower(cmd)
	for _, m := range readonlyGroundMarkers {
		if strings.Contains(low, m) {
			return true
		}
	}
	for _, f := range splitCommand(cmd) {
		if !strings.ContainsAny(f, `\/`) {
			continue
		}
		abs, err := filepath.Abs(f)
		if err != nil {
			continue
		}
		a := strings.ToLower(filepath.Clean(abs))
		if strings.Contains(a, `\estate\`) || strings.Contains(a, `/estate/`) ||
			strings.Contains(a, `\secondbrain\`) || strings.Contains(a, `/secondbrain/`) {
			return true
		}
	}
	return false
}

func toolAskSteward(t tenant.Tenant, args map[string]any) (string, error) {
	q, _ := args["question"].(string)
	q = strings.TrimSpace(q)
	if q == "" {
		return "", fmt.Errorf("ask_steward needs a question — he cannot weigh the empty string")
	}
	if t.Engine == "" {
		return "", fmt.Errorf("ask_steward has no engine wired for project %q: nothing to wake. The operator wires one with --engine.", t.Name)
	}
	// ZERO-WRITE GUARD (B1 hardening): atlas is self-contained and must never
	// boot or forward to a read-only ground. The operator lands everything;
	// ask_steward refuses until its own rebuilt engine lands (F1).
	if touchesReadonlyGround(t.Engine) {
		return "", fmt.Errorf("REFUSED — ask_steward will not boot or forward to a read-only ground (estate/, secondbrain/, manjuel core). atlas is self-contained; the operator lands everything.")
	}
	fields := splitCommand(t.Engine)
	if len(fields) == 0 {
		return "", fmt.Errorf("ask_steward engine command is empty for %q", t.Name)
	}
	cmdArgs := append(append([]string{}, fields[1:]...), q)
	askLock.Lock()
	defer askLock.Unlock()
	// Through the one spawn contract (ADR-006 item 5). The bound, the
	// closed stdin and the kept streams all come from there now; what stays
	// local is the only part that is this tool's own -- the WORDS of the
	// refusal, which name the engine rather than the exit code.
	res := spawn(fields[0], cmdArgs, spawnOpts{Dir: t.Home, Timeout: askTimeout})
	if res.TimedOut {
		return "", fmt.Errorf("REFUSED — the weighing did not finish inside %d seconds; the engine may be cold. Nothing is claimed.", int(askTimeout.Seconds()))
	}
	if res.Err != nil {
		tail := strings.Split(strings.TrimRight(res.Stderr, "\r\n"), "\n")
		last := ""
		if len(tail) > 0 {
			last = tail[len(tail)-1]
		}
		return "", fmt.Errorf("REFUSED — the engine did not answer (exit %v): %s", res.Err, last)
	}
	out := strings.TrimSpace(res.Stdout)
	if out == "" {
		return "", fmt.Errorf("REFUSED — the engine said nothing")
	}
	return out, nil
}

func toolRemember(t tenant.Tenant, args map[string]any) (string, error) {
	text, _ := args["text"].(string)
	text = strings.TrimSpace(text)
	if text == "" {
		return "", fmt.Errorf("remember needs some text to hold")
	}
	dir := filepath.Join(t.Home, "state")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	path := filepath.Join(dir, "remembered.jsonl")
	stamp := time.Now().UTC().Format(time.RFC3339)
	rec := map[string]any{
		"ts":        stamp,
		"testimony": true,
		"project":   t.Name,
		"text":      text,
	}
	b, err := json.Marshal(rec)
	if err != nil {
		return "", err
	}
	line := string(b) + "\n"
	askLock.Lock()
	defer askLock.Unlock()
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return "", err
	}
	defer f.Close()
	if _, err := f.WriteString(line); err != nil {
		return "", err
	}
	sha := sha256Bytes([]byte(line))
	return fmt.Sprintf("REMEMBERED (testimony, staged for operator ascend) — %s · sha256 %s\n%s", stamp, sha, text), nil
}

func toolReadPlan(t tenant.Tenant, args map[string]any) (string, error) {
	which, _ := args["which"].(string)
	which = strings.TrimSpace(which)
	if which == "" {
		return "", fmt.Errorf("read_plan needs a name — e.g. road, state, catalog, acceptance, charter, or a plans/ path")
	}
	p := t.PlanPath(which)
	if p == "" {
		return "", fmt.Errorf("No such plan %q for project %q. An absent name is denied honestly — try road/state/catalog/acceptance/charter.", which, t.Name)
	}
	body, err := os.ReadFile(p)
	if err != nil {
		return "", fmt.Errorf("plan %q present in the map but unreadable: %s", which, err)
	}
	sha, _ := sha256File(p)
	return fmt.Sprintf("%s · sha256 %s\n\n%s", filepath.Base(p), sha, string(body)), nil
}

// --- THE MESH (B2) ----------------------------------------------------------

// meshDir roots one tenant's mesh ground: the channel IS the project.
func meshDir(t tenant.Tenant) string {
	return filepath.Join(t.Home, "state", "mesh")
}

// meshChan resolves the channel: absent means the caller's own project;
// anything else is refused by name — cross-project chatter is a packet,
// not a message.
func meshChan(t tenant.Tenant, args map[string]any) (string, error) {
	c, _ := args["chan"].(string)
	c = strings.TrimSpace(c)
	if c == "" {
		return t.Name, nil
	}
	if !strings.EqualFold(c, t.Name) {
		return "", fmt.Errorf("REFUSED — chan %q is not your ground %q. %s",
			c, t.Name, WallLaw)
	}
	return t.Name, nil
}

func meshCites(args map[string]any) []string {
	switch c := args["cites"].(type) {
	case string:
		var out []string
		for _, s := range strings.Split(c, ",") {
			if s = strings.TrimSpace(s); s != "" {
				out = append(out, s)
			}
		}
		return out
	case []any:
		var out []string
		for _, v := range c {
			if s, ok := v.(string); ok && strings.TrimSpace(s) != "" {
				out = append(out, strings.TrimSpace(s))
			}
		}
		return out
	}
	return nil
}

func meshNum(args map[string]any, key string) int {
	switch n := args[key].(type) {
	case float64:
		return int(n)
	case int:
		return n
	}
	return 0
}

func meshBool(args map[string]any, key string) bool {
	b, _ := args[key].(bool)
	return b
}

func toolMeshEnroll(t tenant.Tenant, args map[string]any) (string, error) {
	member, _ := args["member"].(string)
	pub, _ := args["pub"].(string)
	if strings.TrimSpace(member) == "" || strings.TrimSpace(pub) == "" {
		return "", fmt.Errorf("mesh_enroll needs a member id and a pub (64 bytes hex)")
	}
	askLock.Lock()
	defer askLock.Unlock()
	mb, err := mesh.Enroll(meshDir(t), strings.TrimSpace(member), strings.TrimSpace(pub))
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("ENROLLED %q on channel %q · mark %s", member, t.Name, mb.Mark), nil
}

func toolMeshPost(t tenant.Tenant, args map[string]any) (string, error) {
	text, _ := args["text"].(string)
	to, _ := args["to"].(string)
	if strings.TrimSpace(to) == "" {
		return "", fmt.Errorf("mesh_post needs text and to (a member, @channel, or @everyone)")
	}
	chanName, err := meshChan(t, args)
	if err != nil {
		return "", err
	}
	mode, _ := args["mode"].(string)
	mode = strings.TrimSpace(mode)
	if mode == "" {
		mode = mesh.ModeOpen
	}
	kind, _ := args["kind"].(string)
	kind = strings.TrimSpace(kind)
	if kind == "" {
		kind = "mesh"
	}
	actor, _ := args["actor"].(string)
	actor = strings.TrimSpace(actor)
	if actor == "" {
		return "", fmt.Errorf("mesh_post needs an actor — every message names its pen")
	}
	askLock.Lock()
	defer askLock.Unlock()
	e, head, err := mesh.Post(meshDir(t), chanName, actor, strings.TrimSpace(to),
		mode, text, kind, meshCites(args))
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("POSTED n=%d · %s · head %s\n  face: %s",
		e.Payload.N, e.Hash[:16], head.Hash[:16], faceOf(e.Payload.Ct, e.Payload.Mode)), nil
}

func faceOf(ct, mode string) string {
	if mode == mesh.ModeOpen {
		return truncateRunes(ct, 160)
	}
	return "(sealed: ciphertext at rest)"
}

func toolMeshRead(t tenant.Tenant, args map[string]any) (string, error) {
	if _, err := meshChan(t, args); err != nil {
		return "", err
	}
	actor, _ := args["actor"].(string)
	results, err := mesh.Read(meshDir(t), strings.TrimSpace(actor), meshNum(args, "last"), meshBool(args, "reveal"))
	if err != nil {
		return "", err
	}
	var b strings.Builder
	for _, r := range results {
		face := r.Plaintext
		if r.Withheld != "" {
			face = "WITHHELD: " + r.Withheld
		}
		fmt.Fprintf(&b, "n=%d %s %s -> %s · %s\n  %s\n",
			r.Entry.Payload.N, r.Entry.Actor, r.Entry.Payload.Mode,
			r.Entry.Payload.To, r.Entry.Hash[:16], truncateRunes(face, 300))
	}
	if len(results) == 0 {
		fmt.Fprintf(&b, "channel %q holds nothing yet", t.Name)
	}
	return b.String(), nil
}

func toolMeshChain(t tenant.Tenant, args map[string]any) (string, error) {
	if _, err := meshChan(t, args); err != nil {
		return "", err
	}
	v, err := mesh.Chain(meshDir(t))
	if err != nil {
		return "", err
	}
	var b strings.Builder
	fmt.Fprintf(&b, "MESH %s — %s\n", v.Overall, v.Detail)
	names := make([]string, 0, len(v.Chains))
	for n := range v.Chains {
		names = append(names, n)
	}
	sort.Strings(names)
	for _, n := range names {
		fmt.Fprintf(&b, "  %-16s %s\n", n, v.Chains[n])
	}
	return b.String(), nil
}

func toolMeshCite(t tenant.Tenant, args map[string]any) (string, error) {
	targets := meshCites(args)
	if len(targets) == 0 {
		return "", fmt.Errorf("mesh_cite needs targets (hash cites) and text saying why")
	}
	text, _ := args["text"].(string)
	to, _ := args["to"].(string)
	to = strings.TrimSpace(to)
	if to == "" {
		to = "@channel"
	}
	chanName, err := meshChan(t, args)
	if err != nil {
		return "", err
	}
	actor, _ := args["actor"].(string)
	actor = strings.TrimSpace(actor)
	if actor == "" {
		return "", fmt.Errorf("mesh_cite needs an actor — every cite names its pen")
	}
	askLock.Lock()
	defer askLock.Unlock()
	e, head, err := mesh.Post(meshDir(t), chanName, actor, to, mesh.ModeOpen, text, "cite", targets)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("CITED %d target(s) at n=%d · %s · head %s",
		len(targets), e.Payload.N, e.Hash[:16], head.Hash[:16]), nil
}

// toolUsToVC converts a .us file to a W3C Verifiable Credential.
func toolUsToVC(t tenant.Tenant, usPath string) (string, error) {
	// Resolve path relative to tenant home
	if !filepath.IsAbs(usPath) {
		usPath = filepath.Join(t.Home, usPath)
	}
	issuerDID := fmt.Sprintf("did:atlas:1512741580b7239b:operator")
	v, err := vc.FromFile(usPath, issuerDID)
	if err != nil {
		return "", fmt.Errorf("us_to_vc: %w", err)
	}
	data, err := vc.ToJSON(v)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// toolTenantListReg enumerates the carried registry (N0 real): every
// tenant by name with its RBAC mode + trust-grant count. Strangers never
// appear — the registry is the enrollment law.
func toolTenantListReg(reg *tenant.Registry, t tenant.Tenant) (string, error) {
	names := reg.Names()
	var b strings.Builder
	fmt.Fprintf(&b, "TENANTS — %d carried project(s):\n", len(names))
	for _, n := range names {
		tn, err := reg.Resolve(n)
		if err != nil {
			continue
		}
		mode := "open mode"
		if len(tn.Policy.Assign) > 0 {
			mode = fmt.Sprintf("%d assigned", len(tn.Policy.Assign))
		}
		ng := len(trust.Load(tn.Home).Grants)
		mark := ""
		if n == t.Name {
			mark = " (you are here)"
		}
		fmt.Fprintf(&b, "  - %s · %s · %d trust grant(s)%s\n", n, mode, ng, mark)
	}
	return b.String(), nil
}

// toolTenantList keeps the old single-tenant shape for direct callers.
func toolTenantList(t tenant.Tenant, _ map[string]any) (string, error) {
	mode := "open mode"
	if len(t.Policy.Assign) > 0 {
		mode = fmt.Sprintf("%d assigned", len(t.Policy.Assign))
	}
	return fmt.Sprintf("TENANT — %s (%s)", t.Name, mode), nil
}

// toolTenantRBACAssign assigns a role to an agent in a tenant's RBAC policy.
func toolTenantRBACAssign(t tenant.Tenant, args map[string]any) (string, error) {
	actor, _ := args["actor"].(string)
	if actor == "" {
		return "", fmt.Errorf("tenant_rbac_assign needs an actor")
	}
	role, _ := args["role"].(string)
	if role == "" {
		return "", fmt.Errorf("tenant_rbac_assign needs a role")
	}
	if err := t.AssignRole(actor, role); err != nil {
		return "", err
	}
	if err := t.SavePolicy(); err != nil {
		return "", fmt.Errorf("rbac assigned but failed to persist: %w", err)
	}
	return fmt.Sprintf("ASSIGNED role %q to agent %q in tenant %q", role, actor, t.Name), nil
}

// toolTenantRBACCheck checks if an agent has permission for a tool.
func toolTenantRBACCheck(t tenant.Tenant, args map[string]any) (string, error) {
	actor, _ := args["actor"].(string)
	if actor == "" {
		return "", fmt.Errorf("tenant_rbac_check needs an actor")
	}
	toolName, _ := args["tool"].(string)
	if toolName == "" {
		return "", fmt.Errorf("tenant_rbac_check needs a tool")
	}
	allowed, role, reason := t.CheckRBAC(actor, toolName)
	if allowed {
		if role == "" {
			return fmt.Sprintf("ALLOWED — %s on %s (open mode)", actor, t.Name), nil
		}
		return fmt.Sprintf("ALLOWED — %s (role %q) on %s", actor, role, t.Name), nil
	}
	return fmt.Sprintf("DENIED — %s (role %q) on %s: %s", actor, role, t.Name, reason), nil
}

// toolTenantTrustReg validates names against the registry + surface,
// persists the grant in the caller's home (wall law), and receipts it.
// Forbidden verbs are never delegable — absent by construction, refused
// by name here too.
func toolTenantTrustReg(reg *tenant.Registry, t tenant.Tenant, args map[string]any) (string, error) {
	from, _ := args["from_project"].(string)
	if strings.TrimSpace(from) == "" {
		return "", fmt.Errorf("tenant_trust needs from_project")
	}
	to, _ := args["to_project"].(string)
	if strings.TrimSpace(to) == "" {
		return "", fmt.Errorf("tenant_trust needs to_project")
	}
	toolName, _ := args["tool"].(string)
	if strings.TrimSpace(toolName) == "" {
		return "", fmt.Errorf("tenant_trust needs a tool")
	}
	action, _ := args["action"].(string)
	if action != "allow" && action != "deny" {
		return "", fmt.Errorf("tenant_trust action must be 'allow' or 'deny', got %q", action)
	}
	from = strings.ToLower(strings.TrimSpace(from))
	to = strings.ToLower(strings.TrimSpace(to))
	toolName = strings.TrimSpace(toolName)
	for _, f := range []string{"approve", "ascend", "merge", "commit", "push", "delete", "reject", "promote"} {
		if strings.EqualFold(toolName, f) {
			return "", fmt.Errorf("refused: %q is a forbidden verb — absent by construction, never delegable", toolName)
		}
	}
	if !reg.Has(from) {
		return "", fmt.Errorf("unknown project %q: not a carried tenant (from_project)", from)
	}
	if !reg.Has(to) {
		return "", fmt.Errorf("unknown project %q: not a carried tenant (to_project)", to)
	}
	if _, err := trust.Upsert(t.Home, trust.Grant{From: from, To: to, Tool: toolName, Action: action}); err != nil {
		return "", err
	}
	sha, _ := sha256File(filepath.Join(t.Home, "state", "trust.json"))
	return fmt.Sprintf("TRUST %s %s: %s → %s (witnessed state/trust.json · sha256 %s)", action, toolName, from, to, sha), nil
}

// toolTenantTrust grants or revokes cross-tenant trust (legacy shape).
func toolTenantTrust(t tenant.Tenant, args map[string]any) (string, error) {
	from, _ := args["from_project"].(string)
	if from == "" {
		return "", fmt.Errorf("tenant_trust needs from_project")
	}
	to, _ := args["to_project"].(string)
	if to == "" {
		return "", fmt.Errorf("tenant_trust needs to_project")
	}
	toolName, _ := args["tool"].(string)
	if toolName == "" {
		return "", fmt.Errorf("tenant_trust needs a tool")
	}
	action, _ := args["action"].(string)
	if action != "allow" && action != "deny" {
		return "", fmt.Errorf("tenant_trust action must be 'allow' or 'deny', got %q", action)
	}
	return fmt.Sprintf("TRUST %s %s: %s → %s", action, toolName, from, to), nil
}
