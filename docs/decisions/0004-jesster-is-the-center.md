---
status: accepted
contact: Kyle
date: 2026-11-05
deciders: Kyle
---

# 0004: Jesster is the center; Neiro retired as a gate; Aurora parked

Supersedes in part [ADR-0001](0001-steward-is-a-maf-harness-agent.md): the platform it names (Manjuel, SecondBrain and
Atlas) becomes Jesster as the one center; Manjuel stays the ground and the record; Atlas (Aurora) is parked.

## Context and Problem Statement

By 2026-11-04 the Estate (Neiro) was told as four parts plus a manifest: Steward the agent, SecondBrain (Jesster) the
console, Manjuel the ground, Atlas (Aurora) the glass and door, and the Neiro repository's `estate.lock.json` with a
drift gate every part had to pass. In practice Steward and Jesster carried the work, and each new hub (MCP surfaces,
the phone, automations) needed a home. Where does the Estate's center sit, and what gates a change?

## Decision Drivers

- The operator, 2026-11-05: "steward doesn't need manjuel, doesn't use aurora, and neiro is essentially a placeholder
  and a name or a gate. jesster is actually the console for steward, who really is running everything and has
  centralized command. That being said, let's simplify the process."
- The operator, 2026-11-05: "Jesster can be central MCP, A2A, IDE, etc."
- The operator, 2026-11-05: "Aurora really is kind of useless right now until steward starts running the computer in
  a way i can see, kind of like how the chrome playwright controls work in other systems."
- One gate per change is enough: each repository already has its own CI and a protected main.

## Considered Options

- Jesster is the center; each repository's CI and protected main is its gate; Neiro retired; Aurora parked.
- Keep the four-part shape with Neiro's lock as the Estate-wide gate.

## Decision Outcome

Chosen option: "Jesster is the center", because it matches how the Estate is actually run and removes a gate that
checked versions rather than behaviour.

- **Steward runs everything.** He is the Estate's agent (the 2026-11-04 ruling: "Steward is the Agent in control of
  the modules, tools, and skills") and Manjuel's default agent.
- **Jesster (SecondBrain) is the center:** his console (the Agent tab and its shelves, the Phone view, the Flows
  shelf), the MCP hub (notes, web, skills, the Estate's controls, the door's tools), the automations' clock, and the
  Estate's status with every part's version (`estate_status`, Jesster #74). New hubs (MCP surfaces, A2A when it
  comes, IDE hooks) go in Jesster.
- **Manjuel** stays the ground and the record: the laws, the history, the engine. Steward does not depend on its index
  or record unless the operator asks.
- **Neiro is retired as a gate.** The operator's word: "do it, you have authorization to set it all up on github".
  Each part's own CI and protected main is the gate. The Neiro repository is archived on GitHub (read-only, public,
  Apache-2.0) and its lock is no longer refreshed (Jesster #75; the ground's CLAUDE.md, 2026-11-05). "Neiro" stays the
  Estate's name.
- **Aurora is parked** until Steward has visible computer control (Playwright-style, open source). No new Aurora work
  until then; its existing rules hold (its look is never changed). The GitHub repository Atlas was renamed Aurora on
  2026-11-05; the folder `atlas/`, its binaries and tool names are unchanged. Its door (43111) still serves the git
  tools Steward uses on cards, through Jesster.

### Consequences

- Good, because there is one place to look for the Estate's state and one console for the operator.
- Good, because a change lands on its own repository's checks, with no second lock to refresh after every merge.
- Bad, because nothing now checks that the parts' versions fit together; `estate_status` shows them, but does not
  refuse a mismatch.
- Neutral: Aurora's code and binaries stay in place and keep running the door.

## Validation

`estate_status` reports each repository's branch, HEAD, origin/main and whether it is behind (Jesster #74). Each
repository's main is protected and takes changes only through a pull request whose checks pass.

## More Information

- The SecondBrain notes `plan-steward-controls-the-estate-under-m-c9f628` (2026-11-04, the Estate under MAF) and
  `steward-s-dev-path-evals-that-grow-with--cb3211` ("Neiro is no longer the version gate").
- Repositories: Steward, Jesster, Manjuel and Aurora are public and MIT; Neiro is archived (Apache-2.0).
