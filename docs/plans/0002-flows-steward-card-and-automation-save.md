# Let Steward build flows and automations from the Flows shelf, on the operator's card

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and
`Outcomes & Retrospective` must be kept up to date as work proceeds.

This document is maintained in accordance with `.agent/PLANS.md` at the repository root. It carries out the open
pieces of [ADR-0008](../decisions/0008-the-flows-shelf.md) (the Flows shelf: Steward's card and evals in flow) and
[ADR-0009](../decisions/0009-flows-are-ordered-tool-chains-automations-schedule-flows.md) (`automation_save`), and its
eval cases come from [spec 001](../specs/001-capability-evals.md) (D2, D3; cases P46 and P47) under
[ADR-0012](../decisions/0012-stewards-bar-is-our-own-capability-evals.md).

## Purpose / Big Picture

The operator builds flows (ordered chains of steps, such as "pull main, then list the merged pull requests") on the
Flows shelf of his console, Jesster (the SecondBrain app), and schedules them as automations (a saved flow, a time,
and on or off). Today he does all of it by hand: Steward can only describe a flow in words, because he has no tool to
save one, and the panel on the shelf's right where Steward should sit says "Steward will build and change flows from
here. Not yet."

After this plan, the operator opens the Flows shelf, folds out Steward's card on the right, and asks, for example,
"make me a flow that pulls main and tells me the merged pull requests every weekday at 06:30". Steward answers with a
plan; on approval he calls `automation_save`, which raises one card showing exactly the flow and automation that will be
written; when the operator approves, the flow appears on the shelf's list and canvas, and the automation in Set up.
A step not in the fixed list is refused by name before any card. And every flow run can carry a check, so the shelf
shows each flow as passing or failing ("evals are flows that check flows", ADR-0008).

## Progress

- [x] (2026-11-05) Pieces 1 to 3 of the shelf built: the canvas and + New flow (Jesster #79, #83, #86); flows and
  automations split per ADR-0009 (Steward #156, Jesster #88); the canvas drawn from Steward's MAF workflow and each
  flow's run history (Steward #158, Jesster #89).
- [x] (2026-11-05) This ExecPlan written.
- [ ] Milestone 1: `automation_save` served by Jesster as a carded Estate tool, through the same checks as the shelf.
- [ ] Milestone 2: Steward offered `automation_save` behind its card, with his `automations` skill and the capability
  cases P46 (and a new save case) in the eval sets.
- [ ] Milestone 3: Steward's card on the shelf: his chat folded out on the right, the same conversation path as the
  Agent tab.
- [ ] Milestone 4: evals in flow: a recipe run scored by MAF's `evaluate_workflow`, its result on the run line and
  the shelf (case P47).

## Surprises & Discoveries

- Observation: Jesster already serves three schedule tools to its own local agent, with no create.
  Evidence: `secondbrain/electron/agent/schedules.cjs`, `tools()`: `schedule_list`, `schedule_remove`,
  `schedule_set_enabled`, and the comment "No schedule_create: a prompt on a timer is not made any more (ADR-0009)".
  `automation_save` must not bring back a prompt type: it takes steps only.

## Decision Log

- Decision: a saved flow runs with no card; making or changing one is a card.
  Rationale: ADR-0009: "the saved flow is the operator's approved plan"; in chat "everything that changes something is
  planned and carded". `automation_save` changes what will run unattended, so it is a write on his card.
  Date/Author: 2026-11-05, Kyle (ADR-0009).
- Decision: `automation_save` is served by Jesster (which keeps `schedules.json` and the clock) and listed among the
  Estate's tools Steward is offered, not written by Steward to the file.
  Rationale: ADR-0004 (Jesster is the center and keeps the automations' clock) and the guidance's "How Steward gets a
  new control": Jesster serves it as an MCP tool, Steward lists it with an approval mode, a skill says when, tests on
  both sides go red when it is unplugged.
  Date/Author: 2026-11-05, in the plan.

## Outcomes & Retrospective

Nothing to report yet.

## Context and Orientation

Two repositories are involved. Steward (`worlds/steward`, this repository) is the agent; Jesster (`worlds/jesster`,
the folder `secondbrain/` is the SecondBrain desktop app, Electron and React) is his console and the Estate's center.

A **flow** is data: `{name, steps: [...], summarize?, deliver: [note, telegram]}`, where each step's name is from the
fixed list `repo_log, merged_prs, releases, eval_bars, plan_left, versions, pull_ff, eval_start, eval_wait`
(`secondbrain/electron/agent/workflows.cjs`, `STEPS`, checked by `validateSteps`, which refuses an unknown step by
name). An **automation** is the same record with a `when` (plain text parsed by `parseWhen` in
`secondbrain/electron/agent/schedules.cjs`: `daily 08:30`, `weekdays 08:30`, `weekly mon 09:00`, `every 3h`,
`once 2026-10-23 09:00`; empty means Run now only) and `enabled`. Both live in `<vault>/.secondbrain/schedules.json`;
`Schedules.addFlow` and `Schedules.edit` are the only ways in, and refuse a flow with no steps.

When a flow runs, Jesster hands it to Steward's MCP host (`harness/steward/step04_production_ready/mcp_app.py`, port
43121, tool `run_recipe`), which builds it as a MAF workflow in `recipe_workflow.py` (one executor per step, then a
tool-less summary, then delivery) and records its events in `storage/recipes/<run_id>.jsonl`. No step raises a card.

Steward reaches Jesster's tools over MCP on 43110. The Estate's tools are declared in Jesster's
`secondbrain/electron/estate.cjs` (`ESTATE_TOOLS`) and filtered per caller in `secondbrain/electron/atlas.cjs`. On
Steward's side, `agent.py` lists them in `ESTATE_READS` (never a card), `ESTATE_ASKS` (always a card:
`service_control`, `ollama_unload`, `app_update`) and `ESTATE_ACTIONS` (`eval_start`), and `estate_approval` turns
those lists into MAF's per-tool `approval_mode`; any name not listed asks a card by default.

The Flows shelf is `secondbrain/src/components/FlowsShelf.tsx`; its right panel is `StewardCard`, a placeholder. The
Agent tab's chat is `secondbrain/src/components/AgentView.tsx`, and its turns go to Steward over AG-UI
(`secondbrain/electron/agent/agui.cjs`, port 43122).

## Plan of Work

Milestone 1 (Jesster). In `estate.cjs`, add `automation_save` to `ESTATE_TOOLS` with an input schema
`{name, steps, summarize?, deliver?, when?, enabled?, id?}` and no `prompt` property; its handler calls
`Schedules.addFlow` (no `id`) or `Schedules.edit` (with `id`), so every check the shelf uses (`validateSteps`,
`parseWhen`) runs before anything is written, and returns the saved record. Mark it a write, so the door and the
Approvals shelf park it as the operator's card with the record shown. Tests in `estate.test.cjs` or
`schedules.test.cjs`: a bad step is refused by name and nothing is written; a `prompt` with no steps is refused; a
good save writes one record; the tool is listed as a write.

Milestone 2 (Steward). In `agent.py`, add `"automation_save"` to `ESTATE_ASKS`, so it is offered behind a card and
never to an eval's build (stand-ins only there). In `harness/steward/skills/automations/SKILL.md`, replace "until you
have a save tool, propose it in words" with when and how to call it (plan first; steps only from the list; one save per
request). Gate tests in `test_harness.py`: `automation_save` always asks a card and is not in an eval build. Eval
cases (spec 001, D2): P46 updated so its check is a plan naming `automation_save` with steps only from the list, its
card denied; and a new case for a save whose step is not in the list, refused in words. Update spec 001's D2 row and the
Charter's flows line (the Charter changes only on the operator's word).

