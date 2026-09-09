# ADR-003: can_approve:false — Structural Refusal

**Status:** Accepted  
**Date:** 2026-08-24 (A2 Registry stone)  
**Decider:** Operator (Kyler Carr)

## Context

AI agents can cause harm through:
- Self-approval (approving their own actions)
- Privilege escalation (granting themselves new capabilities)
- Silent authority (acting without explicit permission)

Traditional safety relies on policy documents and runtime flags. These can
be misconfigured, overridden, or forgotten.

## Decision

`can_approve` must be stated explicitly as `false` in every `.us` declaration.
The parser enforces this at the grammar level:

1. **Field present, value `false`:** Approved. The agent is declared safe.
2. **Field absent:** **Refused** (UsRefused error). Not a default — a refusal.
3. **Field present, any other value:** **Refused.**

This is structural enforcement, not policy:
- It is checked at parse time, before any action
- It cannot be overridden at runtime
- Absence is explicitly a refusal, never a default
- The parser refuses to process a declaration that doesn't explicitly say safe

## Consequences

### Positive
- Strongest safety guarantee in the market
- Agent cannot self-approve by omission
- Structural gate survives all refactoring
- Auditors can verify by parsing, not by inspecting runtime config
- Aligns with EU AI Act Article 14 (human oversight requirements)

### Negative
- Custom format (.us) rather than off-the-shelf JSON Schema
- Every agent must explicitly declare false (can't rely on defaults)
- New contributors must learn the .us format

### Comparison

| Approach | Strength | Failure Mode |
|---|---|---|
| Runtime flag (`approve=false`) | Config-level | Can be overridden at runtime |
| Policy document | Governance-level | Can be misinterpreted |
| **Grammar rule (`can_approve:false`)** | **Structural** | **Cannot be circumvented** |
| Absence = approval (default) | Permissive | Dangerous — omission grants authority |

### Novel Contribution
This pattern is not present in any competing standard:
- Agent Manifest v1.0: no approval semantics
- ADL (IETF): deny-by-default permissions, but no structural refusal
- AAE (IETF): mandate-based, not grammar-enforced
- ATN (IETF): capability intersection, not refusal-by-omission
