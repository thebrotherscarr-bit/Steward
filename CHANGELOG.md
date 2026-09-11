# Changelog

All notable changes to ATLAS will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

Versions are plain semver from 0.1.2 on. Through 0.1.1 they carried a build
tag naming the stone that cut them — `0.1.0+a1` through `0.1.1+f1`. The
operator struck the moniker 2026-09-10: *"remove the moniker for the stones,
no letters in my versions."* Released headers below keep the tag they shipped
under, because they are the record of what happened.

## [Unreleased]

### The first strokes on the MCP, and two bugs they caught immediately

ADR-006 measured the door and found the thing that explains a two-day failure
streak: `internal/httpserver` is 800 lines, it is what makes atlas-mcp an MCP
server rather than a pile of functions, and it had **zero tests**. The tool
bodies behind it carry 755 strokes; the wire in front of them carried none.
Twelve strokes now stand there, hermetic — a real registry over a real temp
tenant that deliberately does NOT look like manjuel, asserting only what the
wire says.

- **A tool's own words outrank the Go error** (ADR-006 item 1). The tools/call
  error branch discarded `out` one line before it would have been sent and
  returned `err.Error()` instead — which for anything shelling a subprocess is
  the bare string `exit status 1`. `verify_chain` exposed it: it captures the
  Rust spine's `CombinedOutput` INTO `out`, so the diagnosis was in hand and
  thrown away. **Protocol-level**: every tool that errored was losing whatever
  it had written. `isError` still tells the caller it failed; it now also says
  why.
- **THE REGRESSION STROKE WAS WORTHLESS UNTIL IT WASN'T.** It passed with the
  fix reverted, which means it proved nothing. The reason was a second bug, in
  the resolver written earlier the same day: `findAtlas` walked from `"."`, and
  `filepath.Dir(".")` is `"."` — so that root broke out of the walk on its
  first step and never climbed. The door never noticed because its own
  executable path walks fine; a TEST binary lives in a build temp dir, where
  that root was the only one that could reach the tree and it was the one doing
  nothing. So the spine was never found, `out` was empty, and both branches
  produced identical text. Fixed to walk from an absolute cwd. **The stroke now
  fails with the fix reverted** (`the caller got only "exit status 1"`) and
  passes with it applied, which is the only thing that makes it a test.

**What the twelve pin:** the protocol version is a promise to every client
(`2025-06-18`); a notification is answered with silence; every advertised tool
carries a description and an inputSchema and never requires a property it does
not declare; `-32601` for an unknown method and `-32602` for an unknown tool,
each naming what it did not know; `-32700` for a malformed line; the id comes
back; a tool's refusal is `isError` and NOT a transport error, because a client
that retries transport errors would retry a refusal forever.

**And one the review found that the ADR missed:** `GET /tools` and `tools/list`
are two copies of the same 28-line rendering. A stroke now holds them
byte-identical, because a REST caller and an MCP caller disagreeing about what
a tool takes is the worst kind of quiet.

17 Go packages green, 0 failing.


### The spine is found, not assumed

`verify_chain` was dead on every machine where the Rust spine had been built
but not installed on PATH — which is every fresh clone. `--atlas-bin` defaults
to the bare word `"atlas"`, `atlas-door` walked the built tree to find it, and
`atlas-mcp` never did: the same estate answered differently depending on which
door you came through. `tests/PROVING.md` has named this a trap since it was
written, and RUNBOOK's start line still did not carry the flag.

- **The walk moved to `internal/tools`**, the one place that actually shells
  the binary, so every caller gets it and there is no second copy to drift.
  Order: an explicit `--atlas-bin` that is not the placeholder, then
  `ATLAS_BIN`, then PATH, then the built tree.
- **It starts from the running binary's own location.** A first cut walked up
  from the tenant home and from cwd; for `atlas-mcp` the tenant home is the
  CORE ground and the spine lives DOWN from there in `atlas/target/`, so the
  walk climbed past Desktop and found nothing. `atlas-mcp.exe` sits at
  `<repo>/line/` and the spine is built at `<repo>/target/` — two up and back
  down, which the walk now covers. Both `debug` and `release` profiles.
- **It still names what it could not run.** Nothing found returns `"atlas"`
  unchanged, so the refusal a caller sees is the same honest one as before.

Proved live, with no `--atlas-bin` passed at all: `verify_chain` on
`law/chain.jsonl` went from `exec: "atlas": not found in %PATH%` to
`verdict=FLIP entries=4`. 16 Go packages green after the change.

### The README stopped asking for what it does not need

Found by cloning this repo onto a clean tree and following it literally.

- **The MSVC toolchain is named.** `store/src/ffi.rs` links Windows' own
  `winsqlite3`, so `cargo build` needs `link.exe`. A fresh PC with only rustup
  dies on `linker 'link.exe' not found`, which says nothing about this
  project. Several GB of prerequisite, named nowhere until today.
- **Python 3.14 was never needed.** The core's `pyproject.toml` says `>=3.10`
  and CI proves 3.10 and 3.13. The `.venv` the same line named is created by
  nothing and is gitignored; `tests/prove.py` uses `sys.executable`.
- **`cd line ; go build ./...` produced no binaries and no error.** `line/cmd`
  holds five main packages and Go discards every result when it compiles more
  than one. It is a compile check that reads like a build.


### The rule that kept winning arguments it was not in

`.covenant` being declared twice was one instance of something; this is the
rest of it, found by measuring instead of by eye. Two audits were written
against the stylesheet: one for the same selector declared twice, one for the
shape that actually did the damage — two DIFFERENT classes worn on one element
where the later one silently takes a property.

