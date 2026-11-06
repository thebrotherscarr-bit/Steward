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
- [x] (2026-11-05 20:05) Measured what the real host sends (a scripted model through `ag_ui_app.build_ag_ui_app`): see
  Surprises & Discoveries.
- [x] (2026-11-05 20:20) Milestone 1: Jesster's AG-UI client turns STEP_STARTED and STEP_FINISHED into
  `workflow_step` events, with a test (Jesster #93). Steward's side: gate test
  `test_the_ag_ui_host_announces_each_workflow_step_by_its_executor` and capability A12 (this repository's pull
  request for the plan's update).
- [x] (2026-11-05 20:28) Milestone 2: the Agent tab draws the turn's step line from those events (Jesster #94):
  `stepLine` in `agentConsole.ts`, `StepLine.tsx`, drawn by `AgentView.tsx` above the turn's output.
- [x] (2026-11-05 20:33) Milestone 3: the Phone view draws the same for a phone turn (Jesster #95): `phoneSession`
  and `keepSteps` in `agentConsole.ts`, `PhoneView.tsx`.
- [ ] The live acceptance below, on SecondBrain's build carrying Jesster #95 (the operator's build to install; no
  build or host was restarted by this work).
- [ ] Milestone 4 (pilot): A2UI for the plan's approval card only. The operator gave his word on 2026-11-05 ("do the
  A2UI work, as well"); it is carried out under its own ADR and ExecPlan, as this plan's Milestone 4 asked:
  ADR-0013 and `docs/plans/0004-a2ui-pilot-plan-card.md`.

## Surprises & Discoveries

- Observation: the events are already sent and already tested on Steward's side; only the client ignores them.
  Evidence: `harness/steward/step04_production_ready/ag_ui_app.py`, its header ("RUN_STARTED, STEP_STARTED/STEP_FINISHED
  per executor"), and `test_harness.py`'s scripted AG-UI streams carrying `{"type": "STEP_STARTED", "stepName":
  "plan"}`; Jesster's `secondbrain/electron/agent/agui.cjs` handles TEXT_MESSAGE_*, REASONING_*, TOOL_CALL_* and
  RUN_FINISHED, and has no case for STEP_*.

- Observation: MAF wraps each superstep of the graph in its own STEP_STARTED/STEP_FINISHED pair, named
  `superstep:<n>`, around the executor's own pair; the executors' names are their ids (`route`, `explore`, `plan`,
  `read_plan`, `ask_approval`, `execute`, `check`, `repair`, `commit`, `report`, `answer`), not the "approve" this plan
  first wrote. Evidence, the first run of "Write x.py." with a scripted plan: `superstep:1, route, superstep:2,
  explore, superstep:3, plan, superstep:4, read_plan, superstep:5, ask_approval (request_info), RUN_FINISHED`.
- Observation: every step is finished before a card's RUN_FINISHED, and the card's step runs again on the resume,
  where it takes the answer. Evidence: the resume after Approve streams `ask_approval` again, then `execute`; the
  AG-UI client itself refuses a run that ends with a step open ("Cannot send 'RUN_FINISHED' while steps are still
  active: execute", seen in a first fake stream). So "a step still open when the card is denied" never happens: a
  denied card's step is the one that finishes on the resume.
- Observation: a denied write card does not end the run in this workflow when the model stops on its own; the
  scripted run went `execute, check, report` after the No. The step line reports what ran.

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

- Decision: the client's event is `{type: 'workflow_step', name, state: 'started' | 'finished' | 'failed'}`, not
  `type: 'step'`.
  Rationale: `'step'` is already the local loop's step counter in Jesster's `AgentEvent` (`src/types/desktop.ts`).
  Date/Author: 2026-11-05, in the plan.
- Decision: MAF's `superstep:<n>` pairs are not passed to the window; a card answered No marks its step `failed` when
  that step finishes on the resume; a step open when a run errors is marked `failed`.
  Rationale: the measured stream (Surprises & Discoveries); the supersteps are the engine's rounds, not his steps.
  Date/Author: 2026-11-05, in the plan.
- Decision: the capability is A12 in spec 001 and `capabilities.yaml` ("each step of a request is announced as it
  runs, by its executor's id"), required, named by the steps set's `discount_fix` case (its `plan_step` and
  `execute_step` find each step's work by its executor's own events), with the host's side in a gate test and the
  client's in Jesster's tests. No new eval set version: a case's `capability` ids are not in its fingerprint.
  Rationale: the operator's rule that every capability comes with its eval (ADR-0012, amended); no eval is run for
  this (a baseline run was in progress), and `evals.py validate` passes.
  Date/Author: 2026-11-05, in the plan.
- Decision: the step line is drawn in the Agent tab's conversation (`AgentView.tsx`), above the turn's output, and
  not inside the console panel (`AgentConsole.tsx`) that Milestone 2 first named.
  Rationale: the console panel holds the shelves and has no conversation (it may also be folded); the line belongs
  to the turn the operator is watching. One component (`StepLine.tsx`) draws it in both views.
  Date/Author: 2026-11-05, in the plan.
- Decision: the Phone view gets the step events from the same `agent:event` channel, matched by the phone chat's
  Steward session id (each phone entry carries `sessionId`), not as `phone:entry` lines.
  Rationale: the phone log is a capped record of what was said (5000 lines); a step is live state, and every
  session's events, phone sessions included, already reach the window on `agent:event` (`service.cjs` `send`).
  Date/Author: 2026-11-05, in the plan.

## Outcomes & Retrospective

2026-11-05, Milestones 1 to 3. The step events Steward's AG-UI host already sent now reach the operator: the Agent
tab and the Phone view draw a line of steps (plan, approve, execute, check, repair, commit, report) for the turn in
progress, each running, done or failed, a waiting card shown on its step and "check, attempt 2" counted. Nothing in
Steward's running code changed; the wire is held on both sides: Steward's gate test
`test_the_ag_ui_host_announces_each_workflow_step_by_its_executor` and capability A12 (required, `evals.py validate`)
for the host, Jesster's `agui.test.cjs` and `agentConsole.test.ts` for the client and both views, each red when its
piece is unplugged. What remains: the live acceptance on the operator's build, and Milestone 4 under its own plan.

Lesson: the plan was written from the code's names and guessed "approve" for a step and an open step at a card;
measuring the real host first (a scripted model through `build_ag_ui_app`, a few minutes) gave the true names, MAF's
`superstep:<n>` pairs and the resume behaviour, and the client's own verifier (no RUN_FINISHED with a step open)
before any UI was built.

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
