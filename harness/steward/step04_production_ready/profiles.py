"""Harness profiles (ADR-0018, spec 002): one small STEW `.us` file per task family, read when Steward's workflow is built.

A profile names what a task is offered: its tools (an allow-list of exact names; nothing else is offered), up to 8 lines
of instructions added to the Charter for the task, its reading budget before the plan card, the model's reasoning effort,
the bounds it touches and any extra refusal (the bounds stay on whatever it says, ADR-0014), whether it raises a plan
card, the deterministic check that says done, and the one-line summary for the phone. The files are
harness/steward/profiles/<name>.us: STEW `kind: profile` declarations (STEW spec/profile.md; ADR-0019 migration step 2,
ExecPlan 0006 P8), Markdown with one ```json block, and only the members Steward enforces (STEW_PROFILE_KEYS). There is
no other form: the YAML files are gone and nothing here reads one.

The router (steward_workflow.Router) picks one profile per request (pick_profile): an explicit name in the request
first, then the patterns below (PROFILE_ROUTES), the model only when two profiles' patterns both match, and `general`
otherwise. The run applies it (steward_workflow): only its tools at each step, intersected with the step's own narrowing
(offered_in_step), its instructions through a MAF context provider (ProfileInstructions), its reading budget for EXPLORE,
its reasoning effort as the chat client's reasoning option (Ollama's `think` today), and its name, version, tools, budget, reasoning and success check on
the plan card; its success and summary ride on a custom workflow event for the phone (PROFILE_EVENT).

`general` is today's whole harness unchanged (ExecPlan 0005, Decision Log 2026-11-08): its tools are every tool the build
offers, so it cuts nothing. Narrow profiles replace it family by family, in the frozen order.

evals.py validate checks every profile (profile_problems): its tools exist (Steward's own, as capabilities.yaml names
them, or the MAF harness's own, MAF_HARNESS_TOOLS) and none is withheld; every non-ext eval case names a profile that
exists; every profile has a case; each capability id in its `for` is covered by a case naming it; its success check is
one evals.py knows; and every route names a profile.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_framework import ContextProvider, FileAccessProvider

import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install as _install  # noqa: E402 - a profile's requires, checked against the binding (ExecPlan 0006 P2)

PROFILES_DIR = Path(__file__).resolve().parents[1] / "profiles"
PROFILE_SUFFIX = ".us"
GENERAL = "general"
# The STEW version Steward implements (ADR-0019 decision 1), and the profile's members, each one Steward reads. STEW
# leaves instructions, budgets and reasoning optional; Steward's run uses each, so a profile of his states them. An
# `x-` member is ignored (STEW spec/declarations.md), except `x-min_context` below.
STEW_VERSION = "2026-11-08-draft"
STEW_PROFILE_KEYS = (
    "stew", "kind", "name", "version", "for", "tools", "requires", "instructions", "budgets", "reasoning", "gates", "card",
    "success", "summary",
)
# STEW's card values Steward runs: `plan` (one plan card; spec 002's yes) and `none` (a read or a refusal; spec 002's
# no). `every-write` is refused by name until Steward raises a card on each write.
CARDS = {"plan": True, "none": False}
# STEW requires min_context as a number of tokens. Steward's is to be measured (ExecPlan 0006 P2: the smallest window
# a profile's cases pass with, never guessed), so a profile says so in `x-min_context` and holds 1, which every binding
# meets; the loader reads that pair as None, and nothing is checked for it until it is measured.
MIN_CONTEXT_UNMEASURED = "to be measured"
REASONING = ("low", "medium", "high")
MAX_INSTRUCTION_LINES = 8
_NAME = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
_CAPABILITY_ID = re.compile(r"[A-Z]\d+")
# The session state key the workflow keeps the picked profile under (JSON-native, so it is in the workflow's checkpoint
# with the session: AgentExecutor.on_checkpoint_save), and the workflow event that names the pick to every caller.
PROFILE_KEY = "steward_profile"
PROFILE_EVENT = "steward_profile"

# MAF's MemoryContextProvider's tools (_harness/_memory.py before_run), all six.
MEMORY_TOOLS = frozenset({
    "list_memory_topics", "read_memory_topic", "write_memory", "delete_memory_topic", "search_memory_transcripts",
    "consolidate_memories",
})
# The MAF harness's own tools, by the names MAF gives them (agent_framework/_harness: FileAccessProvider's constants,
# _todo.py, _mode.py, _file_memory.py, _background_agents.py; SkillsProvider's load_skill, read_skill_resource and
# run_skill_script; MemoryContextProvider's four). They are not Steward's own, so capabilities.yaml does not map them
# (evals.steward_tool_names), and a profile may still name them: a code fix needs file access and its todos.
MAF_HARNESS_TOOLS = frozenset({
    *FileAccessProvider._ALL_TOOL_NAMES,  # noqa: SLF001 - MAF's own set of its file tools' names
    "todos_add", "todos_complete", "todos_remove", "todos_get_remaining", "todos_get_all",
    "mode_set", "mode_get",
    "file_memory_write", "file_memory_read", "file_memory_delete", "file_memory_ls", "file_memory_replace",
    "file_memory_replace_lines", "file_memory_grep",
    "background_agents_start_task", "background_agents_wait_for_first_completion", "background_agents_get_task_results",
    "background_agents_get_all_tasks", "background_agents_continue_task", "background_agents_clear_completed_task",
    "load_skill", "read_skill_resource", "run_skill_script",
    *MEMORY_TOOLS,
})

# The router's deterministic patterns, by profile name: a request (its source line included) that matches a profile's
# pattern picks it. A profile with no pattern is picked only by name (or, for `general`, by default). Each
# narrow profile adds its pattern here in the pull request that lands it (validate refuses a pattern naming no profile).
PROFILE_ROUTES: dict[str, re.Pattern[str]] = {
    # MP (N8): a request naming an eval, the evals or an eval tool, or a set with its tag ("Run the bounds set, tag
    # phone-1", the operator's own example).
    "eval-runner": re.compile(r"\beval(?:s|_start|_status)?\b|\bset,?\s+tag\s+[\w.-]+", re.IGNORECASE),
    # M0 (ExecPlan 0005's bounds profile set). Each pattern sees the whole request, Jesster's source line included (an
    # automation's turn is told apart by it); a request a bound refuses runs under refuse or github-review instead
    # (steward_workflow.refusal_profile), whatever these say.
    # code-fix (A4, P1): a request that opens with "fix" (the small, steps and heldout sets' bug fixes are this family).
    "code-fix": re.compile(r"\A(?:\s*\[[^\]\n]*\]\s*)?\W*(?:please\W+)?fix\b", re.IGNORECASE),
    # program (I6, P34): a command written in backticks, or one to run in the shell.
    "program": re.compile(r"`[^`\n]+`|\bin the shell\b", re.IGNORECASE),
    # estate-keeper (C7, G7, P36): a request that opens with restart, stop or start (an eval excepted), not an automation's.
    "estate-keeper": re.compile(
        r"\A(?!\s*\[from an automation)(?:\s*\[[^\]\n]*\]\s*)?\W*(?:please\W+)?(?:restart|stop|start)\b(?!.*\beval)",
        re.IGNORECASE | re.DOTALL,
    ),
    # away-end (B4, B5, P31): an automation's turn that asks for a change to the Estate or the PC.
    "away-end": re.compile(
        r"\A\s*\[from an automation \([^\]\n]*\]\s*\n\W*(?:please\W+)?"
        r"(?:restart|stop|start|install|update|upgrade|delete|remove|push|commit|unload|kill)\b",
        re.IGNORECASE,
    ),
}
# A profile's extra refusals in code (spec 002's `gates.extra`, held as ADR-0014 holds the bounds): by profile name, a
# pattern on the request's body and the reply, in words, with no plan and no card.
PROFILE_REFUSALS: dict[str, tuple[re.Pattern[str], str]] = {
    "eval-runner": (
        re.compile(r"\b(?:every|all|each)\b(?:\W+\w+){0,3}?\W+(?:eval|evals|eval sets?|sets)\b|\b(?:evals|sets)\b\W+(?:at once|together)\b", re.IGNORECASE),
        "Not done: one eval set per request, so I start no run that takes every set. Name the set (and a tag), and I "
        "will plan that one; the full sets run overnight when you start them.",
    ),
}


def profile_refusal(name: str, body: str) -> str | None:
    """The profile's own refusal of a request (PROFILE_REFUSALS), or None."""
    refusal = PROFILE_REFUSALS.get(name)
    return refusal[1] if refusal is not None and refusal[0].search(body or "") else None


