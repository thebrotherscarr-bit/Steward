# ATLAS 6 CI/CD Pipelines

**Version:** 0.1.2
**Ollama Backend:** 127.0.0.1:11434

---

## Pipeline 1: SPINE (Rust Core)

**Trigger:** push/PR to main
**Duration:** ~90s
**Runner:** ubuntu-latest

### Stages

| Stage | Command | Gate |
|---|---|---|
| build | `cargo build --workspace` | exit 0 |
| unit | `cargo test --workspace` | 85+ pass |
| version | `cargo run -q -p atlas -- --version` | prints 0.1.2 |
| chain-verify | `cargo run -q -p atlas -- chain verify tests/fixtures/chains/agents_seatlog.jsonl` | INTACT |
| chain-recognize | `cargo run -q -p atlas -- chain recognize tests/fixtures/chains/agents_seatlog.jsonl` | form recognized |
| db-init | `cargo run -q -p atlas -- db init /tmp/spine_test.db` | exit 0 |
| db-import | `cargo run -q -p atlas -- db import /tmp/spine_test.db estate tests/fixtures/chains/agents_seatlog.jsonl` | imported |
| db-status | `cargo run -q -p atlas -- db status /tmp/spine_test.db` | chains/pointers reported |
| agent-enroll | `cp data/master.db /tmp/spine_enroll.db && cargo run -q -p atlas -- agent enroll /tmp/spine_enroll.db --dir agents --dry` | 40 enrolled |
| orient | `cargo run -q -p atlas -- orient --home .` | line + road + log-tail |
| prove | `cargo run -q -p atlas -- --prove` | strokes PASS |
| doc-tests | `cargo test --doc` | 3+ pass |

### Artifacts
- `target/debug/atlas` binary
- test results JSON

### Failure Policy
- Any stage fails → pipeline fails
- Version mismatch → immediate fail
- Chain TAMPER → immediate fail

---

## Pipeline 2: LINE (Go MCP + Tools)

**Trigger:** push/PR to main
**Duration:** ~120s
**Runner:** ubuntu-latest

### Stages

| Stage | Command | Gate |
|---|---|---|
| build-line | `cd line && go build ./...` | exit 0 |
| vet-line | `cd line && go vet ./...` | clean |
| test-line | `cd line && go test ./...` | 92+ pass |
| build-webapp | `cd webapp && go build ./...` | exit 0 |
| vet-webapp | `cd webapp && go vet ./...` | clean |
| mcp-tools | `cd line && go run ./cmd/atlas-mcp --prove` | surface carries 78 tools |
| mcp-version | `cd line && go run ./cmd/atlas-mcp --version` | 0.1.2 |
| mcp-prove | `cd line && go run ./cmd/atlas-mcp --prove` | 125 strokes PASS |
| town-prove | `cd line && go run ./cmd/atlas-town --prove` | 11 strokes PASS |
| door-prove | `cd line && go run ./cmd/atlas-door --prove` | 13 strokes PASS |
| tui-version | `cd line && go run ./cmd/atlas-tui --version` | atlas-tui 0.1.2 |

### Artifacts
- `atlas-mcp`, `atlas-tui`, `atlas-town`, `atlas-door` binaries
- `atlas-webapp` binary
- prove results

### Failure Policy
- Go vet clean → fail on warning
- Any prove stroke fails → pipeline fails
- Tool count < 20 → fail

---

## Pipeline 3: GOLDEN (Python Verifiers)

**Trigger:** push/PR to main
**Duration:** ~60s
**Runner:** ubuntu-latest

### Stages

| Stage | Command | Gate |
|---|---|---|
| setup-python | `python3.14 --version` | 3.14 |
| cut-canon | `python tools/cut_canon_vectors.py` | vectors.json created |
| verify-canon | `python tools/cut_canon_vectors.py --verify` | byte-identical |
| cut-chain | `python tools/cut_chain_verdicts.py` | verdicts.json created |
| verify-chain | `python tools/cut_chain_verdicts.py --verify` | byte-identical |
| cut-us | `python tools/cut_us_vectors.py` | us_vectors.json created |
| verify-us | `python tools/cut_us_vectors.py --verify` | byte-identical |
| fold-agents | `python tools/fold_agents.py` | fold applied |
| verify-fold | `python tools/fold_agents.py --verify` | byte-identical |
| all-cutters | `for f in tools/cut_*.py; do python "$f" --verify; done` | 12 byte-identical, 12 ABSENT (oracle) |
| trade-parity | `python tools/check_trade_parity.py` | cross-impl match |

### Artifacts
- verification results
- cutter outputs

### Failure Policy
- Any --verify fails → pipeline fails
- Byte mismatch → immediate fail
- Trade parity mismatch → fail

---

## Pipeline 4: AGENT (40-seat Validation)

**Trigger:** push/PR to main
**Duration:** ~45s
**Runner:** ubuntu-latest

### Stages

| Stage | Command | Gate |
|---|---|---|
| build-atlas | `cargo build -p atlas` | exit 0 |
| copy-master | `cp data/master.db /tmp/agent_test.db` | file exists |
| enroll-dry | `cargo run -q -p atlas -- agent enroll /tmp/agent_test.db --dir agents --dry` | 40 enrolled |
| file-count | `ls agents/*.us \| wc -l` | 40 files |
| module-count | `ls agents/modules/*.us \| wc -l` | 4 module maps |
| can-approve | SQL check: `SELECT count(*) FROM agents WHERE can_approve != 0` | 0 rows |
| covenant-hash | `grep -r "1512741580b7239b" agents/` | 40 matches |
| reports-to | Verify all reports_to resolve | no orphans |
| refused-actor | Attempt enroll of undeclared actor | refused by name |
| docs-check | `ls agents/docs/*.md \| wc -l` | 41 doc files |
| skill-check | `ls skills/*/SKILL.md \| wc -l` | 3 skills |

