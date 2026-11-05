# Architectural Decision Records (ADRs)

An Architectural Decision (AD) is a justified design choice that addresses a functional or non-functional
requirement that is architecturally significant. An Architectural Decision Record (ADR) captures a single AD and its
rationale. See <https://adr.github.io/>.

This folder follows Microsoft Agent Framework's own practice: its `docs/decisions/` folder, MADR-style records, and
its two templates, copied here unchanged from
[microsoft/agent-framework `docs/decisions/`](https://github.com/microsoft/agent-framework/tree/main/docs/decisions)
(`adr-template.md` and `adr-short-template.md`, as of commit `feed6f4`; MIT, Copyright (c) Microsoft Corporation).
MAF's contributor instructions say: "when proposing architectural changes, create an ADR to capture options
considered and the decision rationale".

## The standard, from 2026-11-05

The operator's ruling, 2026-11-05: "make this the standard moving forward, this way nothing gets misaligned."

- **Every architectural change gets an ADR before it is built.** A change is architectural when it adds, removes or
  moves a part of the Estate, a wire between parts (a port, a protocol, a transport), a store of data, or a rule
  about who decides what.
- **`docs/ARCHITECTURE.md` is updated in the same pull request** whenever a decision changes the shape it describes.
- **Nothing is deleted.** A decision that is replaced is marked `superseded by [ADR-NNNN](...)`, with a dated line
  saying what changed; the new ADR says what it supersedes.
- Stale documents elsewhere (other repositories' READMEs, the ground's SPEC.md, SecondBrain notes) are annotated with
  a dated pointer here, never rewritten.

## Adding one

1. Copy `adr-template.md` (or the short form, `adr-short-template.md`) to `NNNN-title-with-dashes.md`, where `NNNN`
   is the next number. Check open pull requests so two ADRs do not take the same number.
2. Fill in the frontmatter:
   - `status`: `proposed` at first; `accepted` once the operator has agreed it, with `date` updated to that day.
   - `contact`: Kyle (the work is his; no hand or agent puts its own name on it).
   - `deciders`: Kyle. He is the only decider.
   - `consulted` and `informed`: optional.
3. Fill in the sections: Context and Problem Statement, Decision Drivers, Considered Options, Decision Outcome,
   Consequences. Quote the operator's own words and their date for every ruling. List the good, neutral and bad of
   each option; long investigations go under More Information or in a linked SecondBrain note.
4. Open one pull request with the ADR (and the ARCHITECTURE.md change, if any). It lands when its checks pass and the
   operator has agreed; acceptance is his word, recorded in the ADR's status and date.
5. Add the ADR to the index below and to `docs/README.md`.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-steward-is-a-maf-harness-agent.md) | Steward is a MAF harness agent; the local stack is its platform | accepted; superseded in part by 0004 |
| [0002](0002-one-model-for-everything.md) | One model for everything | accepted |
| [0003](0003-ag-ui-is-the-default-transport.md) | AG-UI is the default transport, Responses the fallback | accepted |
| [0004](0004-jesster-is-the-center.md) | Jesster is the center; Neiro retired as a gate; Aurora parked | accepted |
| [0005](0005-automations-are-recipes-run-as-maf-workflows.md) | Automations are recipes run as MAF workflows | accepted |
| [0006](0006-evals-are-versioned-long-runs-at-night.md) | Evals are versioned; long runs at night as eval workflows | accepted |
| [0007](0007-time-is-stamped-by-jesster.md) | Every turn's time is stamped by Jesster | accepted |
| [0008](0008-the-flows-shelf.md) | The Flows shelf | accepted |
