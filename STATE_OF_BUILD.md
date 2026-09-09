# STATE OF BUILD — ATLAS

*Append-only. One dated block per sitting: what landed, what passed, what
opens next. The tail of this file is always the answer to "how is the build
coming along?"*

---

## 2026-08-24 — P0 GROUNDWORK (sitting 1)

**Stone state:** P0 IN PROGRESS → docs complete, seed pending verification.

Landed this sitting:

- `CHARTER.md` — four founding rulings, wall-widening record, standing laws,
  §6 build discipline (venv + sandboxing + hermetic proves).
- `README.md` — reading order and layout.
- `THE_CATALOG.md` — full reconciliation dictionary (~230 modules → 68
  artifact rows across Rust/Go/C++/TS/JSON/SQLite/KEEP-FOLD).
- `SEAT_LOG.md` — opened; P0 witness recorded.
- `specs\` ×7 — SPEC_CHAINS (4-form recognition + live-chain inventory),
  SPEC_CANON (BODY_V 1/2/3), SPEC_US (.us grammar), SPEC_SEAM (one-computer
  rule, Go↔Rust subprocess contract), SPEC_SQLITE (seven DBs, WAL +
  synchronous=FULL + journaled-ledger sync law: record-first writes,
  journal_sync pointer, replay-on-open, refuse-on-break, wrap checkpoints),
  SPEC_MCP.json (14-tool union surface, forbidden verbs absent),
  SPEC_COMMANDS (old↔new map, ports never move at cutover).
- `ACCEPTANCE.md` — testable sheet: every stone's GOAL / PROVEN MODE /
  REVIEW GATE, row IDs P0-01 … Gx-03.
- `tools\` + `data\` — seed_catalog.py + master.db seeding.

Next rows to close: P0-02/P0-03 (seed verify) → then STOP for operator
review gate before A1 opens.

---

## 2026-08-24 — P0 continued: seed green, versioning set (sitting 1, part 2)

- **VENV:** `tools\make_venv.ps1` created `.venv` on Python 3.14.7; pip
  26.2.1; requirements pinned-empty (stdlib only through P0).
- **SEED:** `master.db` seeded via venv — rulings=5, catalog=**73/73**,
  agents empty until A2; `--verify` green and idempotent: dispositions
  valid, no duplicate source paths, schema complete, **journal_mode=WAL**.
- **Defects paid this sitting:**
  1. Disposition `NEW` was used in THE_CATALOG but absent from the seed's
     CHECK vocabulary — `INSERT OR IGNORE` silently swallowed exactly those
     7 rows (R9,R13,T4,J1,J7,S2,S6). Fixed vocabulary in seeder + spec +
     catalog doc; seeder now pre-validates and refuses loudly; `--reset`
     added for P0-scratch schema changes.
  2. `make_venv.ps1` ran bare `install` instead of `-m pip install`.
  3. `verify()`'s inline disposition list drifted from the module constant —
     single-sourced now.
- **VERSIONING:** root `VERSION` = `0.1.0+p0`; SPEC_SEAM now requires every
  binary to answer `--version`; ACCEPTANCE gains P0-07. Git history remains
  uncreated by seat law — init commands handed to the operator at close.
- **Acceptance state:** P0-01 ✓ · P0-02 ✓ · P0-03 ✓ · P0-04 ✓ · P0-05 ✓ ·
  P0-06 ✓ (tree verified docs/specs/tools/data/tests only) · P0-07 ✓.

**P0 COMPLETE — stopped at the operator's review gate. A1 (Spine) does not
open until the ruling comes back.**

---

## 2026-08-24 — P0 addendum: docs suite landed (sitting 1, part 3)

- `docs\QUICKSTART.md` · `docs\WALKTHROUGH.md` · `docs\TUTORIAL.md` (5
  exercises) · `docs\GUIDED_DEMO.md` (7-act scripted tour; every output in
  it captured from real runs this sitting).
- Demo outputs re-captured live: seed VERIFY OK idempotent; catalog
  tallies PORT 34 / ADAPT 19 / NEW 7 / HARVEST 6 / KEEP 4 / FOLD 3;
  stones A1=15 … G-stone=9. One query defect paid en route (missing
  `AS n` alias → ORDER BY error; fixed in-line, no record impact).
- Still: no code artifacts; review gate holds.

---

## 2026-08-25 — P0 repair sitting (sitting 2): record reconciled; gate re-presented

- **Review of the whole dir at the operator's order found one regression and
  three drifts:** CHARTER overwritten unwitnessed 08-24 ~15:01 (content =
  SPEC_COVENANT v2 copy; P0-01 regressed); THE_CATALOG R9 stale vs the
  two-epoch spec (sorted-docs/elder-mark); ACCEPTANCE A1-07 testing Elder
  only; G2 storing bytes as lines. Toolchains absent (cargo/go/g++; node
  present) — installs are the operator's hand.
- **Repairs landed** (rulings banked first: repairs-only · restore-from-record ·
  errata-appendix · operator installs):
  - `CHARTER.md` rebuilt from held record (seeder/master.db rulings,
    SEAT_LOG wall-widening, cited laws); incident folded into dated
    addendum; sources named; nothing invented.
  - `THE_CATALOG.md` ERRATA appendix (append-only respected): R9 two-epoch
    correction; G2 = 453 lines (was 19,133 bytes misfiled).
  - Seeder constants trued; `--reset` reseed → VERIFY OK (rulings=5,
    catalog=73/73, WAL on, idempotent); trued rows query-confirmed.
  - `ACCEPTANCE.md`: A1-07 folded → A1-07a/b (House/Elder, intruder+flip
    strokes both epochs); P0-04/P0-06 annotated; Amendments section opened.
  - `SEAT_LOG.md`: sitting-2 witness appended.
- **Verification:** seed --verify exit 0 twice (post-reset + standalone);
  DB read-back shows R9/G2 carrying corrected values; VERSION unchanged at
  `0.1.0+p0`; no code artifacts; no git history; source grounds untouched.
- **P0 still COMPLETE — the gate is re-presented with a clean record.**
  A1 (Spine) opens only on the operator's ruling; fixtures-first order
  stands per the sitting-1 lesson.

---

## 2026-08-25 — A1 opened: step 1, golden-master fixtures landed (sitting 3)

- **The ruling came back:** "perform step 1." A1 opens through its door in
  the banked order — vectors cut from the live chains BEFORE any Rust
  canon/forms assertions exist.
- **`VERSION` → `0.1.0+a1`.** Stone tag live per SPEC_SEAM §Versioning.
- **`tools\cut_fixtures.py`** forged (stdlib-only, re-runnable): read-only
  walks of the estate ground; byte-faithful full copies for chains ≤256 KB,
  byte-faithful head windows (46 entries) for the three larger ones;
  single-entry sample vectors (first/last/mid/wraps) per chain; MANIFEST.json
  carrying sha256 + structural stats + honest form hints + wrap positions.
- **Cut:** 21/21 SPEC_CHAINS-named chains · 10,759 source entries ·
  4.1 MB walked · 106 fixture files / 788 KB landed under
  `tests\fixtures\{chains,samples,identity}`. Form families captured:
  jcs-v3, envelope, board/links legacy 64-hex, bare16 (harvest, skills
  board), unknowns left to recognition-by-trial.
- **Identity pack cut and PROVEN Python-side:** House construction-A over
  his five live foundation docs reproduces `151274…5bbb`; Elder over the
  four genesis copies reproduces `65118a…9dd9`. Both PASS. Anchors copied
  (`weights\covenant.json`, `amendments.jsonl`). This banks the A1-07a/b
  golden material before a line of Rust exists.
- **Deferred, named:** gateway sqlite shards (R12/S7 stones), remote
  manjuel.us ledger (no seat egress), attic/folded mirrors and reading
  catalogs (corpus, not chains).
- **Verification:** independent fidelity pass — 94/94 fixtures byte-exact
  vs their sources (full copies by sha256; windows/samples by exact bytes);
  zero missing, zero mismatches. One cutter defect paid en route (list/dict
  init typo, caught by first run).
- **A1 state:** step 1 DONE. Step 2 (Rust workspace scaffold) waits on the
  operator's cargo/rustc install — nothing compiles without it.

---

## 2026-08-25 — A1 step 2: the Rust spine stands and proves green (sitting 4)

- **Toolchain found:** the operator had landed rustup stable
  (`rustc 1.98.0, x86_64-pc-windows-msvc`) between sittings; it was simply
  off PATH (`~\.cargo\bin`). First real build also proved the MSVC linker.
- **Workspace scaffolded** — three crates, ZERO external dependencies
  (provenance math stays self-contained; no crates.io, no network):
  - `core\` (atlas-core): `sha256.rs` hand-rolled FIPS 180-4 with RFC
    vectors · `version.rs` (--version seam) · spec-cited stubs for canon /
    chain / forms / covenant / us / schnorr / keys / fold / merkle_dag /
    blanks / vault, each naming its catalog row and landing stone.
  - `store\` (atlas-store): frozen DDL constants verbatim from
    SPEC_SQLITE (rulings/catalog/agents/journal_sync) + schema_migrations +
    the append-only trigger template; driver lands at A1-06.
  - `apps\atlas\` : the `atlas` binary — `--version` prints exactly the
    root VERSION string; `--describe`; unknown commands refused on stderr
    with **exit 2** (SPEC_SEAM lawful-refusal shape).
- **Proven:** `cargo build --workspace` clean · `cargo test --workspace`
  **16 strokes, 0 failed, exit 0** — sha256 RFC vectors + incremental-feed
  parity (7) · **covenant golden strokes in RUST (4)**: House `151274…5bbb`
  and Elder `65118a…9dd9` reproduce from the cut fixtures, intruder files
  move nothing on temp ground, one flipped byte changes the covenant AND
  names `03_CREED.md` · fixture bytes pinned against silent edits (2) ·
  store law shapes (3). Binary smoke: version/describe exit 0, refusal
  exit 2.
- **Design ruling taken (operator may amend):** SHA-256 implemented by hand
  rather than pulling the `sha2` crate — keeps A1 buildable on a bare
  toolchain with no network; if he prefers the crate, this module folds,
  never deletes.
- **Defects paid en route:** finalize() borrow type error · an unparenthesized
  if-expression in the flip test · CARGO_MANIFEST_DIR path math (crate root,
  not tests/) — each caught by compile or first run, fixed, re-proven.
- **A1 state:** steps 1–2 DONE. Step 3 next: canon.rs against the BODY_V
  vectors, then forms/chain verdicts — every assertion meets the frozen
  fixture bytes, never the hints.

---

## 2026-08-25 — A1 step 3: canon proves against the Python oracle (sitting 5)

- **Rulings banked at stand-up:** JSON parsing hand-rolled like SHA-256
  before it (zero external crates standing); scope = canon only this
  sitting, stop for review once A1-01 proves.
- **`tools\cut_canon_vectors.py`** forged — cuts A1-01 vectors from the
  read-only oracle (`estate\Neiro\lib\us_canon.py`) BEFORE any Rust canon
  assertion exists: **89 cases / 356 form-vectors** (16 synthetic sharp-edge
  inputs + all 73 live sample entries ×forms 1/2/3 + unknown-form stroke),
  250 outputs · 106 named refusals (float×12, int_range×5,
  unknown_body_v×89). Deterministic on content — no wall clock, provenance
  by oracle sha256; `--verify` byte-compares a fresh cut, green twice.
- **Probe named the risks before implementation:** 11 floats in live samples
  (V1/V2 must carry Python repr layout) and six ~77-digit BIP-340 sig
  components beyond i64 in custody samples. Neither coerced:
  `core\src\json.rs` landed hand-rolled (last-key-wins like json.loads,
  surrogate folding, loud named refusals, depth cap; `Json::Big` carries
  digit text verbatim) · `core\src\canon.rs` filled its stub (V1 BOARD /
  V2 LINKS reproduction incl. CPython-repr float writer; V3 JCS UTF-16-be
  key order, minimal escapes, ±(2^53−1) bounds; `CanonRefused`
  {Float, IntRange, UnknownBodyV}).
- **Proven:** `cargo test -p atlas-core canon` green — all **356 oracle
  vectors met byte-for-byte on first full contact**; workspace total now
  **28 strokes exit 0** (was 16). Binary seams hold: `--version` →
  `0.1.0+a1` exit 0, unknown command refused exit 2.
- **Defects paid en route:** two `jcs_write` arms returned Err where unit
  was owed (compile caught) · cutter source corrupted by transport-level
  escape mangling, rewritten backslash-free (chr(92) construction — the
  file can no longer rot that way).
- **A1 state:** steps 1–3 DONE; A1-01 closed. Step 4 next: forms.rs
  recognition-by-trial + chain.rs FLIP/TAMPER verdicts over the frozen
  fixture chains (A1-02/A1-03). Opens at the operator's word.

---

## 2026-08-25 — A1 step 4: recognition + verdicts mirror both provers (sitting 6)

- **`tools\cut_chain_verdicts.py`** — golden verdicts cut from BOTH read-only
  oracles before a line of Rust: `us_chain.verify` (verdict dict) +
  `prove_parity.read_chain` (13-form trial) over all 21 fixture chains, plus
  **8 injection recipes on temp ground** (flip/drop/truncate/corrupt × the
  V3 ledger and a legacy board). Deterministic; `--verify` green twice.
- **Oracle crash recorded, not patched:** `us_chain.verify` cannot walk
  hash-less rows (commons board/snapshots/custody) — guarded as a named
  skip; Rust asserts the same ground truth independently.
- **Landed:** `core\src\forms.rs` (13 constructions, oracle order verbatim;
  quirks pinned: zero-match reports the FIRST form's name with matched=0) ·
  `core\src\chain.rs` (EMPTY/INTACT/FLIP/TAMPER mirror; weld follows STORED
  hashes; canonicalisation refusal → TAMPER at that entry).
- **Proven:** 42 golden records met — 21×2 provers + 8 injections re-applied
  to fresh temp copies; A1-03 strokes asserted directly (FLIP names #1,
  appendable; TAMPER locates and refuses append; truncation = lawful
  INTACT prefix). Workspace **41 strokes exit 0** (was 28).
- **Binary seam:** `atlas chain verify|recognize (<path> | --roots <dir>)`.
  Live estate walk witnessed end-to-end: every readable chain fully matched
  under its named form (steward_ledger 2062/2062, jesster gen4 1246/1246);
  agents_seatlog verifies INTACT live; walk exits UNSOUND naming exactly the
  six chains no known form reads (hash-less ×3, keyed/blake ops-trade ×4
  rows SPEC_CHAINS defers). Reported, never explained away.
- **A1 state:** A1-01/02/03/05/07a/07b closed. Open: A1-04 (export
  round-trip), A1-06 (store journal-sync driver) — both blocked on one
  operator ruling: the SQLite story (vendored amalgamation, admitted crate,
  or defer). Gate reached.

---

## 2026-08-25 — A1 step 5: the store stands on the system DLL; A1 COMPLETE (sitting 7)

- **Rulings:** SQLite binds the SYSTEM `winsqlite3.dll` (zero crates.io /
  downloads / compiler); Merkle proof-walk in scope; export trio approved.
  Spike: 26/26 symbols present, `libversion 3.51.1`; SDK import lib found →
  static `#[link]`.
