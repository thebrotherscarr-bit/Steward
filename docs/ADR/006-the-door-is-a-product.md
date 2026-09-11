# ADR-006: The Door Is a Product — `atlas-mcp` as a Standalone MCP Server

**Status:** Proposed
**Date:** 2026-09-11
**Decider:** Operator (Kyle Carr)
**Supersedes:** nothing. **Cites:** ADR-001 (polyglot seam), ADR-004 (socket-free kernels)

## Context

The door arrived as part of the atlas package and was never combed through. It
is now the single surface every other thing in the estate reaches the record
through — the dashboard, the engine, the git verbs — and it has failed on two
consecutive days in two unrelated ways. The operator's ruling that opened this
review: *"set this as our proprietary MCP that works without our system
perfectly."*

That sentence contains the whole question. **Is the door a component of the
manjuel estate, or is it a product that happens to be used by it?** Until now
nobody had measured which, so every change was made as if it were the former.

### What was measured, not assumed

Everything below was obtained by running the door, not by reading it.

**It is already a conforming MCP server.** Started in stdio mode with one plain
tenant and **no `--manjuel` at all**:

    initialize  ->  protocolVersion 2025-06-18
                    serverInfo: atlas-mcp
                    capabilities: ["tools"]
    tools/list  ->  78 tools
                    without a description: 0
                    without an inputSchema: 0

**It is already 96% independent of manjuel.** Of the 78 tools, classified by
what their bodies actually reach for:

| Depends on | Count | Which |
|---|---|---|
| the engine (`--manjuel`) | 2 | `env_open`, `run_start` |
| the Rust spine (`--atlas-bin`) | 1 | `verify_chain` |
| neither | 75 | everything else |

