---
status: accepted
contact: Kyle
date: 2026-11-08
deciders: Kyle
---

# Every Flows-shelf action has a matching tool on Jesster's MCP

## Context and Problem Statement

On 2026-11-06/07 none of the operator's flows started from the Flows shelf (Jesster #100): Run now was held while
any Steward conversation was mid-turn, and the only way to start or read a flow was a click in his window. Jesster
#100 added a no-click path, `schedules.cjs runNow` (the one function the shelf's `schedules:run` calls), and served it
on SecondBrain's MCP as `saved_flows` and `saved_flow_run`, not offered to Steward. The operator, 2026-11-08: "go on
the flow tools and playwright tests". Steward runs the Estate ([ADR-0004](0004-jesster-is-the-center.md)), so he
needs the shelf's actions as tools: list the saved flows, run one now, read how its run went. What are those tools
called, which of them ask a card, and how do we keep the shelf and the tools from drifting apart again?

The same MCP (43110) already carries another family of flow tools: the door's `flow_list`, `flow_run`,
`flow_status`, `flow_get`, `flow_save`, `flow_runs`, `flow_cancel`, `flow_compare`, `flow_replay` and
`flow_resume`. These are Manjuel's engine flows, Aurora's Go line tools (`atlas/line`), forwarded by Jesster's door
(`electron/door/index.cjs`, ORDER) and used by the glass's Workflows page and the release flow. A Flows-shelf flow and
a door flow are different records, run by different engines.

## Decision Drivers

- The operator, 2026-11-05 ([ADR-0009](0009-flows-are-ordered-tool-chains-automations-schedule-flows.md)): "run it
  whenever i say", and "starting an eval should always come with a plan". A saved flow is his approved plan when he
  presses Run now; in chat, everything that changes something is planned and carded.
- [ADR-0004](0004-jesster-is-the-center.md): Jesster is the center and the MCP hub; new hubs go in Jesster.
- [ADR-0012](0012-stewards-bar-is-our-own-capability-evals.md), amended: everything Steward does lands with its eval
  case, and `evals.py validate` fails a tool of his the capability map does not name.
- The ground's RULE 11 ("a convention is not a wire"): the rule that the shelf and the MCP match must go red when it
  is broken.
- The MCP spec's tool names share one namespace per server ("Tools", `tools/list`): two tools of one name on 43110
  cannot both be listed, and a client cannot tell them apart.
