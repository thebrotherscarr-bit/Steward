# Changelog

All notable changes to ATLAS will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

Versions are plain semver from 0.1.2 on. Through 0.1.1 they carried a build
tag naming the stone that cut them — `0.1.0+a1` through `0.1.1+f1`. The
operator struck the moniker 2026-09-10: *"remove the moniker for the stones,
no letters in my versions."* Released headers below keep the tag they shipped
under, because they are the record of what happened.

## [Unreleased]

### The repair path is judged too, and the verdict now means something

`recheck -> land always`. A run that failed its requirement, repaired and
rechecked arrived at the hand with **no judgement of the repaired work** — the
same fault as the original green-on-wrong-code, moved one edge down. It was the
last of the three holes that firing this flow found, and the only one left open
when the other two landed.

**Fixed — `proof`, a second eval on `recheck`, holding the repair to the SAME
expectation.** `coder` is at v12, eight nodes.

**IT HAS NO FAIL EDGE, AND THAT IS THE DESIGN.** An eval that fails with no
fail edge stops the run (`run.go`: `if !hasFailEdge(...) { return VerdictFail }`),
and there is nothing to steer to anyway — the retry is UNROLLED, so there is no
second repair. Work that still does not meet the requirement must not be
OFFERED for landing. So the verdict carries information it did not before:

    PAUSED   it passed, and your hand decides
    FAIL     it did not, and no gate is offered for it

Nothing is thrown away either way: every attempt stays in the workspace with
what each run said.

Strokes: `TestARepairThatWorksReachesTheGate` — judge fails, repair and recheck
fire, proof passes, the run PAUSES at the gate with all four named;
`TestARepairThatDidNotWorkNeverReachesTheGate` — the same path with a repair
that did not fix it FAILS, never fires `land`, and never sets a paused node.
The flow lives in gitignored runtime state, so the strokes are how this shape
travels at all.

**Also measured live, and it closes a gap in the previous landing's own
judgement.** That landing noted the pass side had never been proven on real
code — every live run had ended verdict-fail. It has now: objective "print the
6th Fibonacci number", `FIB6: 8` expected, and the coder got it first try —
artifact prints `FIB6: 8`, the evidence block carries it, verdict `pass`, gate.

### An eval scores evidence, and prose is not scored at all

**The run that forced it.** With the correctness check in, the coder was asked
for a script printing `FIB6: 8`. It wrote a fibonacci that never sets
`fib_sequence[1]`, so it printed `FIB6: 0`. **The verdict passed.** The seat
had reported the failure perfectly — *"printed `FIB6: 0`, which is not the
expected output of `FIB6: 8`"* — and a `contains "FIB6: 8"` found the marker
inside the clause saying it did not match.

Requiring the verdict block (landed an hour earlier) did not stop it: the block
was present, because `run_python` really had run. **Evidence that something ran
is not evidence that the marker came from what ran.** And the second road is
worse — naming the marker in the objective puts it in the brief, the brief puts
it in the node's objective, and the seat quotes it. The guidance to name the
marker was manufacturing the false pass.

**Fixed — for a `run` node, the check reads only the machine's lines.**

    evidenceOf()     the text after the verdict marker, and whether there is
                     any. The LAST marker wins -- belt to the braces below.
    flow/run.go      an eval judging a `run` node scores that and nothing
                     else. The answer stays whole as what a person reads at
                     the gate; it is simply no longer scoreable.

**And the marker itself is now unforgeable.** `appendVerdicts` used to SKIP
when a marker was already present — "the news reaches the gate exactly once".
It does, but a SEAT can write that string, and a seat that did would have
suppressed the machine's block and left its own words sitting exactly where an
eval now reads evidence from. It is strip-then-append: every seat-written
marker line is removed, then the real block is written. A turn with no verdicts
leaves no marker at all, because a suppressed block is indistinguishable from
an invented one.

`TestAppendVerdicts`' once-only assertion was REWRITTEN the same day it was
written: it held the IMPLEMENTATION (byte-identical on a second call) where the
property is what matters (exactly one marker, the real lines under it). The
guard is the same guard.

Strokes: `TestTheVerdictScoresEvidenceAndNotProse` carries the real answer —
requirement quoted, failure honestly reported, evidence saying `FIB6: 0` — and
must fail, with the right-output twin passing so the rule did not become a
refusal of everything. `TestAnObjectiveCannotSatisfyItself` holds the other
road. `TestARunNodeThatCalledNoToolCannotBeJudged` and
`TestAVoiceIsJudgedWithoutToolEvidence` still stand: an `ask`, `prompt` or
`memory` node holds no tools by definition and is judged on its answer, which
is the only thing it has.

Measured live, re-firing the exact case that had passed:

    prose     contains "FIB6: 8"   True
    evidence  contains "FIB6: 8"   False
    evidence  run_python: RAN: fibonacci.py / --- stdout --- / FIB6: 5
    verdict   fail -> repair -> recheck -> land (gate)

**Still open, and it is the last of them:** `recheck -> land` is UNJUDGED. Only
`verify` is scored, so a run that fails the verdict, repairs and rechecks
reaches the gate with no judgement of the repaired work.

### No evidence is not a verdict

**How it was found: by the run immediately after the correctness check
landed.** A `verify` node came back in **5.6 seconds** with no verdict block at
all — it had called no tool — and the eval failed it. Taking the fail edge was
right. Recording it as `fail: expected contains "X"` was not: failing because
the work was WRONG and failing because NOBODY WATCHED THE WORK are different
facts, and a reader at the gate could not tell them apart.

**And the pass side was the real hole.** The marker a check hunts is a string,
and a seat can WRITE the string without anything having run. That is the same
laundering that made a pasted `RAN:` pass earlier the same day, arriving by a
new road: not a marker that travelled between nodes, but one a seat simply
asserted. A check that accepts it is scoring testimony again (LAW 5).

**Fixed — an eval judging a `run` node requires the machine's own block before
it judges at all.**

    play.ToolVerdictHead   the marker moved to `play`, which imports nothing
                           of ours. `tools` WRITES the block and `flow` now
                           READS it; `tools` imports `flow`, so it could live
                           in neither, and two copies of the string would be
                           one rule with two spellings.
    flow/run.go            execNode takes the spec's nodes, so an eval can ask
                           what KIND the node it judges is. A `run` node whose
                           answer carries no block returns
                           `fail: NO EVIDENCE -- <node> is a run node that
                           called no tool`, and says nothing was judged.

**IT CANNOT PASS, and that is the point rather than a nicety.** Requiring the
block means the evidence was machine-emitted from the tool results, not typed
by the seat being judged.

**ONLY FOR `run` NODES.** An `ask`, `prompt` or `memory` node holds no tools by
definition, so demanding tool evidence there would refuse every honest eval
over a voice — `branchSpec`'s does exactly that, and a stroke holds it.

Strokes: `TestARunNodeThatCalledNoToolCannotBeJudged` — the 5.6-second turn,
whose prose literally contains `RAN:` and must still fail, with the record
naming why; `TestEvidenceLetsTheJudgementStand` — the same answer WITH the
block passes, and a witnessed failure still fails, so the rule did not become
a rubber stamp; `TestAVoiceIsJudgedWithoutToolEvidence` — the ask-node eval is
untouched. The stub engine gained a canned `Turn` answer so the rule could be
struck both ways; with none it returns the old string and every existing
stroke reads as it did.

**Also — the builder now states the discipline it had left implicit.** The
expectation box said only "what expect is, for this run", and a run whose code
was CORRECT failed because the hand wrote `Refused` where the program printed
`Refusing`. The block now says the test is exact and case-sensitive, and that
the marker belongs in the objective and repeated in the box. A looser test
would go green on work that only sounded right, which is the thing all of this
exists to refuse.

**Still open from the same run:** `recheck -> land` remains UNJUDGED. Only
`verify` is scored, so a run that fails the verdict, repairs and rechecks
reaches the gate with no judgement of the repaired work. That is the last of
the three holes firing this flow found, and it is not closed here.

### The check scored liveness and called it correctness

**How it was found: by firing it.** The coder flow was given a real task — "turn
a version string into a release target, and it must REFUSE any string carrying
a plus build tag INSTEAD OF STRIPPING OR DEFAULTING IT". The coder wrote
`version_str.split('+')[0]`: it stripped, the one behaviour the objective named
and forbade. **The flow went green.** `check` had asked whether `run_python`
said `RAN:`, and it had. The delivery even wrote both halves of the
contradiction in one sentence: *"It refuses to process any string carrying a
plus build tag, effectively ignoring it."*

A flow that goes green on wrong code is worse than one that goes red. The green
is the thing a reader trusts, and it launders wrong work to a gate.

**Fixed — an eval's `expected` is rendered, so a check can hold a node to an
expectation supplied at FIRE time.** It was a literal, so a check could only
ever test something written when the flow was FOLDED. That is enough for
liveness and cannot express correctness, because what a correct run prints is a
fact about THIS request.

    flow/run.go      play.Render on nd.Expected before scoring; the fail
                     message carries the RENDERED want, because "expected
                     contains {{expect}}" tells a reader nothing
    scoreNode        takes `want` already rendered -- the caller owns the
                     templating so this stays one question
    workflows.js     openVars scans `expected` too, and the comment that said
                     it deliberately did not is corrected in the same stroke.
                     A gate's title is still excluded: gates never reach
                     execNode, so a box for it would fill nothing

**THE EXPECTATION COMES FROM THE HAND, NOT A MODEL.** A model that both states
what correct output looks like and writes the code can agree with itself, and
agreeing with itself is the disease. `play.Render` refuses a missing var, so a
flow that templates an expectation nobody supplied fails at that node instead
of scoring against an empty string.

