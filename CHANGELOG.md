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

### Added

- `STEWARD_SANDBOX=hyperlight` (off by default, so nothing changes until it is turned on): CodeAct runs in MAF's
  Hyperlight sandbox (`HyperlightCodeActProvider`, harness/ at `/input/harness`) instead of Monty, and a `run_shell`
  after untrusted content (a note, an Estate log, the web) is refused without running and sent to `execute_code`.
  Probed once at start; if Hyperlight cannot run (Windows Hypervisor Platform off), one line is logged
  (`Hyperlight sandbox off: <reason>`) and the build is today's. Test:
  `test_the_hyperlight_sandbox_is_off_by_default_and_on_runs_codeact_and_the_untrusted_shell_in_it`.
- The last Estate controls as skills. `ollama-ops` reads Ollama's loaded models with `secondbrain_estate_status`,
  unloads a stale or crowding model only with `secondbrain_ollama_unload` on Kyle's card, and reads the pinned
  `OLLAMA_*` settings from the Ollama settings note in SecondBrain, never from `.env`. `approvals` answers what Kyle
  approved, denied or left waiting from `secondbrain_approvals_history` and `secondbrain_hold_status` (how one held
  door call ended), and never acts on a card. `hold_status` joins `ESTATE_READS`: on his live build, no card. Test:
  `test_the_ollama_ops_and_approvals_skills_read_and_leave_every_change_to_the_card`.
