"""The install's own entries (ADR-0020 decision 2; ExecPlan 0006 P1): every value that belongs to one machine, read in one
place, each with today's value as its default or a path computed from the install folder.

The install folder is this repository's root (INSTALL_DIR). Each entry is an environment variable, set in the install's
`.env` (see `.env.example`) or by the launcher; an empty or absent entry means its default. A relative path is read
against the install folder. No entry holds a key (keys stay in `.env`, read by nothing here).

    STEWARD_OWNER       who Steward works for, as the model is told it (default: OWNER_DEFAULT)
    STEWARD_BASH        the bash his shell runs on Windows (default: Git for Windows under %ProgramFiles%)
    STEWARD_GROUND_DIR  Manjuel's ground, when there is one (default: inferred from the folder layout, else none)
    STEWARD_MCP_PORT    the port of his MCP host, mcp_app.py (default: 43121)

The portability audit (the SecondBrain note portability-audit-2026-11-08-8af9d1, entries A5, A7, B1, B6 and D7) named
each one; ExecPlan 0006's P4 folds them into the install's one `.us` declaration when STEW gives an install a kind.

The model is a binding (ExecPlan 0006 P2; ADR-0019 migration step 5; ADR-0020 decision 3; STEW spec/binding.md): one
STEW `kind: binding` declaration names the model, its server and its options, and nothing else in Steward's code names
a model. It is `binding.us` in the install folder, or the file STEWARD_BINDING names. apply_binding() reads it once
when a host starts and puts its model and endpoint in OLLAMA_MODEL and OLLAMA_HOST, which every MAF Ollama client
reads, so the binding wins over any older value in `.env`. A profile's `requires` is checked against it before a run
(binding_refusal), and the reasoning option is sent only when it provides `reasoning_effort`.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

INSTALL_DIR = Path(__file__).resolve().parents[2]

OWNER_ENV = "STEWARD_OWNER"
OWNER_DEFAULT = "Kyle"
BASH_ENV = "STEWARD_BASH"
GROUND_ENV = "STEWARD_GROUND_DIR"
MCP_PORT_ENV = "STEWARD_MCP_PORT"
MCP_PORT_DEFAULT = 43121


def _entry(name: str, environ: Mapping[str, str] | None) -> str:
    return ((os.environ if environ is None else environ).get(name) or "").strip()


def install_path(raw: str) -> Path:
    """A path entry: absolute as written, or relative to the install folder."""
    path = Path(raw).expanduser()
    return path if path.is_absolute() else INSTALL_DIR / path


def owner(environ: Mapping[str, str] | None = None) -> str:
    """Who Steward works for, as his instructions and refusals name them (B1, B6)."""
    return _entry(OWNER_ENV, environ) or OWNER_DEFAULT


def bash(environ: Mapping[str, str] | None = None) -> str | None:
    """The bash his shell runs (A5): STEWARD_BASH, else Git for Windows' under %ProgramFiles% on Windows, else None
    (MAF's own default, /bin/bash on Linux)."""
    if raw := _entry(BASH_ENV, environ):
        return str(install_path(raw))
    if os.name != "nt":
        return None
    program_files = _entry("ProgramFiles", environ) or r"C:\Program Files"
    return str(Path(program_files) / "Git" / "bin" / "bash.exe")


def ground_dir(inferred: Path | None, environ: Mapping[str, str] | None = None) -> Path | None:
    """Manjuel's ground (A7): STEWARD_GROUND_DIR when set, else what the caller inferred from the folder layout."""
    raw = _entry(GROUND_ENV, environ)
    return install_path(raw).resolve() if raw else inferred


def mcp_port(environ: Mapping[str, str] | None = None) -> int:
    """His MCP host's port (D7): STEWARD_MCP_PORT, else 43121. A value that is not a port raises, naming the entry."""
    raw = _entry(MCP_PORT_ENV, environ)
    if not raw:
        return MCP_PORT_DEFAULT
    if not (raw.isdigit() and 0 < int(raw) < 65536):
        raise ValueError(f"{MCP_PORT_ENV}={raw!r} is not a port: use a number from 1 to 65535")
    return int(raw)


# <binding>
BINDING_ENV = "STEWARD_BINDING"
BINDING_FILE = "binding.us"
# The APIs Steward's clients speak today. STEW also allows "openai-compatible"; a binding naming it is refused by name
# until Steward has that client (ExecPlan 0006 P4).
BINDING_APIS = ("ollama",)
_BINDING_KEYS = {"stew", "kind", "name", "api", "endpoint", "model", "provides", "hardware", "options"}
_PROVIDES = {"tool_calling", "context", "structured_output", "reasoning_effort"}
# A .us file: Markdown with exactly one ```json block (STEW tools/validate.py, BLOCK_RE).
_JSON_BLOCK = re.compile(r"^```json[ \t]*\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)
# A profile's requires (STEW spec/profile.md; spec 002 as ExecPlan 0006 P2 amends it): min_context None means "to be
# measured" (the smallest window its cases pass with, not guessed), and nothing is checked for it until it is.
REQUIRES_KEYS = ("tool_calling", "min_context", "reasoning_effort")
logger = logging.getLogger(__name__)


class BindingError(ValueError):
    """A binding that cannot be used: one line saying what is wrong and where."""


@dataclass(frozen=True)
class Binding:
    """The install's model, as its binding declares it (STEW spec/binding.md)."""

    name: str
    api: str
    endpoint: str
    model: str
    provides: Mapping[str, Any]
    hardware: str = ""
    options: Mapping[str, Any] = field(default_factory=dict)
    path: Path | None = None

    @property
    def context(self) -> int:
        """The window every call loads the model with: the options' num_ctx, else what the model provides."""
        return int(self.options.get("num_ctx") or self.provides["context"])

    def offers(self, what: str) -> bool:
        """Whether the binding provides it (tool_calling, structured_output, reasoning_effort)."""
        return self.provides.get(what) is True


def binding_path(environ: Mapping[str, str] | None = None) -> Path:
    """The binding's file: STEWARD_BINDING (relative to the install folder), else binding.us in the install folder."""
    return install_path(_entry(BINDING_ENV, environ) or BINDING_FILE)


def parse_binding(text: str, where: str = BINDING_FILE) -> Binding:
    """A binding read from a .us file's text; BindingError names the first thing wrong, in one line."""
    blocks = _JSON_BLOCK.findall(text.replace("\r\n", "\n"))
    if len(blocks) != 1:
        raise BindingError(f"{where}: a .us file holds exactly one ```json block; found {len(blocks)}")
    try:
        raw = json.loads(blocks[0])
    except ValueError as error:
        raise BindingError(f"{where}: its json block does not parse: {error}") from error
    if not isinstance(raw, dict) or raw.get("kind") != "binding":
        raise BindingError(f"{where}: not a STEW binding (kind: binding)")
    if unknown := sorted(set(raw) - _BINDING_KEYS):
        raise BindingError(f"{where}: unknown member(s) {unknown}")
    for key in ("name", "api", "endpoint", "model"):
        if not (isinstance(raw.get(key), str) and raw[key].strip()):
            raise BindingError(f"{where}: {key} is missing or empty")
    if raw["api"] not in BINDING_APIS:
        raise BindingError(f"{where}: api {raw['api']!r} is not one Steward speaks yet ({', '.join(BINDING_APIS)})")
    if not re.match(r"https?://[^\s/]+", raw["endpoint"]):
        raise BindingError(f"{where}: endpoint {raw['endpoint']!r} is not an http(s) URL")
    provides = raw.get("provides")
    if not (isinstance(provides, dict) and set(provides) <= _PROVIDES and isinstance(provides.get("tool_calling"), bool)
            and isinstance(provides.get("context"), int) and not isinstance(provides.get("context"), bool)
            and provides["context"] > 0):
        raise BindingError(f"{where}: provides is not {{tool_calling: true|false, context: <tokens>, ...}} of {sorted(_PROVIDES)}")
    options = raw.get("options", {})
    if not isinstance(options, dict):
        raise BindingError(f"{where}: options is not a mapping")
    if "num_ctx" in options and not (isinstance(options["num_ctx"], int) and 0 < options["num_ctx"] <= provides["context"]):
        raise BindingError(f"{where}: options.num_ctx is not a window from 1 to provides.context ({provides['context']})")
    return Binding(
        name=raw["name"], api=raw["api"], endpoint=raw["endpoint"].rstrip("/"), model=raw["model"],
        provides=dict(provides), hardware=str(raw.get("hardware") or ""), options=dict(options),
    )


def load_binding(path: Path | None = None) -> Binding:
    """The binding in its file (binding_path() by default); BindingError, in one line, when it is missing or bad."""
    path = binding_path() if path is None else path
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise BindingError(
            f"{path.name}: the install's binding cannot be read ({error.strerror or error}); write one "
            f"(STEW spec/binding.md) or set {BINDING_ENV}"
        ) from error
    binding = parse_binding(text, path.name)
    return Binding(**{**binding.__dict__, "path": path})


_LOADED: dict[str, Binding] = {}
_USING: ContextVar[Binding | None] = ContextVar("steward_binding", default=None)


def current_binding() -> Binding:
    """The binding this run is on: one an eval case runs under (using_binding), else the install's, read once."""
    if (binding := _USING.get()) is not None:
        return binding
    if "install" not in _LOADED:
        _LOADED["install"] = load_binding()
    return _LOADED["install"]


@contextmanager
def using_binding(binding: Binding | Path) -> Iterator[Binding]:
    """Run under another binding (an eval case's `binding:`): a profile's requires are checked against it."""
    binding = load_binding(binding) if isinstance(binding, Path) else binding
    token = _USING.set(binding)
    try:
        yield binding
    finally:
        _USING.reset(token)


def apply_binding(environ: Any = None) -> Binding:
    """The install's binding read (current_binding) and put where MAF's Ollama clients read the model: OLLAMA_MODEL and
    OLLAMA_HOST. A different value already there (an older `.env`) is replaced, and said once in the log."""
    environ = os.environ if environ is None else environ
    binding = current_binding()
    for name, value in (("OLLAMA_MODEL", binding.model), ("OLLAMA_HOST", binding.endpoint)):
        if (old := environ.get(name)) and old.rstrip("/") != value:
            logger.info("%s=%s replaced by the binding %s: %s", name, old, binding.name, value)
        environ[name] = value
    return binding


def requires_problems(requires: Any) -> list[str]:
    """What is wrong with a profile's requires: {tool_calling: bool, min_context: <tokens> or null (to be measured),
    reasoning_effort: bool}."""
    if not isinstance(requires, dict) or set(requires) != set(REQUIRES_KEYS):
        return [f"requires is not {{{', '.join(REQUIRES_KEYS)}}}"]
    problems = [
        f"requires.{key} is not true or false" for key in ("tool_calling", "reasoning_effort") if not isinstance(requires[key], bool)
    ]
    window = requires["min_context"]
    if window is not None and not (isinstance(window, int) and not isinstance(window, bool) and window > 0):
        problems.append("requires.min_context is not a number of tokens, or null (to be measured)")
    return problems


def unmet(requires: Mapping[str, Any], binding: Binding) -> list[str]:
    """What a profile requires that the binding does not offer, in words; [] when it fits."""
    missing = []
    if requires.get("tool_calling") and not binding.offers("tool_calling"):
        missing.append("tool calling")
    if (window := requires.get("min_context")) and binding.context < window:
        missing.append(f"a context window of {window} tokens (it loads {binding.context})")
    if requires.get("reasoning_effort") and not binding.offers("reasoning_effort"):
        missing.append("reasoning effort")
    return missing


def binding_refusal(profile: str, requires: Mapping[str, Any], binding: Binding | None = None) -> str | None:
    """The one-line refusal of a run whose profile the binding does not fit (STEW spec/binding.md rule 2), or None."""
    binding = current_binding() if binding is None else binding
    if not (missing := unmet(requires, binding)):
        return None
    where = binding.path.name if binding.path is not None else BINDING_FILE
    return (
        f"Not done: the {profile} profile needs {' and '.join(missing)}, which this install's binding {binding.name} "
        f"({binding.model}) does not offer. Bind a model that does, in {where}."
    )
# </binding>
