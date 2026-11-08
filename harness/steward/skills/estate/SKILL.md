---
name: estate
description: Run Kyle's estate (Neiro) - Manjuel, SecondBrain (Jesster), Atlas (Aurora), Ollama and you - its servers, logs, models, SecondBrain's update and the approvals history, on Kyle's card for every change. Use when a request names a part of the estate, a server, a port, a log, a model in memory, an update or a past card; when something is down, slow or stuck; or before any step that reaches beyond your own workspace.
---

## Usage

Read first, every time. Then change one thing, on the card, and read again.

1. **Look.** Call `secondbrain_estate_status`: every server (name, port, up, pid), SecondBrain's build, Ollama's
   loaded models, and whether a Manjuel sitting is open. Report what it shows in one or two lines. The Estate's
   versions (which commit each part runs) come from `secondbrain_estate_status` too: Neiro's lock is retired.
2. **Find the cause.** For a server that is down or misbehaving, call `secondbrain_estate_logs` with its `service`
   name from the status (and `lines`, at most 400). Quote the lines that show the fault. Never guess past the log.
3. **Name the part.** Read `references/map.md` for what the part is, its port and who starts it.
4. **Change one thing**, only when the user asks for it or agrees to it, and say what and why before the call:
   - Restart, start or stop a server: `secondbrain_service_control` with `service` and `action`
     (`start`, `stop` or `restart`). It waits on the user's card.
   - A model stuck in memory, or two chat models loaded at once: `secondbrain_ollama_unload` with its `model`
     name from the status. It waits on the user's card. The `ollama-ops` skill has the rest of Ollama.
   - SecondBrain's update: `secondbrain_app_update` with `action="check"` first and report the two builds. Only
     on the user's word, `action="apply"`: it restarts SecondBrain and ends your connection, so say so first.
     Both ask the user's card.
5. **Check.** Call `secondbrain_estate_status` again and report what changed, as the tool shows it.

What the user has approved or denied: `secondbrain_approvals_history` (`limit`, newest first), and how a held door
call ended: `secondbrain_hold_status` (`id`). The `approvals` skill says how. Use them before asking again for
something the user has just refused.

Your eval sets: `secondbrain_eval_start` starts them in their own window (planned first, then its own card: ADR-0009) and
`secondbrain_eval_status` reads a run's progress. The `bar-runner` skill says when and how; the `automations` skill
says how a saved flow runs them (no card: the flow is his approved plan), and the daily what-happened.

His saved flows (the Flows shelf, ADR-0016): `secondbrain_saved_flows` lists them (id, name, steps, when, running or
waiting, the last result), `secondbrain_saved_flow_status` reads how one flow's run went (by its `id`, or Steward's
`run_id`: each step's state and ms, a failed run's reason), and `secondbrain_saved_flow_run` runs one now by its `id`,
as his Run now button does (planned first in chat, then its own card). The `automations` skill says how.

Rules:
- Every change asks the user's card. A refused or unanswered card means stop; never try another way round it.
- Never SecondBrain itself: it serves these tools. SecondBrain refuses it by name.
- RULE 9: while a Manjuel sitting is open (`sitting.open` in the status), nothing in the ground (Desktop\Research)
  is edited, committed or sent, and the door is not stopped or restarted. Say the sitting is open and wait.
- Never Desktop\Archive: not read, not written, not named in a git call.
- Never read or print a `.env` file or a key, wherever it is.
- Never change Aurora's look.
- One chat model at a time on the GPU. Unload the one not in use rather than loading a second.
- For git across the estate's repositories, follow the `github` skill.