class ProfileError(ValueError):
    """A profile file that cannot be used: its problems, one per line."""


@dataclass(frozen=True)
class Profile:
    """One harness profile, as its file holds it (spec 002)."""

    name: str
    version: int
    task: str
    capabilities: tuple[str, ...]
    tools: tuple[str, ...]
    instructions: str
    read_budget: int
    reasoning: str
    # What a model must offer to wear it (ExecPlan 0006 P2): {tool_calling, min_context (None: to be measured),
    # reasoning_effort}; the run refuses it on a binding that does not (install.binding_refusal).
    requires: Mapping[str, Any] = field(default_factory=dict)
    gates: Mapping[str, Any] = field(default_factory=dict)
    card: bool = True
    success: str = ""
    summary: str = ""
    path: Path | None = None

    @property
    def ref(self) -> str:
        """name@version, as the plan card, the transcript and the history name it."""
        return f"{self.name}@{self.version}"

    def card_view(self) -> dict[str, Any]:
        """What the plan card shows of the profile (ADR-0018 item 2): name, version, tools, read budget, reasoning and
        success."""
        return {
            "name": self.name, "version": self.version, "tools": list(self.tools), "read_budget": self.read_budget,
            "reasoning": self.reasoning, "success": self.success,
        }

    def state(self) -> dict[str, Any]:
        """What a step's session keeps of it (PROFILE_KEY): JSON-native, so it rides in the workflow's checkpoint."""
        return {**self.card_view(), "instructions": self.instructions, "card": self.card, "summary": self.summary}

    def event(self, how: str) -> dict[str, Any]:
        """The PROFILE_EVENT's data: the pick, how it was made, and its success check and summary for the phone."""
        return {"profile": self.ref, "name": self.name, "version": self.version, "picked_by": how,
                "success": self.success, "summary": self.summary}


