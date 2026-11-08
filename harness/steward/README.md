# Steward: build your own engineering assistant

MAF's [**"Build your own claw and agent harness"**](https://devblogs.microsoft.com/agent-framework/build-your-own-claw-and-agent-harness-with-microsoft-agent-framework)
series, step by step, building Steward, a software engineering and development assistant, instead
of the guide's finance assistant. Everything runs on local Ollama and reuses the shared harness
`console` package in the parent `harness/` folder.

- **Step 1: `step01_meet_steward.py`**: the minimal harness, with planning, compaction and a `get_repo_status` tool.
- **Step 2: `step02_working_with_code.py`**: file access over the workspace, approval-gated `git_commit`, and durable file memory.
- **Step 3: `step03_scaling_capabilities.py`**: skills (`code-review`, `codebase-map`), a confined shell, CodeAct, and a background `CodeExplorer` agent.
- **Step 4: `step04_production_ready/`**: one shared `build_steward_agent` factory, Steward's workflow (`steward_workflow.py`), a console host with OpenTelemetry, the local service the Agent tab talks to (`hosted.py`), an MCP host (`mcp_app.py`), DevUI (`devui_app.py`), and local evals.

## Setup

From the repo root:

```
copy .env.example .env      # keys and the install's entries; the model is binding.us (steward:1 here)
```

`STEWARD_WORKSPACE` (optional, in `.env`) points Steward at a real repo. It defaults to this
repo's root, so his own harness code is in reach (ADR-0001 item 11). Reads run without a card,
writes ask, and his file store never reads, searches or lists a `.env` file.
`harness/steward/working/sample-project/` is a small module the walkthrough and the evals use; the
evals plant its discount bug in the working copy for a run and put it back after.

## Changes from the guide (local Ollama)

- `OllamaChatClient` replaces `FoundryChatClient`.
- The Ollama client has no hosted web search. Step 1 and the step 4 factory use SecondBrain's
  `web_search` and `web_fetch` over MCP instead; steps 2 and 3 run without web search.
- The shell is passed as `shell.as_function()`, because the Ollama client doesn't implement
  `SupportsShellTool`.
- Foundry memory is Mem0 running locally (step 2 on). Left out because they need Microsoft Foundry
  or Azure: Foundry Hosted Agents and Foundry evaluators. The Foundry host's own server
  (`ResponsesHostServer`) runs on loopback instead (see the Agent tab, below).
- The step 4 factory replaces the rest with local pieces: Purview with Presidio
  (`PRESIDIO_ENTITIES`), Foundry Toolbox skills with SecondBrain's skill notes over MCP
  (`MCPSkillsSource`), and the web-search research sub-agent with `WebResearchAgent` on
  SecondBrain's web tools. Step 3 has a read-only code explorer in its place.

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

`evals.py` runs fixed queries with the shell off and skill scripts auto-approved, then scores them
with local evaluators. Like the console, it writes every span to `halo_traces/traces.jsonl` (capped
at 100 MB, newest kept), and a failed check prints its reason.