### Artifacts
- enrollment report
- validation results

### Failure Policy
- Count mismatch → fail
- can_approve != 0 found → critical fail
- Covenant hash missing → fail
- Orphaned reports_to → fail

---

## Pipeline 5: OLLAMA (Live Integration)

**Trigger:** manual dispatch or nightly
**Duration:** ~180s
**Runner:** ubuntu-latest (with Ollama) or local
**Requires:** Ollama at 127.0.0.1:11434

### Stages

| Stage | Command | Gate |
|---|---|---|
| health | `curl http://127.0.0.1:11434/api/tags` | 200 OK |
| list-models | Parse response, count >= 1 | models listed |
| generate-qwen | POST /api/generate with qwen3.5:4b | non-empty response |
| generate-llama | POST /api/generate with llama3.2 | non-empty response |
| generate-phi | POST /api/generate with phi4-mini | non-empty response |
| tool-calling | POST /api/chat with tool schema | tool_use in response |
| embedding | POST /api/embed with nomic-embed-text | vector returned |
| rack-ladder | Start MCP, rack_list via HTTP | voices listed in tiers |
| rack-ask | Start MCP, rack_ask via HTTP | answer + witness |
| memory-recall | Start MCP, memory after rack_ask | cited answer |
| guard-injection | Start MCP, rack_ask with injection | blocked by guard |
| webapp-trace | Start webapp, POST /api/traces | trace with hash |
| webapp-eval | Start webapp, POST /api/evals | eval recorded |
| full-cycle | orient → rack_ask → remember → verify_chain | all PASS |

### Models Under Test

| Model | Size | Capabilities | Role |
|---|---|---|---|
| qwen3.5:4b | 3.4GB | completion, tools, thinking | Scout tier |
| qwen3.5:9b | 6.6GB | completion, tools, thinking, vision | Voice tier |
| qwen2.5-coder:7b | 4.7GB | completion, tools, insert | Voice tier |
| qwen2.5-coder:14b | 9.0GB | completion, tools, insert | Mind tier |
| llama3.2 | 2.0GB | completion, tools | Scout tier |
| phi4-mini | 2.5GB | completion, tools | Scout tier |
| deepseek-r1:8b | 5.2GB | completion, thinking | Voice tier |
| gemma4:12b | 7.6GB | completion, tools, thinking, vision | Voice tier |
| gemma4:e4b | 9.6GB | completion, tools, thinking | Mind tier |
| qwen3-vl:8b | 6.1GB | vision, completion, tools, thinking | Voice tier |
| nomic-embed-text-v2-moe | 958MB | embedding | Embedder |

### Artifacts
- Ollama integration test results
- Model response times
- Rack ladder output

### Failure Policy
- Ollama unreachable → skip (not fail) with warning
- Model timeout (30s) → fail that model, continue others
- Rack ask empty → fail
- Guard bypass → critical fail

---

## Pipeline 6: WEBAPP (GUI + API)

**Trigger:** push/PR to main
**Duration:** ~60s
**Runner:** ubuntu-latest

### Stages

| Stage | Command | Gate |
|---|---|---|
| build | `cd webapp && go build -o atlas-webapp .` | exit 0 |
| vet | `cd webapp && go vet ./...` | clean |
| start | `./atlas-webapp &` (port 8091) | process running |
| health | `curl http://localhost:8091/api/health` | status ok |
| version | Response contains 0.1.2 | version matches |
| list-agents | `curl http://localhost:8091/api/agents` | count >= 40 |
| get-agent | `curl http://localhost:8091/api/agents/manjuel` | agent found |
| add-trace | `POST /api/traces` with test data | trace with hash |
| list-traces | `GET /api/traces` | traces listed |
| get-trace | `GET /api/traces/{id}` | trace + evals |
| add-eval | `POST /api/evals` with test data | eval recorded |
| list-evals | `GET /api/evals` | evals listed |
| search | `GET /api/search?q=atlas` | results found |
| settings | `GET/POST /api/settings/test-key` | get/set roundtrip |
| messages | `POST /api/messages/send` + `GET /api/messages` | message stored |
| sse | `GET /api/events` | event stream opens |
| static | `GET /` | index.html served |
| css | `GET /css/app.css` | stylesheet served |
| js-api | `GET /js/api.js` | JS served |
| js-app | `GET /js/app.js` | JS served |
| kill | Stop webapp process | clean exit |

### Artifacts
- webapp binary
- API test results
- coverage report

### Failure Policy
- Build fail → pipeline fail
- Any API endpoint returns error → fail
- Static file 404 → fail
- SSE timeout → fail

---

## Pipeline Summary

| Pipeline | Stages | Duration | Trigger |
|---|---|---|---|
| SPINE | 12 | ~90s | push/PR |
| LINE | 11 | ~120s | push/PR |
| GOLDEN | 11 | ~60s | push/PR |
| AGENT | 11 | ~45s | push/PR |
| OLLAMA | 14 | ~180s | manual/nightly |
| WEBAPP | 18 | ~60s | push/PR |
| **Total** | **77** | **~9 min** | — |

## Orchestration

All 6 pipelines run in parallel on push/PR. The `ci.yml` workflow orchestrates them as parallel jobs. OLLAMA runs only on manual dispatch or nightly schedule (requires Ollama backend).

```
push/PR → ci.yml
  ├── SPINE (Rust)
  ├── LINE (Go)
  ├── GOLDEN (Python)
  ├── AGENT (Declarations)
  ├── WEBAPP (GUI)
  └── OLLAMA (manual/nightly)
```

For release, `release.yml` runs all 6 as a gate before cross-platform build.
