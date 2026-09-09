# ADR-005: Golden-Master Parity — Strangler Migration Proof

**Status:** Accepted  
**Date:** 2026-09-02 (C1 Faces stone, matured through D1/G-cutovers)  
**Decider:** Operator (Kyler Carr)

## Context

Atlas is a strangler migration: Python estate processes are being replaced
by polyglot (Rust/Go/C++/TS) implementations one service at a time. The
challenge: how do we prove the replacement is identical to the original
without introducing trust regression?

Options considered:
1. **Trust the rewrite** — too risky; bugs hide in rewrites
2. **Run both in parallel** — expensive; divergent state
3. **Byte-for-byte proof** — the golden-master approach

## Decision

Before any service cutover, `@atl/gm` (the golden-master harness) proves
byte-parity between the Python original and the polyglot replacement:

1. **Cut goldens from the read-only oracle FIRST** (Python cutter → JSON)
2. **Run the atlas artifact on identical input** (Rust/Go/TS consumer)
3. **Compare hashes byte-for-byte** (SHA-256 of output)
4. **Zero mismatches required** for cutover approval

This is not "the port passes its own tests" — that's circular. The Python
cutter is the oracle; the atlas artifact must match it exactly.

## Consequences

### Positive
- Trust regression is mathematically impossible (byte-parity = identical)
- Migration is provable, not just tested
- Rollback is safe (old process is unchanged, still running)
- Creates a reusable pattern for any strangler migration

### Negative
- Slower migration (must cut goldens before assertions)
- Python cutters must be maintained during the strangler period
- Some divergence is expected (floating-point tolerance in kernels)

### Verification
```bash
# Run all cutters and verify parity
python tests/e2e/test_suite.py --layer=8
# Expected: 17/17 ALL GREEN (all cutters PROVEN)

# Run the gm harness for a specific stone
atl gm run --stone A1
# Expected: 8/8 strokes green
```

### Pattern Name
This pattern is called **"Golden-Master Strangler Parity"**. It could be
documented as a reusable pattern for any polyglot migration where trust
regression is unacceptable.
