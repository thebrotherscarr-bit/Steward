---
name: improve
description: Fix one failure in your own harness during an improvement round - find the failing check, find the cause, make the smallest change, prove it with a test - so the eval gate can keep it. Use when the task says it is an improvement round, or names an eval failure to fix.
---

## Usage

An improvement round (step 6 of the plan) fixes one failure seen in your evals. You are the fixer: your own harness,
on the coder model. After you stop, the gate runs your harness tests and then the small-ask evals; the change is
kept only if the tests pass and the eval checks do not drop below the baseline, and the user decides keep or drop.

1. **Name the failure.** The task names it (for example "the plan comes back as prose"). Find the check that
   catches it in `harness/steward/step04_production_ready/evals.py` (the small-ask checks: `plan_is_approval`,
   `check_covers_writes`, `edit_keeps_file_whole`, `commit_by_tool`, `commit_message_specific`,
   `no_nudge_in_reply`, `answer_on_topic`) and read what it requires. When the task is the diagnosis's first top
   priority (the handoff follows it in full), that priority is the one change; its evidence in the handoff names
   the failure, and your test in step 4 is what proves it.
2. **Find the cause in the harness, not the model.** Look where the behaviour is shaped:
   `steward_workflow.py` (the graph: `ReadPlan`, `AskCommit`, `Report`, the messages each step sends),
   `agent.py` (instructions, `REQUEST_HINTS`, the loop's nudges, tools and approvals) and `skills/`. Read the
   code before changing it.
3. **Make the smallest change that removes the cause.** Prefer a deterministic fix (the workflow checking or
   correcting something in code) over more words in an instruction. Keep the file's style, and keep its line
   endings exactly as they are.
4. **Prove it.** Add or adjust a test in `harness/steward/step04_production_ready/test_harness.py` that fails
   without your change and passes with it. Run that test once with run_shell:
   `python -m pytest -q -p no:cacheprovider harness/steward/step04_production_ready/test_harness.py -k <name>`.
5. **Stop and report:** the failure, the cause you found (file and line), the change, and the test. Do not
   commit: the review decides.

Never:
- change an eval's check, or `eval_baselines.json`, to make the gate pass;
- change more than the one failure asks for;
- touch `.env`, or anything outside your workspace.
