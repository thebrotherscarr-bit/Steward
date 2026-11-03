# Changelog

All notable changes to Steward are recorded in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Steward is pre-1.0 (0.y.z): a minor version may change
behaviour, ports or interfaces.

The current version is the `version` line in `pyproject.toml`. Versions are recorded here, not as git tags: a tag is
created only on the owner's word. The versions below were assigned after the fact by grouping the merged pull requests
by milestone. Each version carries the date of its last merge, and each entry cites its pull request. Pull request #12
was never merged and has no entry.

## [Unreleased]

### Fixed

- A request hint requires only the work's tools, never `load_skill`. In his workflow he reads a skill while
  planning and the work is checked in the execute step's own session, so the required-tools check read the skill
  as never loaded and sent him back: live 2026-11-02 he ran the whole eval set twice, and the nudge's text leaked
  into his reply. `test_a_skill_read_while_planning_is_not_demanded_again_when_the_work_is_done`.
- His shell starts with his own virtual environment active (`_own_python_env`: `VIRTUAL_ENV` and his
  `Scripts` folder first on `PATH`), so `python`, `pip` and `pytest` are the Python he runs on. Live 2026-11-02 he ran
  `python .../evals.py` and the system Python had no `agent_framework`. `test_his_shell_runs_his_own_python`.
- He runs an eval set once: the `evals` skill now says to mark its todo complete as soon as the run finishes, and
  never to run the set again when reminded of that todo. Live 2026-11-02 the todo loop's reminder sent him back and
  he ran the whole set a second time, reporting only the second run. The `run-tests` skill now says it has no
  script (he had called `run_skill_script` for a `run_tests.py` that does not exist).
- Eval runs no longer share Steward's real memory. `run_steward` (the small asks and the regression set) and the
  `steps` set give each run a throwaway `FileSystemAgentFileStore` under `storage/`, removed when the run ends, as
  the walkthrough set already did. Live 2026-11-02: eval runs had saved their plans into
  `agent-file-memory/steward`, and a later run's commit message described that work instead of its own.
  `test_an_eval_run_never_touches_stewards_real_memory` proves a memory written in an eval stays out.

### Added

- Step 4, piece 4.2: Ollama options on every agent, defined once as `agent.OLLAMA_OPTIONS`
  (`{"num_ctx": 65536, "keep_alive": "30m"}`, MAF's `OllamaChatOptions`): Steward, CodeExplorer and WebResearchAgent
  send their own window and keep-alive with every call, so the window no longer rests on the Ollama server's default
  (set to 32K for a while on 2026-11-03, under his 64K compaction budget). His compaction budget is now the same
  constant (`_STEWARD_CONTEXT`); a caller's options win, so the fixer keeps its 32K window.
  `test_steward_and_his_team_send_their_own_ollama_window_and_keep_alive`.
- Step 4, piece 4.3: MAF's tool-call settings (`FunctionInvocationConfiguration`) on the one client Steward, his
  team and the fixer use, defined once as `agent.TOOL_CALLS`: calls run one at a time in the model's order, a failing
  tool's error text goes back to the model, and a pass of his loop stops calling tools after 40 calls or 30 minutes
  and answers in text. Earned by round 1 (2026-11-03), whose fixer completed a finished todo every 18 seconds until
  it was stopped. `test_maf_tool_call_limits_stop_a_repeating_call`.
- Step 6, piece 6.4: the diagnosis feeds the loop, the cookbook's handoff to the coding agent. A round that
  names no failure (`improve:` alone in the Agent tab, or no task on the command line) takes the first top
  priority from `improvement_loop.py`'s handoff (`improvement_loop/<run>/handoff.md`, HALO's ranking), with the
  whole handoff as its evidence; a named failure is used as named. `round_task` and `handoff_task` stop the round
  with the reason when there is no handoff or it lists no priorities. The reader takes each `top_priorities` shape
  HALO writes, and handoffs saved JSON-escaped. The improve skill says how to work such a task.
  `test_a_round_that_names_nothing_takes_the_diagnosis_first_priority`.
