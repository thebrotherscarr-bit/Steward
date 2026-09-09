# THE CATALOG — Atlas Reconciliation Dictionary

*Every module of the estate and second brain grounds mapped to its base
language, the artifact to be written, and its disposition. Folded from full
scans of both grounds, 2026-08-24. Append-only: new modules found later get
appended rows; existing rows are never rewritten.*

**Source grounds:** `Archive\estate` (~2,300 code files across Steward 1.0,
Neiro, Manjuel ×3 gens, CARR, forge, builder, Agent Skills, Agents) ·
`Archive\secondbrain` (6 repos: SecondBrain-collab, superagent, skills-main,
agentrun-cli, open-genspark, clawverse).

**Disposition codes:**
`PORT` rewrite natively · `ADAPT` port reshaped · `WRAP` keep running, bridge
to it · `KEEP` strangler (Python until its cutover stone) · `HARVEST` adopt
pattern only · `FOLD` record/history, never ported · `NEW` written fresh
(no direct source module).

---

## 0. Cross-cutting seams (written once, used everywhere)

| Seam | Artifact | Contract |
|---|---|---|
| Go ↔ Rust | `specs\SPEC_SEAM.md` — Go services invoke Rust provers as subprocess CLIs, JSON on stdout | every hash/canon/sign operation computed in exactly one place |
| Python ↔ atlas | `@atl/gm` golden-master harness: runs Python original + atlas binary on same input, diffs hashes byte-for-byte | strangler proof instrument |
| C++ ↔ rest | kernels are CLI filters: SQLite/JSONL in → JSON out | no kernel ever holds network sockets |
| Trust | forbidden verbs absent-by-construction in every server (no approve/ascend/merge/commit/push/delete/reject/promote routes exist) | gatehouse + guardscan ports enforce |

---

## §1 RUST — `atlas-core` + `atlas-store` (provenance, identity, storage)

| # | Source module (lines) | New artifact | Disp. | Notes |
|---|---|---|---|---|
| R1 | `Neiro\lib\us_canon.py` (327) | `core/src/canon.rs` | PORT | BODY_V 1/2/3; JCS UTF-16-be key order; ±2^53−1 ints; vectors from its prove() |
| R2 | `Neiro\lib\us_chain.py` (609) | `core/src/chain.rs` | PORT | entry shape {ts,kind,n,payload,prev,actor,body_v,hash}; verdicts EMPTY/INTACT/FLIP/TAMPER; wraps-every-40 Merkle; consistency proofs |
| R3 | `Neiro\lib\prove_parity.py` (287) | `core/src/forms.rs` | PORT | all 13 legacy FORMS incl. board escaped-ASCII V1 and {prev,hash,body} envelope — recognition by trial, form stamped going forward |
| R4 | `Neiro\lib\us_read.py` (434) | `core/src/us.rs` | PORT | .us prose+fenced-JSON grammar; can_approve:false refusal-not-default; round-trip render |
| R5 | `forge\links\bip340.py` (175) + `jesster.py` (519) | `core/src/schnorr.rs` + `keys.rs` | PORT | BIP-340 sign/verify; five-key derivation from two halves never co-stored |
| R6 | `Steward 1.0\link.py` (12k) + `neiro\custody.py` (526) | `cmd/link` | ADAPT | character-chain pen + chain-of-custody signatures on one Rust pen |
| R7 | `manjuel.py` §1.5 Fold (~140) + `5.0\fold.py` (119) | `core/src/fold.rs` | PORT | secp256k1 constant-size relaxed-R1CS accumulator, domain tags preserved |
| R8 | `neiro\merkle.py` (224) + `5.0\memory.py` (111) | `core/src/merkle_dag.rs` | PORT | git-style body DAG, tamper pinpointed to file |
| R9 | foundation four docs + covenant checks everywhere | `core/src/covenant.rs` | NEW | sha256-over-sorted-docs → `65118a147dd49ed9`; precondition of every identity op |
| R10 | `builder\engine\prove.py` + blank-scanning | `core/src/blanks.rs` | PORT | no-placeholder proof for scaffolds |
| R11 | `Agent Skills\board.py` `_mark/_last_hash` ledger half (451) | `store/src/import_board.rs` | ADAPT | divergent V1 escaped-ASCII form read; receipts.json + ledger.jsonl imported |
| R12 | `forge\gateway\gateway.py` blake2b-32 event hashes (84) | `store/src/import_gateway.rs` | ADAPT | sharded users\<id>\ledger.sqlite → consolidated gateway.db (user_id column; shard layout folded) |
| R13 | all 36 live JSONL chains + workorders.db + mail_cache.sqlite3 + Seat_log\ledger.jsonl | `store/` migrations + `atlas db import/verify/export` | NEW | export regenerates byte-identical JSONL (golden-master asserted) |
| R14 | `skills\ark.py` (147) + `scripts\checkpoint.py` (169) | `cmd/ark`, `cmd/deposit` | PORT | backup payloads, token-ledger deposits |
| R15 | `vault.py` (345) + platform `auth.py` crypto cores (157) | `core/src/vault.rs` | PORT | pbkdf2 params verbatim (200k/600k); HMAC session mint moved to Go at cutover |

