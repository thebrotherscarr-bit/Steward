# Changelog

All notable changes to ATLAS will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

Versions are plain semver from 0.1.2 on. Through 0.1.1 they carried a build
tag naming the stone that cut them — `0.1.0+a1` through `0.1.1+f1`. The
operator struck the moniker 2026-09-10: *"remove the moniker for the stones,
no letters in my versions."* Released headers below keep the tag they shipped
under, because they are the record of what happened.

## [Unreleased]

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
