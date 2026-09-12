# ATLAS E2E Test Scenarios

**Version:** 0.1.5
**Ollama:** 127.0.0.1:11434 (11 models available)

---

## Scenario Categories

### S1: Binary Smoke (5 scenarios)
| # | Scenario | Binary | Expected |
|---|---|---|---|
| S1-1 | atlas --version | atlas | prints 0.1.5 |
| S1-2 | atlas-mcp --version | atlas-mcp | prints 0.1.5 |
| S1-3 | atlas-tui --version | atlas-tui | prints atlas-tui 0.1.5 |
| S1-4 | atlas-town --version | atlas-town | prints 0.1.5 |
| S1-5 | atlas-door --version | atlas-door | prints 0.1.5 |

### S2: MCP Tool Surface (8 scenarios)
| # | Scenario | Tool | Expected |
|---|---|---|---|
| S2-1 | Handshake | get_in_line | protocol 2025-06-18, standing law |
| S2-2 | Verify chain | verify_chain | verdict EMPTY/INTACT/FLIP/TAMPER |
| S2-3 | Muster | muster | lists carried projects |
| S2-4 | Read handoffs | read_handoffs | SEAT_LOG with sha256 receipt |
| S2-5 | List doctrine | list_doctrine | doctrine names |
| S2-6 | Check wall (inside) | check_the_wall | allows inside path |
| S2-7 | Check wall (outside) | check_the_wall | refuses quoting law |
| S2-8 | State matrix | state_matrix | fold(record) index |

### S3: Write Tools (5 scenarios)
| # | Scenario | Tool | Expected |
|---|---|---|---|
| S3-1 | Remember | remember | testimony stamped, hash chain intact |
| S3-2 | Remember (concurrent) | remember x2 | askLock serializes, chain INTACT |
| S3-3 | Remember (cap) | remember | 60k orientation cap holds |
| S3-4 | Read plan | read_plan | plan with receipt |
| S3-5 | Ask steward (refusal) | ask_steward | refuses honestly when no engine |

### S4: Mesh B2 (8 scenarios)
| # | Scenario | Tool | Expected |
|---|---|---|---|
| S4-1 | Enroll alice | mesh_enroll | admits with curve-bound key |
| S4-2 | Enroll bob | mesh_enroll | admits |
| S4-3 | Post open message | mesh_post | signed message lands |
| S4-4 | Post sealed message | mesh_post | ciphertext at rest |
| S4-5 | Walk chain | mesh_chain | INTACT, all signatures good |
| S4-6 | Read with reveal | mesh_read | opens sealed message |
| S4-7 | Read without reveal | mesh_read | withholds honestly |
| S4-8 | Tamper detection | mesh_chain | FLIP after byte change |

### S5: Rack F1 (10 scenarios)
| # | Scenario | Tool | Expected |
|---|---|---|---|
| S5-1 | List voices | rack_list | ladder with tiers (scout/voice/mind) |
| S5-2 | Outward refusal | rack_list | refuses non-loopback host |
| S5-3 | Silence honesty | rack_list | names silence when empty |
| S5-4 | Ask voice | rack_ask | routed answer with witness |
| S5-5 | Ask stranger refusal | rack_ask | refuses by name |
| S5-6 | Ask injection block | rack_ask | guard blocks injection |
| S5-7 | Open depth-1 | rack_open | voice card bundle |
| S5-8 | Open depth-2 | rack_open | adds ladder + memory |
| S5-9 | Open depth-3 | rack_open | adds project pack |
| S5-10 | Memory cited | memory | cited answer from ledger |

### S6: Guard (5 scenarios)
| # | Scenario | Tool | Expected |
|---|---|---|---|
| S6-1 | Injection block | rack_ask | guard blocks 13 poke patterns |
| S6-2 | PII strip | rack_ask | email/ssn/card/key stripped |
| S6-3 | Poison flags | rack_ask | zero-width/bidi/b64 flagged |
| S6-4 | Pipeline order | rack_ask | guard -> redact -> scan |
| S6-5 | Gate words | rack_ask | refusal quotes gate's words |