Strokes: `TestExpectationComesFromTheFiring` (met -> pass; **ran and WRONG ->
fail**, which is the run above), `TestAnExpectationNobodySuppliedIsRefused`,
`TestTheFailMessageNamesTheRenderedWant`, and
`TestAFoldedLiteralExpectationIsUnchanged` -- because every spec written before
this carries a plain literal and must score exactly as it did.

**Measured live.** `coder` v11: the same objective that went green now fails.

    verify    run_python: RAN: version_to_release_target.py   (exit 0)
    verdict   fail: expected contains "Refused"
              -> repair -> recheck -> land (gate)

**THREE WIRING ATTEMPTS, EACH CORRECTED BY A RUN, AND THE LESSONS ARE THE
VALUE:**

    v9   check(liveness) gated verdict(correctness). Wrong: a task whose
         correct behaviour is a NON-ZERO EXIT fails the liveness gate. A
         correct refusal exits 1.
    v10  check and verdict both hung off verify as recorders. Wrong, and the
         engine says so plainly: `if !hasFailEdge(...) { return VerdictFail }`
         -- AN EVAL IS A GATE, NEVER A PASSIVE RECORDER. Removing check's fail
         edge made the whole run FAIL before verdict could fire.
    v11  one eval, on the requirement. Liveness is not a second gate; it is
         evidence, and it is already in the verdict block a reader sees.

**And the expectation is only as good as the observable the objective names.**
A run where the code was CORRECT still failed the verdict, because the
expectation said `Refused` and the program printed `Refusing`. `contains` is
exact and case-sensitive and did what it was told. The cure is a spec -- the
objective naming the marker, the expectation matching it -- not fuzzy matching,
which would reintroduce the laundering this exists to stop. The brief now also
states that the file is run with NO arguments, after a coder wrote an
`sys.argv`-reading script that `run_python` structurally cannot invoke.

**Open, named, not fixed — two holes this found and did not close:**

    the retry is unjudged   `recheck -> land always`. Only `verify` is judged,
                            so a run that fails the verdict, repairs and
                            rechecks reaches the gate with NO correctness
                            judgement of the repaired work. Same shape as the
                            original bug, one branch over. Wants a second eval
                            after recheck.
    verify can run nothing  a verify node came back in 5.6s with no verdict
                            block at all -- it called no tool, so the verdict
                            had nothing to judge and failed for want of
                            evidence rather than for wrong work. The two are
                            not the same and the record should not conflate
                            them.

### 0.1.4 — THE DELIVERY PACKAGING

His word, 2026-09-12: *"atlas 0.1.4 - the delivery packaging."*

`VERSION` is the single authority and it is now true in all EIGHT files,
not six: the root, `line/`, one beside each of the five `line/cmd/*`
mains, and a new `webapp/handlers/VERSION`. Two of those did not exist
this morning, and their absence is the whole entry:

    atlas-vc    printed the literal "0.1.3" unconditionally and had no
                VERSION file at all -- the fifth command, outside the
                scheme the other four were in, while ACCEPTANCE.md
                counted "all 6 files" as though it were not
    atlas-tui   had a VERSION file beside it and did not read it: it
                asked the Rust spine for --version and fell back to a
                LITERAL when the spine was absent. So it printed a stale
                number on exactly the machines where the spine is not
                built -- the fresh clone `prove.py` keeps an ABSENT
                branch for, and the one case ACCEPTANCE.md is written to
                catch. The one place the staleness could not be noticed
                was the one place it lived.
    webapp      said "0.1.3" by hand in TWO unrelated functions --
                /health's `version` field and the Prometheus gauge
                `atlas_server_info{server="atlas-webapp",version=...}`.
                A version a monitoring system scrapes is the last one
                anybody re-reads.

All five commands and the glass now answer from the file: measured, not
asserted -- `atlas-mcp 0.1.4`, `atlas-tui atlas-tui 0.1.4` (with the
spine absent, which is the fixed path), `atlas-vc 0.1.4`, `atlas-door
0.1.4`, `atlas-town 0.1.4`. `Cargo.toml` and `core/src/version.rs`'s own
assertion moved with them, and every doc line that ASSERTS what the build
prints -- ACCEPTANCE, PIPELINES, OLLAMA_PROVER, WORKFLOWS, E2E_SCENARIOS,
AGENTS -- moved too. The released headers below did not: they are the
record of what shipped.

### The gofmt gate repeated the fault it was named after

Its own note, written this morning: *"three files had never been through gofmt
and nobody knew, because the check that found the first one was scoped to a
single directory."* It was then written with `working-directory: line`.

SIX FILES IN `webapp/` HAD NEVER BEEN FORMATTED — `db/db.go` and
`handlers/{flows,prompts,session,team,ws}.go`, untouched since they landed in
`77162d9` on 2026-09-09 — and the gate could not see one of them, because
webapp is a separate Go module. Found by running gofmt by hand during a
function check, not by the gate.

Five were struct-tag alignment and nothing else; their token streams with all
whitespace removed hash identical before and after. `ws.go` was NOT: gofmt
1.19 and later read the hanging indent under `Frames out:` as a CODE BLOCK and
would have reflowed it to a tab and split the label from its own list. That
comment was reflowed flat by hand instead, so it says the same thing, reads the
same way, and gofmt now has nothing left to do to it — checked, zero lines.

THE GATE NOW NAMES BOTH MODULES, and deliberately does not just run `gofmt -l .`
from the root: that walks `target/` and every vendored tree, which is how a
gate gets slow and then gets deleted. It also reports both before exiting, so
one run names every offender instead of one per push. A third Go module has to
be added to that list on the day it is created, and the note in the workflow
says so.

Proven to bite: an unformatted function was put into `webapp/handlers/team.go`
and the gate's own script exited 1 naming the file, then the file was restored
and it exited 0. `go build` and `go vet` clean across both modules.

### 0.1.3

His word: atlas is 0.1.3. `VERSION` is the single authority — `core/src/version.rs`
reads it with `include_str!` — but it is not the only pin, and `version.ps1`
says so itself in yellow every time it runs: it moves six VERSION files and
then names `python tests/prove.py` as the thing that finds the rest.

Fourteen real pins moved: the six VERSION files, the workspace package in
`Cargo.toml` (and `Cargo.lock`'s three crates, regenerated by cargo rather than
typed), the spine's own `assert_eq!`, `atlas-tui` and `atlas-vc`'s `--version`,
the glass's `/api/health` and its metric label, and the two test harnesses.
Then the live documents that ASSERT a version: `docs/ACCEPTANCE.md`,
`docs/PIPELINES.md`, `docs/OLLAMA_PROVER.md`, `tests/e2e/E2E_SCENARIOS.md`,
`AGENTS.md` and two `**Version:**` headers.

WHAT WAS NOT TOUCHED, AND WHY EACH ONE STAYS:

    core/src/version.rs:3    a doc comment reading "e.g. `0.1.2`" -- an example
    gitctl_test.go:146       `v0.1.2` is a BRANCH NAME in a name-law fixture
    docs/WORKFLOWS.md:408    sample message text inside an example payload
    version.ps1, release.ps1 help text and the record of the struck moniker
    DELIVERABLE.md           dated 2026-09-08, with its own "verified" table
                             and a frozen git-history block -- a snapshot OF
                             0.1.2. Renaming it would claim it was proven at
                             0.1.3, which it was not.

