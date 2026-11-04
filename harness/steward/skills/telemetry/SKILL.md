---
name: telemetry
description: Summarise your own recent telemetry - the newest runs, model calls, tool calls and errors in your traces. Use when the user asks what you did recently, which tools you called, how many model calls a run made, or what errored.
---

## Usage

Your spans are written to `halo_traces/traces.jsonl` in your repo. The file grows past 100 MB, so never open,
read or search it with the file tools or the shell: only this skill's script reads it, and only its tail.

1. Run `scripts/telemetry.py` with no arguments (the last 1024 KB). For more of the past, add `["--kb", "4096"]`
   (4096 KB is the most it reads).
2. It prints JSON: the time range it covers (`from`, `to`), `runs` (workflow and agent runs), `model_calls` by model,
   `tool_calls` by tool, the number of `errors` and the `last_errors` (span, time, message).
3. Report the time range, the runs, the model and tool call counts, and each error as printed. Say that it covers only
   the newest part of the file.

Rules:
- Read only. Never change, move or empty the traces file.
- Never read the whole file, with this script or any other tool.
