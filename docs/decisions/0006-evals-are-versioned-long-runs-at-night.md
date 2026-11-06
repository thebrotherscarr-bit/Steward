---
status: accepted; superseded in part by [ADR-0009](0009-flows-are-ordered-tool-chains-automations-schedule-flows.md) and [ADR-0012](0012-stewards-bar-is-our-own-capability-evals.md)
contact: Kyle
date: 2026-11-05
deciders: Kyle
---

# Evals are versioned; long runs at night as eval workflows

> 2026-11-05: superseded in part by [ADR-0009](0009-flows-are-ordered-tool-chains-automations-schedule-flows.md):
> evals run whenever the operator says, day or night; the night-only rule for long sets is gone. In chat,
> `eval_start` is planned and carded.
>
> 2026-11-05: superseded in part by [ADR-0012](0012-stewards-bar-is-our-own-capability-evals.md): Steward's bar is our
> own capability evals ("can he do what is needed for the system reliably", the operator). A tier now holds one small
> deterministic case per capability of the coverage map ([spec 001](../specs/001-capability-evals.md)), written from
> the map before any failure (error analysis still adds cases for failures that recur), and the bar of every
> capability tier from T2 is all of its cases, twice in a row. What stands: versioned set files, the validator and
> fingerprints, the tiers' order, one run per case on a gating tier, and `ext` sets as calibration only.

## Context and Problem Statement

Steward's evals were cases inside `evals.py`. A check changed between runs, so results did not compare like with
like, and Steward could not grow the cases himself. Long sets (hours of GPU time) also competed with the operator's
own use of Steward by day. How are evals kept, grown and scheduled?

## Decision Drivers

- The operator, 2026-11-05: "Write up a set of evals for him to run that is in-line with the dev path, then set up
  version control for the evals themselves, so he is able to grow the evals as he grows his skill set ... eventually
  a generalist that can essentially run the entire system."
- The operator, 2026-11-05: "I'd rather run the long-runs as overnight evals."
- The operator, 2026-11-05: "we can build workflows for the evals, and then keep him as the general purpose agent for
  personal use during the day."
- One run per case on a gating tier (his rule): a result that flips between runs is a harness defect, not noise.
- MAF-native: `evaluate_agent` / `evaluate_workflow` with `LocalEvaluator`; FoundryEvals is hosted and out (RULE 4).
  _(2026-11-05: `evaluate_workflow` is not called yet. Evals use `evaluate_agent` with `LocalEvaluator`, the steps set
  a `LocalEvaluator` per step; recipe runs are not evaluated until the Flows shelf's piece 5.)_

## Considered Options

- Versioned set files in Steward's repo, tiered along the dev path, gating tiers run once per case; long sets as
  night automations.
- Cases kept in code, run by hand when needed.

## Decision Outcome

Chosen option: "Versioned set files, tiered, long sets at night", because it makes results comparable across
versions, lets Steward add cases by pull request, and keeps the GPU his by day.

- **Versioned sets** (Steward #139): one `<tier>-<name>.yaml` per set in `harness/steward/evals/`, with version, tier,
  owner, runner, split, bar, changes and cases. A set changes only by pull request; its version goes up on any change
  to a case or a check. `evals.py validate` (in the gate) refuses a bad schema, an unknown check, a case with no
  result check, a precondition the fixture already meets, and cases that differ from their version's fingerprint in
  `baselines.json`. Every history line carries the set name and version.
- **Tiers** (the dev path): T0 regression (frozen; the bar was met 2026-11-05, 01:32), T1 held out (met at v2:
  5/5, 24/24 twice), then T2 real work in his repo, T3 Estate operations, T4 GitHub, T5 the (former) Neiro lock, T6
  Estate iteration, T7 generalist. Each bar unlocks the next reach; earlier tiers stay as regression gates.
- **ext sets** (Steward #143): ext-bfcl v1 (80 BFCL cases, Apache-2.0) and ext-aider-py v1 (20 Aider/Exercism Python
  exercises, MIT), pinned with their licenses, calibration only and never a gate.
- **Long runs at night, as eval workflows:** a nightly eval is a recipe ([ADR-0005](0005-automations-are-recipes-run-as-maf-workflows.md))
  of `eval_start` then `eval_wait`, scheduled by the operator in Settings (for example aider-py `daily 23:00`).
  Only one eval runs at a time. By day, Steward is the operator's.

### Consequences

- Good, because a bar is always measured against a named set version.
- Good, because Steward's `eval-author` work grows the sets from failures (label, count, then write the case).
- Bad, because every change to a case means a new version and a new fingerprint to record.
- Neutral: with T5 written against the Neiro lock, that tier needs restating now that Neiro is retired
  ([ADR-0004](0004-jesster-is-the-center.md)); not yet done.

## Validation

`evals.py validate` runs in the gate; `evals.py bar <set>` says whether a bar is met; `run-bar.ps1` runs a bar in its
own window.

## More Information

- `harness/steward/evals/README.md`; the SecondBrain note `steward-s-dev-path-evals-that-grow-with--cb3211`.
- Open (in the record): whether `plan_step` scores only the plan that reached the card. The dev-path note lists it
  as a T0 scoring change; the overnight note (run 20) leaves it for the operator's word.
