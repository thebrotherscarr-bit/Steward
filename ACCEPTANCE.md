# ACCEPTANCE — the testable sheet

*Every stone exits through its proven mode. Rows are added as stones open;
a stone is DONE only when every row passes and STATE_OF_BUILD carries its
witness. All proves run hermetic (CHARTER §6).*

Legend: **GOAL** what the stone is for · **PROVEN MODE** exact commands ·
**REVIEW GATE** what the operator sees before the next stone opens.

---

## P0 — Groundwork

| ID | Criterion | Command | Expected |
|---|---|---|---|
| P0-01 | Charter + rulings recorded | read CHARTER.md | 4 founding rulings + wall-widening present |
| P0-02 | Catalog covers both grounds | `python tools\seed_catalog.py --verify` | row count ≥ 68; zero dispositions outside the six codes |
| P0-03 | Seed idempotent | re-run seed_catalog.py | no duplicate rows; journal_sync schema present |
| P0-04 | Specs frozen | specs\ file count + names | CHAINS, CANON, US, SEAM, SQLITE(+sync), MCP.json, COMMANDS *(amended 2026-08-25: SPEC_COVENANT v2 landed post-P0 — expectation is now eight files)* |
| P0-05 | Venv discipline | `tools\make_venv.ps1` | .venv created from pinned requirements |
| P0-06 | No code yet, no git | tree check | only docs/specs/tools/data/tests dirs *(amended 2026-08-25: `.venv` expected since sitting 1 part 2; still no code, no git)* |
| P0-07 | Versioning live | `Get-Content VERSION`; spot-check | `0.1.0+p0`; every future binary answers `--version` (semver+stone) |

**Review gate:** operator reads THE_CATALOG + specs; amends dispositions.

## A1 — Spine (Rust core + store)

| ID | Criterion | Command | Expected |
|---|---|---|---|
| A1-01 | Canon vectors byte-parity | `cargo test -p atlas-core canon` | all green incl. UTF-16 ordering + refusals |
| A1-02 | Live chains recognized | `atlas chain verify --roots estate` | every known chain: form named, verdict matches Python's own prover |
| A1-03 | FLIP vs TAMPER distinguished | injected-tamper prove | correct verdicts on temp copies |
| A1-04 | Export round-trip | `atlas db export <chain>` ×3 samples | byte-identical JSONL |
| A1-05 | Golden masters cut BEFORE forms asserted | fixtures dir | vectors captured from live chains first (SEAT_LOG lesson) |
| A1-06 | Journal sync law | store prove: record-first ordering, replay-on-open, refuse-on-break | strokes green; WAL=wal, synchronous=FULL observed |
| ~~A1-07~~ | *folded 2026-08-25 → A1-07a/b per SPEC_COVENANT v2 (two epochs)* | — | original text preserved in Amendments below |
| A1-07a | Covenant precondition — HOUSE (default target) | `atlas covenant check --genesis <house-foundation-dir> --anchor <weights\covenant.json>` | construction-A reproduction of `151274…5bbb` over his live foundation copies; mark = covenant[:16]; intruder file moves nothing; one flipped byte changes the covenant and names that doc |
| A1-07b | Covenant precondition — ELDER (explicit `--epoch elder`) | `atlas covenant check --epoch elder --genesis <dir> --anchor <amendments.jsonl>` | construction-A reproduction of `65118a…9dd9` over the 5.0 genesis copies; legacy alias = prefix; same intruder/flip strokes as A1-07a |

**Review gate:** watch one live verify walk end to end.

## A2 — Registry

| ID | Criterion | Command | Expected |
|---|---|---|---|
| A2-01 | `.us` parity | us.rs tests vs existing Agents.us/Neiro.us | parse+render identical |
| A2-02 | can_approve refusal | missing-field fixture | refused with named error |
| A2-03 | ~30 agents enrolled | `atl agent enroll --dry` then real | registry rows; undeclared actor refused context |
| A2-04 | Orientation pack | `atlas-mcp get_in_line` against a test home | line+road+log-tail assembled |

**Review gate:** spot-check five declarations against observed behavior.

## B1 — The Line (Go MCP)

