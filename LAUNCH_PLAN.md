# LAUNCH_PLAN — the appliance, the business, the week

*Written 2026-09-08, end of day, at the operator's word: "check everything,
seatlogs, handoffs, etc. write me up a plan. set it in the
research/worlds/atlas … write me up a full launch plan." Placed in
`worlds\atlas\` — the world he named for atlas's pull, read-only by
position, never an index root, source only.*

*What was read whole today: Manjuel's `CLAUDE.md`, every file in `law/`,
`SPEC.md`, `SEAT_LOG.md` (every toll), `HANDOFF.md` (every block),
`memory.md`, DAYBOOK's last entry, CHANGELOG's Unreleased, TASKS' open
lines, `README`, `QUICKSTART`, `rack.md`, `agents.md`, `pipelines.md`,
`DESIGN.md`, `REFUSALS.md`, `BUILDPATH.md`, every module in `manjuel/`;
atlas's `CLAUDE.md`, `AGENTS.md`, `CHARTER.md`, `THE_ROAD.md`,
`DELIVERABLE.md`, `CHANGELOG.md`, `HANDOFF.md`, the tails of `SEAT_LOG.md`
and `STATE_OF_BUILD.md`, `SPEC_COMMANDS`, the GUI gap analysis and the GUI
plan, `atlas-tui/main.go`, `webapp/db/db.go`; all of `worlds\TBC` outside
the vendored repos. NOT read whole: Manjuel's `DAYBOOK.md`, `CHANGELOG.md`
and `TASKS.md` beyond the parts named; atlas's `SEAT_LOG.md` and
`STATE_OF_BUILD.md` beyond their tails; `worlds\manjuel`, `worlds\sewder`.
Nothing asserted below rests on the unread parts.*

---

## 0. Where it stands tonight — verified against the disk

| thing | state | proof |
|---|---|---|
| Manjuel engine | 0.1.6 built, unsealed; **1,854 strokes / 60 smoke on the mirror**; `manjuel/serve.py` (the headless door) landed 14:30 | `CHANGELOG.md` Unreleased; `sessions/hands.jsonl` H…142045 |
| Manjuel's own stamp | **`tests/last_run.json` says 1697** — the mirror runs never stamp the ground; the boot report reads back a number 157 behind | `tests/last_run.json` 08:18; `run_history.jsonl` |
| version strings | `manjuel/__init__.py` and `pyproject.toml` still **0.1.4** while 0.1.5 and 0.1.6 are built | both files |
| sittings | 98, closed; **12 numbering gaps now** (98 opened the twelfth; `SPEC.md:177` says 11); 5 unmarked duplicates (22, 26, 40, 42, 57), 5 `(re-tolled)` | `SEAT_LOG.md` |
| hands ledger | 9 hands today; **one orphan open: `H20260908-130404`** (his own, never closed) → the release gate refuses until it is closed by `--id` | `sessions/hands.jsonl` |
| HANDOFF.md | newest block 2026-09-08 (L673); **`START AT` pointer (L17) still says 2026-09-07**; module count says 26 (disk: 27 + `__init__`); "Archive/atlas … untouched" is no longer true | `HANDOFF.md` |
| the record after 12:55 | `serve.py`, `SPEC_CONTROL_CENTER.md`, `SYSTEM_DESIGN.md`, the TBC scrub, TBC's move to `worlds/`, the 1,854 run — **in `hands.jsonl` and CHANGELOG only**; not in SEAT_LOG, HANDOFF, DAYBOOK or memory | the three files' mtimes |
| memory.md | 11 entries; 4–6 are one rule three times (the s63 dedup fault, kept under LAW 1); 7 is empty; 11 is the defective `index_ground` entry HANDOFF names | `memory.md` |
| index | **known clean**: 863 docs / 4,572 chunks, rebuilt 08:18 in 294 s; HANDOFF's "not known clean" is stale | `logs/2026-09-08_081850_index_ground_rebuild.md` |
| atlas | `0.1.1+f1`, all stones P0–G witnessed; git is his hand; `.gitattributes` still missing there (fixtures show as modified on any clone); `atlas-tui` shells to `curl`; `webapp/db` is a second truth | `Archive\atlas` |
| the business | `worlds\TBC`: four billed visits ($575), estimate TBC-1005 ($1,185) outstanding, templates in three generations with ten contradictions, an estimate CLI already in the seam's shape, a hub prototype with its truth in a browser tab; names scrubbed (B), **second pass owed** | `worlds\TBC`, `SYSTEM_DESIGN.md` App. A |
| the specs | `SPEC_CONTROL_CENTER.md` (the glass, H-stones), `SYSTEM_DESIGN.md` (the appliance, T1–T8) at the Research root | root |
| his profile | Me + 1; iPhone photos/voice, texts, Gmail, Zelle/Venmo, Instagram/Facebook; all eight headaches; **whole backend by 2026-09-15** | his answers, 2026-09-08 |

---

## 1. Definition of LAUNCHED

Three sentences, each provable:

1. **The backend is whole**: every world opens its own sitting with its
   own record; the estate's five pieces and the business's T1–T5 + T8 are
   mirror-proved, CHANGELOG'd, and the standup runs live 10/10 inside
   `worlds\TBC`. *(Target: Mon 2026-09-15.)*
2. **A job runs through the record**: photos from the phone land hashed
   and GPS-free in the drop; a visit is filed by his hand; the invoice is
   numbered by the one counter; nothing was typed into a browser tab.
   *(Target: the first visit after the 15th.)*
3. **The campaign is live**: released material only, drafts refused by
   the Guardian where they name what wasn't released, posted by his hand.
   *(Target: the week of 2026-09-22, after the glass pages or from the
   REPL — his call.)*

The glass (T6) and the LAN gate (T7) are the front end and come after 1.
They are the second week, not the first.

---

## 2. Before any piece — the record's honesty (his hand, 15 minutes)

These are not builds; they are the lines a hand cannot land without his
word, and the release gate will refuse the first tag until the first one
is done.

1. ~~close the orphan hand from 13:04~~ — **MOOT.** The hands ledger was
   removed 2026-09-09 at the operator's word ("we didnt have it 3 days
   ago"); `seatlog`'s CLI went with it, so there is no line to close.
   `sessions/hands.jsonl` stays on disk, unwritten (LAW 1).
2. `python tests\test_manjuel.py` and `python tests\smoke_cli.py` **on
   his terminal** — the ground's stamp is 157 strokes stale; the mirror is
   the hand's check, his terminal is the proof.
3. `HANDOFF.md:17` `START AT` → `2026-09-08`; one block for the afternoon
   (the door, the specs, the scrub, TBC to worlds) — or order a hand to
   write it with the sitting closed.
4. `SPEC.md:177` "11 gaps" → 12 (sitting 97 was never tolled).
5. `manjuel/__init__.py` + `pyproject.toml` → `0.1.6` when he tags;
   `tests\release.py --check v0.1.5` first, as DAYBOOK's next-session line
   says.
6. In `Archive\atlas`: `.gitattributes` with `* -text` before anyone
   clones it.

---

## 3. Rulings owed — each one line, none blocking the first piece

| # | ruling | gates |
|---|---|---|
| R1 | the second-pass scrub of `worlds\TBC` (third-party names in the two non-competes; the business name in two base64 payloads; a live UUID + PIN; a P.O. box; initials; the Windows user path) — **go** | T1 |
| R2 | `worlds\marketing` — that name, that place | the campaign |
| R3 | the drop share's name and path (`\\box\drop\<world>`) | T4 |
| R4 | the TBC world's seats (door on llama3.2, Router, Guardian, Clerk on phi4-mini) — or his names | T1 |
| R5 | the ten template contradictions (`SYSTEM_DESIGN.md` App. A): Tier 2 identity · Tier 3 scope · materials rule (the $1,000 A.R.S. cap) · retainer · grandfather · notice/venue · "no property management" vs the old packets · the two non-competes · numbering · one persona per world | T8 |
| R6 | LAN posture: bind the glass to the LAN with one operator secret (a departure from loopback-only) | T7 |
| R7 | the weekly cadence phrase and day (he skipped it; proposed "weekly check-in", Monday) | — |
| R8 | the Business context block (shown 2026-09-08) → `remember that:` in the REPL, his hand | — |

---

## 4. Week one — the backend, two pieces a day

Every piece: read what it touches whole → build on a mirror (no `.git`,
no `logs/`, no `index/`) → strokes green → one CHANGELOG entry →
"restart required" when `manjuel/` moved → stop. He says **go** per
piece, or **run the list** once and reads each entry before the next.

| day | piece A | piece B | needs |
|---|---|---|---|
| **Tue 9** | **`--ground <path>`** on `manjuel.py` (REPL and `--headless`); `cli.ROOT` stops being the package's parent; a temp world opens its own sitting and writes only its own record | **R1** — the second-pass scrub, inside `worlds\TBC` | §2.1–2; R1 |
| **Wed 10** | **T1** `worlds\TBC` becomes a world: `agents/`, `skills/` (the `tbc_estimate` verbs wrapped; `intake`, `visit`, `invoice`, `packet`), `pipelines.md`, `ROUTES.md`, `law/` copied + sealed, `index_roots.txt` = itself; stroke: the origin's roots resolve nothing under it | **T2** the counter is the only issuer (`AUTO` only; hand-numbered documents imported with a ledger line; uniqueness stroked) | R4 |
| **Thu 11** | **T3** the client ledger `clients\<id>\ledger.jsonl` + the fold (open items, next due, balance); the four visits and two estimates imported as the first hashed lines; the fold reproduces `seat_log.md`'s NEXT from the lines alone | **T5** access codes → `clients\<id>\access.env`; the packet prints "on file"; stroke: no export, index or transcript carries a code | — |
| **Fri 12** | **T4** the drop: SMB share per world, `drop_ingest` (hash via `atlas` when pulled, sha256 in the meantime), EXIF/XMP stripped on arrival, whisper.cpp transcript → draft `visit` → `needs_answer`; filed only by his hand | *(carry-over slack — Friday is one piece on purpose)* | R3 |
| **Sat 13** | **`worlds\marketing`** forked from the origin's declarations, `law/` sealed, roots = itself | **`release`** — one skill, the only path across; stroke: no marketing read/write path resolves into any other world, by name and by property | R2 |
| **Sun 14** | **the marketing seats + `campaign` pipeline**: copywriter on the smallest model that can write a caption (SITTING LAW 3), Proofreader, Guardian (addresses, names, prices, anything not in a release line), Delivery; released set → drafts → posting calendar; refused drafts stay in the delivery | **the door drives a world**: the 60-case smoke through `--headless --ground worlds\TBC` on the mirror | — |
| **Mon 15** | **T8** the rulings applied to the templates — one canonical document per kind under `worlds\TBC`, the drift folded, not erased | **the prove**: full strokes + smoke on his terminal; standup live inside `worlds\TBC` 10/10; `tests\release.py --check`; **backend LAUNCHED** | R5 |

Dependencies are strict in two places only: nothing before `--ground`;
the campaign needs `release`. Everything else can shuffle. Two a day holds
only if he is there twice a day to say the word; one a day slips the
15th to the 19th — say so on Wednesday, not Sunday.

---

## 5. Week two — the front end, then the first job through it

| day | piece | note |
|---|---|---|
| Tue 16 | **H0** pull `atlas` (Rust spine) and THE LINE into Research at the places he names; Research's `.gitattributes` covers them; `atlas-tui` off `curl` (`net/http`); `webapp/db` retired | first pulls from the artifact; each a place he names |
| Wed 17 | **H2** THE LINE carries worlds: `env_*`, `run_*` (over `serve.py`'s wire), `route_*`; tenant = world | `atlas-mcp --prove` on temp grounds |
| Thu 18 | **T6a** the glass's estate pages: Environments, Run, Record, Alerts, Law | `SPEC_CONTROL_CENTER.md` P0-5/7/9 |
| Fri 19 | **T6b** the glass's TBC pages: clients · visits · photos · estimates · invoices · contracts · calendar · logbook — the hub's eight panels over THE LINE, reading the record, writing through `run_*` and `needs_answer` only | retires `localStorage['tbc_hub_v2']` |
| Sat 20 | **T7** the LAN gate: LAN interface, one operator secret, self-signed TLS; the phone reaches the glass | R6 first |
| Sun 21 | **the first job through the record** — his next scheduled visit: drop → file → checklist → invoice, no terminal | LAUNCHED §1.2 |

## 6. Week three — the campaign, the money, the calendar

- **Mon 22 – Wed 24**: the campaign — released material from the first
  job(s), drafts, his posts. LAUNCHED §1.3.
- **`worlds\books`**: Zelle/Venmo statement CSV in; the fold answers "how
  much did I make"; taxes are a report, not a service.
- **`worlds\clients`** (texts and Gmail): inbound as drops (screenshots,
  `.eml`); outbound as `mailto:`/copy with the body filled — drafted,
  never sent (RULE 4; the gate).
- **calendar**: visits due from the tier cadence in each client's fold;
  an `.ics` export he subscribes to on the phone — a file, not a service.
- **chain 0.1.7 → 0.1.8** on its own path (the citation check's harder
  half, the door's prose faults, parity on the tiers; workflows; the gate
  in CI; SPEC §4 with no OPEN line).
- **H3–H7** on atlas's path (traces/waterfall, TUI, evals/compare/replay,
  the engine port behind golden-master parity, chain retired by fold note).

---

## 7. The daily rhythm (the operator's, written down once)

**Morning** — `python manjuel.py` (or the door, `--headless`);
`/brief`; the standup once the pieces of the day are in; the pieces, two,
each with its word; **close every sitting** (the toll, attended when he
sat). **Monday** — "weekly check-in": the fold of every
client (open items, next due, balance), the estate's last prove, the tags
owed. **Never** — `git status` from a sandbox; an edit while a sitting is
open; a folder unasked; a name in the record.

---

## 8. Inputs — what comes in, as files, at no cost

| source | in | out |
|---|---|---|
| iPhone photos / voice memos | the drop share (T4) — hashed, GPS-stripped, transcribed, drafted, filed by hand | — |
| texts / iMessage | screenshots or pasted text into the drop | copy-to-clipboard drafts |
| Gmail | `.eml` / pasted mail into the drop | `mailto:` with the body filled |
| Zelle / Venmo | statement CSV → `worlds\books` | the invoice's memo text |
| Instagram / Facebook | — | the campaign's drafts + calendar; he posts |
| the calendar | the fold of tier cadences | an `.ics` file he subscribes to |

Nothing reaches Apple, Google, Meta or a bank from the box. That is the
product, not a limitation.

---

## 9. Risks, and what to do the day each one shows

| risk | signal | move |
|---|---|---|
| pace | a day ends with one piece | say so; the 15th → 19th; the order does not change |
| the hand keeps going | a piece lands with a second one attached | refuse it; RULE 10; the CHANGELOG says what was named |
| the record goes stale | HANDOFF's pointer, the stamp, the versions (§2) | §2 first; a release gate that refuses is doing its job |
| VRAM | the court past 600 s again | the seat bound holds; SITTING LAW 3 — smaller, measured |
| client material leaks | any token in a transcript, index or delivery | the release verb and the Guardian are the only doors; a stroke per world proves the origin never indexes it |
| the templates | a client signs the wrong generation | R5 on the 15th; one canonical document per kind |
| the brother | two hands on one world | one writer per world by construction; a second seat is a second world or a second box |

---

## 10. Read in this order (for any hand, any morning)

`CLAUDE.md` → `law/` (all) → `DAYBOOK.md` last entry → `HANDOFF.md`
newest block → `CHANGELOG.md` Unreleased → `TASKS.md` open lines →
`SPEC.md` → **this file** → `SYSTEM_DESIGN.md` → `SPEC_CONTROL_CENTER.md`
→ `worlds\TBC\agents.md` and `seat_log.md` for the business → atlas's
`CLAUDE.md`, `THE_ROAD.md`, `SPEC_SEAM.md` when a pull is named.

---

## 11. For the record — lines that belong in the ledgers, by his hand or at his word

- **HANDOFF.md** — a `## HANDOFF FOR 2026-09-08 (afternoon)` block: the
  headless door; `SPEC_CONTROL_CENTER.md` and `SYSTEM_DESIGN.md` at the
  root; the TBC scrub (B) and its move to `worlds\`; `worlds\atlas` and
  this plan; the orphan hand; the stale stamp. `START AT` → 2026-09-08.
- **DAYBOOK.md** — Session 6's "At close" and "Next session": the six
  hands, the pieces named for Tuesday, the 15th.
- **TASKS.md** — his list; nothing added by a hand. If he wants the week
  tracked there, §4's rows are the lines.
- **memory.md** — R8, the Business context, via `remember that:`.
- **SEAT_LOG.md** — nothing; no sitting sat this afternoon.

*Hand `H20260908-174703` opened for this review and closed with this
file and one CHANGELOG line. The three surveys behind it — Manjuel
record, the atlas record's tails, the TBC world — are in the day's chat
and folded here; nothing in `worlds\` was written except this file, at his
word.*
