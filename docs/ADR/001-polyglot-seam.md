# ADR-001: Polyglot Seam — Rust Core, Go Services, C++ Kernels, TypeScript Tooling

**Status:** Accepted  
**Date:** 2026-08-24 (founding ruling)  
**Decider:** Operator (Kyler Carr)

## Context

Atlas reconciles ~230 source modules across a Python estate and a harvested
second brain. The modules serve different purposes: provenance math, service
routing, numeric computation, and developer tooling. No single language is
optimal for all four.

## Decision

Each subsystem lives in its strongest language:

| Language | Role | Rationale |
|---|---|---|
| **Rust** | Provenance core (hashing, canonicalization, signing, chain verification, .us parsing) | Memory safety without GC; zero-cost abstractions for crypto; single binary |
| **Go** | Services (MCP server, town beat, door HTTP, guard pipeline) | Fast compilation; goroutines for concurrency; stdlib HTTP/MCP |
| **C++** | Numeric kernels (PPMI embedder, digest, predictor) | Maximum numeric performance; SIMD; no runtime overhead |
| **TypeScript** | Developer tooling (CLI, golden-master harness, faces) | Fast iteration; Node.js ecosystem; JSON-native |
| **JSON** | Declarations, contracts, fixtures | Human-readable; machine-parseable; universal interchange |
| **SQLite** | Derived state (7 databases) | Embedded; zero-config; WAL mode for concurrent reads |

## Consequences

### Positive
- Every subsystem is written in its strongest language
- Provenance math is computed in exactly one place (Rust core)
- Services invoke Rust via subprocess; they never reimplement
- C++ kernels are socket-free CLI filters; auditability by construction

### Negative
- Four build systems (cargo, go build, g++, tsc)
- Cross-language seam contracts must be explicitly defined (SPEC_SEAM)
- Subprocess invocation has overhead (mitigated by: crypto operations are
  fast relative to network/LLM latency)

### Mitigations
- SPEC_SEAM defines the exact JSON-on-stdout contract
- Handshake versioning ensures compatibility
- Timeouts mandatory per call; kill on breach
