---
name: improve
description: Fix one failure in your own harness during an improvement round - find the failing check, find the cause, hand the smallest change and its test to the coder - so the eval gate can keep it. Use when the task says it is an improvement round, or names an eval failure to fix.
---

## Usage

An improvement round (step 6 of the plan) fixes one failure seen in your evals. You diagnose, on your own model; the
coder (a small agent on your own model) makes the edits you hand it with `hand_to_coder`, and sees only the lines
you name and your words. After the coder, the gate runs your harness tests and then the small-ask evals; the change
is kept only if the tests pass and the eval checks do not drop below the baseline, and the user decides keep or drop.

1. **Name the failure.** The task names it (for example "the plan comes back as prose"). Find the check that
   catches it in `harness/steward/step04_production_ready/evals.py` (the small-ask checks: `plan_is_approval`,
   `check_covers_writes`, `edit_keeps_file_whole`, `commit_by_tool`, `commit_message_specific`,
   `no_nudge_in_reply`, `answer_on_topic`) and read what it requires. When the task is the diagnosis's first top
   priority (the handoff follows it in full), that priority is the one change; its evidence in the handoff names
   the failure, and the test in step 4 is what proves it.
2. **Find the cause in the harness, not the model.** Look where the behaviour is shaped:
   `steward_workflow.py` (the graph: `ReadPlan`, `AskCommit`, `Report`, the messages each step sends),
   `agent.py` (instructions, `REQUEST_HINTS`, the loop's nudges, tools and approvals) and `skills/`. Read the
   code first, with `file_access_read_lines`, so you know the exact line numbers.
3. **Hand the smallest change to the coder.** Call `hand_to_coder` with the file, the first and last line to
   change (at most 80 lines) and the change in plain words: what those lines must say or do afterwards. Prefer a
   deterministic fix (the workflow checking or correcting something in code) over more words in an instruction.
   Do not edit files yourself.
4. **Hand the test too.** A second `hand_to_coder` for `harness/steward/step04_production_ready/test_harness.py`:
   a test that fails without the change and passes with it. To add a test, name the file's last line and say
   "add after it". The gate's checks run the tests after the coder.
5. **Stop and report:** the failure, the cause you found (file and line), and the edits you handed over. Do not
   commit: the review decides. If the checks fail, you get their output: find the cause and hand the fix over
   again.

Never:
- change an eval's check, or anything in `harness/steward/evals/` (the eval sets and their baselines), to make the gate pass;
- change more than the one failure asks for;
- touch `.env`, or anything outside your workspace.
