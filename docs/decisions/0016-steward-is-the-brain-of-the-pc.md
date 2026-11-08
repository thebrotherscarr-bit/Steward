---
status: accepted
contact: Kyle
date: 2026-11-08
deciders: Kyle
---

# Steward is the brain of the PC: what he runs while Kyle is away

Accepted on the operator's word of 2026-11-08 (quoted below). This record supersedes in part
[ADR-0014](0014-the-bounds-are-gates-in-code.md): its Archive gate, for Steward, gives way to read-only archive tools
(see "The Archive amendment"). Everything else in ADR-0014 stands. It is carried out by
[ExecPlan 0005](../plans/0005-steward-runs-the-pc-from-the-phone.md); its capabilities are N1 to N18 in
[spec 001](../specs/001-capability-evals.md).

2026-11-08: amended in part by [ADR-0018](0018-harness-profiles-per-task-tuned-by-evals.md): each operation of the
table below is a harness profile ([spec 004](../specs/004-operation.md)), and Steward's GitHub write tools come out
of his build now (ExecPlan 0005, M9a). Everything else here stands.

## Context and Problem Statement

The operator, 2026-11-08: "We are building a harness for agents to get them to properly conduct my PC operations
while I am away from my PC." And: "Let's focus hard on getting Steward's agentic capabilities on-line."

The operations, in his words: "Keep the Estate running, Perform research note taking from the phone. Run all evals
and programs from the phone through the agent, review/update all guthub information. Check on progress on agents on
my PC. Look into any archival information or data I may need from my PC, Install apps and run flows as needed.
Cleanup and general tidyness of the system he is an agent of, with approvals and summaries. Basically the brain of
the PC with the ability to essentially run anything as if I am sitting there at the keyboard, at any time."

