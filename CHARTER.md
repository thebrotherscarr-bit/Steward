# CHARTER — ATLAS founding rulings and standing laws

*RESTORED 2026-08-25 from the held record after the overwrite incident of
2026-08-24 ~15:01 (see addendum). Restoration sources: `data\master.db`
table `rulings` (5 rows, seeded 2026-08-24) · `tools\seed_catalog.py`
RULINGS constant (verbatim bodies) · `SEAT_LOG.md` 2026-08-24 entry
(wall-widening) · `STATE_OF_BUILD.md` sitting 1 (section inventory) ·
`ACCEPTANCE.md` P0-01 and `SPEC_SEAM.md` §Versioning (laws cited by name).
Section numbering follows the witnesses: founding rulings stood in §2–§3;
build discipline stood at §6. Prose lost with the original file is not
invented; gaps are marked as folded.*

---

## §1 Name and ground

The project is **ATLAS**: one polyglot system (Rust · Go · C++ · TypeScript ·
JSON · SQLite) reconciling the whole estate. It lives at
`C:\Users\novad\Desktop\Archive\atlas\`, beside the grounds it reconciles.
`Archive\estate\` and `Archive\secondbrain\` are **read-only sources** —
walked, hashed, and copied from; never written.

## §2 Founding rulings

Banked 2026-08-24, before any code (bodies verbatim from the seed record):

1. **Best-fit per component.** Each subsystem lives in its strongest
   language: Rust provenance, Go services, C++ kernels, TypeScript
   faces/tooling, JSON interchange, SQLite state.
2. **Atlas lives beside the grounds.** `C:\Users\novad\Desktop\Archive\atlas\`;
   estate and secondbrain are read-only sources.
3. **Strangler migration.** Python estate keeps running; golden-master
   byte-parity required before any per-service cutover through the same
   ports/commands.
4. **Harvest the second brain.** Adopt patterns natively (Memory API v1 +
   split SQLite topology, SKILL.md spec, Guard/Redact/Scan, declarative
   deploys); no repo ported wholesale or wrapped.

## §3 Wall-widening record

The operator ordered the whole project recreated as a polyglot system
reconciling `estate\` and `secondbrain\`; a new folder was founded in
`Archive\` (`atlas`, a working name until he rules otherwise). This widened
the seat's wall from the Steward 1.0 folder to this ground; everything about
the atlas build stays inside this folder. Witnessed in `SEAT_LOG.md`
2026-08-24.

## §4 Standing laws

- **Fold, never delete.** Nothing is erased; the superseded is folded and
  kept whole. Corrections are new dated entries, never silent rewrites
  (THE_CATALOG rows are append-only; ACCEPTANCE amendments keep the old row
  visible; STATE_OF_BUILD and SEAT_LOG are append-only).
- **The gate.** Nothing lands without the operator's word. Never commit,
  never push — git history is created only by his hand (init commands are
  handed to him at close).
- **Read-only grounds.** estate and secondbrain are walked, never written;
  golden masters arrive as copies inside `tests\fixtures\`.
- **Testimony, proven.** Every stone exits through its proven mode; a model's
  answer is testimony until a prove witnesses it.

## §5 Versioning and the record

The build is versioned from root `VERSION` (semver + stone tag, currently
`0.1.0+p0`). Every binary answers `--version` with exactly that string;
bumps are witnessed per stone in `STATE_OF_BUILD.md`. Progress state lives
there (tail first); handoffs live in `SEAT_LOG.md`.

## §6 Build discipline

Implementation and testing move together: **venv** (Python only inside
`atlas\.venv`, pinned via `tools\make_venv.ps1`) · **sandboxing** (work stays
inside this folder; scratch on temp ground) · **hermetic proves** (every prove
runs on temp books and stub engines, never the live record).

---

## ADDENDUM — 2026-08-25: the overwrite incident, recorded

During the review sitting of 2026-08-25 the seat found `CHARTER.md` carrying,
byte-for-byte, the text of `specs\SPEC_COVENANT.md` v2 ("identity derivation
reference", two epochs) instead of the founding rulings. Evidence: file
content identical to the spec; mtime 2026-08-24 ~15:01 against ≤12:00 for all
other P0 docs; no witness entry in any append-only record covers the edit.
P0-01 (charter + rulings present) had silently regressed.

Disposition: this file is rebuilt from the held record (sources listed in the
header); nothing of the covenant text is kept here — identity law lives
solely at `specs\SPEC_COVENANT.md`, which is correct and frozen. The incident
is folded, not deleted: the overwritten state is fully preserved in that spec
and witnessed here and in `SEAT_LOG.md`. No blame is assigned by this seat;
if the operator made the change by his own hand, he may rule this addendum
amended accordingly.
