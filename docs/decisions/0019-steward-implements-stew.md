---
status: accepted
contact: Kyle
date: 2026-11-08
deciders: Kyle
---

# Steward implements STEW

Accepted on the operator's word of 2026-11-08 (quoted below). It amends in part
[ADR-0002](0002-one-model-for-everything.md): one model holds per install, and the model becomes a binding in runtime
config. It also amends in part [ADR-0018](0018-harness-profiles-per-task-tuned-by-evals.md): the profile, case and
operation formats of specs 002 to 004 become STEW declarations, by the migration below. Everything else in both
stands.

## Context and Problem Statement

The operator, 2026-11-08: "The spec is STEW, the steward spec. .us declarations for easy of use and format. use what
existing protocal formats and outlines exist within the current open source commmunity. let's make sure this is going
to work, and be able to be forward-integrated as the spec gains momentum." And: "This is going to be released as a
standardized MIT spec for agent harnessing on local hardware, as a research project." His card choice: "Its own new
repo now (STEW, MIT, public)".

His standing rule of the same day: "going forward STEW spec and .us declarations are to be implemented, utitlized,
and proven within this harnessing framework for Steward and any agent deployed within this harness. This system needs
to be open enough to be placed on another system and function from anywhere. IE: It will be installed on a friends
PC, and he should be able to set it all up on his own hardware, and it 'just works'. simplicity is key."

And on models: "we can set it up with the smallest model we need to run the stuff, Steward is just a partially rolled
version of gpt-oss. If someone has different hardware and all that, we shouldnt be locking them into this exact
setup, the idea is that anyone anywhere can use this spec for their local hardware and harnessing needs, kind of the
way that MAF gives you all the pieces, and doesnt actually show you the agent, just kind of tells how its supposed to
work, and you make it your own on your hardware."