- `STEWARD_FIDES_ENFORCE` (off by default, so nothing changes until it is turned on): `on` turns on MAF's FIDES
  `block_on_violation` for his sinks (file writes, `run_shell`, `git_commit`, the door's branch, commit, push and PR,
  note writes and the Estate's asks). A sink called after untrusted content (a web page, a note, an Estate log) is in
  his context is refused, MAF's refusal is his tool result, and its `halo_traces/fides.jsonl` line says `"blocked":
  true`. Every other tool keeps the record-only enforcer. Test:
  `test_fides_enforce_refuses_an_untrusted_write_and_leaves_a_trusted_one`.
- Two read skills for the Estate's own record. `eval-history` (`scripts/eval_history.py`) compares the last runs of
  a set in `storage/evals/history.jsonl`: each run's counts, commit and model, its failed checks, and which checks
  flipped between the last two. `telemetry` (`scripts/telemetry.py`) summarises the newest spans of
  `halo_traces/traces.jsonl` (runs, model calls by model, tool calls by tool, errors), reading only the file's tail
  (`--kb`, 1024 by default, at most 4096), never the whole file. Both are reads and run through the skills' script
  runner. Test: `test_the_eval_history_and_telemetry_skills_compare_runs_and_read_only_the_traces_tail`.
- Approvals cross the MCP door: a turn through `mcp_app.py` (Manjuel's `maf` face, Aurora's `ask_steward`) that
  reaches a tool needing approval no longer ends with the card unanswered. Each `function_approval_request` is asked on
  SecondBrain's `approval_ask` (its MCP server, `SECONDBRAIN_MCP_URL` and `SECONDBRAIN_MCP_KEY`, on a client of its own
  read for 660 s), which raises the card in the Agent tab, the Approvals shelf and Telegram tagged "Manjuel / MCP" and
  answers No after 10 minutes. The answer goes back on the same session as MAF's `function_approval_response`, and
  the turn continues (`run_with_cards`, at most `MAX_CARD_ROUNDS` rounds). Without SecondBrain the cards are left
  unanswered, as before. Tests: `test_a_card_under_the_mcp_host_is_asked_in_secondbrain_and_allow_runs_the_tool`,
  `test_a_card_under_the_mcp_host_denied_runs_nothing_and_the_turn_still_ends`,
  `test_secondbrain_cards_asks_approval_ask_and_only_an_allow_is_yes`.
- Ollama's timings on every chat call: `load_duration`, `prompt_eval_duration`, `eval_count` and `eval_duration`
  (nanoseconds; tokens for the count), which MAF's `OllamaChatClient` drops, are added to the call's usage as
  `ollama.<field>` (MAF's `UsageDetails` is open for provider fields, `_types.py:553-557`) and set on its chat span
  under the same names, streamed or not (`_record_ollama_timings` on the live build's client). Test:
  `test_each_ollama_chat_call_records_its_timings_in_usage_and_on_its_span`.
- Progress from CHECK and REPAIR: MAF custom workflow events (`ctx.add_event`, `StewardProgress`, type `progress`),
  in order: "checking: pytest -q <folder>" before each folder's tests (the check reports from its worker thread through
  `check_progress`), "check passed" or "check failed", and "repair attempt n/3". A caller streaming the workflow reads
  them; the Responses host passes on only output and request_info events, so the Agent tab does not show them yet.
  Test: `test_check_and_repair_emit_progress_events_in_order`.
- History on disk for the console and the MCP door: MAF's `FileHistoryProvider`, one JSON Lines file per session under
  the repo's gitignored `storage/history` (`steward_history_provider`), in place of `InMemoryHistoryProvider`, so a
  session continued after a restart keeps its history. The console prints its session ID and `--session ID`
  continues it. A session's file not written within the host-state window (`STEWARD_STATE_RETENTION_DAYS`, 14 days;
  the rule moved from hosted.py to agent.py and is shared) is removed at start. The Responses host keeps its own
  checkpoints and in-memory history as before. MCP sessions saved before this carry their old in-memory history in
  their session file, which the new provider does not read. Test: `test_a_sessions_history_survives_rebuilding_the_agent`.
- Model drift at start: the Responses host (hosted.py) and the MCP host (mcp_app.py) compare Ollama's installed
  models (`/api/tags`, through ollama's `AsyncClient.list`) with the Estate lock (`worlds/neiro/estate.lock.json`,
  read only) for the models it gives Steward (`used_by: steward`), and log one plain warning line per model whose
  digest differs or that is not installed (`warn_model_drift`). The start never fails on it: a missing lock or
  Ollama down is one info line. Test: `test_model_drift_from_the_estate_lock_is_one_warning_line_and_never_fails_start`.
- Steward runs the Estate (Neiro), on Kyle's ruling of 2026-11-04. SecondBrain's Estate tools are on his live build
  as one more `MCPStreamableHTTPTool` (`secondbrain_estate`) with MAF's per-tool `approval_mode`: `estate_status`,
  `estate_logs` and `approvals_history` never ask; `service_control`, `ollama_unload` and `app_update` (one name for
  its check and its apply) always ask the user's card, and plan mode leaves them alone. Any other name asks
  (`default: always_require`). The tool-policy shelf reports each with its source and approval. An eval's build gets
  the reads only.
- The `estate` skill is the Estate's operations: read `estate_status` and `estate_logs` first, then restart a
  server, unload a model or check and apply SecondBrain's update, one change on the card, and read again. RULE 9
  holds (no edit, send or door restart in the ground while a Manjuel sitting is open). Its map lists the tools and
  the five repositories as the door names them.
- The door's git tools and the `github` skill reach the Estate's five repositories (`research`, `atlas`,
  `secondbrain`, `steward`, `neiro`), every write still on the card; `pr_checks` takes the `project`.
  `estate_door_gate` replaces `steward_world_only`. A tag, a release, closing main, and a force, mirror, all, tags
  or delete flag or a path under `Desktop\Archive` in a door argument are refused before any card. The same
  patterns (`ESTATE_GIT_REFUSALS`) are in his shell's `ShellPolicy` denylist: no push, tag, release, history rewrite
  (rebase, amend, filter-branch), deleting main, or Archive path. The door does not carry `neiro` yet and refuses it
  by name.

### Changed

- Each workflow step's model calls are offered only that step's tools, not the whole set (the bar at 98d54d5: 43 tools
  in an eval's build, 56 live, on every call; of 56 PLAN calls in the traces, 4 wrote a call's arguments as text and
  one called `functions?`). PLAN gets the reads, the todo tools and his memory's reads (22 in an eval's build, of 43);
  ANSWER everything that changes nothing; EXECUTE and its repair everything but `git_commit` (COMMIT's) and the mode
  tools. Ollama has no `allowed_tools`, so `step_tools_turn` (chat middleware) cuts the call's live tool list in
  place, as MAF's own `remove_tools` does; a left-out tool is not found if called. A host that runs Steward without
  the graph is offered everything, as before. Test: `test_each_workflow_step_is_offered_only_its_own_tools`.

### Removed

- The older build path (`part > 4`), called by no host, caller or test in this repo, SecondBrain's Electron app or
  Manjuel: its Coder, Reasoner and Explainer background agents (`STEWARD_REASONER_MODEL` deepseek-r1:14b and
  `STEWARD_CONVERSATION_MODEL` gemma4:26b, `_TEAM_CONTEXT`), its `STEWARD_INSTRUCTIONS`, its `_build_explorer_agent`
  and its own SecondBrain connection (`_connect_secondbrain` and its tool lists). A part above 4 is now refused. The
  live build (CodeExplorer and WebResearchAgent) and the improvement loop's coder (`STEWARD_CODER_MODEL`,
  qwen2.5-coder:14b) are unchanged. Test: `test_the_older_team_path_is_gone_and_the_live_team_is_kept`.

### Fixed

- A plan written as JSON text in the model's own shape now raises the plan card (the bar at 6d8b127, the README
  ask's run 2: `{"summary": "...", "steps": [{"title": "Locate README.md", "action": "read file ..."}, ...]}` ended
  with "No plan card"). `steward_plan_in` reads a plan-shaped object with no `type` (a `summary` or `question`, and a
  `steps` list of strings or of objects with a `title`, `action` or `description`) as the approval: each step one
  line ("Locate README.md: read file ..."), the summary the card's question. A blank step, a step with no line, or no
  summary is still no plan, and PLAN is asked again. Run 1's README write written as text is asked again
  (`PLAN_NOT_A_CALL`), nothing is written, and its answer in either shape raises the card. Test:
  `test_a_plan_written_as_json_text_in_its_own_shape_gets_the_plan_card`.
- EXECUTE is no longer offered CodeAct (`execute_code`; the steps set at 6d8b127 called it seven times and never
  wrote inventory.py). CodeAct is for counting and calculation, so ANSWER keeps it; EXECUTE gets it only while the
  Hyperlight sandbox is on, where `SANDBOX_SHELL_REFUSAL` sends a shell step to it. The steps set's empty first PLAN
  reply had been asked again (`PLAN_AGAIN`) and its second reply was the plan; `PLAN_AGAIN` now asks for the
  structured plan by name, as `PLAN_NOT_A_CALL` does. Test:
  `test_execute_is_not_offered_codeact_and_an_empty_plan_is_asked_for_the_structured_plan`.
- A run no longer ends on an empty reply (the bar at 98d54d5: the item_count ask's last reply was `''`). MAF's harness
  loop asks once more (`plan_reply_loop`, feedback `answer`): the turn's message carries `ANSWER_NOW_KEY`,
  `tools_off_to_answer_now` makes it a `tool_choice` "none" call, and `answer_when_tools_are_off` adds
  `TOOLS_OFF_ANSWER_NOW`, as when a limit trips. Once per run; not for a plan-mode reply (READ_PLAN asks for the
  plan), but for the ANSWER step and for work that is done. `IN_WORDS_KEY` now lives in agent.py (hosted.py imports
  it). Test: `test_an_empty_last_reply_is_asked_once_more_with_tools_off`.
- A blank plan step no longer ends the run (the bar at 98d54d5, the README ask: an approved plan's steps held `""`
  lines, they were stored as todos, and MAF's todo store refused the blank title on its next load: `ValueError: Todo
  item title must be a non-empty string`). `StewardPlan`'s steps are non-blank in the schema Ollama is sent, so a
  reply with a blank step is no plan and PLAN is asked again; `approved_plan_turn` never stores a blank step. A
  tool's own argument error (`todos_add` with an empty title) already comes back to him as the tool's error result,
  and the run goes on. Test: `test_a_blank_plan_step_or_an_invalid_tool_argument_never_ends_the_run`.
- The PLAN step ended on a tool call's arguments written as text, so no plan card came (the bar at 0016cf4: the
  README ask's `{"query":"pytest"}`, which fits `search_code` and `secondbrain_search_notes`; the steps set's
  `{"edits": [...], "file_name": ".../inventory.py"}`, which fits `file_access_replace_lines` and
  `file_memory_replace_lines`). In the plan step a write written as text is now the one gated write it fits, which
  the plan-mode gate answers with its refusal as the tool result ("plan first; writes come after approval"); nothing
  is written, and file memory's never-asking write is never chosen. A read still runs as before. A reply that is, or
  ends with, a JSON object and holds no plan is sent back to PLAN once with `PLAN_NOT_A_CALL`, asking for the
  structured plan. Test: `test_a_plan_step_ending_on_a_tool_calls_arguments_gets_a_plan_card`.
- A bare file name was written at the repository root (small run 1, the item_count ask: a stray `inventory.py`
  beside the sample project's, and `check_covers_writes` failed on it). A write of a bare name that is no file at the
  root, when the request names a folder holding that file (or the file itself), is refused, even with its card
  approved, and the refusal names the path the request meant. It is refused rather than moved because MAF's file
  tools take the path the model gives and the harness never rewrites a call's arguments. The evals' resets (the small
  asks and the steps set) also remove every untracked file a run created anywhere in the repository, and leave what
  was untracked before it. Test:
  `test_a_bare_file_name_the_request_put_in_a_folder_is_refused_and_the_evals_remove_a_runs_stray_files`.
- The README eval ask asked for a line the README already had (bar run B, 2026-11-04 22:09Z, head 06657a1: "No plan
  card", he said the README already holds "Run the tests:" / "python -m unittest -v", committed since c17cd62). For
  that ask only, `readme_run_tests_removed` takes the how-to block out of the working copy, its line endings kept, and
  puts it back after, as `discount_bug_planted` plants the bug; the committed README never changes. Test:
  `test_the_readme_ask_runs_with_the_readmes_how_to_taken_out_and_put_back_after`.
- A run whose tool-call limit tripped ended on MAF's "Function invocation limit reached before a final answer could
  be produced." (bar run A, 22:05Z, the item_count ask). MAF's way is one more call with `tool_choice` "none"
  (`_tools.py:4850-4877`; Ollama then sends no tools), but nothing told him: on that call he wrote `todos_complete`
  again, and MAF dropped it for its fallback text (`_tools.py:2938-2951`). Chat middleware `answer_when_tools_are_off`
  adds one call-local line to that call only (`TOOLS_OFF_ANSWER_NOW`: the tools are off, answer now in text), so the
  reply is his; `no_nudge_in_reply` counts the line as a harness message. Test:
  `test_when_the_tool_call_limit_trips_the_last_call_asks_for_his_answer_and_his_answer_is_the_reply`.
- The discount ask's last reply answered a question never asked ("the total number of code lines in the `harness`
  directory is **42**", bar run A). The traces (21:5xZ) show the cause: the execute turn carries the approved plan
  ("divide the discount percent by 100"), `RequestHints` matched "percent" in it, and the evidence check sent him to
  count lines in CodeAct. Persistent history was not it (eval builds pass no history provider). A harness turn now
  names its request (`REQUEST_KEY` on `execute_message`; "" on a repair turn) and the hints match that alone
  (`asked_request`). Test: `test_an_approved_plans_wording_never_matches_a_request_hint_only_the_request_does`.
- A step ended with no call after malformed tool calls (steps eval 2026-11-04 21:52, head 90dc8d4: three "error parsing
  tool call" in EXECUTE, "No write to inventory.py. Calls: []"). Ollama's error carries the model's raw text; when it
  decodes leniently (a raw line break inside a string, text after the object) to arguments that fit exactly one offered
  tool, or names one (`tool_call_in_raw`, the fit rule `tool_call_in_text` uses), it runs as that call, given back as
  Ollama's own tool call. When the retries and the one unload are spent, the model is asked once more with the parse
  error as a correction turn (`TOOL_CALL_CORRECTION`) before the error is the run's. The steps log did not hold the
  raw text, so the test replays a write whose code carries raw line breaks. Test:
  `test_a_malformed_tool_call_in_execute_is_recovered_or_corrected_and_the_write_happens`.
- A run ended by a cut connection after the stale-runner unload (eval run 2026-11-04 21:46, README ask: two malformed
  tool calls, the unload, then httpx's `ReadError`). The unload ends the runner and cuts the connection it was serving,
  so within `_AFTER_UNLOAD_SECONDS` (120 s) of an unload a call cut by `httpx.ReadError` or `RemoteProtocolError`
  (ollama's `AsyncClient` is httpx) is asked once more against the reloaded model; with no unload behind it, it is the
  run's error as before. Test: `test_a_call_cut_right_after_the_runner_is_unloaded_is_asked_again`.
- The answer given twice in a non-streaming run (the MCP door). After #93 the Agent tab showed it once, but MAF's
  loop returns a non-streaming run as one combined response (`_aggregate_response`: every pass plus the injected
  nudges), so the text carried the answer, the open-todo reminder and the answer again. `answer_once`, outside the
  loop, drops the loop's own user messages and the text of a passage after a nudge that repeats what is already given
  (`repeats_what_was_shown`, moved from hosted.py to agent.py so both share it); his tool calls stay. Test:
  `test_a_non_streaming_answer_after_the_todo_nudge_is_given_once`.
- A read routed to the plan (live 2026-11-04 13:41, "What is the estate status right now? Read it with
  estate_status and list each service with up or down."): the router's model called it a task, so it got a plan card
  and todos. `ROUTE_PROMPT` now counts read-only tools, status, logs, history, "what is", "show", "list" and "how
  many" as an answer, with that request as its example; and `asks_only_to_read` sends a request that names one of
  the Estate's reads (`ESTATE_READS`) and no change word (write, fix, add, commit, restart, update, delete, ...) to
  the answer step whatever the model says. "Restart the glass" and "Fix the bug in inventory.py" still plan.
- An answer given twice after the open-todo nudge (live 2026-11-04, Agent tab, "What is the estate status right
  now?"). His first pass gave the table but left the plan's todos open, so MAF's `todos_remaining` loop re-ran him
  with `todos_remaining_message` ("Continue working through them now ... only stop once every todo item is
  complete"); he marked them done and gave the table again. The reminder now ends with `TODOS_ALREADY_SHOWN` (his
  words are already shown; do not repeat the answer), and the Agent tab's `_only_his_own_words` holds his words
  after a nudge until he calls a tool, is nudged again or ends, and does not show a passage that mostly repeats
  what it already shows (`repeats_what_was_shown`). His tool calls and his first pass stream as before; the
  `no_nudge_in_reply` eval also watches the new text. Test: `test_an_answer_given_before_the_todo_nudge_is_not_given_again`.
- Security audit, 2026-11-04 (each with a test that goes red when the fix is unplugged):
  - SecondBrain's web tools are untrusted content to FIDES: `secondbrain_web_tools` connects them through
    `labelled_mcp_tool` (`IntegrityLabel.UNTRUSTED`), as his notes and the Estate are, and WebResearchAgent records
    with its own `fides_observer` (`web_search` and `web_fetch` are its data fetchers). FIDES stays record-only.
  - His shell sees no keys. `LocalShellTool` gets MAF's `clean_env=True` with `shell_env()`: the names Windows, Git
    Bash, git, Python and pytest need, the `PYTHON*` and `LC_*` ones and his own venv first; never a name `.env` sets
    (`SECONDBRAIN_MCP_KEY` among them) nor one that reads as a secret.
  - The workflow's commit takes only what the run wrote. `record_written_files` (function middleware) keeps each file
    a MAF write tool wrote in the run's session; `git_commit` stages and commits only those (`git commit --only`),
    never `git add --all -- .`, and says so when there is nothing. The commit step runs it through the agent's
    function middleware with EXECUTE's session (`invoke_through_middleware`), not `FunctionTool.invoke` alone; a new
    approved plan starts the list again, a repair keeps it.
  - An error raised by SecondBrain's MCP server (notes, the Estate, the web) reaches him without the server's text
    (`withhold_untrusted_errors`). MAF's `include_detailed_errors` is one switch per client, so it stays on for his
    own tools, whose error text he repairs from.
- Two stale docstrings: `hosted.py` (Steward is built per request, not once and kept warm) and `agent.py`'s team list
  (the live build is CodeExplorer and WebResearchAgent; Coder, Reasoner and Explainer only on the unused part > 4
  path).
- The small-ask evals pass and fail for the right reason (audit 2026-11-04, against the cookbook's answer-level
  checks). A case whose fixture raises (`discount_bug_planted`) fails that case with the reason and the set goes on
  and records its history (`fixture_entered`; the regression and steps sets too). `answer_on_topic` scores his own
  last reply, not the workflow's `ask_commit`, `report` or `commit` outputs: the denied commit's sentence quoted
  "item_count" and passed it for him. `written_python_files` counts a write only when its tool result, where present,
  says it wrote; the small asks also ask the disk, since the workflow-as-agent response carries no tool results, so
  an approved card the middleware or the tool refused is no write. `edit_keeps_file_whole` also fails a file that
  lost a top-level function or class. Two result checks run the sample project after each ask, before the reset:
  `discount_test_passes` (its `test_percent_discount` passes) and `item_count_works` (`item_count` returns the total
  quantity, in a fresh Python); the baseline stays 10, now of 16. The evals run real commands on his PC, so the small
  and steps sets approve a `run_shell` card only when its command is the sample project's pytest
  (`card_approved`, `is_sample_project_pytest`) and deny every other shell command; the steps set approved them all.
- The background CodeExplorer's own `read_file`, `search_code` and `list_files` never read, search or list a `.env`
  file (RULE 7), as the file store already kept them from the `file_access_*` tools; they had no such check and run
  without a card (audit 2026-11-04).
- A whole-file write of a `.py` file must parse, or it is refused and nothing is written (`whole_write_problem`, in
  the write middleware beside the Unicode-punctuation check). On 2026-11-04 at 10:14 Steward overwrote the sample
  project's `inventory.py` with a shortened stand-in (its docstring's first words and "..."). Edits made in parts
  (`file_access_replace`) are not judged.
- The evals put the sample project back to its committed text (`sample_project_as_committed`, `git checkout HEAD`)
  before they snapshot it. Their resets restored what was on disk when they began, so the damaged file was every
  later run's "original": the bug could not be planted, and the live eval of 2026-11-04 spent the discount ask
  debugging the harness.
- A tool call written as text whose keys fit several tools now runs as the one read-only tool among them, judged by
  MAF's own read-only approval rules (`READ_ONLY_RULES`, shared with the build's approval rules); a write is never
  chosen, and zero or several read-only fits stay text (live eval 2026-11-04: the discount ask's plan step wrote
  `{"file_name": ...}`).
- The small-ask evals see a write approved on its card. `_run_answering_cards` kept only the agent's streamed
  updates and dropped its own Approve answers, which carry the approved call, so `check_covers_writes` and
  `edit_keeps_file_whole` reported "no write" on a run that wrote (live 2026-11-04, item_count). Each answer now goes
  into the scored conversation right after the turn that raised its card. A run that writes nothing still fails.
- A denied commit says which change was not committed: `The commit "<message>" was not approved, so nothing was
  committed.` (live eval 2026-11-04: the bare sentence left a denied run's last reply naming nothing).
- He never asks about committing in words (live evals 2026-11-04, three runs: "Do you approve this commit?" in prose,
  so no card). The commit step writes only the message: one structured-output call (`CommitMessage`, one line of at
  most 72 characters, at least two words), then the workflow raises his `git_commit` card itself; Approve commits,
  Deny commits nothing. An unparseable message is asked again once, then built from the request and the changed
  files.
- A stale Ollama runner recovers by itself. When both malformed-call retries fail, Steward unloads the model once
  (`keep_alive` 0) and asks again on a fresh runner, at most once per 10 minutes per process. Measured 2026-11-04: a
  runner past 141,000 tasks wrote garbage into tool calls and failed a whole eval; a fresh one on the same settings
  made 20 of 20 valid calls.
- Evals never reach the owner's door (live 2026-11-04: the eval's Steward committed through the door and parked a real
  card in his window). An eval's Steward is built with `eval_build=True`: no Atlas door tool, no `pr_checks`, no note
  write; note reads, the Charter, skills and the web stay.
- A `.py` write with Unicode dashes, curly quotes or a no-break space outside a string or comment is refused with its
  line, column and the ASCII character to use (live 2026-11-04: gpt-oss wrote U+2011 into code, a SyntaxError).
  `refuse_unicode_punctuation_in_code`, function middleware on Steward's and the coder's write tools; nothing is
  rewritten for him.
- An eval case whose run raises fails, and the set goes on (live 2026-11-04: Ollama's "error parsing tool call" in
  one ask aborted the whole `small` set with a traceback). The case is scored "the run raised <Type>: <first line>"
  (`run_completed`), the sample project is put back, and the exit code is 1. `--options NAME` runs a set with a named
  settings set from `eval_options.json` (baseline, plan_t0, execute_think_low, plan_think_high); the report's first
  line names it.
- The plan step runs a tool call written as text (live eval 2026-11-04, the discount ask: the plan came back as
  `{"directory":...,"glob_pattern":"*"}`). `recover_text_tool_calls` now also recovers when a Pydantic
  `response_format` is set, but only when the reply does not validate as that format, so a valid plan is never made a
  call; a dict schema is left as before.
- His memory holds only what he saves (Kyle, 2026-11-04: "Deliberate only"). Live, MAF's automatic extraction on
  gpt-oss saved his own answers (order_total) and his memory eval's output (Kestrel-47 codenames) as facts and doubled
  what he had saved himself with `write_memory`, whatever its prompt said. `steward_memory()` sets
  `max_extractions=0`; the index, the topics in front of him, `write_memory`, transcripts and consolidation stay.
  `MEMORY_EXTRACTION_PROMPT` is retired; his Charter (v4.2) says what to save. Six extracted topics moved to
  `agent-file-memory/attic/2026-11-04-memory-extraction-junk` (kept). Restart required.
- The host's state is no longer kept forever (Kyle, 2026-11-04: 14 days). At start, `expire_host_state` removes
  responses, workflow records and checkpoints older than `STEWARD_STATE_RETENTION_DAYS` (14), through the hosting
  SDK's store calls where it has them, and keeps anything an unanswered approval still needs; superseded checkpoints
  go at once. The SDK's 30-day store TTL applies only when a store is read again, `FileResponseStore` has no expiry,
  and the Responses host never reclaims superseded checkpoints (29 MB on 2026-11-03). Restart required.
- A misspelled tool name is repaired on streamed calls too (live 2026-11-03: `totos_complete`, "not found"). Streamed,
  the context's stream hooks were lost, so `repair_tool_names` now wraps the stream (`names_repaired_as_they_pass`) as
  `recover_text_tool_calls` does; nothing is held back. The test suite no longer writes `halo_traces/` (an autouse
  fixture sends traces, metrics and logs to each test's temp folder).
- A tool call written as plain text runs as that call. gpt-oss sometimes ended a turn with a tool's arguments as its
  reply (live 2026-11-03: `{"directory":"steward/working","glob_pattern":""}`), so nothing ran. `recover_text_tool_calls`
  (chat middleware, inside MAF's tool loop) turns one JSON object that fits exactly one offered tool into that call;
  only a streamed reply that opens with `{` or a fence is held back, so prose still streams. The Ollama
  malformed-call retry stays on the client: streamed, that error arises outside the chat middleware.
- The memory eval's recall check reads a Unicode hyphen as a hyphen. Live 2026-11-03 (the first memory eval to finish
  with an approved run_shell), he recalled the codename in a new conversation as "Kestrel‑47" with U+2011, and the
  check, looking for "Kestrel-47", failed a recall that had happened.
- His service's telemetry stays out of `steward.log` (192 MB on 2026-11-03). The host's default observability, the
  microsoft-opentelemetry distro, printed every metric, span and log record as indented JSON on stdout. `hosted.py`
  now passes the host's own `configure_observability` hook `steward_observability`: spans to HALO as before; metrics
  and OTel log records through OpenTelemetry's console exporters into rotating files, `halo_traces/metrics.jsonl` and
  `logs.jsonl` (10 MB, five kept). A swallowed workflow failure is logged with its traceback, as MAF's own
  `_log_response_failure` does. Telemetry is named `steward`; OTLP is `http/protobuf`. Restart required.
- The Agent tab shows only his own words. MAF's AgentLoopMiddleware streams its nudges ("Progress so far", the
  open-todo reminder) as user updates between passes, and the Responses host glued them into his message (live
  2026-11-03, the Juniper answer). `hosted.py`'s `_only_his_own_words` drops them with `ResponseStream.flat_map`, as
  MAF's `WorkflowAgent` does, and gives each pass its own message. The model still receives the nudges.
- With automatic memory on, an approved `run_shell` no longer fails the hosted run. MemoryContextProvider's transcript
  save (msgspec) refused MAF's `_ShellResultText`, a str subclass, and the host reported only "Native workflow
  execution failed" (live 2026-11-03: the memory eval and the diagnosis both ended there). `steward_memory()` now
  passes MAF's `history_message_filter`, `plain_tool_results`, which saves tool results as plain text. The hosted tests
  keep their response records in a temp folder, not `storage/responses`.
- Step 5: his automatic memory saves facts, not the harness's chatter. The first live recall (2026-11-03) saved six
  memories with MAF's default extraction prompt; only one was a fact. Extraction reads each run's input, which in his
  workflow's later steps is the harness's own text ("The user approved your plan", todo reminders, plan cards), so it
  was taken as the user's words, and one memory was wrong ("The assistant's name is Juniper"). MAF's
  `extraction_prompt` now carries his rules (`MEMORY_EXTRACTION_PROMPT`, the cookbook's: only facts the user states;
  never about the assistant, never the harness's messages, tasks, plans or answers), built once in `steward_memory()`.
  The five junk topics moved to `agent-file-memory/attic/2026-11-03-memory-extraction-junk`.
  `test_what_he_learns_in_one_conversation_is_in_front_of_him_in_the_next` checks the rules are sent.
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

- CI: everything the gate runs on is pinned. `requirements.lock` (pip-compile, hashed, 218 packages) holds
  pyproject's pins, the new `test` extra (pytest 9.2.0) and every dependency beneath them; the gate runs on
  ubuntu-26.04 with Python 3.14.9 and pip 26.3, installs with `--require-hashes`, and pins its actions by commit
  SHA. A test fails on a pin that was not re-locked, an action not pinned by SHA, or a `-latest` runner.
- The `estate` skill: the map of Kyle's estate, Neiro (Manjuel, SecondBrain/Jesster, Atlas/Aurora, Ollama and
  Steward): what each part is, how it connects to him (Responses on 43120, MCP on 43121, SecondBrain's MCP on 43110,
  the door on 43111), who starts what, his own records, and his reach (his repository only, for now). The Charter
  (v4.3) names the parts and points to it.
- Data for SecondBrain's shelves. Every eval set appends one JSON line to `storage/evals/history.jsonl` (newest 500
  kept; a failed write is only a warning; the report and exit code are unchanged). The live build writes
  `storage/tool-policy.json`: each tool's approval (always, never, or a rule, named) read off the built agent and its
  auto-approval rules; eval builds and the improvement round's diagnoser write nothing.
- Per-step model options, for measuring gpt-oss: `STEWARD_<STEP>_THINK` (low, medium, high, true, false),
  `_TEMPERATURE` (0 to 2) and `_SEED` for route, plan, answer, execute and repair, read once at build and logged; a
  bad value stops the build. Unset, every call's options are unchanged. Plan, answer and execute get them through
  `step_options_turn` (agent middleware setting the run's options, as `plan_mode_turns` sets `response_format`).
- `pr_checks`: he waits through the door's `git_pr` list for a pull request to open (on the owner's Approve) and for
  its checks to pass or fail, asking every 30 s for up to 20 minutes, no card; the github skill calls it before
  reporting (Kyle, 2026-11-04: "make the doors push and PR results visible"). A push's own outcome is not readable by
  a client yet: the door needs a read-only `hold_status`.
- `search_code`: he searches the workspace's tracked .py and .md files by meaning (MAF's `InMemoryCollection` and
  `create_vector_search_tool`; embeddinggemma-2:270m on the CPU, `num_gpu` 0, Kyle's ruling of 2026-11-02). Chunks are
  top-level defs and classes, and Markdown headings. The index is built on the first search; each chunk's vector is
  kept in `storage/code-search/embeddings.json`, keyed by the model and the chunk's text, so only new or changed
  chunks are embedded (after a restart 0.3 s, against 263 s cold). Reads only, no card; `STEWARD_CODE_SEARCH=off`
  turns it off.
- FIDES records what it would block, and blocks nothing (Learn, Agent Security). MAF's label tracker and enforcer in
  its record-only branch (`block_on_violation=False`; the documented dry run builds no enforcer and records nothing),
  last in his middleware: SecondBrain notes are labelled untrusted and the door trusted through `SecureMCPToolProxy`,
  `git_commit` and `run_shell` are sinks, and each would-block entry goes to `halo_traces/fides.jsonl`.
  `STEWARD_SAFETY_OBSERVE=off` turns it off. Agent Hooks stay off the live path: on 1.24.0 `evaluate_only` still
  buffers streamed replies and a streamed run inside the harness loop fails (a test measures both). Not yet labelled:
  web pages via WebResearchAgent's results and skill notes via `load_skill`; `fides.jsonl` has no size cap yet.
- An improvement round cannot change what grades it. `edit_problem` refuses a hand-off to `evals.py`,
  `eval_baselines.json`, `diagnosis_feedback.json` or `.github/workflows/`, and `refuse_grader_writes` (MAF function
  middleware on the coder and the diagnoser) refuses a write there; `test_harness.py` takes only new test functions at
  its end, so a round's proving test still lands. The workflow's CHECK fails a code change where pytest collects no
  tests (exit 5: "No tests ran for the changed files in ..."); a docs-only change is still not checked.
- His workflow routes before it plans (live 2026-11-03: a plain question came back as an approval card, "No further
  action needed"). A classifier step, `route`, makes one structured-output call (`Route`, answer or task) and MAF's
  switch-case edge group sends a question to `answer`, which replies in words with reads only, and a task, or an
  unclear route (`Default`), to the plan card as before (Learn, Workflows > Edges, switch-case).
- Every eval set exits 1 when a case fails (MAF's `EvalResults.all_passed`, `evals.exit_code`); `small --gate` keeps
  its baseline gate. The evals skill says an exit code of 1 is the result, not a broken run.
- DevUI serves Steward's workflow beside the agent, with its approval cards and a checkpoint per conversation; a test
  reads the graph through MAF's `WorkflowViz` and checks its loop-back edges (read_plan to plan, repair to execute).
- Step 6: he can run the diagnosis. His evals skill says how (`improvement_loop.py`, once, 20 to 40 minutes) and
  what to report (the Promptfoo line and the handoff's top three priorities); "diagnosis" joins the evals
  request hint. A hint assertion covers it.
- Step 6: the diagnosis traces the real workflow: `improvement_loop.py` no longer asks a bare `build_steward_agent`
  Part 3's five old read-only questions. It traces evals.py small's three asks (item_count, the discount fix, the
  README line) plus one plain question ("What does order_total do in harness/steward/working/sample-project?"), each
  once through `evals.run_small_asks`, the per-ask runner now shared with `small_main` (define once: `run_steward`,
  the same approvals, the discount bug planted for its ask only, the sample project put back, a throwaway memory per
  run), each in its own trace span; `serialize_agent_config` describes the workflow and the agent that ran. The
  feedback is `diagnosis_feedback.json` (a list keyed by the ask, edited without code; seeded from the small-ask checks
  and, for the plain question, "A question is answered directly; it does not become a plan, a clarification or an
  approval card."), and each failing small-ask check on a traced run is one more item (source_type `eval_checks`, with
  its reason; `evals.score_small_asks`, shared with `small_main`). `drop_background_spans` drops background MCP
  housekeeping traces (roots "MCP send ping", "tools/list", "MCP send tools/list", "MCP send server/discover", "MCP
  send initialize" and a bare "POST") before HALO's context is written, keeping every span of a traced ask's trace
  (1651 of a 5000-line sample of the trace file). Tests:
  `test_the_diagnosis_traces_the_small_asks_and_a_plain_question_through_his_workflow`,
  `test_the_diagnosis_reads_its_feedback_file_and_adds_each_failing_check`,
  `test_the_diagnosis_drops_background_mcp_spans_and_keeps_every_span_of_an_ask`.
- Step 5, piece 5.3: the memory eval case, `evals.py memory`. Two requests run through his workflow (`run_steward`),
  each a new conversation, sharing one throwaway automatic memory (`isolated_memory_store`; file memory is not
  shared, so a recall proves MAF's MemoryContextProvider carried it):
  the first states a fact about the sample project that cannot be guessed (its release codename) and asks him to
  remember it, the second asks for it, and `memory_recalled` passes when the answer carries it. The old `plan`,
  `roundtrip` and `walkthrough` sets retire (their mains, queries, evaluators and helpers only they used); `steps`
  keeps its own query and `STEPS_MUST_NAME`. Their two tests moved: the plan that does not name the work now fails
  the steps set's `plan_step` (`test_a_plan_that_does_not_name_the_work_fails_the_plan_step_eval`), and the denied
  commit card runs on a small ask, scored by `commit_by_tool` and `commit_message_specific`
  (`test_the_small_asks_deny_a_commit_card_and_nothing_is_committed`). New:
  `test_the_memory_eval_recalls_in_a_new_conversation_what_the_first_one_saved`.
- Step 5, pieces 5.1 and 5.2: memory across conversations, MAF's way. MAF's `MemoryContextProvider` sits beside his
  history (not in its place: as the history provider it drops the conversation's own messages, tested 2026-11-03).
  After each turn one call on his own model extracts at most five durable facts into topic files under a `MEMORY.md`
  index; before each turn the index and the three best-matching topics are in front of him; transcripts are kept and
  topics consolidated over time. Store: `steward_memory_store()` (MAF's `MemoryFileStore` under `agent-memory/`, one
  owner "steward", set on every session by the `memory_owner` middleware). Hosts pass it (the Agent tab's service,
  the improvement loop, the MCP door, the console, DevUI); evals pass a throwaway one (`isolated_memory_store`); the
  harness tests turn the default off (`STEWARD_AUTOMATIC_MEMORY=off`). His MCP door keeps each session in MAF's
  `FileSessionStore` (`storage/mcp-sessions`), so Manjuel's sessions survive a restart. His file memory now lives
  under his workspace, not the host's working folder (that made a second memory root). The unused Mem0 path and the
  `memory` extra are removed; old per-session memory and the Mem0 store moved to
  `agent-file-memory/attic/2026-11-03-old-session-memory` (329 empty folders deleted). The response store has no
  expiry option, so it is left as it is. `test_what_he_learns_in_one_conversation_is_in_front_of_him_in_the_next`,
  `test_without_a_memory_store_nothing_is_extracted_and_hosts_pass_his_store`,
  `test_the_mcp_doors_sessions_are_kept_on_disk`.
- Step 4, piece 4.1: Microsoft Agent Framework 1.24.0 (from 1.23.0; ollama, tools, monty, foundry-hosting and
  devui 1.0.0b261030, foundry 1.16.0), upgraded together. `pyproject.toml` now pins every package the hosts import,
  the MAF packages exactly, the rest at the versions the suite passed on; Mem0 and Presidio are the `memory` and
  `governance` extras. The gate installs the project (`pip install . pytest`) instead of its own list, so the pins are
  defined once. No code changed: the harness suite (52) and the sample project's tests (4) pass as they were. None of
  `hosted.py`'s workarounds is fixed in 1.24.0: the workflow host still hands `additional_function_arguments` to
  every agent and the Ollama client still passes it on, `prepare_options` still applies to every agent in the graph,
  the session id is resolved as before, and the host still releases no background tasks. `requires-python` is now
  `>=3.11`, MAF 1.24.0's baseline, and the README's "missing to deploy locally" line no longer lists the package.
- Step 4, piece 4.4: background agents finish. MAF's `background_tasks_running` and
  `background_tasks_running_message` are in his harness loop (`plan_reply_loop`, checked after its other conditions):
  while a background task (CodeExplorer, WebResearchAgent) is still running, the turn does not end, and the loop tells
  him which tasks still run and to wait for their results. Before, a turn could end while a background agent still
  ran. With no task running the loop is as before, and `loop_max_iterations` still bounds it.
  `test_a_turn_does_not_end_while_a_background_agent_still_runs`.
- Step 4, piece 4.5: skills, MAF's way. His skills source is wrapped in MAF's `CachingSkillsSource`, under the
  `DeduplicatingSkillsSource` as `SkillsProvider.from_paths` composes it, so the skill files are walked and
  SecondBrain's skills listed once per build instead of on every turn (MAF never caches a caller's own source).
  MAF's `SkillsProvider.read_only_tools_auto_approval_rule` joins his auto-approval rules, so reading a skill
  (`load_skill`, `read_skill_resource`) never asks a card, while `run_skill_script` keeps its card unless the run is
  unattended. The hosted workflow builds him for every request, so there the cache lasts one request (the runs and
  loop passes inside it, such as execute and its repairs); the console, DevUI and MCP hosts keep it for the session.
  `test_his_skills_are_discovered_once_per_build_not_every_turn`,
  `test_reading_a_skill_asks_no_card_and_running_its_script_still_does`.
- Step 6: the split fixer (the operator, 2026-11-03: "the fixer doesn't need some big huge model"), Aider's architect
  and editor in MAF's pieces. Steward diagnoses on his own model (gpt-oss reads long prompts fast) and hands each edit
  to the coder with his new `hand_to_coder` tool: a file, at most 80 lines, and the change in words. A new `HandToCoder`
  step checks each edit (a file in the workspace, real lines, a short span; a bad one goes back to Steward with the
  reason) and gives the coder only the change and those lines, numbered. The coder (`build_coder`) is a small MAF
  `Agent` on `qwen2.5-coder:14b` with only MAF's file tools (reads at once, every write on its card), his tool-call
  limits and a 16K window. Failing checks and the review's guidance go back to Steward, not the coder. The coder is a
  workflow step, not `Agent.as_tool()`, because MAF does not carry a child agent's approvals to its caller. Round 1's
  fixer, his whole harness on the coder model, opened at 13,466 tokens before reading any code. `build_steward_agent`
  takes `extra_tools`; the improve skill says how to hand edits over.
  `test_improvement_loop_workflow_diagnoses_hands_edits_repairs_reviews_and_resumes`,
  `test_a_bad_edit_goes_back_to_steward_with_the_reason`,
  `test_the_split_fixer_is_steward_diagnosing_and_a_small_coder_on_the_coder_model`.
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

- Sensitive telemetry is off by default (security audit, 2026-11-04; MAF: sensitive events "only ... on test and
  development environments"). `setup_halo_tracing` records message and tool content only when
  `STEWARD_SENSITIVE_TELEMETRY` is on, so the live hosts (`hosted.py`, `mcp_app.py`, and the console and DevUI) leave
  it out; the evals, dev runs, keep `enable_sensitive_data=True`. Set it on for a diagnosis that needs the live
  traces' content.
- The fixer's model is now `qwen2.5-coder:14b` (the operator, 2026-11-03), and `devstral-small-2:24b` is dropped.
  Measured that day with one model loaded at a time: qwen sits wholly on the 16 GB card at the fixer's 32K window
  (12.1 GB), reads 227 tok/s on a 2.7K prompt and 49 on a 17K one, and writes 28-46 tok/s; devstral kept 5-7 of its
  41 layers on the CPU at 32K and 24K and wrote 3.5 tok/s. An f16 context cache was tried for qwen's long-prompt
  reading and made it no faster (45.5 tok/s, writing 6.4), so the server stays on q8_0.
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
