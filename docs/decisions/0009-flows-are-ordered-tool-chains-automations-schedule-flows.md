---
status: accepted
contact: Kyle
date: 2026-11-05
deciders: Kyle
---

# Flows are ordered tool chains; automations schedule flows

## Context and Problem Statement

After [ADR-0005](0005-automations-are-recipes-run-as-maf-workflows.md) and [ADR-0008](0008-the-flows-shelf.md), one
record in SecondBrain's `schedules.json` was at once a flow (its steps) and an automation (its clock), and Set up
could still make a "Steward prompt" automation: an open-ended turn on a timer, the shape ADR-0005 replaced. Evals
carried a night-only rule ([ADR-0006](0006-evals-are-versioned-long-runs-at-night.md)): long sets were badged
"night", Run now by day asked "This takes hours; run now anyway?", and the `bar-runner` skill refused long sets by
day. And in chat, `eval_start` ran with no card, as a "bounded Estate action". What is a flow, what is an automation,
when may an eval run, and what does Steward ask before he starts one?

## Decision Drivers

- The operator, 2026-11-05: "open ended prompt, nah. a flow thats gonna just work that doesnt need gates, yea."
- The operator, 2026-11-05: "starting an eval should always come with a plan, that doesnt make sense" (on
  `eval_start` running without a card). The lead's reading, recorded as such: asked in chat, Steward plans first and
  the operator approves (`eval_start` goes back behind the plan and its card); inside a flow, the flow the operator
  built, saved and scheduled is the approved plan, so it runs without asking again. The safe pull (`pull_ff`:
  `git pull --ff-only` on main only, with a clean work tree, never during a sitting) is the flow step behind Startup's
  "bring all repos current".
- The operator, 2026-11-05: "run it whenever i say. day or night or whenever, its my system. same as any eval."
- The operator, 2026-11-05: "a flow is like a list of the tools in order or whatever like a skill or series of
  skills, right? so thats like, needing to be usable so set up the flows and then the automations are like where i
  set up my different nightly jobs if i want or like a daily digest or a deep web dive over night, or a series of
  tasks to another agent, whatever i want."
- MAF's overview, "When to use agents vs workflows" (learn.microsoft.com/agent-framework/overview): use an agent when
  "The task is open-ended or conversational" and "You need autonomous tool use and planning"; use a workflow when
  "The process has well-defined steps" and "You need explicit control over execution order". And: "If you can write
  a function to handle the task, do that instead of using an AI agent."
- OpenAI, "A practical guide to building agents" (the PDF on openai.com): "Before committing to building an agent,
  validate that your use case can meet these criteria clearly. Otherwise, a deterministic solution may suffice."
  And, under "Plan for human intervention": "High-risk actions: Actions that are sensitive, irreversible, or have
  high stakes should trigger human oversight until confidence in the agent's reliability grows."
- OpenAI Cookbook, "Orchestrating Agents: Routines and Handoffs" (`examples/Orchestrating_agents.ipynb`): "let's
  define a routine to be a list of instructions in natural language (which we'll represent with a system prompt),
  along with the tools necessary to complete them." A flow is that idea made fixed: the steps and their tools, in
  order, with no model choosing the order.

## Considered Options

- Flows are ordered tool chains saved on their own; an automation is a saved flow plus when and on/off; no prompt
  type; evals run whenever the operator says; `eval_start` in chat is planned and carded.
- Keep the "Steward prompt" automation type beside recipes, and the night-only rule for long evals (as before).
- Gates inside flows: each flow step that changes something raises a card when it runs.

## Decision Outcome

Chosen option: "Flows are ordered tool chains; automations schedule flows", because it is the operator's
2026-11-05 call, and it is MAF's split as MAF states it: open-ended work is an agent's (Steward in chat, behind his
plan and cards), well-defined steps in an explicit order are a workflow's (a flow, run unattended).

- **A flow** is an ordered chain of steps, built on the Flows shelf's canvas ("+ New flow", the only way to make
  one) and saved by itself, with no clock. Its steps come from the fixed list in `recipe_workflow.py` (ADR-0005);
  it runs as a MAF workflow on Steward's host. **No gates when it runs:** the saved flow is the operator's approved
  plan, so no step in it raises a card. A step that could do harm is made safe in its own code instead (`pull_ff`:
  main only, a clean tree, never during a sitting; `eval_start`: eval sets only, one at a time).
