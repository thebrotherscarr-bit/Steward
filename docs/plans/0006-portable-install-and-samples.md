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
- [ ] P1 portability fixes from the audit (Lanes A and B; consumes the audit, not yet written).
- [ ] P2 the model as a binding (Lane A; O1, O2).
- [ ] P3 one installer (Lane B).
- [ ] P4 first-run setup, the doctor, and the one-case proof (Lane B, with Lane A for `steward doctor`; O3, O4).
- [ ] P5 optional pieces off by default (Lane B; O5).
- [ ] P6 the clean-machine test in CI (Lane B; O6).
- [ ] P7 STEW samples 01 to 05 (the STEW repository).
- [ ] P8 Steward's declarations migrated to STEW `.us` (Lane A; ADR-0019's migration steps 1 to 4, 6 and 7).

## Surprises & Discoveries

- Observation: the portability audit named as this plan's first input (the SecondBrain note "Portability audit
  (2026-11-08)", ADR-0019 decision 5) did not exist when this plan was written.
  Evidence: a search of the notes for "Portability audit" on 2026-11-08 returned no such note. P1 therefore begins by
  reading it once it exists and is left as a placeholder milestone until then.
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
