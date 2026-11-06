---
status: rejected
contact: Kyle
date: 2026-11-05
deciders: Kyle
---

# The harness parity set: τ-bench retail and airline, with Aider's Python exercises second

> 2026-11-05: rejected. The operator, having read it: "ok, so that all seems kind of useless for our system then,
> seeing as our evals are literally "can he do what is needed for the system reliably" therefore, we need to make
> custom evals to make sure steward is using everything as expected within our harness." Superseded by
> [ADR-0012](0012-stewards-bar-is-our-own-capability-evals.md): Steward's bar is our own capability evals. Nothing
> below is built; the text is kept as it was proposed, and the evidence table stays a record of what was read.

## Context and Problem Statement

Steward is a MAF 1.24 harness on one local model, `steward:1` (gpt-oss-20b, stock Harmony template, Ollama, 16 GB
RX 6800 XT, Windows 11, no Docker; [ADR-0002](0002-one-model-for-everything.md)). Its outside calibration so far is
BFCL (`harness/steward/evals/ext-bfcl.yaml`): 24 of 65 single-call AST cases and 12 of 15 irrelevance cases on an
80-case subset. BFCL's leaderboard (`gorilla.cs.berkeley.edu/data_overall.csv`, read 2026-11-05) has no gpt-oss row,
so that score cannot say whether a shortfall is the harness or the model.

The operator, 2026-11-05: "find which harness benchmark has a published gpt-oss-20B result with a known scaffold, and
whether a subset runs fully locally. Then it goes into an ADR as our harness parity set before anything is built." He
chose this path over fixing BFCL first.

Which outside benchmark gives a published gpt-oss-20b number, under a scaffold we can name, on tasks that run fully on
this PC, so that Steward's score on the same tasks with the same model reads as the harness's difference?

## Decision Drivers

- **A published gpt-oss-20b (or, failing that, 120b) number** from a primary source: the model card, an official
  leaderboard or the benchmark's own paper.
- **A known scaffold**: the agent loop that produced the number is named, and ideally public, so it can be run here as
  the reference.
- **Fully local** (CLAUDE.md RULE 4): offline, pinned snapshot, no first-use downloads at run time, no hosted judge or
  user simulator unless it runs on local Ollama. **No Docker**, by ruling (SecondBrain note "Steward rulings: web,
  embeddings, Docker", 2026-11-02). Windows 11.
- **One model at a time** ([ADR-0002](0002-one-model-for-everything.md)): anything the benchmark needs besides the
  agent (a user simulator, a judge) should be `steward:1` too.
- **Fits the eval tiers** (`harness/steward/evals`, tier `ext`): calibration only, never a gate, never tuned on; long
  runs at night ([ADR-0006](0006-evals-are-versioned-long-runs-at-night.md), [ADR-0009](0009-flows-are-ordered-tool-chains-automations-schedule-flows.md)).

## Considered Options

- τ-bench (v1) retail and airline, tool-calling agent
- τ²-bench / τ³-bench
- Terminal-Bench 2.0 (Terminus 2, mini-swe-agent)
- SWE-bench Verified (bash-only, mini-swe-agent; model-card subset)
- Aider polyglot (Python exercises)
- HAL (Holistic Agent Leaderboard)
- BFCL (single-turn and multi-turn)
- AgentBench, ToolBench / StableToolBench

### The evidence (read 2026-11-05)

"MC" is OpenAI's gpt-oss model card, Table 3 ([arXiv:2508.10925v1](https://arxiv.org/html/2508.10925), card dated
2025-08-05): pass@1, the model's default system prompt, MXFP4 weights, reported at low / medium / high reasoning
effort. Secondary sources are marked.