### S7: Tenant (4 scenarios)
| # | Scenario | Tool | Expected |
|---|---|---|---|
| S7-1 | List tenants | tenant_list | all registered projects |
| S7-2 | RBAC assign | tenant_rbac_assign | role assigned |
| S7-3 | RBAC check | tenant_rbac_check | permission reported |
| S7-4 | Trust grant | tenant_trust | trust level set |

### S8: Ollama Integration (10 scenarios)
| # | Scenario | Model | Expected |
|---|---|---|---|
| S8-1 | Health check | — | 127.0.0.1:11434 responds |
| S8-2 | List models | — | >=1 model listed |
| S8-3 | Generate (qwen3.5:4b) | qwen3.5:4b | non-empty completion |
| S8-4 | Generate (llama3.2) | llama3.2 | non-empty completion |
| S8-5 | Generate (phi4-mini) | phi4-mini | non-empty completion |
| S8-6 | Tool calling | qwen2.5-coder:7b | tool_use response |
| S8-7 | Embedding | nomic-embed-text-v2-moe | vector returned |
| S8-8 | Rack ask via MCP | qwen3.5:4b | answer through rack_ask |
| S8-9 | Rack ask with witness | qwen3.5:4b | witness line in ledger |
| S8-10 | Memory recall | — | cited answer matches |

### S9: Webapp (6 scenarios)
| # | Scenario | Endpoint | Expected |
|---|---|---|---|
| S9-1 | Health | GET /api/health | status ok, version 0.1.5 |
| S9-2 | List agents | GET /api/agents | count >= 40 |
| S9-3 | Add trace | POST /api/traces | trace with hash |
| S9-4 | Add eval | POST /api/evals | eval recorded |
| S9-5 | Search | GET /api/search?q=manjuel | results found |
| S9-6 | SSE stream | GET /api/events | event stream opens |

### S10: Cross-Impl Parity (4 scenarios)
| # | Scenario | Expected |
|---|---|---|
| S10-1 | All 17 cutters --verify | byte-identical |
| S10-2 | Fold agents --verify | byte-identical |
| S10-3 | Trade parity | cross-impl match |
| S10-4 | Chain fixture parity | oracle match |

### S11: Agent Lifecycle (6 scenarios)
| # | Scenario | Expected |
|---|---|---|
| S11-1 | Enroll all 40 | 40/40 dry run |
| S11-2 | can_approve invariant | 0 rows with can_approve != 0 |
| S11-3 | reports_to chain | all resolve to root |
| S11-4 | Covenant hash | 1512741580b7239b in all |
| S11-5 | Module map | 4 module maps parse |
| S11-6 | Refused actor | undeclared actor refused by name |

### S12: Prove Chain (3 scenarios)
| # | Scenario | Expected |
|---|---|---|
| S12-1 | MCP 58-stroke prove | all PASS |
| S12-2 | Town 11-stroke prove | all PASS |
| S12-3 | Door 13-stroke prove | all PASS |

---

## Total: 84 scenarios across 12 categories

| Category | Count | Time Est |
|---|---|---|
| S1: Binary Smoke | 5 | <5s |
| S2: MCP Tools | 8 | <30s |
| S3: Write Tools | 5 | <20s |
| S4: Mesh B2 | 8 | <30s |
| S5: Rack F1 | 10 | <60s (Ollama) |
| S6: Guard | 5 | <15s |
| S7: Tenant | 4 | <10s |
| S8: Ollama Integration | 10 | <120s |
| S9: Webapp | 6 | <15s |
| S10: Cross-Impl | 4 | <10s |
| S11: Agent Lifecycle | 6 | <10s |
| S12: Prove Chain | 3 | <60s |
| **Total** | **84** | **~6 min** |