def allowed_tools(session: Any) -> frozenset[str] | None:
    """The picked profile's allow-list on a session (PROFILE_KEY), or None when it has no profile."""
    profile = (getattr(session, "state", None) or {}).get(PROFILE_KEY) if session is not None else None
    return frozenset(profile.get("tools") or []) if isinstance(profile, dict) else None


def without_lines_naming(text: str, names: Iterable[str]) -> str:
    """The text without its lines naming any of these tools (each by its whole name)."""
    names = list(names)
    if not names:
        return text
    named = re.compile("|".join(rf"(?<![\w]){re.escape(n)}(?![\w])" for n in names))
    return "\n".join(line for line in text.split("\n") if not named.search(line))


def card_line(view: Mapping[str, Any]) -> str:
    """The plan card's one line of the profile, as Kyle reads it: "Harness: name@v; N tools: ...; read budget; ..."."""
    tools = list(view.get("tools") or [])
    shown = ", ".join(tools[:12]) + (f", and {len(tools) - 12} more" if len(tools) > 12 else "")
    return (
        f"Harness: {view.get('name')}@{view.get('version')}; {len(tools)} tool(s): {shown or 'none'}; read budget "
        f"{view.get('read_budget')}; reasoning {view.get('reasoning')}; success: {view.get('success')}"
    )


def _core(value: Any) -> Any:
    """A STEW object without its `x-` members (STEW spec/declarations.md: a processor ignores one it does not know)."""
    return {k: v for k, v in value.items() if not str(k).startswith("x-")} if isinstance(value, dict) else value


def _requires(raw: Any) -> Any:
    """STEW's requires as Steward's runtime holds it (install.REQUIRES_KEYS): {tool_calling, min_context (None: to be
    measured, the `x-min_context` pair), reasoning_effort (false when not said)}; the raw value when it is not a
    mapping, for requires_problems to name."""
    if not isinstance(raw, dict):
        return raw
    core = _core(raw)
    window = core.get("min_context")
    if raw.get("x-min_context") == MIN_CONTEXT_UNMEASURED and window == 1:
        window = None
    return {**core, "min_context": window, "reasoning_effort": core.get("reasoning_effort", False)}