| ID | Criterion | Command | Expected |
|---|---|---|---|
| B1-01 | Tool surface parity | `atlas-mcp --prove` | ≥12 strokes exit 0 |
| B1-02 | Forbidden verbs absent | route-table assertion test | approve/ascend/merge/commit/push/delete/reject/promote absent |
| B1-03 | Receipts honest | read_doctrine absent-name knock | denial, not fabrication |
| B1-04 | One-writer lock | concurrent ask stress (temp chain) | serialized; chain INTACT after |
| B1-05 | Zero-write guard | `atlas-mcp --prove` | 24 strokes exit 0; ask_steward refuses any engine reaching estate/secondbrain/manjuel core |

**Review gate:** operator knocks tools from his own session.

## B2 — THE MESH (`.us` messaging protocol)

*Spec-first. The spec (`specs/SPEC_US_MESH.md`) and golden vectors
(`tools/cut_mesh_vectors.py`) land before any protocol or server code. atlas
version pins `0.1.0+b2` at this implementation. All proves hermetic — the
oracle is the LOCAL folded fixture set; live `manjuel.us`/`api.manjuel.us` seed
the fixtures once and are a separate optional drift stroke, never in `--verify`.*

| ID | Criterion | Command | Expected |
|---|---|---|---|
| B2-01 | Envelope integrity | `python tools\cut_mesh_vectors.py --verify` | chain-intact / flip / tamper / mark-welded PASS (hash = sha256(prev \|\| canon), sig/pub OUTSIDE the five keys) |
| B2-02 | Sealed commitment | `cut_mesh_vectors.py --verify` | `sealed` PASS: commitment = `H(salt \|\| plaintext)`, salt 32B, reveal verifies, `commitment != H(plaintext)` — **NOT** `H(ct)` (low-entropy msgs brute-forceable; `H(ct)` cannot verify on reveal) |
| B2-03 | Identity / auth | `cut_mesh_vectors.py --verify` | auth-refuse PASS: unenrolled `actor` refused by name; mark welds `sha256(pub)[:16]` |
| B2-04 | Wall isolation | `cut_mesh_vectors.py --verify` | wall-refuse PASS: `chan` != caller project refused by name |
| B2-05 | Egress + read-only mirror | `cut_mesh_vectors.py --verify` | egress-refuse + mirror-readonly PASS: non-estate destination refused; `api.manjuel.us`/`manjuel.us` refuse write verbs (405) by structure |
| B2-06 | Signing — structural | `cut_mesh_vectors.py --verify` | signing-model PASS: `sig`/`pub` ride OUTSIDE the hashed body; `mark` welds to `pub` (envelope shape lets old entries survive a signature) |
| B2-07 | Signing — differential Py↔Go | `atlas` sign/verify vs `jesster.py` | sign in Python → verify in Go; sign in Go → verify in Python, over the fixture chain, **incl. malleability edges**. Hand-rolled Go secp256k1 Schnorr (zero crates) must byte-match `jesster.py`; "the port passes its own tests" is NOT sufficient |
| B2-08 | Cross-impl verdict | `cut_mesh_vectors.py --verify` | cross-impl PASS: two independent walkers (estate `us_chain.py` ↔ atlas logic, both local) agree on verdict + head hash |
| B2-09 | Per-actor + channel-head | `cut_mesh_vectors.py --verify` | one-pen PASS: distinct chains (per-actor + SSM channel-head), each INTACT, zero forks |
| B2-10 | Marks cross-weld | `cut_mesh_vectors.py --verify` | marks-weld PASS: jesster chain cites covenant `65118a147dd49ed9` + foundation `2cee607d21696d63` |
| B2-11 | Reconcile kind | `cut_mesh_vectors.py --verify` | reconcile PASS: on-chain `reconcile` tallies weighed/grounded/flagged |
| B2-12 | Breach kind | `cut_mesh_vectors.py --verify` | breach PASS: on-chain `breach_attempt` logs refused op (`detail: "network call refused"`) — the structural gate's receipt |
| B2-13 | Hermetic oracle discipline | `cut_mesh_vectors.py` | oracle = local `tests/fixtures/chains/*`; each golden pins the fixture `sha256`; tool touches NO network; live re-seed is separate/optional |
| B2-14 | Spec frozen (corrected) | `specs\SPEC_US_MESH.md` present | salted SEALED (`H(salt\|\|plaintext)`), hand-rolled Schnorr + differential acceptance, local-oracle law, three-system distinction, structural gate, read-only mirror surfaces |

