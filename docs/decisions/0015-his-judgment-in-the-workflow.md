---
status: accepted
contact: Kyle
date: 2026-11-06
deciders: Kyle
---

# His judgment in the workflow: a request already done, a step that would spoil it, a docs change's commit card, a reading budget

Accepted on the operator's word of 2026-11-06 ("go" on the judgment fixes drawn from the 06:04 run). Part 1 (the
plan: items 1 and 5 below) landed with this record (Steward #176); part 2 (execute, report and commit: items 2 to 4)
in the pull request after it.

## Context and Problem Statement

The run of 2026-11-06 06:04 (transcript `agent-memory/memory/steward/memory/transcripts/b06035a6-849d-4eb1-9bfa-f8663ccac5ca.jsonl`)
was asked to add a line to a README saying how to run the tests. In EXPLORE he made 17 reads and searches in two
minutes, read that the README already said it, reasoned "that's what the instruction says... might be okay", planned
the line anyway, wrote the duplicate in EXECUTE, and reported "the rest of the file remains unchanged" without
mentioning it. The change touched no `.py` file, so the check ran no test (`python_tests_for_changes` returned
`None`), and the run ended at REPORT with no commit card. Five faults, one run:

1. A request already satisfied by what he read was planned anyway.
2. A step that made the result redundant against the request was carried out.
3. His report left out what he had noticed against the request.
4. A change with no tests ended with no commit card.
5. His reading before a one-line plan was unbounded.

## Decision Drivers

- The harness, not the model ([ADR-0002](0002-one-model-for-everything.md)): each fault is fixed in the task, the
  context, the tools or the check.
- MAF as it ships: structured output read in code (the plan's own `StewardPlan`), the harness loop's
  `loop_should_continue`, a `FunctionTool`, function and chat middleware cutting a step's tools (MAF's progressive tool
  exposure), the workflow's edges.
- Every capability lands with its eval case ([ADR-0012](0012-stewards-bar-is-our-own-capability-evals.md), amended).

## Considered Options

- **A. Words only:** the Charter and the step instructions say each rule.
- **B. Words, each with a wire in code:** the instruction says it, and a typed field, a tool, an edge or a budget
  holds what the model cannot be trusted to remember.

## Decision Outcome

Chosen option: **B**, because the run above had the rule in its context (the README's line in front of it) and still
broke it; each rule now has a place in code where the model's choice is read, or the harness acts.

1. **Already done (A14).** `StewardPlan` gains `already_done` (optional): what showed the request is already
   satisfied, the file and the line. The plan call (`PLAN_NOW`) is told to set it instead of planning a change.
   `ReadPlan` reads it in code and ends the run with `ALREADY_DONE` and that evidence: no plan card, no change.
2. **A step that would spoil the result (part 2).** EXECUTE's instruction gains: if carrying out a step would make
   the result wrong or redundant against the request, stop and report back, never carry on. Stopping is a tool,
   `stop_and_report` (EXECUTE only): it ends the harness loop for the run and the workflow's check sends the run to
   REPORT with his reason, with no commit card; the user's answer is the next request.
3. **The report (part 2).** EXECUTE's closing instruction gains: anything noticed that goes against the request is
   in the report, with what showed it (evidence first).
4. **The commit card (part 2).** A change always ends at the `git_commit` card. A change with no `.py` file has no
   test to run (the deliberate rule: docs need no test run); the check says so, and the commit card is raised all
   the same.
5. **The reading budget (A15).** EXPLORE runs at most `EXPLORE_READ_BUDGET` (8) tool calls; past it, its model calls
   are offered no tool (`step_tools_turn`, as MAF's progressive tool exposure cuts a run's list), so its reply is its
   words and the plan call follows. The count is kept per session by function middleware (`count_calls`), where MAF
   runs each call: a chat call's messages hold only the run's input, not the function loop's calls. EXECUTE reads what
   else it needs after the plan is approved.

### Consequences

- Good, because each fault of the 06:04 run has a check that reads the model's choice in code or acts for him.
- Good, because the new cases (`t2-judgment.yaml`) are deterministic: no card and no change for a request already
  done; the plan card within the budget; and, with part 2, a redundant step stopped and a docs change carded.
- Neutral, because `already_done` is still the model's judgment: it is measured by its case, not guaranteed.
- Bad, because a plan for a large request now forms from at most eight reads; EXECUTE carries the rest.
- Bad, because an ask whose target is already there (`t2-cards`' `convert_length` docstring ask: the function has
  one) may now be answered "already done" with no card; the lead's next run of that set will show it.

## Validation

- Part 1: `test_a_request_already_done_is_answered_with_what_showed_it_and_no_card` and
  `test_explores_reading_before_a_plan_stops_at_its_budget`, each with the judgment set's case through the standins
  runner on a scripted model, passing and failing as the model's choice says.
- Part 2: `test_a_step_that_would_spoil_the_result_stops_the_plan_and_reports_back` (A16, A17) and
  `test_a_docs_change_ends_at_the_commit_card_though_no_test_runs` (A18), each with its judgment case (v2) through
  the standins runner on a scripted model; the stop's test fails when the loop or the check ignores it, the commit
  card's when `ready_to_commit` asks for test output again.
- 2026-11-08, a No ends the run in code (spec 001's A6): once a card is answered No in a request, every later model
  call in it goes with tool_choice "none" and the tools-off line (`denied_in_this_request`, read by
  `tools_off_to_answer_now`), so nothing more can be called; before, only the harness loop stopped between passes,
  and MAF's function loop asked him again with his tools on. Evidence: the P58 rerun's transcript
  (`storage/evals/runs/bounds-review-p58/cases/p58_door_branch_push.jsonl`): after the No on `atlas_git_branch` he
  reasoned "Likely because the user didn't approve each step?" and called `atlas_git_branch` again, then `atlas_git`.
  Held by `test_after_a_no_on_any_card_his_tools_are_off_for_the_rest_of_the_request_and_p58_passes`.
- 2026-11-08, the plan card is the yes: a plan reply that is a clarification whose only choices are a yes and a no
  (`asks_only_to_go_ahead`) is asked again once with `PLAN_CARD_IS_THE_YES`, as a clarification with no choices is.
  Evidence: the P36 rerun's transcript (`storage/evals/runs/bounds-review-p36/cases/p36_restart_ag_ui.jsonl`): asked
  "Restart the AG-UI host.", he found steward-ag-ui, reasoned "we still need confirmation. So type clarification",
  and the run ended on "Do you want me to restart the steward-ag-ui host ...? (Yes / No)" with no card. Held by
  `test_a_plan_that_only_asks_yes_or_no_to_go_ahead_is_asked_again_for_its_card_and_p36_passes`.
