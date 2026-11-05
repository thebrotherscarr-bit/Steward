# Steward

Steward is the agent of the Estate: a Microsoft Agent Framework (MAF) agent that runs on local
Ollama and does the work (code, tests, evals and the Estate's own controls), with every write on an
approval card you answer.

## Where he sits in the Estate

- **Steward** (this repository) runs everything.
- **SecondBrain** (repository [Jesster](https://github.com/thebrotherscarr-bit/Jesster)) is his
  console and the hub: its Agent tab is where you work with him and answer his cards, and it serves
  the notes, web and MCP tools he uses.
- **Manjuel** ([Manjuel](https://github.com/thebrotherscarr-bit/Manjuel)) is the ground and the
  record: the laws, the history and the engine.
- **Atlas** (repository [Aurora](https://github.com/thebrotherscarr-bit/Aurora)) is parked until Steward has visible computer control.
- **Neiro** has been retired as a gate.

Everything runs on your own PC on local models. No hosted model is used by default.

**The Estate's design** is in [`docs/`](docs/README.md): [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (the parts,
their wires, their data and the build plan) and the decision records in [`docs/decisions/`](docs/decisions/README.md).
Every architectural change gets a decision record before it is built.

Steward himself, built step by step on MAF's "Build your own claw" guide, is in `harness/steward/`
(see its README). His service, `harness/steward/step04_production_ready/hosted.py`, listens on
127.0.0.1:43120 for SecondBrain's Agent tab; his MCP endpoint (`mcp_app.py`) is on 127.0.0.1:43121.

## Install on another PC (Windows)

1. Install [Ollama](https://ollama.com) and Python 3.11 or newer.
2. Build Steward's model. One model does everything, coding included:

   ```
   ollama pull gpt-oss:20b
   ollama create steward:1 -f steward.Modelfile
   ```

   The embedding model for code search and memory is named in `harness/steward/README.md`.
3. Clone and install:

   ```
   git clone https://github.com/thebrotherscarr-bit/Steward.git
   cd Steward
   python -m venv .venv
   .venv\Scripts\pip install -e .
   copy .env.example .env
   ```

   In `.env`, set `OLLAMA_MODEL=steward:1` and paste SecondBrain's MCP key (SecondBrain, Settings,
   Share) into `SECONDBRAIN_MCP_KEY`. Keep `.env` to yourself: it is never committed.
4. Install SecondBrain: download `SecondBrain-win32-x64.zip` from the newest `secondbrain-b<N>`
   release of [Jesster](https://github.com/thebrotherscarr-bit/Jesster/releases), unzip it anywhere
   and run `SecondBrain.exe`. Its **Update** button installs later releases.
5. Start Steward's service and open SecondBrain's Agent tab:

   ```
   .venv\Scripts\python harness\steward\step04_production_ready\hosted.py
   ```

## Where it stands

The current version is the `version` line in `pyproject.toml`. `CHANGELOG.md` records what each
version holds, and today's findings under Unreleased. Versions are not git tags.

## License and names

MIT (`LICENSE`). The outside eval data under `harness/steward/evals/data/` keeps its own license,
in each folder's `LICENSE`. See `TRADEMARKS.md` for the names policy and `SECURITY.md` to report a
vulnerability.
