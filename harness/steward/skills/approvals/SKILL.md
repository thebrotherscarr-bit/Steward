---
name: approvals
description: Answer what Kyle approved, denied or left waiting - the answered cards and how a held call ended. Use when the user asks what was approved or refused, why something did not run, or whether a card or a held door call is still waiting.
---

## Usage

1. **The answered cards.** Call `secondbrain_approvals_history` (`limit`, newest first, at most 200). Report each card
   asked about: the tool, what it would have done, approved or denied, and when.
2. **A held call.** A door write you made is parked as a hold with an id (`hold_...` in its answer). Call
   `secondbrain_hold_status` with that `id`: it says waiting, approved (with what the call answered), denied or
   expired. Report it as it says.
3. Before asking again for something, read the history: if Kyle has just refused it, say so and do not ask again.

Rules:
- Read only. Never answer, approve, deny or re-raise a card, and never repeat a denied call another way.
- Quote what the tools return; never guess what Kyle decided.
