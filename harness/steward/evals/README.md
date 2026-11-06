# Steward's eval sets

Each eval set is one versioned file here, `<tier>-<name>.yaml`. `evals.py` reads them at import (`load_eval_sets`);
`python harness/steward/step04_production_ready/evals.py validate` checks every file with no model, and the gate runs
it (test_harness.py and the `validate` step of `.github/workflows/gate.yml`). A set changes only by pull request.

| File | Tier | Set | Run |
|---|---|---|---|
| `t0-small.yaml` | T0, regression (frozen) | small | `evals.py small [--gate]` |
| `t0-steps.yaml` | T0, regression (frozen) | steps | `evals.py steps` |
| `t0-direct.yaml` | T0, regression | direct | `evals.py direct` |
| `t1-heldout.yaml` | T1, held out | heldout | `evals.py heldout` |
| `ext-bfcl.yaml` | ext, calibration (outside, pinned) | bfcl | `evals.py bfcl` |
| `ext-aider-py.yaml` | ext, calibration (outside, pinned) | aider-py | `evals.py aider-py` |

`baselines.json` holds, per set and version, the fingerprint of its cases (`cases`) and any baseline its gate reads
(`small` v1: `checks`). `run-bar.ps1` runs sets for their bar; `evals.py bar <set>` says whether a bar is met.

## Transports: in-process, Responses, AG-UI

An asks set (small, heldout) can reach Steward three ways, with `--transport` (run-bar's `-Transport`):

| Transport | What runs the workflow | Cards |
|---|---|---|
| `in-process` (default) | evals.py itself (`run_steward`), an eval build: no Atlas door, no note writes, throwaway memory | answered in the process |
| `responses` | the running Responses host, hosted.py on `http://127.0.0.1:43120` | `mcp_approval_request` items, answered with `mcp_approval_response` and `previous_response_id`, as SecondBrain's steward.cjs does |
| `ag-ui` | the running AG-UI host, ag_ui_app.py on `http://127.0.0.1:43122/` | RUN_FINISHED's interrupts, resumed with `interruptId` and `forwardedProps.checkpointId` |

The approval policy is the same on every transport (`evals.card_approved`): the plan, the writes and the sample
project's pytest are approved, everything else is denied. The same checks score each run (the conversation is turned
into the Messages an in-process run gives), and the result checks read the disk, so the host must serve this checkout
(its `STEWARD_WORKSPACE`). A host runs its own build: its memory, its door and its settings, not the eval build's.

