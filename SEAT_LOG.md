# SEAT LOG — ATLAS working folder

*Append-only. Dated. Everything about the atlas build stays in this folder;
the source grounds (`Archive\estate`, `Archive\secondbrain`) are read-only.
The operator's founding rulings live in `CHARTER.md`; progress state lives in
`STATE_OF_BUILD.md`; this log witnesses what each seat landed, broke,
repaired, and learned.*

---

## 2026-08-24 — P0 GROUNDWORK: the dictionary landed

- **The ruling that widened the wall:** the operator ordered the whole
  project recreated as a polyglot system (Rust / Go / C++ / TypeScript /
  JSON / SQLite) reconciling `estate\` and `secondbrain\`. Four rulings
  banked before any code: best-fit per component · new folder in Archive ·
  strangler migration with golden-master parity · harvest the secondbrain
  patterns rather than port or wrap the repos. All four recorded in
  `CHARTER.md` §2–§3 with the wall-widening named plainly.
- **Scanned:** both grounds end to end — Steward 1.0 root + skills rack +
  heart sections; Neiro lib formats (`us_canon/us_chain/us_read/us_matrix/
  us_mcp/fold_us/prove_parity`), steward pkg (32 modules), neiro organs
  (43), proofs (18); Manjuel platform (~50 modules, 30-table SQLite),
  5.0 held heart; CARR T0–T8 (~70 modules); forge (:7375/:7374, links,
  bip340, manjuel_us, billboard worker, victor); builder engine; Agent
  Skills board; secondbrain's six repos inventoried and classified.
- **Landed:** `README.md` · `CHARTER.md` · `THE_CATALOG.md` (the dictionary:
  ~230 modules → 15 Rust + 25 Go + 6 C++ + 7 TS + 8 JSON + 7 SQLite
  artifacts, every row dispositioned PORT/ADAPT/WRAP/KEEP/HARVEST/FOLD) ·
  `SEAT_LOG.md` (this file) · `specs\` (seven frozen references: chains,
  canon, .us, seam, sqlite, mcp surface, command map) · `ACCEPTANCE.md`
  (testable sheet, stone-by-stone proven modes) · `STATE_OF_BUILD.md`
  (append-only progress) · `data\master.db` seeded from THE_CATALOG via
  `tools\seed_catalog.py` (re-runnable, idempotent).
- **Env law honored:** no `.env` present beside this ground (checked
  2026-08-24); absence noted honestly.
- **Not done on purpose:** no Rust/Go/C++/TS code exists yet — P0 stops at
  documents + catalog seed, per the plan's review gate. No git history
  created (never commit without the operator's word).
- **Open for the operator:** review THE_CATALOG dispositions (esp. §7
  KEEP/FOLD lines and the G8 aurora strangler path); rule whether THE_ROAD
  gets an atlas pointer-stone appended; name any renames (folder is
  `atlas` by working choice).
- **Lesson for the next seat:** the four chain FORMS are discoverable only
  by trial today (`prove_parity.py` FORMS table); A1 must cut test vectors
  from the live chains BEFORE writing `canon.rs`/`forms.rs` assertions, or
  the golden masters will lie.

---

## 2026-08-25 — P0 REPAIR SITTING (sitting 2): the record reconciled

- **Wake:** line + handoffs read; atlas-local law applied (the steward-line
  MCP serves the Steward 1.0 folder; this ground is governed by its own
  charter/log/state docs). No `.env` beside this ground (re-checked).
- **The finding that mattered:** `CHARTER.md` had been overwritten
  2026-08-24 ~15:01 with a byte-copy of `specs\SPEC_COVENANT.md` v2 — no
  witness entry covers the edit; P0-01 had silently regressed. Found by
  cross-checking content against mtime against the append-only records.
  Recovery needed no invention: all five ruling bodies survive in
  `master.db.rulings` and the seeder constant; wall-widening survives in
  this log's sitting-1 entry.
- **Rulings banked at the gate before any edit** (operator's word): repairs
  only, then re-stop at his gate · CHARTER restored from record · catalog
  corrected via errata appendix (rows never rewritten) · toolchains
  installed by the operator's own hand between sittings (cargo/go/g++
  absent on this box; node present).
- **Landed:**
  - `CHARTER.md` restored — §1–§6 per witness inventory (founding rulings
    verbatim from seed record; wall-widening; standing laws; versioning;
    §6 build discipline), restoration sources named in its header,
    overwrite incident folded into a dated addendum. Identity law lives
    solely at `specs\SPEC_COVENANT.md`.
  - `THE_CATALOG.md` — ERRATA appendix appended: R9 corrected to
    construction-A/declared-order, House `151274…5bbb` default, Elder
    `65118a…9dd9` legacy-only behind `--epoch elder`; G2 source_lines was
    bytes-not-lines (19,133 B = **453 lines**, measured against the real
    `estate\Steward 1.0\door.py`, read-only).
  - `tools\seed_catalog.py` — R9 notes + G2 lines constants trued;
    `--reset` reseed (P0 scratch allowance) → **VERIFY OK, rulings=5,
    catalog=73/73**, WAL on; trued rows confirmed by read-only query.
  - `ACCEPTANCE.md` — A1-07 folded → **A1-07a (House)** / **A1-07b
    (Elder)** per SPEC_COVENANT prove requirements; P0-04/P0-06 annotated
    (eight spec files; `.venv` expected); original row text preserved in a
    new append-only Amendments section.
  - `STATE_OF_BUILD.md` — repair block appended below.
- **Untouched:** all seven other frozen specs (none needed edits —
  SPEC_COVENANT was already correct; the drift lived in the catalog and
  acceptance sheet); `data\master.db` beyond the documented reset-reseed;
  both source grounds (read-only walks only: one line/byte count of door.py).
- **Open for the operator:** rule A1 open or hold (fixtures-first order per
  the sitting-1 lesson when it opens); toolchain installs on your side
  before any Rust compiles; name any renames still pending.
- **Lessons for the next seat:** (1) an unwitnessed doc overwrite is found
  by triangulating content × mtime × the append-only records — trust the
  records over the file when they disagree, then reconcile through the
  fold law. (2) The seeder's INSERT OR IGNORE means constant edits never
  touch existing rows; truthing requires the documented P0 --reset while
  master.db holds no record of weight — after A1 lands, corrections ride
  forward migrations only. (3) Measure, don't assume: the 19k "lines" was
  bytes; one read settled it.

---

## 2026-08-25 — A1 step 1: the golden masters are cut (sitting 3)

- **Gate ruling received:** "perform step 1." Fixtures-first executed
  exactly as banked; VERSION now `0.1.0+a1`.
- **Discovery first:** ~250 JSONLs live across the estate; most are attic
  mirrors or reading corpora. The cutter takes exactly the SPEC_CHAINS
  named set (21 slugs) plus the two identity epochs — scope discipline over
  completeness; everything else recorded as deferred in the manifest.
- **Landed:** `tools\cut_fixtures.py` + `tests\fixtures\` (21 chains full
  or windowed, 73 sample vectors, house five docs + elder four docs +
  both anchors). MANIFEST.json = the frozen reference sheet: sha256 per
  source, entry counts, body_v distributions, wrap line-indexes, form
  hints labeled hints.
- **The stroke that matters:** construction-A reproduced BOTH covenants
  from the living grounds on the first run — House `151274…5bbb`,
  Elder `65118a…9dd9`. The identity spec's derivation section is now
  witnessed fact, not frozen prose. A1-07a/b have their golden material.
- **Proven:** independent fidelity pass 94/94 byte-exact; manifest
  self-consistent; sources untouched throughout (reads only).
- **Defects paid:** one init typo in the cutter (dict where list belonged),
  caught by the very first execution, fixed, re-run clean.
- **Open for the operator:** install cargo/rustc when ready — step 2 (Rust
  workspace scaffold + `--version` seam) starts the moment toolchain lands.
  Nothing else blocks.
- **Lesson for the next seat:** the manifest's `form_hint` is a navigation
  aid, never an oracle — commons_board reads "unknown" precisely because
  recognition belongs to the trial-running prover (SPEC_CHAINS), and the
  Rust forms.rs must meet these exact bytes, not the hints.

---

## 2026-08-25 — A1 step 2: first Rust blood, all green (sitting 4)

- The operator's toolchain had landed quietly (`~\.cargo\bin`, msvc host);
  scaffold executed same sitting as ordered.
- **Zero-dep ruling:** hand-rolled SHA-256 instead of the `sha2` crate so
  the provenance core builds anywhere with a bare rustup install, no
  network. RFC vectors green; incremental feeds match one-shot. Foldable if
  the operator rules for the crate.
- **The stroke that matters:** SPEC_COVENANT now proven in a second
  language from the SAME frozen fixtures — House and Elder constructions
  reproduce, intruders move nothing, a flipped byte names its doc. Python
  said it; Rust agrees; the fixtures bind both.
- Workspace shape: `core` (sha256/version + spec-cited stubs) · `store`
  (frozen DDL + append-only trigger law, driver deferred to A1-06) ·
  `apps\atlas` (binary whose --version is welded to the root VERSION file;
  unknown commands refuse with exit 2). 16 test strokes, exit 0; build
  clean; MSVC linker proved by the very first build.
- Defects paid: three compile/run catches (borrow type, parenthesized
  if-expression, manifest-dir path math) — none reached a witness claim.
- **Open for the operator:** none blocking. Step 3 (canon.rs vectors →
  forms/chain verdicts) opens next sitting at your word.

---

## 2026-08-25 — SESSION CLOSE: before / after (sittings 2–4, one session)

*The operator ended the session; this entry is the whole delta, so the next
seat can see in one place what this session changed.*

### BEFORE (session open)

- P0 complete but parked at the review gate; nothing built.
- **CHARTER.md silently overwritten** (08-24 ~15:01) with a byte-copy of
  `specs\SPEC_COVENANT.md` v2 — founding rulings gone from their cited
  home; P0-01 regressed unwitnessed.
- THE_CATALOG R9 stale against the two-epoch spec (sorted-docs construction,
  elder-only mark); ACCEPTANCE A1-07 covered Elder only; P0-04/P0-06 drifted
  (7 spec files vs 8; .venv unaccounted).
- G2 catalog row stored door.py's BYTES (19,133) in the lines column.
- `VERSION = 0.1.0+p0`; no code artifacts; no test fixtures; no git.
- Toolchain state unknown/absent-on-PATH; master.db carried the only
  surviving copy of the five ruling bodies.

### AFTER (session close)

- **Record reconciled:** CHARTER restored §1–§6 from the held record with
  sources named and the overwrite incident folded into a dated addendum;
  THE_CATALOG gained an append-only ERRATA (R9 two-epoch correction; G2 =
  453 lines); seeder constants trued and master.db reset-reseeded — VERIFY
  OK, rulings=5, catalog=73/73, WAL on; ACCEPTANCE amended A1-07a/b with
  the original text preserved and P0-04/P0-06 annotated.
- **Gate ruled through:** repairs accepted → "perform step 1" → "step 2".
- **Golden masters cut (A1 step 1):** `tools\cut_fixtures.py` +
  `tests\fixtures\` — 106 files / 788 KB: 21/21 SPEC_CHAINS-named chains,
  73 single-entry vectors, House five docs + Elder four docs + both
  anchors; MANIFEST.json freezing sha256/stats per source. Fidelity proven
  94/94 byte-exact. Both covenants reproduced Python-side on first run.
- **Rust spine stands (A1 step 2):** workspace `core` / `store` /
  `apps\atlas`, ZERO external crates; hand-rolled SHA-256 (RFC vectors);
  --version seam welded to root VERSION (`0.1.0+a1`); store DDL law frozen
  verbatim. Build clean; **16 test strokes exit 0** — including covenant
  reproduction in a second language from the same fixtures, intruder
  immobility, flip-names-doc. Binary refuses unknown commands exit 2.
- **VERSION → `0.1.0+a1`.** Toolchain found present after all
  (`~\.cargo\bin`, rustc 1.98.0 msvc) — installed by the operator between
  sittings, exactly as ruled.
- Witnesses appended for every sitting (STATE_OF_BUILD blocks 2–4, entries
  in this log); no source-ground writes anywhere; no git history created.

**Seals at stand-up:** `cargo test --workspace` 16/16 exit 0 · seed
`--verify` OK · fixtures pinned · VERSION consistent everywhere.

**Next stone:** A1 step 3 — canon.rs against the BODY_V vectors, then
forms.rs recognition-by-trial and chain.rs FLIP/TAMPER verdicts, every
assertion meeting the frozen fixture bytes. Opens at the operator's word.

**Standing lesson:** the record beats the file when they disagree — this
session found a lost charter in a database and proved a covenant twice over
from bytes nobody had asserted against before.

---

## 2026-08-25 - A1 step 3: canon meets the oracle bytes (sitting 5)

- **Rulings banked at stand-up:** JSON parsing hand-rolled like SHA-256
  before it (zero external crates standing); scope canon-only, stop at
  review gate once A1-01 proves.
- **Vectors cut BEFORE assertions (law held):** tools\cut_canon_vectors.py
  forged over the read-only oracle estate\Neiro\lib\us_canon.py - 89 cases
  / 356 form-vectors (16 synthetic + all 73 live samples x forms 1/2/3 +
  unknown-form stroke); 250 outputs, 106 named refusals (float x12,
  int_range x5, unknown_body_v x89). Deterministic on content (no wall
  clock; oracle sha256 carries provenance); --verify green twice.
- **Probe named the risks first:** 11 floats in live samples and six
  ~77-digit BIP-340 sig components beyond i64 in custody. Neither coerced:
  json.rs landed hand-rolled (last-key-wins like json.loads, surrogate
  folding, named refusals, depth cap 256, Json::Big digit-verbatim);
  canon.rs filled its stub (V1/V2 reproduction incl. CPython-repr float
  writer; V3 JCS UTF-16-be order, minimal escapes, safe-int bounds;
  CanonRefused {Float, IntRange, UnknownBodyV}).
- **Proven:** all 356 oracle vectors met byte-for-byte on FIRST full
  contact; workspace now 28 strokes exit 0 (was 16). Binary seams hold:
  --version exit 0, refusal exit 2. VERSION unchanged at 0.1.0+a1.
- **Defects paid en route:** two jcs_write match arms returned Err where
  unit was owed (compile caught); cutter source rewritten backslash-free
  after transport-level escape mangling.
- **A1 state:** steps 1-3 DONE; A1-01 closed. Step 4 next: forms.rs
  recognition-by-trial + chain.rs FLIP/TAMPER verdicts (A1-02/A1-03).
  Opens at the operator's word.

**Seals at close:** vectors --verify OK x2 . cargo test --workspace 28/28
exit 0 . VERSION consistent . no source-ground writes.

**Standing lesson:** cut the oracle's answer before writing the code that
must match it - the probe turned floats and bignums into design choices
instead of midnight debugging.

---

## 2026-08-25 - A1 step 4: forms named, verdicts mirrored, live walk taken (sitting 6)

- **Golden verdicts cut BEFORE Rust (law held):** tools\cut_chain_verdicts.py
  forged over BOTH read-only provers - us_chain.verify (EMPTY/INTACT/FLIP/
  TAMPER) and prove_parity.read_chain (recognition-by-trial over 13 named
  constructions + separate weld walk): 21 fixture chains x 2 provers, plus
  EIGHT injection recipes run on temp ground (flip/drop/truncate/corrupt x
  two representative chains). Deterministic; --verify green twice.
- **Oracle crash found and recorded, not patched:** us_chain.verify dies on
  hash-less rows (prev[:12] TypeError) - three chains carry them (commons
  board/snapshots/custody). Cutter guards with a NAMED skip preserving the
  fact; the Rust test asserts the same ground truth independently.
- **Landed:** core\src\forms.rs - the 13-form table verbatim in oracle order
  (board V1/V2 whole 16, links projected V1/V2/V3-16, harvest bare 16,
  envelope body 64, whole 64, JCS projected/whole); quirks pinned not fixed
  (zero-match reports the FIRST form name with matched=0). core\src\chain.rs
  - byte-faithful verdict mirror: weld follows STORED hashes (the whole
  FLIP/TAMPER separation), CanonRefused mid-walk -> TAMPER at that entry,
  unparsable line -> TAMPER 'line is not JSON'.
- **Proven:** all 42 golden records met (21 chains x parity+verify, 8
  injections re-applied on fresh temp copies); direct A1-03 strokes asserted
  - FLIP names entry #1 and stays appendable, TAMPER locates the break and
  refuses append, truncation reads INTACT as a lawful prefix. Workspace now
  **41 strokes exit 0** (was 28).
- **The binary grew its seam:** tlas chain verify|recognize (<path> |
  --roots <dir>). Live estate walk end to end: steward_ledger 2062/2062,
  jesster gen4 1246/1246, neiro 361/361, skills board 62/62 bare-16 -
  every READABLE chain fully matched under its named form; agents_seatlog
  verifies INTACT live under the real prover semantics. Walk exits UNSOUND
  naming exactly six chains no known form can read (three hash-less, four
  ops/trade zero-match - keyed/blake territory SPEC_CHAINS defers to R12/S7
  stones). Reported, never explained away - the oracle's own law.
- **Defects paid en route:** two missing .collect() and one format! brace
  (compile caught); a test premised removal on a two-entry chain where
  truncation is a legal prefix - the very lesson the seatlog drop-golden
  had taught hours earlier, re-learned in Rust.
- **A1 state:** A1-01/02/03/05/07a/07b closed. Remaining: A1-04 (export
  round-trip) and A1-06 (store journal-sync driver) - both need a real
  SQLite story, which is an operator ruling: vendored amalgamation, an
  admitted crate, or deferred. The gate is reached.

**Seals at close:** chain_verdicts --verify OK x2 . cargo test --workspace
41/41 exit 0 . live --roots walk witnessed . VERSION unchanged 0.1.0+a1 .
no source-ground writes .

**Standing lesson:** mirror the prover, not the idea of the prover - the
oracle's crash on hash-less rows and its first-form-name quirk are both now
pinned behavior, because the goldens were cut from what Python DOES.

---

## 2026-08-25 - A1 step 5: the store stands; A1 complete (sitting 7)

- **Rulings banked:** SQLite via the SYSTEM winsqlite3.dll (Option A - zero
  crates.io, zero downloads, zero compiler); Merkle proof-walk IN scope;
  export trio approved (agents_seatlog / forge_links / steward_ledger.head46).
- **Spike witnessed:** 26/26 probed symbols present, libversion 3.51.1
  (>= the 3.50.4 that wrote data\master.db). Windows Kits ships
  um\x64\winsqlite3.lib, so the seam is a plain static #[link].
- **Landed:** store\src\ffi.rs (raw seam) . driver.rs (RAII Conn/Stmt;
  connection law APPLIED AND OBSERVED - wal/full/fk/timeout) .
  migrations.rs (frozen DDL verbatim, forward-only registry, append-only
  triggers on the MIRROR; chains is derived and mutable by definition) .
  core\src\merkle.rs . sync.rs (all six sync rules as named code) .
  import_export.rs (two-door admission law) . atlas db
  init|import|export|status seams, unknown verbs refused exit 2.
- **FINDING OF THE SITTING - three Merkle dialects on one ground:** the
  Jesster library wraps (no mv stamp) reproduce under NEITHER us_chain tree:
  their writer forge\links\links.py hashed HEX TEXT concatenations (its own
  _h), a third tree. Probed first, then pinned: all EIGHT closed roots
  (gen2 x3, gen3 x4, gen4-head46 x1) reproduce under links-v1-text AND climb
  by path alone. merkle.rs grew the named tree + verify_wrap_root trial:
  stamped mv=2 verifies only under the separated tree; absent mv tries the
  two historical v1 dialects and NAMES which reproduced. kimi's kind='wrap'
  rows carry no root/window - harvest verdicts wearing the name; skipped as
  such.
- **A1-04 proven:** trio round-trips BYTE-IDENTICAL, including CRLF
  fidelity - the steward ledger was written with \r\n line endings and the
  mirror stores raw segments verbatim (a re-serialised canon would have
  silently rewritten history's spacing).
- **A1-06 proven hermetic:** WAL=wal + synchronous=full + FK ON observed
  through FFI; triggers refuse UPDATE/DELETE by name; record-first refusal
  leaves the DB byte-for-byte unchanged; crash-window healed by replay-on-
  open, second replay a no-op; refuse-on-break opens read-only carrying the
  why; PASSIVE checkpoint + consistency walk after any wrap crossing.
- **Cross-version stroke:** Rust opens a COPY of Python-written master.db
  read-only: catalog 73, rulings 5, journal_mode=wal.
- **Defects paid en route:** sqlite_master.name (not table_name);
  PRAGMA synchronous answers an INTEGER (normalized to words at the law);
  FK ordering inverted until replay seeded its parent row inside the txn;
  import learned TWO lawful doors after the V3-world prover necessarily
  reads unstamped projections as all-flip (the golden cut had already
  witnessed exactly this).
- **A1 COMPLETE - every row closed (01..07b).** Stopped at the operator's
  review gate. Next stone: A2 (the Registry) opens at your word.

**Seals at close:** cargo test --workspace 65/65 exit 0 . live db lifecycle
smoked through the CLI . VERSION 0.1.0+a1 unchanged . no source-ground
writes .

**Standing lesson:** the ground outruns the spec's vocabulary - three Merkle
trees wore one name, and only recognition-by-trial with NAMED verdicts keeps
them honest. Cut from what IS, never from what the spec assumed.

---

## 2026-08-25 - A2: the household is named (sitting 8)

- **Rulings banked:** manjuel5.us STRICKEN by operator ruling - folded to
  attics (estate 5.0 + .secondbrain mirror), excluded from every golden set
  permanently; the lawful .us census is FOUR tool-born declarations, so the
  byte-round-trip law now holds universally with no exception case. tlas
  agent enroll lands the verb; atl wraps it at C1. Roster folds from the
  HOUSE world first.
- **Goldens before Rust (law held):** tools\cut_us_vectors.py over the
  read-only oracle (us_read.py, sha pinned) - parse+render bytes for all
  four files, a 14-stroke refusal battery stored as INPUT BLOCKS + named
  classes (never Python error text), document-level failure shapes keyed
  structurally, seven derive_tools folds incl. what they lose. Deterministic;
  --verify green.
- **Landed core\src\us.rs** - exact mirror: line-scanned fences (unknown tag
  stays prose), stem law, THE GATE (can_approve absent/true both refused),
  declaration/roster/derive_tools/render. Oracle quirk honored: 'ask' still
  GRANTS the tool - the fold carries it and reports the lost gate.
- **A2-01/02 PROVEN on first contact:** us_parity.rs drives all goldens -
  parse parity x4, BYTE round-trip x4, refusal classes on identical inputs,
  loss reports verbatim.
- **The household folded:** tools\fold_agents.py emits 37 single-seat
  declarations through the ORACLE'S OWN render (born canonical) + four
  household maps under modules\. Sources cited per seat: TWELVE TRIBES
  offices quoted from LAW_002; four council personas; ten lineage actors
  from the sitting-8 chain census; operator + opencode; seven doctrine
  seats. Even the operator's row carries can_approve:false - approval lives
  outside the registry.
- **A2-03 PROVEN:** store\src\enroll.rs - enrollment law beyond validate:
  covenant cited, reports_to resolvable in the declared universe; INSERT
  into master-copy agents (CHECK=0 backs the door); idempotent re-runs;
  dry run = BEGIN/ROLLBACK (a real txn answering to rollback - the only
  trustworthy would-list); undeclared actors refused context BY NAME.
- **A2-04 PROVEN:** orient_home assembles standing law + LINE (AGENTS.md)
  + ROAD (THE_ROAD/STATE_OF_BUILD) + LOG TAIL (40 lines) under the 60k cap,
  refusing honestly when pieces are absent; proven live against the
  demo-vault Manjuel home (21,774-byte pack). CLI: atlas agent enroll /
  atlas orient --home.
- **Defects paid en route:** agents.us_path UNIQUE was the P0-frozen law -
  one agent per file all along (fold restructured to single-seat units);
  dry-run originally skipped BEGIN but still stepped INSERTs (autocommit
  landed rows - replaced by real-txn-then-rollback); 'ask'-grants quirk
  caught by our own stroke disagreeing with an assumed expectation.
- **A2 COMPLETE pending review gate:** operator spot-checks five
  declarations against observed behavior. Workspace: **77 strokes exit 0**
  (was 65). VERSION unchanged 0.1.0+a1.

**Seals at close:** us_vectors --verify OK . fold --verify OK . live enroll
lifecycle smoked (dry/real/idempotent) . live orientation pack witnessed .
no source-ground writes beyond the ruled manjuel5 strike .

**Standing lesson:** the registry's shape came from the record twice over -
the frozen DDL dictated one-seat-per-file, and LAW_002 dictated the roster.
When law and convenience disagreed, law moved first and the tooling bent.

---

## 2026-08-25 - A2 gate rulings + B1 genesis law (sitting 8, part 2)

- **Operator ruled at the five-declaration spot-check:**
  1. 'i am the approval' - operator.can_approve stays false because approval
     lives in the hand alone; the registry never held it to give.
  2. The circle: operator reports_to manjuel; manjuel reports_to operator.
  3. 'manjuel is in charge unless i say otherwise, like my serf' - delegated
     charge, absolute override. Execution flows through manjuel, who acts as
     the operator and answers by ruling and judging (operator bash stays
     deny BECAUSE manjuel executes as him).
- **Folded and proven:** fold_agents.py amended, re-folded byte-canonical;
  fresh master-copy enrollment 37/37 zero refusals; circle verified in the
  record (operator->manjuel->operator, both can_approve=0).
- **B1 GENESIS LAW (operator):** the MCP is MULTI-TENANT from birth - it
  holds ALL of the estate, every project a first-class tenant, no single-
  seat worldview. SPEC_MCP's --home selection is superseded by a tenant
  registry derived from the declarations themselves; tools take a project
  selector. Go toolchain reported installed by the operator.

---

## 2026-08-25 - B1 opened: THE LINE stands multi-tenant (sitting 9)

- **Genesis law (operator):** the MCP is MULTI-TENANT from birth - one door
  carrying ALL of the estate, every project first-class, no single-seat
  worldview. SPEC_MCP's --home selection superseded by a tenant registry;
  tools name their ground.
- **Toolchain:** go1.26.7 windows/amd64, installed by the operator between
  sittings. VERSION bumped 0.1.0+b1 (a2 rode a1's tag by oversight - paid
  and pinned here).
- **Scaffolded line\\ (Go, stdlib-only):**
  internal\\tenant - the registry: case-insensitive names, default tenant,
  strangers refused BY NAME (enrollment law carried into transport);
  internal\\orient - per-tenant orientation pack (standing law + LINE +
  ROAD + LOG TAIL under the 60k cap), port of A2-04 generalized;
  internal\\tools - the surface: get_in_line / verify_chain (SPEC_SEAM
  subprocess contract -> atlas.exe) / muster LANDED; eleven later-stone
  tools named but refusing HONESTLY until their stones open; forbidden
  verbs absent by construction;
  internal\\protocol - newline JSON-RPC, protocol 2025-06-18, handshake
  carries parity instructions;
  cmd\\atlas-mcp - flags --prove/--describe/--version/--tenant k=v
  (repeatable)/--default-project/--atlas-bin; --go:embed VERSION seam.
- **PROVEN (13 strokes exit 0, shipped --prove):** handshake speaks the
  protocol and carries the standing law . surface >=14 tools, forbidden
  absent . MULTI-TENANCY: same tool, three temp grounds, three different
  truths, each pack labeled with its tenant . default serves unnamed .
  stranger refused by name . muster rolls all . remember refuses honestly .
  60k cap holds . case-insensitive tenancy . empty registry resolves
  nothing. go test ok; binary smoke: --version prints 0.1.0+b1 exit 0,
  unknown verb refused exit 2.
- **Rust suite re-sealed:** version pin updated to b1 (the pin did its job -
  it caught an unlogged bump). Workspace 77 strokes exit 0.
- **B1 state:** foundation landed; next sittings land the remaining tools
  for real (read_handoffs/doctrine/wall/matrix/ask_steward/remember with
  receipts + the one-writer ask lock), then B1-01..04 close.

**Seals at close:** go build+test+prove green . rust workspace green .
VERSION 0.1.0+b1 everywhere . no source-ground writes .

---

## 2026-08-25 - sitting 9 addendum: atlas orients itself

- AGENTS.md + THE_ROAD.md landed at repo root (the orientation door we sold
  to everyone else now accepts our own home: 16,938-byte pack, exit 0).
- THE_ROAD carries the full build path: NEXT = finish B1's eleven tools
  (receipts/doctrine/wall/matrix/ask_steward under the one-writer lock,
  DONE-MEANS per row), then C1 faces -> D1 town -> D2 trade+door ->
  E1 kernels -> F1 harvest -> G cutovers; PARKED items named.

---

## 2026-08-27 - B1 closed: THE LINE carries the household (sitting 10)

- **Rulings banked (operator Q&A, carried from B1 genesis):** neiro is the
  ONLY auto-carry tenant — Home from `NEIRO_HOME` (default const empty;
  operator-set). atlas NOT auto-carried (deferred to the build plan). Every
  other tenant by `--tenant name=path` + `--engine name=cmd`. Per-tenant
  record-map manifest (`line.manifest.json`) maps the logical keys
  line/road/state/log/doctrine/plans/wall; absent key = rigid default.
  ask_steward wired via `line/engine/manjuel_ask.py` mirroring manjuel's
  `_RUNNER` (conscience.wake() + skills.invoke("weigh")); honest refusal when
  unwired. remember writes `<Home>/state/remembered.jsonl`, testimony-stamped,
  under the ask lock.
- **LATENT FINDING (manjuel build):** the current manjuel engine changed — it
  now requires `conscience.wake()` (the heart in its own process) before
  weigh; the classic entry point was the native `seat_mcp.py` `_RUNNER`, not
  the core. The atlas adapter mirrors the `_RUNNER` exactly and never edits the
  read-only secondbrain/estate grounds.
- **neiro RECORD MAP (carried law):** Doctrine + foundation carry the law at
  `estate\Doctrine\` + `estate\foundation\`; handoffs at `estate\shelf\journal\`.
  The neiro ground itself (`estate\Neiro\`) carries no THE_ROAD/SEAT_LOG/
  doctrine — those resolve to the estate roots. The neiro manifest is authored
  by the operator in the estate ground; atlas only reads it.
- **LANDED tools (8 now real, not refusing):** read_handoffs (SEAT_LOG whole +
  sha256 receipts; manifest may remap 'log' to a dir) · list_doctrine /
  read_doctrine (carried law by name, absent name denied honestly with the
  named why) · check_the_wall (judges a path; INSIDE / REFUSED quoting THE
  WALL) · state_matrix (fold(record) index) · read_plan (HLD/LLD/road/catalog/
  acceptance/charter by the manifest 'plans' key) · ask_steward (engine
  subprocess under the ask lock; honest refusal when unwired) · remember
  (testimony-stamped append under the ask lock). rack_list / rack_ask /
  rack_open stay HONEST refusals until F1 — a receipt that fabricates is worse
  than none.
- **tenant model:** internal/tenant gained Manifest + Engine; Default prefers
  neiro; manifest-aware LinePath/LogPath/RoadPath/StatePath/RoadCandidates/
  DoctrineDirs/PlanPath/WallRoot. orient generalized over tenants, degrades
  gracefully (named absence, not refusal) — neiro's standing law still carries.
- **PROVEN (shipped --prove):** strokes grew 13 -> 23, all exit 0. Augmented:
  read_handoffs receipt matches disk · list/read_doctrine honest denial
  (B1-03) · check_the_wall inside/outside quoting the law · state_matrix folds
  · read_plan returns a plan with sha · ask_steward honest refusal when unwired
  + routes through the wired (stub) engine under the ask lock · manifest
  remaps handoffs to a dir · B1-04 one-writer lock: 8 concurrent remember
  calls serialize, chain INTACT (8 JSON lines, all parse). Surface holds 14
  tools; forbidden verbs (approve/ascend/merge/commit/push/delete/reject/
  promote) absent by construction (B1-02).
- **Seals at close:** go build+vet clean · go test ./... ok · atlas-mcp
  --prove 23 strokes exit 0 · cargo test --workspace 77/77 (no Rust change,
  regression-free) · VERSION unchanged 0.1.0+b1 · no source-ground writes.

**Standing lesson:** the door is the household, not a seat — every tool names
its ground, strangers get nothing, and one writer at a time keeps each
tenant's chain intact.

---

## 2026-08-27 — B1 hardening + B2 THE MESH spec (sitting 11)

- **Ruling carried (zero-write law):** atlas folds the estate grounds; it must
  never boot or forward to them. The manjuel build's `Steward().awaken()` writes
  to secondbrain state — triggering it from the MCP would violate the read-only
  law. `toolAskSteward` now refuses any engine command whose tokens resolve into
  estate/, secondbrain/, or manjuel core, by name. `manjuel_ask.py` left
  untouched (operator: "don't touch yet").
- **B1 hardening proven:** shipped `--prove` 23 -> 24 strokes exit 0 (new
  stroke refuses an engine reaching a read-only ground). go build/vet/test green;
  Rust suite 77/77 unchanged.
- **B2 THE MESH opened, spec-first:** the operator ruled the mesh is atlas's
  secure internal messaging fabric (operational half of `.us`), and that the
  confidentiality model is ciphertext at rest + a SOVEREIGN deciphering ledger —
  the paper cypher is 2FA to unlock once/day (not 35 typing rounds); per-agent
  keys live in `.env`; security lives in admin/orchestration, not the internals.
- **Landed:** `specs/SPEC_US_MESH.md` (envelope = the proven links-chain entry;
  five security guarantees; deciphering-ledger model) · `tools/cut_mesh_vectors.py`
  (8 goldens cut from the read-only oracle `forge_links_chain.jsonl`; --verify
  PROVEN 8/8). Goldens: chain INTACT / FLIP / TAMPER / mark-welded / confidentiality
  / auth-refuse / wall-refuse / egress-refuse.
- **B2 state:** SPEC-FIRST COMPLETE. Implementation (mesh_* tools over THE LINE,
  the deciphering ledger) opens at the operator's ruling; version pins
  `0.1.0+b2` then.
- **Seals at close:** go build+vet clean · go test ./... ok · atlas-mcp --prove
  24 strokes exit 0 · cut_mesh_vectors.py --verify 8/8 · cargo test --workspace
  77/77 · VERSION unchanged 0.1.0+b1 · no source-ground writes.

---

## 2026-08-27 — B2 THE MESH spec corrected + executed (sitting 12)

- **Operator corrections received (three, each load-bearing — and each right):**
  1. **SEALED commitment was wrong.** The draft committed to `H(ct)` (the
     ciphertext). That neither hides a low-entropy message (`H("yes")` /
     `H("meet at 3")` brute-forces in milliseconds — a bare hash only hides when
     its input is unguessable) nor verifies on reveal (you'd need the key + nonce
     to reproduce `ct`). Fix: commit to `H(salt ‖ plaintext)`, `salt` = 32 random
     bytes stored beside the message in the estate and revealed with it. Hides
     low-entropy plaintext; the reveal recomputes and verifies. Hooke's anagram,
     as `links.py` SEALED intends.
  2. **"Go stdlib Schnorr port" does not exist.** Go stdlib has ecdsa/ed25519/
     ecdh — no secp256k1, no Schnorr. So atlas signs with secp256k1 Schnorr
     **hand-rolled in Go (zero crates)**, byte-for-byte with `jesster.py`. That
     is a *second* hand-rolled impl; the acceptance row is a **differential
     Py↔Go vector set** (sign Py→verify Go, sign Go→verify Py, over the fixture
     chain incl. malleability edges) — not "the port passes its own tests."
  3. **Live endpoints as oracles break the hermetic law.** `cut_mesh_vectors.py`
     must not reach `manjuel.us`/`api.manjuel.us`. The live chains were folded
     into `tests/fixtures/chains/` ONCE (cut 2026-08-25); each golden now pins
     the fixture `sha256`. Live re-fetch is a SEPARATE optional drift stroke,
     never in `--verify`.
- **Rewrite executed (spec-first, corrected):**
  - `specs/SPEC_US_MESH.md` — three-system distinction made explicit (manjuel.us
    = operator BLAKE3 ledger; estate `manjuel` engine; `jesster` = keygen; signing
    is jesster's, never `keys.py` whose asymmetric path is parked). Envelope
    unchanged shape but signing now correctly described as hand-rolled Go Schnorr
    with differential acceptance; SEALED = `H(salt ‖ plaintext)`; the gate is
    **structural** (refused verbs ABSENT, wall = tenant isolation, cypher = root,
    breach logged on-chain) — NOT "security in orchestration." Transport = live
    websocket (estate-internal) + ledger truth + channel-head chain; surfaces =
    Aurora (view/verify), `api.manjuel.us` (read-only 405), `manjuel.us` (PaaS),
    atlas (SSM, writes on the estate with the cypher).
  - `tools/cut_mesh_vectors.py` — extended **8 → 15 goldens**, all hermetic, all
    local: added signing-model (sig/pub outside body; mark welds) · cross-impl
    (two walkers agree) · one-pen (per-actor + channel-head, zero forks) · marks
    weld (covenant `65118a147dd49ed9` + foundation `2cee607d21696d63`) · reconcile
    kind · breach_attempt kind · mirror-readonly (write verbs 405). The existing
    confidentiality golden rewritten to the **salted** commitment. Each golden
    pins its fixture sha256; the tool touches no network.
  - `ACCEPTANCE.md` B2 section rewritten to 14 rows (B2-01..B2-14), with B2-07
    the differential Py↔Go signing acceptance and B2-13 the hermetic-oracle
    discipline.
  - **VERSION → `0.1.0+b2`** (root VERSION, line/VERSION, line/cmd/atlas-mcp/
    VERSION, core/src/version.rs assert) — the B2 stone is now open.
- **PROVEN:** go build+vet clean · go test ./... ok · atlas-mcp --prove 24
  strokes exit 0 · `cut_mesh_vectors.py --verify` **15/15 PASS** · cargo test
  --workspace **77/77** (version assert now `+b2`) · no source-ground writes.
- **B2 state:** SPEC-FIRST (corrected) COMPLETE + executed. Implementation
  (mesh_* tools, deciphering ledger, hand-rolled Go Schnorr with differential
  Py↔Go prove) opens at the operator's word.

**Standing lesson:** a spec correction from the operator is not a style note — it
is a doctrine. `H(ct)` would have shipped an insecure mesh; "Go stdlib Schnorr"
would have shipped a crypto claim Go cannot honor; live oracles would have broken
the hermetic law we just paid for. Cut from what IS and what the operator rules.

---

## 2026-09-03 — RULING BANKED: "1 then 2" (sitting 13 open)

- **Operator ruling received:** repair A2 first (the 37-pin vs 40-seat red), then
  continue into B2 implementation. Report-only pause lifted by the operator's
  "1 then 2".
- **Observed at stand-up:** `cargo test --workspace` red (2 enroll strokes);
  mesh goldens 15/15 PASS; Go `--prove` 24 strokes PASS; household 40 files,
  `data\master.db` holding 40 agents, no witness block yet for the 37→40
  estate-alignment fold. Repair opens first; B2 implementation follows on the
  same sitting only if the suite re-seals green.

---

## 2026-09-03 — A2 REPAIR landed (sitting 13, step 1)

- **The red and its cause (observed):** `household_enrolls...` pinned
  `files_read = 37` while `agents\*.us` holds 40; `dry_run_writes_nothing`
  assumed the temp copy starts empty while the live `data\master.db` it copies
  already enrolls all 40 — so the would-list came back empty. Both strokes
  copy the live DB, so both inherited its past instead of proving enrollment.
- **Folded, not patched over:** the 37→40 growth is the witnessed
  estate-alignment fold (`fold_agents.py` ESTATE_SEATS: analyst/courier/scout
  per `Archive\Agents\*.md` frontmatter + dispatcher prose, comment-dated
  2026-08-27; plan `estate\Agents\Plan\PLAN_THE_ESTATE_ALIGNED_20260827.md`;
  files re-folded 8/28; live DB enrolled to 40). `fold_agents.py --verify`
  confirms the 40 born canonical via the oracle's own render.
- **Landed:** `store\src\enroll.rs` tests clear the temp copy (`DELETE FROM
  agents`) before proving — temp ground only, live `data\master.db` untouched —
  and pin `files_read = 40`. The agents table carries no append-only trigger
  (triggers guard the chain mirror only), so the clear is lawful.
- **Proven:** `cargo test --workspace` **77/77 exit 0** (40 core + stores incl.
  3/3 enroll) · `fold_agents.py --verify` OK · mesh 15/15 still PASS · Go
  `--prove` 24 strokes still PASS · no source-ground writes.
- **Lesson:** a test that copies the live record must empty what it means to
  fill — otherwise it asserts history, not law. The version pin caught the
  unlogged bump last time; this time the count pin did.

---

## 2026-09-03 — B2-07 DIFFERENTIAL SIGNING landed (sitting 13, step 2)

- **Goldens before code (law held):** `tools\cut_schnorr_vectors.py` forged over
  the read-only oracle `estate\forge\links\jesster.py` (sha256 pinned
  `6b551aa…3707f4`; drift fails loud). Fixed keys/msgs only — never the machine
  secret, never the network. 9 vectors: determinism, 16× verify-accept,
  wrong-message / flipped-byte / s≥N / bad-length / infinity-pub / off-curve-pub
  refusals, certify round-trip + tamper refuse. `--verify` green.
- **Landed:** `line\internal\mesh\schnorr.go` — secp256k1 Schnorr hand-rolled in
  Go, stdlib only (`math/big` + `crypto/sha256`): affine dbl/add/mul, 64B x||y
  ser, `JESSTER|nonce|`/`JESSTER|chal|` domains exactly as the oracle.
  `schnorr_test.go` drives the golden JSON: Go re-signs all 16 cases
  byte-identical AND verifies them, refuses every edge, certifies both ways.
- **Proven both directions, explicitly:** Go verifies Python sigs 16/16; Go
  signs byte-identical to Python (deterministic, same inputs); a FRESH Go sig
  (priv=999, new message, never in goldens) verifies `True` under the real
  `jesster.verify` — run via transient `line\tmpcross`, removed after (tree
  confirmed clean). First-contact green on both sides.
- **Seals:** `go build/vet/test` ok (new `mesh` package tested) · `--prove`
  still 24 strokes PASS · mesh goldens 15/15 · schnorr 9/9 · cargo 77/77
  unchanged · fold OK · no source-ground writes.
- **Remaining on B2:** `mesh_*` tools over THE LINE (`mesh_post`/`mesh_read`/
  `mesh_chain`/`mesh_cite`/`mesh_enroll`), the deciphering ledger (sovereign
  cypher root + per-agent `.env` keys + session certs), a `--prove` stroke for
  the mesh, then the operator's review gate. Signing was the load-bearing half;
  the tools ride on it.

---

## 2026-09-03 — RULING BANKED: "continue the build plan" (sitting 14 open)

- **Operator ruling:** continue the build plan = B2 remainder (mesh_* tools +
  deciphering ledger + mesh prove stroke, then the review gate).
- **Standing constraints carried in:** envelope byte-compat with the estate's
  links chain (five-key body, `sha256(prev‖canon)`, sig/pub outside, mark weld);
  per-agent keys from process env only (never repo/disk); hermetic proves on
  temp ground; forbidden verbs stay absent.

---

## 2026-09-03 — B2 TOOLS LANDED: the mesh speaks (sitting 14)

- **Convention read before code (observed):** `links.py:_append` signs the hash
  HEX STRING (`jesster.sign(priv, entry["hash"])`, verified live: the 3 signed
  forge-fixture entries verify under Go hands with message = hash string);
  canon is `json.dumps(sort_keys, ensure_ascii=False)` (probe-cut, byte-pinned
  in test); SEALED commits `H(doc)` on the estate, corrected per spec to
  `H(salt‖plaintext)` for messages. No `agent check` verb exists on the Rust
  CLI — so mesh-local admission (`mesh_enroll` bindings) is the honest v1
  gate; the `.us`-registry cross-check is named open work, not invented.
- **Landed (`line\internal\mesh`, stdlib only):**
  - `envelope.go` — Python-compat canon (short escapes, raw UTF-8, sorted
    keys; floats REFUSED, canon.rs parity), `sha256(prev‖canon)`, entry
    build/parse/verify (weld → FLIP/TAMPER vocabulary kept; bad sig/unsigned/
    unwelded mark → FORGERY, never blessed INTACT).
  - `seal.go` — salted commitment + SHA-256-CTR-shaped stream cipher with a
    written HONESTY CLAUSE (auditable, not validated; Seal/Open is the seam).
    Keys from `MESH_KEY_<actor>` env only; no default key, ever.
  - `store.go` — members.json (key BINDINGS, conflicting pub refused),
    per-actor chains + channel-head chain (signed by the posting actor — no
    invented ssm actor), deciphering ledger (entry → salt + commitment).
    Domain-separated scalar/seal derivation; posting key must match the
    enrolled pub or it signs nothing.
  - Operator flow: pick 32B secret → `PubForSecret` → `mesh_enroll` → keep the
    secret in the local `.env`. Once-a-day unlock is procedural (env present =
    unlocked), stated not enforced.
- **Surfaced (THE LINE, all naming their ground):** `mesh_enroll`/`mesh_post`/
  `mesh_read`/`mesh_chain`/`mesh_cite` — writes under the ask lock; chan
  defaults to the caller project, anything else refused quoting the wall.
  Surface 14 → 19 tools; forbidden verbs still absent by construction.
- **Proven:** `--prove` 24 → **34 strokes exit 0** (10 mesh: enroll ×2, open
  post, INTACT walk, sealed post, reveal opens, unrevealed withholds,
  wall-refuse, auth-refuse, flip→FLIP) · `go build/vet/test` ok · mesh package
  7 tests green (incl. estate signatures + oracle canon bytes) · cargo 77/77 ·
  all six python cutters `--verify` OK · no source-ground writes.
- **Open before the gate:** `.us`-registry cross-check for mesh admission
  (needs a Rust query seam); wrap/Merkle closing at n=40 (entries carry n;
  no wrap has closed yet); websocket live transport (v1 = THE LINE tools).
  THE_ROAD snapshot update rides the review gate.

---

## 2026-09-03 — RULING BANKED: "continue" = B2 gate passed, C1 opens (sitting 15)

- **Operator ruling:** "continue", read as passage of the B2 review gate into
  C1 Faces. Standing note: the first "no" is law — if this reading is wrong,
  the operator's correction overrules and this sitting rewinds to B2 polish.
- **Gate accepted on the record:** SPEC_US_MESH (corrected) + sittings 13–14
  witnessed; seals at passage: `--prove` 34/34, cargo 77/77, all cutters green.
  B2 open items (cross-check, wraps, websocket) ride as named follow-ups, not
  blockers.

---

## 2026-09-03 — C1 FACES landed: byte-parity, bridge, atl (sitting 15)

- **Goldens before code (law held):** `tools\cut_faces_vectors.py` pins the
  oracle (`estate\Aurora\aurora\console.html` 43,852 B sha `1306985a…4388`;
  `game\sprites.js` 6,580 B sha `169f3ad8…8bde`; singularity: one `*.html`
  entry point, STOP law) AND builds `tests\fixtures\faces_ground/` (fixed
  keys/msgs/clock, jesster-signed) plus `faces_snapshot.json` (exact bridge
  bytes). `--verify` green.
- **Landed (zero npm packages — node + tsc only):**
  - `faces\console-v2\` — oracle bytes vendored verbatim (sha-confirmed);
    `flags.js` loader + empty `modules/` + MANIFEST pins. Served flags-off =
    oracle bytes exactly; flags-on = server injects the loader only.
  - `faces\bridge\bridge.ts` — read-only fold (no write export; ground bytes
    proven unchanged across snapshots); canonical JSON reproduces the cutter
    bytes exactly (BRIDGE GOLDEN MATCH).
  - `atl\cli.ts` — version/enroll+orient wrap/bridge snapshot/faces
    serve+check/lint/self-test (`--prove` alias); `atl\node.d.ts` hand-rolls
    the node surface tsc needs (@types/node is npm → refused, hand-rolled);
    `package.json` carries `type: module` only — no dependencies.
  - Cross-impl, both new directions: Go `Chain`+`Read` verify the
    Python-built golden ground INTACT (canon+hash+sig+mark); lint negative
    control proven (planted remote+eval caught, temp cleaned).
- **C1-02 substitution, stated plainly:** ACCEPTANCE says "visual diff"; there
  is no hermetic pixel renderer on this ground, so flags-off parity is proven
  at the byte level (served bytes == oracle sha) — stronger than visual,
  weaker than seen. The gate judges with eyes; the bytes already hold.
- **Observed, not ours:** root `node_modules/` + `package-lock.json`
  predate this sitting (no seat ran npm); lint exempts machine dirs
  (.venv/node_modules/target/.git), npm's ledger, and cutter-pinned fixtures
  by name — authored tree scans LINT CLEAN.
- **Lesson:** golden files must be written binary-mode — the cutter's first
  run smeared CRLF on Windows text mode and broke byte-parity until
  `write_bytes` pinned LF. Portability is a byte discipline, not a hope.
- **Proven:** `atl self-test` 9/9 · `tsc --strict --noEmit` clean · `atl lint`
  CLEAN · cargo 77/77 · `go build/vet/test` ok · `--prove` 34 strokes exit 0 ·
  all seven python cutters `--verify` OK · `atl --version` 0.1.0+c1 ·
  no source-ground writes.
- **VERSION → `0.1.0+c1`** (root + line + atlas-mcp + version.rs pin +
  atl cross-file consistency stroke).

---

## 2026-09-03 — RULING BANKED: "continue" = C1 gate passed, D1 opens (sitting 16)

- **Operator ruling:** "continue", read as passage of the C1 review gate into
  D1 Town (same standing as sitting 15: the first "no" is law and rewinds).
- **Gate accepted on the record:** sitting-15 witnessed; seals at passage:
  `atl self-test` 9/9, tsc strict clean, lint CLEAN, cargo 77/77,
  `--prove` 34/34, seven cutters green, VERSION 0.1.0+c1.
- **D1 per ACCEPTANCE:** beat posts REVIEW-gated trade tasks (`atlas-town
  --prove`, temp ground) · no auto-approve path (static self-check) · flow
  jitter (seeded stats, SystemRandom-grade entropy live) · dedup while open ·
  month-key patrol recurrence. Catalog: G3 town+trade_tasks+river/clock/
  chancery → `cmd/atlas-town` (Go, stdlib); G4 bob queue → durable claims.

---

## 2026-09-03 — D1 TOWN landed: the beat walks (sitting 16)

- **Goldens before code (law held):** `tools\cut_town_vectors.py` calls the
  oracle's OWN `candidates()` (read-only `trade_tasks.py`, sha pinned
  `0821ebcd…50c19e`) on a fixed sqlite+JSONL ground at fixed noon — 4 vectors
  (draft keys+titles verbatim incl. the em-dash, dedup, next-month re-key,
  quiet ground). `--verify` green. The Go port reproduces the decision bytes
  from the JSONL mirror.
- **ADAPT, stated once:** the oracle reads work orders from sqlite; Go stdlib
  has no sqlite, so the port reads the JSONL face (same logical rows). D2's
  trade-skill parity owns the sqlite books; town never writes the ops ground.
  Trade hash-chain verification rides D2 too — named, not claimed.
- **Landed (`line\internal\town` + `line\cmd\atlas-town`, stdlib only):**
  ops readers (missing book reads as empty, bad lines skipped — oracle
  guards kept) · `Candidates` decision-for-decision (month key, slug, vendor
  fallback, >=30d boundary) · board (tasks.jsonl + worked.jsonl, both
  append-only; exactly one status: review) · `Beat` (draft→seed→work→file;
  second cycle files nothing) · jitter (crypto/rand live, seeded prove
  stats, backwards window refused) · story/look thin over the mesh ground ·
  binary verbs beat/flow/story/look/prove (+--describe/--version). No resolve
  verb anywhere — absent by construction, and the static self-check
  (`TestNoApprovePath`, concatenation-aware like the oracle's own trick)
  fails the build if approve/ascend/done paths ever land. The check has
  teeth: it caught a `"open"` read literal mid-sitting, fixed by sourcing
  the field from the row.
- **Proven:** `atlas-town --prove` 11/11 exit 0 · town package 6 tests green
  (goldens byte-exact, REVIEW filing, dedup, jitter stats, static check) ·
  `go build/vet/test` ok incl. town prove-test pin · cargo 77/77 · `atl
  self-test` 10/10 (new binaries-consistency stroke) · tsc strict clean ·
  lint CLEAN · all eight python cutters `--verify` OK · no source-ground writes.
- **VERSION → `0.1.0+d1`** (root + line + both binaries + version.rs pin).

---

## 2026-09-03 — RULING BANKED: "continue" = D1 gate passed, D2 opens (sitting 17)

- **Operator ruling:** "continue", read as passage of the D1 review gate into
  D2 Trade+Door (first-"no"-is-law standing).
- **Gate accepted on the record:** sitting-16 witnessed; seals at passage:
  town `--prove` 11/11, town 6 tests green, go suite ok, cargo 77/77, `atl
  self-test` 10/10, tsc clean, lint CLEAN, eight cutters green, VERSION d1.
- **D2 per ACCEPTANCE (Go+Rust):** D2-01 trade parity (property/workorder/
  inspect/report proves vs golden masters, identical outputs incl. $ receipts)
  · D2-02 badge truth (`atlas-door --prove`, tamper flip → red names break,
  green when whole) · D2-03 crew forms sealed (phone-form writes on temp book,
  entries chained + witnessed). Catalog G2: door.py (:8080) → cmd/atlas-door;
  badge rewalks roster+audit+inspections+ledger via Rust verify. Language
  split, stated upfront: Rust owns the sqlite books (FFI seam proven in A1);
  Go owns serving the door. Ports never move (:8080).

---

## 2026-09-03 — D2 TRADE+DOOR landed: the books balance (sitting 17)

- **Goldens before code (law held):** `tools\cut_trade_vectors.py` replays the
  four skills' own scenario on temp ground — 15 command outputs (raw +
  time/hash/tmp-normalized) + chain stats + the scenario books copied byte-safe
  to `tests\fixtures\trade_books/`. The cutter caught its own leaks twice
  (HH:MM clocks, temp paths) and one real corruption (sqlite round-tripped
  through text — binary copy since). `--verify` green.
- **Parity method, stated (wall clocks differ, so byte-pinning outputs across
  runs is impossible):** normalized-shape equality (15/15) PLUS
  cross-verification both directions — Rust walks the oracle's committed books
  intact; the oracle walks Rust-written books intact
  (`tools\check_trade_parity.py` 7/7, dev-run + witnessed). Either direction
  alone would be "the port passes its own tests."
- **Landed Rust (`core\src\pyjson.rs`, `store\src\trade.rs` + FFI `real()`,
  `atlas trade` verbs):** third canon mode (CPython ascii dumps, 7 probe cases
  byte-exact incl. surrogate pairs) · four grammars verbatim (UTC clock + honest
  refusal-instead-of-traceback, both witnessed) · audit nests event under
  "event" exactly as the oracle · checklist storage keeps typed order (hashes
  stay order-free) so report output renders file order. The port found real
  divergences mid-sitting via failing tests (binary book corruption, key-order
  rendering) and fixed the code, not the goldens.
- **Landed Go (`line\cmd\atlas-door`, stdlib net/http):** page/search/answer
  with receipts, badge from the three chains (oracle's whole-rule), two crew
  forms writing only through `atlas trade` under a one-writer mutex, /badge
  text endpoint, loopback-only default. Two stated substitutions: loopback
  instead of all-interfaces (`--bind` is the operator's call); WO search
  receipts are audit-seal hashes, not opened dates. `--prove` 13/13 on temp
  book over real loopback, pinned in `go test`.
- **Proven:** cargo **82/82** (77 + pyjson 2 + trade 3) · `atlas-door --prove`
  13/13 · `go build/vet/test` ok · `atl self-test` 10/10 (binaries check now
  covers three) · tsc strict clean · lint CLEAN · all nine python cutters
  `--verify` OK · check_trade_parity 7/7 · no source-ground writes.
- **VERSION → `0.1.0+d2`** (root + line + three binaries + version.rs pin).

---

## 2026-09-03 — RULINGS BANKED: "continue" + "loopback is the default" (sitting 18)

- **Operator rulings (two):** (1) "continue" — passage of the D2 review gate
  into E1 Kernels (first-"no"-is-law standing). (2) "loopback is the
  default" — the sitting-17 substitution is CONFIRMED as doctrine: atlas
  servers bind loopback; anything wider is the operator's explicit call
  (`--bind`), never a default. This now covers atlas-door and every future
  atlas server (glass, townweb, platform).
- **Gate accepted on the record:** sitting-17 witnessed; seals at passage:
  cargo 82/82, door `--prove` 13/13, go suite ok, `atl self-test` 10/10, tsc
  clean, lint CLEAN, nine cutters green, check_trade_parity 7/7, VERSION d2.
- **E1 per ACCEPTANCE (C++):** E1-01 PPMI parity (integer counts bit-exact,
  floats within tolerance) · E1-02 digest scale (bounded RSS, links via Rust
  pen) · E1-03 predictor speed (≥10× Python on fixed corpus) · E1-04
  socket-free (source scan). Standing law already bans network; E1 proves it
  by scan. Gate: side-by-side timing/output review.

---

## 2026-09-03 — E1 STEP 1: libppmi + socket scan green (sitting 18)

- **Goldens before code (law held):** `tools\cut_ppmi_vectors.py` trains the
  read-only oracle (`5.0/manjuel5/models.py`, sha pinned `19d7fa11…51aab`)
  on a fixed ASCII corpus — 20 vectors (tokens/stems/sentences/vocab/counts,
  hex-float vectors+freqs, trigram tables, lambdas, prob/perplexity spots,
  fixed-seed generations, detokenize). Floats pinned via float.hex()
  (exact); `--verify` green. The cutter tripped on its own JSON tuple/list
  shapes twice — fixed the cutter, not the oracle.
- **Landed (`kernels/`, C++17, stdlib only, MSVC /O2):** `ppmi.hpp/cpp` —
  tokenizer/stemmer/sentences/dot/normalize/detokenize, Embedder (PPMI +
  JL projection), LanguageModel (deleted-interpolation trigram), and a
  CPython-faithful MT19937 (variant init_by_array, LE int→key, res53,
  choices via sequential cum + bisect_right). `prove.cpp` asserts the golden
  fixture (counts bit-exact, floats ≤1e-9, generations byte-exact).
  `prove.py` bootstraps MSVC via vswhere→vcvarsall (env capture, never
  downloaded), compiles, runs, then the E1-04 socket scan.
- **First-contact verdict:** 13/13 strokes green, generations byte-exact
  (the RNG replication was right the first time), vectors worst diff
  1.67e-16 — seven orders inside tolerance (libm log 1-ulp class).
- **Harness defects paid (all mine):** vswhere `-requires` filter too strict
  for v18 metadata (verify path instead); `Path` vs injected all-caps `PATH`
  (prefer the vcvarsall spelling); CRLF lesson re-applied to golden files
  (binary writes).
- **Proven:** kernels `prove.py` exit 0 (compile clean + 13 strokes + scan
  clean) · cargo 82/82 · go suite ok · `atl self-test` PROVEN · eight
  cutters (incl. new ppmi) green · no source-ground writes.
- **E1 state:** E1-01 ✓ + E1-04 ✓ (for the landed surface). OPEN: E1-02
  digest scale (foldall + Rust-pen links) and E1-03 predictor bench (≥10×) —
  oracles surveyed (digest.py meals/wraps, predictor.py lanes/solver), ports
  next sitting. No VERSION bump: the stone closes whole or not at all.

---

## 2026-09-03 — RULING BANKED: "continue" = finish E1 (sitting 19)

- **Operator ruling:** "continue" — finish the stone (E1-02 digest scale +
  E1-03 predictor bench), then the side-by-side gate.
- **Standing plan:** digest meal goldens from digest.py → `atlas link lay`
  verbs (the Rust pen, SPEC_COMMANDS-named) → foldall driver → predictor
  goldens from predictor.py → libpredictor + bench ≥10× → seals → VERSION e1.

---

## 2026-09-03 — E1 CLOSED: digest + predictor + bench (sitting 19)

- **Goldens before code (law held):** `cut_digest_vectors.py` (planted sample
  catalog via the oracle's own planter; meal marks/vocab/vectors/prune
  events incl. 13 forced prunes; meal links laid with the LIVE pen; chain
  INTACT + records; catalog fixture committed) · `cut_predict_vectors.py`
  (fixed seeded weights; 5 expects + 3 surprises from the oracle's own
  methods with the library standing stubbed). Both `--verify` green. Cutters
  tripped on tuple/list shapes and binary book handling — fixed the cutters.
- **Landed Rust (`store\src\link.rs`, the pen):** `atlas link lay|status` —
  links-shape entries (UTC/+0000, cites validated, sealed doc hashed, mark
  welded, sig/pub paired), wraps every 40 under Merkle v2 (v1 honored for
  old), status rewalks weld+hash+wrap-roots. Merkle roots byte-match the
  oracle both versions (probe-cut). Unparsable lines read TAMPER, never Err.
- **Landed C++ (`kernels/`):** `sha256.hpp` (FIPS, NIST-anchored) ·
  `digest.hpp/cpp` (tokens/sign-row/marks/count+prune/project/banker-5) ·
  `foldall.cpp` (catalog → vocab/vectors + meal links + closing via the pen,
  argv-spawned, no shell) · `predict.hpp/cpp` (context/predict/expect/
  surprise) · `bench.cpp` + `bench_py.py` baselines · `prove.py` compiles,
  runs, benches, scans.
- **The sha256 incident, witnessed plainly:** a recalled NIST literal
  (cf0bb/dfa2fd9) failed against FIVE agreeing implementations (OpenSSL ×2,
  CNG ×2 via certutil/Get-FileHash, our Rust, new C++, pure-Python
  reference) plus famous anchors (hello, 32-zero, 64-zero all correct).
  Ruling: recalled tails lie; consensus + anchors rule. The implementation
  was right all along — the test literal was wrong. The diet failure beside
  it was REAL and separate (raw lines hashed without newlines; stats canon
  is an ARRAY of pairs, not an object — both fixed, diet now bit-exact).
- **Shell lesson:** cmd.exe quote-stripping broke `_popen` pen calls;
  foldall now spawns argv directly (CreateProcess/pipe, fork/exec) — no
  shell, no quoting class of bug.
- **Proven:** kernels exit 0 — 17 unit strokes (worst float diff 1.67e-16),
  foldall end-to-end (records match, vectors worst 0, chain INTACT),
  bench 8/8 answers + **51.5× speedup** (618.6ms vs 12.01ms, 320 reps),
  socket scan clean · cargo **84/84** · go suite ok · `atl self-test`
  PROVEN · tsc clean · lint CLEAN · twelve cutters green · no source-ground
  writes.
- **VERSION → `0.1.0+e1`** (root + line + three binaries + version.rs pin).

---

## 2026-09-03 — RULINGS BANKED: "continue" + "use local ollama models and rack, start small" (sitting 20)

- **Operator rulings (three readings, one sitting):** (1) "continue" — passage
  of the E1 review gate into F1 Harvest (first-"no"-is-law standing).
  (2) F1 runs on **local Ollama models and the rack** — no hosted inference,
  no API keys, loopback only. (3) **Start small** — one rack tool at a time,
  each provable before the next wakes.
- **Gate accepted on the record:** sittings 18–19 witnessed; seals at passage:
  kernels exit 0 (17 strokes + foldall e2e + bench 51.5× + scan clean),
  cargo 84/84, go suite ok, `atl self-test` PROVEN, tsc clean, lint CLEAN,
  twelve cutters green, VERSION e1.
- **F1 per ACCEPTANCE:** F1-01 memory envelopes (citations or refusal) ·
  F1-02 guard/redact/scan pipeline (injection blocked, PII stripped, poison
  flagged) · F1-03 SKILL.md lint (`atl skill lint`). The rack_* trio
  (honest refusals since B1) wakes here. Step 1 (small): rack_list real —
  the live tier ladder of lawful local voices, loopback Ollama + rack
  inventory; rack_ask/rack_open stay honestly refusing until their turn.

---

## 2026-09-03 — F1 STEP 1: rack_list wakes, small and proven (sitting 20)

- **Ground observed:** Ollama UP on loopback :11434 with 9 live models
  (scout 3 / voice 5 / mind 1); manifests mirror them on disk. The box
  exports OLLAMA_HOST=0.0.0.0:11434 (Ollama's own bind spelling).
- **Goldens before code (law held):** `tools\cut_rack_vectors.py` folds the
  live list ONCE (`rack_tags.json`) and pins the ladder rendering
  (`rack_ladder.txt`). `--verify` never fetches (live models come and go;
  re-folding is a separate drift stroke). Tier contract: ≤3GB scout,
  ≤8GB voice, else mind; decimal GB, family shown, no role guessing.
- **Landed (`line\internal\rack`, stdlib only):** loopback-guarded Host
  (bare host:port normalized; 0.0.0.0/:: admitted as this-host with the
  reasoning witnessed — they dial loopback, never outward; example.com/
  RFC1918 stay refused), List (/api/tags, 10s timeout, 8MB cap), Ladder
  (byte-exact with the cutter). `rack_list` real on the surface;
  rack_ask/rack_open still refusing honestly. Silence is an honest empty,
  never fabricated voices.
- **The guard earned its keep:** first contact refused the box's own
  OLLAMA_HOST (no scheme); rather than narrowing the world to fit the code,
  the code learned Ollama's own spelling with the boundary intact — live
  ladder proven through the real tool against the real door (9 voices).
- **Proven:** rack 4 tests green (golden byte-match, stub tiers, outward
  refused, silence honest) · `--prove` 40 strokes exit 0 (4 new) from module
  root AND package dir (fixture search walks up) · cargo 84/84 · go suite
  ok · `atl self-test` PROVEN · tsc clean · lint CLEAN · thirteen cutters
  green · no source-ground writes.
- **F1 state:** step 1 DONE (rack_list). OPEN: rack_ask (routed ask to a
  local voice, ledger-witnessed), rack_open (context bundles), F1-01
  envelopes, F1-02 guard pipeline, F1-03 skill lint. No VERSION bump: the
  stone closes whole or not at all.

---

## 2026-09-03 — RULING BANKED: "continue" = rack_ask, next small step (sitting 21)

- **Operator ruling:** "continue" — the next small F1 step after rack_list.
- **Scoped (small, like step 1):** rack_ask real — route (explicit voice, or
  first speaking voice in ladder order with embedding voices excluded via
  /api/show capabilities), ask over loopback Ollama (/api/generate,
  stream:false), witness to a rack ledger under the ask lock. rack_open
  stays refusing; envelopes (F1-01) wrap answers next, not here — the seam
  is the witness record they will cite.

---

## 2026-09-04 — F1 STEP 2: rack_ask routes, answers, witnesses (sitting 21)

- **Goldens before code (law held):** `tools\cut_rack_ask_vectors.py` folds
  /api/show per voice (trimmed to capabilities — full templates would bloat
  100x) + one real answer ("witnessed"). Pins: default route
  llama3.2:latest, the embedder to refuse, the answer shape. `--verify`
  never fetches.
- **Landed (`line\internal\rack\ask.go`, stdlib only):** Capabilities facts
  (not inference) · Route (explicit-by-name, else first speaking in ladder
  order; strangers refused by name, embedders with the reason) · Ask
  (stream:false, whole-and-nonempty or refused — never truncated-as-whole,
  600s bound like ask_steward) · Witness (ts/kind/voice/question/answer to
  state/rack_ledger.jsonl — the record F1-01's envelopes will cite).
  `rack_ask` real on the surface under the ask lock; rack_open still
  refusing honestly.
- **Live proven:** phi4-mini:latest answered "witnessed" through the real
  tool against the real door, witness line verified in shape, probe file
  removed after (temp-ground discipline for a live tree — the line held).
- **Proven:** rack 7 tests green (golden route, answer shape, stubbed
  end-to-end incl. ledger fields, stranger + embedder refusals) · `--prove`
  44 strokes exit 0 (4 new) from module root AND package dir · cargo 84/84 ·
  go suite ok · `atl self-test` PROVEN · tsc clean · lint CLEAN · fourteen
  cutters green · no source-ground writes.
- **F1 state:** steps 1–2 DONE (list, ask). OPEN: rack_open, F1-01
  envelopes, F1-02 guard pipeline, F1-03 skill lint. No VERSION bump: the
  stone closes whole or not at all.

---

## 2026-09-04 — RULING BANKED: "continue" = rack_open, next small step (sitting 22)

- **Operator ruling:** "continue" — the next small F1 step after rack_ask.
- **Scoped (small, like steps 1–2):** rack_open real — expanded context
  bundle at a depth: depth 1 = voice card (folded /api/show facts); depth 2
  = + ladder + recent ledger lines (capped, truncated by rule); depth 3 =
  + the project's get_in_line pack (reused, not rebuilt). Read-only.
  Unknown voices refused by name; depths outside 1–3 refused; absent ledger
  named, not errored. Envelopes (F1-01) come next — bundles are what they
  will wrap.

---

## 2026-09-04 — F1 STEP 3: rack_open bundles at every depth (sitting 22)

- **Goldens before code (law held):** `tools\cut_rack_open_vectors.py` builds
  a fixed bundle ground (3 witness lines, one long answer) and pins depth-1
  + depth-2 bundles byte-exact; depth 3 embeds the live pack, so it is
  asserted structurally (headers), never by bytes. `--verify` never fetches.
- **Landed (`line\internal\rack\open.go`, stdlib only):** VoiceCard (folded
  facts, sorted capabilities) · MemoryLines (last 5, 200-rune truncation
  with remainder counted, absence named) · Bundle (depths 1–3, outside
  refused) · ReadLedger (missing reads as absent). `rack_open` real on the
  surface, read-only; the rack trio is awake — nothing refuses honestly
  anymore (forbidden verbs still absent by construction).
- **Live proven:** depth-2 bundle through the real tool against the real
  door — routed voice, true capabilities, full ladder, honest "(no ledger
  yet)". Read-only all the way; no live writes anywhere.
- **Proven:** rack 10 tests green (bundles byte-exact, d3 structural,
  truncation rule, refusals) · `--prove` 49 strokes exit 0 (5 new) from
  module root AND package dir · cargo 84/84 · go suite ok · `atl self-test`
  PROVEN · tsc clean · lint CLEAN · fifteen cutters green · no
  source-ground writes.
- **F1 state:** steps 1–3 DONE (list, ask, open). OPEN: F1-01 envelopes,
  F1-02 guard pipeline, F1-03 skill lint. No VERSION bump: the stone closes
  whole or not at all.

---

## 2026-09-04 — RULING BANKED: "continue" = F1-01 envelopes (sitting 23)

- **Operator ruling:** "continue" — the next small F1 step after rack_open.
- **Scoped (small):** F1-01 memory envelopes — a read-only memory tool over
  the rack ledger: every answer carries its witness citations or is refused
  (never an uncited answer, never an invented one). Match by voice and/or
  question substring (case-insensitive); empty query returns the latest.
  Citations point at witness records (ledger ts + voice), the seam rack_ask
  banked in sitting 21. Guard pipeline (F1-02) will demand envelopes next —
  not here.

---

## 2026-09-04 — F1-01 ENVELOPES: cited or refused (sitting 23)

- **Goldens before code (law held):** `tools\cut_memory_vectors.py` renders
  expected envelopes over the fixed bundle-ground ledger (3 witness lines):
  query, voice, and latest cases byte-exact; the refusal pinned word for
  word. `--verify` fetches nothing.
- **Landed (`line\internal\rack\memory.go`, stdlib only):** Recall (AND
  filters, latest-single on empty query, latest-5 cap with remainder
  counted) + Envelope (full answers — truncation was the bundle's job) +
  the two pinned refusals. `memory` real on the surface (20 tools),
  read-only.
- **Live proven:** empty live ledger refused honestly through the real tool
  (no fabrication to fill the silence); the golden ground proves the cited
  path byte-exact.
- **Proven:** rack 13 tests green (golden renders, pinned refusals, bounds)
  · `--prove` 53 strokes exit 0 (4 new) · cargo 84/84 · go suite ok · `atl
  self-test` PROVEN · tsc clean · lint CLEAN · sixteen cutters green · no
  source-ground writes.
- **F1 state:** steps 1–3 + F1-01 DONE (list, ask, open, envelopes). OPEN:
  F1-02 guard pipeline, F1-03 skill lint. No VERSION bump: the stone closes
  whole or not at all.

---

## 2026-09-04 — RULING BANKED: "continur" = F1-02 guard pipeline (sitting 24)

- **Operator ruling:** "continur" — the next small F1 step after envelopes.
- **Scoped (small):** F1-02 guard/redact/scan — Guard ports the gatehouse
  pokes verbatim (injection blocked with the gate's own words); Redact
  strips specified PII classes before voice and ledger; Scan flags
  mechanical poison markers (flagged, never blocked). Wired FIRST in
  rack_ask. No clamp (stated: the 600-char rule belongs to chat vestibules,
  not the rack).

---

## 2026-09-04 — F1-02 GUARD: pokes blocked, PII stripped, poison flagged (sitting 24)

- **Goldens before code (law held):** `tools\cut_guard_vectors.py` pins poke
  verdicts from the oracle's OWN admit() (gatehouse.py, sha pinned) +
  specified redact/poison pairs with self-honesty checks. The cutter caught
  its own bucket bug (shared rate bucket refused later texts — fresh
  gatehouse per text, and the verdicts flipped to the oracle's true ones)
  and a card regex eating its trailing space. `--verify` green.
- **Landed (`line\internal\guard`, stdlib only):** Guard (14 poke patterns
  verbatim, matched-substring receipts, gate's words quoted) · Redact
  (email/ssn/card/key/phone in the golden order) · Scan (zero-width, bidi,
  b64-blob — flags, never blocks) · Pipeline (guard→redact→scan). Blocked
  asks never route and leave no witness; PII redacts before voice AND
  ledger; poison rides answer wrapper + witness flags (schema gains
  "flags", always present).
- **Live proven:** injection refused with gate words + matched receipt,
  zero ledger trace, no live writes.
- **Encoding discipline (paid twice):** non-ASCII test characters ride
  explicit \u escapes in Go source — the transport smuggled U+2028 once;
  byte-exact scripts fixed it. ASCII in source, always.
- **Proven:** guard 4 tests green (oracle pokes, specified pairs, pipeline
  order) · `--prove` 59 strokes exit 0 (6 new) · cargo 84/84 · go suite ok ·
  `atl self-test` 10/10 · tsc clean · lint CLEAN · seventeen cutters green ·
  no source-ground writes.
- **F1 state:** steps 1–3 + F1-01 + F1-02 DONE. OPEN: F1-03 skill lint. No
  VERSION bump: the stone closes whole or not at all.

---

## 2026-09-04 — RULING BANKED: "continue" = F1-03 skill lint (sitting 25)

- **Operator ruling:** "continue" — the last open F1 row after the guard.
- **Scoped (small, closing the stone if whole):** F1-03 SKILL.md lint —
  `atl skill lint` over the rack: spec violations named file-by-file, valid
  set green. Oracle: the skills-main validator pattern (T6). Goldens first
  (valid + violation fixtures), then the command, then the seals; if every
  F1 row stands green, VERSION f1 pins and the stone is presented shut.

---

## 2026-09-04 — F1-03 SKILL LINT + F1 CLOSED WHOLE (sitting 25)

- **Goldens before code (law held):** `tools\cut_skill_vectors.py` writes one
  minimal fixture per rule (valid + 9 violations) and pins verdicts. No
  validator file survives on the estate (T6 cites a pattern only), so the
  oracle is the FORMAT + the rack corpus: rules R1..R5 specified here.
  Cutter bugs paid (fixture name≠dirname; cascade honestly pinned).
- **Landed (`atl skill lint`, node stdlib):** frontmatter/name/description/
  body/dupkey rules + folded-scalar (`>`/`|`) support — the REAL rack caught
  the gap (agentic-actions-auditor falsely flagged until folding landed),
  then scanned 9/9 CLEAN. Off-by-one in the cutter paid the same way. A JS/
  Python split-semantics trap (split limit) caught by the self-test, fixed
  with the difference named in a comment.
- **Proven:** cutter 10/10 · `atl self-test` 11/11 (golden verdicts matched
  exactly) · real rack 9/9 CLEAN · tsc strict clean · cargo 84/84 · go suite
  ok · kernels exit 0 · eighteen cutters green · no source-ground writes.
- **F1 CLOSED:** every row green — rack trio (live-proven) + envelopes +
  guard + skill lint. **VERSION → `0.1.0+f1`** (root + line + three binaries
  + version.rs pin + atl consistency).
- **F1 state:** COMPLETE pending review gate (feature demos = the proves;
  adoption order is the operator's). Next stone on ruling: G Cutovers.

---

## 2026-09-04 — RECORD REPAIR: one null byte (sitting 25, appendix)

- **Found during close-out:** a single NUL byte inside the sitting-9 block
  ("VERSION bumped [NUL].1.0+b1") — transport corruption of old standing,
  same class as the sitting-5 backslash mangling. Original unambiguous from
  context; repaired to "0" in place, nothing else touched. Above history
  otherwise unrewritten, per the append-only law.

---

## 2026-09-07 — G Cutovers Phase 1: gm harness + Rust --prove (sitting 26)

- **F1 gate ruled by operator** ("proceed").
- **Rust `--prove` landed:** `apps/atlas/src/prove.rs` — 10 strokes,
  hermetic temp grounds, exit 0. version-pin · version-cross ·
  chain-verify-fixtures (16/21 INTACT, 5 expected TAMPER) ·
  chain-recognize-fixtures (21/21 recognized) · store-trio (byte-identical) ·
  db-lifecycle (init/import/export/status) · enroll-dry (idempotent) ·
  orient-pack · link-lay-status · covenant-repro (construction-A over both
  epochs). Wired into `main.rs` as `--prove` arm. `cargo test` 10/10 green.
- **@atl/gm landed:** `atl/gm.ts` — golden-master orchestration harness
  (catalog T4, SPEC_SEAM). Stone registry: A1/B1/C1/D1/D2/E1/F1, each
  mapping to its cutter `--verify` + consumer test batteries. Report format:
  `{stone, name, strokes[{pair, match, detail}], mismatches}`.
- **`atl gm` wired:** `atl gm run [--stone <S>]` · `atl gm list` added to
  `atl/cli.ts`. Runs cutters via `python --verify`, Rust via `cargo test`,
  Go via `go test` (from line/ module root), TS via `node --experimental-strip-types`.
- **PROVEN:** `atl gm run` **28/28 strokes green across 7 stones** — all
  cutters verify, all Rust tests pass, all Go tests ok, TS self-test 11/11.
  cargo 84/84 · go ok · tsc clean · lint CLEAN · VERSION 0.1.0+f1 unchanged.
- **Open for the operator:** Phase 2 (per-service cutover proofs: Gx-02 port
  check + Gx-03 rollback notes) opens at your word.
- **Lesson:** the gm harness is orchestration, not re-implementation — the
  existing 18 cutters already prove cross-impl parity for every built
  service. The harness just collects the receipts.

---

## 2026-09-07 — G Cutovers Phase 2: cutover proofs + rollback notes (sitting 26 cont.)

- **Gx-01 proven:** `atl gm run` 28/28 green across 7 stones (A1/B1/C1/
  D1/D2/E1/F1). Prove output saved to `docs/rollback/GX01_GM_PROVE.txt`.
- **Gx-02 proven:** Port/command verification for all 7 services against
  SPEC_COMMANDS. Report at `docs/rollback/GX02_PORT_COMMAND_REPORT.md`.
  D1 verbs match · D2 port 8080 frozen · B1 protocol 2025-06-18 + 20
  tools + forbidden absent · C1 byte-parity · A1 CLI full · E1 socket-free
  · F1 Ollama loopback.
- **Gx-03 proven:** 7 rollback fold notes drafted under `docs/rollback/`:
  A1_SPINE.md (additive, no process) · B1_LINE.md (re-point .mcp.json) ·
  C1_FACES.md (stop atl, Aurora stays) · D1_TOWN.md (CLI additive) ·
  D2_DOOR.md (stop Go, start Python on :8080) · E1_KERNELS.md (additive) ·
  F1_HARVEST.md (re-point MCP, Ollama stays).
- **G Cutovers COMPLETE** (pending operator gate on each switch).
  All receipts gathered. VERSION 0.1.0+f1 unchanged. No source-ground writes.

---

## 2026-09-07 — Documentation Phase: 18 documents (sitting 27)

- **Operator ruling:** "write a plan first, then execute." All 18 docs
  written in 7 phases, operator holds gate for publication.
- **Phase 1 Foundation:** LICENSE (MIT), SECURITY.md (vulnerability
  reporting + security model), CONTRIBUTING.md (dev setup, code style,
  PR process).
- **Phase 2 Public Face:** README.md (full rewrite with badges, architecture
  diagram, quickstart), CHANGELOG.md (version history P0 through F1).
- **Phase 3 Specs:** specs/SPEC_US_SCHEMA.json (JSON Schema for .us format),
  docs/ARCHITECTURE.md (system architecture, layer diagram, data flow,
  trust model, seam contracts).
- **Phase 4 ADRs:** 5 architecture decision records — 001-polyglot-seam,
  002-fold-never-delete, 003-can-approve-false, 004-socket-free-kernels,
  005-golden-master-parity.
- **Phase 5 User Guides:** docs/QUICKSTART.md (rewritten for current state),
  docs/WALKTHROUGH.md (full system tour), docs/TUTORIAL.md (5 exercises),
  docs/CLI_REFERENCE.md (every command, every flag, all 4 binaries).
- **Phase 6 Compliance:** docs/COMPLIANCE.md (EU AI Act Art. 12/14/19,
  SOC 2, ISO 42001 mapping, competitor comparison, readiness assessment).
- **Phase 7 Packaging:** Dockerfile (multi-stage build: Rust + Go + runtime).
- **Market report delivered** (pre-session): Atlas positioned as provenance
  and governance runtime; key differentiators identified; gaps named.
- **Seals at close:** all 18 files verified present and consistent.
  65/65 E2E still green. 85+ Rust tests still green. 14 Go tests still
  green. VERSION 0.1.0+f1 unchanged. No source-ground writes.
- **Documentation Phase COMPLETE.** 77 total stones across build + docs.
  Operator holds gate for publication.

---

## 2026-09-07 — CI/CD + Parity Plan (sitting 28)

- **Parity plan written:** docs/PARITY_PLAN.md — full build path, 5
  internal parity groups, 8 cross-language seam maps (Rust↔Go chain
  verification, Rust↔Go trade books, Python→C++ kernel goldens,
  Python→TS face goldens, Python→TS GM harness, Python→Go town
  decisions, Python→Go mesh envelopes, cross-cutting guard pipeline),
  9-layer prove matrix, parity acceptance criteria, CI/CD architecture.
- **CI pipeline landed:** .github/workflows/ci.yml — 8 parallel jobs:
  lint (tsc + go vet + atl lint), build (Rust + Go + C++), test-rust,
  test-go, prove-binaries (atlas + atl + 3 Go binaries), prove-kernels
  (C++ compile + prove + bench + scan), golden-cutters (17 cutters
  --verify), cross-impl (trade parity + fold agents), e2e (65 tests),
  version-check (all binaries answer VERSION). Triggers: push/PR to
  main, workflow_call (for release), workflow_dispatch.
- **Release pipeline landed:** .github/workflows/release.yml — triggered
  on tag push (v*), runs full CI first, then builds release tarball
  (musl static + Go ldflags -s -w), creates GitHub Release with tarball,
  builds Docker image to GHCR.
- **prove.py adapted for Linux:** cross-platform compiler detection
  (MSVC on Windows, g++/clang++ on Linux), same prove battery, portable.
  foldall.cpp already had POSIX fork/exec/waitpid in #ifdef #else.
- **Dockerfile fixed:** golang version 1.22 → 1.26, removed live data/
  copy (source-ground law), added empty data/ directory for operator
  to populate at runtime.
- **.gitignore expanded:** CI/CD artifacts (*.exe, *.o, kernels/build/),
  IDE files, OS files, temp files.
- **Seals at close:** go vet clean, go tests all pass, rust 85+ still
  green. VERSION 0.1.0+f1 unchanged. No source-ground writes.
- **CI/CD Phase COMPLETE.** 78 total stones. Operator holds gate for
  first push to GitHub.

## 2026-09-08 — BUG FIX: TUI extractField transform + doc audit cleanup

- **extractField bug fixed:** `cmdAgentsList` now iterates the agents
  array directly when a transform is given (matching `cmdToolsList`
  pattern), instead of passing the wrapper map. `--transform name -r`
  now works. Help example updated from `*.name` to `name`.
- **extractField hardened:** When `*` hits a map instead of an array,
  the function now auto-finds the first array-valued field and iterates
  that. This makes `*.name` work on wrapper maps like
  `{"agents": [...], "count": N}`.
- **Tests added:** `extract_test.go` — 3 test functions covering
  nested paths, wrapper-map auto-find, and single-field extraction.
- **Full prove re-run:** 92 Go tests PASS (tui + mcp + town + door),
  85 Rust tests PASS, 4 Python verifiers PASS, MCP 58 strokes PASS.
- **All binaries rebuilt:** atlas 0.1.0+f1, atlas-mcp, atlas-town,
  atlas-door, atlas-tui — all in bin/, all green.
- **Seals at close:** go vet clean, go tests all pass, rust 85+
  green, Python verifiers byte-identical. VERSION 0.1.0+f1 unchanged.
  No source-ground writes. 79 total stones.

## 2026-09-08 — TUI TEST + AGENT DOCS + SKILLS (sitting 80)

- **TUI end-to-end tested:** all resource commands verified against
  live MCP on :8090. Status, tools list/get, chain list/verify,
  agents list/get, rbac list, tenants, mesh, rack — all return valid
  output. Transform paths (`name`, `*.name`) work. Output formats
  (json, yaml, pretty, raw) work. Error handling verified for
  nonexistent agents/tools. Version and completion commands work.
- **YAML format fixed:** `printYAML` type mismatch — `[]map[string]any`
  didn't match `case []any:`. Fixed by using `[]any` in cmdRBACList
  and cmdAgentsList. YAML now renders correctly for all resources.
- **40/40 agent .us declarations validated:** `atlas agent enroll --dry`
  confirms all files parse clean, can_approve:false present in all,
  covenant hash matches in all, reports_to resolves in all.
- **40 agent.md files written:** one per citizen, organized by household
  hierarchy. Each includes: office, role, reports_to, mode, permissions,
  source, description. Index at `agents/docs/README.md`.
- **3 skills added:** `skills/prove/SKILL.md`, `skills/orient/SKILL.md`,
  `skills/enroll/SKILL.md` — basic skill documentation following estate
  SKILL.md format (frontmatter + usage + expected output).
- **Documentation updated:** `docs/README.md` updated with agents, skills,
  and build plan sections. File count updated.
- **Full prove re-run:** 92 Go tests PASS, 85 Rust tests PASS,
  4 Python verifiers PASS, MCP 58 strokes PASS.
- **Seals at close:** go vet clean, go tests all pass, rust 85+
  green, Python verifiers byte-identical. VERSION 0.1.0+f1 unchanged.
  No source-ground writes. 80 total stones.

---

### Sitting 81 — Webapp + Full Release Docs (2026-09-08)

**Stone:** Webapp observability GUI + MIT license + release documentation
**Seat:** opencode (builder)

**What landed:**
- **Webapp backend:** `webapp/` — Go + vanilla JS, zero external dependencies
  - `main.go` — entry point, wires DB/stores/handlers, embeds static
  - `db/db.go` — JSON file store (pure stdlib, no external imports)
  - `server/server.go` — HTTP server with embedded SPA + 16 API routes
  - `handlers/handlers.go` — health, agents, traces, evals, tools, search,
    messages, settings, SSE, tool call with SHA-256 hashing
  - `agents/agents.go` — agent registry backed by DB
  - `traces/traces.go` — trace store with listing and settings
  - `evals/evals.go` — eval engine
  - `search/search.go` — cross-agent and trace search
  - `messaging/messaging.go` — message bus + Discord/Slack/WhatsApp adapter stubs
- **Webapp frontend:** `webapp/static/`
  - `index.html` — SPA shell with sidebar nav
  - `css/app.css` — Sovereign Dark Theme design system
  - `js/api.js` — API client, SSE, toast, time formatting
  - `js/app.js` — SPA router + 7 pages (dashboard, agents, agent detail,
    traces, trace detail, tools, evals, messages, settings)
- **Release documentation:**
  - `LICENSE` — MIT license
  - `README.md` — full project README with architecture, quickstart, features
  - `CONTRIBUTING.md` — dev setup, code style, agent declarations, PR process
  - `CHANGELOG.md` — full changelog for 0.1.0+f1
  - `SECURITY.md` — vulnerability reporting, scope, hardening checklist

**Verification:**
- `go build ./webapp/...` — PASS (zero external deps)
- `go vet ./webapp/...` — PASS (clean)
- 85 Rust tests PASS
- 92 Go tests PASS
- 4 Python verifiers PASS
- MCP 58 strokes PASS
- VERSION unchanged `0.1.0+f1`
- No source-ground writes

---

## 2026-09-08 — Sitting 83: CUTOVER COMPLETE — all 7 switches flipped

**Operator ruling:** "formally flip em" — received 2026-09-08.

**What landed:**

All 7 cutover switches formally flipped per THE_ROAD and sitting 26's
Gx-01/Gx-02/Gx-03 receipts:

| Service | Binary/Port | Status |
|---|---|---|
| A1 Spine | `atlas` (Rust CLI) | FLIPPED |
| B1 MCP | `atlas-mcp` on `:8090` | FLIPPED |
| C1 Faces | vendored bytes + atl toolchain | FLIPPED |
| D1 Town | `atlas-town` | FLIPPED |
| D2 Door | `atlas-door` on `:8080` | FLIPPED |
| E1 Kernels | C++ ppmi/digest/foldall | FLIPPED |
| F1 Harvest | rack tools via MCP | FLIPPED |

Additional confirmed live:
- Webapp on `:8091` (Go + vanilla JS, 16 API routes, SSE)
- Ollama on `:11434` (11 models, live integration proven)

**Verification:**
- All services responding on their ports
- 112/112 E2E proven (74 scenarios + 38 workflow steps)
- 85+ Rust, 92 Go, 4 Python, 58 MCP strokes — all green
- 40/40 agent declarations validated
- 7 rollback notes at `docs/rollback/`
- VERSION `0.1.1+f1` unchanged
- No source-ground writes

---

### Sitting 82 — CI/CD (2026-09-08)

**Stone:** GitHub Actions CI/CD + prove script + release flow
**Seat:** opencode (builder)

**What landed:**
- **CI workflow:** `.github/workflows/prove.yml` — runs on push/PR to main
  - Rust tests (ubuntu, rust-cache)
  - Go tests (line + webapp build + vet)
  - Python verifiers (4 scripts)
  - Agent enrollment validation (copy master.db, dry run)
  - MCP 58-stroke prove (depends on Rust + Go)
  - Webapp build + vet
- **Release workflow:** `.github/workflows/release.yml` — triggered by `v*` tags
  - Full prove gate before any build
  - Cross-platform matrix: ubuntu, windows, macos (x86_64)
  - Builds Rust + Go binaries into release/
  - Tar.gz per platform
  - Creates GitHub release with artifacts + LICENSE + README + CHANGELOG
- **prove.ps1** — local PowerShell prove script (5 steps + webapp)
  - Rust tests, Go tests, Python verifiers, MCP prove, agent enrollment, webapp build
  -彩色 output, exit 0 on success
- **release.ps1** — release automation script
  - Runs prove, updates VERSION files, commits, tags, pushes

**Verification:**
- `prove.ps1` runs clean: all 5 steps + webapp PASS
- All prior tests unchanged: 85 Rust, 92 Go, 4 Python, MCP 58 strokes
- VERSION unchanged `0.1.0+f1`
- No source-ground writes

---

## 2026-09-09 — RULING BANKED: reverse the six No's (N-stones open)

- **Operator ruling:** "fix the chat ui, fix the workflow builder, fix the
  model hosting, fix the prompt playground, fix the team chat, and line up
  for the SaaS" — the seven `ATLAS_PRODUCT_PLAN.md` No's are reversed.
- **Answers banked:** chat = SSE + WebSocket · team chat = two-way now ·
  SaaS = full multi-user auth now · workflows = full DAG now.
- **Conflicts named (operator holds each gate):** two-way chat needs
  someone else's server + inbound webhooks (bends RULE 4 + loopback);
  multi-user bends "second user is a fork"; full DAG is new semantics over
  linear town/chain; WS is a new surface on `:8091` (no new port).
- **Order ruled by proposal, opened by this sitting:** N0 hygiene →
  N3 rack → N1 chat → N4 playground → N2 DAG → N5 team-chat → N6 SaaS.
  Law kept throughout: zero external deps, goldens first, hermetic proves,
  `can_approve:false`, forbidden verbs absent, ports never move.

---

## 2026-09-09 — N0 HYGIENE + N3 RACK-PLAN landed (sitting 84)

- **Goldens before code (law held):** `tools\cut_rack_plan_vectors.py` pins
  the VRAM planner v1 contract (15GB budget, 1.5GB graph overhead,
  tiered KV/token, ctx 4096, largest-first evictions) — 12 vectors in
  `tests\fixtures\rack_plan.json`, `--verify` 12/12 green.
- **Landed:**
  - `.gitattributes` (`* -text`) — fixtures keep their bytes on clone
    (sitting-15 CRLF lesson; SPEC_CONTROL_CENTER §9 Q6).
  - `atlas-tui` off `curl` → stdlib `net/http` loopback-only
    (P0-10); no `exec.Command("curl")` remains.
  - `line\internal\trust\` — `state/trust.json` store (atomic write,
    sorted, honest empty); wall law kept (record lives in caller's home).
  - `tenant_list` REAL — enumerates `reg.Names()` with RBAC mode +
    trust counts; `tenant_trust` REAL — validates names against the
    registry, refuses forbidden verbs + strangers by name, persists +
    receipts with sha256. Enforcement on cross-project hops rides N6.
  - `line\internal\rack\vram.go` — Footprint/Plan/RenderPlan byte-pinned
    to the cutter; `rack_plan` (models-JSON or live voices),
    `rack_pull` (needs `confirm=true` + `CHAINKIT_RACK_PULL=1`),
    `rack_warm` (presence + footprint), `rack_sync` (ladder + receipt).
- **Staged, not broken:** `webapp/db` fold deferred to N6 (16 routes read
  it today; retiring now breaks `:8091`). Decision witnessed here.
- **Proven:** `go build/vet` clean · `go test ./...` ok (rack incl. 12
  goldens, trust, tui) · `atlas-mcp --prove` **66 strokes exit 0** (was 58:
  +5 tenants/trust, +3 rack-plan/pull) · rack-plan/rack/rack-ask cutters
  `--verify` OK · `fold_agents.py --verify` OK · `cargo test --workspace`
  green (no Rust change) · no source-ground writes.
- **N0/N3 state:** implementation COMPLETE pending review gate. Next on
  ruling: N1 chat (SSE+WS page + `chat_*` tools).

---

## 2026-09-09 — N1 CHAT landed: sessions with receipts (sitting 85)

- **Goldens before code (law held):** `tools\cut_chat_vectors.py` pins the
  chat v1 contract — session shape `c-YYYYMMDD-HHMMSS-hex8`, receipt =
  `sha256(session\nquestion\nanswer\nts)`, guard-first refusal, redact
  marker, per-session 1..N ordering, cross-session isolation.
  `tests\fixtures\chat_vectors.json`, `--verify` green.
- **Landed (`line\`, stdlib only):**
  - `internal\rack` — `Ask` refactored to `AskCtx` (context cancels the
    Ollama stream); new `AskStream` (stream:true NDJSON, tokens forwarded,
    same whole-and-nonempty-or-refused discipline at the end).
  - `internal\chat\` — `state/chat.jsonl` append-only record (open + turn
    lines); `Start/Send/SendStream/List/Sessions/Cancel`; receipt formula
    byte-pinned to the cutter; blocked sends write NOTHING; sessions
    never see each other; in-flight registry so `chat_cancel` ends the
    stream with no partial kept.
  - THE LINE — `chat_start/send/list/cancel/sessions` (writes under the
    ask lock; shape law refused before I/O); shared `ChatSendStream`
    helper so the RPC and SSE faces cannot drift.
  - `internal\httpserver` — `GET /chat/stream` SSE (`token`/`done` with
    receipt/`refused`); strangers refused before anything streams.
- **Landed (`webapp\`, stdlib only):**
  - `handlers\chat.go` — `/api/chat/{sessions,session,start,send}`
    (whole-answer via MCP `/rpc`) + `/api/chat/stream` (MCP SSE proxied
    1:1). The webapp owns no chat logic — guard/route/ask/witness stay
    in the LINE.
  - `handlers\ws.go` — `GET /ws` hand-rolled RFC 6455 (handshake +
    masked-read/unmasked-write, ping/close); `chat.send` frames run the
    MCP stream and forward `chat.token/done/error`; hub broadcasts reach
    WS too. Frame round-trip unit-tested (`ws_test.go`).
  - SPA `/chat` (`chat.js` + nav + route + toasts): sessions, bubbles,
    Details-behind-receipts, form inputs only (no `prompt()`); WS live,
    SSE fallback, whole-answer fallback; Cancel drops the live bubble.
- **Proven:** `atlas-mcp --prove` **75 strokes exit 0** (was 66: +9 chat
  incl. isolation, no-write-on-block, quiet-cancel honesty) · `go test
  ./...` ok both modules (chat contract + isolation, vram, trust, tui,
  ws frames) · cutters `--verify` OK (chat, rack-plan 12/12, rack,
  rack-ask, fold) · live smoke: `/chat/stream?session=nope` returns
  `event: refused` naming the shape law, and `state\chat.jsonl` stays
  absent (refused writes nothing) · no source-ground writes.
- **N1 state:** implementation COMPLETE pending review gate. Next on
  ruling: N4 playground (prompts registry + `@seat` + model override).

---

## 2026-09-09 — N4 PLAYGROUND landed: measured runs (sitting 86)

- **Goldens before code (law held):** `tools\cut_playground_vectors.py`
  pins the v1 contract — name law, `{{var}}` render + missing-var
  refusal, run receipt formula, `@seat` shape, exact-match scoring.
  `tests\fixtures\playground_vectors.json`, `--verify` green. (The
  cutter caught its own bad good-name mid-sitting: a dotted name against
  a dotless law — fixed the cutter, not the law.)
- **Landed (`line\`, stdlib only):**
  - `internal\rack` — `Detail` telemetry (`AskDetail`: eval tokens +
    durations where stated, wall ms always); finishers return it, old
    faces unchanged (proven by the unchanged suites).
  - `internal\play\` — `prompts/<name>.md` registry (fold: old latest
    kept as `<name>.v<k>.md`); `Get` reads latest-or-history honestly
    (a real bug paid here: v2 lived in `hello.md`, not `hello.v2.md` —
    found by a failing stroke, fixed the code); `Render` refuses
    missing vars; `RunPrompt/SeatAsk/EvalPrompt/ComparePrompt` measure
    through guard→route→ask→rack-ledger→`runs.jsonl`; `@seat` reads the
    declaration as context, method spent after one run, model stamped
    measurement; evals score trim+casefold exact-match.
  - THE LINE — `prompt_save/get/list/run/compare/eval` + `seat_ask`
    (writes under the ask lock; names, vars, seats, datasets refused by
    name, never guessed).
- **Landed (`webapp\`, stdlib only):** `/api/prompts/*` + `/api/seat/ask`
  (whole answers — compares and evals need complete outputs to judge);
  SPA `/playground` (registry, editor, run, A/B, `@seat`, eval + record
  score as eval). Also repaired an N1 gap found en route: `api.js` never
  carried `getSession/startSession/sendChat/chatStream/wsChat` — the
  chat page called functions that did not exist. They exist now.
- **Proven:** `atlas-mcp --prove` **88 strokes exit 0** (was 75: +13
  playground incl. fold survival, 1/2 eval, seat laws) · `go test ./...`
  ok both modules · cutters `--verify` OK (playground, chat, rack-plan,
  rack, rack-ask, fold) · live smoke: `prompt_list` honest-empty,
  `prompt_save BAD NAME` refused naming the law, no `prompts/` dir
  created by refusal · no source-ground writes.
- **N4 state:** implementation COMPLETE pending review gate. Next on
  ruling: N2 workflow builder (full DAG).

---

## 2026-09-09 — N2 FLOWS landed: the DAG builder (sitting 87)

- **Goldens before code (law held):** `tools\cut_flow_vectors.py` pins the
  v1 contract — name/run-id shapes, closed kinds, edge law (fail-edges
  from eval/gate only), deterministic topo, branch/gate simulation,
  run-receipt formula, pure budget check, six refusal holes (each proven
  to refuse under the cutter's own walk). `--verify` green.
- **Landed (`line\`, stdlib only):**
  - `internal\flow\` — versioned specs (`flows/<name>.json`, history
    folds whole); `Validate` (one start, full reach, no cycles,
    name-sorted Kahn); `Run` over an `Engine` seam (production wires
    rack+play via exported `play.Measure`); templates render inputs +
    `{{out_<node>}}`; evals steer, gates pause for continue|stop, budget
    binds (ctx backstop + honest early stop); runs append to
    `flows/runs.jsonl` carrying their own spec (transcript = replay
    script); `Resume/Status/Compare/Replay/ListRuns/Cancel`; verdicts
    COMPLETE/PAUSED/FAIL/OUT_OF_TIME/STOPPED — no verb here finishes,
    lands or closes anything.
  - THE LINE — `town_beat` (ask-locked cycle, REVIEW filings) +
    `town_status` (read-only board) + `flow_save/get/list/run/resume/
    cancel/status/compare/replay/runs`.
- **Landed (`webapp\`):** `/api/town/*` + `/api/flows/*`; SPA `/flows`
  (registry, JSON editor with SVG graph preview, run + waterfall,
  continue/stop, runs/compare/replay, town board). Trade passthrough
  named open: no `trade` node yet, needs the Rust spine on PATH.
- **Defects paid:** `Get(v2)` repeated the N4 latest-file miss (fixed
  the same way); resume/replay read specs from the registry until a
  failing stroke proved unsaved specs unresumable — the start line now
  carries its spec; the static no-finish check first flagged Go's own
  `delete(` builtin, so the check judges verbs, not builtins.
- **Proven:** `atlas-mcp --prove` **105 strokes exit 0** (was 88: +3 town
  incl. no-double-cycle, +14 flows incl. pause/resume/stop, templating,
  compare, replay) · `go test ./...` ok both modules (golden topo,
  branch pass/fail, gate pause/resume/stop, var-fail never dials,
  isolation, no-finish-path scan) · cutters `--verify` OK (flow,
  playground, chat, rack-plan, rack, rack-ask, fold) · live smoke:
  honest-empty flows + quiet town on the real home, zero read-writes ·
  no source-ground writes.
- **N2 state:** implementation COMPLETE pending review gate. Next on
  ruling: N5 team chat (two-way adapters).

---

## 2026-09-09 — N5 TEAM CHAT landed: the two-way bridge (sitting 88)

- **Goldens before code (law held):** `tools\cut_teamchat_vectors.py`
  pins the v1 contract — closed platforms, channel shape, receipt
  formula, HMAC sign/verify (wrong secret catastrophically refuses),
  per-platform payload shapes, dedupe semantics. `--verify` green.
- **Landed (`line\`, stdlib only):**
  - `internal\team\` — `Send` (guard-first: injection refuses with no
    POST, PII redacted; platform-shaped payloads; https except loopback;
    non-2xx witnesses nothing) + `Ingest` (constant-time HMAC, per-
    platform parsers, Slack challenge echoes with nothing stored,
    WhatsApp statuses ignored as non-messages, external-id dedupe) +
    `History/Status` over `state/team.jsonl`. Secrets ONLY in
    `state/chat_secrets.json` (0600, operator-placed: webhooks, WA token
    + phone id, hook secret); status is presence booleans, never values.
  - THE LINE — `team_send/status/history/ingest` (sends + ingests under
    the ask lock).
- **Landed (`webapp\`):** `/api/team/*` (send/history/status, all via
  MCP `/rpc` — the face owns no logic) + `POST /hooks/:platform`
  (raw body + `X-Atlas-Signature` forwarded to `team_ingest`; challenge
  echoed, duplicates reported, bad signatures refused); Messages page
  rebuilt on the bridge (filters, direction badges, receipt hashes,
  form-only send, live presence); Settings shows live presence with the
  connect recipe. Legacy `/api/messages/*` kept green (S9).
- **Operator recipe (connect):** place `state/chat_secrets.json` —
  `{"hook_secret":"...","discord_webhook":"https://...","slack_webhook":
  "https://...","whatsapp_token":"...","whatsapp_phone_id":"..."}` —
  then point each platform at `POST :8091/hooks/<platform>` carrying
  `X-Atlas-Signature: sha256=<hmac>`. Egress happens only to pasted
  URLs: the named N5 conflict, fenced.
- **Proven:** `atlas-mcp --prove` **115 strokes exit 0** (was 105: +10
  incl. no-POST-on-block, replay-stores-once, presence-without-secrets)
  · `go test ./...` ok both modules · cutters `--verify` OK (teamchat,
  flow, playground, chat, rack-plan, rack, rack-ask, fold) · live smoke:
  disconnected-honest + bad-signature refused, `team.jsonl` and secrets
  both absent after refusals · no source-ground writes.
- **N5 state:** implementation COMPLETE pending review gate. Next on
  ruling: N6 SaaS lineup (full multi-user auth).
