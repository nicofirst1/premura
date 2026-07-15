"""FR-8: launchd plist renders + parses as a valid Apple plist."""

from __future__ import annotations

import importlib.resources as resources
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jinja2 import Template


def _render(**overrides: str) -> str:
    template_text = resources.files("premura.ops").joinpath("launchd.plist.j2").read_text()
    ctx = {
        "label": "com.example.premura.monthly",
        "program_args": ["/opt/homebrew/bin/uv", "run", "premura", "run-monthly"],
        "working_dir": "/Users/test/repos/premura",
        "log_out": "/Users/test/Library/Logs/premura/out.log",
        "log_err": "/Users/test/Library/Logs/premura/err.log",
    }
    ctx.update(overrides)
    return Template(template_text).render(**ctx)


def test_plist_renders_all_required_keys() -> None:
    rendered = _render()
    parsed = plistlib.loads(rendered.encode("utf-8"))

    assert parsed["Label"] == "com.example.premura.monthly"
    assert parsed["ProgramArguments"] == [
        "/opt/homebrew/bin/uv",
        "run",
        "premura",
        "run-monthly",
    ]
    assert parsed["WorkingDirectory"] == "/Users/test/repos/premura"
    assert parsed["StandardOutPath"].endswith("/out.log")
    assert parsed["StandardErrorPath"].endswith("/err.log")
    assert parsed["RunAtLoad"] is False
    assert parsed["ProcessType"] == "Background"

    cal = parsed["StartCalendarInterval"]
    assert cal == {"Day": 1, "Hour": 10, "Minute": 0}

    env = parsed["EnvironmentVariables"]
    assert "PATH" in env
    assert "/opt/homebrew/bin" in env["PATH"]


def test_plist_label_is_configurable() -> None:
    rendered = _render(label="com.custom.foo.monthly")
    parsed = plistlib.loads(rendered.encode("utf-8"))
    assert parsed["Label"] == "com.custom.foo.monthly"


@pytest.mark.skipif(sys.platform != "darwin", reason="plutil is macOS-only")
@pytest.mark.skipif(shutil.which("plutil") is None, reason="plutil not on PATH")
def test_rendered_plist_passes_plutil_lint(tmp_path: Path) -> None:
    plist_path = tmp_path / "premura.plist"
    plist_path.write_text(_render())
    res = subprocess.run(
        ["plutil", "-lint", str(plist_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"plutil -lint failed: {res.stdout} {res.stderr}"
    assert "OK" in res.stdout


@pytest.mark.skipif(sys.platform != "darwin", reason="install-launchd is macOS-only")
def test_install_launchd_writes_valid_plist(tmp_path: Path, monkeypatch) -> None:
    """`premura install-launchd` writes a plutil-valid plist into the LaunchAgents dir."""
    fake_home = tmp_path / "home"
    fake_log = tmp_path / "logs"
    (fake_home / "Library" / "LaunchAgents").mkdir(parents=True)
    fake_log.mkdir(parents=True)

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    from premura import cli as cli_mod
    from premura.config import settings as live_settings

    monkeypatch.setattr(live_settings, "log_dir", fake_log)
    monkeypatch.setattr(live_settings, "launchd_label", "com.example.premura.monthly")

    monkeypatch.chdir(tmp_path)
    cli_mod.install_launchd()

    plist_path = fake_home / "Library" / "LaunchAgents" / "com.example.premura.monthly.plist"
    assert plist_path.exists(), f"install-launchd did not write {plist_path}"

    parsed = plistlib.loads(plist_path.read_bytes())
    assert parsed["Label"] == "com.example.premura.monthly"
    assert parsed["WorkingDirectory"] == str(tmp_path)

    if shutil.which("plutil") is not None:
        res = subprocess.run(
            ["plutil", "-lint", str(plist_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, res.stdout + res.stderr
