# ATLAS Ollama Prover

**Version:** 0.1.5
**Ollama Backend:** 127.0.0.1:11434

---

## Purpose

The Ollama Prover is a stdlib-only Python test harness that:

1. Verifies Ollama connectivity and model availability
2. Tests model inference (generate, chat, embed)
3. Runs the MCP server against live Ollama via rack_ask
4. Executes 6 agent workflows through the MCP tool surface
5. Validates the full pipeline: Ollama → MCP → Tool → Trace → Chain

## Architecture

```
ollama_prover.py
├── OllamaClient          HTTP client for 127.0.0.1:11434
├── MCPClient             HTTP client for atlas-mcp on :8090
├── WebappClient          HTTP client for atlas-webapp on :8091
├── Scenario              Individual test scenario
├── Pipeline              Group of scenarios
├── Workflow              Agent workflow (multi-step)
└── Prover                Main orchestrator
```

## Usage

```powershell
# Full prove (all scenarios + workflows)
python tests/e2e/ollama_prover.py

# Scenarios only
python tests/e2e/ollama_prover.py --scenarios

# Workflows only
python tests/e2e/ollama_prover.py --workflows

# Specific category
python tests/e2e/ollama_prover.py --category s8

# Specific workflow
python tests/e2e/ollama_prover.py --workflow operator

# Verbose output
python tests/e2e/ollama_prover.py --verbose

# With MCP server management
python tests/e2e/ollama_prover.py --start-mcp

# Dry run (show what would run)
python tests/e2e/ollama_prover.py --dry-run
```

## Prerequisites

- Python 3.14 (stdlib only, no pip)
- Ollama running at 127.0.0.1:11434
- atlas-mcp binary built (`cd line && go build ./cmd/atlas-mcp`)
- atlas-webapp binary built (`cd webapp && go build .`)

## Test Categories

| Category | Scenarios | Description |
|---|---|---|
| S1 | 5 | Binary smoke tests |
| S2 | 8 | MCP tool surface |
| S3 | 5 | Write tools |
| S4 | 8 | Mesh B2 |
| S5 | 10 | Rack F1 |
| S6 | 5 | Guard |
| S7 | 4 | Tenant |
| S8 | 10 | Ollama integration |
| S9 | 6 | Webapp API |
| S10 | 4 | Cross-impl parity |
| S11 | 6 | Agent lifecycle |
| S12 | 3 | Prove chains |
| **Total** | **84** | |

## Workflows

| Workflow | Steps | Description |
|---|---|---|
| SCOUT | 5 | Read-only survey |
| STEWARD | 5 | Memory + testimony |
| MESH | 7 | Encrypted communication |
| GATE | 5 | Security + guard |
| TOWN | 4 | Task scheduling |
| OPERATOR | 12 | Full lifecycle |
| **Total** | **38** | |

## Output

```
=== ATLAS OLLAMA PROVER ===
Version: 0.1.5
Ollama: 127.0.0.1:11434

[S1] Binary Smoke .................. 5/5 PASS
[S2] MCP Tool Surface ............. 8/8 PASS
[S3] Write Tools .................. 5/5 PASS
[S4] Mesh B2 ...................... 8/8 PASS
[S5] Rack F1 ...................... 10/10 PASS
[S6] Guard ....................... 5/5 PASS
[S7] Tenant ...................... 4/4 PASS
[S8] Ollama Integration .......... 10/10 PASS
[S9] Webapp ...................... 6/6 PASS
[S10] Cross-Impl Parity .......... 4/4 PASS
[W1] SCOUT ....................... 5/5 PASS
[W2] STEWARD ..................... 5/5 PASS
[W3] MESH ....................... 7/7 PASS
[W4] GATE ....................... 5/5 PASS
[W5] TOWN ....................... 4/4 PASS
[W6] OPERATOR ................... 12/12 PASS

=== ALL PROVEN ===
Scenarios: 84/84 PASS
Workflows: 38/38 PASS
Total: 122/122 PASS
```

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | All pass |
| 1 | One or more failures |
| 2 | Prerequisites missing (Ollama, binaries) |
| 3 | Skip (Ollama unreachable, not failure)

## JSON Output

Results written to `tests/e2e/ollama_prover_results.json`:

```json
{
  "version": "0.1.5",
  "ollama": "127.0.0.1:11434",
  "timestamp": "2026-09-08T...",
  "scenarios": {
    "total": 84,
    "passed": 84,
    "failed": 0,
    "skipped": 0
  },
  "workflows": {
    "total": 38,
    "passed": 38,
    "failed": 0
  },
  "models_tested": [...],
  "duration_ms": 12345
}
```

## Failure Handling

- Ollama unreachable → skip S8 scenarios (exit 3, not 1)
- Model timeout (30s) → fail that scenario, continue
- MCP server crash → restart and retry once
- Chain TAMPER → immediate fail, abort remaining
- Guard bypass → critical fail, abort remaining
