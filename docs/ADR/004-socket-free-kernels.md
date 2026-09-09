# ADR-004: Socket-Free Kernels — Zero Network Surface

**Status:** Accepted  
**Date:** 2026-09-05 (E1 Kernels stone)  
**Decider:** Operator (Kyler Carr)

## Context

C++ kernels perform numeric computation: PPMI embedding, corpus digestion,
prediction. These operations:
- Process sensitive data (corpus statistics, model weights)
- Run at high frequency (called by Go services)
- Must not leak data or accept external input during execution

Network sockets in kernels would:
- Create attack surface (remote code execution, data exfiltration)
- Complicate auditability (network activity is hard to trace)
- Violate the "Rule of One Computer" (kernels should compute, not communicate)

## Decision

C++ kernels are CLI filters with zero network surface:
- Read input via `--db/--in` args or stdin
- Write output to stdout (one JSON object)
- No `#include` of network headers
- No socket(), connect(), bind(), listen(), accept()
- Enforced by source scan in CI

## Consequences

### Positive
- Auditability by construction: no network = no exfiltration
- Simpler testing: CLI in, JSON out
- Faster: no socket overhead, no connection management
- Fits the seam contract: same ok/refused/error shape as Go↔Rust
- Proven by E1-04: socket scan finds zero network includes

### Negative
- No streaming (must buffer entire result in memory)
- No real-time progress (must wait for completion)
- No concurrent requests (one kernel invocation at a time per process)

### Mitigations
- Kernels are fast (PPMI: <100ms, predictor: <50ms for typical inputs)
- Go services can spawn multiple kernel processes for parallelism
- Streaming is unnecessary for the current use cases

### Verification
```
# E1-04: Socket scan
grep -r "socket\|connect\|bind\|listen\|accept" kernels/
# Expected: zero matches
```
