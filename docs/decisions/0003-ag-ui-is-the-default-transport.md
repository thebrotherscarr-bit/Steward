---
status: accepted
contact: Kyle
date: 2026-11-05
deciders: Kyle
---

# AG-UI is the default transport, Responses the fallback

Supersedes in part [ADR-0001](0001-steward-is-a-maf-harness-agent.md): the Agent tab reaches Steward over AG-UI (43122) by default; his Responses host
(43120) is the fallback.

## Context and Problem Statement

Until 2026-11-05 SecondBrain's Agent tab reached Steward over the OpenAI Responses protocol, served by MAF's
`ResponsesHostServer` (`hosted.py`, 127.0.0.1:43120), with approval cards as `mcp_approval_request` items. MAF also
ships an AG-UI host (`agent_framework_ag_ui`), which streams a workflow's steps and turns approvals into AG-UI
interrupts. Which transport should every caller (the Agent tab, the phone, automations, evals) use?

## Decision Drivers

- The operator, 2026-11-05: "The pairing of MAF with UI abstractions (like AG-UI) separates the underlying logic from
  the visual layer, resulting in more robust, non-breaking desktop automation. This seems important."
- Use MAF as it ships: the AG-UI host and its interrupt and step events come from MAF, not from our own code.
- The workflow's step events (StepStarted, StepFinished per executor) are what the console shelves and the Flows
  shelf need to light up steps live.
- Evidence first: the switch is made on a measured comparison (`evals.py compare-transports`), with the rule written
  in `harness/steward/evals/README.md` ("The decision rule").

## Considered Options

- AG-UI by default, Responses as the fallback.
- Responses only (as before).
- AG-UI only.

## Decision Outcome

Chosen option: "AG-UI by default, Responses as the fallback", because AG-UI passed small 3/3 at `6401b56` and was
faster on every case, and the fallback keeps a turn working while the AG-UI host is down.

The operator's word, 2026-11-05: "use it" (recorded in Jesster #77).

- Step 1, Steward #138: Steward's workflow served over AG-UI on 127.0.0.1:43122 (`ag_ui_app.py`), cards as its
  interrupts (resumed with `interruptId` and `forwardedProps.checkpointId`).
- Step 2, Jesster #70 then #77: the Agent tab, the phone and automation turns reach Steward over AG-UI. If its host is
  down, the turn falls back to Responses (43120) and one console line says so. Only a Responses choice made in
  Settings stays on Responses.
- The eval workflows run with `-Transport ag-ui`. _(2026-11-05, later: for asks sets only. evals.py sends only an
  asks set (small, heldout) over a host and exits 2 on any other, so the Flows' "Eval: bfcl" failed at once. A
  workflow's `eval_start` step now sends no transport unless it names one, and SecondBrain's `eval_start` picks AG-UI
  when every set is an asks set and in-process otherwise; a host transport named for another set is refused before
  anything starts. Jesster `estate.cjs`, Steward `recipe_workflow.py`; ADR-0009's flows are unchanged.)_
  _(2026-11-08: the flows saved while AG-UI was the default kept `transport: ag-ui` in their `eval_start` step, so
  on 2026-11-06 the Flows' "Eval: bfcl", "Eval: steps" and "Eval: direct" were refused at once. The step now
  chooses the transport by set itself (`recipe_workflow.eval_transport`, from the set files' `runner:` lines): AG-UI
  only when every set is an asks set, else in-process, and a stored host transport on any other set is stale: it
  runs in-process with one logged line. Jesster removes such a stored transport from saved flows once. evals.py's
  own refusal stands for the command line.)_
- Exception (noted 2026-11-05): an improve conversation stays on Responses, because its review card has no AG-UI
  answer yet (Jesster `electron/agent/service.cjs`, the `!s.improve` test before the AG-UI path).

### Consequences

- Good, because the UI reads MAF's own step and interrupt events, so a change in Steward's workflow does not break the
  console.
- Good, because the evals can check the same events the operator sees.
- Bad, because the AG-UI host keeps checkpoints in memory: a restart drops a parked card's checkpoint, and its resume
  is refused (the case fails with its reason).
- Neutral: MAF's `agent-framework-ag-ui` 1.7.1 pins `ag-ui-protocol` below 0.2, while AG-UI's latest is 1.0. We hold
  until MAF moves.

## Validation

Jesster's `agent.test.cjs` covers the default, the fallback and a chosen setting; `agui.test.cjs` covers the resume.
Steward's `evals.py --transport ag-ui` runs the asks sets against the live AG-UI host.

## More Information

- Next: AG-UI step 3, the Phone view and the console shelves on the same events; then an A2UI pilot for approval
  cards only (after step 2, the operator's choice). A2A is deferred until a second autonomous agent exists.
- The SecondBrain note `steward-s-dev-path-evals-that-grow-with--cb3211`, sections "AG-UI: added on his word" and
  "Protocols".
