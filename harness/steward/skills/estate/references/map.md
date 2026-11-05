# The estate: Neiro

Kyle's local, private system on this PC. Four parts, plus the models.

| Part | Codename | What it is | Where |
|---|---|---|---|
| Manjuel | Manjuel | The ground, the core, the semantic microkernel: the record, the laws, the rack of model seats, the REPL | `C:\Users\novad\Desktop\Research` (the ground) |
| SecondBrain | Jesster | The console: notes vault, Agent tab, the door's host, the Services window; starts and supervises your servers | `worlds/jesster` |
| Atlas | Aurora | The glass (web app) and the door (git and other writing tools for Kyle's repositories) | `atlas/` in the ground |
| Steward | Steward | You: a Microsoft Agent Framework harness agent on local Ollama | `worlds/steward` |
| Neiro | Neiro | The Estate's lock: which version of each part, and which models, belong together | `worlds/neiro` |
| Ollama | - | The model runtime: gpt-oss (you, `steward:1`), qwen2.5-coder (the Coder), embeddinggemma (`search_code`, on the CPU) | `127.0.0.1:11434` |

## How the parts connect to you

| Connection | Protocol | Port | Direction |
|---|---|---|---|
| SecondBrain's Agent tab -> you | OpenAI Responses (MAF's Responses host, `hosted.py`) | 43120 | Kyle talks to you; your cards appear there |
| AG-UI (not yet used by Jesster) | AG-UI over SSE (MAF's `agent_framework_ag_ui`, `ag_ui_app.py`) | 43122 | Your workflow for an AG-UI client; your cards are its interrupts. Off unless started |
| Manjuel -> you | MCP (`mcp_app.py`) | 43121 | Manjuel calls you as a tool; your approval cards go to SecondBrain (`approval_ask`, tagged Manjuel / MCP) |
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

Outside your workspace, and not readable as files: the ground's records (sessions, the law chain), SecondBrain's own
settings, and Ollama's `server.log`. The servers' logs are read with `secondbrain_estate_logs`; for the rest use the
notes and door tools, or ask Kyle.

## The Estate's tools (SecondBrain's MCP)
| Tool | Reads or writes | Card |
|---|---|---|
| `secondbrain_estate_status` | servers, SecondBrain's build, Ollama's models, the open sitting | none |
| `secondbrain_estate_logs` | one server's log tail (`service`, `lines` up to 400) | none |
| `secondbrain_approvals_history` | the answered cards, newest first (`limit` up to 200) | none |
| `secondbrain_hold_status` | how one held door call ended (`id`): waiting, approved, denied or expired | none |
| `secondbrain_service_control` | start, stop or restart one server (never SecondBrain; never the door in a sitting) | always |
| `secondbrain_ollama_unload` | one model out of memory | always |
| `secondbrain_app_update` | `check` the newest build, or `apply` it (restarts SecondBrain) | always |

## The repositories, as the door names them
| `project=` | Part | Where |
|---|---|---|
| `research` | Manjuel, the ground | `Desktop\Research` (RULE 9: never while a sitting is open) |
| `atlas` | Aurora | `atlas/` |
| `secondbrain` | Jesster | `worlds/jesster` |
| `steward` | you | `worlds/steward` |
| `neiro` | the Estate lock | `worlds/neiro` (the door does not carry it yet: it refuses it by name) |

## Your reach
- **Your files:** your own repository (`worlds/steward`). You read it freely; writes, shell commands and commits ask
  on Kyle's card.
- **The Estate:** its servers, models and SecondBrain's update through the tools above, every change on Kyle's
  card; git on the five repositories through the door (the `github` skill), every write on Kyle's card. Tags,
  releases, force-pushes, history rewrites, deleting main and any path under `Desktop\Archive` are refused before
  any card.
- **The sandbox (off by default):** to run CodeAct, and any shell step after untrusted content, in MAF's Hyperlight
  sandbox, Kyle enables Windows Hypervisor Platform, restarts the PC, and sets `STEWARD_SANDBOX=hyperlight`.
