"""`premura install-client` — idempotent MCP registration, default surface only.

Onboarding arc gap #1 (ADR 0016): one command registers the default
``premura-mcp`` surface with a coding-agent client by merging one entry into
that client's config file. Three invariants matter and are asserted here:

* **Portable launch command** — the entry runs ``uvx --from git+…/premura
  premura-mcp`` so a cold user needs no clone and no PyPI publish.
* **Idempotent** — running twice writes the entry once, never a duplicate.
* **Operator surface is never auto-registered** — no config this module writes
  may reference ``premura-mcp-operator`` or ``--ack`` (the raw-SQL escape hatch
  stays a deliberate manual step).

All fixtures are synthetic temp dirs (no PHI).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from premura.harness.client_install import CLIENTS, REPO_URL, register_client


def _all_configs(root: Path, home: Path) -> str:
    """Concatenate every config file the installer could write, for grepping."""
    paths = [root / ".mcp.json", root / "opencode.json", home / ".codex" / "config.toml"]
    return "\n".join(p.read_text() for p in paths if p.exists())


@pytest.mark.parametrize("client", sorted(CLIENTS))
def test_registers_then_idempotent(tmp_path: Path, client: str) -> None:
    root = tmp_path / "repo"
    home = tmp_path / "home"
    root.mkdir()
    home.mkdir()

    first = register_client(client, root, home)
    assert first.changed is True
    assert first.config_path.exists()

    second = register_client(client, root, home)
    assert second.changed is False  # already present -> no-op
    assert second.config_path == first.config_path


@pytest.mark.parametrize("client", sorted(CLIENTS))
def test_writes_portable_uvx_command(tmp_path: Path, client: str) -> None:
    """Cold user (no clone): a bare tmp dir has no pyproject.toml, so the
    installer falls back to the portable uvx form."""
    root = tmp_path / "repo"
    home = tmp_path / "home"
    root.mkdir()
    home.mkdir()

    register_client(client, root, home)
    blob = _all_configs(root, home)
    # The portable form: fetch-and-run from the public repo via uvx, no clone.
    assert "uvx" in blob
    assert REPO_URL in blob
    assert "premura-mcp" in blob


@pytest.mark.parametrize("client", sorted(CLIENTS))
def test_clone_registers_local_uv_run(tmp_path: Path, client: str) -> None:
    """From a Premura clone (pyproject.toml names the premura project), the
    installer registers the clone-local server so the operator's own edits
    reach the running server, instead of the published uvx form."""
    root = tmp_path / "repo"
    home = tmp_path / "home"
    root.mkdir()
    home.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "premura"\n')

    register_client(client, root, home)
    blob = _all_configs(root, home)

    assert "uvx" not in blob
    assert REPO_URL not in blob
    assert "uv" in blob
    assert "run" in blob
    assert "premura-mcp" in blob
    assert str(root) in blob


def test_codex_append_preserves_existing_table(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    (codex / "config.toml").write_text('[mcp_servers.other]\ncommand = "echo"\nargs = []\n')

    register_client("codex", tmp_path / "repo", home)

    parsed = tomllib.loads((codex / "config.toml").read_text())
    # The pre-existing server survives, and premura is added alongside it.
    assert set(parsed["mcp_servers"]) == {"other", "premura"}
    assert parsed["mcp_servers"]["premura"]["command"] == "uvx"


def test_never_registers_operator_surface(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    home = tmp_path / "home"
    root.mkdir()
    home.mkdir()

    for client in CLIENTS:
        register_client(client, root, home)

    blob = _all_configs(root, home)
    assert "premura-mcp-operator" not in blob
    assert "--ack" not in blob
    assert "premura-mcp" in blob  # the default surface *is* present
