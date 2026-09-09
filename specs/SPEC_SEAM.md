# SPEC_SEAM — cross-language reconciliation contract

*Frozen reference for all stones. The glue that lets five codebases act as
one system without duplicating any trust-critical computation.*

## Rule of one computer

Every hash, canonicalization, signature, and seal verification is computed
in exactly one place: the Rust core. Services (Go), kernels (C++), and tools
(TS) never reimplement provenance math; they invoke it.

## Versioning

The build is versioned from the root `VERSION` file (semver + stone tag,
e.g. `0.1.0+p0`). Every binary answers `--version` with exactly that string;
bumps are witnessed per stone in STATE_OF_BUILD. Git history is created only
by the operator's hand.

## Go ↔ Rust (subprocess seam)

- Invocation: direct exec (no shell), argument array, working dir set.
- Contract version handshake: first stdout object carries
  `"atlas_seam": 1`. Mismatch = refuse.
- Output: exactly one JSON object on stdout.
  - Success: `{"ok": true, ...}` exit 0.
  - Refusal (lawful no): `{"ok": false, "refused": "<reason>"}` exit 2.
  - Error (broken): `{"ok": false, "error": "<message>"}` exit 1.
- Human-readable progress lines go to stderr only.
- Timeouts mandatory per call; kill on breach; never partial-trust output.

## C++ kernel filter seam

- Kernels read SQLite/JSONL/JSON inputs via `--db/--in` args or stdin;
  write one JSON result to stdout. Same ok/refused/error + exit-code shape.
- Kernels hold NO sockets and NO egress. Violation fails review.
- Numeric parity: integer counts bit-exact; floating results within the
  tolerance recorded beside each fixture (`tests/fixtures/`).

## TypeScript golden-master seam (`@atl/gm`)

- Runs a command pair (Python original vs atlas artifact) on identical
  input; canonicalizes outputs; compares byte-for-byte / hash-level.
- Report: `{"pair": ..., "input": sha256, "match": bool, "first_diff": ...}`.
- A stone's cutover requires zero mismatches across its fixture set.

## Trust invariants at every server surface

- Forbidden verbs are absent-by-construction from every route table:
  approve · ascend · merge · commit · push · delete · reject · promote.
  Each server ships a test asserting their absence.
- Egress only through `pkg/guardfetch` (private-IP refusal, allowlist,
  timeout). Tool-call arguments pass `pkg/guardscan`; verdicts land in the
  chained gate book (`pkg/gate`).
- Model output is stamped testimony end to end.

## Prove requirements

Each artifact proves its seam side: handshake honored, refusal shape
correct, timeout kills cleanly, forbidden-verb absence asserted.
