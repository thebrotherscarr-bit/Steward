---
name: automations
description: What SecondBrain's flows and automations are (ADR-0009; a flow is an ordered chain of steps from a fixed list, with a summarize prompt and deliver, and an automation is a saved flow, when, and on or off), the operator's Startup and eval flows as worked examples, and how to propose a new or changed one. Use when the user asks about his automations, a scheduled run, the daily what-happened, an eval flow, or asks you to make, change or explain an automation; and when a turn's first line is "[from an automation (<name>)]".
---

## Usage

A **flow** is an ordered chain of steps from the fixed list below, made on the Flows shelf's canvas ("+ New flow")
and saved by itself. An **automation** is `{flow, when, on/off}` and nothing else, made in the Flows shelf's Set up
(ADR-0009; both kept in the vault's `.secondbrain/schedules.json`). There is no open-ended prompt type: the operator,
2026-11-05, "open ended prompt, nah. a flow thats gonna just work that doesnt need gates, yea." SecondBrain keeps only
the clock: at an automation's time (or on Run now) it hands the flow to your MCP host's
`run_recipe`, where it runs as a MAF workflow (`step04_production_ready/recipe_workflow.py`: one executor per step,
then summarize, then deliver, checkpointed, its events in `storage/recipes/<run_id>.jsonl`), and reads `recipe_status`
until it is done. The result is filed as a note (tag `automation`) with one short line to Telegram. It is not a chat
with you: the summarize step is a tool-less run in a session of its own, and your daytime conversations and their
context are never touched.

### The flow (the data, a recipe)

```json
{
  "name": "Startup",
  "when": "weekdays 06:00",
  "prompt": "the operator's own words for it",
  "steps": ["pull_ff", "versions", "repo_log", "merged_prs", "releases", "eval_bars", "plan_left"],
  "summarize": "Write the daily what-happened from this: a short plain summary, under 300 words.",
  "deliver": ["note", "telegram"]
}
```

- `when` (the automation's, set in Set up): `daily 08:30`, `weekdays 08:30`, `weekly mon 09:00`, `every 3h`,
  `every 30m` or `once 2026-10-23 09:00`. A flow with none runs only on Run now.
- `steps`: in order, only from the list below. A step is its name, or `{"step": name, ...its arguments}`.
- `summarize` (optional): the one turn to you, given everything the steps gathered. Without it the gathered text
  is the result.
- `deliver`: `note` and/or `telegram`.

### The steps (the only ones there are)

| Step | What it reads or does |
|---|---|
| `repo_log` | each Estate repository's commits on main since the last run (`git log main --first-parent`) |
| `merged_prs` | each repository's pull requests merged since then (`gh pr list --state merged`) |
| `releases` | Jesster's and Atlas's releases since then (`gh release list`) |
| `eval_bars` | the newest eval runs' result lines (`storage/evals/runs/<tag>/progress.txt`) |
| `versions` | each repository's branch, HEAD, origin/main, how far behind and ahead, and clean (as `secondbrain_estate_status` shows them) |
| `plan_left` | the working path of the plan (`WHATS_LEFT.md`, "Today's working path") |
| `pull_ff` | brings each repository current: `git pull --ff-only` of main, only on main with a clean work tree, and never the ground while a Manjuel sitting is open (RULE 9); anything else is listed "not pulled: why" and left alone |
| `eval_start` | `{"step": "eval_start", "sets": [...], "runs": 1}`: starts eval sets, as `secondbrain_eval_start` does |
| `eval_wait` | `{"step": "eval_wait", "hours": 8}`: waits for the started run's "BAR DONE" (8 hours at most), then goes on |

Every step but `pull_ff` and `eval_start` only reads, and those two are made safe in their own code. No step raises
a card: a flow runs unattended by design, because the flow the operator built, saved and scheduled is his approved
plan (ADR-0009). In chat it is different: there `secondbrain_eval_start` is planned and carded (the `bar-runner`
skill).

### The two the operator has

1. **Startup** (his, weekdays 06:00): the flow above, his prompt kept. It is the baseline: copy its shape. Its
   `pull_ff` step is the safe pull behind "bring all repos current".
2. **An eval flow** (run whenever he says; for example an automation at 23:00): `{"name": "Nightly aider-py", "when": "daily 23:00", "steps": [{"step":
   "eval_start", "sets": ["aider-py"], "runs": 1}, {"step": "eval_wait", "hours": 8}], "deliver": ["note",
   "telegram"]}`. An optional second for `bfcl` has the same shape. No `summarize`: the progress lines are the result.

### When a turn says "[from an automation (<name>)]" (legacy)

Only prompt-only schedules saved before 2026-11-05 still send such a turn; SecondBrain shows them as "legacy: convert
to a flow". The steps have already run and their text is in the message. Answer in words from it, as its `summarize` asks:
short and plain, no plan, no tool that changes anything. Say what is missing rather than guessing.

### Making or changing one

Saving a new or changed automation needs the operator's request and his card. There is no tool for you to save one
yet, so when he asks: write the recipe in the shape above, only with steps from the list, show it to him in words,
and say he can make it with "+ New flow" on the Flows shelf and schedule it in Set up. Never edit `schedules.json` yourself.

Rules:
- An automation never approves its own card. A card raised from one waits on the operator (the window, the
  Approvals shelf, Telegram) and is answered No after 10 minutes.
- His personal use comes first: an automation that starts an eval is skipped while you are working on a request
  ("skipped: Steward busy").
- Evals run whenever the operator says, day or night (ADR-0009): there is no night-only rule.