**The culprit is `.muted`, and it has now ambushed three things.** It is worn
as a colour utility, 62 times across this console, but it also sets a
`font-size` and a `margin-top`, and at one class of specificity the later rule
wins. It took the hero verdict from 40px down to 12px this morning. It was
also cutting Version control's footnote — *"Every button here is your hand,
not the machine's"* — from 16px of top margin to 6px, which is why that line
has been sitting closer to the buttons than it was written to.

- **The spacing utilities moved to the foot of the file.** A utility exists to
  set one property and `.mt-16` was losing that property to a colour class.
  Utilities come last; that is the whole reason they are a category. Measured
  after: the footnote gets its 16px.
- **The hazard is written down at `.muted`'s own definition**, in the terms a
  hand needs: wearing it beside any class that sets `font-size` or
  `margin-top` means `.muted` wins unless that class is declared after it.
  Stripping the two extra properties would resize all 62 uses, which is a
  change nobody asked for, so the rule stands and the trap is documented where
  it is stepped in.
- **`.seat-open` declared `color: inherit` and never got it** — `.card-title`
  is later and sets the colour. What the link actually wanted was to look like
  every other card title, which is what it was already doing, so the dead
  declaration is gone and the hover stays (a pseudo-class outranks a bare
  class). Measured: the seat name renders at `--accent-2`, identical to a
  title that is not a link.
- **`.sidebar-footer`'s `font-size: 11px`** was re-stated verbatim as
  `var(--t-xs)` further down and never read.

**What the audits say now.** Three pairs still collide and all three are the
INTENDED rule winning: `.btn-sm` over `.btn`, `.home-box` over `.card`,
`.chat-foot` over `.muted`. Three more — `.empty-text`, `.textarea`, `th` — hold
an earlier value a later rule deliberately refines, which is a cascade doing
its job rather than a defect. No ambushes remain.

Swept afterwards across all eight pages: none scrolls sideways, and the crumb
is hidden on the Dashboard and present everywhere else.

### Two the sweep turned up on the way

- **"Through the council" was pushing its own input out of its card.** The
  header's right-hand group was `flex-shrink: 0`, which is right for a row of
  buttons and wrong the moment a FIELD is in it — the base field rule is
  `width: 100%`, and a full-width input in a group that will not give anything
  back goes straight through the card's edge. A field in a header now sizes to
  the room it is given. Measured at 1400px: one row, 48px, inside the card.
- **A changed file's label ran into its filename with no gap.** The label was
  an inline-block with `min-width: 150px`, which is a floor and not a ceiling,
  and *"changed, ready to save"* is wider than that in the mono face. It is
  two real columns now: the label takes what it needs up to a cap, the path
  takes the rest and wraps rather than pushing the card.

### The Aurora scheme

The operator pointed at a console he built for an earlier version of this
estate and said what he wanted from it: *"i like the current dashboard layout,
and the colors/flow of the one i sent."* So the layout is untouched — the
deck, the hero, the ledger, the crumb all stand — and the palette and the
flow devices are his.

**The palette now means something.** This console was Catppuccin-adjacent: a
neutral near-black under a cornflower blue. Aurora's ground is blue-GREEN at
the root (`#05080a`), its text is teal-tinted rather than grey, and it runs a
phosphor cyan with an amber second. The colours are not decoration — the
**amber is what the estate calls SEALED**, the **phosphor is what it calls
PROVEN**, and the orange marks a section of the record. Fifty-five hardcoded
`rgba()` literals of the old palette were still scattered through the file
behind the tokens; every one of them moved.

- **Mono-first, as Aurora is.** Its whole console is one fixed pitch and that
  is most of why it reads the way it does: every label, value, field and
  control on one grid. The prose face is kept for the handful of places this
  console carries real SENTENCES — a hero line, a page subtitle, the brief,
  a delivery — where a fixed pitch costs more in reading than it earns.
- **The glowing edge.** A 2px bar down the left of the panel the page is
  about, with a 12px bloom off it, in the verdict's own colour — so the edge
  says the same thing as the word beside it, or it says nothing.
- **The section rule.** Aurora's headings are a tracked micro-label followed
  by a hairline running to the panel's edge. That single device is what makes
  its panels read as parts of one instrument rather than a stack of boxes;
  every card header in this console now closes the same way.
- **The washed ground**, a cyan bleed at top centre and an amber at top right,
  fixed behind everything for one paint.
- **The pinned action wears the seal.** Booting opens a sitting and closing
  pays its toll: both move the record, so that one button is amber while cyan
  stays the colour of reading.

### Four that were wrong, found by looking at every page

- **The Watchboard's badge read "delivered — 54.3s" over a panel reading
  "nothing has run in this tab yet."** `Run.check()` is where a turn kept from
  a previous visit comes back, and the only handler it fires is `state`, which
  repaints the badge alone. The board now paints from what that read found.
- **A dead badge on Evals.** The run card moved to the Dashboard and took its
  log element with it; `paintRun` returns at its first line when that element
  is absent, so `#ev-run-state` was never painted once and sat in the header
  of every visit showing a hardcoded em dash — a control that looks like a
  reading and is a literal.
- **`.covenant` was declared twice** in one stylesheet, and the later rule won
  silently. Two rules for one class is exactly how `.muted` came to steal the
  hero verdict's font-size this morning. One rule now, and the hairline above
  it does the lifting rather than the colour.
- **Three tables were written bare**, and a bare table pushes its card, which
  pushes the grid, which scrolls the page sideways: Settings was 601px of
  content in a 595px main because of a badge reading `can_approve:false`.
  Wrapping the three by hand fixes the three and not the fourth, so a table
  in a card scrolls in its own box whether or not anyone remembered the
  wrapper. Button labels stopped breaking mid-word in the same pass — the
  mono face is wider, and a row of buttons wraps between buttons or it stops
  reading as a row of controls.

