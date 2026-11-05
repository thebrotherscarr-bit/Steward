---
status: accepted
contact: Kyle
date: 2026-11-05
deciders: Kyle
---

# 0007: Every turn's time is stamped by Jesster

## Context and Problem Statement

Steward had no reliable clock: a local model does not know the date, and "today", "tonight" or "how long ago" came out
wrong. Turns arrive from several places (the Agent tab, Telegram, WhatsApp, automations). Who tells Steward the time?

## Decision Drivers

- The operator's 2026-11-05 simplification ([ADR-0004](0004-jesster-is-the-center.md)): Jesster is the center that
  every turn passes through; the 2026-11-05 ruling records "time stamped by Jesster".
- No time service and nothing hosted: the PC's own clock.
- The source line already exists on every turn (`[from ...]`), and the Charter tells Steward to read it.

## Considered Options

- Jesster adds the machine's time, local with its UTC offset and UTC, to each turn's source line.
- Give Steward a clock tool to call.
- Put the date in Steward's instructions at start.

## Decision Outcome

Chosen option: "Jesster stamps each turn's source line", because it costs no tool call, is read fresh for every
message, and covers every channel in one place.

Built as Jesster #73: `withSource` (service.cjs) adds the clock to the line on every turn to Steward, for example
`[from the phone (Telegram) | Thu 2026-11-05 09:12 local (UTC-07:00) | 16:12 UTC]`. The Charter (v4.9) says to use
that time for "today", "yesterday", "tonight" and how long ago something was.

### Consequences

- Good, because every answer about time rests on the PC's clock.
- Bad, because turns that do not pass through `withSource` are not stamped: local schedules, evals and the door's
  `ask_steward` (as Jesster #73 says).

## Validation

`phone.test.cjs` goes red if `withSource` stops adding the stamp; the source-line tests expect it.