## §2 GO — services, scheduling, gating, connectivity

| # | Source (lines) | New artifact | Disp. | Notes |
|---|---|---|---|---|
| G1 | `seat_mcp.py` (22k) + `us_mcp.py` (656) | `cmd/atlas-mcp` | PORT | one stdio MCP server, --home drives any module; 10-tool parity; forbidden tools absent |
| G2 | `door.py` (:8080) | `cmd/atlas-door` | PORT | search box / answer+receipt / badge rewalks roster+audit+inspections+ledger via Rust verify |
| G3 | `town.py` + `trade_tasks.py` + river/clock/chancery organs | `cmd/atlas-town` | PORT | beat/flow (SystemRandom jitter), trade tasks REVIEW-gated, static no-approve self-check kept as test |
| G4 | `steward\bob.py` (328) | `pkg/queue` in atlas-town | PORT | durable claims collision-safe, refusal escalates to morning review |
| G5 | commons `board.py` (919) + Forge taskmaster board.py kit/mail halves (451) | `cmd/atlas-board` | ADAPT | three offices, one ethics, two modes, separate chains (per 08-15 ruling) |
| G6 | `gatehouse.py` (836) + `guardscan.py` (340) + `fetch.py` (97) | `pkg/gate`, `pkg/guardscan`, `pkg/guardfetch` | PORT | 5 risk tiers → chained verdict book; arg scanning; private-IP-refusing egress; linked into every server |
| G7 | `watch.py` sentinel + `radar.py` (229) | `cmd/atlas-watch` | PORT | fingerprint/covenant-drift loops, blackboard snapshots, SSE feed |
| G8 | `aurora\server.py` (:7788, 18 endpoints) | `cmd/atlas-glass` | KEEP→G-stone | strangler: Python serves until cutover; binary serves identical routes + her untouched console |
| G9 | `forge_server.py` (:7375, HMAC token) | `cmd/atlas-forge` | PORT | shape/run/remold/smooth/stations; /ascend stays 403-by-name |
| G10 | `gateway.py` + `gateway.js` twins | `cmd/atlas-gateway` | ADAPT | one broker absorbs both; intent→script dispatch |
| G11 | `wall.py` (724) | `cmd/atlas-wall` | PORT | Streamable-HTTP MCP, loopback + bearer, UI-facing |
| G12 | `harvest.py` OAI-PMH daemon (56) | `cmd/atlas-harvest` | PORT | resumable, 503-polite |
| G13 | CARR kernel (message/bus/router/scheduler/service, 467) | `pkg/kernel` | PORT | Message protocol verbatim; asyncio→goroutines; two-phase boot |
| G14 | CARR civic core (town 565, citizen, quest, tribunal, ladder) | `pkg/carr` | PORT | Citizen→Steward→Nerio→Operator ladder; charter enforced |
| G15 | CARR offices (jesster 148 / coder 78 / steward 62 / archive 102 / nerio 66 / harness 120 / sandbox 40 / shape 259) | `pkg/carr/offices` | PORT | planner/generator/evaluator/arbiter composition roots |
| G16 | CARR frontends.web (:8760 + WS push, 573) | `cmd/atlas-townweb` | PORT | zero-dep IDE served; bus-tap WebSocket |
| G17 | CARR spine (188, gated GitHub egress) | `cmd/atlas-spine` | PORT | world.egress gate honored, witnessed |
| G18 | platform runner (307) / scheduler (120) / cron (171) / prompt (101) / mcp_client (284) | `pkg/runner`, `pkg/cron`, `pkg/mcpclient` | PORT | bounded loop, sub-agents one level deep; 5-field cron stdlib port |
| G19 | platform api\ (19 handlers ≈3.3k) + auth sessions | `cmd/atlas-platform` | PORT (G-stone) | route-table pattern kept; sessions via R15 |
| G20 | platform llm connectors + `remote.py` (199) + `scale.py` discovery (326) | `pkg/llm` | PORT | Ollama :11434 first; remote racks same testimony law |
| G21 | victor Discord stack (1,586) | `cmd/atlas-victor` | PORT | gateway_ws pure-socket approach, no SDK |
| G22 | `panel.py` (406) | `cmd/atlas-panel` | PORT | load arithmetic / transfer switching |
| G23 | `puller.py` (210) extraction | `pkg/extract` | ADAPT | zip+xml natives replace Python stdlib tricks |
| G24 | `manjuel_us.py` serve-half (540) | `cmd/atlas-mirror` | ADAPT | read-only public mirror; genesis/append stay operator-hand (R6 signs) |
| G25 | weigh pipeline (`weigh.py`, scale ask-pipeline, rack_router settle/judge) | `pkg/weigh` | ADAPT | settling, two-register sense floor, tier bounds ride HTTP client config; embedding scoring delegated to K1 |