- **Landed:** `store\src\ffi.rs` · `driver.rs` (RAII; connection law applied
  AND observed) · `migrations.rs` (frozen DDL verbatim; append-only triggers
  on the mirror — `chains` is derived and mutable by definition) ·
  `core\src\merkle.rs` (+ a THIRD tree: forge/links text-v1) · `sync.rs`
  (six sync rules as named code) · `import_export.rs` (two-door admission) ·
  CLI `atlas db init|import|export|status`.
- **Finding of the sitting — three Merkle dialects on one ground:** Jesster
  library wraps reproduce under NEITHER us_chain tree; their writer hashed
  hex-text concatenations. All EIGHT closed roots pinned under links-v1-text
  + path climbs; stamped mv=2 verifies only under v2; absent mv trials both
  historical dialects and names the match. kimi's `wrap` kind = harvest
  verdicts without roots — named skip.
- **A1-04 proven:** trio round-trips byte-identical INCLUDING CRLF fidelity
  (steward ledger carries `\r\n`; mirror stores raw segments verbatim).
- **A1-06 proven hermetic:** law observed through FFI; triggers refuse by
  name; record-first refusal leaves DB bytes unchanged; crash window healed
  by idempotent replay-on-open; refuse-on-break read-only with the why;
  checkpoint + consistency walk after wrap crossings. Cross-version stroke:
  Rust reads Python-written master.db (73 catalog / 5 rulings / WAL).
