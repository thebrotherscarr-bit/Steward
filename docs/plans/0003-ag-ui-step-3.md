# AG-UI step 3: show Steward's workflow steps live in the Agent tab's console and the Phone view

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and
`Outcomes & Retrospective` must be kept up to date as work proceeds.

This document is maintained in accordance with `.agent/PLANS.md` at the repository root. It carries out the "Next"
item of [ADR-0003](../decisions/0003-ag-ui-is-the-default-transport.md) ("AG-UI step 3, the Phone view and the console
shelves on the same events; then an A2UI pilot for approval cards only"). Its eval and test duties follow
[ADR-0012](../decisions/0012-stewards-bar-is-our-own-capability-evals.md).

## Purpose / Big Picture

When the operator asks Steward for something, Steward's request runs through a fixed workflow: plan, the plan's card,
execute, check, repair, commit card, report. Today the operator sees Steward's words, tool lines and cards, but not
which of those steps is running: the console in his Agent tab and the Phone view (his Telegram and WhatsApp
conversations, shown on the PC) show a stream of text with no step. AG-UI, the protocol Steward's host speaks to the
console since ADR-0003, already sends a STEP_STARTED and a STEP_FINISHED event for every step; nothing reads them.

After this plan, the Agent tab's console shows a line of steps for the turn in progress (plan, approve, execute, check,
repair, commit, report), each lit as it starts and marked done or failed as it ends, and the Phone view shows the same
for a turn that came from the phone. The operator can see at a glance that Steward is in "check, attempt 2" rather than
stuck. Then, as a separate pilot, the plan card can be drawn from an A2UI description sent by Steward rather than by
Jesster's own card code.

## Progress

