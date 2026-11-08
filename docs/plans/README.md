# ExecPlans

One file per multi-step build in progress: `NNNN-title-with-dashes.md`, written and kept to `.agent/PLANS.md` (the
OpenAI Cookbook's ExecPlan format, with this Estate's adaptations at its top).

An ExecPlan is a living document: its `Progress`, `Surprises & Discoveries`, `Decision Log` and
`Outcomes & Retrospective` sections are kept current as the work goes. When the work is done, the plan stays here as
the record, with its retrospective written.

| Plan | Title | Carries out | State |
|---|---|---|---|
| [0001](0001-capability-evals-build.md) | Build Steward's capability evals: one small case for every capability, in tiers T2, T3 and T4 | [ADR-0012](../decisions/0012-stewards-bar-is-our-own-capability-evals.md), [spec 001](../specs/001-capability-evals.md) | in progress: Milestones 1 and 2 built (Steward #164); the `bounds` bar and Milestones 3 to 6 open |
| [0002](0002-flows-steward-card-and-automation-save.md) | Let Steward build flows and automations from the Flows shelf, on the operator's card | [ADR-0008](../decisions/0008-the-flows-shelf.md), [ADR-0009](../decisions/0009-flows-are-ordered-tool-chains-automations-schedule-flows.md) | not started |
| [0003](0003-ag-ui-step-3.md) | AG-UI step 3: show Steward's workflow steps live in the Agent tab's console and the Phone view | [ADR-0003](../decisions/0003-ag-ui-is-the-default-transport.md) | Milestones 1 to 3 built (Jesster #93, #94, #95; Steward #166); the live acceptance on the operator's build open; Milestone 4 carried out by plan 0004 |
| [0004](0004-a2ui-pilot-plan-card.md) | A2UI pilot: draw Steward's plan card from an A2UI surface he sends | [ADR-0013](../decisions/0013-a2ui-pilot-plan-card.md) | Milestones 1 to 3 built (Steward #169, #170; Jesster #96, #97); the live acceptance on the operator's builds open |
| [0005](0005-steward-runs-the-pc-from-the-phone.md) | Steward runs the PC from the phone: the away loop, the Estate kept running, and one family per operation | [ADR-0016](../decisions/0016-steward-is-the-brain-of-the-pc.md), [ADR-0018](../decisions/0018-harness-profiles-per-task-tuned-by-evals.md) | frozen 2026-11-08 (ADR-0018); order M9a, M0 through profiles, MP, M1 to M10; M0 in progress |

The order between them is [ARCHITECTURE.md](../ARCHITECTURE.md), section 6.