Defined once (the guide's Part 4): `build_steward_agent` is the guide's harness agent, and
`steward_workflow.build_steward(stack, **build)` builds it with the workflow below and returns
`(agent, workflow)`. The Agent tab's service (`hosted.py`), `evals.py` (its default, `small`, `steps` and `memory` runs) and the tests run
the workflow from that one builder; `test_every_host_builds_the_same_steward_workflow` checks that the service's
graph is the builder's. `console_app.py` runs the same harness agent on
its own, as the guide's console ships: a workflow's cards resume from checkpoints, which MAF's
Responses host keeps, and not from a console's session (MAF issue #5818). In SecondBrain, the Agent
tab is Steward's console.

### The Agent tab: a MAF workflow (`steward_workflow.py`, served by `ag_ui_app.py` and `hosted.py`)

SecondBrain's Agent tab talks to `ag_ui_app.py` over AG-UI on 43122 by default, and falls back to
`hosted.py` on 43120 when that host is down (ADR-0003, `docs/ARCHITECTURE.md`). `hosted.py` serves Steward as a MAF workflow on MAF's own
`ResponsesHostServer(workflow=...)`, a fresh Steward per request. His work in execute streams to
the tab as it happens (MAF's `intermediate_output_from`):

```
request -> plan -> read_plan -> ask_approval (approve_plan card) -> execute -> check
                                                                      ^          |
                                                                      +- repair -+   (tests failed; at most 3 attempts)
check passed on changed code -> ask_commit ("Checks passed") -> commit (git_commit card)
nothing changed, or attempts spent -> report
```

1. **Plan:** structured output (`StewardPlan`: the guide's PlanningResponse plus its steps), read
   in code. A question ends the run as text; your answer is the next request.
2. **Approve:** the plan comes to you as an `approve_plan` card. Deny it and nothing runs.
3. **Execute:** the plan's steps become his todos, in execute mode. Every write still asks on its
   own card, and your No on a card ends the run.
4. **Check:** model-free, on the files themselves. The tests in the folder of each Python file that
   differs from the committed state are run (pytest), whichever tool or card wrote it, so the
   workspace starts each run at the committed state. The check's own pytest carries
   `STEWARD_CHECK_RUNNING`, so a workflow run inside those tests does not start the check again.
5. **Repair:** failing, the output goes back to him in execute mode, with "Fix the failing
   checks" (`REPAIR_TODO`) as his todo, and the check runs again; at most 3 attempts.
6. **Commit:** only after passing checks on changed code. The tab shows "Checks passed", the model
   writes only the message (structured output, `CommitMessage`: one line of at most 72 characters),
   and the workflow raises his `git_commit` card with it; Approve commits, Deny commits nothing. A
   message that fails to parse twice is replaced by one built from the request and the changed
   files. Execute is told not to commit; failing work never reaches this step.
7. **Report:** when nothing changed, or the attempts are spent, the run ends with the checks'
   result. His answer has already streamed, so it is not repeated.

The host keeps its state in `worlds/steward/.as` (gitignored). Its short name keeps the host's file
paths under Windows' 260-character limit.

With the factory (SecondBrain's Agent tab or `console_app.py`), Step 3's list adds:

7. `Research Microsoft Agent Framework, Ollama and mem0 with the WebResearchAgent and summarize the latest news.` (background research agent)
8. `How do I set up a flow in SecondBrain?` (loads a SecondBrain skill over MCP)

### Ports (all on loopback)

| Port  | What                                                                          |
|-------|-------------------------------------------------------------------------------|
| 43120 | Steward's service, `hosted.py` (Responses protocol; Jesster's fallback; `STEWARD_PORT`) |
| 43121 | Steward as an MCP tool, `mcp_app.py` (`http://127.0.0.1:43121/mcp`; `STEWARD_MCP_PORT`) |
| 43122 | Steward over AG-UI, `ag_ui_app.py` (Jesster's default, ADR-0003; `STEWARD_AG_UI_PORT`) |
| 43110 | SecondBrain's MCP (`SECONDBRAIN_MCP_URL`)                                     |
| 43111 | The Atlas door                                                                |
| 8091  | The glass                                                                     |
| 11434 | Ollama (`OLLAMA_HOST`)                                                        |

Cards (approvals) do not cross the MCP endpoint, so a tool that waits for approval does not run
through it; the Agent tab, where you answer his cards, is the way to work with him.

## Known limits on gpt-oss:20b

The background-agent and todo tools don't always work on this model. In testing, delegating to
CodeExplorer succeeded 2 times out of 4. The failures were malformed `todos_add` calls, or the model
trying to call the background tools from inside the CodeAct sandbox. A larger local model such as
`qwen3-coder:30b` (set `OLLAMA_MODEL` in `.env`) may do better.

_2026-11-05: superseded by [ADR-0002](../../docs/decisions/0002-one-model-for-everything.md): one model, `steward:1`,
does everything; another model returns only on eval evidence._

## Where it stands

The version is in `pyproject.toml`; what each version holds is in `CHANGELOG.md` at the repo root.
The order agreed for the workflow:

1. The check sees every write. Done.
2. Commit after a passing check. Done.
3. Define once. Done.
4. Evals as small single asks. In progress: the seven checks and the `evals` skill are built. Then, from
   the 2026-11-02 deep dive: MAF 1.24.0 with pinned versions (a deployment package); `num_ctx` and
   `keep_alive` sent on every agent; tool calls one at a time with detailed errors and caps; background
   agents waited for; skills cached; a pass/fail exit for the evals.
5. Memory across requests, as an eval case: MAF's `MemoryContextProvider` (automatic, same model),
   history and sessions that survive a restart, and the memory case. The older eval sets retire here.
6. The cookbook's improvement loop, with the owner's approval at the merge, gated on the evals and
   measured (Ollama's reload and speed counters, metrics).

After those, in order: safety (FIDES, Agent Hooks), long runs (summarising compaction, the loop's
progress log, `think` per step), visibility (the workflow in DevUI, `WorkflowViz`, progress events),
and hosting (AG-UI for the whole workflow with cards, planned with SecondBrain; _2026-11-05: built, and the default
transport, [ADR-0003](../../docs/decisions/0003-ag-ui-is-the-default-transport.md)_). Ruled 2026-11-02:
web search and web fetch go only through SecondBrain's route, the one Steward already uses (no Ollama
web search); Steward's embedding model is `embeddinggemma-2:270m` (303 MB, 8K context, MTEB code
78.68), for semantic code search and memory, on the CPU beside the chat model on the GPU (Ollama's
`options: {"num_gpu": 0}`; MAF's `OllamaEmbeddingClient` does not forward `options` yet);
`nomic-embed-text-v2-moe` stays for Manjuel's index; no Docker sandbox; Foundry Local is ruled out. The full plan is the SecondBrain note
`steward-the-build-plan-after-the-deep-di-f92d04`; the gaps are in `steward-what-maf-and-ollama-offer-that-w-3acc5a`.

### The Ollama server on this PC

Set in the Windows user environment, 2026-11-02 (Ollama 0.40.13, updated from 0.35.0 the same day;
AMD Radeon RX 6800 XT, 16 GB; 32 GB RAM):

| Setting | Value | Why |
|---|---|---|
| `OLLAMA_KEEP_ALIVE` | `30m` | It was `30`, which Ollama reads as 30 seconds: a reload after every turn |
| `OLLAMA_MAX_LOADED_MODELS` | `2` | The chat model on the GPU and the embedder on the CPU; no second chat model |
| `OLLAMA_NUM_PARALLEL` | `1` | Context memory scales with it; 3 x 65,536 would spill gpt-oss:20b out of 16 GB |
| `OLLAMA_CONTEXT_LENGTH` | `65536` | Matches the compaction budget |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` | About half the context memory of f16 |
| `OLLAMA_FLASH_ATTENTION` | `1` | Needed for the q8_0 cache |

Ollama reads these only when it starts: quit it from the tray and start it again after a change.

## Findings (2026-11-02)

From the SecondBrain note `maf-solved-patterns-checked-2026-11-02-d8d89a`; the details are in
`CHANGELOG.md` under Unreleased.

- **Evals with cards.** MAF's `evaluate_workflow(queries=...)` runs each query once and does not
  answer cards, so a run is scored only up to its first card. As in the guide's `evals.py`, each
  query is run with its cards answered and scored with `evaluate_agent(..., responses=...)`;
  `evals.py` does this (`run_steward`, `_run_answering_cards`). Step 4 turns today's live failures
  into small single-ask cases, by the cookbook's evaluation flywheel (Analyze, Measure, Improve).
- **Hosting.** MAF's self-hosting helpers (`agent-framework-hosting-responses`, sample
  `04-hosting/af-hosting/local_responses_workflow`) cannot yet take an approval answer back in
  (`_parsing.py`: "Unsupported Responses input content type") and do not handle workflow
  `request_info`, so the Foundry host's `ResponsesHostServer`, with `WorkflowTurn` and
  `CheckpointStoreProvider`, on loopback stays his host. `hosted.py` carries three local
  workarounds for it: a fixed `FOUNDRY_AGENT_SESSION_ID`, the short `AGENTSERVER_STATE_ROOT` `.as`,
  and dropping `additional_function_arguments` before the Ollama call.
- **Missing to deploy locally.** (The deployment package is done, 2026-11-03: `pyproject.toml` pins every
  package the hosts import, and the gate installs from it.) An eval gate in front of deploying; an eval case proving memory across requests; and the
  cookbook's improvement loop with approval at the merge.