### The watchboard: the council from the inside

Chat was a second conversation — the same box as the launchpad, the same
`Chat.thread` array, the same bubbles, plus scrollback. Two of its jobs were
real and neither needed a whole page: answering a gate, and showing each
seat's words as they stream. Both belong in a watchboard. His words:
*"basically like a multi-panel watchboard to see the backend of all the system
and core work so literally every tool call and everything is being landed on a
page. this would be like the internal chat of the models themselves."*

**The feed was already there and nothing rendered it.** council.js has kept
EVERY event of every turn since it was written — *"the record of a run is the
events"* — and the only reader was a single-column card that drops, on
purpose, the one kind that matters most here:

    case 'token': return '';   // App.runRow

The seats' own words. The step-by-step shows what the council DID; this shows
what the models SAID while doing it. Same wire, nothing new asked of the
engine, nothing new stored, no second definition of anything.

- **Four panels**, because they answer four different questions and reading
  them interleaved is what made the single column unreadable. THE TURN: what
  was asked, under which pipeline, and the delivery. THE FLOOR: every seat that
  took it, its model, and its raw output whole. THE TOOLS: every call, the
  arguments in, the result out, `failed` read off the engine's own field. THE
  WIRE: every event in order, unreduced — with a `raw` toggle that prints
  each whole payload, because *every event* has to mean every event or the
  panel is only another summary. An event kind this build has never met is
  printed as its own JSON rather than dropped.
- **Tokens are counted, not listed, when the wire is folded** — a turn carries
  hundreds and they are shown whole on the floor. `raw` lists them too.
- **The past is on the page.** The live turn is one turn; `logs/` holds every
  run this ground has made, served whole with a sha256 by `records`. That
  answers the other half of what he asked: *"should we move the session
  tracking over there? more of the in-depth view."*
- **The gate stays** — a council question is answered in a field on this page,
  never a `prompt()`, never a default, never a guess (RULE 6). The label in the
  panel is Watchboard; the route and `data-page` stay `chat`, exactly as flows
  did when it became Version control.

**Proved against a real turn, not a stub.** Engine booted, sitting 196,
`git status` run from the watchboard's own box: 2 seats, 1 tool call, **148
events**, 54.3s, delivered. The floor carried Router (`qwen3.5:4b`, 280 chars)
and Steward (`llama3.2:latest`, 409 chars) streaming their own words under
their own names; the wire carried the arithmetic guard, the skill decision, the
call, the result, both token runs and the delivery. Sitting closed and tolled.

- **Two clocks on one page stopped disagreeing.** The facts row is painted per
  EVENT, and a seat can think for a minute without putting one on the wire — so
  it read 2.6s beside a badge reading 49s. The turn's clock now ticks into its
  own span, the same shape as the engine's age on the Dashboard.
- **`when()` takes an epoch, not an ISO string**, and hands anything else
  straight back — so the earlier-runs table printed raw `2026-09-11T02:59:20Z`
  in UTC. Records already knew this and wrapped it in `Date.parse`.

### The Dashboard answers the question it is actually asked

Rebuilt against what the console is FOR, at the operator's word: *"think about
what the dashboard is used for and what would make sense to put where
functionally"*, and against a read of what dashboards do now.

**The order was wrong, and it was wrong in the one way that costs something.**
He sits down and asks, in this order: *can I work at all — what do I want done
— what is happening — is the ground sound — is anything waiting on me.* The
page answered them almost backwards. The ENGINE CARD, which gates every other
thing here — nothing typed into that box runs without an engine — sat BELOW
the box it gates, three scrolls down. Meanwhile the five score cards, which
move perhaps twice a day, held the top-left quadrant.

- **The hero is the sitting now.** Open or not, on which world, since when,
  with the one button that changes it. The engine card is folded into it and
  gone as a card; its whole content was one sentence, which is the exact
  complaint its own comment made about the card it had replaced.
- **With one override: a red build outranks an unopened engine.** Booting onto
  a broken build without being told is worse than not knowing the engine is
  shut, so red anywhere raises an alarm in the hero that NAMES what fell and
  the first thing to fall. A measure that was never run raises a yellow one:
  *not-tried is not the same as passed*, and only one of those is good news.
- **The proof drops to a ledger beside it** — rows, not cards. Five cards of
  identical weight made the eye do the ranking; a ruled list puts every value
  in one column where they can be compared in a single sweep, which is the
  only reason to show them together. Three elements above the fold now
  (the sitting, the ledger, the box) where there were nine.
- **The brief rose above the box, and green went actually silent.** It is the
  interrupt channel — a gate waiting, a refusal, an engine running code older
  than the ground — and it arrived UNDER the box it should have changed what
  he typed into. When nothing needs him it now renders nothing at all; the
  page subtitle still carries the all-clear, which is where a quiet statement
  belongs.

**What the market read gave us, and what it did not.** The 2026 consensus
across the tools this one sits beside is decision-first rather than KPI-grid:
one north-star answer in the top-left, four to six supporting measures, and
nothing above the fold that does not change the next move — with Nielsen
Norman's finding as the hard edge, that a reader scans in a Z and gives up
past about seven competing elements. That is the shape taken. What was NOT
taken: sparklines, donuts, and an "AI summary" of numbers the record already
states plainly. Every line still names the file it was read from, which is
this console's own law and worth more than any chart.

### The seat page stops being a lie

- **`/agents/:id` was an orphan AND wrong.** Nothing on the seats page linked
  to it, so the only way in was to type the URL — and when you did it read
  `API.getAgent`, which queries the webapp's own SQLite `agents` table. Nothing
  writes that table. The list beside it reads `agents/*.md` through the `seats`
  tool, so a ground holding fourteen declared seats answered **404 for every
  one of them**, and the fields it was built to show (office, reports_to, mode,
  permissions) do not exist in a declaration at all. Fourth instance of a page
  counting the webapp's store instead of asking the record, and the last one
  standing. A route nobody can reach is a route nobody notices is broken.
