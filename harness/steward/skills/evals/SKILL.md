---
name: evals
description: Run your own evals, the checks that measure how you work, and report their results exactly. Use when the user asks you to run your evals, an eval set (small asks, regression, steps), or to check your progress.
---

## Usage

Your evals live in `harness/steward/step04_production_ready/evals.py`. Each set runs real requests through you
on the local model and scores them with MAF's `LocalEvaluator` checks. The sets:

| Set | What it checks |
|---|---|
| `small` | Step 4: the failures seen live on 2026-11-02, as three small asks (a docstring, the discount fix, a README line) run through your workflow, scored by seven checks |
| (none) | The regression set: repo status, the codebase map, the bug diagnosis, and the improvement loop's four cases |
| `steps` | One run of your workflow on the planted bug, each step (plan, execute, overall) scored by its own check |
| `plan`, `roundtrip`, `walkthrough` | The older single-agent sets, from before the workflow |

When the user asks you to run your evals:

1. Pick the set the user named. If none is named, ask which set, and list the sets above.
2. Run it once with the run_shell tool, from the workspace root:
   `.venv/Scripts/python.exe -W ignore harness/steward/step04_production_ready/evals.py <set>`
   (leave `<set>` out for the regression set). It takes several minutes; wait for it to finish.
3. Report the pass count line and every line printed under each case, exactly as printed. Do not summarise
   the failures away or explain them before you have reported them.
4. Run a set once per request. Never run it again to get a better result: a result that changes between runs
   is a fault in the harness to look into, not a reason to retry.
5. Do not change any file during or after the run. The evals plant and remove their own test bug, answer their
   own cards, and put the sample project back when they finish. If a card from SecondBrain's door appears
   during the run (a commit through the door), tell the user to deny it.