**And the coupling is file-scoped, not smeared.** `internal/tools` is 4,987
lines; the manjuel-shaped part of it is three files:

    proofs.go     195   reads tests/last_run.json, run_history.jsonl, sessions.jsonl
    seats.go      164   reads agents/*.md, pipelines.md
    runstream.go  133   streams a turn from the engine
                  ---
                  492   9.9% of the package

**It already degrades honestly.** Against a tenant with no manjuel layout
(atlas itself — a plain git repo), nine representative tools:

| Tool | Result | What it said |
|---|---|---|
| `git` | ok | real branch, ahead/behind, dirty counts |
| `muster` | ok | the carried projects |
| `read_handoffs` | ok | the document, with a sha256 |
| `check_the_wall` | ok | jailed the path correctly |
| `seats` | ok | `{"seats": [], "pipelines_error": "never run in this world"}` |
| `proofs` | ok | `{"parity_error": "never run in this world", …}` |
| `records` | refused | *no kind "doctrine" in atlas. Kinds carried: record (3), spec (2)…* |
| `env_open` | refused | *no engine wired: atlas-mcp was started without `--manjuel`…* |
| `verify_chain` | refused | **`exit status 1`** |

Eight of nine are exemplary: they either answer, or they refuse while naming
what *is* there and what is missing. The ninth is the defect.

## Decision

**Treat the door as a product with a published contract, not as estate
plumbing.** Concretely, three things become rules rather than habits:

### 1. The dependency tiers are declared, and a tool states its tier

Every tool belongs to exactly one tier, declared in its registration:

| Tier | Needs | Contract |
|---|---|---|
| **CORE** | nothing but a directory | Must work against any tenant, on any machine. 75 tools today. |
| **SPINE** | the Rust binary | May refuse if unbuilt — but must say *which binary* and *how to build it*. |
| **ENGINE** | `--manjuel` | May refuse if unwired — but must name the missing flag. |

The tier is not documentation; it is a field the registry carries, so
`tools/list` can be filtered and a CORE tool that reaches for the engine fails
its own test rather than someone's review.

### 2. A refusal names its cause. `exit status N` is a lie by omission.

`httpserver.go:267-272` currently does this:

```go
out, err := s.tools.Call(...)
if err != nil {
    return resultResponse(req.ID, map[string]any{
        "isError": true,
        "content": []map[string]any{{"type": "text", "text": err.Error()}},
    })
}
```

`out` is discarded one line before it would have been sent. `verify_chain`
captures the spine's `CombinedOutput` into `out` and returns `(out, err)` — so
the real diagnosis was in hand and thrown away in favour of `exit status 1`.
**This is protocol-level and affects every tool that errors**, not just the one
that exposed it. The rule: when a tool errors and produced output, the client
receives the output, and the Go error only when there is nothing else.

### 3. There is ONE spawn contract, and every seam uses it

The door is a process supervisor with six seams, and the contract at each is
invented locally:

    engine.go:264    the engine        StdinPipe        (correct — it is the wire)
    tools.go:242     the Rust spine    nil stdin        resolver added 2026-09-11
    tools.go:2276    ask_steward       nil stdin
    gitctl.go:53     git               Stdin = devnull
    gitstate.go:39   git               Stdin = devnull
    door.go:65       the Rust spine    nil stdin        its own private resolver

Two close stdin explicitly; the rest rely on Go's default (which is safe — a
nil `Stdin` gets `os.DevNull` — so this is inconsistency, not a live bug).
Two resolve a binary by walking the tree; the rest assume PATH. One parses a
command string with a hand-written splitter. A single `spawn(bin, args, opts)`
helper replaces six local decisions with one reviewable one.

## Options Considered

### Option A: Leave it as estate plumbing

| Dimension | Assessment |
|---|---|
| Complexity | None — no work |
| Cost | Zero now, compounding later |
| Scalability | Poor: every new consumer re-discovers the coupling |
| Familiarity | Highest |

**Pros:** nothing to do. The door already works for its one caller.
**Cons:** the two-day failure streak is the cost, already being paid. The MCP
protocol layer — the part a second consumer touches first — is the least
tested code in the door (below). Nothing stops tier drift.

### Option B: Extract a separate `mcp-core` repository

| Dimension | Assessment |
|---|---|
| Complexity | High — a third repo, a third CI, a version seam |
| Cost | Weeks |
| Scalability | Good |
| Familiarity | Low |

**Pros:** genuine independence, enforced by the compiler.
**Cons:** the estate is one operator on one machine (SPEC §1). A third repo
triples the packaging problem that is *currently unsolved for two*. The
measured coupling is 492 lines in three files — extraction buys a boundary that
a declared tier buys for a tenth of the cost.

### Option C: Declare the contract in place *(recommended)*

| Dimension | Assessment |
|---|---|
| Complexity | Low — a field, an error path, a helper |
| Cost | Days |
| Scalability | Good enough for the next consumer |
| Familiarity | High — same repo, same build |

**Pros:** buys the property the operator asked for (works without our system)
without buying a repo split. Each of the three rules is independently testable,
so the contract is *proved* rather than asserted.
**Cons:** the boundary is enforced by tests, not by the compiler. A determined
hand can still reach across it.

## Trade-off Analysis

The decisive number is **75 of 78**. The door is not entangled with manjuel; it
is a general-purpose MCP over a filesystem, a git repo and a record, with three
tools that reach into the estate's own machinery. Option B pays a repo-split
price for a separation that already exists in the code. Option A keeps paying
the failure price. Option C writes down what is already true and puts tests
behind it.

The second number is **1,979** — lines in the door with *zero* tests:

| Package | Source | Tests |
|---|---|---|
| `internal/httpserver` | 800 | **0** |
| `internal/tenant` | 288 | **0** |
| `internal/ground` | 200 | **0** |
| `internal/vc` | 200 | **0** |
| `internal/rbac` | 187 | **0** |
| `internal/protocol` | 179 | **0** |
| `internal/orient` | 125 | **0** |

**The MCP protocol layer and the tenant model — the two things that define the
door as a product — are the two least tested things in it.** That is not a
coincidence with the two-day failure streak; it is its explanation. And
`internal/ground` (0 tests) holds `Siblings()`, which enumerates the parent of
the detected ground and adopts whatever carries an `AGENTS.md`. Launched from
the ground root, that parent is `Desktop`, which is how a world outside the
estate arrived on the dashboard on 2026-09-11.

## Consequences

**Easier:** a second consumer can point any MCP client at the door and get 75
working tools against any directory. A CORE tool that reaches for the engine is
caught by its own test. A refusal tells the caller what to do about it.

**Harder:** every new tool must choose a tier and defend it. `tools/list` grows
a filter that must stay correct.

**To revisit:** `ground.Siblings()` is a deliberate feature ("SEE THE TOWN")
that reaches outside the ground by design. Under a declared contract it becomes
opt-in, not default — but that is a behaviour change and is the operator's call,
tracked separately from this ADR.

## Action Items

1. [ ] **Send the tool's own output on error.** One line in
       `httpserver.go:269`. Protocol-level; fixes `verify_chain`'s bare
       `exit status 1` and every future one. Test: a tool that writes to stdout
       and exits non-zero must surface the text, not the status.
2. [ ] **Add a `Tier` field to `Tool`** and set it on all 78. Test: every
       CORE tool answers against an empty temp directory without an engine or
       a spine wired.
3. [ ] **First tests for `internal/httpserver`** — `initialize` returns the
       pinned protocol version; `tools/list` returns a description and an
       inputSchema for every tool; an unknown method is `-32601`; an unknown
       tool is `-32602`; a tool error is `isError` with the tool's own text.
4. [ ] **First tests for `internal/tenant` and `internal/ground`** — an unknown
       project refuses by name; `Siblings()` returns exactly what it is
       pointed at and never crosses a level it was not given.
5. [ ] **One `spawn()` helper**, used by all six seams.
6. [ ] **The 14 ABSENT prove legs** are the golden cutters naming source
       grounds that do not ship (`tests/prove.py --check`: 21 held, 14 absent,
       0 broke). Standalone means those goldens are re-cut from material that
       travels, or the legs are retired. Tracked separately — it is the same
       ruling as this ADR applied to the fixtures.

---

*Every number in this ADR was produced by running the door on 2026-09-11:
`tools/list` over stdio with no engine wired, nine `tools/call` against a
manjuel-free tenant, `go test ./...` (16 packages green), and
`python tests/prove.py --check`.*