## §3 C++ — kernels (numerics only, socket-free)

| # | Source (lines) | New artifact | Disp. | Notes |
|---|---|---|---|---|
| K1 | manjuel grown models (~290) + 5.0 models.py (260) | `kernels/libppmi` | PORT | tokenizer/stemmer/PPMI embedder/trigram; integer counts bit-exact, float tolerance specced |
| K2 | `digest.py` (1,119) + `Jesster\library.py` (277) | `kernels/libdigest` | PORT | streamed meal-folding of GB catalogs; lays links via R6 |
| K3 | `predictor.py` (2,201) | `kernels/libpredictor` | PORT | 64-dim expectation space; benchmark target ≥10× Python |
| K4 | lexicon nearness + etymon scoring halves | `kernels/libsense` | ADAPT | morpheme tables move to JSON data; scoring native |
| K5 | steward library.py fold-at-scale workers (277) | `kernels/foldall` | ADAPT | parallel N-reader batch mode |
| K6 | bench timing stations + mathwright speed contests | `kernels/bench` | HARVEST | proving target for faster-algorithm claims |

## §4 TYPESCRIPT — faces, tooling, reconciliation instruments

| # | Source | New artifact | Disp. | Notes |
|---|---|---|---|---|
| T1 | console.html + sprites.js | `faces/console-v2/` | ADAPT | additive modules behind flags; STOP law: no second face |
| T2 | Studio hub/index.html + ide.html + Codex dashboards | `faces/studio/` | ADAPT | PIN-gate hub, IDE panels; consumes G16 |
| T3 | builder engine (space 61 / ask 110 / fit 302 / scaffold 98) | `@atl/builder` | PORT | interactive enroll/interview; writes .us decls + templates |
| T4 | golden-master needs | `@atl/gm` | NEW | strangler differ: Python vs atlas, hash-level |
| T5 | 23 opencode agent defs + skills.paths | `@atl/wire` | ADAPT | reconciles .opencode\opencode.json + 3× .mcp.json targets |
| T6 | skills-main validator (validate-skills.mjs) | `@atl/skill lint` | HARVEST | SKILL.md spec enforced on atlas skills |
| T7 | billboard worker.js (125) | keep as deployed worker | KEEP | edge mirror, no authority; optional TS hardening only |

## §5 JSON — declarations, contracts, packs