Proven by the spine's own battery rather than by reading: `version-pin
file=0.1.3 bin=0.1.3` and `version-cross all agree: 0.1.3`. Both binaries were
rebuilt and restarted on their own command lines and now answer 0.1.3 — the
door carrying exactly the two worlds it carried before, atlas and research.

### The workflow builder gets its face back

The DAG builder came off the panel 2026-09-10 — "not used, wipe it" — and
`/flows` became Version control. What was wiped was THE PAGE. The engine was
never touched, and this is what was sitting behind the missing page the whole
time: `internal/flow` at 1,140 lines with 455 lines of strokes, ten `flow_*`
tools on the door, nine handlers, all nine routes wired in `server.go`, and a
method in `api.js` for every one of them. Proven live before a line of the page
was written: save -> list -> get -> run -> status, a real llama3.2 call,
receipts, budget bar, verdict COMPLETE.

So nothing here rebuilds a workflow system. `static/js/workflows.js` DRAWS the
one that was already there, and every button is a call the LINE already answers.

THE PATTERNS, in this engine's own terms (his reference,
workflowbuilder.io/blog/agentic-workflow-patterns):

    prompt chaining     nodes joined by `always` edges; topo order is the chain
    routing             an `eval` node, then `pass` / `fail` edges off it
    parallelization     branches declared, run sequentially -- one card, one
                        rack queue, and interleaved model output cannot be read
    reflection          unrolled into fixed passes, because Validate REFUSES
                        cycles. That is what the article recommends anyway.
    human-in-the-loop   a `gate` node: the run stops at PAUSED and waits

All seven node kinds are offered and no eighth is, because `Kinds` is a closed
set and anything else is refused by name at save. The page does not pre-judge a
spec: Validate lives in the LINE, its refusals name the node and the reason, and
a second opinion drawn here is how two validators drift apart. A gate offers
exactly the two moves the engine accepts, and neither is the default.

ITS OWN PAGE, NOT THE OLD ROUTE. `/flows` stays Version control — that is the
git overwatch he uses every day, and taking the route back would cost him the
page he actually stands on. The builder is `/workflows`, its own line on the
panel.

Proven from the browser, not from curl: a two-step flow built in the UI, folded
to v1, fired, `COMPLETE · fired 2 · 57290ms` with a receipt per node.

**Restart required** — the webapp embeds its static files (`go:embed`), so
`:8091` does not carry this until it is rebuilt and restarted. Tested on a
scratch binary on `:8099`; his running server was not touched.

- **`flows/` is ignored.** The engine writes `<home>/flows/` the moment a flow
  is saved or fired — specs, their folded history, `runs.jsonl`. Runtime state,
  the same shape as `state/` beside it, and the provers build their own homes in
  temp dirs rather than reading it.

### The seat log travels, so a clone can prove itself

`atlas/SEAT_LOG.md` was gitignored and never reached a clone, so `cargo test
--workspace` failed there on the `orient-pack` stroke (`LOG=false`) while
passing on the ground. CI never saw it: the gate runs `prove.py --check`, which
skips the cargo leg. Untracked from `.gitignore` on his word, 2026-09-11.

### The criteria documents, measured rather than remembered

`docs/ACCEPTANCE.md` and `docs/PIPELINES.md` are what a stranger reads to learn
what PASS looks like here, so a stale number in them is not cosmetic — it is a
gate reporting the wrong verdict. Every count in both was run rather than read:

    atlas-mcp --prove         said 58 strokes        is 125        CORRECTED
    cutters answering verify  said "all 17 pass"     is 24 legs:   CORRECTED
                                                     12 byte-identical,
                                                     12 ABSENT (oracle)
    agents/docs/*.md          said 40 doc files      is 41         CORRECTED
    atlas-town --prove        said 11 strokes        is 11         held
    atlas-door --prove        said 13 strokes        is 13         held
    agents/*.us               said 40                is 40         held
    agents/modules/*.us       said 4                 is 4          held
    skills/*/SKILL.md         said 3                 is 3          held
    go test ./...             said 92+               is 138 across 19 pkgs, held

The cutter line was wrong twice over, which is why it did not become "all 24
pass". Half of them cannot verify on any machine but the one they were cut from:
twelve re-cut byte-identical and twelve report ABSENT naming `ATLAS_ORACLE_ROOT`,
because the private oracle ground does not ship and never will. A gate that says
"all pass" over that is unpassable by construction, the same defect as the
`--describe` row fixed earlier today. It now states both verdicts, which is the
three-verdict doctrine this repo already holds everywhere else.

Untouched on purpose: `DELIVERABLE.md` is dated 2026-09-08 and carries its own
"verified 2026-09-08" table and a frozen git-history block — a release snapshot,
not a living description, and its numbers are the record of that day.

### Two checks stop naming a command that cannot answer them

`docs/ACCEPTANCE.md` and `docs/PIPELINES.md` both gated on `atlas-mcp
--describe` listing 72 tools. It does not list tools. `--describe` prints one
line — the door's name and what it is — and returns (`cmd/atlas-mcp/main.go`),
and no flag the door declares lists them at all. So the gate could never pass at
any number, which is why renumbering it to 78 with the rest of the sweep was
refused: a fresh coat of paint on a check that does nothing is worse than a
stale one, because the stale one still reads as suspect.

Both now name `atlas-mcp --prove`, which really counts. `prove.go` builds the
surface in-process, calls `tools/list` against it, and reports `surface carries
78 tools (>=20)` — no server, no model, which is what every neighbouring row in
those tables already assumes. PIPELINES' own failure policy for this pipeline,
"Tool count < 20 → fail", is that stroke's gate written out in prose; it had
simply never been pointed at the stroke. The LINE table keeps its eleven
stages, so the summary that counts them stays true.

Measured off the three batteries rather than adjusted:

    atlas-mcp --prove    125 strokes, surface carries 78 tools
    atlas-town --prove    11 strokes
    atlas-door --prove    13 strokes

Which names the next stale number and leaves it standing: both documents still
call `atlas-mcp --prove` 58 strokes. It is 125. Town's 11 and the door's 13 are
right as written.

### The last leg that called an absence a failure

The door's battery learned this doctrine at 07:00 on 2026-09-11. One layer up,
`tests/prove.py` had never learned it, and it was found the same way: by a
fresh clone.

`absent_dependency` recognises an absence only when a refusal NAMES A PATH — it
scans for one, checks it does not exist, and checks it lies outside the atlas
tree. `check_trade_parity` shells the Rust spine, so on an unbuilt tree it
refuses with a COMMAND instead ("REFUSED: build the binary first (cargo build
-p atlas)"), which that scan cannot see. It fell through to FAIL.

So the whole battery went red on any machine that had not yet run cargo build —
which is every fresh clone, and the first thing a second machine does. Measured
by parking the binary and re-running:

    before                       20 held - 14 absent - 1 broke - exit 1
    after                        20 held - 15 absent - 0 broke - exit 0
    after, with the spine built  21 held - 14 absent - 0 broke - exit 0

The new branch is gated on the binary being GENUINELY ABSENT, so it can never
turn a real break into an absence: with the binary on disk it is unreachable,
which the third line proves — that leg still reports the ORACLE absence there,
not this one. `leg_go` has applied the same rule two functions up since it was
written. This is that rule reaching the last leg without it.

- **The tool count was stale in two places.** `README.md` and `DELIVERABLE.md`
  said the door serves 72 tools. It serves 78, counted off the wire — `tools/list`
  and `GET /tools` agree, and every one of them carries a description and an
  inputSchema. The table under DELIVERABLE's heading lists 24 of them and always
  did; only the count moved.

### The first CI run found two, on its first try

atlas's CI went up and the Linux probe went red immediately — which is what
that job is for. The gate passed (the battery, green on Windows, 1m47s). The
probe found one workflow error of mine and one real dependency on the
operator's platform.

- **The door's battery reported ABSENT as FAIL.** Every stroke in
  `cmd/atlas-door` goes through the Rust spine, so on a machine where it has
  not been built there is nothing to prove and nothing has gone wrong. It said
  FAIL. That made a fresh clone look broken: the first thing `go test ./...`
  said on a clean checkout was a red door, with the actual cause — one
  undocumented `cargo build` — buried in a refusal nobody read. Found twice in
  one day: on a clean clone of both repos, where it was the ONLY red in sixteen
  packages, and then by CI, whose Linux job cannot build the spine at all
  (`store/src/ffi.rs` links Windows' `winsqlite3`) and so could never have
  passed it. It now SKIPS with the command that would answer it, which is the
  shape `tests/prove.py` has held since it was written: ABSENT is not a pass
  and it is not a failure.
- **The stub engine was `cmd /c echo`, hardcoded, in two places.** `cmd` does
  not exist off Windows. Nobody could know: until today these suites had never
  run anywhere but one machine. `echoEngine()` picks by `runtime.GOOS`, and
  `splitCommand` takes both spellings to the same argv.

Proven both ways before it was pushed: **19 packages green with the spine
built, and 19 green with `ATLAS_BIN` pointed at a path that cannot exist** —
the closest proxy this machine can run for the Linux job. With the spine the
door PASSES; without it the door SKIPS and says why.


### atlas gets a CI, and it needs no network

Until today every claim in this repo rested on one machine — 78 tools, 19 green
packages, a 35-leg battery — while the core beside it has proved itself on four
matrix legs per push since 2026-09-03. A stranger had to take all of it on
faith. `.github/workflows/prove.yml` is the answer, in the shape the core's
workflow already established.

**It fetches nothing.** `Cargo.lock` holds three packages and all three are
this workspace's own; both `go.mod` files are stdlib only; `tests/prove.py`
imports nothing outside the standard library. Nothing after `checkout` touches
the network. Stated in the file as a PROPERTY, so a change that needs a
dependency is the regression rather than a surprise.

**Two jobs, and they are separate on purpose.**

- **The gate, on Windows.** Toolchains named in the log, `cargo build -p atlas
  --locked` first (the battery reports the spine ABSENT when unbuilt — honest,
  but then the door leg proves nothing), a `gofmt -l` that must come back
  empty, then THE BALL. It does not re-run cargo test or go test separately:
  the battery runs them itself, and two batteries that can disagree are worse
  than one that cannot.

  Windows is not a preference. `store/src/ffi.rs` does
  `#[link(name = "winsqlite3")]` against the Windows SDK with no `cfg(windows)`
  guard and no alternative backend — the store links the OS's own SQLite rather
  than vendoring one (ADR-004). On any other platform cargo fails at link time.

- **The portability probe, on Linux.** Its own job so a red there can never
  mask the gate. The Go half has no platform gating at all — no `_windows.go`,
  no `//go:build windows`, and `GOOS=linux go build ./...` was verified clean
  before the file was written. But the Go SUITES have never once run off
  Windows. They look portable (the Windows-shaped strings in them are test
  INPUTS, paths the wall must refuse) and looking portable is not being
  portable. **A red there is a finding, not a broken workflow** — it would mean
  the suites picked up a dependency on the operator's platform, which is
  exactly what the core's own matrix exists to catch.

Verified locally before it was committed: the YAML parses to two jobs,
`gofmt -l .` is empty, `cargo build -p atlas --locked` succeeds, and
`tests/prove.py --check` exits 0 with 21 held, 14 absent, 0 broke.


### gofmt comes back empty

Three files had never been through it: `internal/tools/gitctl_test.go` (a map
literal whose keys were padded to the wrong width), `cmd/atlas-vc/main.go` (a
doc comment in the pre-1.19 spelling, leading spaces where Go now wants a tab
block), and `internal/engine/engine.go` (one struct field padded for an
alignment group a comment had broken). Eleven lines between them, every one
cosmetic — no semantic change, 19 packages still green.

Worth naming because of how it was nearly missed: the first check ran
`gofmt -l internal/tools/` and found ONE file, so the report said one file. The
module-wide run found three. A scoped check answers the question it was
scoped to, not the question that was asked.

`gofmt -l .` now returns nothing, which is the precondition for making it a CI
gate rather than something a hand has to remember.


### ADR-006 accepted, and items 2 through 6 built

