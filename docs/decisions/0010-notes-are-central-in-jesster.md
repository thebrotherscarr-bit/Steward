---
status: accepted
contact: Kyle
date: 2026-11-05
deciders: Kyle
---

# Notes are central in Jesster

Narrows [ADR-0004](0004-jesster-is-the-center.md) for notes, without superseding it: ADR-0004 already makes Jesster
the MCP hub for notes; this record says what that means for every other surface that reached the notes kernel.

## Context and Problem Statement

The notes kernel (`worlds/jesster/notes/cli.py`, standard-library Python) was reachable on 2026-11-05 through seven
surfaces, most of them older than Jesster's role as the center, and several of them exposing far more than notes:

1. **The ground's `.mcp.json` `notes` server** (`cli.py --vault worlds/notes mcp`): the whole kernel, 46 tools (notes,
   index, context, capture, live, llm, ingest, import, archive, provenance, kernel, system), for Claude Code in the
   ground. The only one of the seven that runs.
2. **Jesster's own `.mcp.json` and `opencode.json`** (`jesster-notes`, `cli.py mcp` with no `--vault`): opens
   `~/JessterNotes`, not `worlds/notes`. Unused, but the repository's `AGENTS.md` points agents at it.
3. **SecondBrain's Archive digger** (`electron/archive.cjs`; Settings → Archive digger; the "notes kernel" row on the
   Servers list), which starts the kernel over JSON-RPC to dig and distill the Archive; and Integrations' "connect
   app" button (`electron/integrations.cjs`), which writes the whole kernel as an MCP server into Claude Desktop's and
   Gemini CLI's config files.
4. **The door's `notes` tool** (Aurora's `atlas/line/internal/tools/notes.go`, served by Jesster's door on 43111),
   reached through the kernel command the operator declares (`MANJUEL_MCP_NOTES_CMD`): four read-only actions.
5. **Manjuel's engine `notes_call`** (`manjuel/serve.py`), through the same declared command.
6. **`sync.ps1`'s restart of `cli.py serve`** (its default port, 43111, is now the door's) and **of `cli.py bridge`**
   (the relay, unused since 2026-10-24). The relay repository itself (`worlds/secondbrain-relay`) is still used by
   SecondBrain's Report back (`electron/report.cjs`).
7. **SecondBrain itself**, which reads and writes the vault `worlds/notes` as files (`electron/vaultfs.cjs`) and serves
   notes to Steward over its MCP hub (43110).

The Archive the digger was built for has been reconciled. Which surfaces should reach the notes, and with what?

## Decision Drivers

- The operator, 2026-11-05: "archive has been reconciled and sorted, no longer needs digging or whatever. the notes
  should all be coming into jesster and centralized. ADR says? simple and cenral."
- The operator, earlier the same day: "If they're not being used, not a point in having them exposed, as such."
- [ADR-0004](0004-jesster-is-the-center.md): Jesster is the MCP hub (notes, web, skills, the Estate's controls).
- One vault. Two vaults (`worlds/notes` and `~/JessterNotes`) means a note saved in one is missing from the other.
- The ground's rules: the Archive never goes on GitHub and is not reached without asking (CLAUDE.md RULE 1); a
  surface that can dig local paths, update the app or write other apps' configs is a reach nobody now needs.

## Considered Options

- Notes are central in Jesster: one vault, one owner, and only notes exposed elsewhere.
- Keep as is: every surface stays, each documented.
- Jesster only: remove every other surface, the IDE adapter included.

## Decision Outcome

Chosen option: "Notes are central in Jesster", because it is the operator's ruling ("simple and cenral"), it keeps the
one surface he uses in the ground working, and it takes away every exposure nothing uses.

- **One vault, `worlds/notes`, owned and served by Jesster.** SecondBrain writes it (`vaultfs.cjs`) and every save is
  on Jesster's provenance chain.
- **Steward and the operator's tools reach notes through Jesster**: its MCP notes tools on 43110 (`search_notes`,
  `read_note`, `list_notes`, `write_note`, `append_to_note`).
- **A local IDE or agent client that cannot hold Jesster's share key** (Claude Code in the ground, an IDE in the Jesster
  repository) uses the kernel's notes-only stdio adapter, `cli.py --vault <worlds/notes> mcp --only notes` (Jesster
  #90: notes, `index.search`, `context.for`, `context.now`), on the same vault, and nothing wider.
