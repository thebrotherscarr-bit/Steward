# ATLAS Acceptance Criteria

**Version:** 0.1.1+f1

---

## Pipeline Acceptance

### SPINE (Rust Core)
- [ ] `cargo build --workspace` exits 0
- [ ] `cargo test --workspace` passes 85+ tests
- [ ] `atlas --version` prints `0.1.1+f1`
- [ ] `atlas chain verify` returns INTACT on lawful chain
- [ ] `atlas chain recognize` identifies form
- [ ] `atlas db init` creates database
- [ ] `atlas db import` imports chain
- [ ] `atlas db status` reports state
- [ ] `atlas agent enroll --dry` enrolls 40 agents
- [ ] `atlas orient --home .` prints line + road
- [ ] `atlas --prove` all strokes PASS
- [ ] `cargo test --doc` 3+ doc tests pass

### LINE (Go MCP)
- [ ] `go build ./...` exits 0
- [ ] `go vet ./...` clean
- [ ] `go test ./...` passes 92+ tests
- [ ] `atlas-mcp --describe` lists 72 tools
- [ ] `atlas-mcp --version` prints `0.1.1+f1`
- [ ] `atlas-mcp --prove` 58 strokes PASS
- [ ] `atlas-town --prove` 11 strokes PASS
- [ ] `atlas-door --prove` 13 strokes PASS
- [ ] `atlas-tui --version` prints `atlas-tui 0.1.1+f1`

### GOLDEN (Python)
- [ ] All 17 cutters `--verify` byte-identical
- [ ] `fold_agents.py --verify` byte-identical
- [ ] `check_trade_parity.py` cross-impl match

### AGENT (Declarations)
- [ ] 40 `.us` files in `agents/`
- [ ] 4 module maps in `agents/modules/`
- [ ] `can_approve` = 0 for all 40 agents
- [ ] Covenant hash `1512741580b7239b` in all 40
- [ ] `reports_to` resolves for all 40
- [ ] Undeclared actor refused by name
- [ ] 40 doc files in `agents/docs/`
- [ ] 3 skill files in `skills/`

### OLLAMA (Integration)
- [ ] Ollama responds at 127.0.0.1:11434
- [ ] >= 1 model listed
- [ ] Generate returns non-empty (qwen3.5:4b)
- [ ] Generate returns non-empty (llama3.2)
- [ ] Generate returns non-empty (phi4-mini)
- [ ] Tool calling returns tool_use
- [ ] Embedding returns vector
- [ ] rack_list returns voice ladder
- [ ] rack_ask returns answer + witness
- [ ] memory returns cited answer
- [ ] Guard blocks injection
- [ ] Webapp records trace
- [ ] Webapp records eval
- [ ] Full cycle: orient → ask → remember → verify

### WEBAPP (GUI)
- [ ] Build exits 0
- [ ] `go vet` clean
- [ ] Health endpoint returns status ok
- [ ] Version matches 0.1.1+f1
- [ ] List agents returns >= 40
- [ ] Get agent returns agent detail
- [ ] Add trace returns hash
- [ ] List traces returns traces
- [ ] Add eval returns eval
- [ ] Search returns results
- [ ] Settings get/set roundtrip
- [ ] Messages send + list works
- [ ] SSE stream opens
- [ ] Static files served (index.html, css, js)

## Workflow Acceptance

### SCOUT
- [ ] get_in_line returns protocol
- [ ] muster lists projects
- [ ] read_handoffs returns receipt
- [ ] state_matrix returns fold
- [ ] tenant_list returns tenants
- [ ] No writes performed
- [ ] Completes < 5s

### STEWARD
- [ ] rack_list returns voices
- [ ] rack_ask returns answer from Ollama
- [ ] memory returns cited answer
- [ ] remember stamps testimony
- [ ] verify_chain returns INTACT
- [ ] Completes < 30s

### MESH
- [ ] mesh_enroll admits alice
- [ ] mesh_enroll admits bob
- [ ] mesh_post lands open message
- [ ] mesh_post lands sealed message
- [ ] mesh_chain returns INTACT
- [ ] mesh_read returns messages
- [ ] mesh_read reveal opens sealed
- [ ] Completes < 15s

### GATE
- [ ] Injection attempt blocked
- [ ] PII stripped from question
- [ ] Poison markers flagged
- [ ] Outside path refused
- [ ] Normal question passes
- [ ] Completes < 15s

### TOWN
- [ ] get_in_line returns protocol
- [ ] remember stamps work order
- [ ] verify_chain returns INTACT
- [ ] state_matrix returns fold
- [ ] Completes < 10s

### OPERATOR
- [ ] All 12 steps PASS
- [ ] Chain INTACT at end
- [ ] Mesh chain INTACT
- [ ] All receipts present
- [ ] Completes < 30s

## Release Acceptance

- [ ] All 6 pipelines PASS
- [ ] All 84 scenarios PASS
- [ ] All 38 workflow steps PASS
- [ ] VERSION = 0.1.1+f1 in all 6 files
- [ ] All 6 binaries version-pinned
- [ ] Git clean (no uncommitted changes)
- [ ] DELIVERABLE.md present
- [ ] CHANGELOG.md updated
- [ ] LICENSE present (MIT)