- **It reads the record now**, keyed on the file stem — stable, unique,
  url-safe, and already what the record calls the document. It carries what
  the card cannot: the declaration with nothing folded, the system prompt open
  rather than behind a toggle, every pipeline placement with its step and
  condition, and **the file itself with its sha256**, served by `records`.
  `/agents/steward` went from HTTP 404 to seven fields, five placements and a
  3422-character prompt.
- **An absent name is denied honestly** and the denial lists the fourteen that
  are there, each one a link — the same doctrine `read_doctrine` already held
  itself to.
- **A seat's name is the way in.** It reads as a title until you go near it:
  on a page of fourteen cards, a row of blue links is a row of noise.

### Three that were silently wrong

- **`.hero-verdict muted` came out at 12px.** `.muted` further down the file
  sets a font-size and a margin, has the same specificity, and is later — so
  it won. A utility class used as a state name is a collision waiting for
  whichever rule happens to be written last. The state has its own name now.
- **`window.Home` is not a thing.** `Home` is declared `const` at the top of
  home.js, and a top-level `const` in a classic script binds in the global
  LEXICAL scope, never as a property of `window`. The guard was always false,
  so the hero came up with its kicker and an empty body — which looks exactly
  like a failed read.
- **A system prompt is prose, so it wraps.** The base `pre` rule now scrolls
  anything too wide, and a paragraph you have to drag sideways is not served
  whole in any sense that matters. Link-buttons stopped underlining in the
  same stroke: several buttons here are `<a>`, and they were carrying the
  browser's underline through the button's own chrome.

### The console says where you are, and what moved
- **A crumb, painted once by the router.** Every page but the Dashboard now
  opens with `ATLAS / <page>`, and a detail view carries its third step
  (`ATLAS / Agents / steward`) because there the depth is a fact. It lives
  above the routed content rather than inside each page's header: the router
  is the only thing that knows where you are, and fourteen hand-written copies
  of one line is fourteen chances for one to be wrong. The page's NAME is read
  off its own nav link, so the relabel to *Version control* reached the crumb
  without a second edit.
- **The standup card carries a delta.** `+1 vs last`, read from
  `run_history.jsonl`, which holds every prior live run. It is the ONLY card
  that gets one: nothing else on that row has a second measurement to compare
  against, and an unchanged reading and a never-measured-twice reading are
  different claims. A card with nothing to compare shows no delta rather than
  a zero.
- **Fields are styled by the element, not only by the class.** Ten inputs in
  this console were written without `class="input"` and came out as the
  browser's white box with black text — the save-message field on Version
  control was a bare white slab sitting on a dark card. Classing the ten by
  hand fixes the ten and not the eleventh, so the rule now binds to `input`,
  `select` and `textarea` themselves, with `:not()` guards keeping it off the
  controls that are not fields. The placeholder took the ground's own muted
  colour in the same stroke; it had been inheriting a grey that read nearly as
  loud as a typed value.
- **A git act on Version control re-proves the sidebar badge.** The badge
  repainted only on a run event, so a save or a send made from that very page
  left the panel showing the count from before the act — the one moment the
  number is most obviously being watched. Seen live: research pushed, the page
  said *in step*, the badge still read 7. It repaints that badge ALONE
  (`paintOwed`, the same shape as `paintProof(box, only)`): it is the only one
  an act on that page can move, and doing all four costs six tool calls in a
  row — long enough that the first cut still showed the stale number when the
  eye went looking for it.
- **Settings stopped scrolling sideways.** A `1fr` grid column is
  `minmax(auto, 1fr)`, and `auto` there means MIN-CONTENT, so one long
  unbreakable line inside a card — the team-bridge readout — made the column
  refuse to narrow and pushed the whole page. Measured: 737px of content in a
  595px main. `min-width: 0` on the grid children, and `pre` scrolls in its
  own box rather than shoving the page.

### The readers are proven too
- **15 more strokes on `internal/tools`**, on the three tools that READ the
  estate's own record — where a quiet wrong answer does the most damage. Every
  one of those three exists because an earlier page counted the webapp's own
  SQLite store instead of asking the record and showed four zeros on a full
  estate; nothing had ever held them to it. **34 strokes in the package now.**
- **`records`**: sorted by what a document *is*, with the law above the seats
  (alphabetical would invert that), `law/` marked sealed, only markdown served,
  and the sha256 receipt matching the bytes actually handed over. The path
  stroke is the one worth reading — **a name is matched against the listing and
  never joined onto Home**, so `../.env`, an absolute path and `law/../.env` are
  not *defended against*, they simply are not in the list and cannot resolve.
- **`proofs`**: a closing sitting line folds over its opening one (get that
  wrong and every sitting counts twice), a half-written last line — what a
  killed process leaves — is dropped without losing the lines before it, one
  absent file never blanks the other two, and the counts the core owns are
  *named* rather than recounted.
- **`seats`**: fields are whatever a declaration carries, including one invented
  tomorrow, because the core's own parser names no field either; the colon comes
  off a key; a `System Prompt` with an empty value takes the body beneath it and
  stops being counted twice.
- **The registry contract is pinned.** A tool that writes must declare it —
  that flag is what the review-only table refuses by, so a mislabelled tool
  would hand counsel a hand instead of eyes.
- **`runstream.go` stays uncovered, deliberately**, and is named as such in
  `tests/PROVING.md`. `RunStream`, `AnswerStream` and `ListenStream` all need a
  live engine on an open sitting; a mock there would prove the mock.


