# ATLAS GUI/UX/IDE PLAN — The Operator's Surface

*How the operator interacts with Atlas: a browser-based control plane,
CLI enhancements, and IDE integration. Written 2026-09-07.*

---

## 1. Design Principles

1. **The operator is the approval.** The GUI never auto-approves. It presents
   evidence and lets the hand decide.
2. **The record is the UI.** Every view is derived from the hash chain. If the
   chain says X, the UI shows X. No separate database, no stale state.
3. **Prove in the browser.** Chain verification runs client-side. The operator
   can verify integrity without trusting the server.
4. **Fold, never delete.** The UI shows the full history. Corrections are new
   entries, not edits. The timeline is always visible.
5. **Zero external dependencies.** The web UI uses vanilla JS + WebCrypto.
   No React, no npm, no build step. Hand-rolled or refused.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    BROWSER (Operator's Hand)                 │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Dashboard   │  │  Chain View  │  │  Agent Manager   │   │
│  │  (status)    │  │  (timeline)  │  │  (.us viewer)    │   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  RBAC Panel │  │  Trust View  │  │  Audit Trail     │   │
│  │  (roles)    │  │  (delegates) │  │  (hash chain)    │   │
│  └─────────────┘  └──────────────┘  └──────────────────   │
├─────────────────────────────────────────────────────────────┤
│                    ATLAS HTTP API (:8090)                    │
│  GET /health · GET /tools · POST /rpc                       │
├─────────────────────────────────────────────────────────────┤
│                    SERVICE LAYER (Go)                        │
│  atlas-mcp · guard pipeline · RBAC · tenant registry        │
├─────────────────────────────────────────────────────────────┤
│                    SPINE (Rust)                              │
│  hash chains · merkle trees · agent enrollment              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Pages and Components

### 3a. Dashboard (`/`)

**Purpose:** At-a-glance system status. The operator's first view.

| Component | Data Source | Update |
|---|---|---|
| System health | `GET /health` | Poll 5s |
| Tenant count | `tenant_list` | On load |
| Tool count | `GET /tools` | On load |
| Chain status | `verify_chain` per tenant | On load + manual |
| Last action | `read_handoffs` tail | Poll 30s |
| RBAC assignments | `tenant_rbac_check` sweep | On load |

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  ATLAS · 0.1.0+f1 · operator                           │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│ HEALTH   │ TENANTS  │ TOOLS    │ CHAIN    │ LAST ACTION │
│ ok       │ 5        │ 25       │ INTACT   │ 2m ago      │
├──────────┴──────────┴──────────┴──────────┴─────────────┤
│                                                         │
│  [Chain Timeline]  [Agent Manager]  [RBAC]  [Trust]     │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Recent entries (last 10 from SEAT_LOG)         │   │
│  │  2026-09-07 14:23  manjuel  RBAC assigned...   │   │
│  │  2026-09-07 14:20  atlas    VC created...      │   │
│  │  ...                                             │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 3b. Chain View (`/chain`)

**Purpose:** Visualize the hash chain as a timeline. Prove integrity.

| Feature | Description |
|---|---|
| Timeline | Vertical chain of entries with hash links |
| Entry detail | Click to expand: timestamp, kind, payload, hash, prev |
| Verify button | Run `verify_chain` and show verdict per entry |
| Merkle tree | Optional tree view for tamper detection |
| Filter | By kind, actor, date range |

**Entry rendering:**
```
┌─────────────────────────────────────────┐
│  n=42  2026-09-07T14:23:00Z            │
│  kind=seat_log  actor=manjuel           │
│  hash: a1b2c3d4...  prev: e5f6g7h8...  │
│  payload: "RBAC assigned steward role"  │
│  verdict: INTACT ✓                      │
├─────────────────────────────────────────┤
│  n=41  2026-09-07T14:20:00Z            │
│  ...                                    │
└─────────────────────────────────────────┘
```

### 3c. Agent Manager (`/agents`)

**Purpose:** View and manage .us declarations.

| Feature | Description |
|---|---|
| Agent list | All 40+ .us files with status |
| Agent detail | Full .us JSON with validation |
| VC export | Convert .us → W3C Verifiable Credential |
| Enroll | Preview enrollment with `--dry` |
| Validation | Show schema validation results |

### 3d. RBAC Panel (`/rbac`)

**Purpose:** Manage role-based access control per tenant.

| Feature | Description |
|---|---|
| Tenant selector | Switch between tenants |
| Role list | Show all roles with permissions |
| Assignment matrix | Agent → Role mapping |
| Assign/revoke | Click to change assignments |
| Permission check | Test if agent can use tool |

### 3e. Trust View (`/trust`)

**Purpose:** Manage cross-tenant trust relationships.

| Feature | Description |
|---|---|
| Trust graph | Visual graph of tenant delegations |
| Add trust | Grant tool delegation between tenants |
| Revoke trust | Remove trust relationships |
| Audit | History of trust changes |

### 3f. Audit Trail (`/audit`)

**Purpose:** Full audit log with hash chain verification.

| Feature | Description |
|---|---|
| Filterable log | By actor, tool, tenant, date |
| Chain verification | Verify integrity per entry |
| Export | JSON/CSV export for compliance |
| SBOM view | CycloneDX component inventory |

---

## 4. Technical Implementation

### 4a. Static File Serving

Add to `httpserver.go`:
```
GET /          → index.html
GET /static/*  → static files (JS, CSS, icons)
```

All files served from `line/internal/httpserver/static/`.

### 4b. Client-Side Chain Verification

Using WebCrypto (SHA-256):
```javascript
async function verifyEntry(entry) {
  const data = entry.prev + entry.kind + entry.n + entry.payload;
  const hash = await crypto.subtle.digest('SHA-256', encoder.encode(data));
  return hex(hash) === entry.hash;
}
```

### 4c. WebSocket for Live Updates

```
GET /ws → WebSocket upgrade
```

Events:
- `chain.append` — new entry added
- `rbac.change` — role assigned/revoked
- `trust.change` — trust granted/revoked
- `agent.enroll` — new agent enrolled

### 4d. File Structure

```
line/internal/httpserver/
├── httpserver.go          # existing
├── static/
│   ├── index.html         # SPA entry
│   ├── css/
│   │   └── atlas.css      # minimal, no framework
│   ├── js/
│   │   ├── app.js         # router + state
│   │   ├── api.js         # HTTP/WS client
│   │   ├── chain.js       # chain verification
│   │   ├── dashboard.js   # dashboard page
│   │   ├── agents.js      # agent manager
│   │   ├── rbac.js        # RBAC panel
│   │   ├── trust.js       # trust view
│   │   └── audit.js       # audit trail
│   └── icons/
│       └── atlas.svg      # logo
```

---

## 5. CLI Enhancements

### 5a. `atlas-tui` (Terminal UI)

A terminal-based UI for operators who prefer the command line.
Built in Go using `tview` or hand-rolled ANSI.

```
atlas-tui --home .
```

**Views:**
- Dashboard (status grid)
- Chain viewer (scrollable timeline)
- Agent list (filterable)
- RBAC matrix

### 5b. `atlas gui` (Launch Browser)

Shortcut to start HTTP server and open browser:
```bash
atlas gui --home . --port 8090
# Starts server, opens http://localhost:8090
```

---

## 6. IDE Integration

### 6a. VS Code Extension (`atlas-vscode`)

**Features:**
1. **Chain viewer** — sidebar showing hash chain entries
2. **.us editor** — syntax highlighting + validation for .us files
3. **RBAC status** — show assigned role in status bar
4. **Prove runner** — run `--prove` from command palette
5. **Agent enrollment** — right-click .us file to enroll
6. **Chain verify** — verify chain integrity from editor

**File structure:**
```
ide/vscode/
├── package.json
├── src/
│   ├── extension.ts
│   ├── chainProvider.ts
│   ├── usLanguage.ts
│   ├── rbacStatus.ts
│   └── proveRunner.ts
├── syntaxes/
│   └── us.tmLanguage.json
└── icons/
    └── atlas-icon.png
```

### 6b. JetBrains Plugin (`atlas-jetbrains`)

**Features:**
1. **.us file support** — syntax highlighting + validation
2. **Tool window** — chain viewer + agent manager
3. **Run configuration** — `atlas-mcp --prove`
4. **Inspections** — flag invalid .us declarations

### 6c. Neovim Plugin (`atlas-nvim`)

**Features:**
1. **.us filetype** — syntax highlighting
2. **Chain viewer** — floating window
3. **Telescope integration** — search agents, tools
4. **LSP server** — .us validation

---

## 7. Design System

### 7a. Colors

```css
:root {
  --atlas-bg: #0a0a0f;        /* deep space */
  --atlas-surface: #12121a;   /* card background */
  --atlas-border: #1e1e2e;    /* borders */
  --atlas-text: #e0e0e0;      /* primary text */
  --atlas-muted: #6c7086;     /* secondary text */
  --atlas-accent: #89b4fa;    /* links, highlights */
  --atlas-green: #a6e3a1;     /* success, INTACT */
  --atlas-red: #f38ba8;       /* error, TAMPER */
  --atlas-yellow: #f9e2af;    /* warning, FLIP */
  --atlas-blue: #89dceb;      /* info */
}
```

### 7b. Typography

```css
body {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 14px;
  line-height: 1.5;
}
```

### 7c. Components

Minimal, no framework. Hand-rolled components:
- `Card` — surface with border
- `Badge` — status indicator (green/yellow/red)
- `Button` — action trigger
- `Table` — data grid
- `Timeline` — chain entry list
- `Modal` — detail view
- `Toast` — notification

---

## 8. MVP Scope

### Phase 1: Core Dashboard (Week 1)
- [ ] Static file serving in httpserver
- [ ] Dashboard page with health/status
- [ ] Chain viewer with verification
- [ ] Basic CSS design system

### Phase 2: Agent & RBAC (Week 2)
- [ ] Agent manager with .us viewer
- [ ] RBAC panel with assignment matrix
- [ ] Trust view with graph

### Phase 3: CLI Tools (Week 3)
- [ ] `atlas-tui` terminal UI
- [ ] `atlas gui` browser launcher

### Phase 4: IDE (Week 4)
- [ ] VS Code extension (.us support)
- [ ] Chain viewer sidebar
- [ ] Prove runner

---

## 9. Success Criteria

| Metric | Target |
|---|---|
| Dashboard loads | < 100ms |
| Chain verify (1000 entries) | < 500ms client-side |
| WebSocket latency | < 50ms |
| VS Code extension size | < 1MB |
| Zero npm dependencies | ✓ |
| Zero React/Vue/Angular | ✓ |
| Works offline | ✓ (after initial load) |

---

## 10. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| WebCrypto browser support | SHA-256 supported in all modern browsers |
| Large chain performance | Paginate, virtual scroll |
| WebSocket reliability | Reconnect with backoff |
| VS Code API stability | Pin API version |
| Offline verification | Cache chain data in IndexedDB |

---

*The operator's hand deserves a surface worthy of the gate it holds.*
