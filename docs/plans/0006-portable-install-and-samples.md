# Portable install and samples

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and
`Outcomes & Retrospective` must be kept up to date as work proceeds.

This document is maintained in accordance with `.agent/PLANS.md` at the repository root. It carries out
[ADR-0020](../decisions/0020-portable-by-design.md) ("Portable by design: one installer, one config, the model as a
binding, a doctor, and a clean-machine test") and the migration steps of
[ADR-0019](../decisions/0019-steward-implements-stew.md) ("Steward implements STEW"). Its eval duties follow
[ADR-0012](../decisions/0012-stewards-bar-is-our-own-capability-evals.md); its capabilities are O1 to O6 in
[spec 001](../specs/001-capability-evals.md) and `harness/steward/evals/capabilities.yaml`. Its place in the order of
all work is [ARCHITECTURE.md](../ARCHITECTURE.md), section 6: after ExecPlan 0005's M0 and the profile mechanism
(MP), before the rest of ExecPlan 0005's M1 to M10.

## Purpose / Big Picture

The operator, 2026-11-08: "This system needs to be open enough to be placed on another system and function from
anywhere... installed on a friends PC... it 'just works'. simplicity is key." And: "We need a minimum failure point
for portability and deployment."

After this plan, a person with a Windows PC that has never seen this Estate can download one zip (SecondBrain's
release), install one outside thing (a local model runtime such as Ollama), unzip, and run SecondBrain.exe. A first-run
setup finds the runtime, suggests a model that fits their hardware, pulls and binds it on their yes, writes one
config file, and runs one small eval case as proof that Steward works on their machine. If anything is missing, a
doctor says what is missing and how to fix it, one line each. Someone who wants to build their own agent instead of
running Steward follows five short STEW samples, the way MAF's getting-started samples teach MAF.

To see it working: on a clean Windows machine with Ollama installed, unzip the release, run SecondBrain.exe, accept
the suggested model, and observe the setup end with "Proof: 1 of 1 passed on <model>". Then run `steward doctor` from
the install folder and observe every line `ok` and exit code 0. Stop Ollama and run it again: observe one line naming
the runtime as unreachable and how to start it, and a non-zero exit code.

## Progress

- [x] (2026-11-08) ADR-0020 and this plan written; capabilities O1 to O6 added to the map and spec 001 (untested, not
  required); ARCHITECTURE.md section 6 places this plan after M0 and MP, before M1 to M10's remaining items.
- [x] (2026-11-08) P1 step 1: the audit (SecondBrain note `portability-audit-2026-11-08-8af9d1`) read; its Steward
  entries copied below and into P1, one line each, by the audit's own numbers. Jesster's entries are Lane B's.
- [ ] P1 portability fixes from the audit (Lanes A and B). Steward's entries, each fixed in P1 or owned by the milestone named:
  - [x] (2026-11-08, Steward PR p1-config-entries) A4 `recipe_workflow.estate_repos`: the Estate's repositories hard-wired under the ground (P1: from the ground entry, A7).
  - [x] (2026-11-08, p1-config-entries: `STEWARD_BASH`) A5 `agent._build_shell`: Git Bash at `C:\Program Files\Git\bin\bash.exe`, hard-coded (P1: a config entry).
  - [ ] A6 `agent.ARCHIVE_DIR`: the operator's Archive bound inside the product (P8, ADR-0019 step 4: the bounds' paths to runtime config).
  - [x] (2026-11-08, p1-config-entries: `STEWARD_GROUND_DIR`) A7 `agent.GROUND_DIR` and `mcp_app.recipe_tools`: the ground inferred from the folder layout (P1: an explicit optional entry).
  - [x] (2026-11-08, p1-config-entries) A8 `agent._WORKING_DIR`: `STEWARD_WORKSPACE` defaults to the repository, unsaid (P1: said in `.env.example`).
  - [x] A14 halo and eval storage paths are repository-relative (no change: already portable).
  - [x] (2026-11-08, p1-config-entries: `STEWARD_OWNER`) B1 the operator's name in model-facing text (`steward.py` INSTRUCTIONS, `agent.SANDBOX_SHELL_REFUSAL`) (P1: an owner entry).
  - [x] (2026-11-08, p1-config-entries: `STEWARD_OWNER`) B6 the operator's name in the improvement loop's review prompt (P1: the owner entry).
  - [x] B7 LICENSE names the operator (docs; no change).
  - [x] B8 README clones the operator's repository (docs; no change).
  - [x] (2026-11-08, p2-binding) C1, C2 the model's defaults disagree (`steward.py` gpt-oss:20b; `improvement_loop.py`, step02 steward:1) (P2: the binding).
  - [ ] C3 `steward:1` is built by hand from `steward.Modelfile` (P2 binds it; P4's setup pulls or builds the bound model).
  - [x] (2026-11-08, p2-binding) C4 the context window 65536 in code (`_STEWARD_CONTEXT`, the compaction budget) (P2: the binding).
  - [ ] C5, C6 the code embedder's name and `num_gpu` 0 in code, code search on by default (P5: an optional piece).
  - [ ] C7 step02's mem0 embedder `nomic-embed-text-v2-moe` in code (P5: automatic memory is an optional piece).
  - [x] (2026-11-08, p2-binding) C12 the reasoning option (`think`) sent whatever the model offers (P2: only when the binding provides it).
  - [ ] C13 the VRAM assumption in comments only, never checked (P4: the doctor).
  - [ ] C15 the eval baselines are measured on `steward:1` only (P8, ADR-0019 step 6: results recorded per binding).
  - [ ] D1 the Python version said four ways (P3: one version, checked by the installer).
  - [ ] D2 the README installs unlocked from PyPI (P3: the installer uses the lock).
  - [x] (2026-11-08, p1-config-entries: `STEWARD_MCP_PORT`) D7 `mcp_app.PORT` 43121 cannot be overridden (P1: a config entry).
  - [x] (2026-11-08, Steward PR p1-share-env; Jesster PR #108) D9 the MCP key pasted by hand into `.env` (P4, Lane B: SecondBrain passes it in the child environment). SecondBrain passes `SECONDBRAIN_SHARE_URL` and `SECONDBRAIN_SHARE_KEY` while sharing is on; Steward reads them when `SECONDBRAIN_MCP_URL` and `_KEY` are unset (`install.secondbrain_mcp`).
  - [x] D12 Hyperlight's packages imported unconditionally (no change: they are in the lock; opt-in at run time).
  - [ ] D16 README step 5 starts `hosted.py`, though SecondBrain starts AG-UI itself (P3: the install's README).
  - [ ] E1 the Charter is not shipped; a missing note runs him without it, silently (P4 and P5: a shipped default).
  - [ ] E2 SecondBrain's MCP is effectively required yet only warned about (P4: the doctor fails loudly). (2026-11-08, p1-share-env: Steward now finds it from SecondBrain's share names without `.env`; the doctor's loud failure is still P4.)
  - [ ] E3 code search on by default needs the embedder pulled (P5, with C5).
- [ ] P2 the model as a binding (Lane A; O1, O2). Built 2026-11-08 (Steward PR p2-binding): `binding.us`, read by
  `install.py`; `requires` on every profile; the router's refusal; T3 `install` v1 with O1 and O2 required.
  Pending the operator's approval: the live run of T3 `install` (`evals.py install`), and the gating sets on
  `steward:1` after the change; each `min_context` measured (it is null, "to be measured", until then); a restart
  of Steward's hosts to load it.
- [ ] P3 one installer (Lane B).
- [ ] P4 first-run setup, the doctor, and the one-case proof (Lane B, with Lane A for `steward doctor`; O3, O4).
- [ ] P5 optional pieces off by default (Lane B; O5).
- [ ] P6 the clean-machine test in CI (Lane B; O6).
- [ ] P7 STEW samples 01 to 05 (the STEW repository).
- [ ] P8 Steward's declarations migrated to STEW `.us` (Lane A; ADR-0019's migration steps 1 to 4, 6 and 7).
  - [x] (2026-11-08, Steward PR p8-stew-validator-ci) Step 1: the gate's `stew` step validates every tracked `.us`
    file with STEW's `tools/validate.py`, STEW checked out at `aec5527ebe25c366057674b558e31e6a5e284881`. Wire: a
    throwaway pull request adding an invalid `.us` file turned the gate red, and was closed unmerged.

## Surprises & Discoveries

- Observation: the portability audit named as this plan's first input (the SecondBrain note "Portability audit
  (2026-11-08)", ADR-0019 decision 5) did not exist when this plan was written.
  Evidence: a search of the notes for "Portability audit" on 2026-11-08 returned no such note. P1 therefore begins by
  reading it once it exists and is left as a placeholder milestone until then.
  (2026-11-08, later: the audit exists, note `portability-audit-2026-11-08-8af9d1`; P1's entries are copied from it.)
- Observation: the audit found very few literal host paths in Steward. Most of the risk is in layout assumptions (the
  ground beside him, Git Bash's folder), the model named in code, and steps done by hand.
  Evidence: the audit's sections A to E; `git grep` for the operator's user folder and `Desktop\Research` in Steward's
  code finds only comments, docstrings, tests and one bound (`ARCHIVE_DIR`, A6). A scan of the string literals in his
  code (comments and docstrings aside) found two more the audit had not listed: the door's description of the ground
  (`agent.ESTATE_WORLDS`, "Desktop\Research") and step02's mem0 scope `"kyle"`; both moved in P1.
- Observation: MAF's Python samples are no longer under `python/samples/getting_started/`; they are a numbered ladder.
  Evidence: microsoft/agent-framework at commit `924a6e5`, `python/samples/`: `01-get-started/`, `02-agents/`,
  `03-workflows/`, `04-hosting/`, `05-end-to-end/`; `01-get-started/` holds `01_hello_agent.py` to
  `07_hosting.py`. P7's ladder follows that layout.

## Decision Log

- Decision: Steward is portable by one installer, one config, the model as a binding, a doctor with a one-case proof,
  optional pieces off by default, a clean-machine test, and STEW samples.
  Rationale: the operator's "minimum failure point"; recorded in ADR-0020.
  Date/Author: 2026-11-08, Kyle.
- Decision: this plan runs after ExecPlan 0005's M0 (the trust bar through profiles) and MP (the profile mechanism),
  and before the rest of M1 to M10.
  Rationale: P2 and P8 build on the profile mechanism (a profile's `requires` and its `.us` form need the profiles to
  exist), and every milestone after it should be built portable rather than fixed later.
  Date/Author: 2026-11-08, in the plan (the lead's ordering, from the operator's "write up the spec and the docs and the
  plan, and then begin implementing").
- Decision: the samples ladder cites MAF's current layout, `python/samples/01-get-started/`.
  Rationale: the older `getting_started/` path no longer exists upstream.
  Date/Author: 2026-11-08, in the plan.
- Decision: P1 takes only the audit's entries that are a value moved to config or a path computed from the install
  folder (A4, A5, A7, A8, B1, B6, D7). Every other Steward entry is owned by the milestone named on its line in
  `Progress`. Comments and docstrings that quote a dated ruling by the operator's name stay: they are the record.
  Rationale: the plan's P1 is "each value moves to a config entry or a computed path"; the others are an installer,
  a doctor, an optional piece or a format migration, which are P2 to P8.
  Date/Author: 2026-11-08, Lane A.
- Decision: P1's entries are environment entries read in one module, `harness/steward/install.py` (`STEWARD_OWNER`,
  `STEWARD_BASH`, `STEWARD_GROUND_DIR`, `STEWARD_MCP_PORT`), documented in `.env.example`, each with today's value as
  its default; a relative path is read against the install folder (the repository's root). The owner's default stays
  "Kyle", today's value, so nothing changes on this PC; P4's setup asks a new install for its owner.
  Rationale: `.env` is the one config Steward reads today; STEW has no `install` kind yet, so P4 folds these entries
  into the install's `.us` declaration when it has one. One module is the one place each is read.
  Date/Author: 2026-11-08, Lane A.
- Decision: the binding is `binding.us` at the install folder's root (a STEW `kind: binding` declaration, STEW's
  reference binding for this PC), or the file `STEWARD_BINDING` names. It is tracked: on this PC it is the config, and
  P4's setup rewrites it in a new install. When a host starts, the binding's model and endpoint replace
  `OLLAMA_MODEL` and `OLLAMA_HOST` in the process (MAF's Ollama clients read those), so the binding wins over an
  older `.env`; a different value is logged once. `api: openai-compatible` is refused by name until Steward has that
  client (P4).
  Rationale: O1, the binding is the only place the model is named; one file, read in one place, with no code change
  to change the model. MAF's clients already read the environment, so no client construction changes.
  Date/Author: 2026-11-08, Lane A.
- Decision: every profile gains `requires: {tool_calling, min_context, reasoning_effort}`. `tool_calling` is true
  when it offers tools (STEW spec/profile.md 7a); `min_context` is null, "to be measured" (no number guessed, and
  nothing is checked for it until it is measured); `reasoning_effort` is false, since a profile's `reasoning` is
  sent only when the binding provides the knob (STEW spec/binding.md rule 3). The profiles keep version 1: adding
  the member is a schema step that changes no run on this PC's binding, and their histories continue.
  Rationale: the operator's word to use a placeholder for context and not guess; spec 002's "any change is a new
  version" is for a change to what a profile does, and this one does nothing on `steward:1`.
  Date/Author: 2026-11-08, Lane A.
- Decision: O1 and O2's eval cases are T3 `install` v1 (standins runner). A standins case may name a `binding:`
  file to run under (evals.py, `install.using_binding`), so the O1 case measures the refusal on a binding without
  tool calling. Both capabilities are required; the set's live run waits for the operator's word.
  Rationale: ADR-0012 (every capability ships with its case); the operator's instruction that no live run is made
  while he is using the PC.
  Date/Author: 2026-11-08, Lane A.
- Decision: P8 step 1 is a step in the existing `gate` job (`.github/workflows/gate.yml`, step `stew`), not a job of
  its own. STEW is checked out by `actions/checkout` at a full commit sha (no branch or tag) into `.stew/`, untracked,
  and its validator is given every file `git ls-files "*.us"` lists; no tracked `.us` file is a failure. The step runs
  after `compile` and before `install`, since the validator is standard library only. The first pin is STEW main
  `aec5527` (2026-11-08); a bump is a change of its own.
  Rationale: `gate` is the check main's protection already requires, so a step in it gates the merge with no change
  to the protection; a full sha cannot move under the gate; `git ls-files` takes each new `.us` file with no list to
  keep.
  Date/Author: 2026-11-08, Lane A.

## Outcomes & Retrospective

None yet.

## Context and Orientation

Three repositories are involved. This one, Steward (`worlds/steward` on the operator's PC, GitHub
`thebrotherscarr-bit/Steward`), is a Python agent built on Microsoft Agent Framework (MAF). His harness code is under
`harness/steward/step04_production_ready/`; his eval sets and capability map are under `harness/steward/evals/`; the
validator is `harness/steward/step04_production_ready/evals.py validate`; his harness profiles are under
`harness/steward/profiles/`, read by `profiles.py`. His Python packages are pinned in `pyproject.toml` and
`requirements.lock`. His model today is `steward:1`, built in Ollama from `steward.Modelfile` over gpt-oss:20b.

Jesster (GitHub `thebrotherscarr-bit/Jesster`, the app named SecondBrain) is an Electron app in its `secondbrain/`
folder. Its release workflow, `.github/workflows/secondbrain-release.yml`, builds on a Windows runner and publishes
`SecondBrain-win32-x64.zip`; its instructions today are "unzip it anywhere, run SecondBrain.exe". SecondBrain talks to
Steward over AG-UI on 127.0.0.1:43122 (`secondbrain/electron/agent/agui.cjs`) and finds his folder through
`STEWARD_DIR` or a folder beside its own source.

STEW (GitHub `thebrotherscarr-bit/STEW`, MIT) is the open spec drawn from Steward: declarations in files with the
`.us` extension, each with a `kind` (`profile`, `task`, `eval`, `board`, `record`, and the binding of a model). A
**binding** is the record of which local model an install uses and how to reach it (model name, endpoint, context
window). A profile's **`requires`** says what a model must offer for the profile to run.

Terms used below. The **install folder** is wherever the user unzipped the release. The **config** is the one `.us`
file the first run writes in the install folder. The **doctor** is a set of checks, each printing `ok` or one line
saying what failed and how to fix it. The **proof case** is one small gating eval case run once on the bound model.
The **friend test** is the clean-machine job in CI. A **lane** is a stream of work owned by one hand: Lane A,
Steward's core (binding, declarations); Lane B, Jesster (installer, setup, doctor, CI); the STEW repository (samples);
Lane C, the plan keeper (this plan, the ADRs, the capability map); and the lead, who reviews, installs builds and runs
one eval at a time (full sets overnight, on the operator's word).

## Plan of Work

Each milestone is one or more pull requests, each with its wire (what goes red if it is unplugged) and, where it gives
Steward a capability, its eval case (ADR-0012). The milestones are in order: each later one stands on the ones before.

### P1. Portability fixes from the audit

The audit (ADR-0019 decision 5) lists every hard-coded path, user name, account, port and model name in Steward and
Jesster, and names the config entry that replaces each. It is a list, not a change. This milestone is a placeholder
until the audit exists: its first step is to read the SecondBrain note "Portability audit (2026-11-08)" and copy its
entries, grouped by repository, into this section and into `Progress` as one line each. Then each entry is fixed in
its own small pull request: the value moves to a config entry (with today's value as its default) or to a path
computed from the install folder. Lane A takes Steward's entries, Lane B Jesster's. Acceptance: a search of both
repositories for the audit's strings (for example the operator's user folder, `Desktop\\Research`, a host name) finds
none outside the config's defaults, tests and docs; every gating eval set still passes on this PC.

The audit's Steward entries (2026-11-08, note `portability-audit-2026-11-08-8af9d1`, by its own numbers; the milestone
that fixes each is on its line in `Progress`):

- A4: `recipe_workflow.py` `estate_repos`: the Estate's repositories hard-wired as `<ground>/worlds/steward` and the rest.
- A5: `agent.py` `_build_shell`: Git Bash at `C:\Program Files\Git\bin\bash.exe`, hard-coded.
- A6: `agent.py` `ARCHIVE_DIR`: `~/Desktop/Archive`, the operator's own bound, inside the product.
- A7: `agent.py` `GROUND_DIR` and `mcp_app.py` `recipe_tools`: the ground inferred from a parent folder named `worlds`
  or a `manjuel.py` two levels up.
- A8: `agent.py` `STEWARD_WORKSPACE` defaults to this repository; `.env.example` does not say so.
- A14: the halo and eval storage paths use `parents[N]` inside the repository (portable already).
- B1: the operator's name in text the model reads: `steward.py` INSTRUCTIONS and `agent.py` `SANDBOX_SHELL_REFUSAL`.
- B6: the operator's name in the improvement loop's review prompt (`improvement_loop_workflow.py`).
- B7: LICENSE names the operator (a document).
- B8: the README's install clones the operator's repository (a document).
- C1, C2: the model's defaults disagree: `steward.py` gpt-oss:20b; `improvement_loop.py` and step02 steward:1.
- C3: `steward:1` must be built by hand (`ollama create steward:1 -f steward.Modelfile`).
- C4: the context window 65536 in code (`_STEWARD_CONTEXT`, the options and the compaction budget).
- C5, C6: the code embedder `embeddinggemma-2:270m` and its `num_gpu` 0 in code; code search on by default.
- C7: step02's mem0 embedder `nomic-embed-text-v2-moe` in code.
- C12: gpt-oss's reasoning option (`think`) is sent whatever the model offers.
- C13: the 16 GB card is assumed in comments only; nothing checks VRAM.
- C15: the eval baselines are measured on `steward:1`.
- D1: the Python version is said four ways (`.python-version`, CI, `pyproject.toml`, the README).
- D2: the README's `pip install -e .` resolves from PyPI; the gate installs the lock.
- D7: `mcp_app.py` `PORT` 43121 cannot be overridden.
- D9: SecondBrain's MCP key is pasted into `.env` by hand.
- D12: Hyperlight's packages are imported unconditionally (they are in the lock; the sandbox is opt-in).
- D16: README step 5 starts `hosted.py`, though SecondBrain starts the AG-UI host itself.
- E1: the Charter is not shipped; without the note he runs without it, with only a warning.
- E2: SecondBrain's MCP is effectively required, yet he starts without it and only warns.
- E3: code search is on by default and needs the embedder pulled.

### P2. The model as a binding

Today the model name, endpoint and options (`OLLAMA_OPTIONS`, the Modelfile name) are in Steward's code. After P2 they
are read from the binding in the config (ADR-0019 migration step 5). Each profile gains `requires` (the context window
its cases pass with, measured, not guessed; tool calling; reasoning), and the run refuses a profile whose `requires`
the binding does not meet, naming what is missing. This PC's config binds `steward:1`. Capabilities O1 (the binding
is the only place the model is named) and O2 (one config, relative paths, no host names). Acceptance: changing the
binding's model in the config changes the model every call uses, with no code change; a binding with a smaller
context window than a profile requires is refused with a one-line reason; the gating sets pass on `steward:1`.

### P3. One installer

Jesster's release workflow adds Steward to the zip: this repository at a pinned commit (its code, `pyproject.toml`
and a `uv.lock` generated from it), and the uv executable. On first run SecondBrain runs `uv sync --frozen` in the
install folder's Steward copy to build his Python environment there, and starts him from it. SecondBrain finds Steward
inside its install folder first, `STEWARD_DIR` second. Acceptance: on a machine with no Python and no clone, the
unzipped release starts Steward and the AG-UI port answers; the zip's size and the first-run build time are recorded
in `Artifacts and Notes`.

### P4. First-run setup, the doctor, and the one-case proof

SecondBrain gains a first-run setup: find the runtime (Ollama on its default port, or an OpenAI-compatible endpoint the
user names), read the hardware (GPU memory, system memory), suggest a model that fits (informative; the user may pick
another), pull and bind it on the user's yes, check the ports, write the config, ask for keys in the app only for
pieces turned on, and run the proof case. The doctor is the same checks, from the app and from `steward doctor` in the
install folder, with exit code 0 only when all pass. Every failure is one line: what failed, how to fix it.
Capabilities O3 (the doctor) and O4 (the one-case proof). Acceptance: the transcript in `Purpose / Big Picture`,
including the failing doctor run with Ollama stopped; each check has a test that makes it fail and reads its line.

### P5. Optional pieces off by default

Telegram, WhatsApp, the sandbox, Aurora (the glass), the door's forwarded tools and the notes kernel start off in a
new install. Each has a switch in the app; turning one on asks for what it needs then and adds its checks to the
doctor. Capability O5. Acceptance: a new install with all of them off passes the doctor and the proof case; turning
Telegram on without a token makes the doctor name the missing token and nothing else.

### P6. The clean-machine test in CI

A job in Jesster's release workflow, on a clean `windows-latest` runner, downloads the built zip, unzips it, installs
Ollama, runs the setup non-interactively with a small CPU model bound (a CI binding, named in the job), runs the doctor
and the proof case, and fails the release if any step fails. Capability O6. Acceptance: the job is green on a good
build, and red on a build where the zip leaves out Steward's lock file (proved once by a pull request that removes it
and is then closed).

### P7. STEW samples 01 to 05

In the STEW repository, a `samples/` ladder after MAF's `python/samples/01-get-started/` (commit `924a6e5`: numbered
files, each one idea, a README table of steps): `01` one profile and one task, `02` a board with two hats, `03` evals
as proof, `04` a card from the phone, `05` an automation. Each runs on any small local model through a binding, with
its own README. Steward is the full reference implementation and is named in the ladder's README as such. Acceptance:
each sample runs from a fresh clone of STEW on a small local model and prints its expected result, and STEW's CI runs
the validator over every sample's declarations.

### P8. Steward's declarations migrated to STEW `.us`

ADR-0019's migration, one pull request per step: STEW's validator in Steward's CI (step 1); the profiles as `.us`
(step 2); eval sets as `kind: eval` (step 3); the board (step 4); records in the board's ledger (step 6); tasks and
orchestration (step 7). Step 5, the binding, is P2. Acceptance: Steward's CI validates every `.us` file against STEW's
pinned validator, every case and its history are kept through each step, and the gating sets pass as before.

## Concrete Steps

From the root of this repository, before and after every pull request of this plan:

    timeout 300 python harness/steward/step04_production_ready/evals.py validate

Expected: no problems listed, and the untested ids listed include O1 to O6 until their cases land. Each milestone's
own commands are written here as it starts.

## Validation and Acceptance

The plan is done when the friend test (P6) is green on a release, the doctor and the proof case pass on this PC's
`steward:1` binding and on the CI binding, O1 to O6 are each covered by a case and required, and STEW's samples 01 to 05
run on a small local model.

## Idempotence and Recovery

The setup and the doctor can be run any number of times: the setup rewrites the config only on the user's yes, and the
doctor only reads. A failed first-run environment build is retried by deleting the install folder's Steward
environment folder and starting SecondBrain again. Each pull request is small and can be reverted alone.

## Artifacts and Notes

None yet.

## Interfaces and Dependencies

uv (the Python package and environment manager) builds Steward's environment from `uv.lock`. Ollama, or any runtime
serving the OpenAI-compatible chat API on loopback, serves the bound model. STEW's `validate.py`, pinned to a STEW
commit, checks every `.us` file. The config's exact members are STEW's (`spec/binding.md` for the binding); a member
Steward needs that STEW does not have goes under an `x-` member first and to STEW as an enhancement proposal.
