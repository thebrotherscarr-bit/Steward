---
status: accepted
contact: Kyle
date: 2026-11-08
deciders: Kyle
---

# The operation: one milestone, one profile

## What is the goal of this feature?

[ADR-0018](../decisions/0018-harness-profiles-per-task-tuned-by-evals.md): each operation of
[ADR-0016](../decisions/0016-steward-is-the-brain-of-the-pc.md) is a profile. An operation is how a milestone of
[ExecPlan 0005](../plans/0005-steward-runs-the-pc-from-the-phone.md) is written and accepted.

1. **Value:** each milestone is the same small shape, so it is written once and executed without redesign.
2. **Success metric:** the operation's cases pass twice in a row and its phone test is seen on the phone.
3. **Outcome:** a milestone is done when its four parts are.

## What is the problem being solved?

ExecPlan 0005's milestones each described scope, tools, gates and cases in their own words. With profiles, a
milestone is the profile and the proof of it, and nothing more.

## API Changes

An operation is a short block in ExecPlan 0005 (not a file of its own) with four parts:

| Part | What it is |
|---|---|
| `profile` | the profile's name ([spec 002](002-harness-profile.md)), and its capability ids |
| `tools` | the profile's allow-list, each marked existing or to build (a tool to build lands with its gate test) |
| `cases` | 3 to 5 deterministic cases, each naming the profile ([spec 003](003-eval-case-names-its-profile.md)), in one versioned set |
| `phone` | the acceptance test: what Kyle sends from Telegram and what he sees on the phone |

The operation is done when its set's bar is met (all cases, twice in a row) and the phone test is observed.

## E2E Code Samples

```text
M4a eval-runner
  profile: eval-runner v1 (N8)
  tools:   secondbrain_eval_start (existing), secondbrain_eval_status (existing)
  cases:   "Run the bounds set, tag phone-1" -> eval_start(set=bounds, tag=phone-1) on its card;
           "How did phone-1 do?" -> one eval_status, reply names the pass count, no card;
           "Run every set" -> refused in words, no card (one set per request)
  phone:   send "Run the bounds set, tag phone-1", Approve, get "bounds phone-1: n/10, failed: ..."
```
