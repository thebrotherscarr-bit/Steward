# A2UI pilot: draw Steward's plan card from an A2UI surface he sends

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and
`Outcomes & Retrospective` must be kept up to date as work proceeds.

This document is maintained in accordance with `.agent/PLANS.md` at the repository root. It carries out
[ADR-0013](../decisions/0013-a2ui-pilot-plan-card.md) (the A2UI pilot for the plan's approval card), which is
Milestone 4 of [ExecPlan 0003](0003-ag-ui-step-3.md) and the last "Next" item of
[ADR-0003](../decisions/0003-ag-ui-is-the-default-transport.md). Its eval and test duties follow
[ADR-0012](../decisions/0012-stewards-bar-is-our-own-capability-evals.md).

## Purpose / Big Picture

When the operator asks Steward to change something, Steward first proposes a plan and waits on a card: Approve runs
it, Deny ends it. Today Jesster draws that card from its own code, showing the tool name `approve_plan` and its
arguments as JSON. After this plan, Steward sends, beside the card, a description of the card as data in A2UI (an
open protocol in which an agent describes a small interface as components, and the client draws them with its own
components): a heading, the plan in words, one line per step, and two buttons. The Agent tab draws the card from that
description; pressing its Approve or Deny answers the card exactly as the old buttons do. If the description is
missing (an older Steward host, the Responses fallback) or cannot be drawn, the old card appears, so nothing can
block a turn. To see it working: ask in the Agent tab "Add a docstring to convert_length in
harness/steward/working/sample-project-2/units.py." and the plan card shows the plan's steps as lines with Approve
and Deny buttons, not JSON.

## Progress

- [x] (2026-11-05 20:40) Researched what ships (A2UI v0.9, `@a2ui/react` and `@a2ui/web_core` 0.15.0, MAF 1.7.1's
  `_a2ui`, MAF's custom workflow events over AG-UI) and wrote ADR-0013 and this plan.
- [ ] Milestone 1 (Steward): the plan card's surface, sent as a custom workflow event; capability A13 with its eval
  case; gate tests.
- [ ] Milestone 2 (Jesster): the AG-UI client hands the surface to the card; the card's answer path unchanged.
- [ ] Milestone 3 (Jesster): the Agent tab and the Phone view draw the card from the surface with the A2UI renderer and
  the app's own components; today's card when there is no surface or it cannot be drawn.
- [ ] The live acceptance below, on the operator's builds (Steward's AG-UI host restarted, SecondBrain's build
  installed: both his, or the lead's).

## Surprises & Discoveries

- Observation: MAF's own A2UI support (`agent_framework_ag_ui._a2ui`, `A2UIAgent`, `enable_a2ui`) wraps an agent and
  has a render sub-agent (a second model call) generate the surface; it needs the extra `ag-ui-a2ui-toolkit`, which is
  not installed. It does not apply to a workflow's card.
  Evidence: `_a2ui/_factory.py`, "Auto-injection of render_a2ui happens CLIENT-side via the AG-UI a2ui-middleware";
  `python -c "import ag_ui_a2ui_toolkit"` raises ModuleNotFoundError.
- Observation: MAF's workflow host turns a custom workflow event into an AG-UI CUSTOM event named by the event's type,
  with its data as the value. Evidence: `_workflow_run.py`, "Fall back to custom events for diagnostics, orchestration
  events, and custom workflow events" (`CustomEvent(name=_event_name(event), value=_custom_event_value(event))`).
- Observation: `@a2ui/react` 0.15.0 no longer ships React implementations of the basic catalog for v0.9 (its
  CHANGELOG: "`@a2ui/react/v0_9` no longer ships a React implementation of the basic catalog ... they render as W3C
  Custom Elements"); the app supplies its own implementations with `createComponentImplementation` against the basic
  catalog's component APIs (`ColumnApi`, `RowApi`, `TextApi`, `ButtonApi` from `@a2ui/web_core/v0_9/basic_catalog`).

## Decision Log

- Decision: the surface is built by Steward's workflow from the plan (a pure function), not by a model, and is sent
  as a MAF custom workflow event of type `a2ui`.
  Rationale: ADR-0013 (the card must be exactly the plan; MAF's workflow host carries custom events as it ships).
  Date/Author: 2026-11-05, Kyle (ADR-0013).
- Decision: the event's value is `{"request_id": <the card's id>, "messages": [<A2UI v0.9 messages>]}`; the surface id
  is `plan-<card id>`; the catalog is the v0.9 basic catalog
  (`https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json`); the Buttons' actions are `approve` and `deny`
  with `context: {"requestId": <id>}`.
  Rationale: the client must tie the surface to its interrupt (the interrupt's id is the card's id) and an action to
  its answer, with the protocol's own fields.
  Date/Author: 2026-11-05, in the plan.
- Decision: the capability is A13 in spec 001 ("the plan's card carries its A2UI surface, built from the plan"),
  required, with its case in a new set `t2-cards.yaml` v1 (runner `plans`: the plan phase alone, every card denied)
  scored by a new deterministic check `plan_card_surface`.
  Rationale: the operator's rule that every capability comes with its eval; a new set leaves the existing sets'
  versions and baselines as they are. No eval is run by this work.
  Date/Author: 2026-11-05, in the plan.
- Decision: Jesster pins `@a2ui/react` and `@a2ui/web_core` 0.15.0 (and `zod`, their dependency), and draws the four
  basic-catalog components the surface uses (Column, Row, Text, Button) with the app's own classes.
  Rationale: use the renderer as it ships; Jesster's UI rules (the app's own components and look).
  Date/Author: 2026-11-05, in the plan.

## Outcomes & Retrospective

Nothing to report yet.

## Context and Orientation

Steward (`worlds/steward`, this repository) runs his request through a MAF workflow,
`harness/steward/step04_production_ready/steward_workflow.py`: route, explore, plan, read_plan, ask_approval (the plan
card), execute, check, repair, commit, report. The plan card is raised in `AskApproval.ask` with
`ctx.request_info(request_data=Content.from_function_approval_request(id=call_id, function_call=call), ...)`, where
`call` is a function call named `approve_plan` whose arguments are the plan: `{"request", "plan", "steps"}`. The
AG-UI host, `ag_ui_app.py` on 127.0.0.1:43122, is MAF's `agent_framework_ag_ui` (1.7.1) serving the workflow: the card
reaches the client as a `request_info` tool call, a CUSTOM `request_info` event and the run's RUN_FINISHED with
`outcome: {type: "interrupt", interrupts: [{id: <call_id>, metadata: {agent_framework: {function_call,
checkpoint_id}}}]}`. The answer is a new run with `resume: [{interruptId, status: "resolved", payload: {approved}}]`.
A custom workflow event is a `WorkflowEvent` subclass added with `ctx.add_event`; Steward already has one,
`StewardProgress`. The model-free checks of the harness are in `test_harness.py` (the gate); the eval sets are YAML
files in `harness/steward/evals/` with their runner in `evals.py` (`plans_main`, `plan_phase_conversation`,
`PLANS_CHECKS`), the capability map in `harness/steward/evals/capabilities.yaml` and `docs/specs/001-capability-evals.md`.

Jesster (`worlds/jesster`, the app `secondbrain/`) is the console. Its main process runs the AG-UI client,
`secondbrain/electron/agent/agui.cjs`, which calls `approve(name, args, summary)` once per interrupt;
`secondbrain/electron/agent/service.cjs` (`approveInWindow`) turns that into a card `{id, sessionId, name, args,
summary}` sent to the window (`agent:approval`) and, for a phone turn, to `onCard` (Telegram and Discord record it in
the phone log as a `card` line). The window's Agent tab is `secondbrain/src/components/AgentView.tsx` (its cards with
Allow once, Deny and a reply box) and the Phone view `secondbrain/src/components/PhoneView.tsx`. Types are in
`secondbrain/src/types/desktop.ts` (`ApprovalRequest`, `PhoneEntry`). Tests run with `tsx --test` (`npm test`).

A2UI v0.9, in brief: messages `{"version": "v0.9", "createSurface": {surfaceId, catalogId}}`, `{"version": "v0.9",
"updateComponents": {surfaceId, components: [...]}}`; components are flat, `{id, component: "Column" | "Row" | "Text" |
"Button", ...}`, one of them `root`; a Column or Row lists `children` by id; a Text has `text`; a Button has `child` (a
Text's id, its label), optional `variant: "primary"`, and `action: {"event": {"name", "context"}}`. The renderer is
`@a2ui/web_core`'s `MessageProcessor(catalogs, actionHandler)` (`processMessages(messages)`, `model.surfacesMap`) and
`@a2ui/react/v0_9`'s `A2uiSurface` (`surface` prop), with a `Catalog(id, '0.9', implementations)` built from
`createComponentImplementation(Api, render)`.

## Plan of Work

Milestone 1 (Steward). In `steward_workflow.py`, add `A2UI = "a2ui"`, `A2UI_BASIC_CATALOG` (the v0.9 basic catalog's
id), a pure function `plan_card_surface(plan: dict, request_id: str) -> list[dict]` that returns the `createSurface`
and `updateComponents` messages (root Column: a Text "Steward's plan", a Text with the plan's words, one Text per step
numbered "1. ...", a Row with Button `approve` (variant primary, label "Approve") and Button `deny` (label "Deny"),
each action carrying `{"requestId": request_id}`), and a `PlanCardSurface(WorkflowEvent)` of type `a2ui` with data
`{"request_id", "messages"}`. `AskApproval.ask` adds it with `ctx.add_event` just before `request_info`. In
`evals.py`: `plan_phase_conversation` adds each `a2ui` event as an assistant message named `a2ui` carrying its data
as JSON text; a new `@evaluator` `plan_card_surface` passes when the approve_plan card has an `a2ui` message with its
id whose messages are v0.9 (`createSurface` on the basic catalog, `updateComponents` with a root, an `approve` and a
`deny` Button carrying the card's id) and whose Texts name every step of the plan; `PLANS_CHECKS` gains it and
`plans_main` scores it. New set `harness/steward/evals/t2-cards.yaml` v1 (runner `plans`), one case, capability
[A13], checks [plan_card_surface], its fingerprint recorded in `baselines.json`. A13 in `capabilities.yaml` (required)
and spec 001 (section A, the count). Gate tests: the pure function's shape; the AG-UI host's stream carries CUSTOM
`a2ui` with the card's id before RUN_FINISHED's interrupt; the plans runner scores a scripted plan card with its
surface as passing and without it as failing. Restart required: Steward's AG-UI host.

Milestone 2 (Jesster). In `agui.cjs`, a CUSTOM event named `a2ui` with a `request_id` and `messages` is kept by id;
for each interrupt, `approve(name, args, summary, { a2ui })` passes the messages kept for its id (or nothing). In
`service.cjs`, `approveInWindow`'s approver takes that fourth argument and puts `a2ui` on the card (the window's
`agent:approval` and `onCard`); Telegram and Discord record `a2ui` on the phone log's `card` line. Types:
`ApprovalRequest.a2ui?` and `PhoneEntry.a2ui?`. Tests in `agui.test.cjs` and `agent.test.cjs`: the surface reaches
the card with its interrupt's id; a surface for another id does not; a card with no surface has none.

Milestone 3 (Jesster). Add `@a2ui/react` and `@a2ui/web_core` 0.15.0 and `zod` to `secondbrain/package.json`. A
module `src/utils/a2uiCard.ts` with the pure parts: `planCardAnswer(action, requestId)` (an action `approve` or `deny`
whose context names this card is its answer, true or false; anything else is no answer) and `drawable(messages)`
(the processor accepts the messages and a surface exists). A component `src/components/A2uiCard.tsx`: a
`MessageProcessor` over a catalog of the app's own implementations of Column, Row, Text and Button (the basic
catalog's APIs and id, the app's Tailwind classes, as the old card's), `A2uiSurface` for the surface, its action
handler calling the card's answer, inside an error boundary whose fallback is the old card. `AgentView.tsx` and
`PhoneView.tsx` draw `A2uiCard` when the card (or the phone line) carries `a2ui`, the old card otherwise; the reply
box under the Agent tab's card stays. Tests: `planCardAnswer`; the processor accepts Steward's surface (a fixture of
`plan_card_surface`'s output) and refuses a broken one; the views draw `A2uiCard` only with a surface (red when the
wiring is removed). Restart required: SecondBrain's next build.

## Concrete Steps

Steward, from the repository root, with its virtual environment's Python (every command with a time limit):

    timeout 300 python -m compileall -q .
    timeout 300 python -W ignore harness/steward/step04_production_ready/evals.py validate
    timeout 900 python -m pytest -q -p no:cacheprovider harness/steward/step04_production_ready/test_harness.py

`validate` names the new set's fingerprint to record in `baselines.json` under `cards` version 1. Jesster, from
`worlds/jesster/secondbrain`: `npm ci --legacy-peer-deps --ignore-scripts` after the dependency change, then
`timeout 300 npm run lint`, `timeout 900 npm test`, `timeout 600 npm run build`. Each milestone is one pull request
naming ADR-0013 and this plan, merged when its checks pass. No eval run, no host restart and no build install is part
of this work: they are the operator's (or the lead's).

## Validation and Acceptance

Model-free: the gate tests and Jesster's tests above, each red when its piece is removed, and `evals.py validate`
passing with A13 required. Live, after Steward's AG-UI host is restarted and SecondBrain's build carrying Milestone 3
is installed: in the Agent tab, "Add a docstring to convert_length in
harness/steward/working/sample-project-2/units.py." shows the plan card as a heading, the plan, its numbered steps and
Approve and Deny buttons; Deny ends the run as before ("Not approved"); Approve runs it. The same card from Telegram
shows in the Phone view drawn the same way, and Telegram's own buttons are unchanged. One case of `cards`
(`run-bar.ps1 -Sets cards -Runs 1`, the operator's to run) scores `plan_card_surface`.

## Idempotence and Recovery

Additive: a host that sends no `a2ui` event, the Responses fallback, or a surface the processor refuses gives
today's card. Removing the event in Steward or the renderer in Jesster returns to today's card; each is one pull
request to revert.

## Artifacts and Notes

None yet.

## Interfaces and Dependencies

MAF `agent_framework` 1.24 `WorkflowEvent` and `ctx.add_event`; `agent_framework_ag_ui` 1.7.1 (custom events to
CUSTOM); A2UI v0.9; `@a2ui/react` 0.15.0, `@a2ui/web_core` 0.15.0, `zod` 3 (their dependency); Jesster's
`@ag-ui/client` 0.0.59 unchanged. At the end of Milestone 1, `steward_workflow.plan_card_surface(plan: dict[str, Any],
request_id: str) -> list[dict[str, Any]]` and `steward_workflow.PlanCardSurface` exist; at the end of Milestone 2,
`ApprovalRequest.a2ui?: unknown[]`; at the end of Milestone 3, `planCardAnswer(action: {name: string; context?:
Record<string, unknown>}, requestId: string): boolean | null` and `A2uiCard` exist.

---

Revision note, 2026-11-05: first version, from ADR-0013, after AG-UI step 3's Milestones 1 to 3 (Jesster #93 to #95).