**Review gate:** operator reads SPEC_US_MESH; confirms three corrections —
(1) SEALED commits to `H(salt ‖ plaintext)` (salt 32B, reveal verifies), not
`H(ct)`; (2) signing is hand-rolled secp256k1 Schnorr in Go with a **differential
Py↔Go** acceptance row, not "Go stdlib Schnorr"; (3) oracles stay local — live
chains seeded the fixtures once (sha256 pinned), live drift is a separate stroke.
Transport = live websocket (estate-internal) + ledger truth; surfaces = Aurora
(view/verify), `api.manjuel.us` (read-only 405), `manjuel.us` (PaaS), atlas (SSM,
writes on the estate with the cypher).

## C1 — Faces (TS)

| ID | Criterion | Command | Expected |
|---|---|---|---|
| C1-01 | Dashboard bridge read-only | bridge prove + write-attempt probe | reads fold live; writes refused by construction |
| C1-02 | Console v2 additive flags off = today's face | visual diff | pixel-parity with flags off |
| C1-03 | `atl` toolchain | atl lint/self-test | green |

**Review gate:** browser pass at phone size.

## D1 — Town (Go)

| ID | Criterion | Command | Expected |
|---|---|---|---|
| D1-01 | Beat posts trade tasks REVIEW-gated | `atlas-town --prove` (temp ground) | open WO → task; closed → none; month-key patrol recurrence |
| D1-02 | No auto-approve path | static self-check (kept from trade_tasks) | assertion green |
| D1-03 | Flow jitter | seeded-run stats | pauses drawn per window a-b, SystemRandom-equivalent entropy |
| D1-04 | Dedup vs full history | approved task not re-posted while open | stroke green |

**Review gate:** one live `beat` acceptance by operator.

## D2 — Trade + Door (Go+Rust)

| ID | Criterion | Command | Expected |
|---|---|---|---|
| D2-01 | Trade parity | property/workorder/inspect/report proves vs golden masters | identical outputs incl. $ receipts |
| D2-02 | Badge truth | `atlas-door --prove` tamper flip | badge red names the break; green when whole |
| D2-03 | Crew forms sealed | phone-form writes on temp book | entries chained + witnessed |

**Review gate:** phone-size acceptance run.

## E1 — Kernels (C++)

| ID | Criterion | Command | Expected |
|---|---|---|---|
| E1-01 | PPMI parity | libppmi prove vs Python fixtures | integer counts bit-exact; floats within specced tolerance |
| E1-02 | Digest scale | foldall on sample catalog slice | bounded RSS; links laid via Rust pen |
| E1-03 | Predictor speed | bench | ≥10× Python on fixed corpus |
| E1-04 | Socket-free | source scan in CI | zero network includes |

**Review gate:** side-by-side timing/output review.

## F1 — Harvest features

| ID | Criterion | Command | Expected |
|---|---|---|---|
| F1-01 | Memory API envelopes | citation-envelope prove | every answer carries citations or refuses |
| F1-02 | Guard/Redact/Scan stages | pack-driven pipeline prove | injection blocked; PII stripped; poison flagged (fixtures) |
| F1-03 | SKILL.md lint | `atl skill lint` over rack | spec violations named; valid set green |

**Review gate:** feature demos, operator rules adoption order.

## G-stones — Cutover (per service)

| ID | Criterion | Command | Expected |
|---|---|---|---|
| Gx-01 | Golden-master zero mismatches | `atl gm run --stone <S>` | match=true across full fixture set |
| Gx-02 | Same ports/commands | cutover rehearsal on temp ports | SPEC_COMMANDS map honored |
| Gx-03 | Rollback fold ready | runbook dry-run | old process restorable; fold note drafted for operator hand |

**Review gate:** the operator pulls each switch himself.

---

## Amendments (append-only)

- **2026-08-25** — A1-07 folded into A1-07a/A1-07b per SPEC_COVENANT v2
  prove requirements (House default + Elder legacy + intruder + flip, both
  epochs). Original row: *"Covenant precondition (SPEC_COVENANT) ·
  `atlas covenant check --genesis <dir> --anchor <amendments.jsonl>` ·
  construction-A reproduction of full covenant `65118a…9dd9`; legacy alias =
  prefix; intruder file moves nothing; flipped byte names the doc."*
- **2026-08-25** — P0-04 annotated: specs\ carries eight frozen files since
  SPEC_COVENANT v2 landed post-P0.
- **2026-08-25** — P0-06 annotated: `.venv` is an expected tree member since
  sitting 1 part 2.