The spec is at [github.com/thebrotherscarr-bit/STEW](https://github.com/thebrotherscarr-bit/STEW), version
`2026-11-08-draft`. It was written from this repository's ADR-0012, 0014, 0016 and 0018 and specs 002 to 004, and it
names Steward and Jesster as its reference implementation. Steward's own formats today are YAML files of his own:
profiles, eval sets and capabilities. They name his model, and they assume this one PC. How does Steward become the
implementation of the spec that was drawn from him, so that it runs on another person's hardware?

## Decision Drivers

- His words above: STEW and `.us` declarations implemented, used and proven in this harness, for Steward and any
  agent in it, and portable to a friend's PC, where it "just works".
- Model-neutral: a declaration never names a model, and a profile states what a model must offer.
- The harness, not the model ([ADR-0002](0002-one-model-for-everything.md)): the profile mechanism
  ([ADR-0018](0018-harness-profiles-per-task-tuned-by-evals.md)) is what STEW standardizes, so it carries over
  unchanged in meaning.
- Evals decide ([ADR-0012](0012-stewards-bar-is-our-own-capability-evals.md)): a format change must not lose a case,
  a check or a result.
- MAF as it ships: STEW names the pieces and the rules and leaves the agent framework free. MAF stays Steward's
  framework.
- Small steps, each with a check that goes red when it is unplugged.

## Considered Options

- **A. Keep Steward's own YAML formats** and treat STEW as documentation beside them.
- **B. Steward implements STEW:** his profiles, tasks, eval sets and records become STEW declarations, his model
  becomes a binding in config, and he follows the spec's versions.
- **C. Adopt another declarative format**, such as MAF's declarative agents or Oracle's Open Agent Specification.

## Decision Outcome

Chosen option: **B, Steward implements STEW**. It is the only option that makes the spec proven by a running
implementation, as he asked ("implemented, utitlized, and proven"). It keeps ADR-0018's mechanism, and it makes the
install portable. A leaves two formats to drift apart. C describes agents and workflows, not per-task bounds, budgets,
cards or eval-gated promotion, so the harness would still need its own format beside it.

1. **The spec lives at github.com/thebrotherscarr-bit/STEW.** Steward implements the version his board declares in
   `supports`, and follows each new version by a pull request here. Experiments go under `x-` members first. A
   change Steward needs in the spec goes to the STEW repository as a STEW Enhancement Proposal, with its eval
   evidence.
2. **Steward's formats map to STEW kinds:**

   | Steward today | STEW |
   |---|---|
   | `harness/steward/profiles/<name>.yaml` (spec 002) | `kind: profile` `.us`. The fields map one to one, with these changes: `read_budget` becomes `budgets.reads`; `card: yes`/`no` becomes `plan`/`none`; `success` becomes `{check}`; `for.capability` becomes `for.capabilities`; and `requires` is new |
   | an eval set and its cases (`evals/*.yaml`, spec 003) | `kind: eval`. `tier: ext` becomes `gating: false` |
   | an operation (spec 004) | one profile, plus its eval set, plus the phone test, as today |
   | a request from the console, the phone or an automation | `kind: task`, posted on the board |
   | the bounds ([ADR-0014](0014-the-bounds-are-gates-in-code.md)), channels and the card timeout | `kind: board`. WhatsApp is a `may: read` channel |
   | `history.jsonl`, per-case transcripts, card answers | `kind: record` lines in the board's ledger. Transcripts stay files named by relative path |
   | `steward:1` on Ollama, `num_ctx` 65536, one 16 GB GPU | a **binding** in runtime config: [`steward-gpt-oss-20b`](https://github.com/thebrotherscarr-bit/STEW/blob/main/examples/bindings/steward-gpt-oss-20b.us), one way |

3. **ADR-0002's "one model" holds per install.** On this PC it is `steward:1`, as a binding in config. On another
   install it is whatever model fits that hardware and meets the profiles' `requires`. Results and promotions are
   recorded per binding, so a profile proven here is proven again on a friend's model.
4. **The migration is in steps, one pull request each. None of them is done in this record:**
   1. Steward's CI runs STEW's `validate.py` over his `.us` declarations (none yet, so trivially green). The
      validator is pinned to a STEW commit.
   2. The three profiles become `.us` files (`general`, `eval-runner`, `refuse`). `profiles.py` reads the `.us`
      form; `evals.py validate` checks each against the schema and against `capabilities.yaml`; the YAML files go.
      Each profile gains `requires`, measured (the smallest window its cases pass with), not guessed.
   3. Eval sets become `kind: eval` `.us` files. `evals.py` reads them, and the baselines' fingerprints are carried.
   4. The board: one `board.us` for this install, with the ADR-0014 bounds stated as rules in words (no paths) and
      the channels. The paths the bounds protect move to runtime config.
   5. The binding: model, endpoint and `num_ctx` move from code (`OLLAMA_OPTIONS`, the Modelfile name) into a
      binding in config. Profiles run only on a binding that fits.
   6. Records: eval runs and card answers append `stew.*` records to the board's ledger. Promotion is recorded as
      `stew.profile.promoted`, with its binding.
   7. Tasks and orchestration: requests are posted as task cards, and the orchestrator tables itself per task
      (STEW spec/orchestration.md), on MAF's file checkpoints.
5. **The next piece is a portability audit**, before step 2. It lists every hard-coded path, user name, account,
   port and model name in Steward and Jesster, and names, for each one, the runtime-config entry that replaces it.
   The audit is a list, not a change. Each fix after it is its own pull request.

### Consequences

- Good, because the spec is proven by the harness it came from, and every format change is checked by the spec's
  validator in CI.
- Good, because another person can install Steward, bind the model their hardware runs, run the conformance kit and
  see which profiles pass. Nothing in a declaration ties it to this PC.
- Good, because a change to the harness is now also a candidate change to an open spec, with its evidence.
- Neutral, because the meaning of ADR-0018's profile is unchanged; only its file format and three field names move.
- Bad, because the migration touches `profiles.py`, `evals.py` and the eval sets' fingerprints. Each step must keep
  every case and its history, and a step that loses one is reverted.
- Bad, because while STEW is a draft its schema can change under Steward. Steward pins a STEW commit and moves it by
  pull request.

## Validation

- Step 1 lands with a CI job that goes red when a `.us` declaration in this repository fails STEW's validator.
- Each later step keeps the T3 bounds set and every other set passing as before, on the same binding.
- The portability audit is accepted when it covers both repositories and every entry names its config key.

## More Information

- STEW: [README](https://github.com/thebrotherscarr-bit/STEW#readme), [spec](https://github.com/thebrotherscarr-bit/STEW/tree/main/spec),
  [bindings](https://github.com/thebrotherscarr-bit/STEW/blob/main/spec/binding.md).
- Amended in part: [ADR-0002](0002-one-model-for-everything.md) (one model per install, as a binding) and
  [ADR-0018](0018-harness-profiles-per-task-tuned-by-evals.md) (its formats become STEW declarations by step 4).
