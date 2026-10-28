# Steward: build your own engineering assistant

MAF's [**"Build your own claw and agent harness"**](https://devblogs.microsoft.com/agent-framework/build-your-own-claw-and-agent-harness-with-microsoft-agent-framework)
series, step by step, building Steward, a software engineering and development assistant, instead
of the guide's finance assistant. Everything runs on local Ollama and reuses the shared harness
`console` package in the parent `harness/` folder.

- **Step 1: `step01_meet_steward.py`**: the minimal harness, with planning, compaction and a `get_repo_status` tool.
- **Step 2: `step02_working_with_code.py`**: file access over the workspace, approval-gated `git_commit`, and durable file memory.
- **Step 3: `step03_scaling_capabilities.py`**: skills (`code-review`, `codebase-map`), a confined shell, CodeAct, and a background `CodeExplorer` agent.
- **Step 4: `step04_production_ready/`**: one shared `build_steward_agent` factory, a console host with OpenTelemetry, and local evals.

## Setup

From the repo root:

```
copy .env.example .env      # OLLAMA_MODEL=gpt-oss:20b by default
```

`STEWARD_WORKSPACE` (optional, in `.env`) points Steward at a real repo. It defaults to
`harness/steward/working`, which holds `sample-project/`: a small module with one deliberately
failing test.

## Changes from the guide (local Ollama)

- `OllamaChatClient` replaces `FoundryChatClient`.
- Web search is disabled, because the Ollama client doesn't support it.
- The shell is passed as `shell.as_function()`, because the Ollama client doesn't implement
  `SupportsShellTool`.
- Left out because they need Microsoft Foundry or Azure: Foundry memory, Foundry Toolbox skills,
  Purview, Foundry hosting and Foundry evaluators.
- The web-search research sub-agent became a read-only code explorer.

## Step 1: Meet Steward

```
.venv\Scripts\python harness\steward\step01_meet_steward.py
```

1. `/mode execute`
2. `What's the state of the repo?` (calls `get_repo_status`)
3. `I'm working on Steward and SecondBrain. Add them to my projects.` (saved to `projects.md` in file memory)
4. `/mode plan`
5. `Plan adding a command-line interface to sample-project.` (plans with todos; `/todos` shows them)

## Step 2: Working with your code, safely

```
.venv\Scripts\python harness\steward\step02_working_with_code.py
```

1. `What does sample-project/inventory.py do?` (file reads are auto-approved)
2. `Why does test_percent_discount fail? Fix it.` (writing the file **asks for your approval**)
3. `Write a short review of sample-project to reports/review.md.` (approval to write)
4. `I use unittest and type hints everywhere.` (a durable preference)
5. `Commit the fix.` (`git_commit` **asks for your approval**)

## Step 3: Scaling its capabilities

```
.venv\Scripts\python harness\steward\step03_scaling_capabilities.py
```

1. `Map this codebase.` (loads the `codebase-map` skill and runs `repo_map.py`)
2. `Run the tests in sample-project.` (`run_shell` **asks for approval** for each command)
3. `Fix the failing test, then run the tests again.`
4. `Review my uncommitted changes.` (loads the `code-review` skill and runs `diff_stats.py`)
5. `What percentage of sample-project's lines are tests?` (CodeAct writes and runs Python)
6. `Explore sample-project with the CodeExplorer agent and summarize it.` (background agent)

## Step 4: Production-ready

```
.venv\Scripts\python harness\steward\step04_production_ready\console_app.py
.venv\Scripts\python harness\steward\step04_production_ready\evals.py
```

`evals.py` runs three fixed queries (repo status, codebase map, bug diagnosis) with the shell off
and skill scripts auto-approved, then scores them with local evaluators.

## Known limits on gpt-oss:20b

The background-agent and todo tools don't always work on this model. In testing, delegating to
CodeExplorer succeeded 2 times out of 4. The failures were malformed `todos_add` calls, or the model
trying to call the background tools from inside the CodeAct sandbox. A larger local model such as
`qwen3-coder:30b` (set `OLLAMA_MODEL` in `.env`) may do better.
