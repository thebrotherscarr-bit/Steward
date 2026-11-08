---
status: accepted
contact: Kyle
date: 2026-11-08
deciders: Kyle
---

# The harness profile: one small file per task family

## What is the goal of this feature?

The operator, 2026-11-08: "write up the simplest formats we can at the start, set the plan in stone, and then
execute", and at run time "here is a plan and the harness needed for this agent".
[ADR-0018](../decisions/0018-harness-profiles-per-task-tuned-by-evals.md) makes a harness profile the unit of
harnessing.

1. **Value:** for each task family, Steward runs with only the tools, instructions and budget that task needs, and the
   operator sees and approves that harness on the plan card.
2. **Success metric:** every case of a profile passes with the profile applied, and the profile's tier bar is met.
3. **Outcome:** one YAML file per task family, read by the harness, named on the card and in every case.

## What is the problem being solved?

One harness for every request offers every tool and skill to every task. In T3 `bounds` (11-05 to 11-08: 4, 7, 6 of
10) each fix held its case and he went wrong elsewhere: `atlas_git_branch` before any plan (P58), five `search_code`
calls instead of the note read he was asked for (P34). A narrower harness per task removes the calls the task does
not need.

## API Changes

A profile is `harness/steward/profiles/<name>.yaml`. Its fields, and only these:

| Field | What it is |
|---|---|
| `name` | the profile's id, the file's name (lowercase, dashes) |
| `version` | an integer; any change to the file is a new version (ADR-0018 item 4) |
| `for` | the task family in words, and the capability ids it serves, e.g. `[N8]` |
| `tools` | the allow-list: exact tool names as `capabilities.yaml` names them; nothing else is offered. `[]` for a refusal |
| `instructions` | at most 8 lines, added to the Charter for this task; never contradicting it |
| `read_budget` | the most reads (file, note, search) before the plan card; 0 for a refusal |
| `reasoning` | gpt-oss's reasoning effort: `low`, `medium` or `high` |
| `requires` | (2026-11-08, ExecPlan 0006 P2; STEW `spec/profile.md`) what a model must offer to wear it: `tool_calling` (true when it offers tools), `min_context` (tokens; `null` until measured, the smallest window its cases pass with) and `reasoning_effort`. The run refuses it, in one line naming what is missing, on a binding that does not meet it; `reasoning` is sent only when the binding provides the knob |
| `gates` | the ADR-0014 gates this task touches (all are always on; listing them is for the card and the cases) and any `extra` refusals, each in words |
| `card` | `yes` (a plan card showing plan and profile) or `no` (a read or a refusal) |
| `success` | the deterministic check that says done: a check name `evals.py` knows (`STANDINS_OWN_CHECKS`, MAF's checks, or a RESULT check) |
| `summary` | what goes to the phone at the end, in one line |

Rules: a tool not in `capabilities.yaml` fails validate, as today. A profile cannot remove a bound. The router picks
one profile per request; the plan card and the run's transcript name `name@version`.

## E2E Code Samples

The operator's example, profile 1, `harness/steward/profiles/eval-runner.yaml`:

```yaml
name: eval-runner
version: 1
for: {task: "run an eval set from the phone and report it", capability: [N8]}
tools: [secondbrain_eval_start, secondbrain_eval_status]
instructions: |
  Plan one eval_start with the set and the tag the request names. Ask nothing else.
  After the card, read eval_status once. Report passed of total and each failed check.
read_budget: 0
reasoning: low
gates: {bounds: [keys, archive, untrusted-shell, sitting], extra: ["no set other than the one named"]}
card: yes
success: tool_call_args_match
summary: "<set> <tag>: <passed>/<total>, failed: <case ids>"
```

A refusal profile, `harness/steward/profiles/refuse.yaml`:

```yaml
name: refuse
version: 1
for: {task: "a request a bound refuses: force-push, a key, the Archive, a change from WhatsApp, the ground while a sitting is open", capability: [L3, B3, L1, L2, F4]}
tools: []
instructions: |
  Say in one sentence that this is refused and why. Offer nothing that does it.
read_budget: 0
reasoning: low
gates: {bounds: [keys, archive, sitting, whatsapp], extra: ["no option that performs the refused act"]}
card: no
success: refused_in_words
summary: "refused: <the act>, <the rule>"
```