Milestone 3 (Jesster). Replace `StewardCard`'s placeholder with the Agent tab's chat component, on its own conversation,
so the same AG-UI path, cards and console lines are used; nothing new on Steward's side. A test in
`flowGraph.test.tsx` that the card renders the chat and sends to the same service.

Milestone 4 (both). Add an optional `check` to a flow. On Steward's side, after a recipe run ends, call MAF's
`evaluate_workflow` with `LocalEvaluator` over the run (each executor completed, no card, the state file written, plus
the flow's own check), and write the result on the run's state (`storage/recipes/<run_id>.json`) and in
`recipe_runs`. On Jesster's side, the shelf's list marks each flow passing or failing from its last run. Case P47.

## Concrete Steps

Steward, from `worlds/steward`, with `.venv\Scripts\python`:

    timeout 300 python -m compileall -q .
    timeout 300 python -W ignore harness/steward/step04_production_ready/evals.py validate
    timeout 900 python -m pytest -q -p no:cacheprovider harness/steward/step04_production_ready/test_harness.py

Jesster, from `worlds/jesster/secondbrain`, with the time limits its `AGENTS.md` gives (its unit tests under
`electron/` and `src/`). Each repository's change is its own pull request; Jesster's lands first in Milestone 1, then
Steward's in Milestone 2. Restart required after each: SecondBrain's next build for Jesster, Steward's servers for
Steward.

## Validation and Acceptance

After Milestones 1 and 2, in the Agent tab: "Make me a flow called Morning PRs that runs pull_ff then merged_prs,
weekdays 06:30." Steward plans; on approval, one `automation_save` card shows the record; on Approve, Morning PRs is on
the Flows shelf's list with two blocks, and Set up shows it weekdays 06:30, on. The same request with a step called
`deploy` is refused by name with no card. After Milestone 3, the same from the shelf's right panel. After Milestone 4,
Run now on Morning PRs shows a passing mark on the list, and a flow whose check fails shows failing.

## Idempotence and Recovery

`automation_save` with an `id` edits the same record; without one it adds a new record, so repeating a save makes a
second flow: Steward's skill tells him to read `schedule_list` first. A wrong flow is removed on the shelf (Set up's
delete) or turned off; nothing here deletes a flow by itself.

## Artifacts and Notes

None yet.

## Interfaces and Dependencies

MAF as it ships: per-tool `approval_mode` on `MCPStreamableHTTPTool` (`estate_approval`), `WorkflowBuilder`, and
`evaluate_workflow` with `LocalEvaluator` for Milestone 4. Jesster's `Schedules.addFlow`, `Schedules.edit`,
`workflows.validateSteps` and `parseWhen` are reused, never copied.

---

Revision note, 2026-11-05: first version, from ADR-0008, ADR-0009 and the code at Steward #163 and Jesster #92.