### The console takes a keyboard
- **Ctrl+K / Cmd+K opens a palette.** Every page and the engine's verbs, three
  letters and Enter. Checked on the event rather than the platform, because a
  Mac keyboard on a Windows box happens and neither should have to learn the
  other's key. **It navigates and it boots, and nothing else** — a palette that
  can run anything is a second command surface to learn and a second place for a
  destructive verb to hide. Close is in it because it *pays the toll*, the one
  routine act the record depends on and the easiest to forget.
- **What it offers is what is true right now.** The engine rows read `Run`'s live
  state, so a palette opened after a crash does not offer to close a sitting that
  already closed.
- **Tables read down a column.** A stripe barely there — enough to hold a line,
  not enough to become a pattern — drawn as a background so a hovered row still
  wins without a specificity fight. Figures are right-aligned, which is what
  makes two numbers comparable at a glance now that they are tabular.
- **Waiting looks like the thing that is coming.** "Reading both grounds..." with
  a spinner is a sentence about the machine; a skeleton says how much is arriving
  and where it will sit, so the layout does not jump when it lands. It is the one
  piece of non-user-triggered motion here and it earns it — a still grey block
  reads as a broken image — and it is switched off under
  `prefers-reduced-motion`, along with the mic pulse.
- **An empty screen is an invitation**, so it gets room and a plain sentence
  rather than a shrug in the corner of a card.


### The console is rearranged around what you actually look at
- **Recent moved with it**, and the nav item is **Version control** now. The
  route and `data-page` stay `flows`: the route is what every link, bookmark and
  history entry points at, and `data-page` is the key `css/icons.css` draws the
  glyph from. Clicking a recent objective still fills the box — the box is on
  the Dashboard, so it stages on `Home.pending` and the router goes there.
  Nothing is run by a click.
- **`escHtml` did not escape quotes, and seventeen attributes were built with
  it.** `textContent -> innerHTML` escapes `&`, `<` and `>` and nothing else, so
  a double quote passed through untouched — fine in a text position, wrong in an
  attribute. Found by moving Recent: the objective `git commit: "a test of the
  recent card"` rendered as `data-say="git commit: "`, the attribute ending at
  the operator's own quote with the rest of his sentence loose as markup.
  Escaped at the source rather than at seventeen call sites, because a rule that
  must be remembered at every use is forgotten at the eighteenth; `&quot;`
  renders as `"` in a text position, so the other 209 uses are unaffected.
- **The Dashboard opens with the scores.** strokes, smoke, standup, standups run
  and parity moved off Records, where they were a page you had to go to, and now
  head the launchpad. They answer *is the build sound* — the question worth
  answering before you type into the box beneath them.
- **The run sits under the box that started it.** The step-by-step was a card on
  Evals, a page away from the thing that produced it. Same renderer, same
  `ev-run` id — `App.paintRun` draws it unchanged, because a second copy of that
  renderer is exactly the drift this estate keeps writing docstrings about.
- **The engine card moved down.** A card whose whole content is one sentence was
  opening the page and crowding it. Still above the brief, because nothing below
  it runs until an engine is open.
- **Every git surface is on one page.** The repository card left the Dashboard
  for Flows — "this needs to go with the other github stuff" — so the door path
  (the per-world buttons, no engine needed) and the council path (law gate,
  recorded run) now sit one above the other. Two ways in, on purpose: *"there is
  a series of redundancies.. its called safety, bud."*
- **The flow builder came off.** Registry, editor, SVG graph, fire, resume, the
  runs table, compare, replay and the town board — all rendered, none ever used.
  **Nothing behind them was deleted:** the `/api/flows` routes, `flow.go`,
  `run.go` and their strokes all stand, so a builder is a render away.
- **Records leads with the documents.** What this ground *carries* is what the
  page is opened for; the sittings and standups are the history behind it.
- **Live standups show the last 5 of 33, newest first.** It listed every run ever
  recorded, oldest first, so the one that mattered — the last — was at the bottom
  of a table that grew a row every morning. The rest are named in
  `tests/run_history.jsonl`.


### Added
- **The Flows page controls git, in your own words.** The overwatch card was
  read-only; it now carries the verbs. Per world: a message box and **Save the
  work**, **Send to GitHub**, **Take from GitHub**, and **Lines of work** —
  which lists every branch as *you are here · the main line · on GitHub*, and
  opens, moves to, or finishes with one. A button that cannot work is greyed
  out **with the reason in its tooltip**, so it says why before it is pressed
  rather than after.

  Five new door tools behind it (`internal/tools/gitctl.go`, split from
  `gitstate.go` because that file's own header promises "REMOTE OPERATIONS ARE
  REPORTED, NEVER PERFORMED" and a file must not quietly stop meaning what it
  says at the top): `git_commit`, `git_push`, `git_pull`, `git_branch`,
  `git_remote`. Every one closes its child's stdin, jails paths to the
  tenant's Home, and reads the remote wall without ever opening it.

  **Nothing here fires on its own.** RULE 6 is untouched: these are the
  buttons on the operator's glass and the hand on the button is his.

  **Plain git, not `gh`.** The GitHub CLI is free, open source, installed and
  authenticated on this machine, and it still does not go in: RULE 4 walls
  anything needing someone else's server "even when the remote thing is
  better, free, or open source", and atlas law 6 is hand-roll or refuse.
  Everything named — branches, mains, open and closed, sending — is plain git.
  What `gh` alone would add is GitHub-side objects (pull requests, issues,
  releases, CI runs): a wall to open deliberately, not a dependency to acquire
  by accident.

