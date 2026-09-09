# ADR-002: Fold, Never Delete — Append-Only Record

**Status:** Accepted  
**Date:** 2026-08-24 (founding ruling)  
**Decider:** Operator (Kyler Carr)

## Context

Atlas operates in a context where:
- Audit trails must survive corrections
- Regulators (EU AI Act, SOC 2) require full history
- Agent actions must be traceable to their origin
- Mistakes happen; silent rewrites destroy trust

## Decision

Nothing is erased. Corrections are new dated entries, never silent rewrites.
This applies to:

| Record | Mechanism |
|---|---|
| SEAT_LOG.md | Append-only; entries never edited |
| STATE_OF_BUILD.md | Append-only; progress blocks appended |
| THE_ROAD.md | Append-only; status snapshots appended |
| THE_CATALOG.md | Append-only; new modules appended |
| JSONL hash chains | Append-only; each entry hashes the previous |
| .us declarations | Round-trip render(parse(x)) == x |

When a correction is needed:
1. Write a new dated entry explaining the correction
2. Reference the original entry
3. Mark the original as "folded" (superseded, kept whole)
4. The old state is fully preserved in the record

## Consequences

### Positive
- Full audit history is always visible
- Corrections are transparent and traceable
- Regulators can see exactly what changed and why
- No silent overwrites (like the CHARTER.md incident of 2026-08-24)

### Negative
- Storage grows monotonically (mitigated: JSONL is compact)
- Old entries may confuse readers (mitigated: fold notes explain context)
- Cannot "undo" in the traditional sense (mitigated: new entry supersedes)

### Precedent
- Git (immutable history)
- Blockchain (append-only ledgers)
- Accounting (double-entry bookkeeping)
- Legal records (amendments, not rewrites)
