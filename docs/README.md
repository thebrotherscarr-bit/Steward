# Docs

The design of the whole Estate lives here. Every document in every repository of the Estate follows this map from
2026-11-05 (the operator: "make this the standard moving forward, this way nothing gets misaligned"; "we need to get
this set up so all of our docs match this format from here moving forward").

## The doc map: which document for what

| Document | For | Where | Format, from |
|---|---|---|---|
| **ARCHITECTURE** | The current whole: parts, wires, data, flows, rules, plan ahead | [ARCHITECTURE.md](ARCHITECTURE.md) | ours; updated in the same PR as any change to the shape |
| **ADR** | One architectural decision, its options and why | [decisions/](decisions/README.md) `NNNN-title.md` | MAF's `docs/decisions/` (MADR): `adr-template.md`, `adr-short-template.md` |
| **Spec** | A feature's design before it is built: goal, problem, API changes, end-to-end samples | [specs/](specs/spec-template.md) `NNN-title.md` | MAF's `docs/specs/spec-template.md` |
| **ExecPlan** | A multi-step build in progress, a living document (Progress, Surprises & Discoveries, Decision Log, Outcomes & Retrospective) | [plans/](plans/README.md) `NNNN-title.md`, written to [`.agent/PLANS.md`](../.agent/PLANS.md) | OpenAI Cookbook, "Using PLANS.md for multi-hour problem solving" (`articles/codex_exec_plans.md`) |
| **AGENTS.md** | How an agent works in a repository: key docs, commands with timeouts, rules, structure | each repository's root | MAF's `python/AGENTS.md` and `dotnet/AGENTS.md`; agents.md |
| **CHANGELOG** | What landed, one entry per change | each repository's `CHANGELOG.md` | Keep a Changelog 1.1.0 |
| **README** | What a repository is and how to install it; links here | each repository's root | ours |
| **SecondBrain notes** | Discussion, day logs, research, the Charter; they point to the documents above for anything decided or built | the vault | ours |

The order for a new piece: an ADR if it decides something architectural, a spec if it is a feature, an ExecPlan if it
takes several steps; then the build; then CHANGELOG, and ARCHITECTURE.md if the shape moved, in the same pull request.

What MAF also keeps and we do not copy: `docs/features/` (implementation summaries by feature, no template),
`docs/design/` (one design note), `docs/FAQS.md`, and `.github/copilot-instructions.md` (the repository map for
Copilot, which points to each `AGENTS.md` and to the ADR process). Our `AGENTS.md` carries what those would.

## Decisions

| ADR | Title | Status |
|---|---|---|
| [0001](decisions/0001-steward-is-a-maf-harness-agent.md) | Steward is a MAF harness agent; the local stack is its platform | accepted; superseded in part by 0002, 0003 and 0004 |
| [0002](decisions/0002-one-model-for-everything.md) | One model for everything | accepted |
| [0003](decisions/0003-ag-ui-is-the-default-transport.md) | AG-UI is the default transport, Responses the fallback | accepted |
| [0004](decisions/0004-jesster-is-the-center.md) | Jesster is the center; Neiro retired as a gate; Aurora parked | accepted |
| [0005](decisions/0005-automations-are-recipes-run-as-maf-workflows.md) | Automations are recipes run as MAF workflows | accepted; superseded in part by 0009 |
| [0006](decisions/0006-evals-are-versioned-long-runs-at-night.md) | Evals are versioned; long runs at night as eval workflows | accepted; superseded in part by 0009 and 0012 |
| [0007](decisions/0007-time-is-stamped-by-jesster.md) | Every turn's time is stamped by Jesster | accepted |
| [0008](decisions/0008-the-flows-shelf.md) | The Flows shelf | accepted; superseded in part by 0009 |
| [0009](decisions/0009-flows-are-ordered-tool-chains-automations-schedule-flows.md) | Flows are ordered tool chains; automations schedule flows | accepted |
| [0010](decisions/0010-notes-are-central-in-jesster.md) | Notes are central in Jesster | accepted |
| [0011](decisions/0011-harness-parity-set.md) | The harness parity set: τ-bench retail and airline, Aider Python second | rejected; superseded by 0012 |
| [0012](decisions/0012-stewards-bar-is-our-own-capability-evals.md) | Steward's bar is our own capability evals (amended 2026-11-05: everything he does lands with its eval case; `evals.py validate` enforces it) | accepted |
| [0013](decisions/0013-a2ui-pilot-plan-card.md) | A2UI pilot: the plan's approval card as an A2UI surface, sent beside its AG-UI interrupt | accepted (pilot scope) |
| [0014](decisions/0014-the-bounds-are-gates-in-code.md) | The bounds are gates in code: refused at the call, and at the plan | accepted |

## Specs

| Spec | Title | Status |
|---|---|---|
| [001](specs/001-capability-evals.md) | Capability evals: what Steward must use, what covers it, and the cases still to write | accepted |

## ExecPlans

The plan of record and its order is [ARCHITECTURE.md](ARCHITECTURE.md), section 6; each multi-step item there has its
ExecPlan here, kept living to [`.agent/PLANS.md`](../.agent/PLANS.md). The index with each plan's state is
[plans/README.md](plans/README.md).

| Plan | Title | Carries out |
|---|---|---|
| [0001](plans/0001-capability-evals-build.md) | Build Steward's capability evals: one small case for every capability, in tiers T2, T3 and T4 | ADR-0012, spec 001 |
| [0002](plans/0002-flows-steward-card-and-automation-save.md) | Let Steward build flows and automations from the Flows shelf, on the operator's card | ADR-0008, ADR-0009 |
| [0003](plans/0003-ag-ui-step-3.md) | AG-UI step 3: show Steward's workflow steps live in the Agent tab's console and the Phone view | ADR-0003 |
| [0004](plans/0004-a2ui-pilot-plan-card.md) | A2UI pilot: draw Steward's plan card from an A2UI surface he sends | ADR-0013 |

Steward's own guides stay beside his code: `harness/steward/README.md` (the harness, step by step) and
`harness/steward/evals/README.md` (the eval sets).
