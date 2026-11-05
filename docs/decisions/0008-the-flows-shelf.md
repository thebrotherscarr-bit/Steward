---
status: accepted; superseded in part by ADR-0009
contact: Kyle
date: 2026-11-05
deciders: Kyle
---

# 0008: The Flows shelf

> 2026-11-05: superseded in part by [ADR-0009](0009-flows-are-ordered-tool-chains-automations-schedule-flows.md):
> Set up holds the automations (a saved flow, when, on/off) and builds no flows; "+ New flow" is the only way to
> make a flow.

## Context and Problem Statement

On 2026-11-04 the operator removed Flows from Jesster's top bar ("flows can be removed, steward will do that"), and the
guidance said "no UI for what Steward does himself (notes, flows ...)". Once automations became recipes run as MAF
workflows ([ADR-0005](0005-automations-are-recipes-run-as-maf-workflows.md)), there was no place to see them, run one,
set one up, or see whether it works. Where do flows live in the UI, and what is drawn from where?

## Decision Drivers

- The operator, 2026-11-05: "I want the shelf to be like the old flows shelf, where it has a UI that is clean and
  usable, the kanban boards with the wiring thing ... like an IDE where there is the agent on a foldout card like the
  console works on the agent tab ... set them to run now, or automate them for later, then the evals can run in flow
  and check the flows that are working ... we kind of data-hoard and tune the whole process while steward works."
- Use MAF as it ships: the graph from `Workflow.to_dict()` / `WorkflowViz`, live steps from AG-UI's StepStarted and
  StepFinished, checks from `evaluate_workflow` with `LocalEvaluator`. DevUI is a sample app, not for production; we
  read its shapes only.
- Jesster's UI rules (2026-11-04): current, simple, readable, consistent; Aurora's look as the reference, Aurora
  itself never changed.

## Considered Options

- One Flows shelf in Jesster: a board, a wiring canvas, Run now and Set up, a fold-out Steward card, evals as flows.
- No flows UI; Steward reports on flows in chat (the 2026-11-04 ruling).

## Decision Outcome

Chosen option: "One Flows shelf in Jesster", because it is the operator's 2026-11-05 call, which supersedes the
2026-11-04 removal for flows.

- **Canvas:** each flow's steps as block cards wired output to input on `@xyflow/react` (the old Flows tab's look),
  laid out in layers. The graph comes from MAF for Steward's workflows, never drawn by hand.
- **Run now and Set up** (Jesster #83): Run now calls the same `runSchedule` path as the clock; Set up is a fold-out
  holding the automations (moved out of the Agent console): create, edit, turn on or off, delete.
- **Steward's card** folds out on the right like the Agent tab's console; he builds and edits flows there through
  `automation_save` on the operator's card (a placeholder today).
- **Evals are flows that check flows:** an eval recipe is a card; a recipe can carry a `check`; Passing and Failing
  come from it.
- **Run history is data:** one line per run, pointing at the run's MAF/HALO trace, with a one-line failure label for
  error analysis.
- Flows took the place of "Open Aurora" in the top bar ("for now", the operator, 2026-11-05).

### Consequences

- Good, because the operator can see, run and schedule every flow in one place, and the evidence for tuning is kept.
- Bad, because a board has no MAF counterpart; it is kept a pure view over run data, with no state of its own.
- Neutral: the canvas is ours (xyflow), drawing MAF's nodes and edges unchanged.

## Validation

Each piece names its test: `flowGraph.test.tsx` (graphs, fold, shelf), `agentConsole.test.ts` (the bar carries
Flows), the schedule edit and run tests in Jesster #83.

## More Information

- Built: piece 1, the read-only shelf (Jesster #79); Run now, Set up and the layered canvas (Jesster #83).
- Open: the run history, the graph from Steward's `to_dict()` (`recipe_graph`, Steward #150, is ready to serve it),
  `automation_save` behind Steward's card, evals in flow.
- The plan: the SecondBrain note `plan-the-flows-shelf-ide-for-steward-s-f-04a93a`. It asks that the guidance
  note's "no UI for ... flows" line be annotated with this date.
