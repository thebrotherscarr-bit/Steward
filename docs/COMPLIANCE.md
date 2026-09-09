# COMPLIANCE — EU AI Act and Regulatory Mapping

*How Atlas capabilities map to regulatory requirements.*

---

## 1. EU AI Act (Regulation (EU) 2024/1689)

### Article 12 — Record-keeping

**Requirement:** High-risk AI systems must automatically record events
(logs) over the lifetime of the system, enabling traceability.

| Atlas Capability | How It Satisfies |
|---|---|
| **JSONL hash chains** | Every action is recorded as a chain entry with SHA-256 hash, timestamp, and previous entry hash |
| **Append-only witnesses** | SEAT_LOG, STATE_OF_BUILD are append-only; corrections are new entries, never rewrites |
| **Chain verification** | `atlas chain verify` proves the record is untampered |
| **Merkle trees** | Tamper is pinpointed to the exact entry |
| **SQLite state** | Derived from chains; re-derivable at any time |

**Evidence:** `atlas chain verify --roots .` produces a verdict per chain.

### Article 14 — Human oversight

**Requirement:** High-risk AI systems must be designed to allow effective
human oversight, including the ability to not use or override the system.

| Atlas Capability | How It Satisfies |
|---|---|
| **`can_approve:false`** | Structural refusal — agents cannot self-approve; the operator holds the gate |
| **Forbidden verbs** | approve/ascend/commit/push/delete/reject/promote are absent-by-construction |
| **Operator gate** | Every stone exits through operator review; no auto-approve path |
| **REVIEW-only board** | Board operations are review-gated, not auto-approved |
| **`--dry` enrollment** | Agent enrollment can be previewed before commitment |

**Evidence:** Route table tests assert forbidden verb absence. `.us` parser
refuses missing `can_approve`. Every binary ships `--prove`.

### Article 19 — Logs

**Requirement:** Automatic recording of events over the lifetime of the
system to ensure traceability.

| Atlas Capability | How It Satisfies |
|---|---|
| **Hash chain entries** | Every entry has: timestamp, kind, sequence number, payload hash, previous hash, actor, body version |
| **Chain verdicts** | EMPTY/INTACT/FLIP/TAMPER — mathematical proof of record integrity |
| **Export round-trip** | `atlas db export --check` proves byte-identical reconstruction |
| **Golden-master parity** | `@atl/gm` proves replacement implementations match the original |
| **Hermetic proves** | Every test runs on temp grounds; reproducible by anyone |

**Evidence:** `atlas db export <chain> --check <original.jsonl>` produces
byte-identical output.

---

## 2. SOC 2

### CC6.1 — Logical access controls

| Atlas Capability | How It Satisfies |
|---|---|
| **Agent enrollment** | Agents must be declared in `.us` before acting |
| **Structural refusal** | Undeclared agents are refused by name |
| **reports_to chain** | Every agent has a resolvable authority chain |
| **Guard pipeline** | guardscan → gate → guardfetch for every external interaction |
| **RBAC** | Per-tenant role assignments with allow/deny permissions |

### CC7.2 — Monitoring

| Atlas Capability | How It Satisfies |
|---|---|
| **Chain verification** | Continuous integrity checking via `atlas chain verify` |
| **Hash chain entries** | Every action recorded with cryptographic hash |
| **Merkle trees** | Tamper detection with pinpoint accuracy |
| **Append-only records** | No silent overwrites; full audit history |

### CC8.1 — Change management

| Atlas Capability | How It Satisfies |
|---|---|
| **Golden-master parity** | Byte-for-byte proof before any cutover |
| **Append-only STATE_OF_BUILD** | Every change witnessed with date |
| **Rollback notes** | Every cutover has a documented rollback path |
| **Operator gate** | No change lands without operator approval |

---

## 3. ISO/IEC 42001 — AI Management System

### Clause 6.1.2 — AI risk assessment

| Atlas Capability | How It Satisfies |
|---|---|
| **Guard pipeline** | 5-risk-tier verdict book |
| **guardscan** | Argument scanning for injection, poison, PII |
| **gate** | Risk-tiered verdicts |
| **guardfetch** | Egress with private-IP refusal |

### Clause 7.5 — Documented information

| Atlas Capability | How It Satisfies |
|---|---|
| **CHARTER.md** | Founding rulings and standing laws |
| **ACCEPTANCE.md** | Testable acceptance criteria for every stone |
| **STATE_OF_BUILD.md** | Append-only progress log |
| **SEAT_LOG.md** | Append-only activity log |
| **THE_CATALOG.md** | Complete module inventory |
| **ADR collection** | Architecture decision rationale |

