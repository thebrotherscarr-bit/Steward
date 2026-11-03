# STEWARD

A Microsoft Agent Framework agent running on local Ollama (default model `gpt-oss:20b`; change it in `.env`).

```
python -m venv .venv && .venv\Scripts\pip install -e .
.venv\Scripts\python steward.py
```

Steward himself, built step by step on MAF's "Build your own claw" guide, is in `harness/steward/`
(see its README). SecondBrain's Agent tab is the console where you work with him: it talks to his
service, `harness/steward/step04_production_ready/hosted.py`, on 127.0.0.1:43120, and his cards
(approvals) are answered there. His MCP endpoint (`mcp_app.py`) is on 127.0.0.1:43121.

## Where it stands

The current version is the `version` line in `pyproject.toml`. `CHANGELOG.md` records what each
version holds, and today's findings under Unreleased. Versions are not git tags.
