---
name: evals
description: Run your own evals, the checks that measure how you work, and report their results exactly. Use when the user asks you to run your evals, an eval set (small asks, regression, steps, memory), the diagnosis, or to check your progress.
---

## Usage

Your evals live in `harness/steward/step04_production_ready/evals.py`. Each set runs real requests through you
on the local model and scores them with MAF's `LocalEvaluator` checks. The sets:

| Set | What it checks |
|---|---|
| `small` | Step 4: the failures seen live on 2026-11-02, as three small asks (a new function, the discount fix, a README line) run through your workflow, scored by seven checks |
| (none) | The regression set: repo status, the codebase map, the bug diagnosis, and the improvement loop's four cases |
| `steps` | One run of your workflow on the planted bug, each step (plan, execute, overall) scored by its own check |
| `memory` | Step 5: a fact you are asked to remember in one request is recalled in the next, a new conversation (a throwaway memory, never your own) |

When the user asks you to run your evals:

1. Pick the set the user named. If none is named, ask which set, and list the sets above.
2. Run it once with the run_shell tool, from the workspace root:
   `.venv/Scripts/python.exe -W ignore harness/steward/step04_production_ready/evals.py <set>`
   (leave `<set>` out for the regression set). It takes several minutes; wait for it to finish.
3. Report the pass count line and every line printed under each case, exactly as printed. Do not summarise
   the failures away or explain them before you have reported them. The run exits with code 1 when any case
   failed and 0 when all passed; an exit code of 1 is the result, not a broken run.
4. Run a set once per request. As soon as the run has finished, mark its todo complete, then report. If you are
   reminded of an open todo whose run has already finished, mark it complete; never run the set again for it.
   Never run it again to get a better result either: a result that changes between runs is a fault in the
   harness to look into, not a reason to retry.
5. Do not change any file during or after the run. The evals plant and remove their own test bug, answer their
   own cards, and put the sample project back when they finish. If a card from SecondBrain's door appears
   during the run (a commit through the door), tell the user to deny it.

## The diagnosis

When the user asks you to run your diagnosis (the cookbook's improvement loop, first half): run it once with
run_shell, from the workspace root:
`.venv/Scripts/python.exe -W ignore harness/steward/step04_production_ready/improvement_loop.py`
It traces your workflow on the small asks and a plain question, generates evals, scores them with Promptfoo and
ranks harness changes with HALO. It takes 20 to 40 minutes; wait for it. Then report the Promptfoo line
(`Promptfoo gate completed ...: N/M passed`) and the three priorities under `## Top 3 changes to implement first`
in `improvement_loop/latest/handoff.md`, exactly as written. The same rules apply: once, no changes, no reruns.