- **`internal/tools` has strokes for the first time.** 19 of them
  (`gitctl_test.go`), on the package that carries every MCP tool handler and
  was named the estate's biggest hole in `tests/PROVING.md` that morning.
  Hermetic by law 5: each builds its own repository in `t.TempDir()`, none
  touches the record, none reaches a network — the two about sending prove the
  *refusal*, which is the only half provable without one.

### Fixed
- **The wall is the estate's, not one repository's.** The panel told the
  operator two different stories about one ruling — `research` "Sending
  allowed" and `atlas` "Sending OFF" side by side — because `dial()` read only
  `<Home>/.env`, and a carried tenant has no `.env` of its own. He had not
  shut a wall for atlas; atlas was looking in the wrong place. `dial()` now
  reads one level up, and that bound is not invented: it is the door's own
  ground law from `main.go` ("one level up, one level across"). It stops
  there, because walking to the filesystem root would leave the ground
  (RULE 1) and a stray `.env` in `Desktop\` must never open this estate's wall.

- **`readGit()` threw on every navigation away from the dashboard.** It
  captured `home-git-card`, `home-git` and `home-git-controls`, *then* awaited
  the door. A route away during that round trip left all three pointing at
  detached nodes — and writing `innerHTML` into a detached node SUCCEEDS,
  which is what hid it; the throw landed one line later on
  `document.getElementById('git-commit')` returning null. Both the 15-second
  poll and every turn-end call it, so it fired constantly and killed the rest
  of the handler each time. The elements are re-acquired after the await and
  the buttons are found through the bar, not the document.

- **The door was started without `--atlas-bin`, so nothing could reach the
  spine.** `verify_chain` answered `exec: "atlas": executable file not found
  in %PATH%`, which is what put three of the six workflows in the red.
  `atlas-mcp` defaults the flag to the bare string `"atlas"` and does none of
  the built-tree lookup `atlas-door` does. Relaunched with it;
  `verify_chain` now answers `verdict=INTACT`. The code default is still a
  trap and is written up as a ruling in `tests/PROVING.md`.

- **The door's `--manjuel` had been mangled into an error.** `mcp.err` held
  `refused: "C:/.../manjuel.py" is not a landed command` — the `python `
  prefix was lost by a PowerShell `-ArgumentList` earlier the same day, so the
  council engine was never wired. Restarted correctly; `mcp.err` now carries
  only its startup notes.

- **`tests/e2e/_start_mcp.ps1` pointed at the wrong tree.** All three of its
  lines named `C:\Users\novad\Desktop\Archive\atlas` — the pre-split copy,
  outside the ground RULE 1 fences, which nobody edits. A suite started
  against it would have proven a repository no one was changing. Every path
  now derives from the script's own location.

## [0.1.2] — 2026-09-10

### Changed
- **The stone moniker is struck from the version.** `0.1.1+f1` → `0.1.2`, in
  all fourteen places it was pinned: the six `VERSION` files, `Cargo.toml`,
  `core/src/version.rs`, both Go `main.go`s, both webapp handlers, and the two
  test harnesses. The stones are still named where they belong — THE_ROAD,
  STATE_OF_BUILD, the released CHANGELOG headers — but the version is now only
  what the thing IS, not which sitting cut it.

  **The drift catcher was inverted, not deleted.** `core/src/version.rs`'s
  tests used to REQUIRE a `+` and a stone; they now REFUSE one, so the
  moniker cannot creep back unnoticed. And `version.ps1` — the canonical
  bumper — was force-appending a stone in `Format-Version` and defaulting a
  stoneless version to `"f1"` in `Parse-Version`, so the very next
  `bump patch` would have quietly rewritten `0.1.2` as `0.1.2+f1` and
  re-broken every pin. The stone is gone from it entirely and it now refuses a
  version carrying one. Same trap as the flow cutter, one file over.

  **The prove battery caught what grep missed.** Five `VERSION` files under
  `line/` carry no extension, so the first sweep walked past all of them; the
  Rust spine's `version-cross` stroke named every one by path on the next run.
  `version.ps1` now says out loud that its six files are not the only pins and
  points at `tests/prove.py` for the rest.

### Added
- **The engine card says how long it has been standing, and when it is idle.**
  The card already showed `started 10:58:58 AM` — a clock time you have to
  subtract from to learn anything. It now ticks a live elapsed beside it, and
  turns amber with `— idle Nm` once nothing has run for five minutes.

  The measurement behind it, taken across every sitting the core has ever
  recorded: a standup gets 69 seconds of engine time per run; sittings of two
  runs or fewer get 208, and there are 63 of them — **5.3 engine-hours for 91
  runs**. Twenty-two sittings were never closed at all. Sitting 74 held an
  engine thirty minutes for 2 runs, 82 held one fifty-four minutes for 5, and
  166 held one **sixteen minutes for zero**. The record had known for weeks;
  nothing on the glass said a word.

  **Idle is measured from the last turn, not from boot.** A first cut went
  amber only when nothing had EVER run, which misses the shape the waste
  actually takes — 74 and 82 both did work, then sat. A running turn is never
  idle however slow the model is: this must not scold a slow rack, only an
  engine nobody is using.

  Ticks at one second, not on the 15s poll, which would read as a broken clock.
  The interval clears itself the moment the span leaves the DOM — an
  idle-engine warning that leaked timers would be its own joke.

  `static/js/home.js` (`Home.age`), `static/css/app.css` (`.eng-idle`).
  Operator: "we can just add that to the dashboard to view as tasks are
  running in real time, right?"

- **The card counts the turns, from the door.** `/run/state` now carries `runs`
  and `last_run`; the engine counts every turn it pumps, in `Engine.tick`.
  Before this the glass used `Run.turn` — only what THIS TAB had seen, empty
  after a reload — so an engine that had run ten turns read as untouched.

  **A slash command is housekeeping, not work.** Booting sends `/warm` and
  `/status` through the same path, so a freshly opened engine reported "2 runs"
  before anyone asked it anything, and **"0 runs" — the state most worth
  shouting about — was unreachable.** Counted in `Run` after `pump` returns
  rather than inside `pump`, because pump cannot see the objective and only the
  caller knows what it was. An `Answer` always counts: that is his hand.

  **Idleness can never predate the engine.** With no runs, the client fell back
  to its own `turn.ended` — which survives a reboot — and a
  THIRTY-EIGHT-SECOND-OLD engine reported `idle 14m`, counting from a turn a
  previous engine had run. The floor is now this engine's own start.

  `internal/engine/engine.go`, `internal/tools/runstream.go`,
  `static/js/council.js`, `static/js/home.js`.

- **A turn is visible in every browser, not only the one that started it.**
  Operator: "i want to be able to see it runing in sync on my chromium browser
  with your internal browser."

  `/council/stream` belongs to whoever opened it, so a second window could not
  know a turn was running and would not learn until its own 15s poll — by then
  the turn was usually over. **Storage could never have fixed this**:
  sessionStorage is per-tab, localStorage is per-browser. The server is the
  only place two browsers can agree, so `pipeSSE` now mirrors every council
  line onto the broadcast bus `/api/events` and `/ws` already serve, and
  `Run.mirror()` follows it. The runner ignores its own echo (`running` is the
  whole test) or every event would be doubled in its trace.

  **A watched turn needed somewhere to land.** The runner pushes its own pair
  into the thread in `ask()`; a mirroring window never did, so every event
  found no live bubble and the page sat on "waiting for the engine" while the
  answer streamed past it.

- **THE BUS HAS NEVER SENT THE TYPE IT IS KEYED ON.** `SSE` marshalled
  `e.Data` alone, dropping `e.Type` — so `App.onEvent`, which switches on
  `e.type` across eleven events, **had never fired once**. The struct already
  carried `json:"type"`; only that one line disagreed. Fixed, and the toasts
  work for the first time.

- **The boot report is kept.** It lived only in a `<pre>` that `render()`
  rebuilds empty and hidden, so a refresh discarded the RECORD, GATE, RACK and
  VOICE the boot had reported and the only way back was rebooting a healthy
  engine. Now written to the settings store, debounced, **keyed to the
  session** so a dead engine's report is never painted over a live one.

- **The conversation is kept, so a reloaded browser is not an empty box.**
  Mirroring live events was only half of "keep the boot report and the run
  turns": `Chat.thread` is in-memory per tab and `Run.turn` is sessionStorage,
  also per tab, so a browser that reloaded AFTER a turn showed the engine card
  and nothing else. That is exactly how he was checking — "i have been
  reloading my external browser tab every once in a while to watch and see if
  there is parity" — and there never could be. The thread now goes to the
  settings store, keyed to the session, and any browser restores it on load.

- **`onRun` HAS THROWN AT THE END OF EVERY TURN SINCE a014c77.** That pass took
  the sittings strip off the launchpad at his markup and deleted
  `Home.readSittings` — but left `this.readSittings()` standing in the turn-end
  handler. A `TypeError` on every completed turn, silent, killing the rest of
  the handler. It cost nothing while it was the last statement, and the moment
  anything was added after it that thing simply never ran: the kept
  conversation looked correct in every unit and stored nothing at all. Found
  by asking the live page which of the three calls threw, rather than reasoning
  about it.

- **A council bubble's words are in `turn.answer`, not `text`.** `line()`
  renders from `m.turn` and leaves `m.text` empty, so a first cut of the keeper
  filtered on `m.text` and discarded every answer, keeping only what he typed.

- **Only a real start opens a watched turn.** The mirror opened one on ANY
  event, so the trailing lines of a turn the tab had just run — arriving after
  `running` went false — opened a second, empty turn and pushed "(a turn
  started in another window)" into the runner's own conversation.

- **The broadcast bus was 32 deep and dropping.** `broadcast` drops rather than
  blocks, which is right — one slow watcher must never hold up a turn — but at
  32 a council turn's token events made dropping the normal case. 512 deep, and
  the writer now drains in batches and flushes once instead of flushing per
  event, which is what let it fall behind in the first place.

- **THE BALL — one command proves the whole of atlas.** `tests/prove.py`
  gathers the eight places atlas proves itself: the Rust spine, both Go
  modules, the two batteries shipped inside the binaries, **twenty-seven**
  golden verifiers, the six workflows and the E2E suite. AGENTS.md named
  four verifiers; nobody had run the other twenty-two, which is how two legs
  stayed red for weeks without anyone seeing it.

  **It answers in three verdicts, not two.** `ABSENT` means a leg named a
  dependency this ground does not hold — a read-only source ground never
  copied in, a binary not built, a door not answering. ABSENT is never
  counted as a pass and never silently skipped: it prints the exact path or
  command that would answer it, and it does not exit red, because nothing is
  broken — something is missing, and the difference is the whole point. Only
  FAIL exits red. Every child runs with `stdin=DEVNULL`, so the ball is safe
  to run from inside a live engine turn.

  Standing today: **22 held · 15 absent · 0 broke**. The fifteen absences are
  fourteen cutters plus one Rust stroke whose read-only oracles
  (`estate\`, `secondbrain\`) are not in this ground. Their goldens are all
  here and green; what is gone is the ability to re-cut them and to notice
  the source drifting. That is a ruling for the operator — restore the
  grounds read-only, or retire those cutters with the goldens frozen as the
  authority. Substituting anything would break law 2 outright.

  `tests/PROVING.md` is the map: every leg, what it costs, what it needs,
  and the seventeen packages that carry no prover at all — `internal/tools`
  first among them, where every MCP tool handler lives.

### Fixed
- **`internal/rack` had been red since the repo split.** Four strokes wanted
  `tests/fixtures/rack_open_ground/state/rack_ledger.jsonl`. Git does not
  track empty directories, so the fixture ground came over empty in the H0
  pull and nothing said a word. The right fix was not a hand-written file
  but running the cutter that owns it — `tools/cut_rack_open_vectors.py`
  builds that ground by definition — after which the five tracked goldens
  judged it byte-exact.

- **The door battery had no binary to shell.** `TestDoorProveStrokesGreen`
  drives `cmd/atlas-door` against the Rust spine over a real loopback
  socket, and the Rust binary was never built in this ground. `cargo build
  -p atlas`. The prover had been behaving correctly the whole time —
  refusing by name rather than fabricating, exactly as law says.

- **`cut_flow_vectors.py` was behind its own fixture, and would have eaten
  it.** `ce9c390` added the `run` node kind to the flow contract and updated
  `flow.go` *and* `flow_vectors.json` — but not the cutter that owns the
  fixture. So `--verify` had been red since; worse, running the cutter
  *without* `--verify` would have rewritten the fixture, stripped `run` back
  out, and turned `internal/flow` red with no visible cause. The cutter now
  carries the seven-kind contract and refuses a `run` node with no
  objective, exactly as `flow.go` does. A full re-cut is now a no-op. (The
  seventh refusal's keys also sort like every other entry now — the giveaway
  that it had been hand-added rather than cut.)

### Note
- Static assets are compiled into the binary (`//go:embed static/...`), so a
  change under `static/` needs `go build -o atlas-webapp.exe .` and a restart
  before it reaches the glass. Editing the file alone does nothing.