**Item 2 — the tier is a field, and the stroke corrected the ADR.** `Tool`
carries a `Tier`: CORE (nothing but a directory), SPINE (the Rust binary),
ENGINE (`--manjuel`). The zero value is CORE, so the common case is free and
the declaration stays honest rather than ceremonial.
`TestEveryCoreToolStandsAlone` calls every tool claiming CORE against a bare
temp tenant with the engine unwired AND the spine denied — and **found four
the ADR's grep had missed**. The table said 2 engine tools; there are **6**
(`env_open`, `env_close`, `run_start`, `run_answer`, `run_cancel`,
`ask_steward`), three of which refuse with *"no engine is open"*, a phrase the
grep was not looking for. The real split is **71 core / 6 engine / 1 spine**,
and the ADR was corrected to the measured number. Denying the spine mattered
too: `verify_chain` passed as CORE until `ATLAS_BIN` was pointed at a path that
cannot exist, because on a machine where cargo has run the walk simply finds
the binary.

**Item 4 — first strokes on `tenant` (288 lines, zero) and `ground` (200
lines, zero).** `ground` is the package that carried a world from outside the
estate onto the dashboard, and nothing was broken in it — Detect and Siblings
both did exactly what they were written to do. What was missing was any stroke
stating what that IS, so the blast radius of a launch directory was
discoverable only by suffering it. Now pinned: nearest ground wins; a `.us`
module outranks a folder name; Siblings scans **exactly one level** and a
grandchild is never carried; the attic and the vendored trees are never
grounds. And for `tenant`: an unknown project refuses BY NAME and hands a
stranger no context; case and space cannot fork a tenant; Home is absolute,
because every wall check downstream is a prefix test against it.

**Item 5 — one spawn contract.** Four seams, four different answers to the
same four questions. Two that actually bit: `gitstate` DISCARDED stderr, so a
git failure there was a shrug, and the spine call had **no timeout at all**, so
a wedged Rust binary hung the tool call and through it the door, forever
(ESTATE LAW 7 is bounded everything). `spawn()` closes stdin at one place,
bounds every child, keeps both streams whether it succeeded or failed, and
names a timeout as a timeout instead of "signal: killed".

Two of the six seams are deliberately left, and say why in the source:
`internal/engine` spawns over `StdinPipe` because that pipe IS the wire, and a
helper that closes stdin would break it by doing its job; and `cmd/atlas-door`
is a different binary whose sharing would need a new leaf package, because
`internal/tools` already imports `internal/engine`. A new package is a new
folder and folders are the operator's to place (RULE 8) — so it was named
here rather than invented.

**Item 6 — the oracle ground is nameable.** Every cutter computed its source
as `ATLAS.parent`. Before the 2026-09-10 split that was true; after it, the
parent is the manjuel core, so 14 legs reported ABSENT naming paths that **have
never existed on any machine**. Right verdict, phantom reason, nothing to act
on. They now take `ATLAS_ORACLE_ROOT`, falling back to the historical location
so nothing that worked stops working, and the ABSENT line names the dial. The
distinction that makes atlas standalone is written into `tests/PROVING.md`:
**the goldens travel, the cutters do not** — every golden is committed and the
Rust implementation is proved against them anywhere; only the RE-CUT needs the
private ground, and that ground never ships.

19 Go packages green, 0 failing. THE BALL: 21 held, 14 absent, 0 broke.


### The door names what it carries

It printed `carried 2`. A count cannot be checked against intent — two is two
whether the two are the ones you meant or not. It now prints:

    ground: atlas (...\Research\atlas via AGENTS.md); carrying 2: atlas, research

**Earned the same day, by the incident it would have prevented.** The door was
started from the ground root, so `ground.Detect` resolved the ground to
`research` and `ground.Siblings()` read the parent of THAT — the desktop —
carrying every neighbour holding an `AGENTS.md`. A world outside the estate
rode in, the dashboard read its git state, and the first anyone knew was a
sidebar badge reading 83,303. Every line needed to catch it at boot was already
there except the names.

**And the launch point is the whole control, which was got wrong out loud
first.** `Detect` walks UP and stops at the FIRST marker it finds, and
`Siblings` scans the parent of what it found — not the parent of the working
directory. From `atlas\line` the first marker is atlas's own `AGENTS.md`, so
the scan is of `Research` and the door carries exactly `atlas, research`. From
the ground root the first marker is the core's, and the scan is of the desktop.
No flag, no env var and no code change was needed for the behaviour the
operator asked for; a different `-WorkingDirectory` was the entire answer, and
this hand told him otherwise before checking. RUNBOOK's own start line already
does `cd atlas\line` first.

### The first strokes on the MCP, and two bugs they caught immediately

ADR-006 measured the door and found the thing that explains a two-day failure
streak: `internal/httpserver` is 800 lines, it is what makes atlas-mcp an MCP
server rather than a pile of functions, and it had **zero tests**. The tool
bodies behind it carry 755 strokes; the wire in front of them carried none.
Twelve strokes now stand there, hermetic — a real registry over a real temp
tenant that deliberately does NOT look like manjuel, asserting only what the
wire says.

- **A tool's own words outrank the Go error** (ADR-006 item 1). The tools/call
  error branch discarded `out` one line before it would have been sent and
  returned `err.Error()` instead — which for anything shelling a subprocess is
  the bare string `exit status 1`. `verify_chain` exposed it: it captures the
  Rust spine's `CombinedOutput` INTO `out`, so the diagnosis was in hand and
  thrown away. **Protocol-level**: every tool that errored was losing whatever
  it had written. `isError` still tells the caller it failed; it now also says
  why.
- **THE REGRESSION STROKE WAS WORTHLESS UNTIL IT WASN'T.** It passed with the
  fix reverted, which means it proved nothing. The reason was a second bug, in
  the resolver written earlier the same day: `findAtlas` walked from `"."`, and
  `filepath.Dir(".")` is `"."` — so that root broke out of the walk on its
  first step and never climbed. The door never noticed because its own
  executable path walks fine; a TEST binary lives in a build temp dir, where
  that root was the only one that could reach the tree and it was the one doing
  nothing. So the spine was never found, `out` was empty, and both branches
  produced identical text. Fixed to walk from an absolute cwd. **The stroke now
  fails with the fix reverted** (`the caller got only "exit status 1"`) and
  passes with it applied, which is the only thing that makes it a test.

**What the twelve pin:** the protocol version is a promise to every client
(`2025-06-18`); a notification is answered with silence; every advertised tool
carries a description and an inputSchema and never requires a property it does
not declare; `-32601` for an unknown method and `-32602` for an unknown tool,
each naming what it did not know; `-32700` for a malformed line; the id comes
back; a tool's refusal is `isError` and NOT a transport error, because a client
that retries transport errors would retry a refusal forever.

**And one the review found that the ADR missed:** `GET /tools` and `tools/list`
are two copies of the same 28-line rendering. A stroke now holds them
byte-identical, because a REST caller and an MCP caller disagreeing about what
a tool takes is the worst kind of quiet.

17 Go packages green, 0 failing.


### The spine is found, not assumed

`verify_chain` was dead on every machine where the Rust spine had been built
but not installed on PATH — which is every fresh clone. `--atlas-bin` defaults
to the bare word `"atlas"`, `atlas-door` walked the built tree to find it, and
`atlas-mcp` never did: the same estate answered differently depending on which
door you came through. `tests/PROVING.md` has named this a trap since it was
written, and RUNBOOK's start line still did not carry the flag.

- **The walk moved to `internal/tools`**, the one place that actually shells
  the binary, so every caller gets it and there is no second copy to drift.
  Order: an explicit `--atlas-bin` that is not the placeholder, then
  `ATLAS_BIN`, then PATH, then the built tree.
- **It starts from the running binary's own location.** A first cut walked up
  from the tenant home and from cwd; for `atlas-mcp` the tenant home is the
  CORE ground and the spine lives DOWN from there in `atlas/target/`, so the
  walk climbed past Desktop and found nothing. `atlas-mcp.exe` sits at
  `<repo>/line/` and the spine is built at `<repo>/target/` — two up and back
  down, which the walk now covers. Both `debug` and `release` profiles.
- **It still names what it could not run.** Nothing found returns `"atlas"`
  unchanged, so the refusal a caller sees is the same honest one as before.

Proved live, with no `--atlas-bin` passed at all: `verify_chain` on
`law/chain.jsonl` went from `exec: "atlas": not found in %PATH%` to
`verdict=FLIP entries=4`. 16 Go packages green after the change.

### The README stopped asking for what it does not need

Found by cloning this repo onto a clean tree and following it literally.

- **The MSVC toolchain is named.** `store/src/ffi.rs` links Windows' own
  `winsqlite3`, so `cargo build` needs `link.exe`. A fresh PC with only rustup
  dies on `linker 'link.exe' not found`, which says nothing about this
  project. Several GB of prerequisite, named nowhere until today.
- **Python 3.14 was never needed.** The core's `pyproject.toml` says `>=3.10`
  and CI proves 3.10 and 3.13. The `.venv` the same line named is created by
  nothing and is gitignored; `tests/prove.py` uses `sys.executable`.
- **`cd line ; go build ./...` produced no binaries and no error.** `line/cmd`
  holds five main packages and Go discards every result when it compiles more
  than one. It is a compile check that reads like a build.


### The rule that kept winning arguments it was not in

`.covenant` being declared twice was one instance of something; this is the
rest of it, found by measuring instead of by eye. Two audits were written
against the stylesheet: one for the same selector declared twice, one for the
shape that actually did the damage — two DIFFERENT classes worn on one element
where the later one silently takes a property.

**The culprit is `.muted`, and it has now ambushed three things.** It is worn
as a colour utility, 62 times across this console, but it also sets a
`font-size` and a `margin-top`, and at one class of specificity the later rule
wins. It took the hero verdict from 40px down to 12px this morning. It was
also cutting Version control's footnote — *"Every button here is your hand,
not the machine's"* — from 16px of top margin to 6px, which is why that line
has been sitting closer to the buttons than it was written to.