- Step 6, piece 6.3 (last part): the `improve` skill, the cookbook's repair procedure for the fixer: name the
  failing check in `evals.py`, find the cause in the harness, make the smallest change, prove it with a test in
  `test_harness.py`, stop and report; never weaken a check or the baseline. The loop's opening message names it
  ("This is an improvement round"), and a request hint points to it. SecondBrain's Agent tab starts a round from a
  conversation beginning `improve:` (SecondBrain #41).
- Step 6, piece 6.3 (first part): the improvement loop on his host. A turn whose request metadata carries
  `{"steward_workflow": "improve"}` runs `improvement_loop_workflow.py` (the coder fixer, the gate, the review)
  instead of his request workflow; the loop has a fixed name (`steward_improve`) so card answers resume it, uses the
  host's checkpoints, and drops the `improve:` prefix from the task. The review comes back as MAF's `request_info`
  call and is answered with `function_call_output`. The Agent tab's side is the next part.
  `test_an_improve_turn_runs_the_improvement_loop_on_the_host_and_its_review_comes_back_as_a_card`.
- Step 6, piece 6.2: the eval gate. `evals.py small` prints `Small-ask checks: N/M` over the checks that apply to
  their ask, and with `--gate` exits 1 when they drop below the baseline in `eval_baselines.json` (10 of 14, the
  first clean run, 2026-11-02; the operator raises it after a real improvement). The improvement loop's gate now
  runs it after the harness tests. `test_the_eval_gate_counts_only_applicable_checks_and_fails_a_drop`.
- Step 6, piece 6.1: the improvement loop's fixer. `improvement_loop_workflow.py`'s writer is now Steward's own
  harness on the coder model (`build_fixer`: `STEWARD_CODER_MODEL`, default `devstral-small-2:24b`, the
  operator's choice), with the same file tools and write cards and a 32K window (`FIXER_CONTEXT`).
  `build_steward_agent` takes `default_options` for it. `test_the_improvement_loops_fixer_is_stewards_harness_on_the_coder_model`.
- Step 4, evals as small single asks: `python evals.py small` runs three asks (a new function, the discount fix with the
  bug planted, a README line) once each through the workflow as the Agent tab runs it, the plan and the writes
  approved and the commit denied, and scores them with seven MAF `@evaluator` checks, one per failure seen live on
  2026-11-02: the plan labelled as a clarification, a write the check missed, an edit that broke the file, "proceed?"
  instead of `git_commit` (or the door's `atlas_git_commit`), a vague commit message, the loop's nudge in a reply, and
  an off-topic answer. The sample project is reset after every ask. `test_the_small_asks_check_each_of_todays_failures`
  proves each check fails on its failure and passes on the right run.
- The `evals` skill (`harness/steward/skills/evals/SKILL.md`): Steward runs his own eval sets on request ("run
  your evals", "run the small asks"), once, with `run_shell`, and reports every line as printed. His instructions
  name it, and a request that names evals gets the one-line hint to load it (`REQUEST_HINTS`). A skill script
  is not used: MAF's script runner stops a script after 30 seconds, and an eval set runs for minutes.
- Three more skills, each a procedure he follows on request, with his instructions naming it and a one-line hint
  (`REQUEST_HINTS`): `github` (a line of work, the commit, the send, the pull request and its checks, through the
  door's `atlas_*` tools, each write on the user's card; the merge only on the user's word), `run-tests` (pytest
  once through `run_shell`, the summary line reported exactly) and `secondbrain-notes` (search first, cite the
  note and its date, append rather than replace, sources and dates on new notes).
- `secondbrain_write_note` and `secondbrain_append_to_note` for the live Steward: his notes were read-only
  (`_SECONDBRAIN_NOTES_TOOLS`), though the skill and the user expect him to write them. Both ask on a card, and
  plan mode's gate counts them among the tools that change things.

### Changed

- The Ollama server's settings on this PC (Windows user environment, not the repo), recorded in
  `harness/steward/README.md`: `OLLAMA_KEEP_ALIVE` `30` (seconds) to `30m`, `OLLAMA_MAX_LOADED_MODELS` 6 to 2 (the
  chat model and the embedder), `OLLAMA_NUM_PARALLEL` 3 to 1. Ollama updated from 0.35.0 to 0.40.13; the embedding
  model for Steward is now `embeddinggemma-2:270m`, run on the CPU; `nomic-embed-text-v2-moe` stays, because Manjuel's
  index (`manjuel/skills.py` `EMBED_MODEL`, `index/vectors.db`) is built on it. The build plan from
  the 2026-11-02 deep dive is in the README's "Where it stands".

### Findings

Research recorded 2026-11-02 in the SecondBrain note `maf-solved-patterns-checked-2026-11-02-d8d89a`. No code changed.

- **Evals for a workflow with cards.** MAF's `evaluate_workflow(queries=...)` calls `workflow.run(q)` once per query
  (`agent_framework/_evaluation.py`) and does not answer `request_info` cards, so a run with cards is scored only up
  to its first card. The guide's own step 4 `evals.py` pattern applies instead: run each query yourself with its cards
  answered, then score with `evaluate_agent(..., responses=...)`. Steward's `evals.py` already does this (`run_steward`,
  `_run_answering_cards`). Its `steps` case groups `executor_completed` events by executor id, which is
  `evaluate_workflow`'s per-agent breakdown done by hand because of the cards.
- **The method is the cookbook's evaluation flywheel** (*Building resilient prompts using an evaluation flywheel*):
  Analyze, Measure, Improve, and again. Today's live failures are the cases. Each becomes one small single-ask case
  with one `@evaluator` reading the artifact or the run, scored by MAF's `LocalEvaluator`, one run per case. Planned
  for step 4, not yet built:
  - a plan labelled as a clarification;
  - a write missed behind a later card;
  - an edit that broke a file (tabs among spaces);
  - "proceed?" asked instead of calling `git_commit`;
  - a vague commit message;
  - the loop's nudge visible in a reply;
  - an off-topic final answer.
- **Deploying locally.** MAF's hosting options (Learn, *Hosting*) are Foundry Hosted Agents, self-hosting and the
  Durable Extension. Foundry Hosted Agents need Azure, which the estate's local-only rule rules out. MAF's
  self-hosting helpers (`agent-framework-hosting`, `agent-framework-hosting-responses`, the sample
  `04-hosting/af-hosting/local_responses_workflow`) cannot yet take an approval answer back in: `hosting-responses`'
  `_parsing.py` raises "Unsupported Responses input content type" for any input item but message, text, image or
  file, and workflow `request_info` and checkpoints are not handled. So the Foundry host,
  `agent_framework_foundry_hosting.ResponsesHostServer` with `WorkflowTurn` and `CheckpointStoreProvider`, run on
  loopback, stays Steward's host. Its cost is three local workarounds in `hosted.py`: a fixed
  `FOUNDRY_AGENT_SESSION_ID`, a short `AGENTSERVER_STATE_ROOT` (`.as`) for Windows' 260-character path limit, and
  dropping `additional_function_arguments` before the Ollama call.
- **What Steward lacks to deploy locally:**
  - A deployment package. `pyproject.toml` pins nothing and does not list packages the code imports:
    `agent-framework-hosting`, `agent-framework-hosting-mcp`, `mcp`, `starlette` and `uvicorn` (`mcp_app.py`), and
    `agent-framework-devui` (`devui_app.py`). Only the gate (`.github/workflows/gate.yml`) pins versions. The guide's
    step 4 folder carries a `requirements.txt` and an `.agentignore`. Recorded as a finding only; the dependencies
    are not changed here.
  - An eval gate in front of deploying. The cookbook (*Agent Improvement Loop*): "a reviewed loop, where the system
    proposes the change set and a developer approves the diff before merge."
  - Proof of memory across requests. MAF's `FileMemoryProvider` is session-scoped by default; an explicit `scope`
    shares it (MAF devblog, BUILD 2026; Learn, *Agent Harness*). `agent.py` already gives his file memory the
    explicit scope `steward` (#20); what is missing is an eval case that proves a note saved in one request is
    recalled in the next (step 5).
  - The cookbook's improvement loop, with the owner's approval at the merge.
- **The agreed order:** 1, the check sees every write (done, #33); 2, commit after a passing check (done, #34); 3,
  define once (done, #35); 4, evals as small single asks (next); 5, memory across requests, as an eval case; 6, the cookbook's
  improvement loop.

## [0.7.0] - 2026-11-02

Ports.

### Changed

- Steward's MCP endpoint (`mcp_app.py`) moves from port 8000, the MAF samples' port, which ComfyUI also takes, to
  43121, beside his service (43120) and SecondBrain's MCP (43110). An MCP client points at
  `http://127.0.0.1:43121/mcp`. (#37)

## [0.6.0] - 2026-11-02

The workflow's fixes from live runs, the commit step, and define once.

### Added

- `steward_workflow.build_steward(stack, **build)` builds Steward and his workflow in one place and returns
  `(agent, workflow)`; the guide's Part 4: "The agent is defined once; only the host around it changes." `hosted.py`
  and `evals.py` build from it, and `test_every_host_builds_the_same_steward_workflow` checks that the service's graph
  is the builder's. (#35)
- The commit step. After the check passes on changed code, ASK_COMMIT says "Checks passed" and asks Steward to commit
  (`COMMIT_TODO`); COMMIT runs his own `git_commit`, which comes to the user on its own card. EXECUTE is told not to
  commit; failing work, and runs that changed nothing, go to REPORT. (#34)
- EXECUTE and COMMIT stream to the caller as intermediate output (MAF's `intermediate_output_from`), so the Agent tab
  shows his work as it happens. REPORT gives only the checks' result. (#35)
- The plan step sends a plan labelled a clarification with no choices the guide's `PlanningResponseType` definitions,
  once per run. (#32)
- `halo_traces.py` caps the trace file at `HALO_TRACE_MAX_BYTES` (100 MB), keeping the newest whole spans. (#32)

### Changed

- The check reads the files on disk, not the transcript: pytest runs in the folder of each `.py` file that differs
  from the committed state (`git ls-files --modified --others`), whichever tool or card wrote it. The check's own
  pytest carries `STEWARD_CHECK_RUNNING`, so a workflow under test does not start the check again. (#33)
- REPAIR runs in execute mode with the fix as its one todo (`REPAIR_TODO`). (#36)
- The plan card's id is its request id, as MAF's `AgentExecutor` raises approvals, so an answer through
  `workflow.as_agent()` finds it. (#35)
- `evals.py` runs each case through the workflow as an agent (Learn, *Using Workflows as Agents*), in a fresh build
  without a session. (#35)

### Fixed

- A write approved before a later card was missed by the check, so a broken test file passed. (#33)
- A repair after finished todos came back as a new plan, because the finished todos had returned him to plan mode.
  (#36)
- The sample project's `test_inventory.py` is put back after a live run's half-done docstring edit broke it. (#32)

## [0.5.0] - 2026-11-01

Steward as a MAF workflow.

### Added

- `steward_workflow.py`: plan (structured output, `StewardPlan`) -> read_plan -> ask_approval (the `approve_plan`
  card) -> execute (the plan's steps as his todos, in execute mode) -> report. Denied, nothing runs. (#30)
- A model-free check after EXECUTE, repaired until it passes, at most three attempts. The attempt count is workflow
  state, kept across a card's pause. (#30)
- `hosted.py` serves the workflow on MAF's `ResponsesHostServer(workflow=...)`: a fresh Steward and graph per request,
  the host's state in `.as`, and one local session id. (#30)
- Evals: the plan names its work; round-trip and walkthrough cases. (#30)

### Fixed

- From the workflow's first live runs: a plan needs at least one step and one question; a clarification reaches the
  user as text; an empty plan reply is asked again once; the check counts writes approved on a card and not denied
  ones; the user's No on a card ends the run; an approved `run_shell` no longer fails the run. (#31)
- The shell is Git Bash on Windows and MAF's default shell elsewhere, so the gate's Linux runner can run the shell
  check. (#31)

## [0.4.0] - 2026-11-01

Plan mode.

### Added

- The plan-mode gate: in plan mode nothing that changes things is offered, and his own switch out of plan mode is
  refused. (#25)
- Plan-before-act evals (`python evals.py plan`, gate 0.8). (#27)
- Request hints carry the tools their work needs; misspelled tool names are repaired before dispatch. (#29)

### Changed

- Every session starts in plan mode, MAF's own default. (#22)
- He keeps a todo list for every task; no "simple task" skips the plan. (#24)
- The guide's plan mode on the host: `PlanningResponse` in plan mode, and the user's Approve switches the session to
  execute (`hosted.py`'s `plan_mode_turns`). Finished todos return him to plan mode. (#23, #26, #27)

### Fixed

- Finished work is no longer asked for a plan. (#28)
- Evals: full-conversation scoring, the discount bug planted for its case, and the test share computed from disk.
  (#29)

## [0.3.0] - 2026-10-31

The ADR-0001 items.

### Added

- Microsoft's `agent-framework-builder-python` skill, pinned to the python-1.23.0 release. (#9)
- MAF's `ShellEnvironmentProvider` tells him his shell environment before each run. (#10)
- Harness looping while his todos are open in execute mode, at most ten iterations. (#11)
- Gate stage 2: model-free checks of the harness (`test_harness.py`) on a scripted chat client. (#13)
- Atlas's door tools (`git`, `git_branch`, `git_diff`, `git_commit`, `git_push`, `records`) on his existing
  SecondBrain connection, kept to his own world by `steward_world_only`; `git_pr` joins them. (#15, #16, #21)
- DevUI with tracing (`devui_app.py`). (#17)
- Steward as an MCP tool (`mcp_app.py`, after MAF's `session_app.py` sample), on loopback port 8000. (#18)
- The improvement loop's change step as a checkpointed MAF workflow (`improvement_loop_workflow.py`). (#19)
- His SecondBrain notes as reads, the `steward-charter` note in his instructions every turn, and file memory with
  one explicit scope, `steward`, shared across sessions. (#20)

### Changed

- The workspace default is the repo root, so his own harness code is in reach. (#14)
- Reads run without a card, and the file store never reads, searches or lists a `.env` file; this supersedes the card
  per read of #14. (#20)
- The door's `state/` and `steward-mcp.log` are ignored. (#21)

### Removed

- The stdio bridge to the door with a key of its own, added in #15. (#16)

## [0.2.0] - 2026-10-30

The guide's Parts 2 to 4, the improvement loop and the CI gate.

### Added

- Parts 2 to 4 as the claw guide plans them: SecondBrain's `web_search` and `web_fetch` on one shared MCP client,
  the background `WebResearchAgent` beside `CodeExplorer`, and SecondBrain's skill notes beside the file skills. (#2)
- `improvement_loop.py`: the cookbook's agent improvement loop. (#2)
- CI gate stage 1: every Python file compiles and the sample project's tests pass. (#3)
- Four regression cases from the improvement loop in `evals.py`. (#5)

### Changed

- The improvement loop uses the cookbook's `reasoning_effort`, medium, for every stage. (#4)
- From Part 3 the web tools belong to the `WebResearchAgent` alone. (#7)
- The evals run each query streamed, so MAF's tool checks see every round. (#8)

### Fixed

- `evals.py` prints its results in UTF-8. (#6)

## [0.1.0] - 2026-10-29

The MAF redo.

### Added

- MAF's get-started samples 01 to 07, the harness samples and the claw guide's steps 1 to 4, on local Ollama
  (committed before the first pull request).
- `hosted.py` serves Steward on 127.0.0.1:43120 (Responses protocol); every span is written to
  `halo_traces/traces.jsonl`.
- `steward.Modelfile` and the stewardship changes to `agent.py` and step 1. (#1)
