# GUI GAP ANALYSIS — Atlas vs Market

*What the GUI has, what the market expects, what's missing. Simple.*

---

## What Atlas IS

Atlas is a **sovereign agent harness** — provenance + governance + observability
in one system. Not an LLM framework. Not a monitoring tool. A control plane
where every agent action is cryptographically verified and structurally constrained.

**Unique Atlas value:**
- Every trace has a hash receipt (SHA-256)
- Every agent has `can_approve:false` (structural, not policy)
- Every operation is append-only (fold, never delete)
- Multi-tenant isolation built-in
- Zero external dependencies

## What the GUI Has Now (6 pages)

| Page | What it does | What's missing |
|---|---|---|
| Dashboard | Health, version, tool count, system status | No live metrics, no agent status |
| Chain | SEAT_LOG viewer (last 20), verify button | No hash visualization, no entry detail |
| Agents | Muster list (names only) | No detail view, no hierarchy, no traces |
| RBAC | Role list, assign form | No policy viewer, no audit log |
| Trust | Empty state | No trust relationships shown |
| Tools | Tool list with args | No invocation, no history, no results |

## What the Market Expects (from Langfuse/Langsmith/AgentOps)

### Tier 1: Table Stakes (must have)

| Feature | Langfuse | Langsmith | Atlas Has |
|---|---|---|---|
| Per-agent trace view | Yes | Yes | **NO** |
| Agent graph visualization | Yes | Yes | **NO** |
| Step-by-step waterfall | Yes | Yes | **NO** |
| Tool call tracing | Yes | Yes | **NO** |
| Cost/latency per trace | Yes | Yes | **NO** |
| Search/filter traces | Yes | Yes | **NO** |
| Real-time monitoring | Yes | Yes | Partial (health poll) |
| Export traces | Yes | Yes | **NO** |
| Detail views (click in) | Yes | Yes | **NO** |

### Tier 2: Evaluation (what you want)

| Feature | Langfuse | Langsmith | Atlas Has |
|---|---|---|---|
| Evals framework | Yes (LLM-as-judge, heuristic) | Yes | **NO** |
| Trajectory evaluation | Yes | Yes | **NO** |
| Step-level evals | Yes | Yes | **NO** |
| Dataset from traces | Yes | Yes | **NO** |
| Experiment comparison | Yes | Yes | **NO** |
| Human annotation | Yes | Yes | **NO** |

### Tier 3: Verification (what Atlas ALREADY has)

| Feature | Langfuse | Langsmith | Atlas Has |
|---|---|---|---|
| Cryptographic receipts | No | No | **YES** |
| Hash chain integrity | No | No | **YES** |
| Structural enforcement | No | No | **YES** |
| Append-only audit trail | No | No | **YES** |
| Multi-tenant isolation | Partial | Partial | **YES** |
| Forbidden verbs | No | No | **YES** |

## The Gap: What Atlas Needs

### Priority 1: Per-Agent Dashboard (the core gap)

**What it is:** Click on an agent → see everything it did.

**What to build:**
- Agent detail page (`/agents/:id`)
- Trace list for that agent (tool calls, decisions, receipts)
- Hierarchy view (reports_to chain)
- Permission summary
- Activity timeline

**Market reference:** Langfuse trace list, Langsmith run view

### Priority 2: Trace/Span Visualization

**What it is:** See the flow of an agent's work as a graph or waterfall.

**What to build:**
- Trace list page (`/traces`)
- Each trace shows: agent, tool, timestamp, result, hash
- Waterfall view: sequential steps with timing
- Graph view: agent → tool → result → next step

**Market reference:** Langfuse agent graphs, AgentOps session replay

### Priority 3: Tool Invocation from GUI

**What it is:** Call any tool from the browser, see the result.

**What to build:**
- Tool call form on each tool page
- Input fields matching inputSchema
- Result display with hash receipt
- History of recent calls

**Market reference:** Langsmith playground, Langfuse tool calls

### Priority 4: Evals Framework

**What it is:** Evaluate agent outputs against criteria.

**What to build:**
- Eval definition page (`/evals`)
- Run evals on traces
- Score display (pass/fail/numeric)
- Compare eval results across runs

**Market reference:** Langfuse evaluations, Langsmith evals

### Priority 5: Search and Filter

**What it is:** Find anything quickly.

**What to build:**
- Global search bar (Cmd+K)
- Filter agents by name, office, reports_to
- Filter traces by agent, tool, time range
- Filter chain entries by date, kind

**Market reference:** Langfuse search, Langsmith SmithDB

### Priority 6: Real-Time Monitoring

**What it is:** See what's happening now.

**What to build:**
- Live agent status (idle/active/error)
- Live tool call feed
- Alert on failures
- Dashboard with live metrics

**Market reference:** Langfuse monitoring, AgentOps real-time

## The Atlas Advantage (what others don't have)

| Atlas Feature | Market Equivalent | Atlas Advantage |
|---|---|---|
| SHA-256 receipts | None | Every operation is cryptographically verifiable |
| Hash chain integrity | None | Tamper-evident audit trail |
| can_approve:false | None | Structural enforcement, not policy |
| Forbidden verbs | None | Absent by construction |
| Append-only record | None | Fold, never delete |
| Multi-tenant RBAC | Partial (Langfuse) | Built-in, not bolted on |

## Simple Build Path

### Phase A: Agent Detail (1-2 days)
- `/agents/:id` page
- Show .us declaration, permissions, reports_to
- Show recent tool calls (from MCP history)

### Phase B: Trace List (2-3 days)
- `/traces` page
- Record tool calls in memory (last N calls)
- Show agent, tool, timestamp, result, hash
- Click into trace detail

### Phase C: Tool Invocation (1 day)
- Call tool from browser
- Show result with hash receipt
- Store in trace list

### Phase D: Search (1 day)
- Global search bar
- Filter by agent, tool, time

### Phase E: Evals (3-5 days)
- Eval definition
- Run on traces
- Score display

**Total: 8-12 days for Tier 1 + Tier 2 coverage**

---

## Summary

Atlas has the **verification layer** (provenance, hashing, structural enforcement)
that Langfuse/Langsmith lack. What it's missing is the **observability layer**
(per-agent dashboards, traces, evals) that makes those tools useful.

The gap is not architectural — the MCP tools already exist. The gap is
**visualization** — the GUI doesn't show what the system already knows.

Build the per-agent dashboard first. That's the core. Everything else layers on top.
