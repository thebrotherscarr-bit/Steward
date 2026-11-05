---
status: accepted; superseded in part by [ADR-0009](0009-flows-are-ordered-tool-chains-automations-schedule-flows.md)
contact: Kyle
date: 2026-11-05
deciders: Kyle
---

# Automations are recipes run as MAF workflows

> 2026-11-05: superseded in part by [ADR-0009](0009-flows-are-ordered-tool-chains-automations-schedule-flows.md):
> a flow (the steps) is saved by itself and an automation is `{flow, when, on/off}`; there is no open-ended prompt
> type.

## Context and Problem Statement

The operator's "Startup" automation (weekdays 06:00: "Review work from the previous day on Github and bring all repos
current. Review the plan for the build and summarize what is left.") was an open-ended chat turn on a timer. As
reported (not verified: the run notes are in SecondBrain's settings, which a hand does not read), it never produced a
summary: "stopped after 12 steps" from Oct 27 to Nov 3, and on Nov 4 at 06:00 "May I proceed?" for a git card nobody
was there to answer. How should scheduled work run when nobody is watching?

## Decision Drivers

- The operator, 2026-11-05: "we can build workflows for the evals, and then keep him as the general purpose agent for
  personal use during the day."
- The operator, 2026-11-05: "since i already did it, you can just tune the automation and use it as a baseline so
  that steward can eventualy build his own per my request and authorization."
- The operator, 2026-11-05: "write it up as a skill.md, same as all the other skills he does."
- An automation never approves its own card; an unanswered card is a No.
- Use MAF as it ships: workflows, checkpoints, step events and `evaluate_workflow` come from MAF. MAF has no
  scheduler.

## Considered Options

- Recipes as data, run as MAF workflows on Steward's host; Jesster keeps only the clock.
- Recipes as data, run by Jesster's own JavaScript step runners (Jesster #72, the first build).
- Open-ended Steward turns on a timer (as before).

## Decision Outcome

Chosen option: "Recipes as data, run as MAF workflows on Steward's host", because it puts every run on MAF's
workflow machinery (checkpoints, step events for the Flows shelf, `evaluate_workflow`) and leaves Jesster only what
MAF lacks, the scheduler. _(2026-11-05: recipe runs are not evaluated yet; `evaluate_workflow` on them is the Flows
shelf's piece 5.)_

- **A recipe is data:** `{ name, when, prompt, steps: [...from a fixed list...], summarize?, deliver: [note, telegram] }`,
  kept in SecondBrain's `schedules.json`. The steps are fixed: repo_log, merged_prs, releases, eval_bars, plan_left,
  versions, pull_ff, eval_start and eval_wait. A step outside the list is refused by name.
- **Steward runs it** (Steward #150, Jesster #78): `recipe_workflow.py` builds each recipe with `WorkflowBuilder`,
  one executor per step, then summarize (a tool-less agent run in its own session), then deliver. Runs are
  checkpointed with `FileCheckpointStorage`; their events go to `storage/recipes/<run_id>.jsonl`. They are served on
  his MCP host (43121) as `run_recipe` and `recipe_status`.
- **Jesster keeps the clock** (`schedules.cjs`: `parseWhen`, the "skip if Steward is busy" rule) and files the result
  note and the Telegram line.
- **Startup is the baseline,** tuned in place (his name, time and prompt kept; the gathering steps, a summarize prompt,
  and delivery to a note and Telegram added).
- **Steward builds his own later,** on the operator's request and card: `automation_save` (not built yet) will write
  exactly this shape through the same step check. Until then he proposes a recipe in words. His `automations` skill
  is the reference.

### Consequences

- Good, because a 06:00 run gathers facts with fixed reads and makes one summary turn; it cannot stall on a card.
- Good, because every run has a checkpoint and a step-by-step event log, which the Flows shelf and the evals read.
- Bad, because a recipe can only use the fixed steps; a new kind of step is a code change in Steward's repo.
- Neutral: Jesster's JS step runners from #72 are gone; `workflows.cjs` only checks recipes and hands them over.

## Validation

`validateSteps` refuses an unknown step by name (Jesster). Steward's tests cover `recipe_workflow.py`'s graph and its
checkpointed run.

## More Information

- Nightly evals are recipes too ([ADR-0006](0006-evals-are-versioned-long-runs-at-night.md)).
- The SecondBrain note `steward-s-dev-path-evals-that-grow-with--cb3211`, "automations are workflows" and "Course
  correction"; the Flows shelf plan's decision 4 ([ADR-0008](0008-the-flows-shelf.md)).