Today Steward works well only with the operator at the PC: his cards are answered in the Agent tab, a run that fails
is seen on the console, and a host that restarts drops its pending card (the AG-UI host keeps its workflow
checkpoints in `InMemoryCheckpointStorage`, `ag_ui_app.py`). From the phone, Telegram carries cards as buttons and
WhatsApp is chat and research only ([ADR-0014](0014-the-bounds-are-gates-in-code.md) item 5), but no eval shows that
a card answered on the phone continues the run and that the result comes back to the phone, and several of the
operations above have no tool at all (agents' progress, the Archive, installing apps, a tidiness survey).

What must Steward be able to run while Kyle is away, through which tools, behind which gates, and in what order are
they built and trusted?

## Decision Drivers

- His goal, above: the PC run from the phone "as if I am sitting there at the keyboard, at any time".
- The gate is Kyle's (RULE 6, the Charter): every change is his card, now answered on the phone. A card he does not
  answer is a No (Charter, "Where a message comes from").
- The bounds hold in code whatever the model does ([ADR-0014](0014-the-bounds-are-gates-in-code.md)); the harness, not
  the model ([ADR-0002](0002-one-model-for-everything.md)).
- Everything he does has an eval, and he proves himself ([ADR-0012](0012-stewards-bar-is-our-own-capability-evals.md)):
  each operation is a capability family with deterministic cases before it is trusted.
- Unattended means nobody is watching the console: a run never ends silently, a failure reaches the phone, a host
  crash loses nothing that was asked.
- MAF as it ships: its approvals (AG-UI interrupts), workflow checkpoints, function middleware and tool-call limits;
  no mechanism of our own beside them.
- RULE 1 for the hand is unchanged; RULE 1's "the ARCHIVE never goes on github, EVER" is absolute for everyone.
- Local first (RULE 4 as amended 2026-11-04): his own accounts' integrations from this PC, no public server.

## Considered Options

- **A. General screen control now** (Aurora's visible control, SecondBrain's `computer_task` and `screen_look`): he
  drives the desktop as a person would, so any operation is covered at once.
- **B. Tools first, screen later:** each operation is a family of named tools on his cards (host shell on a card, app
  install with winget on a card, process status, read-only archive tools), each with its eval; screen control comes
  after, on the operator's word.
- **C. Keep the hand doing it remotely:** the coding agent working for the operator does the operations when asked,
  and Steward stays at his current reach.

## Decision Outcome

Chosen option: **B, tools first, screen later**, because it is the only option where every operation can be gated in
code, carded on the phone and scored by a deterministic case. "As if at the keyboard" is met first by tools on cards:
the host shell on a card for anything no other tool covers, app install by winget on a card, and a process-status
read. Screen control (option A) is in the "Not now" list below.

### The operations as capability families

The phone path, for every family: **Telegram** carries cards as buttons and gets the summaries; **WhatsApp** is chat
and research only (reads, answers, web), and a change asked there is refused, pointing to Telegram or the PC
(ADR-0014 item 5, unchanged). "Card" means Kyle's approval card, on Telegram when he is away. "Summary" means one short
plain message to Telegram when the run ends, whatever its end: what ran, what changed, what is left.

| # | Operation (his words) | Capability ids | Tools: existing / to build | Gate | Summary to the phone |
|---|---|---|---|---|---|
| 1 | "Keep the Estate running" | N5, N6 | existing: `secondbrain_estate_status`, `secondbrain_estate_logs`, `secondbrain_service_control`, `secondbrain_ollama_unload`, `secondbrain_app_update`; to build: a health flow on a schedule (an `estate_check` step, then notify) | reads: no card; a restart, unload or update: card; the health flow itself: no card (a saved flow is his approved plan, ADR-0009) | the flow notifies only when a part is down, naming it and the restart to ask for; a restart's result is read back and sent |
| 2 | "research note taking from the phone" | N7 | existing: WebResearchAgent, `secondbrain_search_notes`, `secondbrain_read_note`, `secondbrain_write_note`, `secondbrain_append_to_note` | reads and web: no card; a note write: card (Telegram only; from WhatsApp the research is answered in chat and not saved) | the note's id and its first lines, read back after the write |
| 3 | "Run all evals and programs from the phone" | N8, N9, N10 | existing: `secondbrain_eval_start`, `secondbrain_eval_status`, `run_shell`; to build: the Jesster flow tools (list, run, status of a saved flow; their own ADR, in flight) | `eval_start`, a flow run asked in chat, and a program (`run_shell`): card; their status: no card | the eval's pass count and the failed checks; the flow's result per step; the program's exit code and last lines |
| 4 | "review/update all guthub information" | N16, N17 | existing reads: `atlas_git`, `atlas_git_diff`, `atlas_records`, `pr_checks`; to build: issues, releases and branch-drift reads | reads: no card; writes: withheld (see "GitHub: review now, writes later") | the review in a few lines per repository: open PRs, red checks, stale branches, drift from main |
| 5 | "Check on progress on agents on my PC" | N11 | to build: a light read of running evals, flows, background agents, Claude Code and Aider processes, with the tail of each one's log | no card (a read); light: one process listing per call, no CIM or WMI scan, no polling loop | what is running, for how long, and each one's last lines |
| 6 | "Look into any archival information or data I may need" | N12, N13 | to build: read-only archive tools (search and read under `Desktop\Archive`) | reads: no card; every write, copy, shell or publish touching the Archive: refused in code | what was found, with each file's path inside the Archive; never its content copied anywhere but the reply |
| 7 | "Install apps" | N14 | to build: winget search, install and upgrade | search: no card; install and upgrade: card, naming the package id, its source and version | what was installed, its version, and winget's exit code |
| 8 | "run flows as needed" | N9 | as in row 3 | as in row 3 | as in row 3 |
| 9 | "Cleanup and general tidyness ... with approvals and summaries" | N15 | existing: file access reads, `atlas_git` (stale branches); to build: a read-only survey (large and stale files, stale branches, logs, caches) | the survey: no card; each removal: its own card, with its reason and every consumer named ("removal needs a reason, not tidiness"); nothing in a World deleted without his word | what was proposed, what he approved, what was removed and the space freed |
| 10 | "run anything as if I am sitting there at the keyboard, at any time" | N18 | existing: `run_shell` on the host | card, with the command in full on it; the bounds of ADR-0014 still refuse (`.env`, the Archive, the shell after untrusted content, the ground during a sitting) | the command, its exit code and its last lines |

The away loop and the unattended rules (N1 to N4) hold for every row.

### The trust prerequisites

Steward is not trusted with any operation away from the PC until both hold, in this order:

1. **The bounds bar:** T3 `bounds` (`t3-bounds.yaml`, ten cases) passes 10 of 10, twice in a row
   ([ExecPlan 0001](../plans/0001-capability-evals-build.md), Milestone 2; in progress).
2. **The away loop, proved on a live host:** a change asked from Telegram raises its card on the phone; the answer on
   the phone continues the run on the same host; the result reaches the phone. The same for **Deny** (nothing runs,
   the phone is told it ended) and **no answer** (the card times out to a No, the phone is told it ended for lack of
   an answer). Capabilities N1 and N2.

### Unattended robustness

- **Never end silently (N3).** Every run started from the phone, by a flow or by an automation ends with a
  what-happened report to Telegram: what ran, what changed, what is left, and the error when it failed.
- **Failures reach the phone (N3).** A tool error, a refused call, a red check or a stopped run is in that report; it is
  not left on the console.
- **Per-run limits (N4).** MAF's tool-call limits stay as set (`max_function_calls` 40, `max_duration_seconds` 1800 per
  agent run); an unattended run also has a whole-run wall clock and a card wait, after which it ends and says where
  it is and what is left. _(2026-11-08: the card wait is 30 minutes, the operator's ruling: "30 minutes". One value in
  Jesster, `electron/agent/cardwait.cjs`, Jesster #105; ExecPlan 0005's Decision Log.)_
- **Host-crash recovery (N5).** A run whose host dies (or is restarted by Jesster) is resumed from a durable checkpoint
  with its pending card raised again, or reported to the phone as ended. The AG-UI host's checkpoints move from
  `InMemoryCheckpointStorage` to MAF's file checkpoint storage for this.
- **A what-happened report on demand.** "What happened while I was away?" is answered from the record (approvals
  history, the Estate's logs, eval history, flow runs) with no card.

### The Archive amendment (supersedes ADR-0014 in part)

The operator's card choice, 2026-11-08: **"Read-only, no card"**. Steward may search and read `Desktop\Archive`
freely, through dedicated read-only archive tools only, with no card. He never writes there, never copies from it into
a repository, never publishes it, and it never goes on GitHub: the ground's CLAUDE.md RULE 1, "the ARCHIVE never goes
on github, EVER", holds absolutely.

So ADR-0014 changes in two places, for Steward only:

- **Item 2 (at the call)** still refuses an Archive path on every tool but the archive tools: the file tools, the
  shell, the door, note writes and every other write keep refusing it. The archive tools take only paths under
  `ARCHIVE_DIR`, open files read-only, and have no write, copy, move or delete.
- **Item 7 (at the request and the plan)** refuses a request or a plan that would write, copy, move, delete or publish
  anything to or from the Archive; a request only to find or read something there is answered by the archive tools.

What the archive tools return is untrusted content (ADR-0014 item 3): after it, the host shell is shut for the
session. Archive content may be quoted in a reply; it is never written into a note, a file of a repository, a commit,
an eval fixture or a log that leaves the PC. The hand's own access to the Archive stays under RULE 1, unchanged: this
amendment is Steward's and nobody else's. The notes kernel's Archive digger stays retired
([ADR-0010](0010-notes-are-central-in-jesster.md)); the archive tools are Steward's own and keep no index.

### GitHub: review now, writes later

The operator, 2026-11-08: "I'll let you know when I am confident in his ability to keep Github up to date, that can
be part of the evals, when he has passed reliably, he can gain the tools to control github."

- **Review is his now** (N16): pull requests, checks, issues, branches, releases and drift, read and summarized,
  evaluated by T4 read cases.
- **Writes are withheld** (N17) until the operator says so after he passes reliably: no branch, commit, push, pull
  request or merge on GitHub from Steward. Asked for one, he says the hand does it until the operator's word. The
  hand keeps doing GitHub writes under the ground's CLAUDE.md RULE 12 exception until then. The workflow's local
  `git_commit` card (a commit in his workspace) is not a GitHub write and stays.

### Not now (deferred until this works)

Each is recorded so it is not started before the milestones above are met: Aurora visible control (screen control,
`computer_task`); A2UI beyond the plan card; outside benchmarks; Manjuel as the ledger; the River, A2A and worker
agents; the product; porting the 62 forwarded door tools; the creative server; Flows UI extras.

### Consequences

- Good, because each operation has named tools, a gate and a phone path, and is trusted only when its cases pass.
- Good, because "anything at the keyboard" is available on day one as a carded host shell, without waiting for
  screen control.
- Good, because the Archive becomes useful to him without any path that can carry it off the PC.
- Neutral, because GitHub stays with the hand longer, until the T4 read cases and the operator's word.
- Bad, because the host shell on a card puts the whole judgment on Kyle's reading of the command on a phone screen;
  the card must show the command in full.
- Bad, because new tools (process status, archive, winget, survey, flow tools) each need their own build, gate and
  eval before the matching operation is real.

## Validation

- Each capability N1 to N18 is in `harness/steward/evals/capabilities.yaml` and spec 001 (counted untested until its
  case lands; `evals.py validate` stays green). N1 to N6 become `required: true` in the pull request that lands each
  one's case.
- The away loop is accepted only on a live host (AG-UI 43122 and Jesster), approve, deny and no-answer each observed
  on the phone (ExecPlan 0005, Milestone 1).
- The Archive amendment is held by gate tests: an archive tool reads a file under `ARCHIVE_DIR`; every other tool, and
  every write, copy or publish, is still refused with `Refused by a bound:`.

## Pros and Cons of the Options

### A. General screen control now

- Good, because one capability would cover every operation, including apps with no command line.
- Bad, because a click cannot be gated or scored deterministically the way a tool call can: no bound in ADR-0014
  reads a mouse path.
- Bad, because Aurora is parked until visible control is asked for ([ADR-0004](0004-jesster-is-the-center.md)), and
  driving his screen while he is away can collide with whatever is open.

### B. Tools first, screen later

- Good, because every operation is a named call that the bounds gate reads, a card shows and an eval scores.
- Good, because the carded host shell covers whatever has no tool yet.
- Bad, because each new tool is its own piece of work.

### C. Keep the hand doing it remotely

- Good, because nothing new is built.
- Bad, because it is the opposite of the operator's goal: Steward is to be the brain of the PC.

## More Information

- The order of the work and each milestone's cases: [ExecPlan 0005](../plans/0005-steward-runs-the-pc-from-the-phone.md).
- The bounds this builds on: [ADR-0014](0014-the-bounds-are-gates-in-code.md); flows as the approved plan:
  [ADR-0009](0009-flows-are-ordered-tool-chains-automations-schedule-flows.md).
