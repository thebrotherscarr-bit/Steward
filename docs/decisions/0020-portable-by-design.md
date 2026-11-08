---
status: accepted
contact: Kyle
date: 2026-11-08
deciders: Kyle
---

# Portable by design: one installer, one config, the model as a binding, a doctor, and a clean-machine test

Accepted on the operator's word of 2026-11-08 (quoted below). It carries out
[ADR-0019](0019-steward-implements-stew.md) ("Steward implements STEW") on the side of the install: where 0019 says
what Steward's formats become, this record says how a person who is not on this PC gets Steward running. It keeps
[ADR-0002](0002-one-model-for-everything.md)'s "one model" per install, as ADR-0019 amended it, and adds nothing to
[ADR-0018](0018-harness-profiles-per-task-tuned-by-evals.md)'s profile beyond the `requires` member ADR-0019 already
gives it.

## Context and Problem Statement

The operator, 2026-11-08: "We need a minimum failure point for portability and deployment, what is the best path
forward for doing this?" Then: "we can set it up with the smallest model we need to run the stuff, Steward is just a
partially rolled version of gpt-oss. If someone has different hardware and all that, we shouldnt be locking them into
this exact setup, the idea is that anyone anywhere can use this spec for their local hardware and harnessing needs,
kind of the way that MAF gives you all the pieces, and doesnt actually show you the agent, just kind of tells how its
supposed to work, and you make it your own on your hardware." And, on the plan proposed: "I like this idea... MAF
gives examples of the setup, we need to do the same, I think it would be smart to write up the spec and the docs and
the plan, and then begin implementing. You have my 'go'".

