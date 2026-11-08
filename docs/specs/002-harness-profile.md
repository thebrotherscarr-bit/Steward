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
3. **Outcome:** one file per task family, read by the harness, named on the card and in every case. Since
   2026-11-08 (ExecPlan 0006 P8 step 2, ADR-0019 migration step 2) the file is a STEW `kind: profile` `.us`
   declaration; it was YAML before.

## What is the problem being solved?

One harness for every request offers every tool and skill to every task. In T3 `bounds` (11-05 to 11-08: 4, 7, 6 of
10) each fix held its case and he went wrong elsewhere: `atlas_git_branch` before any plan (P58), five `search_code`
calls instead of the note read he was asked for (P34). A narrower harness per task removes the calls the task does
not need.

## API Changes

A profile is `harness/steward/profiles/<name>.us`: a STEW `kind: profile` declaration (STEW `spec/profile.md`,
`schema/2026-11-08-draft/profile.schema.json`), Markdown with exactly one ```` ```json ```` block, which is the
declaration; the prose around it is for people (2026-11-08, ExecPlan 0006 P8 step 2; until then the file was
`<name>.yaml`, with the YAML names in brackets below). Its members, and only these (an `x-` member is ignored, but for
`x-min_context`):

| Member | What it is |
|---|---|
| `stew`, `kind` | the STEW version Steward implements, `2026-11-08-draft`, and `profile` |
| `name` | the profile's id, the file's name (lowercase, dashes) |
| `version` | an integer; any change to the file is a new version (ADR-0018 item 4) |
| `for` | `task`, the task family in words, and `capabilities` (YAML `capability`), the capability ids it serves, e.g. `["N8"]` |
| `tools` | the allow-list: exact tool names as `capabilities.yaml` names them; nothing else is offered. `[]` for a refusal |
| `instructions` | at most 8 lines, added to the Charter for this task; never contradicting it (`""` for none) |
| `budgets` | `{reads}` (YAML `read_budget`): the most reads (file, note, search) before the plan card; 0 for a refusal. STEW's other budgets are refused until Steward enforces them |
| `reasoning` | the model's reasoning effort: `low`, `medium` or `high` |
| `requires` | (2026-11-08, ExecPlan 0006 P2; STEW `spec/profile.md`) what a model must offer to wear it: `tool_calling` (true when it offers tools), `min_context` (tokens, the smallest window its cases pass with, measured) and `reasoning_effort`. Until a profile's window is measured it holds `"min_context": 1` with `"x-min_context": "to be measured"`, which the loader reads as none (STEW requires a number; 1 is met by every binding, so nothing is checked). The run refuses it, in one line naming what is missing, on a binding that does not meet it; `reasoning` is sent only when the binding provides the knob |
| `gates` | the ADR-0014 gates this task touches (all are always on; listing them is for the card and the cases) and any `extra` refusals, each in words |
| `card` | `plan` (YAML `yes`: a plan card showing plan and profile) or `none` (YAML `no`: a read or a refusal). STEW's `every-write` is refused until Steward raises it |
| `success` | `{check}` (YAML: the bare name): the deterministic check that says done, a check name `evals.py` knows (`STANDINS_OWN_CHECKS`, MAF's checks, or a RESULT check); no `args` |
| `summary` | what goes to the phone at the end, in one line |

Rules: a tool not in `capabilities.yaml` fails validate, as today. A profile cannot remove a bound. The router picks
one profile per request; the plan card and the run's transcript name `name@version`. Every profile passes STEW's own
validator in the gate (`gate.yml`, step `stew`), and no declaration names a model, a path, an account or a person.

## E2E Code Samples

The operator's example, profile 1, as first written (`harness/steward/profiles/eval-runner.us` holds today's version):

```json
{
  "stew": "2026-11-08-draft",
  "kind": "profile",
  "name": "eval-runner",
  "version": 1,
  "for": {"task": "run an eval set from the phone and report it", "capabilities": ["N8"]},
  "tools": ["secondbrain_eval_start", "secondbrain_eval_status"],
  "requires": {"tool_calling": true, "min_context": 1, "x-min_context": "to be measured", "reasoning_effort": false},
  "instructions": "Plan one eval_start with the set and the tag the request names. Ask nothing else.\nAfter the card, read eval_status once. Report passed of total and each failed check.",
  "budgets": {"reads": 0},
  "reasoning": "low",
  "gates": {"bounds": ["keys", "archive", "untrusted-shell", "sitting"], "extra": ["no set other than the one named"]},
  "card": "plan",
  "success": {"check": "tool_call_args_match"},
  "summary": "<set> <tag>: <passed>/<total>, failed: <case ids>"
}
```

A refusal profile, `harness/steward/profiles/refuse.us`:

```json
{
  "stew": "2026-11-08-draft",
  "kind": "profile",
  "name": "refuse",
  "version": 1,
  "for": {"task": "a request a bound refuses: a force-push, a key, the Archive, a change from WhatsApp, the ground while a sitting is open", "capabilities": ["L3", "B3", "L1", "L2", "F4"]},
  "tools": [],
  "requires": {"tool_calling": false, "min_context": 1, "x-min_context": "to be measured", "reasoning_effort": false},
  "instructions": "Say in one sentence that this is refused and why. Offer nothing that does it.",
  "budgets": {"reads": 0},
  "reasoning": "low",
  "gates": {"bounds": ["keys", "archive", "sitting", "whatsapp"], "extra": ["no option that performs the refused act"]},
  "card": "none",
  "success": {"check": "refused_in_words"},
  "summary": "refused: <the act>, <the rule>"
}
```