- **The spacing utilities moved to the foot of the file.** A utility exists to
  set one property and `.mt-16` was losing that property to a colour class.
  Utilities come last; that is the whole reason they are a category. Measured
  after: the footnote gets its 16px.
- **The hazard is written down at `.muted`'s own definition**, in the terms a
  hand needs: wearing it beside any class that sets `font-size` or
  `margin-top` means `.muted` wins unless that class is declared after it.
  Stripping the two extra properties would resize all 62 uses, which is a
  change nobody asked for, so the rule stands and the trap is documented where
  it is stepped in.
- **`.seat-open` declared `color: inherit` and never got it** — `.card-title`
  is later and sets the colour. What the link actually wanted was to look like
  every other card title, which is what it was already doing, so the dead
  declaration is gone and the hover stays (a pseudo-class outranks a bare
  class). Measured: the seat name renders at `--accent-2`, identical to a
  title that is not a link.
- **`.sidebar-footer`'s `font-size: 11px`** was re-stated verbatim as
  `var(--t-xs)` further down and never read.

**What the audits say now.** Three pairs still collide and all three are the
INTENDED rule winning: `.btn-sm` over `.btn`, `.home-box` over `.card`,
`.chat-foot` over `.muted`. Three more — `.empty-text`, `.textarea`, `th` — hold
an earlier value a later rule deliberately refines, which is a cascade doing
its job rather than a defect. No ambushes remain.

Swept afterwards across all eight pages: none scrolls sideways, and the crumb
is hidden on the Dashboard and present everywhere else.

### Two the sweep turned up on the way

- **"Through the council" was pushing its own input out of its card.** The
  header's right-hand group was `flex-shrink: 0`, which is right for a row of
  buttons and wrong the moment a FIELD is in it — the base field rule is
  `width: 100%`, and a full-width input in a group that will not give anything
  back goes straight through the card's edge. A field in a header now sizes to
  the room it is given. Measured at 1400px: one row, 48px, inside the card.
- **A changed file's label ran into its filename with no gap.** The label was
  an inline-block with `min-width: 150px`, which is a floor and not a ceiling,
  and *"changed, ready to save"* is wider than that in the mono face. It is
  two real columns now: the label takes what it needs up to a cap, the path
  takes the rest and wraps rather than pushing the card.

### The Aurora scheme

The operator pointed at a console he built for an earlier version of this
estate and said what he wanted from it: *"i like the current dashboard layout,
and the colors/flow of the one i sent."* So the layout is untouched — the
deck, the hero, the ledger, the crumb all stand — and the palette and the
flow devices are his.

**The palette now means something.** This console was Catppuccin-adjacent: a
neutral near-black under a cornflower blue. Aurora's ground is blue-GREEN at
the root (`#05080a`), its text is teal-tinted rather than grey, and it runs a
phosphor cyan with an amber second. The colours are not decoration — the
**amber is what the estate calls SEALED**, the **phosphor is what it calls
PROVEN**, and the orange marks a section of the record. Fifty-five hardcoded
`rgba()` literals of the old palette were still scattered through the file
behind the tokens; every one of them moved.

- **Mono-first, as Aurora is.** Its whole console is one fixed pitch and that
  is most of why it reads the way it does: every label, value, field and
  control on one grid. The prose face is kept for the handful of places this
  console carries real SENTENCES — a hero line, a page subtitle, the brief,
  a delivery — where a fixed pitch costs more in reading than it earns.
- **The glowing edge.** A 2px bar down the left of the panel the page is
  about, with a 12px bloom off it, in the verdict's own colour — so the edge
  says the same thing as the word beside it, or it says nothing.
- **The section rule.** Aurora's headings are a tracked micro-label followed
  by a hairline running to the panel's edge. That single device is what makes
  its panels read as parts of one instrument rather than a stack of boxes;
  every card header in this console now closes the same way.
- **The washed ground**, a cyan bleed at top centre and an amber at top right,
  fixed behind everything for one paint.
- **The pinned action wears the seal.** Booting opens a sitting and closing
  pays its toll: both move the record, so that one button is amber while cyan
  stays the colour of reading.

### Four that were wrong, found by looking at every page

- **The Watchboard's badge read "delivered — 54.3s" over a panel reading
  "nothing has run in this tab yet."** `Run.check()` is where a turn kept from
  a previous visit comes back, and the only handler it fires is `state`, which
  repaints the badge alone. The board now paints from what that read found.
- **A dead badge on Evals.** The run card moved to the Dashboard and took its
  log element with it; `paintRun` returns at its first line when that element
  is absent, so `#ev-run-state` was never painted once and sat in the header
  of every visit showing a hardcoded em dash — a control that looks like a
  reading and is a literal.
- **`.covenant` was declared twice** in one stylesheet, and the later rule won
  silently. Two rules for one class is exactly how `.muted` came to steal the
  hero verdict's font-size this morning. One rule now, and the hairline above
  it does the lifting rather than the colour.
- **Three tables were written bare**, and a bare table pushes its card, which
  pushes the grid, which scrolls the page sideways: Settings was 601px of
  content in a 595px main because of a badge reading `can_approve:false`.
  Wrapping the three by hand fixes the three and not the fourth, so a table
  in a card scrolls in its own box whether or not anyone remembered the
  wrapper. Button labels stopped breaking mid-word in the same pass — the
  mono face is wider, and a row of buttons wraps between buttons or it stops
  reading as a row of controls.

### The watchboard: the council from the inside

Chat was a second conversation — the same box as the launchpad, the same
`Chat.thread` array, the same bubbles, plus scrollback. Two of its jobs were
real and neither needed a whole page: answering a gate, and showing each
seat's words as they stream. Both belong in a watchboard. His words:
*"basically like a multi-panel watchboard to see the backend of all the system
and core work so literally every tool call and everything is being landed on a
page. this would be like the internal chat of the models themselves."*

**The feed was already there and nothing rendered it.** council.js has kept
EVERY event of every turn since it was written — *"the record of a run is the
events"* — and the only reader was a single-column card that drops, on
purpose, the one kind that matters most here:

    case 'token': return '';   // App.runRow

The seats' own words. The step-by-step shows what the council DID; this shows
what the models SAID while doing it. Same wire, nothing new asked of the
engine, nothing new stored, no second definition of anything.

- **Four panels**, because they answer four different questions and reading
  them interleaved is what made the single column unreadable. THE TURN: what
  was asked, under which pipeline, and the delivery. THE FLOOR: every seat that
  took it, its model, and its raw output whole. THE TOOLS: every call, the
  arguments in, the result out, `failed` read off the engine's own field. THE
  WIRE: every event in order, unreduced — with a `raw` toggle that prints
  each whole payload, because *every event* has to mean every event or the
  panel is only another summary. An event kind this build has never met is
  printed as its own JSON rather than dropped.
- **Tokens are counted, not listed, when the wire is folded** — a turn carries
  hundreds and they are shown whole on the floor. `raw` lists them too.
- **The past is on the page.** The live turn is one turn; `logs/` holds every
  run this ground has made, served whole with a sha256 by `records`. That
  answers the other half of what he asked: *"should we move the session
  tracking over there? more of the in-depth view."*
- **The gate stays** — a council question is answered in a field on this page,
  never a `prompt()`, never a default, never a guess (RULE 6). The label in the
  panel is Watchboard; the route and `data-page` stay `chat`, exactly as flows
  did when it became Version control.

**Proved against a real turn, not a stub.** Engine booted, sitting 196,
`git status` run from the watchboard's own box: 2 seats, 1 tool call, **148
events**, 54.3s, delivered. The floor carried Router (`qwen3.5:4b`, 280 chars)
and Steward (`llama3.2:latest`, 409 chars) streaming their own words under
their own names; the wire carried the arithmetic guard, the skill decision, the
call, the result, both token runs and the delivery. Sitting closed and tolled.

- **Two clocks on one page stopped disagreeing.** The facts row is painted per
  EVENT, and a seat can think for a minute without putting one on the wire — so
  it read 2.6s beside a badge reading 49s. The turn's clock now ticks into its
  own span, the same shape as the engine's age on the Dashboard.
- **`when()` takes an epoch, not an ISO string**, and hands anything else
  straight back — so the earlier-runs table printed raw `2026-09-11T02:59:20Z`
  in UTC. Records already knew this and wrapped it in `Date.parse`.

### The Dashboard answers the question it is actually asked

Rebuilt against what the console is FOR, at the operator's word: *"think about
what the dashboard is used for and what would make sense to put where
functionally"*, and against a read of what dashboards do now.

**The order was wrong, and it was wrong in the one way that costs something.**
He sits down and asks, in this order: *can I work at all — what do I want done
— what is happening — is the ground sound — is anything waiting on me.* The
page answered them almost backwards. The ENGINE CARD, which gates every other
thing here — nothing typed into that box runs without an engine — sat BELOW
the box it gates, three scrolls down. Meanwhile the five score cards, which
move perhaps twice a day, held the top-left quadrant.

- **The hero is the sitting now.** Open or not, on which world, since when,
  with the one button that changes it. The engine card is folded into it and
  gone as a card; its whole content was one sentence, which is the exact
  complaint its own comment made about the card it had replaced.
- **With one override: a red build outranks an unopened engine.** Booting onto
  a broken build without being told is worse than not knowing the engine is
  shut, so red anywhere raises an alarm in the hero that NAMES what fell and
  the first thing to fall. A measure that was never run raises a yellow one:
  *not-tried is not the same as passed*, and only one of those is good news.
- **The proof drops to a ledger beside it** — rows, not cards. Five cards of
  identical weight made the eye do the ranking; a ruled list puts every value
  in one column where they can be compared in a single sweep, which is the
  only reason to show them together. Three elements above the fold now
  (the sitting, the ledger, the box) where there were nine.