- **An automation** is `{flow, when, on/off}` and nothing else: a saved flow, a time in plain choices, and whether
  it is on. Set up (the Flows shelf) lists the automations and makes, changes, turns on or off and deletes them; it
  does not build flows. Run now runs a flow at once, the way its automation would.
- **No open-ended prompt type.** The "Steward prompt" automation type is removed. Prompt-only schedules already
  saved keep running unchanged and are shown as "legacy: convert to a flow"; nothing is deleted.
- **Evals run whenever the operator says,** day or night, from a flow, an automation or a request in chat, like any
  other run. There is no night-only rule, no night badge and no daytime warning. One eval at a time and one model at
  a time still hold ([ADR-0002](0002-one-model-for-everything.md)).
- **In chat, `eval_start` is planned and carded like any action:** it is in plan mode's list of what changes things
  (so in plan mode it goes on the plan, not run), and after the operator approves the plan it raises its own card.
  Inside a flow it runs with no card (`recipe_workflow.py` calls SecondBrain's `eval_start` on its own client).

This supersedes in part:

- [ADR-0005](0005-automations-are-recipes-run-as-maf-workflows.md): a recipe's `prompt` and its clock no longer
  live on one record; a flow is the steps, an automation is the flow plus when and on/off.
- [ADR-0006](0006-evals-are-versioned-long-runs-at-night.md): "Long runs at night ... By day, Steward is the
  operator's" is replaced by "evals run whenever the operator says".
- [ADR-0008](0008-the-flows-shelf.md): Set up "create, edit, turn on or off, delete" of automations no longer builds
  flows; "+ New flow" is the only way to make a flow.

### Consequences

- Good, because a flow is the same every time it runs, so it can run while nobody watches and its runs compare.
- Good, because chat and flows each have one clear rule: in chat everything that changes something is planned and
  carded; in a flow the operator's saved flow is the approval.
- Good, because the operator runs his evals when he chooses, as the system is his.
- Bad, because a flow cannot do open-ended work (a free prompt to Steward); that is a request in chat, or a new kind
  of step added by pull request.
- Bad, because a step that could do harm must be made safe in its own code, as no card stands behind it.
- Neutral: legacy prompt-only schedules keep running until the operator converts or deletes them.

## Validation

Steward's `test_harness.py`: `eval_start` asks a card in chat and is refused in plan mode, and a recipe's
`eval_start` step runs with no card (red if either moves). Jesster's tests: no prompt automation type, an automation
is a flow plus when, one create button for flows, no daytime prompt on an eval flow.

## More Information

- MAF's own pause, if a flow ever needs one: MAF's "Human-in-the-loop (HITL)" page for workflows says "HITL is
  achieved through the request and response handling mechanism in workflows, which allows executors to send requests
  to external systems (such as human operators) and wait for their responses before proceeding with the workflow
  execution" (Python: `ctx.request_info()`). A gate inside a flow would be such a step, placed by the operator in his
  flow, not a card raised around it. None is built.
- The build: Steward's pull request with this ADR (the `eval_start` card, the `bar-runner`, `automations` and
  `estate` skills); Jesster's pull request after it (Set up as automations, the prompt type removed, the night badge
  and daytime question removed).
- Built (2026-11-05): all of the above. Each run now keeps the flow it ran and whether Run now or its automation
  started it (`run_recipe`'s `flow` and `trigger`), for the Flows shelf's run history ([ADR-0008](0008-the-flows-shelf.md)).
- Open: `automation_save`.
