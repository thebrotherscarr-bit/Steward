# SPEC_CONTROL_CENTER — the manjuel.us private dashboard

*PRD, drafted 2026-09-08 at the operator's word: "atlas is the SMB router for
the manjuel.us system, the private dashboard, the local control center …
a whole UX/frontend that I can use for running the system, so I don't have
to keep running terminals … a modern webapp that can spin up multiple
virtual environments to query different workflows and pipelines for
different sets of agents and models … basically a custom agentic routing
harness." Ruled 2026-09-08: atlas absorbs manjuel.py's verbs; Python retires.
**SUPERSEDED 2026-09-09 by ADR-001 (§11), ACCEPTED: Manjuel is the permanent
engine and atlas is the control plane above it. Python does not retire. The
verbs still move to atlas's surface; the ENGINE does not.**
Audience: the operator and his agents now; outside users later.*

*Status: DRAFT, amended 2026-09-08 on the operator's four rulings (below,
§9). Home: `Desktop\Research`, the one ground; `Desktop\Archive\atlas` is a
read-only artifact — walked and copied from as needed, never written, the
standing `estate` had. Nothing here is a work order until he names the
piece. Every number is read from the two records as of 2026-09-08; the
source is named where it is load-bearing.*

*THE GOVERNING DOCUMENT — amended 2026-09-09 on the operator's word: "we
are reconciling the atlas MCP and the manjuel.py work so that the manjuel.py
has a whole frontend, the atlas system is essentially ready to host the
Manjuel ... implement the full reconciliation plan to make this have parity
with the current market offerings." Four plans described this one system
and none governed. They are reconciled here, and from this line THIS FILE
GOVERNS:*

| plan | date | what it is now |
|---|---|---|
| **`SPEC_CONTROL_CENTER.md`** (this file) | 09-08, amended 09-09 | **GOVERNS.** The architecture, the seam, the stones, the acceptance. |
| `SYSTEM_DESIGN.md` | 2026-09-08 | The appliance and the business. Its T-stones stand and its requirements F1-F10 stand; where it and this file disagree on the seam, this file wins (Appendix D). |
| `worlds\atlas\LAUNCH_PLAN.md` | 2026-09-08 | The calendar. Dates and order only; it settles no architecture. |
| `Archive\atlas\ATLAS_PRODUCT_PLAN.md` | 2026-09-09 | **REFUSED IN PART.** Its surface work is harvested (§4.7); its Phase 3 and Phase 5 break both charters and are refused by name (§3). Folded, not deleted (LAW 1). |

*Read in full for this amendment (2026-09-09): this file, `SYSTEM_DESIGN.md`,
`SPEC.md`, `worlds\atlas\LAUNCH_PLAN.md`, DAYBOOK's last entry, HANDOFF's
newest block, CHANGELOG's Unreleased, TASKS' open lines, `manjuel/serve.py`;
and in `Desktop\Archive\atlas` at his word — `CHARTER.md`, `THE_ROAD.md`,
`ATLAS_PRODUCT_PLAN.md`, `docs/GUI_GAP_ANALYSIS.md`, and in `line/`:
`cmd/atlas-mcp/main.go`, `cmd/atlas-mcp/prove.go`, `internal/protocol`,
`internal/tenant`, `internal/tools`, `internal/guard`, `internal/ground`,
`internal/rbac`, `internal/httpserver/auth.go`. NOT read whole: atlas's
`STATE_OF_BUILD.md`, `DELIVERABLE.md`, `docs/PLAN_GUI_IDE.md`, `webapp/`,
and Manjuel's `DESIGN.md`, `BUILDPATH.md`, `REFUSALS.md`. Nothing below rests
on the unread. The market facts in §7.2 come from one read-only web reach
on 2026-09-09 — the single reach outside the ground, at his word.*

*Archive stays the artifact and the golden source; **the finished product
lands in `Desktop\Research`** (his word, 2026-09-09, and §9 ruling 3).
Nothing in `Archive\atlas` is written by a hand (ESTATE LAW 2).*

---

## 0. The two systems, in one paragraph each

**Manjuel** (`Desktop\Research`, `manjuel.py` → `manjuel/`, 27 modules,
14,718 lines, one dependency: `ollama`). A sequential, markdown-declared
council of 14 small local models over 37 skills and 5 pipelines. Every run
passes a sealed law gate first, every tool runs through exactly one seat
(the Router, 5 hops), every claim is checked against what ran, every run is
written to `logs/` and tolled in `SEAT_LOG.md`. It is a REPL: `input()` at
ten call sites, `print()` as the only channel, `KeyboardInterrupt` as
control. It listens on nothing — by its own SPEC §7.3, on purpose. It is at
0.1.6 unsealed; DONE is 0.1.8 (SPEC §4 with no OPEN line). Its operator's
word, in its own record (DAYBOOK 2026-09-08): *"desktop/archive/atlas has
the ENTIRE webapp/gui end of this thing … there will be a merger at some
point."*

**atlas** (`Desktop\Archive\atlas`, Rust · Go · C++ · TS, zero external
deps, `0.1.2`). The provenance spine: SHA-256, canon, Manjuel verdicts
(`EMPTY|INTACT|FLIP|TAMPER`), Merkle, covenant, a SQLite mirror where
`state = fold(record)`, and THE LINE — a multi-tenant MCP server (**62**
tools, `:8090`) carrying every project by name. Around it: `atlas-town`,
`atlas-door :8080`, `atlas-tui` (a subcommand CLI, not yet a TUI), a
`webapp :8091` whose store is a JSON file of its own, and 40 enrolled `.us`
seats with `can_approve:false` by construction. All stones P0–G carry
witnesses; the operator holds each cutover switch. **Corrected 2026-09-09:**
this file and `SYSTEM_DESIGN.md` both said 25 tools until today; the true
count is 62, read off `line/internal/tools/tools.go` (62 `r.add(Tool{...})`
calls). The 37 unnamed are the N1–N6 and Phase-3 stones — chat, town, flows,
the rack quartet, the playground, the team bridge, auth, RBAC, VC — and
atlas's own `THE_ROAD.md` does not carry them either (its B1 row still reads
"16/19 tools real"). Neither system's road matches its code; §4.4 and §6
are re-scoped against the code, not the roads. Ruled 2026-09-08: it
moves into `Desktop\Research` piece by piece, "pulled out of the archive as
needed"; the Archive copy stays as it is, an artifact and a golden source.

**What each lacks is exactly what the other has.** Manjuel has the engine and
the honesty machinery but no face and no socket. atlas has the faces, the
seam, the multi-tenant door and the receipts, but no engine — its webapp
shows stubs. The control center is the seam between them, built on atlas's
own rule of one computer.

---

## 1. Problem statement

The operator runs his system from three or four terminals: Manjuel REPL,
`atlas-mcp --http`, the webapp, Ollama. Each turn is one ground, one
pipeline, one rack, chosen by hand with `/use`. To try a second seat set or
a second model tier he edits `agents/` and `/reload`s, or runs `/model
<tag>` as a measurement — under the law that nothing is edited while a
sitting is open. Nothing he has shows him a run as it happens across seats,
compares two runs, scores a seat, or tells him the court is about to blow
its 600-second turn budget before it does. The evidence is all on disk
(740 transcripts with their exact prompts, 98 sittings, 12 parity cases,
seven live standups) and none of it is visible without opening a file.

The cost of not solving it is his afternoons: the record shows a day
(2026-09-08) in which a court sat 12½ minutes for a seat that would never
speak, a "finished" that was a `UNIQUE constraint failed`, and a delivery
that named a commit that never happened — each found by reading transcripts
after the fact. A dashboard whose only source is the record would have
shown all three as they happened.

---

## 2. Goals

1. **No terminal for an ordinary day.** Open, run, read, toll, close — every
   `/` command Manjuel offers today has a place in the control center, and a
   sitting can be run start to finish without a shell.
2. **Many environments, one record discipline.** The operator spins up N
   isolated environments — each a ground with its own declarations, seats,
   models, pipelines, sessions, index and workspace — and runs them side by
   side, with the same law gate, the same toll and the same append-only
   record in each.
3. **Routing is deterministic before it is generative.** User input is
   routed to an environment and a pipeline by a rule table the operator
   writes and can read; a model is consulted last, is labelled testimony,
   and never routes alone.
4. **The record is the UI.** Every trace, waterfall, eval, session and
   alert view is derived from `logs/`, `sessions/`, `SEAT_LOG.md`, the
   parity history and the hash chains. No second database of truth. (atlas
   `docs/PLAN_GUI_IDE.md` principle 2; Manjuel SPEC §3 invariant 10.)
5. **Market parity where it counts, receipts where they don't have it.**
   Per-agent traces, waterfall, evals and datasets, live monitoring and
   alerts, sessions and replay, a playground, and a real TUI — every one
   carrying a SHA-256 receipt and a Manjuel verdict, which Langfuse, LangSmith
   and AgentOps do not.

## 3. Non-goals

- **Not a cloud product, not a hosted model, not an API key anywhere.**
  Both charters rule this (Manjuel RULE 4; atlas zero-deps + loopback
  doctrine). Loopback only until the operator rules otherwise.
- **Not a rewrite of Manjuel's law.** Every guard, gate and refusal in
  `REFUSALS.md` §1–22 carries across the seam unchanged; the port is
  golden-master parity against Manjuel's own transcripts, not a redesign.
- **Not a second executor.** Exactly one seat executes tools (Manjuel SPEC §3
  invariant 2). The control center never calls a skill itself.
- **Not approval.** `can_approve` stays false everywhere; landing memory,
  paying an attended toll, committing, tagging, pulling a model — the UI
  presents, the operator's hand confirms. Forbidden verbs stay absent from
  every route table (atlas law 5).
- **Not a bigger-model project.** SITTING LAW 3 governs every seat the
  control center seats: start small, move up on a measured failure.
- **Not multi-user.** "A second user is a fork" (Manjuel SPEC §1). Outside
  users are a later phase behind an authenticated gate; this spec keeps the
  door shaped for it (tenant = `name=path`, already in THE LINE) and builds
  none of it.
- **Not a change to Manjuel's path.** Manjuel's build path (0.1.5 bounds →
  0.1.6 story → 0.1.7 door/court → 0.1.8 seal) is its own and reaches DONE
  on its own terms. The one Manjuel change this spec needs — the headless
  driver, §6 P0-1 — was named by the operator 2026-09-08 ("build it now")
  and is one piece under RULE 10; nothing else in `manjuel/` moves for the
  control center until he names it.