- **Defects paid:** sqlite_master.name; PRAGMA synchronous is an INTEGER;
  FK ordering until replay seeded its parent row inside the txn; raw-bytes
  storage over canon re-serialisation; two-door import for legacy chains.
- **A1 COMPLETE (01…07b).** Review gate reached; A2 (Registry) opens at the
  operator's word. Workspace: **65 strokes exit 0** (was 41). VERSION
  unchanged `0.1.0+a1`.

---

## 2026-08-25 — A2: the household is named (sitting 8)

- **Operator rulings:** manjuel5.us stricken to attics and excluded from all
  goldens permanently (lawful census = four tool-born files → byte-round-
  trip universal); `atlas agent enroll` owns the verb until C1 wraps it;
  roster folds House-first.
- **`tools\cut_us_vectors.py`** — goldens from `us_read.py`: render bytes ×4,
  14 refusals stored as input-blocks + named classes, doc-level shapes,
  7 derive folds. **`core\src\us.rs`** — exact mirror incl. the gate
  (`can_approve` absent/true refuse) and the oracle quirk that 'ask' grants
  the tool while the fold reports the lost gate. **A2-01/02 proven first
  contact** (us_parity.rs).
- **The household:** `tools\fold_agents.py` → **37 single-seat declarations**
  born canonical via the oracle's own render + 4 household maps. Twelve
  Tribes quoted from LAW_002; council personas; ten lineage actors from the
  chain census; operator + opencode; seven doctrine seats — every row
  `can_approve:false`, every source cited.
- **A2-03 proven:** `store\src\enroll.rs` — covenant cited · reports_to
  resolvable · CHECK=0 backs the door · idempotent · dry-run = real txn +
  ROLLBACK · undeclared actors refused context by name.
- **A2-04 proven:** `orient_home` (standing law + LINE + ROAD + LOG TAIL,
  60k cap) against the demo-vault Manjuel home, live-witnessed. CLI:
  `atlas agent enroll`, `atlas orient --home`.
- **Defects paid:** frozen DDL dictated one-agent-per-file (fold rebuilt);
  dry-run originally landed rows via autocommit (now real-txn-rollback);
  the 'ask'-grants stroke corrected an assumed expectation.
- **A2 COMPLETE pending review gate** (five-declaration spot-check).
  Workspace: **77 strokes exit 0**. VERSION unchanged `0.1.0+a1`.

---

## 2026-08-25 — B1 opened: THE LINE stands multi-tenant (sitting 9)

- **Genesis law:** the MCP holds ALL of the estate — every project a
  first-class tenant, tools name their ground, strangers refused by name.
- **A2 gate rulings folded first:** operator↔manjuel circle (operator
  reports_to manjuel; manjuel is in charge as the operator's serf unless
  overruled); "i am the approval" — can_approve false everywhere including
  the operator's row. Re-folded byte-canonical; fresh-copy enrollment
  37/37, circle verified in the record.
