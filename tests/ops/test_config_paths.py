"""Config path defaults — durable, XDG-respecting, never the checkout (ADR 0016).

The warehouse must not default into the repo: a ``uvx``-launched MCP server runs
from uv's disposable cache, so a repo-relative default would put private health
data where uv can garbage-collect it. These tests lock the durable default and
the ``PREMURA_DATA_DIR`` override that keeps the two concerns decoupled.
"""

from __future__ import annotations

from pathlib import Path

from premura.config import REPO_ROOT, Settings


def test_data_dir_default_is_durable_not_repo(monkeypatch) -> None:
    monkeypatch.delenv("PREMURA_DATA_DIR", raising=False)
    data_dir = Settings().data_dir
    assert data_dir.name == "premura"
    # Never inside the checkout — that is the uvx-safety property.
    assert REPO_ROOT != data_dir and REPO_ROOT not in data_dir.parents
    # Warehouse hangs off the durable data dir, not the repo.
    assert REPO_ROOT not in Settings().warehouse_path.parents


def test_data_dir_env_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PREMURA_DATA_DIR", str(tmp_path / "custom"))
    assert Settings().data_dir == tmp_path / "custom"