- **Not the LLM bridge (refused 2026-09-09).** `ATLAS_PRODUCT_PLAN.md`
  Phase 3 proposes an `atlas-proxy` sitting in front of OpenAI and
  Anthropic, a `pip install atlas-sdk`, an `npm install @atlas/sdk`,
  auto-instrumentation of the vendor clients, and cost tracking against a
  cloud pricing table. Every one is refused by name: RULE 4 (no cloud
  service, no API key, no hosted model), both dependency laws (Manjuel one,
  atlas zero), and `SYSTEM_DESIGN.md` §1.2 — "$0 / month", "no WAN, no
  cloud, no key". Cost here is seconds, evictions and watt-hours (§6 P2).
- **Not the public deployment (refused 2026-09-09).** The same plan's
  Phase 5 proposes Let's Encrypt for public deployments, OAuth/SSO via an
  OIDC provider, and Docker/Kubernetes. Refused: LAW 6 (nothing
  world-facing without his hand), RULE 4, and the LAN posture of
  `SYSTEM_DESIGN.md` §5. The gate this system gets is T7 — the LAN
  interface, one operator secret, a self-signed certificate.
- **Not a second config grammar (refused 2026-09-09).** `atlas.yaml` is
  refused. This estate declares in markdown a person can read — `agents/`,
  `skills/`, `pipelines.md`, `ROUTES.md`, `ENV.us`. A YAML file beside
  them is a second place for the truth to live.
- **Not a retreat from what is already built.** The same plan says no to a
  prompt playground, no to a workflow builder and no to model hosting.
  All three exist in `tools.go` today — `prompt_*` (6), `flow_*` (10),
  `rack_pull`. A plan may not refuse what the code already carries; those
  tools are folded into the surface (§4.4), not deleted (LAW 1).
- **Not a rewrite of the engine (ADR-001, 2026-09-09).** `run_pipeline` and
  the 14,718 lines of guards around it stay in Python, where they were
  earned and where 1,872 strokes prove them. A port delivers no capability
  and risks the one component whose defects are silent: a guard that fails
  to fire does not crash, it lets a claim through. The engine moves only on
  a MEASURED failure, with the number written down — SITTING LAW 3's logic,
  applied to code.
---

## 4. The system, defined

### 4.1 The shape

```
┌──────────────────────────────────────────────────────────────────────────┐
│  THE GLASS  — browser SPA (vanilla JS, WebCrypto)  ·  atlas-tui (real)   │
│  environments · run · traces · waterfall · evals · rack · record · toll  │
├──────────────────────────────────────────────────────────────────────────┤
│  THE LINE  — atlas-mcp (Go, :8090)  · JSON-RPC 2.0 + SSE                 │
│  tenant = world · 62 tools + the env_* / run_* / route_* families        │
├─────────────────────────┬────────────────────────┬───────────────────────┤
│  THE ROUTER (Go)        │  THE ENGINE            │  THE RACK (Go)        │
│  rule table → env +     │  Phase 1: manjuel.py     │  Ollama 127.0.0.1:    │
│  pipeline; intent port; │   --headless (stdio)   │  11434 · VRAM planner │
│  model last, as         │  Phase 2: Go port,     │  · one GPU scheduler  │
│  testimony              │   golden-master parity │  · tiers              │
├─────────────────────────┴────────────────────────┴───────────────────────┤
│  THE SPINE  — atlas (Rust): sha256 · canon · Manjuel verdicts · merkle ·   │
│  covenant · SQLite mirror (state = fold(record)) · export byte-identical │
├──────────────────────────────────────────────────────────────────────────┤
│  THE RECORD, per environment: agents/ skills/ pipelines.md commands.md   │
│  law/ sessions/ logs/ (+_prompts) SEAT_LOG.md memory.md index/ workspace │
└──────────────────────────────────────────────────────────────────────────┘
```

Rule of one computer (atlas `SPEC_SEAM`): the Go services never
reimplement provenance math; they exec `atlas` with an argument array,
handshake on `"atlas_seam": 1`, and read one JSON object. The same seam
is used in the other direction for the engine: THE LINE execs the engine
process, speaks JSON lines on stdio, and reads its events. **No engine
socket.** This is the one design that satisfies Manjuel's "no listening
socket" and atlas's "every hash in one place" at the same time.

### 4.2 An environment

