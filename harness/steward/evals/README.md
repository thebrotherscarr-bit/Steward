# Steward's eval sets

Each eval set is one versioned file here, `<tier>-<name>.yaml`. `evals.py` reads them at import (`load_eval_sets`);
`python harness/steward/step04_production_ready/evals.py validate` checks every file with no model, and the gate runs
it (test_harness.py and the `validate` step of `.github/workflows/gate.yml`). A set changes only by pull request.

| File | Tier | Set | Run |
|---|---|---|---|
| `t0-small.yaml` | T0, regression (frozen) | small | `evals.py small [--gate]` |
| `t0-steps.yaml` | T0, regression (frozen) | steps | `evals.py steps` |
| `t1-heldout.yaml` | T1, held out | heldout | `evals.py heldout` |
| `ext-bfcl.yaml` | ext, calibration (outside, pinned) | bfcl | `evals.py bfcl` |
| `ext-aider-py.yaml` | ext, calibration (outside, pinned) | aider-py | `evals.py aider-py` |

`baselines.json` holds, per set and version, the fingerprint of its cases (`cases`) and any baseline its gate reads
(`small` v1: `checks`). `run-bar.ps1` runs sets for their bar; `evals.py bar <set>` says whether a bar is met.

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

1. Start from a failure, not an idea: read the failing traces and the eval history, label each failure, count the
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