def _problems(raw: Any, path: Path) -> list[str]:
    """What is wrong with one profile declaration's shape: STEW's profile members, each one Steward reads
    (STEW_PROFILE_KEYS), and the values Steward runs."""
    if not isinstance(raw, dict):
        return ["the json block is not an object"]
    raw = _core(raw)
    problems = [f"unknown member {key!r}" for key in sorted(set(raw) - set(STEW_PROFILE_KEYS))]
    problems += [f"missing member {key!r}" for key in STEW_PROFILE_KEYS if key not in raw]
    if problems:
        return problems
    if raw["stew"] != STEW_VERSION or raw["kind"] != "profile":
        problems.append(f"not a STEW {STEW_VERSION} profile (stew: {raw['stew']!r}, kind: {raw['kind']!r})")
    name, version = raw["name"], raw["version"]
    if not (isinstance(name, str) and _NAME.fullmatch(name)):
        problems.append(f"name {name!r} is not lowercase words joined by dashes")
    elif path.name != f"{name}{PROFILE_SUFFIX}":
        problems.append(f"the file is named {path.name}, not {name}{PROFILE_SUFFIX}")
    if not (isinstance(version, int) and not isinstance(version, bool) and version >= 1):
        problems.append(f"version {version!r} is not a whole number from 1")
    purpose = _core(raw["for"])
    if not (isinstance(purpose, dict) and set(purpose) == {"task", "capabilities"} and isinstance(purpose["task"], str)
            and purpose["task"].strip() and isinstance(purpose["capabilities"], list)
            and all(isinstance(c, str) and _CAPABILITY_ID.fullmatch(c) for c in purpose["capabilities"])):
        problems.append("for is not {task: <words>, capabilities: [<capability ids>]}")
    tools = raw["tools"]
    if not (isinstance(tools, list) and all(isinstance(t, str) and t.strip() for t in tools)):
        problems.append("tools is not a list of tool names ([] for a refusal)")
    elif len(set(tools)) != len(tools):
        problems.append("a tool is named twice")
    instructions = raw["instructions"]
    if not isinstance(instructions, str):
        problems.append("instructions is not text ('' for none)")
    elif len([line for line in instructions.splitlines() if line.strip()]) > MAX_INSTRUCTION_LINES:
        problems.append(f"instructions has more than {MAX_INSTRUCTION_LINES} lines")
    budgets = _core(raw["budgets"])
    if not (isinstance(budgets, dict) and set(budgets) == {"reads"}):
        problems.append("budgets is not {reads: <reads before the plan card>}: Steward enforces reads, and no other yet")
    elif not (isinstance(budgets["reads"], int) and not isinstance(budgets["reads"], bool) and budgets["reads"] >= 0):
        problems.append(f"budgets.reads {budgets['reads']!r} is not a whole number from 0")
    if raw["reasoning"] not in REASONING:
        problems.append(f"reasoning {raw['reasoning']!r} is not one of {list(REASONING)}")
    requires = raw["requires"]
    if isinstance(requires, dict):
        marker = requires.get("x-min_context")
        if marker is not None and not (marker == MIN_CONTEXT_UNMEASURED and requires.get("min_context") == 1):
            problems.append(f"x-min_context is {MIN_CONTEXT_UNMEASURED!r} with min_context 1, or absent (min_context measured)")
        if "structured_output" in requires:
            problems.append("requires.structured_output is not checked by Steward yet")
    problems += _install.requires_problems(_requires(requires))
    if isinstance(requires, dict) and isinstance(tools, list) and tools and requires.get("tool_calling") is not True:
        problems.append("it offers tools, so requires.tool_calling is true (STEW spec/profile.md 7a)")
    gates = _core(raw["gates"])
    if not (isinstance(gates, dict) and set(gates) <= {"bounds", "extra"}
            and all(isinstance(v, list) and all(isinstance(i, str) and i.strip() for i in v) for v in gates.values())):
        problems.append("gates is not {bounds: [<gate>], extra: [<refusal in words>]}")
    if raw["card"] not in CARDS:
        problems.append(f"card {raw['card']!r} is not one of {list(CARDS)} (every-write is not raised by Steward yet)")
    success = _core(raw["success"])
    if not (isinstance(success, dict) and set(success) == {"check"} and isinstance(success["check"], str)
            and success["check"].strip()):
        problems.append("success is not {check: <a check name>} (Steward's checks take no args)")
    if not (isinstance(raw["summary"], str) and raw["summary"].strip()):
        problems.append("summary is empty")
    return problems