- **The brief rose above the box, and green went actually silent.** It is the
  interrupt channel — a gate waiting, a refusal, an engine running code older
  than the ground — and it arrived UNDER the box it should have changed what
  he typed into. When nothing needs him it now renders nothing at all; the
  page subtitle still carries the all-clear, which is where a quiet statement
  belongs.

**What the market read gave us, and what it did not.** The 2026 consensus
across the tools this one sits beside is decision-first rather than KPI-grid:
one north-star answer in the top-left, four to six supporting measures, and
nothing above the fold that does not change the next move — with Nielsen
Norman's finding as the hard edge, that a reader scans in a Z and gives up
past about seven competing elements. That is the shape taken. What was NOT
taken: sparklines, donuts, and an "AI summary" of numbers the record already
states plainly. Every line still names the file it was read from, which is
this console's own law and worth more than any chart.

### The seat page stops being a lie

- **`/agents/:id` was an orphan AND wrong.** Nothing on the seats page linked
  to it, so the only way in was to type the URL — and when you did it read
  `API.getAgent`, which queries the webapp's own SQLite `agents` table. Nothing
  writes that table. The list beside it reads `agents/*.md` through the `seats`
  tool, so a ground holding fourteen declared seats answered **404 for every
  one of them**, and the fields it was built to show (office, reports_to, mode,
  permissions) do not exist in a declaration at all. Fourth instance of a page
  counting the webapp's store instead of asking the record, and the last one
  standing. A route nobody can reach is a route nobody notices is broken.
- **It reads the record now**, keyed on the file stem — stable, unique,
  url-safe, and already what the record calls the document. It carries what
  the card cannot: the declaration with nothing folded, the system prompt open
  rather than behind a toggle, every pipeline placement with its step and
  condition, and **the file itself with its sha256**, served by `records`.
  `/agents/steward` went from HTTP 404 to seven fields, five placements and a
  3422-character prompt.
- **An absent name is denied honestly** and the denial lists the fourteen that
  are there, each one a link — the same doctrine `read_doctrine` already held
  itself to.
- **A seat's name is the way in.** It reads as a title until you go near it:
  on a page of fourteen cards, a row of blue links is a row of noise.

### Three that were silently wrong

- **`.hero-verdict muted` came out at 12px.** `.muted` further down the file
  sets a font-size and a margin, has the same specificity, and is later — so
  it won. A utility class used as a state name is a collision waiting for
  whichever rule happens to be written last. The state has its own name now.
- **`window.Home` is not a thing.** `Home` is declared `const` at the top of
  home.js, and a top-level `const` in a classic script binds in the global
  LEXICAL scope, never as a property of `window`. The guard was always false,
  so the hero came up with its kicker and an empty body — which looks exactly
  like a failed read.
- **A system prompt is prose, so it wraps.** The base `pre` rule now scrolls
  anything too wide, and a paragraph you have to drag sideways is not served
  whole in any sense that matters. Link-buttons stopped underlining in the
  same stroke: several buttons here are `<a>`, and they were carrying the
  browser's underline through the button's own chrome.

### The console says where you are, and what moved
- **A crumb, painted once by the router.** Every page but the Dashboard now
  opens with `ATLAS / <page>`, and a detail view carries its third step
  (`ATLAS / Agents / steward`) because there the depth is a fact. It lives
  above the routed content rather than inside each page's header: the router
  is the only thing that knows where you are, and fourteen hand-written copies
  of one line is fourteen chances for one to be wrong. The page's NAME is read
  off its own nav link, so the relabel to *Version control* reached the crumb
  without a second edit.
- **The standup card carries a delta.** `+1 vs last`, read from
  `run_history.jsonl`, which holds every prior live run. It is the ONLY card
  that gets one: nothing else on that row has a second measurement to compare
  against, and an unchanged reading and a never-measured-twice reading are
  different claims. A card with nothing to compare shows no delta rather than
  a zero.
- **Fields are styled by the element, not only by the class.** Ten inputs in
  this console were written without `class="input"` and came out as the
  browser's white box with black text — the save-message field on Version
  control was a bare white slab sitting on a dark card. Classing the ten by
  hand fixes the ten and not the eleventh, so the rule now binds to `input`,
  `select` and `textarea` themselves, with `:not()` guards keeping it off the
  controls that are not fields. The placeholder took the ground's own muted
  colour in the same stroke; it had been inheriting a grey that read nearly as
  loud as a typed value.
- **A git act on Version control re-proves the sidebar badge.** The badge
  repainted only on a run event, so a save or a send made from that very page
  left the panel showing the count from before the act — the one moment the
  number is most obviously being watched. Seen live: research pushed, the page
  said *in step*, the badge still read 7. It repaints that badge ALONE
  (`paintOwed`, the same shape as `paintProof(box, only)`): it is the only one
  an act on that page can move, and doing all four costs six tool calls in a
  row — long enough that the first cut still showed the stale number when the
  eye went looking for it.
- **Settings stopped scrolling sideways.** A `1fr` grid column is
  `minmax(auto, 1fr)`, and `auto` there means MIN-CONTENT, so one long
  unbreakable line inside a card — the team-bridge readout — made the column
  refuse to narrow and pushed the whole page. Measured: 737px of content in a
  595px main. `min-width: 0` on the grid children, and `pre` scrolls in its
  own box rather than shoving the page.

### The readers are proven too
- **15 more strokes on `internal/tools`**, on the three tools that READ the
  estate's own record — where a quiet wrong answer does the most damage. Every
  one of those three exists because an earlier page counted the webapp's own
  SQLite store instead of asking the record and showed four zeros on a full
  estate; nothing had ever held them to it. **34 strokes in the package now.**
- **`records`**: sorted by what a document *is*, with the law above the seats
  (alphabetical would invert that), `law/` marked sealed, only markdown served,
  and the sha256 receipt matching the bytes actually handed over. The path
  stroke is the one worth reading — **a name is matched against the listing and
  never joined onto Home**, so `../.env`, an absolute path and `law/../.env` are
  not *defended against*, they simply are not in the list and cannot resolve.
- **`proofs`**: a closing sitting line folds over its opening one (get that
  wrong and every sitting counts twice), a half-written last line — what a
  killed process leaves — is dropped without losing the lines before it, one
  absent file never blanks the other two, and the counts the core owns are
  *named* rather than recounted.
- **`seats`**: fields are whatever a declaration carries, including one invented
  tomorrow, because the core's own parser names no field either; the colon comes
  off a key; a `System Prompt` with an empty value takes the body beneath it and
  stops being counted twice.
- **The registry contract is pinned.** A tool that writes must declare it —
  that flag is what the review-only table refuses by, so a mislabelled tool
  would hand counsel a hand instead of eyes.
- **`runstream.go` stays uncovered, deliberately**, and is named as such in
  `tests/PROVING.md`. `RunStream`, `AnswerStream` and `ListenStream` all need a
  live engine on an open sitting; a mock there would prove the mock.


### The console takes a keyboard
- **Ctrl+K / Cmd+K opens a palette.** Every page and the engine's verbs, three
  letters and Enter. Checked on the event rather than the platform, because a
  Mac keyboard on a Windows box happens and neither should have to learn the
  other's key. **It navigates and it boots, and nothing else** — a palette that
  can run anything is a second command surface to learn and a second place for a
  destructive verb to hide. Close is in it because it *pays the toll*, the one
  routine act the record depends on and the easiest to forget.
- **What it offers is what is true right now.** The engine rows read `Run`'s live
  state, so a palette opened after a crash does not offer to close a sitting that
  already closed.
- **Tables read down a column.** A stripe barely there — enough to hold a line,
  not enough to become a pattern — drawn as a background so a hovered row still
  wins without a specificity fight. Figures are right-aligned, which is what
  makes two numbers comparable at a glance now that they are tabular.
- **Waiting looks like the thing that is coming.** "Reading both grounds..." with
  a spinner is a sentence about the machine; a skeleton says how much is arriving
  and where it will sit, so the layout does not jump when it lands. It is the one
  piece of non-user-triggered motion here and it earns it — a still grey block
  reads as a broken image — and it is switched off under
  `prefers-reduced-motion`, along with the mic pulse.
- **An empty screen is an invitation**, so it gets room and a plain sentence
  rather than a shrug in the corner of a card.


### The console is rearranged around what you actually look at
- **Recent moved with it**, and the nav item is **Version control** now. The
  route and `data-page` stay `flows`: the route is what every link, bookmark and
  history entry points at, and `data-page` is the key `css/icons.css` draws the
  glyph from. Clicking a recent objective still fills the box — the box is on
  the Dashboard, so it stages on `Home.pending` and the router goes there.
  Nothing is run by a click.
- **`escHtml` did not escape quotes, and seventeen attributes were built with
  it.** `textContent -> innerHTML` escapes `&`, `<` and `>` and nothing else, so
  a double quote passed through untouched — fine in a text position, wrong in an
  attribute. Found by moving Recent: the objective `git commit: "a test of the
  recent card"` rendered as `data-say="git commit: "`, the attribute ending at
  the operator's own quote with the rest of his sentence loose as markup.
  Escaped at the source rather than at seventeen call sites, because a rule that
  must be remembered at every use is forgotten at the eighteenth; `&quot;`
  renders as `"` in a text position, so the other 209 uses are unaffected.
- **The Dashboard opens with the scores.** strokes, smoke, standup, standups run
  and parity moved off Records, where they were a page you had to go to, and now
  head the launchpad. They answer *is the build sound* — the question worth
  answering before you type into the box beneath them.
- **The run sits under the box that started it.** The step-by-step was a card on
  Evals, a page away from the thing that produced it. Same renderer, same
  `ev-run` id — `App.paintRun` draws it unchanged, because a second copy of that
  renderer is exactly the drift this estate keeps writing docstrings about.
- **The engine card moved down.** A card whose whole content is one sentence was
  opening the page and crowding it. Still above the brief, because nothing below
  it runs until an engine is open.
