# Hosted.py Report

The **`hosted.py`** file implements a local, loopback-only server for the Steward agent, enabling it to serve SecondBrain via the Azure Responses protocol without relying on Foundry. It is designed for local development and testing, using Ollama as the LLM backend.

## Key Features

1. **Local Hosting** – The server listens on `127.0.0.1` using a configurable port (`STEWARD_PORT`, default `43120`).
2. **Middleware for Background Tasks** – A custom middleware releases background agents per request to keep resources tidy.
3. **Response Persistence** – Conversation history is stored in a disk‑based `FileResponseStore` under `storage/responses`, allowing continuity across restarts.
4. **Tracing** – Integrates with `halo_traces` to record trace spans in `halo_traces/traces.jsonl`.
5. **Environment Variables** – Reads settings such as `OLLAMA_HOST`, `OLLAMA_MODEL`, and others from a `.env` file.
6. **Single Steward Instance** – Builds the Steward agent once and keeps it warm, avoiding per‑request initialization overhead.

## Workflow

1. `build_steward_agent` is called with an in‑memory history provider.
2. The agent’s middleware stack is extended with `_release_background_per_request`.
3. `ResponsesHostServer` wraps the agent and runs asynchronously.
4. On each request, background providers are released once the response stream finishes.

## Usage

```bash
python harness/steward/step04_production_ready/hosted.py
```

The server is now ready to accept turns from SecondBrain on the local machine.
