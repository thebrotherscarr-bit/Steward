"""SecondBrain's automations as MAF workflows: a recipe is built into a Workflow and run on Steward's MCP host.

The operator, 2026-11-05: "we can build workflows for the evals, and then keep him as the general purpose agent for
personal use during the day", and "use it as a baseline so that steward can eventually build his own per my request
and authorization". MAF ships workflows (Learn, Workflows; WorkflowBuilder, executors and edges), so a recipe runs as
one here, not in SecondBrain's JavaScript. SecondBrain keeps only the scheduler (MAF has none): at a schedule's time
it calls ``run_recipe`` on this host (mcp_app.py, 127.0.0.1:43121), and reads ``recipe_status`` until the run ends.

A recipe is data, the shape his ``automations`` skill teaches and a later automation_save will write::

    {"name": "Startup", "prompt": "...", "deliver": ["note", "telegram"],
     "steps": ["pull_ff", "versions", "repo_log", "merged_prs", "releases", "eval_bars", "plan_left"],
     "summarize": "Write the daily what-happened from this ..."}

The workflow (build_recipe_workflow): Begin, then one executor per step in order (a chain), then Summarize (one run of
a tool-less agent on his model, in a session of its own, never his chat thread) when the recipe has ``summarize``,
then Deliver, which yields the result. Every step reads, but two bounded acts: ``pull_ff`` (a fast-forward of main only
on main with a clean work tree, never the ground while a Manjuel sitting is open: RULE 9) and ``eval_start``
(SecondBrain's eval_start, which runs eval sets only). No step raises a card. Checkpoints go to MAF's
FileCheckpointStorage (storage/recipes/checkpoints) and each run's events to storage/recipes/<run_id>.jsonl.
``recipe_graph`` gives the workflow's to_dict() and WorkflowViz Mermaid for the Flows shelf's wiring view.

Run history (ADR-0008, 2026-11-05): every run's state (<run_id>.json) carries the flow it ran for, what started it
(``now`` or ``schedule``) and its executors in order; ``RecipeRuns.runs`` lists a flow's runs, newest first, each with
its per-step states read from MAF's events as they are (executor_invoked and executor_completed give each step's ms; a
step that failed is told by MAF's non-fatal ``error`` event, which GatherStep adds with its executor id).
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
import subprocess
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_framework import (
    Executor,
    FileCheckpointStorage,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowEvent,
    WorkflowViz,
    handler,
    register_checkpoint_type,
)

STEPS = ("repo_log", "merged_prs", "releases", "eval_bars", "plan_left", "versions", "pull_ff", "eval_start", "eval_wait")
EVAL_SETS_TRANSPORTS = ("in-process", "responses", "ag-ui")
EVAL_MAX_HOURS = 8
MAX_RUNS = 3
DAY_SECONDS = 24 * 3600
MAX_SECTION = 4000
PLAN_FILE = "WHATS_LEFT.md"
PLAN_SECTION = "Today's working path"
EVAL_POLL_SECONDS = 60
# eval_wait first waits this long for the run's progress file (run-bar.ps1 validates the sets, ~10 s, before its first
# line), then for BAR DONE; a run with no progress file by then never began, and the flow ends failed with that reason
EVAL_START_SECONDS = 300
EVAL_START_POLL_SECONDS = 10
# the run history (recipe_runs): what may start a run, and how many runs one read lists
TRIGGERS = ("now", "schedule")
RUNS_LIMIT = 10
RUNS_MAX = 50
_RESULT_LINE = re.compile(r" done |BAR DONE|\bbar\b")
_START_LINE = re.compile(r" bar \S+ : sets ")

# One command, as (program, args, cwd) -> (exit code, stdout, stderr); tests give a fake.
Run = Callable[[str, Sequence[str], str], Awaitable[tuple[int, str, str]]]
# One SecondBrain MCP tool call, (name, arguments) -> its text; raises on an error result.
SecondBrain = Callable[[str, Mapping[str, Any]], Awaitable[str]]


class RecipeError(ValueError):
    """A recipe that is not one: a step outside STEPS, or arguments out of bounds."""


def _step(x: Any) -> dict[str, Any]:
    return {"step": x} if isinstance(x, str) else dict(x or {})


def validate_recipe(recipe: Mapping[str, Any]) -> dict[str, Any]:
    """The recipe checked against the fixed step list, its steps normalised; raises RecipeError naming what is wrong."""
    if not isinstance(recipe, Mapping):
        raise RecipeError("a recipe is an object")
    steps = recipe.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RecipeError("a recipe needs one or more steps")
    out: list[dict[str, Any]] = []
    for raw in steps:
        s = _step(raw)
        name = s.get("step")
        if name not in STEPS:
            raise RecipeError(f'no workflow step "{name}" (the steps are: {", ".join(STEPS)})')
        if name == "eval_start":
            sets = s.get("sets")
            if not isinstance(sets, list) or not sets:
                raise RecipeError("eval_start needs sets")
            runs = s.get("runs", 1)
            if not isinstance(runs, int) or not 1 <= runs <= MAX_RUNS:
                raise RecipeError(f"eval_start runs is 1 to {MAX_RUNS}")
            # No transport named: none is sent, and SecondBrain's eval_start picks AG-UI for asks sets only (ADR-0003)
            # and in-process for the rest, which evals.py refuses on a host (2026-11-05: bfcl over ag-ui exited 2).
            transport = s.get("transport")
            if transport is not None and transport not in EVAL_SETS_TRANSPORTS:
                raise RecipeError(f"eval_start transport is one of {', '.join(EVAL_SETS_TRANSPORTS)}")
            out.append({"step": name, "sets": [str(x) for x in sets], "runs": runs, **({"transport": transport} if transport else {})})
        elif name == "eval_wait":
            hours = s.get("hours", EVAL_MAX_HOURS)
            if not isinstance(hours, (int, float)) or not 0 < hours <= EVAL_MAX_HOURS:
                raise RecipeError(f"eval_wait hours is at most {EVAL_MAX_HOURS}")
            out.append({"step": name, "hours": hours})
        else:
            out.append({"step": name})
    summarize = recipe.get("summarize")
    return {
        "name": str(recipe.get("name") or "automation")[:80],
        "prompt": str(recipe.get("prompt") or ""),
        "steps": out,
        **({"summarize": str(summarize)} if summarize else {}),
        "deliver": [d for d in (recipe.get("deliver") or ["note"]) if d in ("note", "telegram")],
    }


@dataclass
class Repo:
    name: str
    dir: str
    ground: bool = False
    releases: bool = False


def estate_repos(ground: str | Path | None) -> list[Repo]:
    """The Estate's repositories from the ground (Desktop\\Research); releases are read for Jesster and Atlas."""
    if not ground:
        return []
    g = Path(ground)
    return [
        Repo("research", str(g), ground=True),
        Repo("steward", str(g / "worlds" / "steward")),
        Repo("jesster", str(g / "worlds" / "jesster"), releases=True),
        Repo("atlas", str(g / "atlas"), releases=True),
    ]


