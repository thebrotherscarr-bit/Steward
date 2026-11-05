# AGENTS.md

Instructions for AI coding agents (Steward himself, and any other hand) working in the Steward repository.

**Key Documentation:**
- [docs/README.md](docs/README.md) - The doc map: which document is for what
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - The Estate as it is now: parts, wires, data, flows, rules, plan
- [docs/decisions/](docs/decisions/README.md) - Architectural Decision Records (MAF's format and templates)
- [docs/specs/](docs/specs/spec-template.md) - A feature's design before it is built (MAF's spec template)
- [.agent/PLANS.md](.agent/PLANS.md) - How to write an ExecPlan; the plans themselves are in [docs/plans/](docs/plans/README.md)
- [harness/steward/README.md](harness/steward/README.md) - The harness, step by step, its ports and its workflow
- [harness/steward/evals/README.md](harness/steward/evals/README.md) - The eval sets and how to add a case

**Agent Skills** (`harness/steward/skills/<name>/SKILL.md`) - Steward's task-specific instructions, loaded on demand
(estate, github, automations, bar-runner, eval-history, telemetry, ollama-ops, approvals and the rest).

## The doc standard (2026-11-05)

The operator, 2026-11-05: "make this the standard moving forward, this way nothing gets misaligned."

- **A decision** (a part, a wire, a store of data, a rule) gets an ADR in `docs/decisions/` before it is built.
- **A feature's design** gets a spec in `docs/specs/` before it is built, when it is more than one small change.
- **A multi-step build** gets an ExecPlan in `docs/plans/`, kept to `.agent/PLANS.md`, from design to finish.
- **`docs/ARCHITECTURE.md`** is updated in the same pull request when a change moves the shape it describes.
- **`CHANGELOG.md`** gets one entry under Unreleased for every change that lands.
- Older documents elsewhere are annotated with a dated pointer, never rewritten or deleted.

## ExecPlans

When writing complex features or significant refactors, use an ExecPlan (as described in .agent/PLANS.md) from design
to implementation.

## Rules that bind every change

- `.env` and keys are never read, printed, copied, committed or put on a command line. Every file tool refuses `.env*`.
- The Archive never goes on GitHub.
- Kyle holds the gate: every write, shell command, commit, push and Estate change is his card. Changes land on main only
  through a pull request whose checks pass. No force-push, tags, releases or history rewrites.
- No agent puts its own name on the work: no co-author line, no "generated with", no byline. Kyle is the author.
- Use MAF as it ships: check the MAF Learn pages and the installed `agent_framework` source first, and name the passage.
- The harness, not the model: fix the task, the context, the tools or the check. One model, `steward:1`.
- Name the wire: every piece has a test that goes red when it is unplugged.
- One piece, one line of work, one pull request. Say "restart required" when running code changes.

## Quick Reference

Run from the repository root, with the virtual environment's Python (`.venv\Scripts\python` on Windows). Every
command carries a hard time limit.

```
timeout 300 python -m compileall -q .
timeout 300 python -m pytest -q harness/steward/working/sample-project harness/steward/working/sample-project-2
timeout 300 python -W ignore harness/steward/step04_production_ready/evals.py validate
timeout 900 python -m pytest -q -p no:cacheprovider harness/steward/step04_production_ready/test_harness.py
```

These are the gate's steps (`.github/workflows/gate.yml`), which run on every pull request. Model-run evals need the
GPU and run on this PC only, each set in its own window (`harness/steward/evals/run-bar.ps1`), one at a time,
whenever the operator says (ADR-0009).

## Project Structure

```
docs/                          # the Estate's design: ARCHITECTURE, decisions, specs, plans
.agent/PLANS.md                # the ExecPlan format
harness/
├── console/                   # the shared console package
└── steward/
    ├── step01..03_*.py        # the guide's steps
    ├── step04_production_ready/
    │   ├── agent.py           # build_steward_agent: the harness agent
    │   ├── steward_workflow.py# plan, approve, execute, check, repair, commit, report
    │   ├── hosted.py          # Responses host, 43120
    │   ├── ag_ui_app.py       # AG-UI host, 43122
    │   ├── mcp_app.py         # MCP host, 43121 (run_recipe, recipe_status)
    │   ├── recipe_workflow.py # automations as MAF workflows
    │   ├── evals.py           # eval runner, validate, bar
    │   └── test_harness.py    # the gate's model-free checks
    ├── evals/                 # versioned eval sets, baselines, run-bar.ps1
    ├── skills/                # Steward's skills
    └── working/               # sample projects the evals use
```

## Maintaining Documentation

When a change moves a part, a port, a tool, a skill or a command, check whether these need updating in the same pull
request: this file, `docs/ARCHITECTURE.md`, `harness/steward/README.md`, the skill's `SKILL.md`, and Steward's
Charter (the SecondBrain note `steward-charter`, changed only on Kyle's word).