Each run's line in `storage/evals/history.jsonl` carries `transport`, and each case `timings`: `transport`,
`first_event_s` (seconds to the first text or reasoning event), `total_s`, `cards`, `cards_resumed`, `card_log` (each
card's tool, the answer, and whether its resume went through) and `stream_errors`. A dropped stream or a refused
resume (an AG-UI checkpoint the host no longer has: it keeps them in memory, so a restart drops them) ends the case as
failed with its reason (`run_completed`), never as a crash.

To compare (each host started first; one model at a time, so run the sets one after another):

```powershell
powershell -File harness/steward/evals/run-bar.ps1 -Sets small -Tag inproc -Runs 3
powershell -File harness/steward/evals/run-bar.ps1 -Sets small -Tag responses -Runs 3 -Transport responses
powershell -File harness/steward/evals/run-bar.ps1 -Sets small -Tag agui -Runs 3 -Transport ag-ui
python harness/steward/step04_production_ready/evals.py compare-transports --set small --last 3
```

`compare-transports` prints, per case and transport, the runs passed, the median time to the first event and total
time, the cards resumed of those answered and the stream errors, then the decision line.

**The decision rule.** AG-UI goes on by default only if, on every case, it matches or beats `responses` on the result
(the share of runs passed) and on the resumes (the share of cards resumed), with no stream error on any case. Anything
short of that keeps it off, and the decision line names each case that fell short. Time is reported, not ruled on.

## A set file

```yaml
name: heldout              # lower-case word; the file is <tier lower-cased>-<name>.yaml
tier: T1                   # T0..T9, or ext for a non-gating set
version: 1                 # whole number from 1
owner: operator            # who approves a change to the set
runner: asks               # asks: each case one run (evals.py <name>); steps: the workflow's steps scored
split: full                # MAF's ConversationSplit: full for multi-step cases (T0 and T1 use full), or last_turn
bar: {passed: 4, of: 5, runs_in_a_row: 2}   # of = the number of cases
changes:                   # what each version changed; the current version must have its line
  1: Five asks on sample-project-2.
cases:
  - id: add_function
    ask: Add a function ... to harness/steward/working/sample-project-2/units.py ...
    fixture: {project: harness/steward/working/sample-project-2, plant: null}   # plant: a name in evals.PLANTS
    subject: [fahrenheit_to_celsius]   # lower-case terms an on-topic answer (and a commit message) names
    precondition: fahrenheit_to_celsius_works   # a RESULT check that must FAIL on the fixture before the run
    checks: [plan_is_approval, edit_keeps_file_whole, no_nudge_in_reply, answer_on_topic, fahrenheit_to_celsius_works]
    # optional, handed to MAF's evaluate_agent as they are:
    # expected_output: "..."
    # expected_tool_calls: [{name: load_skill}, {name: background_agents_start_task, arguments: {agent_name: CodeExplorer}}]
```

Optional at the set level: `num_repetitions: N`, only for a non-gating set (tier `ext`, e.g. a flakiness check):
the whole set runs N times, each pass scored and recorded on its own. A gating tier (T0 to T9) runs each case once.

## What validate refuses

- A key that is unknown or missing, a name, tier, version, split, runner or bar of the wrong shape, a file named
  for another set, or a version with no `changes` line.
- A check the runner does not have (`evals.ASKS_PROCESS_CHECKS`, `evals.RESULT_CHECKS`; the steps runner scores
  exactly `plan_step`, `execute_step` and `steps_overall`), or a plant not in `evals.PLANTS`.
- A case with no RESULT check (only process checks such as plan_is_approval): every case checks the work itself.
- A case whose `precondition` already passes on its fixture (the plant entered, nothing run): the ask asks for what
  is there, as the old README ask did before its how-to was taken out of the working copy.
- The same set name twice, or one ask in two asks sets.
- Cases that differ from the fingerprint recorded for the set's version in `baselines.json`.

## Adding a case or a set (Steward's eval-author work)

1. _(2026-11-05, [ADR-0012](../../../docs/decisions/0012-stewards-bar-is-our-own-capability-evals.md): a capability
   tier's cases come from the coverage map, [spec 001](../../../docs/specs/001-capability-evals.md), one per
   capability, before any failure; error analysis, below, still adds cases for failures that recur.)_
   Start from a failure, not an idea: read the failing traces and the eval history, label each failure, count the
   labels, and write a case for the one that recurs (the cookbook's error analysis: label, count, then write the
   case). A public or imported set is for calibration only, never a gate: its cases may already be in a model's
   training data.
2. A case needs a result the disk can show. If no RESULT check measures it, add one to `evals.py`: a measurement
   function (no model, deterministic) named in `RESULT_CHECKS`, and its `@evaluator` in `SMALL_ASK_EVALUATORS`.
   If the fixture already satisfies the ask, add a plant step to `PLANTS` that makes the precondition in the
   working copy only and puts the file back; the committed sample project stays green.
3. Edit the set file and bump `version` (any change to a case or a check is a new version), say what changed under
   `changes`, and run `evals.py validate`: it names the new fingerprint to record in `baselines.json` under the new
   version. Keep the old version's entry: history lines carry `set_version`, so runs compare like with like.
4. A new tier is a new file (`t2-<name>.yaml`); earlier tiers stay as regression gates.
5. Open a pull request; it lands when its checks pass.

## T0 direct: the plan phase alone (the plans runner)

`t0-direct.yaml` holds direct asks, where a request names one of his tools and its arguments. They are scored on the
plan card alone. Its one case (v1) is the operator's ask from session-20261105-1110-535a, word for word: "Run the bfcl
eval set once with eval_start, tag ext-bfcl-first. Tell me when it has started." That ask reached its card after 18
EXPLORE calls in 15 minutes. The runner `plans` runs each case once through the workflow, in an eval's build (which
offers no `eval_start`), up to its plan card. Every card is denied, so nothing runs after it. `plan_reached_directly`
scores the card with no model:

- the card came within the case's `max_calls` tool calls (2);
- none of those calls was `search_code` or a `file_access_*` read;
- the plan's summary and steps name each `subject` term (`eval_start`, `bfcl`).

A plans case is `{id, ask, subject, max_calls, checks}`. It has no fixture, plant or RESULT check: nothing on disk
changes, and its plan card is its result. Validate checks its shape and its fingerprint like any other set. The test
`test_a_direct_ask_reaches_its_plan_card_with_no_code_reading` runs this case on a scripted client in the gate. A model
run is one case, about a minute:
`powershell -File harness/steward/evals/run-bar.ps1 -Sets direct -Tag direct-first -Runs 1`.

## T1, held out

`t1-heldout.yaml` runs on `harness/steward/working/sample-project-2` (units.py), which no T0 fix was tuned on. Its
five asks: add `fahrenheit_to_celsius`; fix the planted `fahrenheit_bug` (`test_boiling_point`); rename
`LENGTH_IN_METRES` to `METRES_PER_UNIT` with the tests green; add the README line listing the length units; make the
planted failing `test_format_quantity_without_unit` pass without changing it. Bar: 4/5, twice in a row. Each run puts
the project back as committed (git checkout of the folder) and removes any untracked file it left in the repository.
Never tune the harness on these asks.

## ext, outside sets (calibration only)

`ext-bfcl.yaml` and `ext-aider-py.yaml` are public benchmarks, pinned once in `data/` (each folder with its source's
LICENSE; the set file's `source` names the repository, the commit, the license, the attribution and a contamination
note). Nothing is downloaded at run time. They calibrate Steward against outside numbers and are never a gate: their
cases may be in a model's training data, and no harness change is tuned on them. Their code is
`step04_production_ready/ext_sets.py`.

| Set | Source (commit, license) | Cases | Scored by |
|---|---|---|---|
| bfcl | ShishirPatil/gorilla `6ea5797`, Apache-2.0: BFCL v4 | simple_python 20, multiple 15, parallel 15, parallel_multiple 15, irrelevance 15 | `bfcl_ast_match`, `no_tool_called` |
| aider-py | Aider-AI/polyglot-benchmark `7e0611e`, MIT (Exercism's Python track) | 20 exercises | `exercise_tests_pass` |

- **bfcl** (runner `bfcl`): each case's functions are offered to a bare MAF `Agent` on Steward's model
  (`OllamaChatClient`, `OLLAMA_MODEL`) as declaration-only tools (`FunctionTool(func=None)`: the run stops on the
  calls, nothing runs), with no Estate tool and no instructions. MAF's `evaluate_agent` scores the calls against the
  case's possible answers (its `expected_output`): `bfcl_ast_match` is BFCL's AST check (the function, its required
  parameters, no parameter the answer lacks, each value among its acceptable ones; one call for simple and multiple,
  one-to-one in any order for the parallel kinds), `no_tool_called` the irrelevance check.
- **aider-py** (runner `exercises`): each exercise (stub, tests, instructions) is copied into
  `harness/steward/working/ext-aider-py/<name>` (gitignored, removed after the case) and Steward's workflow runs the
  ask on it as the asks runner does: the plan and the writes approved, a shell card only for pytest on that folder,
  git_commit and everything else denied. `exercise_tests_pass` then runs the PINNED test file on the stub he left
  (`python -m unittest`, 60 s at most): all green or fail. No Docker. Validate checks that each stub fails its tests.

An ext set's cases are `{id, checks}` (an id in the pinned data, the runner's one check); its fingerprint covers the
cases, the source and every pinned file, so a change to the snapshot is a new version too. `num_repetitions: N`
runs each case N times (a flakiness reading). Run one in its own window, one model at a time:

```powershell
powershell -File harness/steward/evals/run-bar.ps1 -Sets bfcl,aider-py -Tag ext-first -Runs 1 -RunMinutes 300
```

To re-pin from a newer source commit: copy the rows or exercises again, update `source.commit` and `changes`, bump
`version`, and record the fingerprint `evals.py validate` names.