## [0.1.1+f1] — 2026-09-08

### Added
- **E2E test suite**: 84 scenarios across 12 categories
  - S1: Binary Smoke (5), S2: MCP Tool Surface (8), S3: Write Tools (5)
  - S4: Mesh B2 (8), S5: Rack F1 (10), S6: Guard (5), S7: Tenant (4)
  - S8: Ollama Integration (10), S9: Webapp (6), S10: Cross-Impl (4)
  - S11: Agent Lifecycle (6), S12: Prove Chains (3)
- **6 CI/CD pipelines** (parallel jobs in ci.yml)
  - SPINE: Rust core (12 stages), LINE: Go MCP (11 stages)
  - GOLDEN: Python verifiers (11 stages), AGENT: 40-seat validation (11 stages)
  - WEBAPP: GUI + API (18 stages), OLLAMA: Live integration (14 stages)
- **6 agent workflows** with Python scripts
  - SCOUT: read-only survey (5 steps)
  - STEWARD: memory + testimony via Ollama (5 steps)
  - MESH: encrypted communication (7 steps)
  - GATE: injection blocking, PII stripping (5 steps)
  - TOWN: task scheduling (4 steps)
  - OPERATOR: full lifecycle (12 steps)
- **Ollama prover**: stdlib-only Python harness
  - Tests 11 models (qwen3.5, llama3.2, phi4-mini, gemma4, deepseek-r1, etc.)
  - Direct Ollama API + MCP integration + webapp API
  - JSON output, exit codes, timeout handling