- [x] (2026-11-05) AG-UI step 1: Steward's workflow served over AG-UI on 127.0.0.1:43122 (`ag_ui_app.py`, Steward #138).
- [x] (2026-11-05) AG-UI step 2: the Agent tab, the phone and automation turns reach Steward over AG-UI by default,
  Responses (43120) the fallback (Jesster #70, #77).
- [x] (2026-11-05) This ExecPlan written.
- [ ] Milestone 1: Jesster's AG-UI client turns STEP_STARTED and STEP_FINISHED into console events, with a test.
- [ ] Milestone 2: the Agent tab's console draws the turn's steps from those events.
- [ ] Milestone 3: the Phone view draws the same for a phone turn.
- [ ] Milestone 4 (pilot, on the operator's word to start it): A2UI for the plan's approval card only.

## Surprises & Discoveries

- Observation: the events are already sent and already tested on Steward's side; only the client ignores them.
  Evidence: `harness/steward/step04_production_ready/ag_ui_app.py`, its header ("RUN_STARTED, STEP_STARTED/STEP_FINISHED
  per executor"), and `test_harness.py`'s scripted AG-UI streams carrying `{"type": "STEP_STARTED", "stepName":
  "plan"}`; Jesster's `secondbrain/electron/agent/agui.cjs` handles TEXT_MESSAGE_*, REASONING_*, TOOL_CALL_* and
  RUN_FINISHED, and has no case for STEP_*.

## Decision Log

- Decision: use AG-UI's own step events as MAF ships them; no step protocol of our own.
  Rationale: ADR-0003, "the UI reads MAF's own step and interrupt events, so a change in Steward's workflow does not
  break the console"; use MAF as it ships.
  Date/Author: 2026-11-05, Kyle (ADR-0003).
- Decision: the A2UI pilot is for the approval card only and comes after step 3.
  Rationale: the operator's choice recorded in ADR-0003 and ARCHITECTURE.md section 2.
  Date/Author: 2026-11-05, Kyle.
- Decision: no change to the look beyond the step line; Jesster's UI rules hold (current, simple, readable, consistent;
  the app's own components and CSS variables).
  Rationale: the operator's UI rules of 2026-11-04, kept in the guidance note.
  Date/Author: 2026-11-05, in the plan.

## Outcomes & Retrospective

Nothing to report yet.

## Context and Orientation

Steward (`worlds/steward`, this repository) runs his workflow, `harness/steward/step04_production_ready/steward_workflow.py`,
under three hosts; the AG-UI one is `ag_ui_app.py` on 127.0.0.1:43122, built on MAF's `agent_framework_ag_ui`
(version 1.7.1, which pins the AG-UI protocol package below 0.2). AG-UI is an open protocol for streaming an agent's
run to a user interface as typed events: RUN_STARTED, STEP_STARTED and STEP_FINISHED (with `stepName`, one pair per
workflow executor), TEXT_MESSAGE_* (words), TOOL_CALL_* (tool calls), and RUN_FINISHED (with an interrupt when the run
waits on a card). A card is resumed by a new run with the interrupt's id and checkpoint.

Jesster (`worlds/jesster`; the app is `secondbrain/`) is the console. Its main process runs the AG-UI client,
`secondbrain/electron/agent/agui.cjs` (on `@ag-ui/client` 0.0.59's `HttpAgent`), and turns events into the Agent
tab's events, sent to the window. The Agent tab is `secondbrain/src/components/AgentView.tsx` with its console
`AgentConsole.tsx` and helpers in `secondbrain/src/utils/agentConsole.ts`. The Phone view,
`secondbrain/src/components/PhoneView.tsx`, shows each phone chat and its entries through the `phone:list`,
`phone:read` and `phone:entry` channels in `secondbrain/electron/preload.cjs`; the phone's turns go to Steward through
`secondbrain/electron/agent/phone.cjs` and `service.cjs`, over AG-UI by default.

A2UI is a protocol for an agent to describe a small user interface (such as a card with a question and buttons) as
data, which the client draws with its own components.

## Plan of Work

Milestone 1 (Jesster). In `agui.cjs`, add cases for STEP_STARTED and STEP_FINISHED that emit one console event each,
`{type: 'step', name, state: 'started' | 'finished'}`, on the same handler path as the tool lines; a step still open
when RUN_FINISHED carries an error is reported failed. Test in `agui.test.cjs` with a scripted stream (plan started,
plan finished, execute started, an interrupt): the events come out in order, and the test goes red if the cases are
removed.

Milestone 2 (Jesster). In `agentConsole.ts`, a pure function from a turn's events to its step line (the workflow's
step names in order, each `waiting`, `running`, `done` or `failed`; a repeated `check` or `repair` counted as an
attempt). In `AgentConsole.tsx`, draw that line above the turn's output with the app's existing components. Test in
`agentConsole.test.ts` over a fixture of events.

Milestone 3 (Jesster). Pass the same step events with the phone's entries (`phone:entry`), and draw the same line in
`PhoneView.tsx` for a turn in progress. Test that a phone turn's step events reach the view's state.

Milestone 4 (pilot, both repositories, only on the operator's word). Steward's plan card carries an A2UI description
beside today's interrupt; Jesster draws it when present and today's card otherwise. Its own ADR before any build, as it
adds a protocol (the doc standard).

## Concrete Steps

Jesster, from `worlds/jesster/secondbrain`, its unit tests with the time limits in its `AGENTS.md`. Steward needs no
change for Milestones 1 to 3; if a step name changes there, its gate (`timeout 900 python -m pytest -q -p
no:cacheprovider harness/steward/step04_production_ready/test_harness.py`) still runs. Each milestone is one pull
request. Restart required: SecondBrain's next build.

## Validation and Acceptance

With SecondBrain's build carrying Milestone 2, ask in the Agent tab "Add a docstring to convert_length in
harness/steward/working/sample-project-2/units.py." Before the plan card, the step line shows plan running; after
Approve, execute running, then check; the line ends with commit waiting on its card. Deny the commit card: the line
shows commit failed and the run ends. The same from Telegram shows the line in the Phone view.

## Idempotence and Recovery

The change is additive: events the console does not know are ignored as before, so an older Steward host or the
Responses fallback (which sends no step events) leaves the line empty and the turn works as today.

## Artifacts and Notes

None yet.

## Interfaces and Dependencies

MAF's `agent_framework_ag_ui` 1.7.1 as it ships (its STEP_STARTED and STEP_FINISHED per executor); Jesster's
`@ag-ui/client` 0.0.59, pinned to match it until MAF moves to AG-UI 1.0 (ADR-0003). No new dependency.

---

Revision note, 2026-11-05: first version, from ADR-0003 and the code at Steward #163 and Jesster #92.
