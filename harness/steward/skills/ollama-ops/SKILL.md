---
name: ollama-ops
description: Look after Ollama on Kyle's PC - which models are loaded, a runner that looks stale, a model that must make room, and the pinned OLLAMA_* settings. Use when a model is slow, stuck or missing, when two chat models are loaded, before a large model must load, or when the user asks how Ollama is set up.
---

## Usage

1. **Look.** Call `secondbrain_estate_status` and report Ollama's loaded models in one or two lines.
2. **Judge.** A runner looks stale when a model stays loaded that nothing is using, or two chat models are loaded at
   once (one chat model at a time on the GPU). If Ollama itself looks down, read its log with
   `secondbrain_estate_logs` and quote the lines.
3. **Make room**, only when the user asks or agrees: say which model and why, then call `secondbrain_ollama_unload`
   with its `model` name from the status. It waits on Kyle's card.
4. **Check.** Call `secondbrain_estate_status` again and report what changed.

The pinned settings (`OLLAMA_*`): call `secondbrain_search_notes` with `"Ollama on this PC"`, then
`secondbrain_read_note` on the settings review it finds, and quote the values as the note gives them.

Rules:
- Reads run as they are; every unload is on Kyle's card. A refused or unanswered card means stop.
- Never read, print or search a `.env` file for a setting, wherever it is. The note is where they are kept.
- Never start, stop or restart Ollama, pull a model or change a setting. Say what you would change and let Kyle do it.
