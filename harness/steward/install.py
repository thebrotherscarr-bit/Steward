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
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

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