- **Every git surface is on one page.** The repository card left the Dashboard
  for Flows — "this needs to go with the other github stuff" — so the door path
  (the per-world buttons, no engine needed) and the council path (law gate,
  recorded run) now sit one above the other. Two ways in, on purpose: *"there is
  a series of redundancies.. its called safety, bud."*
- **The flow builder came off.** Registry, editor, SVG graph, fire, resume, the
  runs table, compare, replay and the town board — all rendered, none ever used.
  **Nothing behind them was deleted:** the `/api/flows` routes, `flow.go`,
  `run.go` and their strokes all stand, so a builder is a render away.
- **Records leads with the documents.** What this ground *carries* is what the
  page is opened for; the sittings and standups are the history behind it.
- **Live standups show the last 5 of 33, newest first.** It listed every run ever
  recorded, oldest first, so the one that mattered — the last — was at the bottom
  of a table that grew a row every morning. The rest are named in
  `tests/run_history.jsonl`.


### Added
- **The Flows page controls git, in your own words.** The overwatch card was
  read-only; it now carries the verbs. Per world: a message box and **Save the
  work**, **Send to GitHub**, **Take from GitHub**, and **Lines of work** —
  which lists every branch as *you are here · the main line · on GitHub*, and
  opens, moves to, or finishes with one. A button that cannot work is greyed
  out **with the reason in its tooltip**, so it says why before it is pressed
  rather than after.

  Five new door tools behind it (`internal/tools/gitctl.go`, split from
  `gitstate.go` because that file's own header promises "REMOTE OPERATIONS ARE
  REPORTED, NEVER PERFORMED" and a file must not quietly stop meaning what it
  says at the top): `git_commit`, `git_push`, `git_pull`, `git_branch`,
  `git_remote`. Every one closes its child's stdin, jails paths to the
  tenant's Home, and reads the remote wall without ever opening it.

  **Nothing here fires on its own.** RULE 6 is untouched: these are the
  buttons on the operator's glass and the hand on the button is his.

  **Plain git, not `gh`.** The GitHub CLI is free, open source, installed and
  authenticated on this machine, and it still does not go in: RULE 4 walls
  anything needing someone else's server "even when the remote thing is
  better, free, or open source", and atlas law 6 is hand-roll or refuse.
  Everything named — branches, mains, open and closed, sending — is plain git.
  What `gh` alone would add is GitHub-side objects (pull requests, issues,
  releases, CI runs): a wall to open deliberately, not a dependency to acquire
  by accident.

- **`internal/tools` has strokes for the first time.** 19 of them
  (`gitctl_test.go`), on the package that carries every MCP tool handler and
  was named the estate's biggest hole in `tests/PROVING.md` that morning.
  Hermetic by law 5: each builds its own repository in `t.TempDir()`, none
  touches the record, none reaches a network — the two about sending prove the
  *refusal*, which is the only half provable without one.

### Fixed
- **The wall is the estate's, not one repository's.** The panel told the
  operator two different stories about one ruling — `research` "Sending
  allowed" and `atlas` "Sending OFF" side by side — because `dial()` read only
  `<Home>/.env`, and a carried tenant has no `.env` of its own. He had not
  shut a wall for atlas; atlas was looking in the wrong place. `dial()` now
  reads one level up, and that bound is not invented: it is the door's own
  ground law from `main.go` ("one level up, one level across"). It stops
  there, because walking to the filesystem root would leave the ground
  (RULE 1) and a stray `.env` in `Desktop\` must never open this estate's wall.

- **`readGit()` threw on every navigation away from the dashboard.** It
  captured `home-git-card`, `home-git` and `home-git-controls`, *then* awaited
  the door. A route away during that round trip left all three pointing at
  detached nodes — and writing `innerHTML` into a detached node SUCCEEDS,
  which is what hid it; the throw landed one line later on
  `document.getElementById('git-commit')` returning null. Both the 15-second
  poll and every turn-end call it, so it fired constantly and killed the rest
  of the handler each time. The elements are re-acquired after the await and
  the buttons are found through the bar, not the document.

- **The door was started without `--atlas-bin`, so nothing could reach the
  spine.** `verify_chain` answered `exec: "atlas": executable file not found
  in %PATH%`, which is what put three of the six workflows in the red.
  `atlas-mcp` defaults the flag to the bare string `"atlas"` and does none of
  the built-tree lookup `atlas-door` does. Relaunched with it;
  `verify_chain` now answers `verdict=INTACT`. The code default is still a
  trap and is written up as a ruling in `tests/PROVING.md`.

- **The door's `--manjuel` had been mangled into an error.** `mcp.err` held
  `refused: "C:/.../manjuel.py" is not a landed command` — the `python `
  prefix was lost by a PowerShell `-ArgumentList` earlier the same day, so the
  council engine was never wired. Restarted correctly; `mcp.err` now carries
  only its startup notes.

- **`tests/e2e/_start_mcp.ps1` pointed at the wrong tree.** All three of its
  lines named `C:\Users\novad\Desktop\Archive\atlas` — the pre-split copy,
  outside the ground RULE 1 fences, which nobody edits. A suite started
  against it would have proven a repository no one was changing. Every path
  now derives from the script's own location.

## [0.1.2] — 2026-09-10

### Changed
- **The stone moniker is struck from the version.** `0.1.1+f1` → `0.1.2`, in
  all fourteen places it was pinned: the six `VERSION` files, `Cargo.toml`,
  `core/src/version.rs`, both Go `main.go`s, both webapp handlers, and the two
  test harnesses. The stones are still named where they belong — THE_ROAD,
  STATE_OF_BUILD, the released CHANGELOG headers — but the version is now only
  what the thing IS, not which sitting cut it.

  **The drift catcher was inverted, not deleted.** `core/src/version.rs`'s
  tests used to REQUIRE a `+` and a stone; they now REFUSE one, so the
  moniker cannot creep back unnoticed. And `version.ps1` — the canonical
  bumper — was force-appending a stone in `Format-Version` and defaulting a
  stoneless version to `"f1"` in `Parse-Version`, so the very next
  `bump patch` would have quietly rewritten `0.1.2` as `0.1.2+f1` and
  re-broken every pin. The stone is gone from it entirely and it now refuses a
  version carrying one. Same trap as the flow cutter, one file over.

  **The prove battery caught what grep missed.** Five `VERSION` files under
  `line/` carry no extension, so the first sweep walked past all of them; the
  Rust spine's `version-cross` stroke named every one by path on the next run.
  `version.ps1` now says out loud that its six files are not the only pins and
  points at `tests/prove.py` for the rest.

### Added
- **The engine card says how long it has been standing, and when it is idle.**
  The card already showed `started 10:58:58 AM` — a clock time you have to
  subtract from to learn anything. It now ticks a live elapsed beside it, and
  turns amber with `— idle Nm` once nothing has run for five minutes.

  The measurement behind it, taken across every sitting the core has ever
  recorded: a standup gets 69 seconds of engine time per run; sittings of two
  runs or fewer get 208, and there are 63 of them — **5.3 engine-hours for 91
  runs**. Twenty-two sittings were never closed at all. Sitting 74 held an
  engine thirty minutes for 2 runs, 82 held one fifty-four minutes for 5, and
  166 held one **sixteen minutes for zero**. The record had known for weeks;
  nothing on the glass said a word.

  **Idle is measured from the last turn, not from boot.** A first cut went
  amber only when nothing had EVER run, which misses the shape the waste
  actually takes — 74 and 82 both did work, then sat. A running turn is never
  idle however slow the model is: this must not scold a slow rack, only an
  engine nobody is using.

  Ticks at one second, not on the 15s poll, which would read as a broken clock.
  The interval clears itself the moment the span leaves the DOM — an
  idle-engine warning that leaked timers would be its own joke.

  `static/js/home.js` (`Home.age`), `static/css/app.css` (`.eng-idle`).
  Operator: "we can just add that to the dashboard to view as tasks are
  running in real time, right?"

- **The card counts the turns, from the door.** `/run/state` now carries `runs`
  and `last_run`; the engine counts every turn it pumps, in `Engine.tick`.
  Before this the glass used `Run.turn` — only what THIS TAB had seen, empty
  after a reload — so an engine that had run ten turns read as untouched.

  **A slash command is housekeeping, not work.** Booting sends `/warm` and
  `/status` through the same path, so a freshly opened engine reported "2 runs"
  before anyone asked it anything, and **"0 runs" — the state most worth
  shouting about — was unreachable.** Counted in `Run` after `pump` returns
  rather than inside `pump`, because pump cannot see the objective and only the
  caller knows what it was. An `Answer` always counts: that is his hand.

  **Idleness can never predate the engine.** With no runs, the client fell back
  to its own `turn.ended` — which survives a reboot — and a
  THIRTY-EIGHT-SECOND-OLD engine reported `idle 14m`, counting from a turn a
  previous engine had run. The floor is now this engine's own start.

  `internal/engine/engine.go`, `internal/tools/runstream.go`,
  `static/js/council.js`, `static/js/home.js`.

- **A turn is visible in every browser, not only the one that started it.**
  Operator: "i want to be able to see it runing in sync on my chromium browser
  with your internal browser."

  `/council/stream` belongs to whoever opened it, so a second window could not
  know a turn was running and would not learn until its own 15s poll — by then
  the turn was usually over. **Storage could never have fixed this**:
  sessionStorage is per-tab, localStorage is per-browser. The server is the
  only place two browsers can agree, so `pipeSSE` now mirrors every council
  line onto the broadcast bus `/api/events` and `/ws` already serve, and
  `Run.mirror()` follows it. The runner ignores its own echo (`running` is the
  whole test) or every event would be doubled in its trace.

  **A watched turn needed somewhere to land.** The runner pushes its own pair
  into the thread in `ask()`; a mirroring window never did, so every event
  found no live bubble and the page sat on "waiting for the engine" while the
  answer streamed past it.

- **THE BUS HAS NEVER SENT THE TYPE IT IS KEYED ON.** `SSE` marshalled
  `e.Data` alone, dropping `e.Type` — so `App.onEvent`, which switches on
  `e.type` across eleven events, **had never fired once**. The struct already
  carried `json:"type"`; only that one line disagreed. Fixed, and the toasts
  work for the first time.

- **The boot report is kept.** It lived only in a `<pre>` that `render()`
  rebuilds empty and hidden, so a refresh discarded the RECORD, GATE, RACK and
  VOICE the boot had reported and the only way back was rebooting a healthy
  engine. Now written to the settings store, debounced, **keyed to the
  session** so a dead engine's report is never painted over a live one.

- **The conversation is kept, so a reloaded browser is not an empty box.**
  Mirroring live events was only half of "keep the boot report and the run
  turns": `Chat.thread` is in-memory per tab and `Run.turn` is sessionStorage,
  also per tab, so a browser that reloaded AFTER a turn showed the engine card
  and nothing else. That is exactly how he was checking — "i have been
  reloading my external browser tab every once in a while to watch and see if
  there is parity" — and there never could be. The thread now goes to the
  settings store, keyed to the session, and any browser restores it on load.

- **`onRun` HAS THROWN AT THE END OF EVERY TURN SINCE a014c77.** That pass took
  the sittings strip off the launchpad at his markup and deleted
  `Home.readSittings` — but left `this.readSittings()` standing in the turn-end
  handler. A `TypeError` on every completed turn, silent, killing the rest of
  the handler. It cost nothing while it was the last statement, and the moment
  anything was added after it that thing simply never ran: the kept
  conversation looked correct in every unit and stored nothing at all. Found
  by asking the live page which of the three calls threw, rather than reasoning
  about it.

- **A council bubble's words are in `turn.answer`, not `text`.** `line()`
  renders from `m.turn` and leaves `m.text` empty, so a first cut of the keeper
  filtered on `m.text` and discarded every answer, keeping only what he typed.

- **Only a real start opens a watched turn.** The mirror opened one on ANY
  event, so the trailing lines of a turn the tab had just run — arriving after
  `running` went false — opened a second, empty turn and pushed "(a turn
  started in another window)" into the runner's own conversation.

- **The broadcast bus was 32 deep and dropping.** `broadcast` drops rather than
  blocks, which is right — one slow watcher must never hold up a turn — but at
  32 a council turn's token events made dropping the normal case. 512 deep, and
  the writer now drains in batches and flushes once instead of flushing per
  event, which is what let it fall behind in the first place.

- **THE BALL — one command proves the whole of atlas.** `tests/prove.py`
  gathers the eight places atlas proves itself: the Rust spine, both Go
  modules, the two batteries shipped inside the binaries, **twenty-seven**
  golden verifiers, the six workflows and the E2E suite. AGENTS.md named
  four verifiers; nobody had run the other twenty-two, which is how two legs
  stayed red for weeks without anyone seeing it.

  **It answers in three verdicts, not two.** `ABSENT` means a leg named a
  dependency this ground does not hold — a read-only source ground never
  copied in, a binary not built, a door not answering. ABSENT is never
  counted as a pass and never silently skipped: it prints the exact path or
  command that would answer it, and it does not exit red, because nothing is
  broken — something is missing, and the difference is the whole point. Only
  FAIL exits red. Every child runs with `stdin=DEVNULL`, so the ball is safe
  to run from inside a live engine turn.

  Standing today: **22 held · 15 absent · 0 broke**. The fifteen absences are
  fourteen cutters plus one Rust stroke whose read-only oracles
  (`estate\`, `secondbrain\`) are not in this ground. Their goldens are all
  here and green; what is gone is the ability to re-cut them and to notice
  the source drifting. That is a ruling for the operator — restore the
  grounds read-only, or retire those cutters with the goldens frozen as the
  authority. Substituting anything would break law 2 outright.

  `tests/PROVING.md` is the map: every leg, what it costs, what it needs,
  and the seventeen packages that carry no prover at all — `internal/tools`
  first among them, where every MCP tool handler lives.

### Fixed
- **`internal/rack` had been red since the repo split.** Four strokes wanted
  `tests/fixtures/rack_open_ground/state/rack_ledger.jsonl`. Git does not
  track empty directories, so the fixture ground came over empty in the H0
  pull and nothing said a word. The right fix was not a hand-written file
  but running the cutter that owns it — `tools/cut_rack_open_vectors.py`
  builds that ground by definition — after which the five tracked goldens
  judged it byte-exact.

- **The door battery had no binary to shell.** `TestDoorProveStrokesGreen`
  drives `cmd/atlas-door` against the Rust spine over a real loopback
  socket, and the Rust binary was never built in this ground. `cargo build
  -p atlas`. The prover had been behaving correctly the whole time —
  refusing by name rather than fabricating, exactly as law says.

- **`cut_flow_vectors.py` was behind its own fixture, and would have eaten
  it.** `ce9c390` added the `run` node kind to the flow contract and updated
  `flow.go` *and* `flow_vectors.json` — but not the cutter that owns the
  fixture. So `--verify` had been red since; worse, running the cutter
  *without* `--verify` would have rewritten the fixture, stripped `run` back
  out, and turned `internal/flow` red with no visible cause. The cutter now
  carries the seven-kind contract and refuses a `run` node with no
  objective, exactly as `flow.go` does. A full re-cut is now a no-op. (The
  seventh refusal's keys also sort like every other entry now — the giveaway
  that it had been hand-added rather than cut.)

### Note
- Static assets are compiled into the binary (`//go:embed static/...`), so a
  change under `static/` needs `go build -o atlas-webapp.exe .` and a restart
  before it reaches the glass. Editing the file alone does nothing.

