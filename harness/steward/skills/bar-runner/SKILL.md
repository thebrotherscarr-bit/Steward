---
name: bar-runner
description: Start one of your eval sets in its own window with SecondBrain's eval_start, follow it with eval_status until it says BAR DONE, and report the result with the eval-history skill. Use when the user asks you to start, run or queue an eval set or a bar run (small, steps, heldout, aider-py, bfcl), asks how a running eval is going, or asks for the last eval result.
---

## Usage

**A saved eval flow first.** When the user names a saved flow ("run the bfcl eval flow", "Eval: bfcl"), or the set he
names is what one saved flow runs, that flow is the plan: find it with `secondbrain_saved_flows` and run it with
`secondbrain_saved_flow_run` by its `id` (planned, then its own card), and read it with `secondbrain_saved_flow_status`
(the `automations` skill, ADR-0016). Use `secondbrain_eval_start` below only for sets no saved flow holds, or a run he
asks for with its own sets, runs or tag.

Your eval sets run through `harness/steward/evals/run-bar.ps1`, each set as its own process in its own minimized
window, one after another (one model at a time). SecondBrain starts it for you; you never run it in your shell.

1. **Check first.** Call `secondbrain_estate_status`: if a Manjuel sitting is open or a chat model other than yours is
   loaded, say so before starting anything.
2. **Plan, then start.** Starting an eval is an action like any other (ADR-0009; the operator, 2026-11-05:
   "starting an eval should always come with a plan"). In plan mode put it on the plan as a todo (the set, the runs,
   the tag) and present the plan; do not call it. Once the operator approves, call `secondbrain_eval_start` with
   `sets` (set names from `harness/steward/evals/`: `small`, `steps`, `heldout`, `aider-py`, `bfcl`), `runs` (1 to 3;
   1 when left out) and, if the user gave one, `tag`. It asks its own card; a No ends it. It refuses an unknown set,
   a used tag, and any start while an eval is already running; report the refusal as it says and stop. Otherwise
   report the tag and the progress file it returns.
3. **Follow.** Call `secondbrain_eval_status` with the tag (no tag: the newest run). It returns the progress file's
   lines: one as each run starts and ends with its counts, then each set's bar, and `done` once it says "BAR DONE".
   Report the last line; do not call it again and again in one turn: a set takes minutes to hours.
4. **Report the result** once `done` is true: quote the "done" lines (cases and checks for each run) and the bar
   lines, then follow the `eval-history` skill to compare the run with the one before and name every flipped check.

Rules:
- Any set runs whenever the operator says, day or night (ADR-0009; the operator, 2026-11-05: "run it whenever i say.
  day or night or whenever, its my system. same as any eval."). There is no night-only rule and no daytime warning.
  A saved eval flow (the `automations` skill) starts its set with no card: the flow is his approved plan.
- One eval at a time. Never start a set to fill the history, and never run the same set again because a check
  flipped: a flip on the same commit is a fault in the harness to look into.
- Never stop an eval, kill a process or unload a model to make room; ask the operator.