An **environment** is a ground: a directory carrying exactly what
`manjuel` reads at `Session()` today (`cli.py:45`), and nothing else.
Ruled 2026-09-08, twice: **the origin is `Desktop\Research` itself;
environments live at `worlds/<name>/`, with the same provenance as
`worlds/manjuel` — read-only by position, never an index root for the
ground, used only as source.** (First ruled to `agent_workspace/`; moved
the same afternoon: *"put the environment into /worlds and give it the same
provenance as the manjuel folder in there. read-only. not indexed for the
ground, only used as source."*) What that provenance means, in the
record's own words (`index_roots.txt`, sitting 78): *"NO WORLD IS A ROOT"*
— no entry in `index_roots.txt` ever resolves under `worlds/`, and a stroke
asserts the property; `worlds/` is not versioned (`.gitignore`); the
origin's Manjuel never writes into a world. Each environment holds:

| in the environment | source | mutability |
|---|---|---|
| `agents/*.md` (seats) | forked from a template env, or edited in the glass | declarations; hot-reload at turn boundary (Manjuel `watch.py`) |
| `skills/*.md` | forked | declarations |
| `pipelines.md`, `commands.md` | forked | declarations |
| `law/` | **copied verbatim, sealed chain included** — `law/chain.jsonl` must verify in every env or no seat sits (REFUSALS §19) | frozen |
| `.env` | per env; never printed, never indexed (RULE 7 / LAW 9) | secret |
| `sessions/`, `logs/`, `SEAT_LOG.md`, `memory.md`, `memory/pending.jsonl` | born empty | append-only record |
| `index/vectors.db`, `index_roots.txt` | born empty; roots inside the env only | derived |
| `agent_workspace/` | born empty | the workspace jail |
| `ENV.us` | new: the environment's own `.us` declaration — name, template, rack tier ceiling, pipelines exposed, `can_approve:false`, enrolled in `master.db` like any seat | declaration |

**THE WORD, ruled here 2026-09-09.** Three names were in use for one thing:
this file said *environment*, `SYSTEM_DESIGN.md` said *world*, and the wire
field in all 62 tools is `project`. The prose word is **world** everywhere
from this line; **the wire field stays `project`**, because 62 landed tools
and every `--tenant name=path` invocation already use it and renaming it
buys nothing but a breaking change. *Environment* survives only as the name
of the glass page.

An environment is a **tenant** of THE LINE (`name=path`, `tenant.go`) and
a **Manjuel** in the spine (`atlas db import` of its `sessions.jsonl` and
`SEAT_LOG.md`; verdicts on demand). Spinning one up is `env_fork
<template> <name>` — a copy of the origin's declarations, never of its
record; forbidden by construction to fork *from* a client-tagged ground
(SITTING LAW 2) or to write anything into the origin's own record.

**Read-only by position, and what that buys.** `worlds/` is outside the
workspace jail, so the origin's seats cannot write into an environment by
construction: `write_file`, `embed_text` and the coder's landing resolve
only under `agent_workspace/` (LAW 8, `skills.py` `JAILS`). The origin's
readers may still *read* a world (the ground jail contains `worlds/` —
HANDOFF's open LAW 2 line), which is what "used only as source" permits;
the origin's index never embeds one (`NO WORLD IS A ROOT`), so a world's
declarations can never answer for the estate — the doctrine collision of
sitting 78 is the reason this provenance exists. **Each environment is
written only by its own engine**, run with that world as its ground (its
own `sessions/`, `logs/`, `SEAT_LOG.md`, `memory.md`, `index/`), and its
own `index_roots.txt` lists only itself. Its declarations and `law/` are
edited by the operator's hand (or the glass, as his hand), only while that
environment's sitting is closed (SITTING LAW 5). A stroke proves: no
origin write path resolves under `worlds/`; no origin index root does; an
environment's roots stay inside it.

**One writer per environment.** `sessions.jsonl` numbering is
read-then-append (`seatlog.next_number`), `thread.jsonl` is overwritten
per turn, `vectors.db` is one SQLite file. Two engines on one ground fork
the ledger — the inherited warning in `worlds/manjuel/AGENTS.md`. THE LINE
enforces it: one engine process per environment, one run at a time per
environment, refused by name otherwise.

### 4.3 The rack, shared

Environments are isolated in record and declarations; they are **not**
isolated in hardware. One Radeon RX 6800 XT, 16 GB, `OLLAMA_NUM_PARALLEL=1`
(Manjuel DESIGN §9: "a single-user sequential pipeline"). A court run is
25.8 GB on a 15 GB card and pays evictions on purpose (Manjuel memory.md
2026-09-04). So:

- THE RACK is one Go scheduler over Ollama. It owns the VRAM plan (port of
  `vram.py`: `KV_BYTES_PER_TOKEN`, `GRAPH_OVERHEAD`, 15 GB budget via
  `MANJUEL_VRAM_GB`), the tier table (llama3.2/phi4-mini → qwen3.5 4b/9b
  → coder 7b/14b → gemma4 e4b/12b → deepseek-r1 8b/qwen3-vl 8b), and a
  **seat-call queue**. Concurrent environments interleave at seat-call
  granularity; a run never sees another run's output; the queue is visible
  in the glass with its VRAM cost.
- Per-seat timeouts by model size carry over exactly (150 / 300 / 600 /
  700; turn ceiling 600 — Manjuel CHANGELOG 2026-09-08). An environment that
  would exceed the card's budget for its pipeline is told so before it runs
  (`vram.render`), not after.
- `rack_pull` and any download stay behind `MANJUEL_RACK_PULL` and an
  operator confirm.

### 4.4 The routing harness

Three layers, cheapest first — Manjuel's law "routing is deterministic before
generative" (DESIGN §13.5), extended one level up:

1. **The environment router** (new, Go). A markdown rule table the operator
   writes — `ROUTES.md`, same grammar as `commands.md` (`## Route: <name>`,
   `**When:**` phrases and patterns, `**Env:**`, `**Pipeline:**`,
   `**Method:**`). Longest match wins, like `intent.names_a_tool`. A `/`
   command in the glass is a route. An input matching no route goes to the
   **default environment, default pipeline**, and the glass says so.
2. **Intent** (port of `intent.py`, pure arithmetic, no model): names a
   tool, a file, a folder, a followup, gibberish, a big objective, wants
   writing, wants action — the same evaluation order as `run_pipeline`
   (pipeline.py:1117-1416), golden-mastered against Manjuel's transcripts.
3. **The Router seat**, inside the pipeline, as today. The only executor.

A fourth, optional layer: a **classifier seat** (smallest model, SITTING
LAW 3) consulted only when layers 1–2 name nothing, whose verdict is
recorded as testimony (`kind: routed_by_model`) and shown as such, and
which may pick among the operator's routes but may not invent one.

### 4.5 What the operator sees

Pages, in the order a day goes. Each names its **source of truth** —
never a page store.

| page | shows | source |
|---|---|---|
| **Environments** | every env: template, seats, rack tier, pipelines, last sitting, Manjuel verdict, VRAM footprint; fork / open / close / retire | `ENV.us`, `sessions.jsonl` tail, `atlas Manjuel verify`, `vram` |
| **Run** | the objective box (routes autocomplete like `/help`); the live run: law-gate stamp, seats waking in order, per-token stream, thinking withheld, tool calls with results, guard verdicts, `NEEDS:`, `OUT OF TIME`; cancel; the delivery with its `NOT EVERYTHING RAN` block | engine event stream; `transcript.name_for` known before stage 1 |
| **Traces** | every run across envs; filter by env, seat, skill, pipeline, verdict, time; open one → the transcript and the exact prompts, receipt-hashed | `logs/*.md`, `logs/_prompts/*.md`, `sessions.jsonl` |
| **Waterfall** | one run as a timeline: seat → elapsed → hops → skill → drift; the 600 s budget as a bar; sub-runs nested | `StepResult.elapsed`, `tool_calls`, `drift` per stage |
| **Seats** | the 14 (+40 atlas) declarations; per-seat: model, timeouts, may-call, wake flags; its runs, its failure rate, its OUT OF TIME count; `@seat` playground | `agents/*.md`, `.us`, traces |
| **Evals** | parity cases as datasets; standup as a suite; drift as a score; run an eval on an env; compare two runs of one objective (same env, two model overrides) side by side | `parity.md`, `parity_history.jsonl`, `standup_*.md`, `tests/last_run.json` |
| **Rack** | installed, resident, foreign, sizes, the queue, tiers, warm/unload; pull behind confirm | Ollama live; `rack.md` is the fold |
| **Record** | sittings, the toll, the story, memory landed and pending (land/drop = operator's click), git state (suggested command, never run), hands ledger | `SEAT_LOG.md`, `sessions.jsonl`, `memory.md`, `memory/pending.jsonl`, `gitstate.read` |
| **Alerts** | live: a seat over its timeout, a turn near 600 s, index rebuild refused, law gate refusal, a claim-check hit, VRAM over budget, `FLIP`/`TAMPER` on any chain | engine events + `watch.py` drain + `verify_chain` |
| **Law** | the sealed laws, the covenant hashes (`65118a147dd49ed9` Manjuel; `1512741580b7239b` atlas HOUSE), verify buttons, the four gate checks per run | `law/chain.jsonl`, `atlas covenant` |

And the **TUI**: `atlas tui` — the same pages over the same LINE, full
screen, stdlib only (ANSI raw mode, no curses dep), for the days he does
want a terminal. `atlas-tui` today shells out to `curl` (`main.go:569`);
that goes first.

### 4.6 THE LINE as the engine's supervisor — the process model

The seam is no longer a design problem. It is an adapter, and both halves
are built and proved:

- **`manjuel/serve.py`** (PROTOCOL 1, landed 2026-09-08) takes five
  commands on stdin — `objective`, `answer`, `cancel`, `close` — and emits
  seventeen events on stdout: `opened · text · run · report · seat · token ·
  tool · tool_result · needs_answer · delivery · refused · aborted ·
  cancelled · unreachable · error · note · closed`.
- **`manjuel.py --ground <path>`** (landed 2026-09-09; 1872/1872 and smoke
  60/60 on the operator's terminal) sits that door inside a world, with the
  world's own `sessions/`, `logs/`, `SEAT_LOG.md` and `index/`.

So `run_*` is a **one-to-one adapter over an existing wire**, not new
semantics. This is the whole reconciliation, in one table:

| THE LINE tool | the wire | what it buys |
|---|---|---|
| `env_open {project}` | spawn `manjuel.py --headless --ground worlds\<w>`, wait for `opened` | that one event carries sitting, session, git stamp, `rack_ok`, pipeline, pipelines, seats — the Environments page needs no second call |
| `run_start {project, objective, feed?, method?}` | `{"cmd":"objective", ...}`; the run id and transcript path come off the `run` event | `transcript.name_for` is known before stage 1, which is exactly what P0-5 requires |
| `run_answer {project, text}` | `{"cmd":"answer"}` | **the gate, on the wire.** Landing a memory, paying an attended toll and confirming a commit are all `input()` sites; none resolves without this call |
| `run_cancel {project}` | `{"cmd":"cancel"}` | mid-run this is `interrupt_main` (the REPL's Ctrl-C); at a pending question it is Ctrl-C at that prompt |
| `run_events {project}` | the event stream, SSE over the existing `--http` | the events are already JSON objects, one per line; SSE is a re-frame, not a translation |
| `env_close {project}` | `{"cmd":"close"}`, wait for `closed` | the toll is paid unattended if runs happened, as on exit |

Nothing in `manjuel/` moves for any of this. The engine is reached through
`cli.py`'s own functions, so a transcript written through THE LINE is the
transcript the REPL would have written — which is what makes P0-1's
byte-compare acceptance meaningful and what keeps H6's golden-master port
honest later.

**What THE LINE must own, that neither half owns today.** *Promoted to P0
by ADR-001 (§11): under a permanent Python engine the supervisor is not a
convenience, it is the single point of failure for the whole estate, and it
is the least-proved thing in either codebase — zero strokes today. It gets
the same stroke discipline the engine got. See P0-15.*

1. **Process lifecycle.** One long-lived Python process per OPEN world —
   not one per call. THE LINE spawns it, holds the pipes, and reaps it on
   `closed`. On its own restart it must reap orphans: a `manjuel.py` left
   running holds that world's sitting open, and an open sitting is what
   RULE 9 forbids editing under and what `tests/release.py` refuses a tag
   over. An orphan here is a stuck estate, not a leaked process.
2. **Backpressure.** A streaming seat emits one `token` event per piece; a
   300-second court is thousands of lines. `run_events` fans out to N
   viewers, and a slow viewer must be dropped rather than allowed to block
   the pipe the engine is writing into. The engine has no flow control —
   `Wire.emit` swallows a closed pipe and moves on.
3. **The one-writer invariant, enforced by refusal.** One engine per world,
   one run at a time per world, refused BY NAME otherwise (§4.2). The
   engine guarantees it inside a process; THE LINE must guarantee there is
   only ever one process.

**THE ASK LOCK BECOMES PER-WORLD BEFORE `run_*` LANDS.**
`line/internal/tools/tools.go:52` declares `var askLock sync.Mutex` — one
package-level mutex, taken by every writing tool on every tenant. With one
tenant that is correct and costs nothing. With N worlds it serialises worlds
that share nothing: `remember` on `books` waits behind `rack_ask` on `TBC`.
Put a 600-second `run_start` under it and one world's court freezes every
tool on every world for the length of the turn. The lock is a per-ground
concern — *one pen per actor, one head per channel*, which is what the
comment above it already claims — so it becomes a map keyed by tenant home,
and `run_*` does not take it at all: one process per world already is the
invariant. **This is a precondition of P0-2, not a follow-up.**

### 4.7 The surface, harvested from ATLAS_PRODUCT_PLAN

That plan's Phase 3 and Phase 5 are refused (§3). Its Phase 2 is kept whole,
because it breaks nothing and it is the half of "market parity" that no
stone in this file covered: **the surface must lie about the depth.** Folded
into H3 as acceptance, not as a separate stone:

- **One word per thing, in the operator's English.** Trace → Activity; Eval
  → Quality Check; Tool → Action; Hash → Record ID; Manjuel → Audit Trail;
  RBAC → Access Level; MCP → Connection; Ground → Project; Tenant →
  Workspace. A **Technical Mode** toggle in Settings restores the internal
  words — a CSS class on `<body>`, no logic. The record's own words never
  change; only the glass's labels do.
- **No `prompt()` anywhere.** One `formModal(title, fields, onSubmit)`; a
  tool's form is generated from its `inputSchema` — which is precisely why
  P0-12 below has to land first, or every generated form will demand a
  `project` the caller does not need.
- **Empty states that name the next action**, error states with a Try
  Again, human durations ("3s", "2m") with milliseconds in the tooltip,
  hashes behind a Details expander, and a mobile layout — the phone reaches
  the glass at T7, so the glass must survive a phone.

This is the one part of the newest plan that survives contact with both
charters, and it is the part that decides whether the thing is usable.

### 4.8 Two skill surfaces, one placement rule

*Ruled 2026-09-09 with ADR-001. The operator: "we can add additional skills
as needed to either system, that's the beauty of it. it's essentially a unix
system." That is the strength; without a placement rule the two surfaces
overlap inside a month.*

There are two, permanently, and that is correct:

- **Manjuel skills** — 37 markdown files in a world's `skills/`, executed by
  the Router and no one else (SPEC §3 invariant 2), inside one world, after
  the law gate.
- **atlas tools** — 62 Go handlers on THE LINE, executed by the door, across
  worlds, for the glass.

**The rule:**

| the thing needs… | it is |
|---|---|
| a seat to reason about it, or it touches one world's record, or it must pass the law gate | a **Manjuel skill** — markdown, no code, hot-reloads at a turn boundary |
| to span worlds, or it is provenance math, or it serves the glass | an **atlas tool** — Go, or Rust behind the seam |
| neither | it should not exist |

A name may appear on both surfaces when both readings are true — `rack_list`
is the standing example: a seat asks it about its own rack, and the Rack page
asks it across worlds. That is not duplication, provided the rule says why.
What the rule forbids is the same job drifting onto the other surface because
that surface was easier to reach that afternoon.

---

### 4.9 THE VIBE CODING LOOP — a `run` node, a gate, and a walk away

The operator, 2026-09-09: "site up my vibe coding loop with atlas." His fourth
acceptance question names the shape: *"can i set a task and come back in 20-30
minutes to a gate question?"* This is that loop, and it is three parts already
in the build wired to each other -- nothing new was invented for it.

**The `run` node.** `flow`'s closed kind set gains one member:

    ask | prompt | seat | memory | eval | gate | run

An `ask` node reaches a **bare model**. A `run` node reaches the **whole
council**: the objective goes through the world's own Manjuel process, so the
sealed law gate stamps it, the one Router runs the tools, the dedup refuses a
repeat, and the recompose puts every failed tool in the answer. A `run` node
whose spec carries no objective (`question`) is refused at `Validate`, not at
run time.

**The refusal that keeps it honest.** A `run` node will NOT start an engine.
If no engine is open on that world, the node fails and the waterfall says why,
in those words. A flow that spawned a process behind the operator's back could
open a sitting he never opened -- and the sitting line is the lock (12.3).

**The gate is the return leg.** A `gate` node's title is now RENDERED against
the run's vars, so `{{out_work}}` puts what the council actually produced into
the question he walks back to. `flow_status` prints that question whole on the
waterfall -- untruncated, with the exact `flow_resume` command under it. The
pause lives in `flows/runs.jsonl`, so it survives the door restarting, the
engine closing, and the machine being left alone for as long as he likes.

**The loop, whole:**

| he does | the system does |
|---|---|
| `env_open {project}` | one Manjuel process for that world; refuses a world already being sat in |
| `flow_run {name: vibe-loop, inputs: {task}}` | the `run` node puts his task through the council; the `gate` node pauses; verdict `PAUSED` |
| *walks away* | nothing moves. No default is taken, nothing is landed, nothing is committed (RULE 6) |
| `flow_status {run}` | the waterfall: what ran, how long, the receipt per node, and the gate question in full |
| `flow_resume {run, continue\|stop}` | `continue` fires the pass-edges past the gate; `stop` ends it `STOPPED`, reached nodes standing |

**Proven live, 2026-09-09,** on the glass world against a real rack: fired
with no engine open -> `FAIL` with the reason on the waterfall; fired with the
engine open -> `PAUSED` at the gate in 4.1s with the council's answer inside
the question; the paused gate read back intact **after the door was rebuilt
and restarted**; `continue` -> the `land` node ran through the council and the
run closed `COMPLETE` in 7.8s total.

The spec that proves it is saved as `vibe-loop` and is three nodes:
`work` (run, `{{task}}`) -> `review` (gate) -> `land` (run, `{{out_work}}`),
with `work -> review` on `always` and `review -> land` on `pass`.

## 5. User stories

**The operator**

- As the operator, I want to open the glass and see every environment's
  state and Manjuel verdict, so that I know what is standing before I type.
- As the operator, I want to type an objective and have it routed to the
  right environment and pipeline by rules I wrote, so that I stop choosing
  `/use` by hand — and I want to see which rule fired.
- As the operator, I want to watch a run seat by seat with a budget bar, so
  that I see a court about to run out of time before it does, and cancel.
- As the operator, I want to fork an environment from a template, change
  one seat's model, and run the same objective in both, so that "move up on
  a measured failure" is one screen, not a day.
- As the operator, I want a trace I can open to the exact prompt each seat
  saw and the receipt hash of the transcript, so that "what did it actually
  see" is one click.
- As the operator, I want landing a memory, paying the toll and committing
  to be buttons that show me the text and wait for my hand, so that the
  gate stays mine and I stop typing three `input()` answers.
- As the operator, I want an alert when a Manjuel reads `FLIP` or `TAMPER`,
  when the law gate refuses, or when the card is over budget, so that the
  record tells me the moment it is wrong.
- As the operator, I want a TUI with the same pages, so that ssh and a bad
  day still work.

**A seat (an agent, human or model, working a ground)**

  in the glass, so that SITTING LAW 6 is one click and cannot be skipped.
- As a seat, I want my declaration, may-call list and timeouts shown as the
  engine reads them, so that a doc never lies about me (Manjuel agents.md:
  "facts are read, not written down").

**A future outside user (designed for, not built)**

- As a tenant, I want an environment of my own behind an authenticated
  gate, so that my record and my keys never touch another's. (Phase 4.)

**Edge cases the stories must survive:** the rack is unreachable (open the
ground, refuse runs, say so — Manjuel boot); a seat's `On Fail: prompt` fires
mid-run (the glass answers retry/skip/abort; headless default is `skip`,
recorded); two hands open at once (ledger tolerates, `--id` closes);
an environment whose `law/chain.jsonl` does not verify (no seat sits, ever);
a run with a pasted feed that trips `injection_markers` (refused, feed
withheld from transcript and index); the index rebuilding while a run
starts (`_INDEX_BUSY`: queue, don't interleave).

---

## 6. Requirements

### P0 — must have (the control center does not exist without these)

**P0-1 · A headless engine driver (Manjuel, one piece — ORDERED 2026-09-08,
built as `manjuel/serve.py`; see CHANGELOG Unreleased).** `python manjuel.py
--headless` (or `python -m manjuel.serve`): reads JSON lines on stdin
(`open`, `objective`, `answer`, `cancel`, `close`), writes JSON events on
stdout (`opened`, `law`, `seat`, `token`, `tool`, `verdict`, `needs_answer`,
`delivery`, `refused`, `closed`), stderr for humans. Replaces the ten
`input()` sites with an `answer` round-trip; passes `report=` and a
`stream_to` that emits events instead of `print`; `on_fail: prompt`
resolves through `needs_answer` with a per-run default. No socket. No
change to `run_pipeline`'s semantics.
*Acceptance:* the 60-case `smoke_cli.py` battery passes through the driver
with identical transcripts (byte-compare `logs/` against a REPL run of the
same objectives on a mirror); `KeyboardInterrupt` ⇢ `cancel` closes the
Ollama stream the way `_bounded_stream` does; the REPL is untouched.
*Owner:* named by the operator 2026-09-08; built on a mirror; "restart
required".

**P0-2 · THE LINE carries environments.** New tools, all naming their
ground: `env_list`, `env_fork <template> <name>`, `env_open`, `env_close`,
`env_retire` (fold: rename, never delete), `run_start {env, objective,
pipeline?, feed?, method?}` → run id + transcript path, `run_answer`,
`run_cancel`, `run_events` (SSE over the existing `--http`), `route_table`,
`route_dry_run <text>` → which route, which env, which pipeline, why.
Forbidden verbs absent by construction; the existing absence test extends
to the new tools.
*Acceptance:* `atlas-mcp --prove` gains strokes for every tool on temp
grounds (hermetic); two environments run two objectives and their
`sessions.jsonl` files each number from 1 with no cross-talk; a fork from
a `vault/`-tagged path is refused by name; `env_fork` writes only under
`worlds/<name>/` and refuses any other destination; no origin write path
(`write_file`, `embed_text`, `land_code`) resolves under `worlds/`; the
origin's `index_roots.txt` resolves nothing under `worlds/` before or after
a fork (the existing stroke, kept green); an environment's own
`index_roots.txt` resolves nothing outside its world.

*Amended 2026-09-09.* Re-scoped against the code rather than the road. The
surface is 62 tools; the `flow_*`, `prompt_*`, `seat_ask` and `rack_*`
families already cover ground this file assigned to P0-8, P1-2, P1-3 and
P1-4, so those stones are smaller than written. The families genuinely
absent are exactly the three named above. §4.6 gives the wire mapping,
which is one-to-one; the ask lock becomes per-world FIRST (§4.6); and
P0-12 through P0-14 land in the same package, or every new tool inherits
three live faults.

**P0-3 · The environment router.** `ROUTES.md` grammar, longest match,
default fallthrough, dry-run, the fired rule recorded in the run's
transcript header (`routed_by: <rule>|default|model`).
*Acceptance:* a golden `routes_vectors.json` cut from the operator's rule
file; `route_dry_run` reproduces every vector; an input that matches no
rule lands on default and the transcript says so.

**P0-4 · Intent port with golden-master parity.** `intent.py` → Go
(`line/internal/intent`), vectors cut from Manjuel's own `test_manjuel.py`
intent cases and from 100 transcripts' `named_tool/named_by` headers.
*Acceptance:* `atl gm run --stone H2` zero mismatches; the ALIASES table
and every skill's `**Says:**` phrases load from the environment's
`skills/`, not from Go constants.

**P0-5 · The Run page.** Objective box with route autocomplete; live seat
stream with thinking withheld (never shown, never returned — Manjuel
runtime.py); tool hops with results and `THIS TOOL FAILED` banners; the
budget bar; cancel; the delivery exactly as the engine's last seat produced
it plus the four `recompose` blocks; `needs_answer` rendered as a modal
that blocks the run until answered or timed out.
*Acceptance:* a run's rendered delivery is byte-equal to the transcript's
`## Delivery`; cancel within 2 s ends the Ollama stream; a refused run
shows the law named and no seat.

**P0-6 · Traces and waterfall from the record.** Every transcript in every
environment listed, filtered, opened; the waterfall from `StepResult`
fields (elapsed, hops, skill, drift, error, skipped, out-of-time); the
exact prompt per seat from `_prompts/`; a SHA-256 receipt on each
transcript computed by `atlas` (never by Go) and its Manjuel verdict.
*Acceptance:* the trace count equals `ls logs/*.md` per env; opening any
of the 740 existing Manjuel transcripts (read-only mount of
`Desktop\Research`, on the operator's yes) renders without error; hash
receipts reproduce under `atlas Manjuel verify`.

**P0-7 · The Record page, with the gate intact.** Sittings, toll (attended
toll = three answers in a form, then `render_toll` + `pay`), story, memory
pending → land/drop as explicit clicks with the entry text shown, git state
and `suggest_commit` text — displayed, never executed; hands ledger with
*Acceptance:* no route in THE LINE contains commit, push, approve, land,
merge, delete, promote, reject, ascend; a static test asserts it; landing a
memory writes exactly what Manjuel's `memory.land` writes (byte-compare on a
mirror).

**P0-8 · The Rack page and scheduler.** Installed/resident/foreign/sizes,
tiers, the seat-call queue with VRAM cost, warm/unload, per-model timeouts
as declared; pull behind `MANJUEL_RACK_PULL` + confirm; the plan refuses a
pipeline that cannot fit unless the operator overrides (recorded).
*Acceptance:* the queue serializes seat calls across two environments with
no interleaved output in either transcript; `vram.render` parity with
Manjuel's `/models` on 12 goldens.

**P0-9 · Alerts.** From engine events and `verify_chain`: seat over
timeout, turn ≥ 80 % of budget, gate refusal, claim-check hit, index
refused/failed, VRAM over budget, `FLIP`/`TAMPER`. Shown live, kept in the
record as `kind: alert` lines in the environment's `sessions.jsonl`.
*Acceptance:* each alert has a stroke that provokes it on a temp ground.

**P0-10 · `atlas-tui` becomes honest.** `curl` replaced with `net/http`;
the missing-binary test; then the same pages as the glass, full screen,
stdlib only.
*Acceptance:* `go test ./cmd/atlas-tui` covers every page against
`atlas-mcp --prove`'s temp ground; no external process is exec'd except
`atlas` through the seam.

**P0-11 · The webapp's own store is folded.** `webapp/db/db.go` (JSON
traces/evals/agents/messages) is retired; every page reads the record
through THE LINE. Discord/Slack/WhatsApp adapter stubs are removed until a
stone names them (RULE 4: nothing that needs someone else's server).
*Acceptance:* `webapp/` has no writer of its own; `grep -r "json.Marshal"
webapp/db` returns nothing because the package is gone.

**P0-12 · The schema tells the truth about what is optional (found
2026-09-09).** `endsWithOptional` (`internal/protocol/protocol.go:145`,
duplicated verbatim at `internal/httpserver/httpserver.go:275`) requires TWO
trailing `?`. Every one of the 62 tools declares ONE — `"project?"` 61
times, plus `voice?`, `version?`, `actor?` and the rest; none uses `??`. So
`required` is emitted carrying every argument, and the default-ground path
that §4.2 and the prover's own stroke both rely on is unreachable over the
wire. This is the exact refusal the comment above `tools/list` describes as
fixed — "a law the caller cannot read is not a law, it is a trap" — and both
doors carry it. `--prove` is structurally blind: `prove.go:127` unmarshals
`tools/list` into a struct carrying only `Name` and discards `inputSchema`,
and the one default-tenant stroke calls the Go function in-process.
*Acceptance:* one trailing `?` marks optional; a stroke reads `required` off
the emitted JSON and asserts no tool makes `project` required; a second
asserts `verify_chain.path` still is, so the fix cannot degenerate into
"everything is optional". H3's generated forms (§4.7) depend on this.

**P0-13 · RBAC cannot be skipped, and an assignment takes effect (found
2026-09-09).** Three faults, all live. (1) `tools.go:113` runs the
permission check only when the caller supplies an `actor`; omit it and no
check runs at all — and `actor` is not among most tools' declared `Args`, so
it never reaches the published schema and the identity is a self-asserted
string. (2) `tenant.go:274` returns allow-all whenever `Policy.Assign` is
empty, and `DefaultPolicy()` ships it empty. (3) `tenant_rbac_assign` writes
`rbac.json` to disk but mutates a copy — `Fn` takes `tenant.Tenant` by value
and the registry's tenant is loaded once in `Registry.Add` — so the running
door keeps enforcing the old policy until restart. Worst case is the common
one: a world in open mode, the operator assigns the first role to lock it
down, the tool answers `ASSIGNED`, and the door stays wide open.
*Acceptance:* with a policy assigned, a call naming no `actor` is refused;
`actor` is a declared argument on every tool that honours it; an assignment
is visible to the next call in the same process.

**P0-14 · The absence test actually tests absence (found 2026-09-09).**
`prove.go:135` matches whole tool NAMES against eight bare verbs (`approve`,
`commit`, `push`, …). No tool would ever be named `commit`, so the stroke
cannot fail; it has never tested anything. Meanwhile `SYSTEM_DESIGN.md` §2.3
adds **send** and **post** to the forbidden list and both are live:
`team_send` POSTs to Discord/Slack/WhatsApp and `mesh_post` writes signed
messages. P0-11 above calls those adapters "stubs … removed until a stone
names them" — they are not stubs.
*Acceptance:* one forbidden list, named in Appendix D, matched as a
substring of every tool name AND of every route in every route table. Until
the operator stones it, `team_send` is refused at the door by name: a
network send from the box contradicts RULE 4 and `SYSTEM_DESIGN.md` §3.7,
"the box drafts; the box does not send".

### P1 — should have (fast follows)

**P1-1 · Evals and datasets.** `parity.md` cases as datasets; the standup
as a suite; an eval run = an objective set × an environment; scores from
parity (`CLOSE 0.75 / FAR 0.55`), drift, and the standup's 10-point rubric;
results appended to `parity_history.jsonl`; **no LLM-as-judge unless the
operator seats one, and then as testimony**.

**P1-2 · Compare.** Two runs of one objective side by side (two envs, or
one env with a `/model` override); diff of deliveries, waterfalls, hops,
time; the "move up" decision with its measurement attached.

**P1-3 · Playground.** `@seat` addressing (one seat, not the shared
thread), a `/model <tag>` override marked "measurement, not configuration",
a method box (`**Method:**` semantics, spent after one run).

**P1-4 · Sessions and replay.** A sitting as a timeline of runs; replay =
re-run the same objectives in a fresh environment forked from the same
declarations, then Compare. (A transcript is already a complete replay
script: objective, feed, method, pipeline.)

**P1-5 · The classifier seat** for unrouted input (§4.4 layer 4).

**P1-6 · Engine port, stone by stone. — WITHDRAWN 2026-09-09 by ADR-001
(§11).** It read: *"`run_pipeline` → Go behind golden-master parity on
transcripts (headers, stage lines, `recompose` blocks), one seat builder at
a time, Manjuel's REPL as the oracle until each stroke is green; then Manjuel
retires by fold note (SPEC_COMMANDS rule 4)."* Kept here, folded not
deleted (LAW 1), because it was the plan of record for a day and the record
should show what was believed. The engine stays Python; the intent port
(P0-4) stands and is the only piece of it that survives.

**P0-15 · The engine supervisor (promoted by ADR-001, §11).** THE LINE owns
one long-lived engine process per open world: spawn, pipes, health, reap on
`closed`, and orphan reaping on its OWN restart — an orphaned `manjuel.py`
holds that world's sitting open, which is what RULE 9 forbids editing under
and what `tests/release.py` refuses a tag over. Plus SSE fan-out with a slow
viewer dropped rather than allowed to block the engine's pipe, and the
per-world ask lock of §4.6.
*Acceptance:* a stroke per line above on temp grounds — a killed supervisor
leaves no engine running and no sitting open; a viewer that stops reading is
dropped and the run completes; two worlds run two objectives with no
cross-talk and neither blocks the other. This package carries the same
stroke discipline as `manjuel/` because ADR-001 makes it load-bearing.

### P2 — future considerations (design for, don't build)

- **Authenticated gate for outside tenants** — one channel, per-tenant
  keys, RBAC already in THE LINE (`tenant_rbac_*`).
- **The mesh** — environments exchanging signed envelopes over B2's
  `mesh_*` tools; an environment's delivery as a mesh post.
- **Voice** — Manjuel's `voice.py` (whisper.cpp, SAPI) as a glass affordance;
  Windows-bound, degrades alone.
- **Cost accounting** — local, so "cost" is seconds, evictions and
  watt-hours; a per-run number once the rack scheduler measures it.
- **Skill marketplace** — `atl skill lint|list|install` over a folder of
  `SKILL.md`, already harvested in F1.

---

## 7. Market parity

### 7.1 The observability axis (Langfuse · LangSmith · AgentOps)

Reference: `docs/GUI_GAP_ANALYSIS.md` (Langfuse / LangSmith / AgentOps),
re-read against what the two records actually hold.

| capability | market | atlas today | Manjuel today | control center | stone |
|---|---|---|---|---|---|
| Per-agent trace view | yes | stub store | `logs/*.md` per run, prompts beside | Seats page → runs | P0-6 |
| Step waterfall | yes | no | `StepResult.elapsed/tool_calls/drift` | Waterfall page | P0-6 |
| Tool-call tracing | yes | no | hop loop, `THIS TOOL FAILED`, dedup | Run + Waterfall | P0-5/6 |
| Cost / latency | yes | no | elapsed per seat; VRAM plan | seconds + evictions; watts P2 | P0-8, P2 |
| Search / filter traces | yes | no | `sitting`, `when` skills | Traces filters + semantic search | P0-6 |
| Real-time monitoring | yes | health poll | boot report; watcher | Run stream + Rack queue + Alerts | P0-5/8/9 |
| Alerts | partial | no | none (found after the fact) | Alerts page, recorded | P0-9 |
| Export traces | yes | `db export` byte-identical | transcripts are files | `atlas db export`; Markdown is the format | done |
| Detail / click-in | yes | no | open the file | every page | P0 |
| Evals framework | yes | stub | parity.py, standup.py, drift.py | Evals page, no judge by default | P1-1 |
| Trajectory / step evals | yes | no | standup judges seats, stages, OUT OF TIME | standup as suite | P1-1 |
| Datasets from traces | yes | no | `parity.md` cases; transcripts are scripts | Datasets from Traces (select → case) | P1-1/4 |
| Experiment comparison | yes | no | `/model` override, `/parity` | Compare | P1-2 |
| Human annotation | yes | no | `remember`, the toll's three answers | toll + memory land = annotation, gated | P0-7 |
| Sessions / replay | AgentOps | no | `sessions.jsonl`, story, thread | Sessions + Replay | P1-4 |
| Playground / prompt | LangSmith | no | `@seat`, `/model`, `**Method:**` | Playground | P1-3 |
| Agent graph | yes | no | pipelines are linear; rack wakes on flags | pipeline + rack as a wake-graph per run | P1 (with Waterfall) |
| Multi-env / multi-tenant | partial | tenants in THE LINE | one ground, one writer | Environments | P0-2 |
| Routing by rules | no | no | `intent.py` (deterministic) | ROUTES.md + intent + classifier-as-testimony | P0-3/4, P1-5 |
| Cryptographic receipts | **no** | yes | law chain sealed (4 links) | every transcript, every env, every alert | P0-6 |
| Tamper-evident record | **no** | `FLIP`/`TAMPER` | append-only, `(re-tolled)` | verdict on every page | P0 |
| Structural non-approval | **no** | `can_approve:false` ×40 | RULE 6 / LAW 6 | ×(40 + 14 + N envs) | P0-7 |
| Law gate before any model | **no** | covenant | `lawgate.py`, four checks | per env, verified at fork | P0-2 |
| Claim / citation check | **no** | no | REFUSALS §7, §7b, §8, §10 | carried; the "harder half" stays Manjuel's open line | P1-6 |
| Local-only, zero deps | **no** | yes | one dep (`ollama`) | yes | — |

The last seven rows are the product. The first eighteen are the price of
admission.

### 7.2 The runtime axis (AgentOS · Letta)

*Added 2026-09-09 at his word. The table above was cut against three
observability products. The offerings he named are a different shape —
runtimes that host and serve agents — so this is a second table, not an edit
to the first. Facts from one read-only web reach, 2026-09-09.*

**AgentOS (Agno)** is a stateless FastAPI runtime plus a control-plane UI:
tracing, scheduling, human approval and JWT-based RBAC. The runtime is free
and open source and will serve agents into ChatGPT and Claude; the live
control plane is $150/month and a self-hosted control plane is an enterprise
conversation. **Letta** (formerly MemGPT) is the LLM-as-operating-system
thesis: tiered memory, self-editing memory blocks, virtual context
management for unbounded context, Apache-2.0 and self-hostable, with a
model-agnostic harness carrying skills and subagents.

| capability | AgentOS | Letta | this estate today | verdict |
|---|---|---|---|---|
| Serve agents to outside users over HTTP | yes — the headline | yes | **no, by position**: BUILDPATH's no-listening-socket; THE LINE is the only door and T7 binds it to the LAN | RULED OUT (§3) — and named here as the market gap it is |
| Control-plane UI | yes; $150/mo, self-hosted behind sales | yes | the glass — self-hosted only, no tier, no account | H3 |
| Per-agent traces | yes | yes | every run a transcript with its exact prompts, hash-receipted | P0-6 |
| Waterfall / step timing | yes | yes | `StepResult.elapsed/tool_calls/drift`; `flow_status` already renders one | P0-6, smaller than written |
| Human approval in the loop | yes, a feature you enable | partial | `can_approve:false` in every declaration, plus `needs_answer` on the wire | **ahead** — grammar, not a setting |
| RBAC | JWT-based | — | `tenant_rbac_*` exists and **fails open twice** | **defect**, P0-13 |
| Scheduling | yes | — | `town_beat` on the atlas side; an `.ics` export on Manjuel side | **gap, unstoned** — H5 |
| Sessions and replay | yes | yes | `sessions.jsonl`, the story, the thread; `flow_replay` built | P1-4, smaller than written |
| Memory the model edits itself | — | **yes, the thesis** | refused: a model may only propose; the operator's hand lands it | POSITION (LAW 5, RULE 6) |
| Unbounded context / paging | — | yes | the bounded story block, the thread, and the index with transcripts ageing out at 45 days | equivalent in substance, different shape |
| Subagents / multi-agent | yes | yes | 14 seats, 5 pipelines, racked seats woken by flags | done |
| Skills as portable artifacts | yes | yes | 37 markdown skills; `atl skill lint` harvested | **ahead** — a skill is a file, not code |
| Any model provider | yes | yes | Ollama on loopback, by law | RULED OUT (RULE 4) |
| Where the truth lives | your database | their database | **plain files, hash-chained; no database is the truth** | the product |
| Cryptographic receipts · tamper-evidence | no | no | yes, on every transcript and every Manjuel | the product |
| Price and vendor | runtime free, control plane $150/mo | OSS plus a cloud | $0, no vendor, no account | the product |

**What the two tables say together.** The price of admission is twenty-four
rows, and most of them are already paid — the code carries more than either
road admits. Three are real, named gaps: **scheduling**, which no stone
covers; **RBAC**, which is built and broken (P0-13); and **serving agents to
someone who is not the operator**, which is refused by position. That last
one is the single largest difference between this and AgentOS, and it is a
choice rather than a shortfall — it should be re-read as a choice when he
rules on outside users (H8). Everything below that line — receipts,
tamper-evidence, structural non-approval, a sealed law gate before any model
reads a word, the record as the only truth, $0 and no vendor — is what
neither AgentOS nor Letta has, and neither is likely to build: each needs a
database to be the truth and a tier to be the business.

---

## 8. Success metrics

**Leading (first two weeks after P0)**

- Terminals open on an ordinary day: **0** for a full sitting (open →
  runs → toll → close) — measured by the operator's word in DAYBOOK.
- Runs started from the glass vs the REPL: **≥ 90 %** glass by week two.
- Route hit rate: **≥ 80 %** of inputs land on a named rule, not default
  (from `routed_by` headers).
- Alert lead time: a court that will breach 600 s is flagged at **≥ 120 s**
  remaining in **every** case in the record's next ten standups.
- Parity: `atl gm run` **zero mismatches** for every ported stroke; the
  headless driver's transcripts **byte-equal** to REPL transcripts on the
  60-case smoke.

**Lagging (first quarter)**

- Faults found by reading transcripts after the fact (the 2026-09-08 kind):
  **0** — every one surfaces as an alert or a Run-page banner first.
- Standup live score: **10/10 twice running** in the glass, the same gate
  Manjuel's SPEC §7.2 sets.
- Environments in use: **≥ 3** forked and running (a door tier, a court
  tier, a coder tier) with measured, not reasoned, model choices.
- Manjuel retired by fold note with **zero** open golden-master mismatches;
  `Desktop\Research` read-only thereafter.
- A stranger runs it in an hour from `QUICKSTART.md` alone (Manjuel SPEC
  §7.2 goal 5, carried).

---

## 9. Open questions (the operator's)

**Ruled 2026-09-08** (his words, verbatim, in the order asked)

1. Git in `Archive\atlas` — *"my hand, get over it."* Closed. Archive is an
   artifact now; its `.git` is his.
2. The headless driver — *"im ok with that, build it now and get it out of
   the way."* Closed: one piece, `manjuel/serve.py`, on a mirror, restart
   required.
3. Where atlas lives — *"everything moved over to the research folder on
   the desktop, pulled out of the archive as needed. stale dir for atlas
   stays as is after the copy, it can be an artifact."* Closed. Each pull
   is a place he names (SITTING LAW 4); Research's `.gitattributes`
   governs terminators for what comes in.
4. The default environment — *"research origin, agent-workspace is the
   dir."*, then the same afternoon: *"put the environment into /worlds and
   give it the same provenance as the manjuel folder in there. read-only.
   not indexed for the ground, only used as source."* Closed: origin = the
   Research ground; environments = `worlds/<name>/`, manjuel's provenance
   (§4.2). The `agent_workspace/` reading stood for one hour and is folded
   here, not erased.

**Non-blocking**

6. CRLF or LF for the glass's writers (Manjuel rules CRLF everywhere; atlas
   docs are LF; fixtures must keep whatever they have).
7. Whether `rack_report` (a model reading rack facts) sits at the table in
   an environment — Manjuel TASKS records this as his call.
8. Cost accounting unit (seconds / evictions / watts).
9. Port for the glass: keep `:8091` and fold it into `:8090`'s embedded GUI,
   or the reverse. Ports never move at cutover (SPEC_COMMANDS rule 2).

---

## 10. Timeline and phasing

No dates — stones, each with an ACCEPTANCE row and a STATE_OF_BUILD
witness, each a gate he holds. Proposed as H-stones on THE ROAD.

| stone | name | what lands | gate |
|---|---|---|---|
| **H0** | the first pulls | `atlas` (Rust spine) and THE LINE pulled into Research at places he names; Research's `.gitattributes` covers them; `atlas-tui` off `curl`; `webapp/db` retired | prove green in Research; Archive untouched. **BLOCKED 2026-09-09 on one thing only: the places have not been named** (RULE 8 / SITTING LAW 4). Everything downstream waits on that sentence. |
| **H1** | the driver | Manjuel `--headless` — **in hand 2026-09-08** (`manjuel/serve.py`, mirror-proved, restart required) | 60/60 smoke byte-equal transcripts |
| **H2** | the line carries worlds | the per-world ask lock (§4.6) **first**, then P0-12/13/14, then `env_*`, `run_*`, `route_*`; ROUTES.md; intent port | `--prove` + `atl gm run --stone H2` zero mismatches; a `run_start` on one world does not block a tool on another |
| **H3** | the glass, P0 pages | Run, Traces, Waterfall, Seats, Rack, Record, Alerts, Law, Environments | a sitting start-to-finish with no terminal; standup 10/10 live from the glass |
| **H4** | the TUI | `atlas tui`, same pages | every page stroked |
| **H5** | evals, compare, playground, replay, **scheduling** | P1-1..4, plus the one unstoned market gap (§7.2): a due-work beat over `town_beat` and the tier cadences, and the `.ics` export | parity history grows only through the glass; a visit due and unscheduled raises an alert without anyone opening a page |
| ~~**H6**~~ | ~~the engine port~~ | **WITHDRAWN 2026-09-09 by ADR-001 (§11).** The engine stays Python. The row is kept, struck, not deleted (LAW 1). | — |
| **H7** | the glass is the front door | REDEFINED by ADR-001: not Manjuel's retirement. The terminal becomes optional — an ordinary day opens, runs, tolls and closes from the glass, and the REPL is the fallback, not the path | a full sitting with no terminal, twice running; the REPL still works and is still proved by the same suites |
| **H8** | the gate for tenants (P2) | auth channel, per-tenant keys | not before he rules on outside users |

Dependencies, as ADR-001 leaves them: H1 is in hand; H2 needs H0 and H1;
H3 needs H2; H7 needs H3. **H6 is gone, and with it the longest edge on the
graph** — the road is now H0 → H1 (done) → H2 → H3 → H7, with H4 and H5
hanging off H3 in parallel. Every stone lands inside `Desktop\Research`,
one piece at a time, at his word (RULE 10); the Archive copy is never
written.

---

## 11. ADR-001 — Manjuel is the permanent engine

```
status:   ACCEPTED
date:     2026-09-09
decider:  the operator
```

### Context

Two rulings collided. The ruling of record (§0, 2026-09-08) was *"atlas
absorbs manjuel.py's verbs; Python retires,"* carried as H6 (port
`run_pipeline` to Go) and H7 (retire Manjuel). The operator, 2026-09-09: *"use
Manjuel as the underpinning of the atlas system, the actual harnessing that
it runs"* — and, on accepting: *"I like the idea of keeping the chained core
underpinning, it seems to be the way 90% of the market is leaning, and good
for transparency."*

Under the first, Manjuel is scaffolding. Under the second, Manjuel is the engine
and atlas is the control plane above it. Everything else the operator
described — a glass to watch headless agents and keep command and control, a
polyglot MCP/Rust/Go/TS surface, the webapp built alongside — fits both. This
one line did not.

### Decision

**Manjuel is the permanent engine. atlas is the control plane. H6 is withdrawn;
H7 is redefined; Python does not retire.**

### Why

1. **The guards are the product, and a port is where they die quietly.**
   `SPEC.md` §1: *"Every guard in it is named after a failure that actually
   happened."* Porting re-earns each one in a language that has never seen
   those failures. Golden-master parity is the only defence and it can only
   prove paths the 740 transcripts happen to cover — but guards fire on the
   RARE path, which transcripts under-sample by construction. A ported guard
   that fails to fire does not crash; it lets a claim through. That is the
   exact failure class this estate exists to prevent.
2. **It buys no capability.** H6 was the largest single item on the road and
   would have ended where it started.
3. **The premise was already conceded.** `SYSTEM_DESIGN.md` §7: *"the Python
   engine is not the bottleneck today."* SITTING LAW 3 — move on a measured
   failure, never in anticipation — governs code as well as models.
4. **The strangler ruling does not reach here.** atlas `CHARTER.md` §2.3 was
   written for the *estate* Python, a codebase nobody was hardening. Manjuel is
   hardened weekly; strangling a moving target is the expensive case.
5. **No charter is broken** (the operator's correction, 2026-09-09): zero
   dependencies and one language are different axes. The no-dep law is about
   not importing a solved problem you should own; atlas is polyglot for the
   same reason it is a control plane — *it can speak all the languages.* That
   is `CHARTER.md` §2.1, best-fit-per-component, a sibling of the no-dep law
   and not in tension with it. A Python engine needs no charter amendment.
6. **The market leans this way.** AgentOS's runtime is FastAPI — Python — with
   its control plane in another stack; Letta is Python behind a server
   (§7.2). Neither rewrote its engine to match its control plane's language.
7. **Transparency.** 37 skills as markdown a person can read beats the same
   logic compiled into a binary.

### The frame, in the operator's words: "essentially a unix system"

| Unix | here |
|---|---|
| a filter: stdin → stdout, text protocol | `manjuel.py --headless` — four commands in, seventeen events out |
| a filter: argv → one object | `atlas` (Rust), exec'd through the seam |
| init / the shell | THE LINE — spawns, wires pipes, supervises, reaps |
| the filesystem; everything is a file | the record: plain files, append-only, hashed |
| separate mounts, one writer each | `worlds/<name>/` |
| small programs, one job each | the 37 markdown skills |
| a shell script | `pipelines.md`, the running order |
| the permission bit | `can_approve:false` — structural, not policy |
| the kernel refusing a syscall | the law gate, before any model reads a word |
| `/var/log`, greppable | the transcripts and their prompts |

This is not a metaphor; it is the design, and it settles H6 on its own: **in
a Unix system you do not rewrite `grep` in the shell's language to make it
part of the system.** The shell composes programs, it does not absorb them.
H6 proposed absorbing the engine into the shell — under this frame that is a
category error before it is an expense. It is also why the seam is already
right rather than provisional: JSON lines over a pipe is the most Unix thing
in either codebase.

### Consequences

**Easier.** H6 leaves the road and takes the longest dependency edge with it.
The guards stay proved where they were earned. The seam is finished rather
than rebuilt. Two skill surfaces, each in its best language, with a placement
rule (§4.8).

**Harder, and this is the real cost.** The supervisor becomes the single
point of failure for the whole estate, and it is the least-proved thing in
either codebase — zero strokes today. Option A's risk was silent guard
failures spread thin over 14,718 lines; this concentrates the risk in one Go
package that does not exist yet. A better trade, not a free one. Hence P0-15.
Also: two languages in the hot path, a fault possible on either side of the
pipe, and a per-world process plus model warm at open.

**To revisit.** If the engine is ever MEASURED as the bottleneck, or the
per-world process model proves unmanageable in practice, H6 returns — with a
number attached, as SITTING LAW 3 requires. Nothing here forecloses it; the
withdrawn text is kept at P1-6.

### What this amendment changed

§0 (the retirement line, superseded) · §3 (a new non-goal) · §4.6 (the
supervisor promoted) · §4.8 (new, the placement rule) · §6 (P0-15 added, P1-6
withdrawn and folded) · §10 (H6 struck, H7 redefined, the dependency graph
redrawn) · this section.

---
## 12. THE STACK — the CLI and the GUI over one engine

*Written 2026-09-09 at the operator's word: "this is the reconciliation of
the CLI and the GUI control plane don't forget how this stacks up. we are
working to bring the atlas system online as a control plane for Manjuel."*

### 12.1 The five layers

```
  FACES      the REPL (CLI)   ·   the glass :8091   ·   atlas-tui
             python manjuel.py      webapp, 10 pages      subcommand CLI
                   │                     │                   │
  ─────────────────┴─────────────────────┴───────────────────┴─────────
  THE LINE   atlas-mcp :8090 — JSON-RPC 2.0 + SSE — 62 tools
             tenant = world (wire field `project`)
                   │
  ─────────────────┼───────────────────────────────────────────────────
  THE ENGINE manjuel.py --headless --ground worlds\<w>   one per open world
             PROTOCOL 1: 5 commands in, 19 events out (6 terminal)
                   │
  ─────────────────┼───────────────────────────────────────────────────
  THE SPINE  atlas (Rust) — sha256 · canon · Manjuel verdicts · merkle
             exec'd with an argv array; never reimplemented in Go
                   │
  ─────────────────┼───────────────────────────────────────────────────
  THE RECORD worlds/<w>/ — plain files, append-only, hashed
```

Two seams, both the same shape and both already built: Go execs the Rust
spine and reads one JSON object (`SPEC_SEAM`, the rule of one computer);
THE LINE execs the engine and reads JSON lines on its pipes (`serve.py`).
**Neither seam is a socket.** The only listening socket in the estate is
atlas's, and that is the point of the layering: Manjuel's "no listening
socket" is Manjuel's position, and atlas is where the socket belongs.

### 12.2 The CLI and the GUI are peers, not predecessor and successor

This is the reconciliation, and the documents did not say it plainly before
today. The REPL is not a legacy path being replaced by the glass. They are
**two faces over one engine, one record and one law gate.** H7 says the
glass becomes the front door and the terminal becomes optional; optional is
not deprecated. `CONTRIBUTING.md` already promises the REPL proves under the
same suites, and ADR-001 keeps the engine they both drive.

What differs is only how each reaches the engine:

| | the REPL | the glass |
|---|---|---|
| reaches the engine by | being it — `input()` and `print()` in-process | THE LINE, which execs it and speaks JSON lines |
| the gate | he types the answer | `run_answer` carries it |
| what it is good for | one ground, full attention, no supervision to fail | many worlds, watching, comparing, a phone on the LAN |
| proved by | `smoke_cli.py`, 60 cases | `--prove` on temp grounds |

### 12.3 THE RULING THIS NEEDED: the sitting line is the lock

One writer per world; one engine process per world (§4.2). So **the REPL and
the glass cannot drive the same world at the same time.** Open the REPL on a
world and then open it in the glass, and two engines number the same ledger
— the fault `worlds/manjuel/AGENTS.md` has warned about since it was
inherited. Nothing in the record answered this until now.

**The answer costs no new mechanism, because the lock already exists.**
`sessions/sessions.jsonl`'s last line with no `ended` is precisely the signal
RULE 9 and SITTING LAW 5 already use to mean *hands off, someone is sitting*.
THE LINE reads that line and refuses that world BY NAME — the estate's own
idiom — and the glass shows who holds it and since when.

    env_open worlds\TBC
      -> refused: TBC has an open sitting (97, opened 09:41). One engine per
         world. Close it in the REPL, or open a different world.

*Acceptance:* a stroke opens a sitting by hand, then `env_open` on that world
is refused naming the sitting number; after a close it succeeds. The reverse
too: with the glass holding a world, the REPL says so at boot rather than
forking the ledger.

Later, if he wants both faces live on one world at once, the REPL becomes a
CLIENT of THE LINE rather than a process that boots its own engine. That is
a larger change, it is not needed to come online, and it is not on the road.

### 12.4 H0 — LANDED 2026-09-09

The operator: *"take what you need and bring it over"*, *"moved into the root
dir. go for it."* atlas lives at **`Desktop\Research\atlas`**, beside
`manjuel/` — the layer it actually occupies, and inside the repo so it is
versioned and reaches CI. `worlds/` was considered and rejected: `worlds/` is
gitignored, so the control plane would never have been versioned, and a
control plane nested inside the tree it controls inverts §12.1.

**What came (ESTATE LAW 3 — live organs imported):** the Rust workspace
(`core`, `store`, `apps`), `line/` (62 Go files — mcp, door, town, tui, vc),
`webapp/`, `specs/`, `docs/`, `agents/` (85 `.us`), `skills/`, `tools/`,
`atl/`, `tests/` (168 fixtures and goldens), the build scripts, and the
charter-and-road documents. **497 files, 4.5 MB** out of an artifact of
**562 MB**.

**What did not:** `target/` (456 MB of build cache), `bin/` and every `.exe`
(rebuildable), `.git` (his history stays with the artifact), `.venv`,
`node_modules`, `shdbg.obj`, the C++ `kernels/`, `faces/`, `ide/`, `sdk/` —
capability not required by the mission stays unloaded (LAW 7). Say the word
and any of it follows.

**And one thing deliberately excluded that had to come back.** `data/master.db`,
`SEAT_LOG.md` and `STATE_OF_BUILD.md` were left behind under "records are
referenced, state starts fresh" — and the spine's prover failed on exactly
those three (`enroll-dry: data/master.db absent`; `orient-pack: LOG=false
STATE=false`). They are not state; they are read at runtime to build the
orientation pack a seat is handed and to answer enrolment. They came, and the
prover went green. Recorded because the first judgment was wrong and the
prover is what caught it.

**Proved in Research, which is H0's own gate:**

| | result |
|---|---|
| `go vet ./...` (line) | clean |
| `go build` × 5 commands | all built |
| `cargo build --release` | built, 4.9s |
| `atlas --prove` (spine) | **PROVEN, full battery** |
| `atlas-mcp --prove` (THE LINE) | **125/125 PROVEN** |

Built with `CARGO_TARGET_DIR` pointed at scratch, so no 456 MB `target/`
touched the ground; `.gitignore` now carries `atlas/target/` and `*.exe` for
the first in-place build. **Archive was read and never written** (ESTATE LAW
2); it remains the artifact and the golden source.

**Where this document lives, and the copy it replaced.** Until 2026-09-10 the
governing copy sat at the GROUND'S root while a second copy — 644 lines,
pre-amendment, still carrying *"atlas absorbs manjuel.py's verbs; Python
retires"*, the ruling ADR-001 superseded — was deliberately left out of the
ground at this path, because a contradicting copy of the governing spec is a
trap for the next hand. The core and atlas became separate repositories that
day, and a spec for atlas held in the core's repository is the same trap by
another route. So the governing copy moved HERE, to the repository it governs,
and it is the only copy in the ground. The stale 644-line one remains where it
always was: in the artifact, and nowhere else. Likewise `atlas/CLAUDE.md`:
a second CLAUDE.md inside the ground would be read as the standing rules by a
hand and as a ground marker by `ground.Detect`.

### 12.5 What "online" now requires, in order

| # | piece | state |
|---|---|---|
| 1 | ~~the place~~ | **DONE — H0, above** |
| 2 | the ask lock becomes per-world (§4.6) | precondition of anything multi-world |
| 3 | P0-12 schema · P0-13 RBAC · P0-14 absence test | three live faults, found 2026-09-09 |
| 4 | `env_*` / `run_*` — `line/internal/engine`, one Go package over `serve.py`'s wire (§4.6) | **DONE 2026-09-09.** `env_open` · `env_close` · `env_list` · `run_start` · `run_answer` · `run_cancel`, 68 tools on the surface, `--prove` 125/125. A turn runs through the council with the law gate stamped and the transcript written. `route_*` is not built. |
| 5 | the sitting-line refusal (§12.3) | **DONE 2026-09-09**, and proved live: `env_open research` is refused by name -- *"research has an open sitting (99, opened 2026-09-09T06:36:55)"* -- while `env_list` reports it *sat in elsewhere*. |
| 6 | the Run page — the glass has ten pages and none watches a run | prototyped |

Everything beneath that list already works and is proved: the wire (a commit
and a push driven through the headless door, 2026-09-09), `--ground`, the
spine, the 62 tools, the webapp shell, and an SSE fan-out in `webapp/handlers/
ws.go` that already drops slow clients — the backpressure discipline §4.6
asks for, written before it was asked for.

### 12.6 Trade-offs this layering accepts

| decision | over | why | what it costs |
|---|---|---|---|
| two faces, one engine | one face | the REPL is proved, offline, and needs no supervisor; the glass is what he watches | two clients to keep honest against one wire |
| exec + pipes between layers | a socket in the engine | keeps Manjuel's position and atlas's rule of one computer at once | THE LINE must supervise processes (P0-15) |
| one engine per world | one engine, many worlds | one writer per record, by construction rather than by discipline | a process and a model warm per open world |
| the ledger line as the lock | a lock file, a mutex, a daemon | it already exists and already means this | a crashed REPL leaves a world locked until the line is closed |
| atlas at the root | atlas under worlds/ | versioned, in CI, at its own layer | the ground grows by 4.5 MB and a second language |

### 12.7 What to revisit as it grows

- **The REPL as a client of THE LINE** — only if he wants both faces on one
  world at once. Until then the lock is enough.
- **A crashed REPL holding a world.** The ledger line is the lock, so an
  needs the same escape hatch before this bites.
- **Two provers, two languages, one gate.** `tests/release.py` refuses a
  Manjuel tag today. Nothing refuses an atlas tag. When atlas ships from
  Research, the release gate should read both batteries.
- **`atlas/docs/` and `Research/` will drift**, as `SPEC_CONTROL_CENTER.md`
  already did. One governing copy, cross-referenced, is the rule (§0).

---
## Appendix A — verb map, Manjuel → atlas (names keep their verbs)

| Manjuel (`/` palette) | atlas verb (THE LINE tool · glass page) | note |
|---|---|---|
| `Objective:` prompt | `run_start` · Run | routed first (§4.4) |
| `/chat`, `/say`, `/listen` | P2 voice | Windows-bound |
| `/new`, `/resume`, `/paste` | `run_start{feed}`, thread controls · Run | `injection_markers` gate carried |
| `/table <q>` | `run_start{pipeline:court, review_only}` · Run | review-only enforced by the line, not the page |
| `@<seat> <q>` | `seat_ask` · Playground | not on the shared thread |
| `/last` | Run (delivery) | |
| `/remember`, `/memory` | `memory_pending`, `memory_land`, `memory_drop` · Record | land = operator's click |
| `/git` | `git_state` · Record | suggests, never commits |
| `/toll` | `toll_render`, `toll_pay{proved,thin,owed}` · Record | attended = a form |
| `/sittings`, `/brief` | `read_handoffs` (exists), `sitting_list`, `brief` · Record | |
| `/status` | `boot_report` · Environments | already a `list[str]` |
| `/index`, `/find` | `index_ground`, `semantic_search` · Traces search | `_INDEX_BUSY` honoured |
| `/parity` | `eval_run` · Evals | confirm before spend |
| `/models`, `/model`, `/warm`, `/rack` | `rack_list` (exists), `rack_plan`, `rack_override`, `rack_warm`, `rack_sync` · Rack | override = measurement |
| `/agents`, `/skills`, `/pipeline(s)`, `/use` | `muster` (exists), `skills_list`, `pipeline_list`, `run_start{pipeline}` · Seats | |
| `/reload` | `env_reload` · Environments | turn boundary only |
| `/help`, `commands.md` | `route_table`, `route_dry_run` · Run autocomplete | commands become routes |
| `/exit` | `env_close` | toll on close if runs happened |

## Appendix B — the record, mapped to the spine

| Manjuel file | shape | atlas treatment |
|---|---|---|
| `sessions/sessions.jsonl` | append-only JSON lines (open/close per sitting) | `atlas db import` as a Manjuel; verdicts; `export` byte-identical |
| `SEAT_LOG.md` | append-only toll, `(re-tolled)` markers | imported as a Manjuel (already a fixture: `agents_seatlog`) |
| `logs/*.md` + `_prompts/*.md` | one transcript + one prompt file per run, CRLF | hashed by `atlas`; receipt stored beside the sitting line |
| `memory.md`, `memory/pending.jsonl` | landed / staged | landed lines imported; pending shown, never auto-landed |
| `law/chain.jsonl` | sealed law chain (4 links; 5–6 drafted) | verified by `atlas chain verify` **and** by chain's `law.py` — both must agree (differential stroke) |
| `us/*.us` | capability manifest (14 seats + manjuel) | enrolled into `master.db` beside atlas's 40; `can_approve` absent/false asserted |
| `rack.md`, `parity_history.jsonl` | derived / append-only | read; `rack.md` regenerated only by `rack_sync` |
| `index/vectors.db` | SQLite, WAL, schema 2 | per environment; never shared |

## Appendix C — laws carried across the seam, by name

RULE 4 local only · RULE 6 / LAW 6 the gate is final · RULE 7 / LAW 9 keys
silent · LAW 1 fold never delete · LAW 5 testimony is never fact · LAW 8
one write-path, jails · SITTING LAW 1 read in full · SITTING LAW 2 client
material sealed · SITTING LAW 3 start small · SITTING LAW 4 no folder
unasked · SITTING LAW 5 nothing edited while a sitting is open · SITTING
rulings 1–4 and §4 standing laws · atlas working laws 1–9 · SPEC_SEAM ·
SPEC_COMMANDS rules 1–4.

*Sources read for this draft: atlas `CLAUDE.md`, `AGENTS.md`, `CHARTER.md`,
`THE_ROAD.md`, `SEAT_LOG.md` tail, `STATE_OF_BUILD.md` tail, `DELIVERABLE.md`,
`CHANGELOG.md`, `HANDOFF.md`, `docs/GUI_GAP_ANALYSIS.md`,
`docs/PLAN_GUI_IDE.md`, `docs/CLI_REFERENCE.md`, `specs/SPEC_COMMANDS.md`,
`line/cmd/atlas-tui/main.go`, `webapp/db/db.go`; Manjuel `manjuel.py`,
`CLAUDE.md`, `law/*`, `SPEC.md`, `DAYBOOK.md` (last entry), `HANDOFF.md`
(newest block), `CHANGELOG.md` (Unreleased), `TASKS.md` (open lines),
`README.md`, `QUICKSTART.md`, `rack.md`, `agents.md`, `memory.md`,
`pipelines.md`, `DESIGN.md`, `REFUSALS.md`, `BUILDPATH.md`, `parity.md`,
`index_roots.txt`, `pyproject.toml`, and every module under `manjuel/`.
Drafted under hand line `H20260908-133137` (nothing in Research written);
amended and placed at the root, with `manjuel/serve.py`, under
`H20260908-142045`.*

---

## Appendix D — the four plans, reconciled line by line (2026-09-09)

Every place the four documents contradicted each other, and what now
governs. Nothing is erased; the superseded reading is named so the record
shows what was believed and when (LAW 1).

| # | the disagreement | what governs now |
|---|---|---|
| D1 | **Tool count.** This file (§0, §4.1) and `SYSTEM_DESIGN.md` §2.3 said THE LINE carries 25 tools. | **62**, read off `tools.go`. Both roads are stale; §6 is scoped against the code. |
| D2 | **Tool families.** `SYSTEM_DESIGN.md` §2.3 says "three families" then tables seven; this file's P0-2 names eleven tools and omits `env_reload`, which Appendix A carries. | The three families H2 must build are `env_*`, `run_*`, `route_*`; `env_reload` belongs to `env_*`. The record, rack, drop and world-skill rows of `SYSTEM_DESIGN.md` §2.3 are **already built** (62 tools) and are not H2 work. |
| D3 | **The word for a ground.** *environment* (this file) · *world* (`SYSTEM_DESIGN.md`) · `project` (the wire). | Prose: **world**. Wire field: **`project`**, unchanged. Glass page: **Environments**. (§4.2) |
| D4 | **The forbidden verbs.** This file's P0-7: commit, push, approve, **land**, merge, delete, promote, reject, ascend. `SYSTEM_DESIGN.md` §2.3: the same minus `land`, plus **send** and **post**. | **One list, here:** approve · ascend · commit · delete · merge · post · promote · push · reject · send. `land` is NOT forbidden — `memory_land` is a gated tool, and the gate is `run_answer`, not absence. P0-14 tests this list as a substring match. |
| D5 | **Where the glass's truth lives.** This file P0-11 retires `webapp/db`; `ATLAS_PRODUCT_PLAN.md` builds new webapp handlers on top of it. | P0-11 stands. Every page reads the record through THE LINE. |
| D6 | **The LLM bridge.** `ATLAS_PRODUCT_PLAN.md` Phase 3 (proxy to OpenAI/Anthropic, two SDKs, cloud cost table). | **Refused** (§3). RULE 4, both dependency laws, `SYSTEM_DESIGN.md` §1.2. |
| D7 | **Public deployment.** `ATLAS_PRODUCT_PLAN.md` Phase 5 (Let's Encrypt, OAuth/SSO, Docker/K8s). | **Refused** (§3). The gate is T7: LAN interface, one operator secret, self-signed TLS. |
| D8 | **Config grammar.** `atlas.yaml`. | **Refused** (§3). Markdown declarations only. |
| D9 | **"We don't do X" vs. X is built.** `ATLAS_PRODUCT_PLAN.md` says no playground, no workflow builder, no model hosting; `prompt_*`, `flow_*` and `rack_pull` exist. | The built tools stand and are folded into the surface. A plan does not refuse what the code carries. |
| D10 | **The surface work.** `ATLAS_PRODUCT_PLAN.md` Phase 2 (plain-English labels, modal forms, empty states, human durations, Technical Mode, mobile). | **Harvested whole** into §4.7 as H3 acceptance. It is the only part of that plan compatible with both charters, and it is the part that decides whether the thing is usable. |
| D11 | **Where environments live.** `manjuel/serve.py`'s docstring still says "grounds under `agent_workspace/`". | Stale by one afternoon: the ruling of 2026-09-08 moved them to `worlds/<name>/` (§4.2, §9 ruling 4). A doc line to fix when `serve.py` is next touched; no code depends on it. |
| D12 | **Where atlas lives.** atlas `CHARTER.md` §1 and §3 name `Desktop\Archive\atlas` as the project's ground and its wall. | His ruling of 2026-09-09 stands: **the finished product lands in `Desktop\Research`**; Archive stays the artifact and golden source, never written. Moving it is a charter amendment on the atlas side, and it is his to make — named here so the move does not happen silently against atlas's own §3. |

**What is NOT in dispute, and is the reason this reconciles at all.** Both
systems already ruled the same migration shape, independently: atlas
`CHARTER.md` §2 ruling 3 — *"Strangler migration. Python estate keeps
running; golden-master byte-parity required before any per-service cutover
through the same ports/commands"* — and this file's H6/H7. Manjuel keeps
running and answering; atlas absorbs it stone by stone behind golden-master
parity; Manjuel retires by fold note with its verbs kept. Nothing in this
amendment changes that, and nothing needs to.
