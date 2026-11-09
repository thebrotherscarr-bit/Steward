---
status: accepted
contact: Kyle
date: 2026-11-05
deciders: Kyle
---

# Steward's bar is our own capability evals

> 2026-11-05: supersedes [ADR-0011](0011-harness-parity-set.md) (the harness parity set, rejected the same day), and
> amends [ADR-0006](0006-evals-are-versioned-long-runs-at-night.md) in part: what a tier holds and what its bar is.
> ADR-0006's versioned sets, its tiers' order and its `ext` sets stand.
>
> Amended 2026-11-05, on the operator's word: "all modules and skills, any capabilities always come with an eval
> set for testing. Everything Steward does has an eval, and he can prove himself." A new
> module, skill, tool or capability lands with its eval case(s) in the same pull request. The wire: the capability
> map is data (`harness/steward/evals/capabilities.yaml`, spec 001's ids in its order), every eval case names its
> capability ids (`capability:`), and `evals.py validate` (the gate's `evals` step) goes red for an id the map does
> not list, a case that names none, a capability marked `required` that no case names, a skill folder or a tool of
> Steward's that the map does not name, and a map whose ids are not spec 001's. A capability with no case that is
> not yet required is counted as untested, a warning. The first ten cases (spec 001's first ten) are
> `t3-bounds.yaml` v1, and their capabilities are required.
>
> Amended in part 2026-11-08 by [ADR-0018](0018-harness-profiles-per-task-tuned-by-evals.md): every eval case also
> names the harness profile it runs under (`profile:`, [spec 003](../specs/003-eval-case-names-its-profile.md)), and a
> profile's cases are its eval. Everything else here stands.

## Context and Problem Statement

[ADR-0011](0011-harness-parity-set.md) proposed an outside parity set (τ-bench retail and airline, Aider's Python
exercises second) so that Steward's score beside a published gpt-oss-20b number would read as the harness's
difference. Having read it, the operator ruled, 2026-11-05:

> "ok, so that all seems kind of useless for our system then, seeing as our evals are literally "can he do what is
> needed for the system reliably" therefore, we need to make custom evals to make sure steward is using everything as
> expected within our harness."

Steward's evals so far are T0 (regression: small, steps, direct) and T1 (held out), both met, plus the `ext`
_(2026-11-08: "T0 met" holds for `small` and `steps`; T0's `direct` (t0-direct v1) has never been run, so T0 as a
whole is not yet met. Its first run is planned with cards, judgment and aider-py.)_
calibration sets (BFCL, Aider Python). They measure the plan-and-card workflow on sample projects. Most of what the
Charter, [ARCHITECTURE.md](../ARCHITECTURE.md) and the ADRs ask him to use (the Estate's tools, the door, the notes,
the source rules, the skills, memory, the team, the bounds) has no eval case at all. What is Steward's bar, and how
is it built so that it answers the operator's question?

## Decision Drivers

- The operator's question, word for word: "can he do what is needed for the system reliably", "within our harness".
- The standing rule for evals: small todos with fast deterministic checks; no long or repeated model evals; one run
  per case on a gating tier (a flip is a harness defect, not noise).
- MAF as it ships: `evaluate_agent` with `LocalEvaluator`, MAF's own checks (`tool_called_check`, `keyword_check`,
  `tool_calls_present`, `tool_call_args_match` with `ExpectedToolCall`) and `@evaluator` functions
  (`agent_framework/_evaluation.py`, 1.24); no hosted judge (RULE 4).
- The harness, not the model: a failing case is fixed in the task, the context, the tools or the check.
- Name the wire: a capability with no case is a capability nothing goes red on.

## Considered Options

- Our own capability evals: one small deterministic case per capability Steward must use, inside our harness
- An outside parity set as the bar (ADR-0011: τ-bench, Aider Python)
- Model-judged scenario evals (a model scores long Estate scenarios)
- Keep the bar as T0 and T1 only, and add cases only from recorded failures

## Decision Outcome

Chosen option: "Our own capability evals", because it is the only option that answers the operator's question
directly: each case asks whether Steward uses one thing the system needs, in the harness he runs in, and its check is
a fact the run left (a tool called, a card raised, a rule kept, a file's state), not a model's opinion.

- **The bar is "can he do what is needed for the system reliably, inside our harness".** It is measured capability by
  capability, not by an outside score.
- **One small deterministic case per capability.** Each case is one ask, run once through Steward's workflow, scored
  by MAF's `evaluate_agent` with `LocalEvaluator`: MAF's checks (`tool_called_check`, `keyword_check`,
  `ExpectedToolCall` scored by `tool_call_args_match`) and our `@evaluator` functions over the conversation and the
  disk (the tool was called with the right arguments, the card was raised and its answer honoured, a rule was kept, a
  file is as it should be). No model judge, no long runs, no repetitions on a gating tier.
- **The capabilities come from the record**: the Charter (the SecondBrain note `steward-charter`),
  [ARCHITECTURE.md](../ARCHITECTURE.md) and the ADRs. They are listed, each with its source, in the coverage map,
  [spec 001](../specs/001-capability-evals.md), which says for each one which existing case covers it (covered, partly,
  untested) and proposes a case for every gap. A change to the Charter, the architecture or an ADR that adds or moves a
  capability updates the map in the same pull request.
- **Grouped into the dev-path tiers** (ADR-0006, and the SecondBrain note
  `steward-s-dev-path-evals-that-grow-with--cb3211`): T0 regression and T1 held out (both met; _2026-11-08: T0's
  small and steps, `direct` never run yet_), T2 his own work in his
  repository, T3 Estate operations (with the source rules and the safety bounds), T4 GitHub, then T5 (still to be
  restated now that Neiro is retired), T6 Estate iteration, T7 generalist.
- **A tier's bar is all of its cases passing, twice in a row**, which is how T0 and T1 were met (T1 at v2: 5/5 and
  24/24, twice). It applies to every capability tier from T2. The bars already recorded for T0 and T1's current set
  versions are not changed here.
- **Outside sets stay tier `ext`, calibration only**: BFCL and Aider Python are never a gate and never tuned on, as
  ADR-0006 recorded. The parity reading ADR-0011 proposed is not built.

### Consequences

- Good, because every capability the system relies on gets a case that goes red when he stops using it right, which
  is what "reliably" means here.
- Good, because the checks are model-free and the cases are one run each, so a tier runs in minutes and a result
  compares across set versions.
- Good, because the map shows the gaps in one place, ordered by the harm a wrong use would do the operator.
- Bad, because many capabilities (the Estate's cards, the door, note writes) are not offered to the eval build today
  (`test_an_eval_build_gets_only_the_estates_reads`, `test_an_eval_never_reaches_the_users_door_or_writes_his_notes`);
  their cases need declaration-only stand-ins in the eval build (MAF `FunctionTool` with no function, as
  `ext_sets.py` already offers BFCL's functions), whose cards are denied. That is a build item.
- Bad, because a case per capability is more cases to keep: each change to one is a new set version (ADR-0006).
- Neutral: a check that the run "named the right thing" is a keyword check, deterministic but narrow; where a tool's
  result exists, the check compares the reply to that result instead.

## Validation

- The coverage map, [spec 001](../specs/001-capability-evals.md), lists every capability with its source and its
  coverage.
- A tier's bar is read by `evals.py bar <set>` from the history, as today.
- Proposed with the first capability set (not built here): each case names the capability id it covers, and
  `evals.py validate` refuses an id the map does not list, so the map and the sets cannot drift apart unseen.

## Pros and Cons of the Options

### Our own capability evals

- Good, because it measures exactly what the operator asked: whether Steward uses what the system needs.
- Good, because MAF ships every piece it needs (`evaluate_agent`, `LocalEvaluator`, its checks, `@evaluator`).
- Bad, because the eval build needs stand-ins for the tools it does not offer today.

### An outside parity set as the bar (ADR-0011)

- Good, because a published number gives an outside reference.
- Bad, because it measures retail and airline tasks, not his system: the operator, 2026-11-05, "useless for our
  system".
- Bad, because a run is hours of GPU time and its simulator is the same model.

### Model-judged scenario evals

- Good, because a scenario can cover several capabilities at once.
- Bad, because a model judge is not deterministic and needs a second model or a hosted one (ADR-0002, RULE 4).
- Bad, because the runs are long, against the standing rule.

### Keep T0 and T1 only, and add cases only from failures

- Good, because every case answers a failure that happened.
- Bad, because a capability never exercised never fails in the record, so it is never tested; most of the Charter
  would stay untested.

## More Information

- Rejected: [ADR-0011](0011-harness-parity-set.md), kept as written with its status `rejected`.
- Amended in part: [ADR-0006](0006-evals-are-versioned-long-runs-at-night.md). What changes: a tier holds one case per
  capability of the map, written from the map before any failure (error analysis still adds cases for failures that
  recur, as the evals README says), and the bar of every capability tier is all of its cases, twice in a row. What
  stands: versioned set files, their validator and fingerprints, the tiers' order, one run per case on a gating tier,
  and `ext` sets as calibration only.
- The coverage map and the proposed cases: [spec 001](../specs/001-capability-evals.md).
- Revisit when a tier's cases are all written and its bar is met: the next reach the dev path names is unlocked then.
- 2026-11-08: a capability case that fails is reviewed from its transcript (`storage/evals/runs/<tag>/cases/<case
  id>.jsonl`: his reasoning, every call with its arguments and result, each card and its answer, his reply), before
  any fix is named; `run-bar.ps1 -Cases` reruns only the failing cases for that review, never as a bar run.
- 2026-11-09: a call no result came back for, and no card, is read by the checks as not run (`evals._run_calls`).
  Evidence: `storage/evals/runs/night-1109-bars/cases/p1_denied_plan.jsonl`, where EXPLORE's last call, `run_shell`,
  came after the reading budget was spent, MAF's function loop returned it unrun, and `plan_card_first` failed on it.
  Held by `test_a_call_no_result_came_back_for_ran_nothing_and_is_no_change_before_the_plan_card`.