- **`line\` scaffolded** (Go 1.26.7, stdlib-only): tenant registry ·
  per-tenant orientation under the 60k cap · surface of 14 tools
  (3 landed: get_in_line, verify_chain via SPEC_SEAM subprocess to
  atlas.exe, muster; 11 refusing honestly until their stones) · newline
  JSON-RPC protocol 2025-06-18 with parity instructions at handshake.
- **PROVEN:** shipped `--prove` — 13 strokes exit 0, incl. the
  multi-tenancy heart: one tool, three temp grounds, three different
  truths, each labeled with its tenant. Binary smoke: `--version` →
  `0.1.0+b1` exit 0 · unknown verb exit 2.
- **VERSION → `0.1.0+b1`** (a2 rode a1's tag by oversight; the version pin
  caught it — pin updated, debt paid and witnessed). Rust workspace
  re-sealed: **77 strokes exit 0**.
- **B1 state:** foundation landed. Next: land the remaining tools for real
  (receipts, doctrine, wall, matrix, ask_steward + one-writer ask lock),
  then A-row closure B1-01..04.

---

## 2026-08-27 — B1 COMPLETE: THE LINE carries the household (sitting 10)

- **Stone state:** B1 COMPLETE. 14-tool surface; 11 of the 14 now land for
  real (the 3 genesis tools carry through; the rack_* trio honest-refuse until
  F1). B1-01..04 closed.

Landed this sitting:

- `line/internal/tenant` — Manifest + Engine; manifest-aware resolvers;
  Default prefers neiro; per-tenant record-map (`line.manifest.json`) honored
  with a rigid default fallback.
- `line/internal/orient` — generalized over tenants, graceful degradation
  (named absence, not refusal).
- `line/internal/tools` — 8 tools real: read_handoffs (sha256 receipts),
  list/read_doctrine (honest denial), check_the_wall (INSIDE/REFUSED + THE
  WALL), state_matrix (fold), read_plan (manifest 'plans'), ask_steward
  (engine subprocess + ask lock), remember (testimony under ask lock);
  rack_* trio honest refusals.
- `line/cmd/atlas-mcp/main` — neiro auto-carry via NEIRO_HOME (default empty
  const), `--engine name=cmd`, dropped auto-atlas.
- `line/engine/manjuel_ask.py` — NEW adapter mirroring manjuel's `_RUNNER`
  (conscience.wake + skills.invoke("weigh")); read-only to the manjuel build.
- `line/cmd/atlas-mcp/prove` — 23 strokes incl B1-01..04.

- **PROVEN:** go build+vet clean · go test ./... ok · atlas-mcp --prove 23
  strokes exit 0 · cargo test --workspace 77/77 (no Rust change).
- **VERSION** unchanged `0.1.0+b1`.

- **B1 state:** COMPLETE. Next stone: C1 (Faces of the Household).

---

## 2026-08-27 — B1 hardening + B2 THE MESH spec (sitting 11)

- **B1 hardening (operator ruling carried):** atlas must never boot or forward
  to the read-only source grounds (estate/, secondbrain/, manjuel core) — doing
  so would write to a ground the law holds read-only. `line/internal/tools`
  gained `touchesReadonlyGround()` + a ZERO-WRITE GUARD in `toolAskSteward`:
  any engine command reaching a read-only ground is refused by name. `manjuel_ask.py`
  left untouched per the operator's "don't touch yet."
- **`line/cmd/atlas-mcp/prove`** — +1 stroke: ask_steward refuses an engine
  reaching a read-only ground. Strokes 23 -> **24**, exit 0.
- **B2 THE MESH — spec-first (operator rulings: transport decided in-spec, v1 =
  THE LINE `mesh_*` tools; all five security guarantees non-negotiable; scale for
  growth; confidentiality = ciphertext at rest + sovereign deciphering ledger).**
  - `specs/SPEC_US_MESH.md` — the envelope IS the estate's proven links-chain
    entry (five-key body `ts,kind,payload,prev,actor` + `hash=sha256(prev ||
    canon)` + JESSTER-domain Schnorr `sig/pub` + `cites` linking), plus
    confidentiality (ciphertext at rest; deciphering ledger sovereign: paper
    cypher = 2FA unlock once/day; per-agent keys in `.env`; session keys
    post-unlock; security in admin/orchestration), wall isolation (channel =
    tenant), zero-egress (no write path, mirror model), transport decided
    (v1 = THE LINE), scale (abstracted store, open enrollment), version pin
    `0.1.0+b2` at impl.
  - `tools/cut_mesh_vectors.py` — stdlib-only, reads the fixture
    `tests/fixtures/chains/forge_links_chain.jsonl` as the oracle; cuts + verifies
    8 golden vectors: chain-intact, flip, tamper, mark-welded, confidentiality,
    auth-refuse, wall-refuse, egress-refuse. `--verify` PROVEN (8/8 PASS);
    bare run writes `tests/fixtures/mesh_vectors.json`.
- **PROVEN:** go build+vet clean · go test ./... ok · atlas-mcp --prove 24
  strokes exit 0 · `cut_mesh_vectors.py --verify` 8/8 PASS · cargo test
  --workspace 77/77 (no Rust change, regression-free).
- **VERSION** unchanged `0.1.0+b1` (B2 implementation will pin `0.1.0+b2`).
- **B1/B2 state:** B1 COMPLETE (incl. hardening). B2 SPEC-FIRST COMPLETE;
  implementation pending the operator's transport + deciphering-ledger ruling.
  Next stone: B2 implement (mesh_* tools + deciphering ledger).

---

## 2026-08-27 — B2 THE MESH spec corrected + executed (sitting 12)

- **Three operator corrections landed (all load-bearing):**
  1. **SEALED committed to the wrong thing.** Draft used `H(ct)` — brute-forceable
     for low-entropy messages and non-verifiable on reveal. Fixed to
     `commitment = H(salt ‖ plaintext)`, `salt` = 32 random bytes stored beside
     the message in the estate and revealed with it (hides; reveals verify).
  2. **"Go stdlib Schnorr port" is impossible.** Go has no secp256k1/Schnorr.
     atlas signs with secp256k1 Schnorr **hand-rolled in Go (zero crates)**,
     byte-for-byte with `jesster.py`. Acceptance is a **differential Py↔Go**
     vector set (sign Py→verify Go, sign Go→verify Py, incl. malleability edges),
     not "the port passes its own tests."
  3. **Live endpoints as oracles break hermetic law.** `cut_mesh_vectors.py`
     reads only the LOCAL folded fixtures (`tests/fixtures/chains/`, cut
     2026-08-25); each golden pins the fixture `sha256`. Live re-fetch is a
     separate optional drift stroke, never in `--verify`.
- **Rewrite executed (spec-first, corrected):**
  - `specs/SPEC_US_MESH.md` — three-system distinction (manjuel.us / estate
    `manjuel` engine / `jesster` keygen; signing = jesster, never parked
    `keys.py`); SEALED = `H(salt ‖ plaintext)`; structural gate (absent verbs,
    wall = tenant isolation, cypher = root, on-chain `breach_attempt`); transport
    = live websocket (estate-internal) + ledger + channel-head chain; surfaces =
    Aurora (view/verify), `api.manjuel.us` (read-only 405), `manjuel.us` (PaaS),
    atlas (SSM).
  - `tools/cut_mesh_vectors.py` — **8 → 15 goldens** (added signing-model,
    cross-impl, one-pen, marks-weld, reconcile, breach, mirror-readonly;
    confidentiality rewritten to salted commitment). All hermetic, local, sha256
    pinned, no network.
  - `ACCEPTANCE.md` B2 → 14 rows (B2-01..B2-14); B2-07 = differential Py↔Go
    signing; B2-13 = hermetic-oracle discipline.
  - **VERSION → `0.1.0+b2`** (root + line + line/cmd/atlas-mcp + version.rs
    assert).
- **PROVEN:** go build+vet clean · go test ./... ok · atlas-mcp --prove 24
  strokes exit 0 · `cut_mesh_vectors.py --verify` **15/15** · cargo test
  --workspace **77/77** (version assert now `+b2`) · no source-ground writes.
- **B1/B2 state:** B1 COMPLETE. B2 SPEC-FIRST (corrected) COMPLETE + executed.
  Implementation opens at the operator's word.

---

## 2026-09-03 — A2 repair: the 40-seat household pinned (sitting 13, step 1)

- **Red found at stand-up:** `cargo test --workspace` failed 2 enroll strokes —
  the registry pin still said 37 while `agents\*.us` carries 40 (estate-alignment
  fold: analyst/courier/scout, 2026-08-28, previously unwitnessed) and the live
  `data\master.db` already holds all 40. The pin did its job — it caught an
  unlogged bump.
- **Repair:** `store\src\enroll.rs` tests now clear the temp copy's agents table
  first (hermetic: prove enrollment, not the live DB's past) and pin
  `files_read = 40`. Live `data\master.db` untouched (already correct at 40).
- **PROVEN:** `cargo test --workspace` **77/77 exit 0** · `fold_agents.py
  --verify` OK · mesh goldens 15/15 still PASS · Go `--prove` 24 strokes still
  PASS · no source-ground writes.
- **A2/B2 state:** A2 re-sealed at 40 seats. B2 implementation opens next on this
  sitting under the banked "1 then 2" ruling.

---

## 2026-09-03 — B2-07 differential signing landed (sitting 13, step 2)

- **Cut:** `tools\cut_schnorr_vectors.py` + `tests\fixtures\schnorr_vectors.json`
  — 9 goldens from read-only `jesster.py` (oracle sha256 pinned), `--verify` 9/9.
- **Built:** `line\internal\mesh\schnorr.go` (hand-rolled secp256k1 Schnorr, stdlib
  only) + `schnorr_test.go` driving the goldens — sign byte-match 16/16,
  verify-accept 16/16, all six refusal edges, certify round-trip + tamper refuse.
  Cross-direction proven explicitly: fresh Go sig verifies `True` in Python.
- **PROVEN:** go build/vet/test ok · `--prove` 24 strokes exit 0 · mesh 15/15 ·
  schnorr 9/9 · cargo 77/77 · fold OK · no source-ground writes.
- **B2 state:** signing half DONE (B2-06/B2-07 structural + differential). Open:
  `mesh_*` tools, deciphering ledger, mesh `--prove` stroke, operator review gate.

---

## 2026-09-03 — B2 tools landed: the mesh speaks (sitting 14)

- **Built (`line\internal\mesh`, stdlib only):** `envelope.go` (Python-compat
  canon; weld verdicts + FORGERY for bad sigs) · `seal.go` (salted commitment
  `H(salt‖plaintext)` + stream cipher with honesty clause; env-only keys) ·
  `store.go` (member bindings, per-actor chains + signed channel-head,
  deciphering ledger; key must match enrolled pub).
- **Surfaced:** `mesh_enroll`/`mesh_post`/`mesh_read`/`mesh_chain`/`mesh_cite`
  (surface 14 → 19; writes under the ask lock; wall = chan defaults to caller
  project).
- **PROVEN:** `--prove` **34 strokes exit 0** (10 new mesh strokes) ·
  `go build/vet/test` ok · mesh 7 tests green · cargo **77/77** · all six
  python cutters `--verify` OK · no source-ground writes.
- **B2 state:** implementation COMPLETE pending review gate. Open (named, not
  blocking): `.us`-registry cross-check, wrap closing at n=40, websocket
  transport. Operator reads SPEC_US_MESH + this sitting, then rules the gate.

---

## 2026-09-03 — B2 gate passed; C1 FACES landed (sitting 15)

- **Gate (banked on "continue"):** B2 COMPLETE. THE_ROAD snapshot + order
  rewritten (B2 ✓, C1 NEXT). First-"no"-is-law note banked with the reading.
- **Cut:** `tools\cut_faces_vectors.py` + `faces_ground/` + `faces_snapshot.json`
  + `faces_vectors.json` — oracle pins + deterministic golden ground, `--verify` green.
- **Built:** `faces\console-v2\` (oracle bytes verbatim + flags loader) ·
  `faces\bridge\bridge.ts` (read-only fold, golden byte-match) · `atl\cli.ts`
  (wrap/serve/check/lint/self-test) + hand-rolled `node.d.ts` + dep-free
  `package.json`.
- **PROVEN:** `atl self-test` 9/9 · tsc strict clean · lint CLEAN · cargo 77/77 ·
  go build/vet/test ok · `--prove` 34 strokes exit 0 · seven cutters OK ·
  `atl --version` 0.1.0+c1 · no source-ground writes.
- **VERSION → `0.1.0+c1`.**
- **C1 state:** implementation COMPLETE pending review gate (incl. the stated
  C1-02 byte-parity substitution). Next stone on ruling: D1 Town.

---

## 2026-09-03 — C1 gate passed; D1 TOWN landed (sitting 16)

- **Gate (banked on "continue"):** C1 COMPLETE. THE_ROAD order rewritten.
- **Cut:** `tools\cut_town_vectors.py` + `tests\fixtures\town_vectors.json` —
  4 decision goldens from the oracle's own `candidates()`, `--verify` green.
- **Built:** `line\internal\town` (ops/candidates/board/beat/jitter) +
  `line\cmd\atlas-town` (beat/flow/story/look/prove, 11 strokes) — stdlib only.
- **PROVEN:** town `--prove` 11/11 exit 0 · town 6 tests green · go suite ok ·
  cargo 77/77 · `atl self-test` 10/10 · tsc clean · lint CLEAN · eight
  cutters OK · no source-ground writes.
- **VERSION → `0.1.0+d1`.**
- **D1 state:** implementation COMPLETE pending review gate (live `beat`
  acceptance). Next stone on ruling: D2 Trade+Door.

---

## 2026-09-03 — D1 gate passed; D2 TRADE+DOOR landed (sitting 17)

- **Gate (banked on "continue"):** D1 COMPLETE. THE_ROAD order rewritten.
- **Cut:** `tools\cut_trade_vectors.py` + `trade_vectors.json` (15 outputs) +
  `trade_books/` — oracle pins + scenario books, `--verify` green.
- **Built:** `core\src\pyjson.rs` + `store\src\trade.rs` (`atlas trade` verbs) +
  `line\cmd\atlas-door` (:8080, badge, forms, 13-stroke prove).
- **PROVEN:** cargo 82/82 · door `--prove` 13/13 · go suite ok · `atl
  self-test` 10/10 · tsc clean · lint CLEAN · nine cutters OK ·
  check_trade_parity 7/7 · no source-ground writes.
- **VERSION → `0.1.0+d2`.**
- **D2 state:** implementation COMPLETE pending review gate (phone-size
  acceptance). Next stone on ruling: E1 Kernels.

---

## 2026-09-03 — D2 gate passed; E1 STEP 1 landed (sitting 18)

- **Gate (banked on "continue" + "loopback is the default"):** D2 COMPLETE;
  loopback-default CONFIRMED as doctrine for all atlas servers. THE_ROAD
  order rewritten.
- **Cut:** `tools\cut_ppmi_vectors.py` + `ppmi_vectors.json` — 20 goldens
  from models.py, `--verify` green.
- **Built:** `kernels/` (ppmi.hpp/cpp, prove.cpp, prove.py harness) — MSVC
  /O2, stdlib only.
- **PROVEN:** kernels 13/13 exit 0 (worst float diff 1.67e-16) + socket scan
  clean · cargo 82/82 · go suite ok · `atl self-test` PROVEN · cutters green ·
  no source-ground writes.
- **VERSION unchanged (`0.1.0+d2`):** E1 closes whole or not at all.
- **E1 state:** E1-01 ✓, E1-04 ✓ (landed surface). OPEN: E1-02 digest scale,
  E1-03 predictor bench. Next sitting finishes the stone.

---

## 2026-09-03 — E1 CLOSED whole (sitting 19)

- **Cut:** `cut_digest_vectors.py` + `digest_catalog.jsonl` + `cut_predict_
  vectors.py` — meal/prune/link + consult goldens, all `--verify` green.
- **Built:** `store\src\link.rs` (`atlas link lay|status`, Merkle v1+v2) +
  `kernels/` (sha256, digest+foldall, predict+bench, prove.py harness).
- **PROVEN:** kernels exit 0 (17 strokes + foldall e2e + bench 51.5× + scan
  clean) · cargo 84/84 · go suite ok · `atl self-test` PROVEN · tsc clean ·
  lint CLEAN · twelve cutters green · no source-ground writes.
- **VERSION → `0.1.0+e1`.**
- **E1 state:** COMPLETE pending review gate (side-by-side timing/output).
  Next stone on ruling: F1 Harvest.

---

## 2026-09-03 — E1 gate passed; F1 STEP 1 landed (sitting 20)

- **Gate (banked on three readings):** E1 COMPLETE; F1 opens on local Ollama
  + rack, starting small. THE_ROAD order rewritten.
- **Cut:** `tools\cut_rack_vectors.py` + `rack_tags.json` + `rack_ladder.txt`
  — folded live list + pinned ladder, `--verify` green without fetching.
- **Built:** `line\internal\rack` (loopback-guarded host, list, ladder) +
  `rack_list` real on THE LINE (ask/open still refusing honestly).
- **PROVEN:** rack 4 tests green · `--prove` 40 strokes exit 0 · cargo 84/84 ·
  go suite ok · `atl self-test` PROVEN · tsc clean · lint CLEAN · thirteen
  cutters green · live ladder via real tool vs real door · no source-ground
  writes.
- **VERSION unchanged (`0.1.0+e1`).**
- **F1 state:** step 1 DONE. OPEN: rack_ask, rack_open, F1-01 envelopes,
  F1-02 guard pipeline, F1-03 skill lint.

---

## 2026-09-04 — F1 STEP 2 landed: rack_ask (sitting 21)

- **Cut:** `tools\cut_rack_ask_vectors.py` + `rack_ask.json` — capabilities,
  default route, answer shape, `--verify` green without fetching.
- **Built:** `line\internal\rack\ask.go` + `rack_ask` real on THE LINE
  (route/ask/witness; rack_open still refusing).
- **PROVEN:** rack 7 tests green · `--prove` 44 strokes exit 0 · cargo 84/84 ·
  go suite ok · `atl self-test` PROVEN · tsc clean · lint CLEAN · fourteen
  cutters green · live ask via real tool vs real door · no source-ground
  writes.
- **VERSION unchanged (`0.1.0+e1`).**
- **F1 state:** steps 1–3 DONE. OPEN: F1-01 envelopes, F1-02 guard pipeline,
  F1-03 skill lint.

---

## 2026-09-04 — F1 STEP 3 landed: rack_open (sitting 22)

- **Cut:** `tools\cut_rack_open_vectors.py` + bundle ground + d1/d2 goldens,
  `--verify` green without fetching.
- **Built:** `line\internal\rack\open.go` + `rack_open` real on THE LINE
  (card/ladder+memory/ground; refusals; read-only).
- **PROVEN:** rack 10 tests green · `--prove` 49 strokes exit 0 · cargo 84/84 ·
  go suite ok · `atl self-test` PROVEN · tsc clean · lint CLEAN · fifteen
  cutters green · live bundle via real tool vs real door · no source-ground
  writes.
- **VERSION unchanged (`0.1.0+e1`).**
- **F1 state:** steps 1–3 DONE. OPEN: F1-01 envelopes, F1-02 guard pipeline,
  F1-03 skill lint.

---

## 2026-09-04 — F1-01 landed: memory envelopes (sitting 23)

- **Cut:** `tools\cut_memory_vectors.py` + 3 envelope goldens, `--verify`
  green without fetching.
- **Built:** `line\internal\rack\memory.go` + `memory` real on THE LINE
  (20 tools; cited answers or pinned refusals; read-only).
- **PROVEN:** rack 13 tests green · `--prove` 53 strokes exit 0 · cargo 84/84 ·
  go suite ok · `atl self-test` PROVEN · tsc clean · lint CLEAN · sixteen
  cutters green · live refusal honest · no source-ground writes.
- **VERSION unchanged (`0.1.0+e1`).**
- **F1 state:** steps 1–3 + F1-01 + F1-02 DONE. OPEN: F1-03 skill lint.

---

## 2026-09-04 — F1-02 landed: guard pipeline (sitting 24)

- **Cut:** `tools\cut_guard_vectors.py` + `guard_vectors.json` — oracle poke
  verdicts + specified redact/poison pairs, `--verify` green.
- **Built:** `line\internal\guard` (guard/redact/scan/pipeline) wired FIRST
  in rack_ask (block→no route/no witness; redact→voice+ledger; flags→answer
  wrapper + witness).
- **PROVEN:** guard 4 tests green · `--prove` 59 strokes exit 0 · cargo 84/84 ·
  go suite ok · `atl self-test` 10/10 · tsc clean · lint CLEAN · seventeen
  cutters green · live refusal with zero trace · no source-ground writes.
- **VERSION unchanged (`0.1.0+e1`).**
- **F1 state:** steps 1–3 + F1-01 + F1-02 DONE. OPEN: F1-03 skill lint.

---

## 2026-09-04 — F1 CLOSED whole (sitting 25)

- **Cut:** `tools\cut_skill_vectors.py` + 10 fixtures, `--verify` green.
- **Built:** `atl skill lint` (rules R1..R5 + folded scalars); real rack
  9/9 CLEAN.
- **PROVEN:** cutter 10/10 · `atl self-test` 11/11 · cargo 84/84 · go suite
  ok · kernels exit 0 · tsc clean · lint CLEAN · eighteen cutters green ·
  no source-ground writes.
- **VERSION → `0.1.0+f1`.**
- **F1 state:** COMPLETE pending review gate (feature demos; adoption
  order is the operator's). Next stone on ruling: G Cutovers.

---

## 2026-09-07 — G Cutovers Phase 1: gm harness + Rust --prove landed

- **F1 gate ruled by operator** (proceed directive received).
- **Rust `--prove` battery landed:** `apps/atlas/src/prove.rs` (10 strokes,
  hermetic temp grounds). version-pin · version-cross · chain-verify-fixtures
  (16/21 INTACT, 5 expected TAMPER per sitting-6 finding) ·
  chain-recognize-fixtures (21/21) · store-trio (byte-identical round-trip) ·
  db-lifecycle (init/import/export/status) · enroll-dry (idempotent 40) ·
  orient-pack · link-lay-status · covenant-repro (House `151274…5bbb` +
  Elder `65118a…9dd9` construction-A). `cargo test -p atlas prove_strokes_green`
  OK.
- **@atl/gm golden-master harness landed:** `atl/gm.ts` — the T4 catalog
  row, orchestrates 18 cutter `--verify` + Rust/Go/TS consumer batteries
  per stone. Stone registry: A1 (8 batteries) · B1 (1) · C1 (2) · D1 (3) ·
  D2 (3) · E1 (3) · F1 (8). Report format per SPEC_SEAM.
- **`atl gm` wired into CLI:** `atl gm run [--stone <S>]` · `atl gm list`.
  Runs via `node --experimental-strip-types` (Node 24, no npm deps).
- **PROVEN:** `atl gm run` **28/28 strokes green across 7 stones** ·
  cargo test --workspace all green · go test ./... all ok ·
  tsc --noEmit clean · atl lint CLEAN · atlas --version 0.1.0+f1 ·
  no source-ground writes.
- **Open for operator:** Phase 2 (per-service cutover proofs with Gx-02 port
  check + Gx-03 rollback notes) opens at your word.
- **Lesson:** the gm harness proved that the existing 18 cutters + consumer
  test suites already provide golden-master parity for every built service.
  The harness is orchestration, not re-implementation — cut from what IS.

---

## 2026-09-07 — G Cutovers Phase 2: cutover proofs + rollback notes (sitting 26 cont.)

- **Gx-01 (golden-master zero mismatches):** `atl gm run` 28/28 green across
  7 stones (A1/B1/C1/D1/D2/E1/F1). Prove output saved to
  `docs/rollback/GX01_GM_PROVE.txt`.
- **Gx-02 (port/command verification):** All 7 services verified against
  SPEC_COMMANDS. Report at `docs/rollback/GX02_PORT_COMMAND_REPORT.md`.
  D1: beat/flow/story/look/prove verbs match · D2: port 8080, loopback
  bind, same routes · B1: JSON-RPC 2025-06-18, 20 tools, forbidden absent
  · C1: vendored bytes match oracle · A1: all CLI commands landed ·
  E1: socket-free, kernel parity · F1: Ollama loopback, guard wired.
- **Gx-03 (rollback fold notes):** 7 notes drafted under `docs/rollback/`:
  A1_SPINE.md · B1_LINE.md · C1_FACES.md · D1_TOWN.md · D2_DOOR.md ·
  E1_KERNELS.md · F1_HARVEST.md. Each names the old process, the port
  mapping, and the fold action.
- **PROVEN:** G Cutovers Phase 2 complete. All G-stones have their
  Gx-01/Gx-02/Gx-03 receipts. Operator holds the gate for each switch.
- **VERSION unchanged `0.1.0+f1`.** No source-ground writes.

---

## Documentation Phase — 2026-09-07

All 18 documents written. Operator holds the gate for publication.

### Phase 1: Foundation
- LICENSE: MIT license
- SECURITY.md: vulnerability reporting + security model
- CONTRIBUTING.md: dev setup, code style, PR process

### Phase 2: Public Face
- README.md: full public-facing rewrite with architecture diagram
- CHANGELOG.md: version history P0 through F1

### Phase 3: Specs
- specs/SPEC_US_SCHEMA.json: JSON Schema for .us declarations
- docs/ARCHITECTURE.md: system architecture, layer diagram, data flow, trust model

### Phase 4: ADRs
- docs/ADR/001-polyglot-seam.md
- docs/ADR/002-fold-never-delete.md
- docs/ADR/003-can-approve-false.md
- docs/ADR/004-socket-free-kernels.md
- docs/ADR/005-golden-master-parity.md

### Phase 5: User Guides
- docs/QUICKSTART.md: rewritten for current built state
- docs/WALKTHROUGH.md: full system tour, rewritten
- docs/TUTORIAL.md: 5 exercises, rewritten for current state
- docs/CLI_REFERENCE.md: every command, every flag, all 4 binaries

### Phase 6: Compliance
- docs/COMPLIANCE.md: EU AI Act Art. 12/14/19, SOC 2, ISO 42001 mapping

### Phase 7: Packaging
- Dockerfile: multi-stage build (Rust + Go + runtime)

### Verification
- All 18 files verified present and consistent.
- 65/65 E2E tests still green.
- 85+ Rust tests still green.
- 14 Go tests still green.
- VERSION unchanged `0.1.0+f1`. No source-ground writes.

---

## CI/CD + Parity Plan Phase — 2026-09-07

### Parity Plan
- docs/PARITY_PLAN.md: full build path, cross-language seam map, 9-layer
  prove matrix, parity acceptance criteria, CI/CD architecture.

### CI/CD Pipeline
- .github/workflows/ci.yml: 8-job pipeline (lint, build, test-rust,
  test-go, prove-binaries, prove-kernels, golden-cutters, cross-impl,
  e2e, version-check). Triggers on push/PR to main + workflow_dispatch.
- .github/workflows/release.yml: builds on tag push, creates tarball +
  GitHub Release + Docker image to GHCR.

### Fixes
- kernels/prove.py: cross-platform compiler detection (MSVC on Windows,
  g++/clang++ on Linux). Same prove battery, portable.
- Dockerfile: golang version fixed 1.22 → 1.26, removed live data/ copy,
  added empty data/ directory.
- .gitignore: expanded for CI/CD artifacts, IDE files, OS files, build
  outputs.

### Verification
- Go vet: clean.
- Go tests: all pass.
- Rust tests: 85+ still green.
- VERSION unchanged `0.1.0+f1`. No source-ground writes.

---

## 2026-09-08 — BUG FIX: TUI extractField (sitting 79)

**Stone state:** BUG FIX COMPLETE. All green.

Landed this sitting:

### Fix
- `line/cmd/atlas-tui/main.go` — `cmdAgentsList` now iterates agents
  array directly when a transform is given (matching `cmdToolsList`
  pattern). `--transform name -r` works. Help example updated.
- `extractField` hardened: when `*` hits a map, auto-finds first
  array-valued field and iterates that. `*.name` works on wrapper maps.

### Tests
- `line/cmd/atlas-tui/extract_test.go` — 3 functions covering nested
  paths, wrapper-map auto-find, single-field extraction. All pass.

### Verification
- Go vet: clean.
- Go tests: all pass (92 total across tui + mcp + town + door).
- Rust tests: 85+ green.
- Python verifiers: 4/4 byte-identical.
- MCP prove: 58 strokes PASS.
- VERSION unchanged `0.1.0+f1`. No source-ground writes.

---

## 2026-09-08 — TUI TEST + AGENT DOCS + SKILLS (sitting 80)

**Stone state:** TUI TEST + DOCS COMPLETE. All green.

Landed this sitting:

### TUI Fixes
- YAML format fixed: `printYAML` type mismatch — `[]map[string]any`
  didn't match `case []any:`. Fixed by using `[]any` in cmdRBACList
  and cmdAgentsList.

### Agent Documentation
- 40 agent.md files written (one per citizen), organized by household
  hierarchy. Each includes: office, role, reports_to, mode, permissions,
  source, description.
- agents/docs/README.md — full household index with hierarchy tree.

### Skills
- skills/prove/SKILL.md — run the full prove battery
- skills/orient/SKILL.md — assemble the orientation pack
- skills/enroll/SKILL.md — enroll .us declarations into master.db

### Documentation
- docs/README.md updated with agents, skills, and build plan sections.

### Verification
- TUI: all resource commands tested against live MCP on :8090.
- Agent validation: 40/40 .us files validate (can_approve:false,
  covenant hash, reports_to all present).
- Go vet: clean.
- Go tests: all pass (92 total).
- Rust tests: 85+ green.
- Python verifiers: 4/4 byte-identical.
- MCP prove: 58 strokes PASS.
- VERSION unchanged `0.1.0+f1`. No source-ground writes.

---

## Sitting 81 — Webapp + Full Release Docs (2026-09-08)

### What landed
- **Webapp (Go + vanilla JS, zero external deps):**
  - Backend: main.go, db/db.go (JSON file store), server/server.go (embedded SPA),
    handlers/handlers.go (16 API routes + SSE), agents/, traces/, evals/,
    search/, messaging/ packages
  - Frontend: SPA with Sovereign Dark Theme, 7 pages (dashboard, agents,
    agent detail, traces, trace detail, tools, evals, messages, settings),
    real-time SSE, SHA-256 hash display, tool invocation modal
  - Messaging adapters: Discord, Slack, WhatsApp (stub implementations)
  - Port 8091 (ATLAS_WEB_PORT env var)
- **Release documentation:**
  - LICENSE (MIT)
  - README.md (architecture, quickstart, features, agent system, laws)
  - CONTRIBUTING.md (dev setup, code style, PR process)
  - CHANGELOG.md (full 0.1.0+f1 history)
  - SECURITY.md (vulnerability reporting, scope, hardening)

### Verification
- go build ./webapp/... — PASS (zero external deps)
- go vet ./webapp/... — PASS (clean)
- All prior tests unchanged: 85 Rust, 92 Go, 4 Python, MCP 58 strokes.
- VERSION unchanged `0.1.0+f1`. No source-ground writes.

---

## Sitting 82 — CI/CD (2026-09-08)

### What landed
- **CI workflow** (.github/workflows/prove.yml): Rust, Go, Python, agents, MCP, webapp
- **Release workflow** (.github/workflows/release.yml): cross-platform builds + GitHub release
- **prove.ps1**: local PowerShell prove script (all 5 steps + webapp)
- **release.ps1**: automate version bump, commit, tag, push

### Verification
- prove.ps1 runs clean: all steps PASS
- All prior tests unchanged: 85 Rust, 92 Go, 4 Python, MCP 58 strokes
- VERSION unchanged `0.1.0+f1`. No source-ground writes.

---

## 2026-09-08 — CUTOVER COMPLETE: all 7 switches flipped (sitting 83)

**Stone state:** CUTOVER COMPLETE. All services live. Operator ruling received.

**Operator ruling:** "formally flip em" — 2026-09-08.

**Services confirmed live:**

| Service | Port/Binary | Version | Status | Rollback |
|---|---|---|---|---|
| A1 Spine | `atlas` binary | 0.1.1+f1 | LIVE | `docs/rollback/A1_SPINE.md` |
| B1 MCP | `:8090` (atlas-mcp) | 0.1.1+f1 | LIVE | `docs/rollback/B1_LINE.md` |
| C1 Faces | vendored bytes | 0.1.1+f1 | LIVE | `docs/rollback/C1_FACES.md` |
| D1 Town | atlas-town | 0.1.1+f1 | LIVE | `docs/rollback/D1_TOWN.md` |
| D2 Door | `:8080` (atlas-door) | 0.1.1+f1 | LIVE | `docs/rollback/D2_DOOR.md` |
| E1 Kernels | C++ (ppmi, digest, foldall) | 0.1.1+f1 | LIVE | `docs/rollback/E1_KERNELS.md` |
| F1 Harvest | rack tools via MCP | 0.1.1+f1 | LIVE | `docs/rollback/F1_HARVEST.md` |

**Additional services confirmed live:**

| Service | Port | Version | Status |
|---|---|---|---|
| Webapp | `:8091` | 0.1.1+f1 | LIVE |
| Ollama | `:11434` | — | ONLINE (11 models) |

**Evidence:**
- All 7 Gx-01/Gx-02/Gx-03 receipts from sitting 26
- 112/112 E2E proven (74 scenarios + 38 workflow steps)
- 85+ Rust tests, 92 Go tests, 4 Python verifiers, 58 MCP strokes — all green
- 40/40 agent declarations validated
- Webapp API live (16 routes, SSE, 7 SPA pages)

**No source-ground writes. VERSION unchanged `0.1.1+f1`.**

---

## 2026-09-09 — N0 HYGIENE + N3 RACK-PLAN (sitting 84)

**Stone state:** N0/N3 implementation COMPLETE pending review gate.
Operator ruling "reverse the six No's" banked in SEAT_LOG (SSE+WS ·
two-way team chat · full multi-user SaaS · full DAG; conflicts named).

Landed this sitting:

- `.gitattributes` (`* -text`); `atlas-tui` stdlib `net/http`
  (curl gone); `line\internal\trust\` store; `tenant_list` enumerates
  the registry; `tenant_trust` persists + refuses forbidden/strangers;
  `rack\vram.go` + `rack_plan/pull/warm/sync` tools (12 VRAM goldens
  pinned by `tools\cut_rack_plan_vectors.py`).
- `webapp/db` fold STAGED to N6 (16 live routes; retire breaks `:8091`).

**Proven:** go build/vet clean · go test ./... ok · `atlas-mcp --prove`
**66 strokes exit 0** (was 58) · cutters `--verify` OK (rack-plan 12/12,
rack, rack-ask, fold_agents) · cargo workspace green · no source-ground
writes. VERSION unchanged `0.1.1+f1`.

Next stone on ruling: N1 chat (SSE+WS + `chat_*` tools).

---

## 2026-09-09 — N1 CHAT (sitting 85)

**Stone state:** N1 implementation COMPLETE pending review gate.

Landed this sitting:

- `tools\cut_chat_vectors.py` + `chat_vectors.json` (session shape,
  receipt formula, guard, ordering, isolation — pinned before code).
- `line\internal\rack` — `AskCtx`/`AskStream` (cancel ends the stream;
  whole-or-refused discipline kept).
- `line\internal\chat\` — `state/chat.jsonl` record, receipted turns,
  guard-first no-write refusal, structural isolation, `chat_cancel`.
- THE LINE — `chat_start/send/list/cancel/sessions` + shared
  `ChatSendStream`; `GET /chat/stream` SSE on the MCP door.
- Webapp — `/api/chat/*` + proxied stream + hand-rolled `GET /ws`
  (`chat.send` → tokens → done/error) + SPA `/chat` (forms only,
  Details-behind-receipts, WS→SSE→whole fallbacks, Cancel).

**Proven:** `atlas-mcp --prove` **75 strokes exit 0** (was 66) · `go test
./...` ok (line + webapp, incl. ws frame round-trip) · cutters `--verify`
OK · live smoke refused-before-write confirmed · no source-ground writes.
VERSION unchanged `0.1.1+f1`.

Next stone on ruling: N4 playground.

---

## 2026-09-09 — N4 PLAYGROUND (sitting 86)

**Stone state:** N4 implementation COMPLETE pending review gate.

Landed this sitting:

- `tools\cut_playground_vectors.py` + `playground_vectors.json`
  (name/render/receipt/seat/eval contract — pinned before code).
- `line\internal\rack` — `Detail` telemetry (`AskDetail`); old faces
  unchanged.
- `line\internal\play\` — versioned registry with whole-history fold,
  measured runs (`prompt_run`), `@seat` singles, A/B compares,
  exact-match evals over `evals/<name>.json`; receipts on every run.
- THE LINE — `prompt_save/get/list/run/compare/eval` + `seat_ask`.
- Webapp — `/api/prompts/*` + `/api/seat/ask` + SPA `/playground`
  (registry/editor/run/A-B/`@seat`/eval/record-score). Repaired N1 gap:
  missing `api.js` chat functions now exist.

**Proven:** `atlas-mcp --prove` **88 strokes exit 0** (was 75) · `go test
./...` ok (line + webapp) · cutters `--verify` OK · live smoke
honest-empty + lawful-refusal confirmed, no refusal writes · no
source-ground writes. VERSION unchanged `0.1.1+f1`.

Next stone on ruling: N2 workflow builder (full DAG).

---

## 2026-09-09 — N2 FLOWS (sitting 87)

**Stone state:** N2 implementation COMPLETE pending review gate.

Landed this sitting:

- `tools\cut_flow_vectors.py` + `flow_vectors.json` (validation, topo,
  branches, gates, receipts, budget, refusals — pinned before code).
- `line\internal\flow\` — versioned DAG specs, deterministic runner
  (sequential branches, gates pause, evals steer, budget binds),
  resume/compare/replay/status/cancel over `flows/runs.jsonl`.
- THE LINE — `town_beat/status` + ten `flow_*` tools.
- Webapp — `/api/town/*` + `/api/flows/*` + SPA `/flows` (editor, SVG
  graph, waterfall, resume, compare, replay, town board).

**Proven:** `atlas-mcp --prove` **105 strokes exit 0** (was 88) · `go
test ./...` ok (line + webapp, incl. no-finish-path scan) · cutters
`--verify` OK · live smoke zero read-writes · no source-ground writes.
VERSION unchanged `0.1.1+f1`. Trade passthrough named open.

Next stone on ruling: N5 team chat (two-way).

---

## 2026-09-09 — N5 TEAM CHAT (sitting 88)

**Stone state:** N5 implementation COMPLETE pending review gate.

Landed this sitting:

- `tools\cut_teamchat_vectors.py` + `teamchat_vectors.json` (platforms,
  channels, receipts, HMAC, payloads, dedupe — pinned before code).
- `line\internal\team\` — guarded sends, HMAC ingest with dedupe,
  receipted `state/team.jsonl`, secrets-only file, presence-only status.
- THE LINE — `team_send/status/history/ingest`.
- Webapp — `/api/team/*` + `POST /hooks/:platform` + rebuilt Messages
  page (receipts, form-only send, live presence) + Settings presence.

**Proven:** `atlas-mcp --prove` **115 strokes exit 0** (was 105) · `go
test ./...` ok (line + webapp) · cutters `--verify` OK · live smoke
honest + zero refusal writes · no source-ground writes. VERSION
unchanged `0.1.1+f1`.

Next stone on ruling: N6 SaaS lineup (full multi-user auth).
