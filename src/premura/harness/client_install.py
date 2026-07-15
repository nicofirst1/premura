"""Register Premura's default MCP surface with a coding-agent client.

The onboarding front door: one command per client so a human never edits config
by hand. Every client reduces to the same act — an *idempotent merge* of one
server entry into that client's config file — so adding a fourth harness is one
registry entry (``CLIENTS``), not a new code path. This is DOCTRINE rule 2
(guide, don't enumerate) applied to the installer.

Launch command: from a Premura clone (a directory whose ``pyproject.toml``
names the ``premura`` project), register the clone-local server (`uv run
--directory <clone> premura-mcp`) so the operator's own edits - new parsers,
fixes - reach the running server. From a cold directory with no clone, fall
back to the portable form that fetches and runs the published surface via
``uvx`` straight from the public repo, so a cold user needs no clone and no
PyPI publish (uv is the only prerequisite). The durable XDG data dir (see
premura.config) means the ephemeral uvx env never touches the warehouse.
See ``ADR 0016``.

Security rail (non-negotiable): only the validity-gated default surface
(``premura-mcp``) is ever written here. The operator surface
(``premura-mcp-operator --ack``, the raw-SQL escape hatch) is NEVER
auto-registered — registering it stays a deliberate, user-approved manual step,
documented in ``docs/using/OPERATIONS.md``. The launch args below are fixed
to ``premura-mcp``; there is no code path that emits ``--ack`` or the operator
script name.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

SERVER_NAME = "premura"
REPO_URL = "git+https://github.com/nicofirst1/premura"


def _launch_command(root: Path) -> list[str]:
    """MCP launch argv for a client registered from ``root``.

    From a Premura clone, register the clone-local server (`uv run --directory
    <clone> premura-mcp`) so the operator's own edits — new parsers, fixes — go
    live. From a cold directory with no clone, fall back to the portable uvx
    form that fetches and runs the published surface straight from the public
    repo (uv the only prerequisite, no clone, no PyPI publish). Either form
    launches only `premura-mcp`; the durable XDG data dir (premura.config) keeps
    the env off the warehouse.
    """
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            meta = tomllib.loads(pyproject.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            meta = {}
        if meta.get("project", {}).get("name") == "premura":
            return ["uv", "run", "--directory", str(root), "premura-mcp"]
    return ["uvx", "--from", REPO_URL, "premura-mcp"]


@dataclass(frozen=True)
class InstallResult:
    client: str
    config_path: Path
    changed: bool  # False => entry already present (idempotent no-op)


def _merge_json(path: Path, container_key: str, entry: dict, defaults: dict | None = None) -> bool:
    """Add ``SERVER_NAME -> entry`` under ``container_key``. Return True if written."""
    data: dict = {}
    if path.exists():
        data = json.loads(path.read_text() or "{}")
    container = data.setdefault(container_key, {})
    if SERVER_NAME in container:
        return False
    if defaults:
        for key, value in defaults.items():
            data.setdefault(key, value)
    container[SERVER_NAME] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return True


def _codex_table(launch: list[str]) -> str:
    args = json.dumps(launch[1:])
    return f'[mcp_servers.{SERVER_NAME}]\ncommand = "{launch[0]}"\nargs = {args}\n'


def _register_claude(root: Path, home: Path) -> InstallResult:
    # Claude Code reads project-scoped .mcp.json directly (same target the
    # `claude mcp add` CLI writes) — writing it is idempotent and binary-free.
    launch = _launch_command(root)
    path = root / ".mcp.json"
    changed = _merge_json(path, "mcpServers", {"command": launch[0], "args": launch[1:]})
    return InstallResult("claude", path, changed)


def _register_opencode(root: Path, home: Path) -> InstallResult:
    launch = _launch_command(root)
    path = root / "opencode.json"
    changed = _merge_json(
        path,
        "mcp",
        {"type": "local", "command": launch, "enabled": True},
        defaults={"$schema": "https://opencode.ai/config.json"},
    )
    return InstallResult("opencode", path, changed)


def _register_codex(root: Path, home: Path) -> InstallResult:
    launch = _launch_command(root)
    path = home / ".codex" / "config.toml"
    if path.exists():
        parsed = tomllib.loads(path.read_text())
        if SERVER_NAME in parsed.get("mcp_servers", {}):
            return InstallResult("codex", path, False)
        # Append the table at EOF: a header applies until the next header/EOF,
        # so appending is a safe merge without a TOML writer dependency.
        text = path.read_text().rstrip("\n")
        table = _codex_table(launch)
        path.write_text(f"{text}\n\n{table}" if text else table)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_codex_table(launch))
    return InstallResult("codex", path, True)


# The registry: adding a client = adding one entry here (guide, don't enumerate).
CLIENTS: dict[str, Callable[[Path, Path], InstallResult]] = {
    "claude": _register_claude,
    "opencode": _register_opencode,
    "codex": _register_codex,
}


def register_client(name: str, root: Path, home: Path) -> InstallResult:
    """Register the default surface with ``name``. Raises KeyError for unknown clients."""
    return CLIENTS[name](root, home)