His standing rule of the same day (#remember): "STEW spec and .us declarations are to be implemented, utitlized, and
proven within this harnessing framework for Steward and any agent deployed within this harness. This system needs to
be open enough to be placed on another system and function from anywhere... installed on a friends PC... it 'just
works'. simplicity is key."

Today Steward runs on one PC. He is a clone of this repository (`worlds/steward`) with a Python environment built by
hand from `requirements.lock`, beside SecondBrain (the Jesster repository, an Electron app released as
`SecondBrain-win32-x64.zip`), which finds him by a folder next to its own source or by `STEWARD_DIR`. His model is
`steward:1` (the `steward.Modelfile` over gpt-oss:20b, about 11.9 GB of VRAM on a 16 GB GPU), named in code. His
ports (AG-UI on 127.0.0.1:43122, the door on 43111), the Ollama endpoint and many paths are written into the code of
both repositories. Nothing checks, on a new machine, that the pieces are present, and when one is missing the failure
is somewhere deep in a run. How does a friend, with different hardware and nothing of this PC, get Steward working
with the fewest places it can fail?

## Decision Drivers

- His words above: "minimum failure point"; "it 'just works'"; "simplicity is key".
- Not locked to this PC's hardware or model: the smallest model that runs the work, chosen for the machine.
- STEW and `.us` declarations implemented and proven here ([ADR-0019](0019-steward-implements-stew.md)), so the
  install's own configuration is a STEW declaration too.
- MAF's way: MAF ships the pieces and a numbered ladder of small samples, not a finished agent
  ([microsoft/agent-framework `python/samples/`](https://github.com/microsoft/agent-framework/tree/main/python/samples),
  commit `924a6e5`: `01-get-started/` with `01_hello_agent.py`, `02_add_tools.py`, `03_multi_turn.py`,
  `04_memory.py`, `05a` to `05c` workflows, `06_agent_harness.py`, `07_hosting.py`; then `02-agents/`,
  `03-workflows/`, `04-hosting/`, `05-end-to-end/`).
- Evals decide ([ADR-0012](0012-stewards-bar-is-our-own-capability-evals.md)): an install is proven by an eval case
  passing on it, not by its files being present.
- Keys are his: never written by an installer into a file a hand reads, never printed (the ground's RULE 7).
- One release to download, one thing outside it to install.

## Considered Options

- **A. Portable by design:** one installer (SecondBrain's release carries Steward), one config file written at first
  run as a STEW declaration, the model as a binding, a first-run setup with a doctor and a one-case proof, optional
  pieces off by default, a clean-machine test in CI, and STEW samples as the examples.
- **B. Document the manual setup** (a README with the clone, the Python environment, Ollama and the model), and leave
  the code as it is.
- **C. A container image** carrying Steward, Python and the runtime.

## Decision Outcome

Chosen option: **A, portable by design**, because it is the only option where a failure has one place to show
(the doctor) and one way to be proven absent (the one-case proof and the clean-machine test). B leaves every
hard-coded path in place and makes every step a place to fail by hand. C is ruled out by the operator's ruling of
2026-11-02 (no Docker) and would still need a GPU-aware
model runtime outside it.

1. **One installer.** SecondBrain's release zip carries Steward: his code (this repository at a pinned commit) and a
   uv lock file. On first run SecondBrain builds Steward's Python environment from that lock with uv, inside the
   install folder; there is no separate clone and no global Python packages. The one dependency outside the zip is a
   local model runtime: Ollama, or any runtime that serves the OpenAI-compatible chat API on loopback. uv itself is
   carried in the zip, so nothing is downloaded but the lock's own packages and the model.
2. **One config.** First run writes one file in the install folder: a STEW `.us` declaration of the install
   (`kind: install`, carrying its `binding`). Every path in it is relative to the install folder; it names no host
   name, no user, no account. Ports are entries in it with today's numbers as defaults. Keys are never in it: the app
   asks for them in its own window and keeps them in its own store. Everything that is hard-coded today and belongs to
   one machine (the portability audit, ADR-0019 decision 5) moves into this file or into a default computed from the
   install folder.
3. **The model is a binding.** A profile declares what it needs of a model (`requires`, ADR-0019: the context window
   its cases pass with, tool calling, reasoning); the config binds one local model to the install. First run reads the
   hardware (GPU memory, system memory) and suggests a model that fits; the suggestion is informative, and the user
   may bind another. `steward:1` (the gpt-oss-20b Modelfile) is the reference example binding, as STEW's
   `examples/bindings/steward-gpt-oss-20b.us`. ADR-0002's one model holds per install: one chat model bound, for
   every role. A profile whose `requires` the binding does not meet is refused by name, with what is missing.
4. **First-run setup and a doctor.** The setup is a short sequence in SecondBrain: find the runtime, bind and pull the
   model (on the user's yes), check the ports, write the config, ask for keys in the app (only for the pieces turned
   on), and run ONE tiny eval case on the bound model as the proof. The doctor is the same checks, runnable any time
   from the app and from the command line (`steward doctor`), with an exit code. Every failure names what failed and
   how to fix it, in one line each. The proof case is Steward's smallest gating case, run once; its pass is shown,
   with the binding it ran on.
5. **Optional pieces off by default.** Telegram, WhatsApp, the sandbox, Aurora (the glass), the door's forwarded tools
   and the notes kernel are off in a new install. Each is turned on in the app, asks for what it needs then, and adds
   its own checks to the doctor. A piece that is off never fails the doctor or a run.
6. **The friend test in CI.** A clean `windows-latest` runner downloads the release zip, unzips it, runs the setup
   non-interactively with a small CPU model, runs the doctor, and runs the one proof case. A red here blocks the
   release. The small model is a CI binding only; it proves the install, not Steward's bar.
7. **Samples, MAF's way.** STEW gets a `samples/` ladder in the STEW repository, after MAF's `01-get-started/`:
   `01` one profile and one task, `02` a board with two hats, `03` evals as proof, `04` a card from the phone, `05` an
   automation. Each runs on any small local model through a binding, and each is short enough to read in one sitting.
   Steward is the full reference implementation; the samples are the pieces, shown one at a time.

### Consequences

- Good, because a new install has one download, one outside dependency, one config file and one check that names any
  failure; the minimum failure point he asked for.
- Good, because the model is the user's choice on their hardware, and a profile proven on one binding is proven again
  on another by the same cases.
- Good, because the clean-machine test makes "it just works" a check that goes red, not a hope.
- Good, because the samples let someone build their own agent on STEW without taking Steward whole, as MAF lets one
  build without its demos.
- Neutral, because this PC keeps its setup: its config binds `steward:1`, and its ports keep today's numbers as
  defaults.
- Bad, because SecondBrain's release grows by Steward's code and uv, and its first run takes minutes to build the
  Python environment and pull a model.
- Bad, because the portability fixes touch both repositories in many small places; each is its own pull request and
  each must keep every eval case passing on this PC's binding.
- Bad, because a small CPU model in CI proves the install only; Steward's bar is still measured on a real binding at
  night (ADR-0006, ADR-0012).

## Validation

- The friend test (decision 6) is red when the release zip cannot install, set up, pass the doctor and pass the proof
  case on a clean runner; it gates the release.
- The doctor's checks each have a test that makes the check fail and reads its one-line fix.
- The capability map carries the install's capabilities (O1 to O6 in [spec 001](../specs/001-capability-evals.md)),
  each required in the pull request that lands its case.
- On this PC, every gating eval set passes as before on the `steward:1` binding after each step.

## Pros and Cons of the Options

### A. Portable by design

- Good, because each place a new install can fail is checked once, by the doctor, with its fix named.
- Good, because the install's config is a STEW declaration, so the spec is used where a stranger first meets it.
- Bad, because it is several pieces of work across two repositories (ExecPlan 0006).

### B. Document the manual setup

- Good, because nothing is built.
- Bad, because every hard-coded path, port and model stays, and a friend's PC fails where this PC does not.
- Bad, because nothing proves the document still works.

### C. A container image

- Good, because the Python environment is fixed in the image.
- Bad, because the operator ruled out Docker (2026-11-02), and a container still needs a model runtime with the GPU.

## More Information

- Carried out by [ExecPlan 0006](../plans/0006-portable-install-and-samples.md), milestones P1 to P8, ordered in
  [ARCHITECTURE.md](../ARCHITECTURE.md), section 6, after ExecPlan 0005's M0 and the profile mechanism.
- STEW: [github.com/thebrotherscarr-bit/STEW](https://github.com/thebrotherscarr-bit/STEW); its bindings,
  `spec/binding.md`.
- MAF's samples ladder: `python/samples/README.md` and `python/samples/01-get-started/` in
  [microsoft/agent-framework](https://github.com/microsoft/agent-framework) at commit `924a6e5`.