async def run_command(program: str, args: Sequence[str], cwd: str) -> tuple[int, str, str]:
    """One command, never through a shell, at most 120 s; git never prompts."""
    import os  # noqa: PLC0415

    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        done = await asyncio.to_thread(
            subprocess.run, [program, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120, env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", f"{type(exc).__name__}: {exc}"
    return done.returncode, done.stdout.strip(), done.stderr.strip()


@dataclass
class RecipeTools:
    """What the steps run on: the repositories, the command runner, SecondBrain's MCP tools, the ground, Steward's
    folder, and the clock and sleep (tests give fakes)."""

    repos: list[Repo]
    ground: str | None
    steward_dir: str | None
    run: Run = run_command
    secondbrain: SecondBrain | None = None
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


@dataclass
class Gathered:
    """What the steps have gathered so far, passed down the chain."""

    name: str
    prompt: str
    since: float
    sections: list[str] = field(default_factory=list)
    ok: bool = True
    tag: str | None = None
    short: str = ""
    # why this recipe's eval run never began (eval_start refused or failed, or no progress file): the run's failure
    eval_failed: str | None = None


@dataclass
class RecipeResult:
    """The workflow's output: the text for the note, one short line for Telegram, whether every step went well, and
    the error that fails the whole run (an eval run that never began)."""

    text: str
    short: str
    ok: bool
    error: str | None = None


def _first(text: str) -> str:
    return next((line for line in str(text or "").splitlines() if line.strip()), "")


def _is_repo(r: Repo) -> bool:
    return (Path(r.dir) / ".git").exists()


async def pull_main(repo: Repo, tools: RecipeTools) -> str:
    """A fast-forward pull of main, only on main with a clean work tree (and no open sitting on the ground)."""
    if repo.ground:
        # whether a Manjuel sitting is open, as SecondBrain's estate_status reads it; unknown is never pulled
        if tools.secondbrain is None:
            return "not pulled: whether a Manjuel sitting is open cannot be read (SecondBrain is not connected)"
        try:
            sitting = json.loads(await tools.secondbrain("estate_status", {})).get("sitting") or {}
        except Exception as exc:  # noqa: BLE001 - unknown is never pulled
            return f"not pulled: whether a Manjuel sitting is open cannot be read ({exc})"
        if sitting.get("open") is not False:
            return f"not pulled: Manjuel sitting {sitting.get('n', '?')} is open (RULE 9)"
    code, branch, err = await tools.run("git", ["rev-parse", "--abbrev-ref", "HEAD"], repo.dir)
    if code != 0:
        return f"not pulled: {_first(err) or 'not a git repository'}"
    if branch != "main":
        return f"not pulled: on branch {branch}, not main"
    # tracked changes against HEAD, staged or not; read-only (the index is not written)
    code, _, _ = await tools.run("git", ["diff-index", "--quiet", "HEAD", "--"], repo.dir)
    if code != 0:
        return "not pulled: the work tree has uncommitted changes"
    code, out, err = await tools.run("git", ["pull", "--ff-only", "origin", "main"], repo.dir)
    if code != 0:
        last = [line for line in err.splitlines() if line.strip()]
        return f"not pulled: {last[-1] if last else 'git pull failed'}"
    return "current (nothing to pull)" if "Already up to date" in out else "pulled (fast-forward)"


def read_plan(ground: str) -> str:
    """The PLAN_SECTION of the ground's WHATS_LEFT.md, at most MAX_SECTION characters."""
    try:
        lines = (Path(ground) / PLAN_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return f"({PLAN_FILE} was not found)"
    at = next((i for i, line in enumerate(lines) if line.startswith("## ") and PLAN_SECTION in line), None)
    if at is None:
        return f'({PLAN_FILE} has no "{PLAN_SECTION}" section)'
    end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    section = "\n".join(lines[at:end]).strip()
    return section[:MAX_SECTION] + "\n..." if len(section) > MAX_SECTION else section


def eval_bars(steward_dir: str | None, since: float, tag: str | None = None) -> str:
    """The newest eval runs' result lines (storage/evals/runs/<tag>/progress.txt in Steward's folder); only ``tag``'s
    when the recipe started a run, never an older run's in its place."""
    folder = Path(steward_dir or "") / "storage" / "evals" / "runs"
    if tag:
        f = folder / tag / "progress.txt"
        if not f.exists():
            return f"{tag}: no progress file: the run did not begin"
        lines = [line for line in f.read_text(encoding="utf-8").splitlines() if _RESULT_LINE.search(line) and not _START_LINE.search(line)]
        return "\n".join([f"{tag}:", *(f"  {line}" for line in lines[-8:])] if lines else [f"{tag}: no result lines yet"])
    runs = sorted(
        ((f.stat().st_mtime, d.name, f) for d in (folder.iterdir() if folder.is_dir() else []) if (f := d / "progress.txt").exists()),
        reverse=True,
    )
    pick = [r for r in runs if r[0] >= since][:3] or runs[:1]
    if not pick:
        return "(no eval runs found)"
    out: list[str] = []
    for mtime, tag, f in pick:
        lines = [line for line in f.read_text(encoding="utf-8").splitlines() if _RESULT_LINE.search(line) and not _START_LINE.search(line)]
        out += [f"{tag}{' (older than this window)' if mtime < since else ''}:", *(f"  {line}" for line in lines[-8:])]
    return "\n".join(out)


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


async def gather(step: Mapping[str, Any], g: Gathered, tools: RecipeTools) -> str:
    """One step's section of the gathered text."""
    name = step["step"]
    repos = [r for r in tools.repos if _is_repo(r)]
    if name == "pull_ff":
        lines = [f"- {r.name}: {await pull_main(r, tools) if _is_repo(r) else 'not found'}" for r in tools.repos]
        return "## The repositories brought current (main, fast-forward only)\n" + "\n".join(lines)
    if name == "repo_log":
        since = datetime.fromtimestamp(g.since, tz=timezone.utc).isoformat()
        out = ["## Commits on main"]
        for r in repos:
            code, log, err = await tools.run("git", ["log", "main", "--first-parent", f"--since={since}", "--format=%h %ad %s", "--date=short", "-n", "40"], r.dir)
            out += [f"{r.name}:", *([f"  (git log failed: {_first(err)})"] if code else [f"  {line}" for line in log.splitlines()] or ["  none"])]
        return "\n".join(out)
    if name == "merged_prs":
        out = ["## Merged pull requests"]
        for r in repos:
            code, text, err = await tools.run("gh", ["pr", "list", "--state", "merged", "--search", f"merged:>={_day(g.since)}", "--json", "number,title,mergedAt", "--limit", "40"], r.dir)
            prs = json.loads(text or "[]") if code == 0 else []
            head = f"(gh failed: {_first(err)})" if code else "" if prs else "none"
            out += [f"{r.name}: {head}", *(f"  #{p['number']} {p['title']} ({p['mergedAt']})" for p in prs)]
        return "\n".join(out)
    if name == "releases":
        out = ["## Releases"]
        for r in (x for x in repos if x.releases):
            code, text, err = await tools.run("gh", ["release", "list", "--limit", "10", "--json", "tagName,publishedAt"], r.dir)
            rel = [x for x in json.loads(text or "[]") if datetime.fromisoformat(x["publishedAt"].replace("Z", "+00:00")).timestamp() >= g.since] if code == 0 else []
            listed = ", ".join(f"{x['tagName']} ({x['publishedAt']})" for x in rel) or "none"
            out.append(f"{r.name}: " + (f"(gh failed: {_first(err)})" if code else listed))
        return "\n".join(out)
    if name == "eval_bars":
        if g.eval_failed and not g.tag:
            return f"## Steward's eval bars\n(no eval run: {g.eval_failed})"
        return f"## Steward's eval bars\n{eval_bars(tools.steward_dir, g.since, g.tag)}"
    if name == "plan_left":
        return f"## What is left ({PLAN_FILE})\n{read_plan(tools.ground) if tools.ground else '(the ground was not found)'}"
    if name == "versions":
        if tools.secondbrain is None:
            return "## The Estate's versions\n(SecondBrain is not connected)"
        repos_v = json.loads(await tools.secondbrain("estate_status", {})).get("repos") or []

        def line(v: Mapping[str, Any]) -> str:
            if v.get("error"):
                return f"- {v['name']}: {v['error']}"
            apart = f", {v['behind']} behind, {v['ahead']} ahead" if "behind" in v else ""
            clean = "" if "clean" not in v else ", clean" if v["clean"] else ", uncommitted changes"
            return f"- {v['name']}: {v.get('branch')} at {v.get('head')}; origin/main {v.get('origin_main') or 'unknown'}{apart}{clean}"

        return "## The Estate's versions (local refs)\n" + ("\n".join(line(v) for v in repos_v) or "(none)")
    if name == "eval_start":
        if tools.secondbrain is None:
            raise RuntimeError("SecondBrain is not connected, so no eval can start")
        now = tools.clock()
        tag = f"{'_'.join(step['sets'])}-{datetime.fromtimestamp(now).strftime('%Y-%m-%d-%H%M')}"
        args = {"sets": step["sets"], "runs": step["runs"], "tag": tag, **({"transport": step["transport"]} if step.get("transport") else {})}
        started = json.loads(await tools.secondbrain("eval_start", args))
        g.tag = started["tag"]
        over = started.get("transport") or step.get("transport") or "SecondBrain's default"
        return f"## Eval run started\n{g.tag}: {', '.join(step['sets'])}, {step['runs']} run(s) each, over {over}"
    if name == "eval_wait":
        if not g.tag or tools.secondbrain is None:
            return "## Eval run\n(nothing to wait for: no eval_start before eval_wait)"
        until = tools.clock() + step["hours"] * 3600
        # first the run's progress file (bounded): eval_status is an error until run-bar.ps1 writes its first line
        begin_by = min(until, tools.clock() + EVAL_START_SECONDS)
        while True:
            try:
                status = json.loads(await tools.secondbrain("eval_status", {"tag": g.tag}))
                break
            except Exception as exc:  # noqa: BLE001 - not begun yet, or never
                if tools.clock() >= begin_by:
                    raise RuntimeError(f"the eval run {g.tag} never began: no progress file after {EVAL_START_SECONDS} s ({_first(str(exc))})") from exc
                await tools.sleep(EVAL_START_POLL_SECONDS)
        while not status.get("done") and tools.clock() < until:
            await tools.sleep(EVAL_POLL_SECONDS)
            status = json.loads(await tools.secondbrain("eval_status", {"tag": g.tag}))
        lines = status.get("lines") or ["no progress lines"]
        if status.get("done"):
            g.short = next((line for line in reversed(lines) if " done " in line), "BAR DONE").split(" ", 1)[-1]
            head = f"{g.tag} ended (BAR DONE)."
        else:
            g.ok = False
            g.short = f"no BAR DONE after {step['hours']} h"
            head = f"{g.tag} did not say BAR DONE within {step['hours']} h."
        return "## Eval run\n" + head + "\n\n```\n" + "\n".join(lines) + "\n```"
    raise RecipeError(f'no workflow step "{name}"')


# ---- the executors -------------------------------------------------------------------------------------------------


@dataclass
class RecipeStart:
    """The run's input: the recipe and the start of its window (the schedule's last run, or a day ago)."""

    recipe: dict[str, Any]
    since: float


class Begin(Executor):
    """Starts the chain: what the steps gather starts empty."""

    @handler
    async def begin(self, start: RecipeStart, ctx: WorkflowContext[Gathered]) -> None:
        await ctx.send_message(Gathered(name=start.recipe["name"], prompt=start.recipe["prompt"], since=start.since))


class GatherStep(Executor):
    """One step of the recipe: its section added to what was gathered. A failed step says so and the chain goes on,
    but for eval_start, whose failure ends what an eval_wait after it would wait for."""

    def __init__(self, id: str, step: Mapping[str, Any], tools: RecipeTools) -> None:
        super().__init__(id=id)
        self._step = dict(step)
        self._tools = tools

    @handler
    async def run_step(self, g: Gathered, ctx: WorkflowContext[Gathered]) -> None:
        try:
            g.sections.append(await gather(self._step, g, self._tools))
        except Exception as exc:  # noqa: BLE001 - a step's failure is the run's record, not a crash
            g.ok = False
            g.sections.append(f"## {self._step['step']}\nFailed: {exc}")
            if self._step["step"] in ("eval_start", "eval_wait") and not (self._step["step"] == "eval_wait" and g.eval_failed):
                # the eval run never began: the whole run fails with this reason, and nothing judges a run that
                # did not happen (Summarize says so instead of asking the agent)
                g.eval_failed = f"{self._step['step']}: {exc}"
                g.short = f"Failed: {g.eval_failed}"
            # MAF's non-fatal "error from user code" event, with this step's id: the run history marks the step failed
            await ctx.add_event(WorkflowEvent("error", data=exc, executor_id=self.id))
        await ctx.send_message(g)


SUMMARIZE_INSTRUCTIONS = (
    "You are Steward, writing the result of one of the operator's automations from what its steps gathered. Nobody is "
    "watching and nothing more can be run: answer in plain words only, short, from the gathered text alone; say what is "
    "missing rather than guessing."
)


class Summarize(Executor):
    """The one turn of the recipe's summarize: a tool-less agent on his model, in a session of its own."""

    def __init__(self, id: str, agent: Any, summarize: str) -> None:
        super().__init__(id=id)
        self._agent = agent
        self._summarize = summarize

    @handler
    async def summarize(self, g: Gathered, ctx: WorkflowContext[Gathered]) -> None:
        gathered = "\n\n".join(g.sections)
        if g.eval_failed:
            # 2026-11-05: asked to judge a run that never began, the agent wrote a verdict from older runs' lines
            g.sections = [f"The eval run did not happen, so there is nothing to judge. {g.eval_failed}", f"---\n\n{gathered}"]
            await ctx.send_message(g)
            return
        text = (
            f"{self._summarize}\n\n"
            + (f"(The automation's own words: {g.prompt})\n\n" if g.prompt else "")
            + "What the steps gathered is below; nothing more needs running.\n\n"
            + gathered
        )
        response = await self._agent.run(text, session=self._agent.create_session())
        answer = response.text or "(no answer)"
        g.short = _first(answer)
        g.sections = [answer, f"---\n\n<details><summary>What the steps gathered</summary>\n\n{gathered}\n\n</details>"]
        await ctx.send_message(g)


class Deliver(Executor):
    """The run's output: the note's text and Telegram's short line (SecondBrain files and sends them)."""

    @handler
    async def deliver(self, g: Gathered, ctx: WorkflowContext[Any, RecipeResult]) -> None:
        text = "\n\n".join(g.sections)
        short = g.short or _first(re.sub(r"^## .*\n", "", text))
        await ctx.yield_output(RecipeResult(text=text, short=short, ok=g.ok, error=g.eval_failed))


for _t in (RecipeStart, Gathered, RecipeResult):
    register_checkpoint_type(_t)


def executor_ids(recipe: Mapping[str, Any]) -> list[str]:
    """The recipe's executors' ids in the order they run: begin, 1_<step> ..., summarize (with summarize), deliver."""
    r = validate_recipe(recipe)
    return ["begin", *(f"{i + 1}_{s['step']}" for i, s in enumerate(r["steps"])), *(["summarize"] if r.get("summarize") else []), "deliver"]


def build_recipe_workflow(recipe: Mapping[str, Any], tools: RecipeTools, summarizer: Any | None, checkpoint_storage: Any | None = None) -> Workflow:
    """The recipe as a MAF Workflow: Begin, one GatherStep per step, Summarize (with summarize), Deliver; a chain."""
    r = validate_recipe(recipe)
    begin = Begin(id="begin")
    chain: list[Executor] = [begin]
    chain += [GatherStep(id=f"{i + 1}_{s['step']}", step=s, tools=tools) for i, s in enumerate(r["steps"])]
    if r.get("summarize"):
        if summarizer is None:
            raise RecipeError("this recipe summarizes, and no agent was given to write it")
        chain.append(Summarize(id="summarize", agent=summarizer, summarize=r["summarize"]))
    deliver = Deliver(id="deliver")
    chain.append(deliver)
    return (
        WorkflowBuilder(
            name=f"recipe_{re.sub(r'[^a-z0-9]+', '_', r['name'].lower()).strip('_') or 'automation'}",
            max_iterations=len(chain) + 2,
            start_executor=begin,
            checkpoint_storage=checkpoint_storage,
            output_from=[deliver],
        )
        .add_chain(chain)
        .build()
    )


def recipe_graph(recipe: Mapping[str, Any]) -> dict[str, Any]:
    """The recipe's workflow for the Flows shelf's wiring view: MAF's to_dict() and WorkflowViz's Mermaid."""
    workflow = build_recipe_workflow(recipe, RecipeTools(repos=[], ground=None, steward_dir=None), summarizer=_NoAgent())
    return {"workflow": workflow.to_dict(), "mermaid": WorkflowViz(workflow).to_mermaid()}


class _NoAgent:
    """A stand-in summarizer for drawing the graph only."""

    async def run(self, *_a: Any, **_k: Any) -> Any:  # pragma: no cover - never run
        raise RuntimeError("drawing only")

    def create_session(self) -> None:  # pragma: no cover - never run
        return None


# ---- the runs ------------------------------------------------------------------------------------------------------


class RecipeRuns:
    """run_recipe and recipe_status: each run its own task on this host, its events to <folder>/<run_id>.jsonl and its
    state to <folder>/<run_id>.json, checkpointed by MAF's FileCheckpointStorage in <folder>/checkpoints."""

    def __init__(self, folder: Path, tools: Callable[[], RecipeTools], summarizer: Any | None) -> None:
        self.folder = Path(folder)
        self._tools = tools
        self._summarizer = summarizer
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def _write(self, run_id: str, state: dict[str, Any]) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = self.folder / f"{run_id}.json.tmp"
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(self.folder / f"{run_id}.json")

    def _event(self, run_id: str, event: Any) -> None:
        line = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": str(getattr(event, "type", type(event).__name__)),
            "executor": getattr(event, "executor_id", None),
            "data": str(getattr(event, "data", ""))[:500],
        }
        with (self.folder / f"{run_id}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")

    def start(self, recipe: Mapping[str, Any], since: float | None = None, flow: str | None = None, trigger: str | None = None) -> dict[str, Any]:
        """Validate and start one run; its id at once (the run goes on in its own task). ``flow`` is the flow's id in
        SecondBrain and ``trigger`` what started it (``now`` or ``schedule``), kept for the run history."""
        r = validate_recipe(recipe)
        tools = self._tools()
        run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
        start = RecipeStart(recipe=r, since=since if since is not None else tools.clock() - DAY_SECONDS)
        workflow = build_recipe_workflow(r, tools, self._summarizer, FileCheckpointStorage(self.folder / "checkpoints"))
        state = {
            "run_id": run_id,
            "name": r["name"],
            "flow": str(flow)[:120] if flow else None,
            "trigger": trigger if trigger in TRIGGERS else None,
            "executors": executor_ids(r),
            "state": "running",
            "started": datetime.now(timezone.utc).isoformat(),
        }
        self._write(run_id, state)
        self._tasks[run_id] = asyncio.create_task(self._run(run_id, workflow, start, state))
        return {"run_id": run_id, "state": "running"}

    async def _run(self, run_id: str, workflow: Workflow, start: RecipeStart, state: dict[str, Any]) -> None:
        try:
            result: RecipeResult | None = None
            async for event in workflow.run(start, stream=True):
                self._event(run_id, event)
                if getattr(event, "type", None) == "output" and isinstance(getattr(event, "data", None), RecipeResult):
                    result = event.data
            if result is None:
                state.update(state="failed", error="the workflow ended with no output")
            elif result.error:
                state.update(state="failed", ok=False, error=result.error, text=result.text, short=result.short)
            else:
                state.update(state="done", ok=result.ok, text=result.text, short=result.short)
        except Exception as exc:  # noqa: BLE001 - the run's failure is its record
            state.update(state="failed", error=f"{type(exc).__name__}: {exc}")
        state["ended"] = datetime.now(timezone.utc).isoformat()
        self._write(run_id, state)

    def status(self, run_id: str) -> dict[str, Any]:
        """One run's state: running, done (ok, text, short) or failed (error), and its steps so far (step_states)."""
        if not re.fullmatch(r"[\w-]+", run_id or ""):
            raise RecipeError("run_id is the id run_recipe returned")
        f = self.folder / f"{run_id}.json"
        if not f.exists():
            raise RecipeError(f"no recipe run {run_id}")
        state = json.loads(f.read_text(encoding="utf-8"))
        return state | {"steps": step_states(state, self._events(run_id))}

    def _events(self, run_id: str) -> list[dict[str, Any]]:
        f = self.folder / f"{run_id}.jsonl"
        out: list[dict[str, Any]] = []
        for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue  # a line cut by a crash is skipped, the rest still read
        return out

    def runs(self, flow: str, limit: int = RUNS_LIMIT) -> list[dict[str, Any]]:
        """One flow's runs, newest first, at most ``limit`` (1 to RUNS_MAX): each run's state without the note's text,
        and its per-step states. Read-only."""
        if not flow:
            raise RecipeError("flow is the flow's id")
        limit = max(1, min(RUNS_MAX, int(limit)))
        found: list[dict[str, Any]] = []
        for f in self.folder.glob("*.json") if self.folder.is_dir() else []:
            try:
                state = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(state, dict) and state.get("flow") == flow:
                found.append(state)
        found.sort(key=lambda s: str(s.get("started") or ""), reverse=True)
        keep = ("run_id", "name", "flow", "trigger", "state", "ok", "short", "error", "started", "ended")
        return [{k: s.get(k) for k in keep} | {"steps": step_states(s, self._events(s["run_id"]))} for s in found[:limit]]


def _ts(s: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(s)).timestamp()
    except ValueError:
        return None


def step_states(state: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Each executor's state in one run, from MAF's events as they were written: ``done`` (completed), ``failed`` (an
    ``error`` or ``executor_failed`` event named it, or it never completed in a run that ended), ``running`` (invoked,
    not completed, in a run still going), ``waiting`` (not reached yet in a run still going) or ``skipped`` (not reached
    in a run that ended); ``ms`` from its executor_invoked to its executor_completed."""
    running = state.get("state") == "running"
    ids = list(state.get("executors") or [])
    seen: dict[str, dict[str, Any]] = {}
    for e in events:
        ex = e.get("executor")
        if not ex:
            continue
        if ex not in ids:
            ids.append(ex)
        s = seen.setdefault(ex, {})
        kind = e.get("type")
        if kind == "executor_invoked":
            s.setdefault("invoked", _ts(e.get("ts")))
        elif kind == "executor_completed":
            s["completed"] = _ts(e.get("ts"))
        elif kind in ("error", "executor_failed"):
            s["error"] = str(e.get("data") or kind)
    out: list[dict[str, Any]] = []
    for ex in ids:
        s = seen.get(ex, {})
        if "invoked" not in s:
            st = "waiting" if running else "skipped"
        elif "error" in s:
            st = "failed"
        elif "completed" in s:
            st = "done"
        else:
            st = "running" if running else "failed"
        ms = round((s["completed"] - s["invoked"]) * 1000) if s.get("completed") is not None and s.get("invoked") is not None else None
        step = ex.split("_", 1)[1] if re.match(r"\d+_", ex) else ex
        out.append({"id": ex, "step": step, "state": st, "ms": ms, "ok": st == "done", **({"error": s["error"]} if "error" in s else {})})
    return out