def load_profile(path: Path) -> Profile:
    """One profile declaration read (a STEW .us file: Markdown with exactly one ```json block) and its shape checked;
    ProfileError names every problem."""
    where = f"profiles/{path.name}"
    if path.suffix != PROFILE_SUFFIX:
        raise ProfileError(f"{where}: a profile is a STEW {PROFILE_SUFFIX} file")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ProfileError(f"{where}: {error}") from error
    blocks = _install._JSON_BLOCK.findall(text.replace("\r\n", "\n"))  # noqa: SLF001 - the one .us block pattern
    if len(blocks) != 1:
        raise ProfileError(f"{where}: a .us file holds exactly one ```json block; found {len(blocks)}")
    try:
        raw = json.loads(blocks[0])
    except ValueError as error:
        raise ProfileError(f"{where}: its json block does not parse: {error}") from error
    if problems := _problems(raw, path):
        raise ProfileError("\n".join(f"{where}: {problem}" for problem in problems))
    return Profile(
        name=raw["name"], version=raw["version"], task=" ".join(raw["for"]["task"].split()),
        capabilities=tuple(raw["for"]["capabilities"]), tools=tuple(raw["tools"]), instructions=raw["instructions"].strip(),
        read_budget=raw["budgets"]["reads"], reasoning=raw["reasoning"], requires=_requires(raw["requires"]),
        gates=_core(raw["gates"]), card=CARDS[raw["card"]],
        success=raw["success"]["check"].strip(), summary=" ".join(raw["summary"].split()), path=path,
    )


def load_profiles(folder: Path = PROFILES_DIR) -> dict[str, Profile]:
    """Every profile in the folder (its .us files, and nothing else), by name; ProfileError on the first that cannot
    be used, or with no `general`."""
    profiles = {p.name: p for p in (load_profile(path) for path in sorted(folder.glob(f"*{PROFILE_SUFFIX}")))}
    if GENERAL not in profiles:
        raise ProfileError(f"profiles/: no {GENERAL}{PROFILE_SUFFIX}, the profile every request falls back to")
    return profiles


def _named_in(body: str, profiles: Mapping[str, Profile]) -> Profile | None:
    """The profile a request names explicitly ("profile eval-runner", "profile: eval-runner", "the eval-runner
    profile"), or None."""
    for name in sorted(profiles, key=len, reverse=True):
        word = re.escape(name)
        if re.search(rf"(?<![\w-])(?:profile[:\s]+{word}|{word}\s+profile)(?![\w-])", body, re.IGNORECASE):
            return profiles[name]
    return None


def pick_profile(
    body: str, profiles: Mapping[str, Profile], routes: Mapping[str, re.Pattern[str]] | None = None,
) -> tuple[Profile | None, str, list[str]]:
    """The deterministic pick for a request's body: (profile, how, candidates). how is "named", "pattern" or
    "default"; when two or more profiles' patterns match, the profile is None, how is "unclear" and candidates are
    their names (the router asks the model to choose among them, and falls back to `general`)."""
    if named := _named_in(body, profiles):
        return named, "named", [named.name]
    routes = PROFILE_ROUTES if routes is None else routes
    matched = [name for name, pattern in routes.items() if name in profiles and pattern.search(body)]
    if len(matched) == 1:
        return profiles[matched[0]], "pattern", matched
    if len(matched) > 1:
        return None, "unclear", matched
    return profiles[GENERAL], "default", [GENERAL]


class ProfileInstructions(ContextProvider):
    """The picked profile's instructions, added to the Charter for this task (spec 002: "added to the Charter for this
    task; never contradicting it"), read from the run's session (PROFILE_KEY), as MAF's context providers add
    instructions before each run (SessionContext.extend_instructions). A session with no profile, or a profile with no
    instructions, adds nothing."""

    def __init__(self) -> None:
        super().__init__("steward-profile")

    async def before_run(self, *, agent: Any, session: Any, context: Any, state: dict[str, Any]) -> None:
        profile = (getattr(session, "state", None) or {}).get(PROFILE_KEY) if session is not None else None
        if isinstance(profile, dict) and str(profile.get("instructions") or "").strip():
            context.extend_instructions(
                self.source_id, f"## Your harness for this task: {profile.get('name')}@{profile.get('version')}\n"
                f"{profile['instructions']}",
            )


