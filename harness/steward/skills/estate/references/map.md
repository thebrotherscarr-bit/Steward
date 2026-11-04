# The estate: Neiro

Kyle's local, private system on this PC. Four parts, plus the models.

| Part | Codename | What it is | Where |
|---|---|---|---|
| Manjuel | Manjuel | The ground, the core, the semantic microkernel: the record, the laws, the rack of model seats, the REPL | `C:\Users\novad\Desktop\Research` (the ground) |
| SecondBrain | Jesster | The console: notes vault, Agent tab, the door's host, the Services window; starts and supervises your servers | `worlds/jesster` |
| Atlas | Aurora | The glass (web app) and the door (git and other writing tools for Kyle's repositories) | `atlas/` in the ground |
| Steward | Steward | You: a Microsoft Agent Framework harness agent on local Ollama | `worlds/steward` |
| Ollama | - | The model runtime: gpt-oss (you, `steward:1`), qwen2.5-coder (the Coder), embeddinggemma (`search_code`, on the CPU) | `127.0.0.1:11434` |

## How the parts connect to you

| Connection | Protocol | Port | Direction |
|---|---|---|---|
| SecondBrain's Agent tab -> you | OpenAI Responses (MAF's Responses host, `hosted.py`) | 43120 | Kyle talks to you; your cards appear there |
| Manjuel -> you | MCP (`mcp_app.py`) | 43121 | Manjuel calls you as a tool; approvals do not cross it |
| You -> SecondBrain | MCP (`/mcp`, SecondBrain's own server) | 43110 | His notes, skills, the web, and the door's tools |
| You -> the door | its tools (`atlas_*`) reach you through SecondBrain's MCP | 43110 | Every write parks a card for Kyle; the door itself listens on 43111 for Manjuel and the glass |
| The glass (Aurora) | HTTP | 8091 | Kyle's web app; SecondBrain keeps it running |
| You -> Ollama | Ollama's API (MAF's `OllamaChatClient`) | 11434 | Your models |
| DevUI (development only) | HTTP | 8080 | Not normally running |

## Who starts what
- **SecondBrain** serves its MCP on 43110, starts your service (43120) and your MCP door (43121), keeps them up, and
  writes their output to `steward.log` and `steward-mcp.log` in your workspace. It is also the door (43111) and
  supervises the glass (8091).
- **Ollama** runs as its own app today (SecondBrain can run it later, from its Services window).
- **Manjuel's REPL** is started by Kyle. A running REPL is a **sitting**: while it is open nothing in the ground is
  edited (the ground's RULE 9).

## Your records (inside your workspace; you can read these)
| What | Where |
|---|---|
| Your service's output | `steward.log`, `steward-mcp.log` |
| Traces, metrics, logs (OpenTelemetry) | `halo_traces/traces.jsonl`, `metrics.jsonl`, `logs.jsonl` |
| What FIDES would have blocked | `halo_traces/fides.jsonl` |
| Eval results, one line per run | `storage/evals/history.jsonl` |
| Which of your tools ask for a card | `storage/tool-policy.json` |
| Your memory | `agent-memory/` (topics), `agent-file-memory/` (files you keep) |
| The diagnosis handoff | `improvement_loop/latest/handoff.md` |
| The host's saved responses and checkpoints (14 days) | `storage/responses/`, `.as/` |

Outside your workspace, and not readable by you: the ground's records (sessions, the law chain), SecondBrain's own
logs and settings, and Ollama's `server.log`. Ask Kyle, or use the notes and door tools.

## Your reach
- **Now:** your own repository (`worlds/steward`). You read it freely; writes, shell commands and commits ask on
  Kyle's card. The door's writes are `project="steward"` only.
- **Later:** Kyle widens your reach one part at a time, "as needed", once you are reliable. Until then, a request
  about another part gets your reading of the map and a plain proposal, not an action.