| Benchmark | gpt-oss-20b published | gpt-oss-120b published | Scaffold | Source | Local on this PC |
|---|---|---|---|---|---|
| τ-bench retail | 35.0 / 47.3 / **54.8** (low/med/high) | 49.4 / 62.0 / 67.8 | OpenAI's own, not named: "functions to call in the model's developer message"; user simulator not named | MC | **Yes**: Python, LiteLLM (`tau_bench/envs/user.py`), no Docker; the user simulator must be local |
| τ-bench airline | 32.0 / 42.6 / **38.0** | 42.6 / 48.6 / 49.2 | as above | MC | **Yes**, as above |
| τ²/τ³-bench | none | none | — | official submissions, [tau2-bench `web/leaderboard/public/submissions`](https://github.com/sierra-research/tau2-bench) (no gpt-oss folder); a 60.2 / 65.8 "τ²" pair on benchlm.ai is **secondary, unverified** | Yes (LiteLLM, no Docker), but no number to compare |
| Terminal-Bench 2.0 (89 tasks) | **3.1 ± 1.5** (Terminus 2); **3.4 ± 1.4** (mini-swe-agent) | 18.7 ± 2.7 (Terminus 2); 14.2 ± 2.3 (mini-swe-agent) | **Terminus 2 and mini-swe-agent, public**; ≥ 5 trials per task; open-weight models via Together.AI | [Terminal-Bench paper, arXiv:2601.11868v1](https://arxiv.org/html/2601.11868v1), Table 2 (ICLR 2026); 120b on [vals.ai](https://www.vals.ai/benchmarks/terminal-bench-2) 19.10 (secondary) | **No**: every task is a Dockerfile run by Harbor (Daytona in the paper) |
| SWE-bench Verified | 37.4 / 53.2 / **60.7** on a fixed n=477 subset | 47.9 / 52.6 / 62.4; bash-only **26.0** (2025-08-07) | MC: scaffold not named for gpt-oss (the card describes its tool scaffold only for o3 / o4-mini); bash-only: **mini-swe-agent 1.7.0, public** | MC; [swe-bench.github.io `data/leaderboards.json`](https://github.com/SWE-bench/swe-bench.github.io) (no 20b row) | **No**: the evaluation harness builds a Docker image per instance |
| Aider polyglot (225 exercises, 6 languages) | 16.6 / 26.6 / **34.2** | 24.0 / 34.2 / 44.4; leaderboard **41.8** (high, `diff`, 79.1 % well formed, 2025-08-06) | MC: not named; leaderboard: **Aider 0.85.3.dev, public** (`aider --model openrouter/openai/gpt-oss-120b --reasoning-effort high`) | MC; [Aider `polyglot_leaderboard.yml`](https://github.com/Aider-AI/aider/blob/main/aider/website/_data/polyglot_leaderboard.yml) | **Yes for Python** (already pinned: `ext-aider-py.yaml`, 20 of 34); whole polyglot needs six toolchains |
| HAL (9 benchmarks incl. τ-bench airline, SWE-bench Verified Mini) | none | none | HAL Generalist, τ-bench Tool Calling, SWE-agent | [hal.cs.princeton.edu](https://hal.cs.princeton.edu/taubench_airline) | Partly; no gpt-oss row to compare |
| BFCL v4 (incl. multi-turn) | none on the official table | none | BFCL's own | [data_overall.csv](https://gorilla.cs.berkeley.edu/data_overall.csv) (0 rows matching "oss"); a third-party table (arXiv:2605.07731) is **secondary** and notes a Harmony parallel-call fault | Yes (already pinned: `ext-bfcl.yaml`) |
| AgentBench, ToolBench / StableToolBench | none found | none found | — | — | AgentBench needs Docker; StableToolBench needs a cached-API server and a GPT judge |

What the table says:

1. **No published gpt-oss-20b number on a task set that runs here comes with a public scaffold.** OpenAI's own
   `gpt_oss/evals` ([openai/gpt-oss](https://github.com/openai/gpt-oss)) ships only AIME, GPQA and HealthBench; the
   model card's τ-bench, SWE-bench and Aider numbers come from unpublished OpenAI setups.
2. **The only gpt-oss-20b numbers with a named public scaffold** are Terminal-Bench 2.0's (Terminus 2 3.1 %,
   mini-swe-agent 3.4 %). They need Docker, and at ~3 % (about 3 of 89 tasks) they would not separate two harnesses.
3. **τ-bench is the only benchmark with a published gpt-oss-20b number that runs fully here**, on its full test split,
   with no Docker. Its catch is the user simulator: the card does not name it, and the repository's default is
   `gpt-4o`, which is hosted. Here it must be `steward:1`.

## Decision Outcome

Chosen option (proposed): **"τ-bench (v1) retail and airline, tool-calling agent"** as the harness parity set, with
**Aider polyglot's Python exercises** (the existing `ext-aider-py`) as the second, because τ-bench is the only
candidate that has a published gpt-oss-20b number at every reasoning effort, is a multi-turn tool-use benchmark (what
Steward is), and runs fully on this PC with no Docker; Aider's Python set is already pinned, and Aider is a public
scaffold with a published gpt-oss number (120b) and a model-card 20b number.

**How the comparison is read.** Because the published scaffold is not public, the published number alone cannot be
the baseline. Each set is read in three columns, same tasks, same model, same reasoning effort, same user simulator:

| Column | What runs | What it is |
|---|---|---|
| Published | — | MC's gpt-oss-20b figure at the effort we run (τ-bench retail 47.3 medium / 54.8 high; airline 42.6 / 38.0; Aider polyglot 26.6 / 34.2) |
| Reference | the benchmark's own public agent on `steward:1`: τ-bench's tool-calling (`tool-calling`) agent; Aider itself | the model in a known, public scaffold on this PC |
| Steward | Steward's MAF workflow on `steward:1` | the harness under test |

- **Steward minus Reference is the harness's difference**: same tasks, model, effort, simulator and machine; only the
  agent loop changes.
- **Reference against Published checks the setup**: if the reference falls far short of the card, the gap is the
  local setup (Ollama's Harmony handling, quantisation, the local user simulator, the effort setting), not Steward,
  and it is named before Steward's number is read.
- Scores are pass^1 over the full split, one run per case (the Estate's rule for evals: a flip between runs is a harness
  defect), at a reasoning effort pinned in the set file.

### Consequences

- Good, because τ-bench has published gpt-oss-20b numbers for both domains at three efforts, so the local setup can be
  checked against them.
- Good, because both sets run fully offline: τ-bench's tasks and databases are files in the repository (pin
  `sierra-research/tau-bench` at `59a200c6d575d595120f1cb70fea53cef0632f6b`, 2026-03-18, MIT); Aider's Python set is
  already pinned (`polyglot-benchmark` `7e0611e`).
- Good, because one model serves agent and simulator ([ADR-0002](0002-one-model-for-everything.md): one model at a
  time).
- Bad, because the user simulator is `steward:1`, not the card's unnamed simulator: the Published column is a sanity
  check, not a like-for-like baseline. Only Reference-against-Steward is like for like.
- Bad, because the card's scaffold is unpublished, so "known scaffold" holds only for the Reference column, which we
  run ourselves.
- Bad, because the τ-bench v1 tasks are no longer updated (the repository's own warning; fixed tasks are in τ²/τ³,
  which have no gpt-oss number). Known faulty tasks stay in; both columns face the same ones.
- Neutral: run time is an estimate, not measured: 165 tasks (retail 115, airline 50), each tens of turns with two
  model calls per turn on one 16 GB card, is several hours per column. It runs at night as an eval workflow
  ([ADR-0006](0006-evals-are-versioned-long-runs-at-night.md)).
- Neutral: Terminal-Bench 2.0 and SWE-bench stay out while the no-Docker ruling stands. WSL with a container runtime
  would make them possible; that is the operator's call, not proposed here.
- RULE 4: no hosted model, judge or simulator. The τ-bench simulator's model is set to the local Ollama `steward:1`;
  nothing is downloaded at run time; no keys.

What would be built after acceptance (not built here):

1. `harness/steward/evals/ext-tau-retail.yaml` and `ext-tau-airline.yaml` (tier `ext`, calibration only): the pinned
   τ-bench test tasks and data under `data/`, with source, licence, attribution and contamination lines like
   `ext-bfcl.yaml`, the reasoning effort pinned, the user simulator `steward:1`.
2. A runner that gives each τ-bench task's tools to Steward's workflow and scores by τ-bench's own reward (database
   state and outputs), and a Reference run of τ-bench's own tool-calling agent on `steward:1` through Ollama.
3. A Reference run of Aider itself on `steward:1` over `ext-aider-py`, beside Steward's existing run.
4. The three-column report (Published, Reference, Steward) per set in `storage/evals/history.jsonl` and the evals
   README.
5. Night runs of both sets as eval workflows.

## Validation

The decision is met when, for each set, the three columns are on record for one reasoning effort, the Reference
column's distance from the card is named, and Steward's distance from the Reference is read as the harness's
difference.

## Pros and Cons of the Options

### τ-bench (v1) retail and airline, tool-calling agent

- Good, because it has published gpt-oss-20b numbers (MC) at low / medium / high.
- Good, because it is multi-turn tool use with a policy, close to Steward's work.
- Good, because it runs on Windows with Python and LiteLLM, no Docker.
- Bad, because the card's scaffold and simulator are not named; the repository's default simulator (`gpt-4o`) is
  hosted, so a local simulator changes the conditions.

### τ²-bench / τ³-bench

- Good, because its tasks are fixed and it is maintained.
- Bad, because there is no gpt-oss row on the official leaderboard; the τ² figures on aggregators are unverified.

### Terminal-Bench 2.0

- Good, because it is the only benchmark with gpt-oss-20b numbers under public scaffolds (Terminus 2, mini-swe-agent).
- Bad, because every task is a Docker container (Harbor): ruled out here.
- Bad, because gpt-oss-20b scores ~3 %, too low to separate harnesses.

### SWE-bench Verified

- Good, because MC has gpt-oss-20b numbers, and the bash-only board has gpt-oss-120b under mini-swe-agent 1.7.0.
- Bad, because evaluation needs Docker images per instance; no 20b row with a public scaffold.

### Aider polyglot (Python exercises)

- Good, because it is already pinned (`ext-aider-py`) and Aider is public; gpt-oss-120b is on the official board.
- Bad, because the published numbers are for all six languages, not Python; the 20b number's scaffold is not named.

### HAL

- Good, because it standardises scaffolds across τ-bench airline and SWE-bench Verified Mini.
- Bad, because it has no gpt-oss row.

### BFCL

- Good, because it is already pinned and fast.
- Bad, because the official table has no gpt-oss row, which is why this ADR exists.

### AgentBench, ToolBench / StableToolBench

- Bad, because no gpt-oss-20b number was found, and they need Docker (AgentBench) or a hosted judge and an API cache
  (StableToolBench).

## More Information

- Sources read 2026-11-05: [gpt-oss model card, arXiv:2508.10925v1](https://arxiv.org/html/2508.10925) (Table 3,
  §2.6, §5.2.3.1); [Terminal-Bench, arXiv:2601.11868v1](https://arxiv.org/html/2601.11868v1) (Table 2);
  [SWE-bench leaderboards.json](https://github.com/SWE-bench/swe-bench.github.io); [Aider polyglot
  leaderboard](https://aider.chat/docs/leaderboards/); [τ-bench](https://github.com/sierra-research/tau-bench);
  [τ²-bench](https://github.com/sierra-research/tau2-bench); [HAL](https://hal.cs.princeton.edu/);
  [BFCL](https://gorilla.cs.berkeley.edu/leaderboard.html); [openai/gpt-oss](https://github.com/openai/gpt-oss).
- The evidence table is also in SecondBrain, note "Harness parity set: evidence (2026-11-05)".
- Revisit if a gpt-oss-20b row appears on τ²-bench, BFCL or the SWE-bench bash-only board, or if the no-Docker ruling
  changes.