- **No MCP surface exposes the kernel's other method groups** (archive, ingest, import, llm, live, system, provenance,
  kernel, capture). The code stays in the kernel (`notes/plugins/`, its proofs in `notes/prove_notes.py`); nothing
  serves it.
- **The Archive digger is retired**: its Settings section, its IPC, `archive.cjs`, the "notes kernel" Servers row and
  Integrations' "connect app" writer of the whole kernel.
- **Dead surfaces are retired**: `sync.ps1`'s restarts of `cli.py serve` and `cli.py bridge` (the relay repository
  stays, for Report back). Jesster's `.mcp.json` and `opencode.json` `jesster-notes` entries are narrowed to the
  notes-only adapter on `../notes`, because the repository's `AGENTS.md` tells agents to use them.
- **Left as they are:** the door's `notes` tool (Aurora's `notes.go`: already four read-only actions; Aurora is parked,
  ADR-0004) and Manjuel's engine `notes_call` (it reaches the kernel through the operator's own declared command in his
  `.env`, which no hand reads or changes, RULE 7; its refusal list in `manjuel/mcp_stdio.py` stays as a second wall).

### Consequences

- Good, because there is one vault and one owner, as ADR-0004 intended for every hub.
- Good, because Claude Code in the ground keeps its notes tools (11 instead of 46): it can no longer dig the Archive,
  ingest paths, update or rebuild the app, or call a model through the kernel.
- Good, because SecondBrain loses a settings section, an IPC group, a child process and a config writer nobody uses.
- Bad, because the Archive digger's distill and write cannot be run from the app again without bringing the section
  back; the kernel's `archive` plugin still works from its CLI (`cli.py rpc`) for whoever needs it.
- Bad, because a Claude Desktop or Gemini CLI config that "connect app" already wrote keeps its whole-kernel entry until
  the operator removes it; this decision does not edit files outside the Estate's repositories.
- Neutral: Manjuel's engine and the door are unchanged.

Every consumer affected:

| Consumer | Change | Restart |
|---|---|---|
| Claude Code in the ground (`.mcp.json` `notes`) | `--only notes` | the operator's next Claude Code start |
| Agents in the Jesster repository (`.mcp.json`, `opencode.json`, `AGENTS.md`) | notes-only on `../notes` | the client's next start |
| SecondBrain (Settings, Servers list, Integrations, `main.cjs`, `preload.cjs`) | digger and connect-app retired | the app's next release build |
| `sync.ps1` (the ground) | serve and bridge restarts dropped | none |
| Steward | none: notes through Jesster's MCP already | none |
| The door's `notes` tool, Manjuel's engine | none | none |

## Validation

- SecondBrain's tests: no `archive:*` IPC is registered, the Servers list has no `notes-kernel` row, and Integrations
  registers no `integrations:connect-app`; each goes red if the retired piece is wired back.
- The kernel's `prove_notes.py` keeps proving `--only notes` (Jesster #90); on 2026-11-05,
  `cli.py mcp --vault <v> --only notes` listed 11 tools.
- The ground's `.mcp.json` and Jesster's `.mcp.json` carry `--only notes`, read back in the pull request.

## Pros and Cons of the Options

### Notes are central in Jesster

- Good, because it matches the ruling and ADR-0004.
- Good, because it keeps the only surface in use, narrowed.
- Bad, because retiring the digger takes a pull request in SecondBrain and one in the ground.

### Keep as is

- Good, because nothing changes and nothing can break.
- Bad, because six of seven surfaces are unused and five expose more than notes; the ruling says they go.
- Bad, because Jesster's repository config points at a second vault.

### Jesster only

- Good, because it is the simplest: one surface.
- Bad, because Claude Code and IDEs cannot hold Jesster's share key in a checked-in config without breaking RULE 7, so
  the ground would lose its notes tools.

## More Information

- Jesster #90: `mcp --only <list>` and the `notes` preset.
- The audit of the seven surfaces, 2026-11-05, recorded in this ADR's context.
- Implemented by one pull request per repository, each naming ADR-0010: Jesster (the digger, the Servers row,
  connect-app, the repository's MCP entries) and Manjuel (the ground's `.mcp.json`, `sync.ps1`, CHANGELOG).