### Clause 8.3 — AI system development lifecycle

| Atlas Capability | How It Satisfies |
|---|---|
| **Stone-based build** | P0 → A1 → A2 → B1 → B2 → C1 → D1 → D2 → E1 → F1 → G |
| **Acceptance criteria** | Every stone has testable criteria in ACCEPTANCE.md |
| **Prove discipline** | Every binary ships `--prove`; every stone exits through proven mode |
| **E2E suite** | 65 tests across 9 layers; full system verification |

---

## 4. Comparison to Competitors

| Capability | Atlas | ProvenanceOne | Providex | Provedit |
|---|---|---|---|---|
| Hash chain provenance | ✅ SHA-256 + Merkle | ✅ Immutable chain | ✅ SHA-256 chained | ✅ Quantum-resistant |
| Structural refusal | ✅ Grammar rule | ❌ Policy flags | ❌ Policy gates | ❌ Policy gates |
| Cross-impl parity | ✅ Golden-master | ❌ | ❌ | ❌ |
| Socket-free kernels | ✅ CLI filters | ❌ | ❌ | ❌ |
| Agent declaration | ✅ .us format | ❌ | ❌ | ❌ |
| Forbidden verbs | ✅ Absent-by-construction | ❌ | ❌ | ❌ |
| Hermetic proves | ✅ Temp grounds | ❌ | ❌ | ❌ |
| Zero dependencies | ✅ Vendored/hand-rolled | ❌ | ❌ | ❌ |

---

## 5. Compliance Readiness Assessment

| Requirement | Status | Evidence |
|---|---|---|
| EU AI Act Art. 12 (record-keeping) | **Ready** | Hash chains + append-only witnesses |
| EU AI Act Art. 14 (human oversight) | **Ready** | can_approve:false + operator gate |
| EU AI Act Art. 19 (log retention) | **Ready** | Append-only + fold-never-delete |
| SOC 2 CC6.1 (access controls) | **Ready** | Agent enrollment + guard pipeline |
| SOC 2 CC7.2 (monitoring) | **Ready** | Chain verification + Merkle trees |
| SOC 2 CC8.1 (change management) | **Ready** | Golden-master parity + operator gate |
| ISO 42001 6.1.2 (risk assessment) | **Partial** | Guard pipeline; formal risk matrix needed |
| ISO 42001 7.5 (documented info) | **Ready** | Full documentation suite |
| ISO 42001 8.3 (dev lifecycle) | **Ready** | Stone-based build + acceptance criteria |

---

## 6. New Capabilities (Phase 2–3)

### HTTP API (Phase 2.1)

| Capability | Compliance Value |
|---|---|
| `GET /health` | System availability monitoring for SOC 2 CC7.2 |
| `GET /tools` | Tool surface auditability — enumerate all capabilities |
| `POST /rpc` | JSON-RPC 2.0 with full audit trail (every call is a request/response) |
| Loopback default | Network exposure is opt-in; zero egress by default |

### OpenAPI Spec (Phase 2.2)

| Capability | Compliance Value |
|---|---|
| Machine-readable API contract | SOC 2 CC6.1 — formal API specification for access control review |
| Endpoint documentation | ISO 42001 7.5 — documented information for API surface |

### Python SDK (Phase 2.3)

| Capability | Compliance Value |
|---|---|
| `chain_verify()` | Programmatic audit — compliance checks in automation pipelines |
| `agent_enroll()` | Automated enrollment with dry-run preview |
| `prove()` | Reproducible compliance evidence generation |

### W3C VC Adapter (Phase 3.1)

| Capability | Compliance Value |
|---|---|
| .us → VC conversion | Cross-system trust — present agent declarations to external auditors |
| `canApprove: false` in VC | Structural safety gate survives cross-system transport |
| DID scheme (`did:atlas:`) | Decentralized identity for agent verification |
| Optional signing | Cryptographic proof for tamper-evident credential presentation |

### SBOM (Phase 2.5)

| Capability | Compliance Value |
|---|---|
| CycloneDX SBOM | Supply chain transparency — SOC 2 CC6.1, EU Cyber Resilience Act |
| Zero external dependencies | Near-zero supply chain attack surface |
| Component inventory | ISO 42001 7.5 — documented information for all components |