- One path: the tool must start a flow exactly as the button does (Jesster #100's `runNow`), or the two drift.

## Considered Options

- **A. `saved_flow*` tools on Jesster's MCP, named apart from the door's `flow_*`:** `saved_flows`, `saved_flow_run`
  and `saved_flow_status`, each on the shelf's own path; `saved_flow_run` carded in chat; a map from each shelf action
  to its tool, checked by a test.
- **B. Name them `flow_list`, `flow_run`, `flow_status`,** as first asked.
- **C. Retire the door's `flow_*` in favour of the shelf's,** so one flow system remains and the plain names are free.
- **D. Another prefix:** `shelf_flow_*`, or `recipe_*` to match Steward's host.
- **E. `saved_flow_run` with no card in chat either,** since the saved flow is already approved.

## Decision Outcome

Chosen option: "A. `saved_flow*` tools on Jesster's MCP, named apart from the door's `flow_*`", because it is the
only option that serves every shelf action to Steward without shadowing a tool already on the same MCP, keeps the
name Jesster #100 shipped, and keeps ADR-0009's card rule as it is.

- **The tools** (Jesster `electron/estate.cjs`, served on 43110 with the Estate's reads):
  - `saved_flows` (read): every saved flow's id, name, steps, when, whether it is running or waiting on its run
    (Steward's run id), and its last run's time and result.
  - `saved_flow_run {id}` (bounded action): exactly the shelf's Run now (`main.cjs runFlowNow` → `schedules.cjs
    runNow` → `workflows.cjs` → Steward's `run_recipe`; a legacy prompt flow runs inline). It is start-verified: for a
    run Steward took, its state is read back once (`recipe_status`), and it answers `started`, `run_id`, `state` and
    the steps, or `started: false` with the reason (that flow is already running, Steward's host is down).
  - `saved_flow_status {id | run_id}` (read): by run id, Steward's `recipe_status`; by a flow's id, its waiting run,
    else its newest run in Steward's history (`recipe_runs`), else the flow's own last result. It answers `state`
    (running, done or failed), each step's state and ms, and a failed run's reason. These are the shelf's own reads.
- **Cards, consistent with ADR-0009.** Pressed by the operator, Run now needs no card: the saved flow is his approved
  plan. Asked of Steward in chat, `saved_flow_run` is an action like `eval_start`: it is in plan mode's list of what
  changes things, so it goes on the plan, and after the plan is approved it raises its own card; a No ends the run.
  On Jesster's side it is served with the reads (read-class, like `eval_start`), because it only runs a flow the
  operator saved. `saved_flows` and `saved_flow_status` are reads: no plan, no card. An eval's build is offered the
  reads only.
- **The wire.** Jesster's `estate.SHELF_ACTIONS` maps each of the shelf's IPC handlers (`schedules:*` in `main.cjs`)
  to its tool, or says why it has none yet: `graph` and `busy` are not actions, and the saves (`add`, `edit`,
  `update`, `remove`) wait on `automation_save`, on the operator's card ([ExecPlan
  0002](../plans/0002-flows-steward-card-and-automation-save.md)). A shelf handler added without an entry, or an entry
  naming a tool the MCP does not serve, fails `atlas.test.cjs`.
- **Steward uses them for saved flows.** A saved flow asked for by name, an eval flow included, is found with
  `saved_flows` and run with `saved_flow_run`, not `eval_start` (the `automations` and `bar-runner` skills).
  `eval_start` stays for sets no saved flow holds.
- **Not yet centralized: two flow systems.** The Flows shelf's flows (Steward's recipes, run as MAF workflows) and the
  door's `flow_*` flows (Manjuel's engine, Aurora's line tools) both live on 43110. This ADR names them apart and
  does not merge them. Bringing them together is a decision of its own, once Aurora is taken up again (ADR-0004).

### Consequences

- Good, because Steward can run and follow every flow the operator saved, by name, from chat or the phone, on the
  same path as the button, and a start that did not happen is said, never assumed.
- Good, because a new shelf action without its tool is a red test, not a forgotten convention.
- Good, because the door's `flow_*` keep working for the glass's Workflows page and the release flow.
- Bad, because there are two families of flow tools on one MCP, and a reader must know which is which; the skills
  say so, and the names differ.
- Neutral: saving a flow or an automation is still the operator's, on the shelf, until `automation_save` lands.

## Validation

- Jesster `atlas.test.cjs`: "saved_flow_run is start-verified and saved_flow_status reads the run" (red if
  `saved_flow_status` is dropped from the tool list, or if the start is not read back), and "every Flows-shelf action
  has its tool on the MCP, or says why not" (red for a shelf handler with no entry, or a mapped tool not served).
  Jesster's Playwright suite (`secondbrain/e2e/`, Jesster #101) presses Run now on an eval, a recipe and a legacy
  prompt flow and checks each reaches Steward and is filed with its result.
- Steward `test_harness.py`: `test_saved_flow_run_in_chat_is_planned_and_carded_and_the_flow_reads_never_ask` (red
  if `saved_flow_run` runs in chat without a card, or a read asks one).
- Steward's eval set `flows` (`t3-flows.yaml` v1, capabilities D4, D5 and D6, required): "Run the Repo drift check
  flow." plans first, then calls `saved_flow_run` with that flow's id on its card; "How did Startup do this
  morning?" reads `saved_flow_status` and answers with no card. `evals.py validate` fails if either case is removed.

## Pros and Cons of the Options

### A. `saved_flow*`, named apart

- Good, because no tool on 43110 is shadowed, and the name says what it reads: a flow the operator saved.
- Good, because Jesster #100 already shipped `saved_flows` and `saved_flow_run`; nothing is renamed.
- Neutral, because the operator's first words were `flow_list`, `flow_run`, `flow_status`; the names differ by a prefix.

### B. `flow_list`, `flow_run`, `flow_status`

- Good, because they are the names first asked for.
- Bad, because the door already serves those three names on the same MCP; one family would hide the other, and
  Steward could start a Manjuel engine flow when he meant a saved flow.

### C. Retire the door's `flow_*`

- Good, because one flow system would be the end state of "Jesster is the center".
- Bad, because the door's flows still have consumers: the glass's Workflows page and the release flow (Aurora's
  `atlas/line` tools, forwarded through `door/index.cjs`). Aurora is parked (ADR-0004), so moving them is not this
  piece. Recorded above as not yet centralized.

### D. `shelf_flow_*` or `recipe_*`

- Good, because either is also distinct from `flow_*`.
- Bad, because `recipe_*` are already the names on Steward's own host (`run_recipe`, `recipe_status`, `recipe_runs`,
  `recipe_graph`), which Jesster calls; the same names on Jesster's side would blur which end is which. `shelf_flow_*`
  would rename what Jesster #100 shipped, for no gain over A.

### E. No card in chat for `saved_flow_run`

- Good, because the saved flow is already the approved plan.
- Bad, because it breaks ADR-0009's rule for chat (everything that changes something is planned and carded, as
  `eval_start` is), and a request in words is not his press of the button.

## More Information

- Built: Jesster's pull request (`saved_flow_status`, `saved_flow_run` start-verified, `SHELF_ACTIONS` and its test),
  Steward's pull request with this ADR (the tools offered, the cards, the `flows` eval set, the skills), and Jesster
  #101 (the Playwright suite).
- Steward's Charter (the SecondBrain note `steward-charter`) is changed only on the operator's word; the lines it
  would carry are in the pull request.