- **Documentation**: PIPELINES.md, WORKFLOWS.md, OLLAMA_PROVER.md, ACCEPTANCE.md, E2E_SCENARIOS.md

### Changed
- `ci.yml` expanded from 1 pipeline to 6 parallel pipelines
- `generate` calls use chat API for thinking-model compatibility (qwen3.5)

## [0.1.0+f1] — 2026-09-08

### Added
- **Rust core**: prov-hash, ground-prove, atlas-api, store crates
- **Go MCP server**: 25 tools + HTTP transport + embedded GUI (port 8090)
- **Go TUI**: Dashboard, traces, agents, chain view, mesh, rack, format output
- **Go webapp**: Observability GUI with real-time SSE (port 8091)
  - Dashboard with stats, recent traces, agent roster
  - Agent registry with full .us declaration viewer
  - Trace log with SHA-256 hash chain
  - Tool surface with JSON argument invocation
  - Evaluations engine with pass/fail scoring
  - Message bus with Discord/Slack/WhatsApp adapters
  - Settings for MCP connection, eval thresholds, provenance
  - Search across agents and traces
- **Agent system**: 40 .us declarations validated, enrolled, documented
- **Skills**: prove, orient, enroll
- **Python verifiers**: cut_canon_vectors, cut_chain_verdicts, cut_us_vectors, fold_agents
- **TUI extractField**: Auto-find array field when `*` hits a map
- **YAML format**: Fixed `[]map[string]any` to `[]any` for type switch compatibility

### Governance
- `can_approve: false` structural enforcement across all 40 agents
- Covenant hash `1512741580b7239b` verified in all declarations
- Append-only witnesses: SEAT_LOG.md + STATE_OF_BUILD.md
- Forbidden verbs absent by construction
- Zero external dependencies enforced

### Documentation
- 54+ specification and design documents
- 40 agent documentation files with hierarchy index
- 3 skill documentation files
- GUI gap analysis (Atlas vs Langfuse/Langsmith)
- Build plan with phased acceptance criteria
- MIT License
- Contributing guide
- Full changelog

### Tests
- 92 Go tests (line workspace)
- 85 Rust tests (cargo test --workspace)
- 4 Python verifiers
- MCP 58-stroke prove
- TUI end-to-end verification against live MCP
- Agent enrollment validation (40/40)

### Fixed
- extractField: `agents.*.name` transform path now works correctly
- extractField: Auto-discovers first array-valued field when `*` encounters a map
- YAML format: `[]map[string]any` changed to `[]any` in rbac/agents list handlers
- TUI help: Changed `*.name` example to `name`
