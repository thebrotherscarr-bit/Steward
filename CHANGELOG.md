# Changelog

All notable changes to ATLAS will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.1+f1] — 2026-09-08

### Added
- **E2E test suite**: 84 scenarios across 12 categories
  - S1: Binary Smoke (5), S2: MCP Tool Surface (8), S3: Write Tools (5)
  - S4: Mesh B2 (8), S5: Rack F1 (10), S6: Guard (5), S7: Tenant (4)
  - S8: Ollama Integration (10), S9: Webapp (6), S10: Cross-Impl (4)
  - S11: Agent Lifecycle (6), S12: Prove Chains (3)
- **6 CI/CD pipelines** (parallel jobs in ci.yml)
  - SPINE: Rust core (12 stages), LINE: Go MCP (11 stages)
  - GOLDEN: Python verifiers (11 stages), AGENT: 40-seat validation (11 stages)
  - WEBAPP: GUI + API (18 stages), OLLAMA: Live integration (14 stages)
- **6 agent workflows** with Python scripts
  - SCOUT: read-only survey (5 steps)
  - STEWARD: memory + testimony via Ollama (5 steps)
  - MESH: encrypted communication (7 steps)
  - GATE: injection blocking, PII stripping (5 steps)
  - TOWN: task scheduling (4 steps)
  - OPERATOR: full lifecycle (12 steps)
- **Ollama prover**: stdlib-only Python harness
  - Tests 11 models (qwen3.5, llama3.2, phi4-mini, gemma4, deepseek-r1, etc.)
  - Direct Ollama API + MCP integration + webapp API
  - JSON output, exit codes, timeout handling
- **Documentation**: PIPELINES.md, WORKFLOWS.md, OLLAMA_PROVER.md, ACCEPTANCE.md, E2E_SCENARIOS.md

### Changed
- `ci.yml` expanded from 1 pipeline to 6 parallel pipelines
- `generate` calls use chat API for thinking-model compatibility (qwen3.5)

## [0.1.0+f1] — 2026-09-08

### Added
- **Rust core**: prov-hash, ground-prove, atlas-api, store crates
- **Go MCP server**: 25 tools + HTTP transport + embedded GUI (port 8090)
- **Go TUI**: Dashboard, traces, agents, chain view, mesh, rack, format output
- **Go webapp**: Observability GUI with real-time SSE (port 8091)
  - Dashboard with stats, recent traces, agent roster
  - Agent registry with full .us declaration viewer
  - Trace log with SHA-256 hash chain
  - Tool surface with JSON argument invocation
  - Evaluations engine with pass/fail scoring
  - Message bus with Discord/Slack/WhatsApp adapters
  - Settings for MCP connection, eval thresholds, provenance
  - Search across agents and traces
- **Agent system**: 40 .us declarations validated, enrolled, documented
- **Skills**: prove, orient, enroll
- **Python verifiers**: cut_canon_vectors, cut_chain_verdicts, cut_us_vectors, fold_agents
- **TUI extractField**: Auto-find array field when `*` hits a map
- **YAML format**: Fixed `[]map[string]any` to `[]any` for type switch compatibility

### Governance
- `can_approve: false` structural enforcement across all 40 agents
- Covenant hash `1512741580b7239b` verified in all declarations
- Append-only witnesses: SEAT_LOG.md + STATE_OF_BUILD.md
- Forbidden verbs absent by construction
- Zero external dependencies enforced

### Documentation
- 54+ specification and design documents
- 40 agent documentation files with hierarchy index
- 3 skill documentation files
- GUI gap analysis (Atlas vs Langfuse/Langsmith)
- Build plan with phased acceptance criteria
- MIT License
- Contributing guide
- Full changelog

### Tests
- 92 Go tests (line workspace)
- 85 Rust tests (cargo test --workspace)
- 4 Python verifiers
- MCP 58-stroke prove
- TUI end-to-end verification against live MCP
- Agent enrollment validation (40/40)

### Fixed
- extractField: `agents.*.name` transform path now works correctly
- extractField: Auto-discovers first array-valued field when `*` encounters a map
- YAML format: `[]map[string]any` changed to `[]any` in rbac/agents list handlers
- TUI help: Changed `*.name` example to `name`