## [0.1.1+f1] — 2026-09-08

### Added
- **E2E test suite**: 84 scenarios across 12 categories
  - S1: Binary Smoke (5), S2: MCP Tool Surface (8), S3: Write Tools (5)
  - S4: Mesh B2 (8), S5: Rack F1 (10), S6: Guard (5), S7: Tenant (4)
  - S8: Ollama Integration (10), S9: Webapp (6), S10: Cross-Impl (4)
  - S11: Agent Lifecycle (6), S12: Prove Chains (3)
- **6 CI/CD pipelines** (parallel jobs in ci.yml)
  - SPINE: Rust core (12 stages), LINE: Go MCP (11 stages)
  - GOLDEN: Python verifiers (11 stages), AGENT: 40-seat validation (11 stages)
  - WEBAPP: GUI + API (18 stages), OLLAMA: Live integration (14 stages)
- **6 agent workflows** with Python scripts
  - SCOUT: read-only survey (5 steps)
  - STEWARD: memory + testimony via Ollama (5 steps)
  - MESH: encrypted communication (7 steps)
  - GATE: injection blocking, PII stripping (5 steps)
  - TOWN: task scheduling (4 steps)
  - OPERATOR: full lifecycle (12 steps)
- **Ollama prover**: stdlib-only Python harness
  - Tests 11 models (qwen3.5, llama3.2, phi4-mini, gemma4, deepseek-r1, etc.)
  - Direct Ollama API + MCP integration + webapp API
  - JSON output, exit codes, timeout handling
- **Documentation**: PIPELINES.md, WORKFLOWS.md, OLLAMA_PROVER.md, ACCEPTANCE.md, E2E_SCENARIOS.md

### Changed
- `ci.yml` expanded from 1 pipeline to 6 parallel pipelines
- `generate` calls use chat API for thinking-model compatibility (qwen3.5)

## [0.1.0+f1] — 2026-09-08

### Added
- **Rust core**: prov-hash, ground-prove, atlas-api, store crates
- **Go MCP server**: 25 tools + HTTP transport + embedded GUI (port 8090)
- **Go TUI**: Dashboard, traces, agents, chain view, mesh, rack, format output
- **Go webapp**: Observability GUI with real-time SSE (port 8091)
  - Dashboard with stats, recent traces, agent roster
  - Agent registry with full .us declaration viewer
  - Trace log with SHA-256 hash chain
  - Tool surface with JSON argument invocation
  - Evaluations engine with pass/fail scoring
  - Message bus with Discord/Slack/WhatsApp adapters
  - Settings for MCP connection, eval thresholds, provenance
  - Search across agents and traces
- **Agent system**: 40 .us declarations validated, enrolled, documented
- **Skills**: prove, orient, enroll
- **Python verifiers**: cut_canon_vectors, cut_chain_verdicts, cut_us_vectors, fold_agents
- **TUI extractField**: Auto-find array field when `*` hits a map
- **YAML format**: Fixed `[]map[string]any` to `[]any` for type switch compatibility

### Governance
- `can_approve: false` structural enforcement across all 40 agents
- Covenant hash `1512741580b7239b` verified in all declarations
- Append-only witnesses: SEAT_LOG.md + STATE_OF_BUILD.md
- Forbidden verbs absent by construction
- Zero external dependencies enforced

### Documentation
- 54+ specification and design documents
- 40 agent documentation files with hierarchy index
- 3 skill documentation files
- GUI gap analysis (Atlas vs Langfuse/Langsmith)
- Build plan with phased acceptance criteria
- MIT License
- Contributing guide
- Full changelog

### Tests
- 92 Go tests (line workspace)
- 85 Rust tests (cargo test --workspace)
- 4 Python verifiers
- MCP 58-stroke prove
- TUI end-to-end verification against live MCP
- Agent enrollment validation (40/40)

### Fixed
- extractField: `agents.*.name` transform path now works correctly
- extractField: Auto-discovers first array-valued field when `*` encounters a map
- YAML format: `[]map[string]any` changed to `[]any` in rbac/agents list handlers
- TUI help: Changed `*.name` example to `name`