| # | Content | Artifact | Disp. |
|---|---|---|---|
| J1 | .us declarations: Agents.us, Neiro.us + ~30 agent decls folded from observed behavior | `agents\*.us` | NEW |
| J2 | kit.json, SKILL.md frontmatter, catalog fingerprints | skills.db seed + shelf JSON | ADAPT |
| J3 | opencode.json, .mcp.json ×3 | repointed at cutover stones | ADAPT |
| J4 | superagent Guard/Redact/Scan prompt templates | `packs/guard/*.json` | HARVEST |
| J5 | SecondBrain Memory API v1 contract | `packs/memory_api.json` | HARVEST |
| J6 | agentrun-style declarative deploy manifests | `packs/deploy.schema.json` | HARVEST |
| J7 | golden-master fixture sets | `tests/fixtures/` | NEW |
| J8 | morpheme/sense rule tables (from K4) | `packs/etymon.json` | ADAPT |

## §6 SQLITE — state topology (one DB per concern)

| DB | Absorbs | Notes |
|---|---|---|
| master.db | platform db.py P1–P6 (30 tables), THE_CATALOG dispositions, agent registry | append-only event tables; UPDATE/DELETE forbidden by store API + lint |
| ledger.db | verified imports of all 36 chains | derived index; JSONL stays canonical (state = fold(record)) |
| trade.db | workorders.db + property/inspection/report JSONLs | owner-report walks all three chains |
| board.db | board ledgers + mail_cache.sqlite3 + inbox/outbox | mission mail rebuilt here |
| memory.db | CARR 8-tier memory_service + SecondBrain split-topology pattern | working/episodic/knowledge + citation envelopes |
| skills.db | catalog fingerprints, kit, rack installs | feeds @atl skill lint |
| gateway.db | sharded users\<id>\ledger.sqlite (R12) | consolidation fold recorded |

## §7 KEEP / FOLD (no port)

| Item | Disposition |
|---|---|
| Sealed heart manjuel.py 3.2.0 + kernel | **KEEP/SEALED — never edited, reached ask-only**; new engines call through the door |
| foundation\ , Doctrine\ (56), SEAT_LOG/THE_ROAD/WEIGH_RUNS | FOLD — the record itself |
| Attics, Manjuel-1, frozen neiro\steward mirror, old generations | FOLD |
| clawverse game, Aurora game\ (:8085), open-genspark app | FOLD / reference only |
| Python estate processes during strangler (run.py, console.py, board.bat …) | KEEP until each G-stone cutover, then retired via fold note |

---

## Totals

15 Rust · 25 Go · 6 C++ · 7 TypeScript · 8 JSON · 7 SQLite artifacts reconcile
~230 source modules. Every PORT row carries its prove stroke; acceptance rows
live in `ACCEPTANCE.md`. Machine-readable copy: `data\master.db`
(table `catalog`, seeded by `tools\seed_catalog.py`).

---

## ERRATA — 2026-08-25

*Append-only erratum sheet: rows above are never rewritten; corrections land
here and in the seeder constants, per fold law.*

- **R9 — corrected against SPEC_COVENANT v2.** The R9 row's note
  ("sha256-over-sorted-docs → `65118a147dd49ed9`") predates the two-epoch
  amendment of 2026-08-24 and is wrong on construction and target:
  derivation is **construction A over the declared doc order** (sha256 each
  doc → concat hex digests in declared order → sha256 of the concat);
  sorted-directory constructions are refuted by the frozen spec.
  **House** is the default identity-of-record: five docs, covenant
  `1512741580b7239b80c53e2456b46aa9ec43586788d569da0895718dccf15bbb`,
  mark `1512741580b7239b`, anchor `core\Archive\weights\covenant.json`.
  **Elder** (`65118a…9dd9`, four docs) is read-only legacy, verified only
  behind an explicit `--epoch elder`; nothing new stamps it. Acceptance
  coverage: A1-07a/b.
- **G2 — source_lines column held bytes, not lines.** Row recorded 19,133
  for `estate\Steward 1.0\door.py`; measured 2026-08-25: **453 lines**
  (19,133 bytes). Seeder constant trued this sitting.
