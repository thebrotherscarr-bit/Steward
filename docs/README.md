# Docs

The design of the whole Estate lives here.

- [ARCHITECTURE.md](ARCHITECTURE.md): the one design document: the parts, the wires (ports and protocols), the data
  each part keeps, how a request, an automation and an eval flow, the rules, and the build plan ahead.
- [decisions/](decisions/README.md): the Architectural Decision Records, in MAF's own format (MADR, with MAF's
  `adr-template.md` and `adr-short-template.md`). Every architectural change gets an ADR before it is built, and
  ARCHITECTURE.md is updated in the same pull request when a decision changes the shape.

## Decisions

| ADR | Title | Status |
|---|---|---|
| [0001](decisions/0001-steward-is-a-maf-harness-agent.md) | Steward is a MAF harness agent; the local stack is its platform | accepted; superseded in part by 0004 |
| [0002](decisions/0002-one-model-for-everything.md) | One model for everything | accepted |
| [0003](decisions/0003-ag-ui-is-the-default-transport.md) | AG-UI is the default transport, Responses the fallback | accepted |
| [0004](decisions/0004-jesster-is-the-center.md) | Jesster is the center; Neiro retired as a gate; Aurora parked | accepted |
| [0005](decisions/0005-automations-are-recipes-run-as-maf-workflows.md) | Automations are recipes run as MAF workflows | accepted |
| [0006](decisions/0006-evals-are-versioned-long-runs-at-night.md) | Evals are versioned; long runs at night as eval workflows | accepted |
| [0007](decisions/0007-time-is-stamped-by-jesster.md) | Every turn's time is stamped by Jesster | accepted |
| [0008](decisions/0008-the-flows-shelf.md) | The Flows shelf | accepted |

Steward's own guides stay beside his code: `harness/steward/README.md` (the harness, step by step) and
`harness/steward/evals/README.md` (the eval sets).
