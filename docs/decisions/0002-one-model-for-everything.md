---
status: accepted; amended in part by ADR-0019
contact: Kyle
date: 2026-11-05
deciders: Kyle
---

# One model for everything

2026-11-08: amended in part by [ADR-0019](0019-steward-implements-stew.md): one model holds per install; the model is a binding in runtime config (STEW).

Supersedes in part [ADR-0001](0001-steward-is-a-maf-harness-agent.md): the models it names give way to one model, `steward:1`, for every role.

## Context and Problem Statement

Steward's improvement loop handed code edits to a separate coder model (qwen2.5-coder:14b), while Steward himself ran
on `steward:1` (gpt-oss:20b with Steward's Modelfile). The PC has one 16 GB GPU (RX 6800 XT). Should the Estate keep
a second model for coding, or run every role on Steward's own model?

## Decision Drivers

- The hardware: `steward:1` takes about 11.9 GB of VRAM and the coder about 9 GB, so they cannot sit side by side;
  every handoff to the coder costs two model loads.
- The traces: 1,015 chat calls, all on `steward:1`, loading 0.4% of the time, with no model switches. Every overnight
  bar pass (2026-11-04 to 11-05) ran on `steward:1` alone.
- The working rule "the harness, not the model": when Steward fails, fix the task, the context, the tools or the
  check, never the model size (guidance note `guidance-developing-steward-and-the-esta-27bfd2`, item 5).

## Considered Options

- One model, `steward:1`, for every role (chat, plan, execute, the coder, background agents, summaries).
- Keep a separate coder model for the improvement loop.

## Decision Outcome

Chosen option: "One model, `steward:1`, for every role", because it is what the evidence ran on, it avoids model
reloads on a single GPU, and it keeps failures in the harness where they can be fixed.

The operator, 2026-11-05: "one model to rule them all. I have faith in our harnessing work, This is the way."

Built as Steward #142: the improvement loop's coder defaults to `steward:1`. `STEWARD_CODER_MODEL` still names
another model if one is ever needed.

### Consequences

- Good, because no second chat model loads, so a coder handoff costs no reload and the GPU is never overloaded.
- Good, because every eval result measures one model, so a change in the harness is the only variable.
- Bad, because a coding-specific weakness of gpt-oss:20b cannot be routed around by switching models.
- Neutral: the CPU embedder (`embeddinggemma-2:270m`, `num_gpu: 0`) stays; it uses no VRAM and is not a chat model.

## Validation

A separate coder comes back only on evidence: the ext-aider-py coding set or the T2 tier shows a coding-specific gap
(see [ADR-0006](0006-evals-are-versioned-long-runs-at-night.md)), and even then only a model sized to fit beside
`steward:1`.

## More Information

- Supersedes the coder-model default in the improvement loop (`improvement_loop_workflow.py`).
- Record: the ground's HANDOFF.md, block for 2026-11-04, "2026-11-05 daytime"; the SecondBrain note
  `overnight-plan-steward-s-bar-and-develop-7d69e1`, "2026-11-05 daytime".
