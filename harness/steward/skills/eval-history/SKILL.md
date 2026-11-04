---
name: eval-history
description: Read the history of your eval runs and compare the last runs of a set - counts, the commit and model each ran on, and which checks flipped between the last two. Use when the user asks how the evals went, whether a set got better or worse, what changed since the last run, or which checks flipped.
---

## Usage

Every eval set run appends one line to `storage/evals/history.jsonl` in your repo. This skill only reads it.

1. Run `scripts/eval_history.py` with the set's name, e.g. `["small"]` (sets: `small`, `steps`, `memory`,
   `regression`). With no arguments it takes the set of the newest run. Add `"--runs", "5"` to list more runs.
2. It prints JSON: `runs` (oldest first: time, passed/total cases, checks passed/total, `git_head`, model and the
   failed checks as "case / check") and `flipped` (each check that changed between the last two runs, with `now`:
   `fail` or `pass`).
3. Report the last two runs' counts and commits, then every flipped check exactly as printed: the case, the check,
   and whether it now passes or fails. If nothing flipped, say so.

Rules:
- Read only. Never run a set to fill the history, and never change the history file.
- A check that flips between two runs on the same commit is a fault in the harness to look into, not a reason to run
  the set again.