def tools_named_in(text: str, tools: Iterable[str]) -> set[str]:
    """The tools a text names: each by its whole name, or a prefixed tool (secondbrain_, atlas_) by the name after its
    prefix when that holds an underscore ("eval_start" names secondbrain_eval_start; a bare "git" names nothing)."""
    found: set[str] = set()
    for tool in tools:
        short = tool.split("_", 1)[1] if tool.startswith(("secondbrain_", "atlas_")) else ""
        for word in (tool, short if "_" in short else ""):
            if word and re.search(rf"(?<![\w]){re.escape(word)}(?![\w])", text or ""):
                found.add(tool)
    return found


def profile_problems(
    profiles: Mapping[str, Profile],
    cases: Iterable[tuple[str, str, str, tuple[str, ...]]],
    known_tools: Iterable[str],
    withheld: Iterable[str],
    capability_ids: Iterable[str],
    checks: Iterable[str],
    routes: Mapping[str, re.Pattern[str]] | None = None,
    refusals: Mapping[str, Any] | None = None,
) -> list[str]:
    """The profiles against the eval cases and Steward's tools (spec 002, spec 003): the problems, one per line.

    ``cases`` is every non-ext case as (set file name, case id, its profile, its capability ids); ``known_tools`` is
    Steward's own tools (evals.steward_tool_names), to which the MAF harness's own (MAF_HARNESS_TOOLS) are added here;
    ``withheld`` the withheld tools (capabilities.yaml's withheld entries); ``checks`` every check name evals.py knows.
    A profile's instructions name only tools it offers (tools_named_in): an instruction to call a tool the run is not
    offered is a "not found" error, and three in a row end the run (t3-away's first run, 2026-11-08)."""
    known = {*known_tools, *MAF_HARNESS_TOOLS}
    withheld = set(withheld)
    capability_ids = set(capability_ids)
    checks = set(checks)
    routes = PROFILE_ROUTES if routes is None else routes
    refusals = PROFILE_REFUSALS if refusals is None else refusals
    cases = list(cases)
    problems: list[str] = []
    for name, profile in profiles.items():
        where = f"profiles/{name}{PROFILE_SUFFIX}"
        problems += [f"{where}: the tool {t} is withheld from Steward's build" for t in profile.tools if t in withheld]
        problems += [f"{where}: names the tool {t}, which neither Steward nor the MAF harness has" for t in profile.tools if t not in known and t not in withheld]
        if profile.success not in checks:
            problems.append(f"{where}: its success check {profile.success!r} is not a check evals.py knows")
        named = tools_named_in(profile.instructions, known | withheld)
        problems += [
            f"{where}: its instructions name {t}, which it does not offer (tools)" for t in sorted(named - set(profile.tools))
        ]
        own = [case for case in cases if case[2] == name]
        if not own:
            problems.append(f"{where}: no eval case names it (profile: {name}); a profile's cases are its eval")
        covered = {cid for case in own for cid in case[3]}
        problems += [f"{where}: for names {cid}, which the capability map does not list" for cid in profile.capabilities if cid not in capability_ids]
        problems += [f"{where}: for names {cid}, and no case naming this profile covers it" for cid in profile.capabilities if cid in capability_ids and cid not in covered]
    for set_file, case_id, profile_name, _ in cases:
        if not profile_name:
            problems.append(f"{set_file}: case {case_id!r} names no profile (profile: <name>, spec 003)")
        elif profile_name not in profiles:
            problems.append(f"{set_file}: case {case_id!r} names the profile {profile_name!r}, which profiles/ does not hold")
    problems += [f"profiles.PROFILE_ROUTES: a route names {name!r}, which profiles/ does not hold" for name in routes if name not in profiles]
    problems += [f"profiles.PROFILE_REFUSALS: a refusal names {name!r}, which profiles/ does not hold" for name in refusals if name not in profiles]
    return problems
