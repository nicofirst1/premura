"""Acceptance-first CLI tests for ``premura bootstrap`` (WP02).

These tests lock the observable behavior of the ``bootstrap`` command before it
is implemented. They drive the command through Typer's ``CliRunner`` and
monkeypatch WP01's service (:func:`premura.bootstrap.run_bootstrap`) at the
boundary the CLI calls, so no real local install runs and the tests focus on CLI
presentation and exit-code semantics.

Coverage map (subtasks T007-T012):

* T007 — acceptance-first command behavior (this whole file).
* T008 — ``bootstrap`` is registered on the Typer app.
* T009 — terminal handoff formatting (status, actions, blockers vs warnings,
  reload guidance, one next step).
* T010 — summary status -> exit code mapping (ready=0, partial-warning=0,
  blocked!=0).
* T011 — installed console-script coverage (``premura bootstrap`` invokable).
* T012 — setup-only safety: bootstrap never calls a health-data operation path.

Assertions target exact high-value phrases, not the whole Rich layout, so the
tests stay robust to cosmetic formatting changes.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from premura import bootstrap as bootstrap_service
from premura import cli
from premura.bootstrap import (
    ActionResult,
    BootstrapAction,
    BootstrapCheck,
    BootstrapRun,
    BootstrapSummary,
    CheckStatus,
    SkillSetupState,
    SummaryStatus,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Report builders — fake BootstrapRun objects so the CLI tests never run real
# installs. Each builder returns a fully-formed run in a known summary state.
# ---------------------------------------------------------------------------


def _skill_state(*, reload_required: bool) -> SkillSetupState:
    path = Path("/tmp/fresh-clone/.claude/skills")
    if reload_required:
        return SkillSetupState(
            installed_count=2,
            unchanged=False,
            install_path=path,
            reload_required=True,
            message=(
                "Installed or updated 2 skill file(s). "
                "Reload required: start a fresh agent session to see the new skills."
            ),
        )
    return SkillSetupState(
        installed_count=0,
        unchanged=True,
        install_path=path,
        reload_required=False,
        message="Skills already current. Reload not required for skill visibility.",
    )


def _ready_run() -> BootstrapRun:
    """A clean checkout: everything passed, nothing to reload, no warnings."""
    checks = [
        BootstrapCheck(
            name="uv available",
            category="command availability",
            status=CheckStatus.PASS,
            observed="uv found on PATH",
        ),
        BootstrapCheck(
            name="local dependencies installed",
            category="project environment",
            status=CheckStatus.PASS,
            observed="dependencies already current",
        ),
        BootstrapCheck(
            name="project skills installed",
            category="skill setup",
            status=CheckStatus.PASS,
            observed="skills already current",
        ),
    ]
    actions = [
        BootstrapAction(
            name="install_local_dependencies",
            scope="local checkout/environment",
            result=ActionResult.NO_CHANGE,
            detail="already current",
        ),
        BootstrapAction(
            name="install_or_verify_skills",
            scope="local checkout/environment",
            result=ActionResult.NO_CHANGE,
            detail="skills already current",
        ),
    ]
    summary = BootstrapSummary(
        status=SummaryStatus.READY,
        ready_for_operation=True,
        reload_guidance="reload not required",
        next_step=(
            "Local checkout is ready. Proceed to normal Premura operation per "
            "README/CONTRIBUTING (no health-data ingest is performed by bootstrap)."
        ),
        blockers=[],
        warnings=[],
    )
    return BootstrapRun(
        started_at=datetime.now(UTC),
        checkout_root=Path("/tmp/fresh-clone"),
        mode="install+verify",
        checks=checks,
        actions=actions,
        skill_setup=_skill_state(reload_required=False),
        summary=summary,
    )


def _partial_run() -> BootstrapRun:
    """Operation is safe but an optional capability is missing (warning only)."""
    checks = [
        BootstrapCheck(
            name="uv available",
            category="command availability",
            status=CheckStatus.PASS,
            observed="uv found on PATH",
        ),
        BootstrapCheck(
            name="local dependencies installed",
            category="project environment",
            status=CheckStatus.FIXED,
            observed="dependencies synced",
        ),
        BootstrapCheck(
            name="project skills installed",
            category="skill setup",
            status=CheckStatus.FIXED,
            observed="2 skill file(s) written",
        ),
        BootstrapCheck(
            name="rclone available",
            category="optional capability",
            status=CheckStatus.WARNING,
            observed="rclone not found on PATH",
            next_action="Encrypted-export upload is unavailable until rclone is set up.",
            local_action_allowed=False,
        ),
    ]
    actions = [
        BootstrapAction(
            name="install_local_dependencies",
            scope="local checkout/environment",
            result=ActionResult.CHANGED,
            detail="synced project dependencies",
        ),
        BootstrapAction(
            name="install_or_verify_skills",
            scope="local checkout/environment",
            result=ActionResult.CHANGED,
            detail="installed 2 skill file(s)",
        ),
    ]
    summary = BootstrapSummary(
        status=SummaryStatus.PARTIAL,
        ready_for_operation=True,
        reload_guidance="reload required",
        next_step=(
            "Local install is ready for normal Premura operation. Review the "
            "warning(s); if skills changed, reload your agent session first."
        ),
        blockers=[],
        warnings=[
            "rclone available: Encrypted-export upload is unavailable until rclone is set up.",
            _skill_state(reload_required=True).message,
        ],
    )
    return BootstrapRun(
        started_at=datetime.now(UTC),
        checkout_root=Path("/tmp/fresh-clone"),
        mode="install+verify",
        checks=checks,
        actions=actions,
        skill_setup=_skill_state(reload_required=True),
        summary=summary,
    )


def _blocked_run() -> BootstrapRun:
    """A required prerequisite is missing: not ready for operation."""
    checks = [
        BootstrapCheck(
            name="uv available",
            category="external prerequisite",
            status=CheckStatus.BLOCKED,
            observed="uv not found on PATH",
            next_action=(
                "Install uv (the project dependency manager) following its official "
                "install guide, then re-run bootstrap."
            ),
            local_action_allowed=False,
        ),
        BootstrapCheck(
            name="project skills installed",
            category="skill setup",
            status=CheckStatus.PASS,
            observed="skills already current",
        ),
    ]
    actions = [
        BootstrapAction(
            name="install_local_dependencies",
            scope="external/system",
            result=ActionResult.NOT_ATTEMPTED,
            detail="uv unavailable; not installing system-wide",
        ),
        BootstrapAction(
            name="install_or_verify_skills",
            scope="local checkout/environment",
            result=ActionResult.NO_CHANGE,
            detail="skills already current",
        ),
    ]
    summary = BootstrapSummary(
        status=SummaryStatus.BLOCKED,
        ready_for_operation=False,
        reload_guidance="reload not required",
        next_step=(
            "Resolve the listed blocker(s), then re-run bootstrap. "
            "Do not start normal Premura operation yet."
        ),
        blockers=[
            "uv available: Install uv (the project dependency manager) following its "
            "official install guide, then re-run bootstrap."
        ],
        warnings=[],
    )
    return BootstrapRun(
        started_at=datetime.now(UTC),
        checkout_root=Path("/tmp/fresh-clone"),
        mode="install+verify",
        checks=checks,
        actions=actions,
        skill_setup=_skill_state(reload_required=False),
        summary=summary,
    )


def _patch_run_bootstrap(monkeypatch: pytest.MonkeyPatch, run: BootstrapRun) -> list[Path]:
    """Patch the service boundary the CLI calls; record the project root passed."""
    seen_roots: list[Path] = []

    def fake_run_bootstrap(project_root: Path, **_kwargs: object) -> BootstrapRun:
        seen_roots.append(Path(project_root))
        return run

    # Patch at the name the CLI module actually calls so the CLI's import style
    # (module attribute vs. direct symbol) does not matter.
    monkeypatch.setattr(cli, "run_bootstrap", fake_run_bootstrap, raising=True)
    return seen_roots


# ---------------------------------------------------------------------------
# T008 — command registration
# ---------------------------------------------------------------------------


def test_cli_registers_bootstrap_command() -> None:
    """``bootstrap`` is registered on the Typer app under that exact name."""
    commands = {cmd.name for cmd in cli.app.registered_commands}
    assert "bootstrap" in commands, f"expected a bootstrap command, got {sorted(commands)}"


def test_cli_bootstrap_help_marks_setup_not_ingest() -> None:
    """The help string must make clear this is fresh-clone/setup readiness."""
    result = runner.invoke(cli.app, ["bootstrap", "--help"])
    assert result.exit_code == 0
    text = result.stdout.lower()
    assert "setup" in text or "fresh" in text or "readiness" in text
    # It is framed as setup readiness, and if it mentions ingest at all it does
    # so only to disclaim it (e.g. "not ... ingest"), never to advertise itself
    # as an ingest/analysis verb.
    if "ingest" in text:
        assert "not" in text, "help mentions ingest but does not disclaim it"


# ---------------------------------------------------------------------------
# T009 / T010 — ready summary: actions + reload guidance, exit 0
# ---------------------------------------------------------------------------


def test_cli_ready_summary_prints_actions_and_reload_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_run_bootstrap(monkeypatch, _ready_run())
    result = runner.invoke(cli.app, ["bootstrap"])
    assert result.exit_code == 0, result.stdout
    out = result.stdout
    # Overall status near the top.
    assert "ready" in out.lower()
    # Local actions are surfaced (no-change is still reported).
    assert "install_or_verify_skills" in out or "skills" in out.lower()
    # Reload guidance always printed.
    assert "reload" in out.lower()
    # One safe next step.
    assert "next step" in out.lower()
    # Delegated to the service with the current working directory.
    assert seen, "run_bootstrap was not called"


# ---------------------------------------------------------------------------
# T010 — blocked summary exits non-zero with blocker + next action
# ---------------------------------------------------------------------------


def test_cli_blocked_summary_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run_bootstrap(monkeypatch, _blocked_run())
    result = runner.invoke(cli.app, ["bootstrap"])
    assert result.exit_code != 0, f"blocked run must exit non-zero, got 0\n{result.stdout}"
    out = result.stdout
    assert "blocked" in out.lower()
    # The blocker itself is named.
    assert "uv available" in out
    # An exact next action is given.
    assert "re-run bootstrap" in out.lower()
    # Reload guidance still printed even on the blocked path.
    assert "reload" in out.lower()


# ---------------------------------------------------------------------------
# T010 — partial with optional-only warnings can exit 0
# ---------------------------------------------------------------------------


def test_cli_partial_optional_warning_can_exit_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run_bootstrap(monkeypatch, _partial_run())
    result = runner.invoke(cli.app, ["bootstrap"])
    # Operation is safe (ready_for_operation=True) and only warnings remain.
    assert result.exit_code == 0, f"partial-warning run should exit 0\n{result.stdout}"
    out = result.stdout
    assert "partial" in out.lower()
    # The warning is surfaced as an optional/non-blocker item.
    assert "rclone" in out.lower()
    assert "warning" in out.lower()
    # There are no required blockers; the blocker section must say so explicitly
    # rather than listing the optional warning as a blocker.
    assert "blockers (required): none" in out.lower()
    # The rclone warning lives in the warnings section, not the blocker list.
    blocker_line = next(
        (line for line in out.splitlines() if "blockers (required)" in line.lower()),
        "",
    )
    assert "rclone" not in blocker_line.lower()


def test_cli_blockers_and_warnings_are_distinguishable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Required blockers must be visually/structurally distinct from warnings.

    Drive a run that has *both* a blocker and a warning and assert the rendered
    output keeps the blocker out of the warnings section.
    """
    run = _blocked_run()
    run.summary.warnings = [
        "rclone available: Encrypted-export upload is unavailable until rclone is set up."
    ]
    _patch_run_bootstrap(monkeypatch, run)
    result = runner.invoke(cli.app, ["bootstrap"])
    out = result.stdout
    # Both sections are labeled and present.
    assert "blocker" in out.lower()
    assert "warning" in out.lower()
    # The blocker phrase appears before the optional warning phrase (separate
    # sections, blockers first so they are not buried).
    blocker_idx = out.lower().find("uv available")
    warning_idx = out.lower().find("rclone")
    assert blocker_idx != -1 and warning_idx != -1
    assert blocker_idx < warning_idx, "blockers must appear before optional warnings"


# ---------------------------------------------------------------------------
# T009 — concise success output (200-line NFR)
# ---------------------------------------------------------------------------


def test_cli_output_stays_concise(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run_bootstrap(monkeypatch, _ready_run())
    result = runner.invoke(cli.app, ["bootstrap"])
    assert result.exit_code == 0
    line_count = len(result.stdout.splitlines())
    assert line_count < 200, f"success output must stay under 200 lines, got {line_count}"


# ---------------------------------------------------------------------------
# T012 — setup-only safety at the CLI layer
# ---------------------------------------------------------------------------


def test_cli_does_not_invoke_health_operations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running ``bootstrap`` must not reach any health-data operation path."""

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("bootstrap invoked a forbidden health-data operation")

    # Trip-wire the forbidden CLI/operation surfaces.
    monkeypatch.setattr(cli, "ingest", _boom, raising=True)
    monkeypatch.setattr(cli, "run_monthly", _boom, raising=True)
    monkeypatch.setattr(cli, "_do_upload", _boom, raising=True)
    monkeypatch.setattr(cli, "export", _boom, raising=True)

    _patch_run_bootstrap(monkeypatch, _ready_run())
    result = runner.invoke(cli.app, ["bootstrap"])
    assert result.exit_code == 0, result.stdout
    # If any trip-wire fired, CliRunner would capture the AssertionError as a
    # non-zero exit with the message in the exception; assert it did not.
    assert result.exception is None, result.exception


def test_cli_bootstrap_succeeds_in_empty_temp_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An empty temp project root (no data/inbox, no warehouse) must work.

    The service is faked, but this also asserts the CLI passes ``Path.cwd()`` to
    the service rather than requiring any private directory to exist.
    """
    seen = _patch_run_bootstrap(monkeypatch, _ready_run())
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli.app, ["bootstrap"])
    assert result.exit_code == 0, result.stdout
    assert seen and seen[0] == tmp_path


def test_cli_does_not_swallow_service_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real exception from the service must not become a false success.

    The risk-checklist forbids catch-all-and-report-success. If the service
    raises, the command must surface a non-zero exit, not exit 0.
    """

    def _raise(*_args: object, **_kwargs: object) -> BootstrapRun:
        raise RuntimeError("service exploded")

    monkeypatch.setattr(cli, "run_bootstrap", _raise, raising=True)
    result = runner.invoke(cli.app, ["bootstrap"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# T011 — installed console-script coverage
# ---------------------------------------------------------------------------


def test_premura_bootstrap_console_script_is_invokable(tmp_path: Path) -> None:
    """``premura bootstrap`` is invokable end-to-end as the installed console script.

    Follows the existing ``tests/test_skeleton.py`` pattern: locate the installed
    binary next to ``sys.executable`` and skip if it is absent (do not fail
    unrelated environments). We run in an *empty temp project root* so no real
    private data exists.

    To avoid a real dependency install in the subprocess we force the dependency
    manager to look absent via PATH, which makes bootstrap take its blocked path
    deterministically — that is a *controlled* non-zero exit, and it still
    proves the command exists and emits bootstrap output (overall status +
    reload guidance), not a "no such command" error.
    """
    premura_bin = Path(sys.executable).parent / "premura"
    if not premura_bin.is_file():
        pytest.skip(f"premura console script not installed at {premura_bin}")

    project_root = tmp_path / "project"
    project_root.mkdir()

    # Empty PATH (plus the dir holding premura so the binary itself resolves) makes
    # `uv` look missing, so bootstrap takes its blocked path without installing.
    env = {
        "PATH": str(premura_bin.parent),
        "HOME": str(tmp_path),
    }
    result = subprocess.run(
        [str(premura_bin), "bootstrap"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    combined = (result.stdout + result.stderr).lower()
    # The command must exist (not "No such command 'bootstrap'").
    assert "no such command" not in combined, (
        f"premura bootstrap is not registered as a console command:\n{combined}"
    )
    # It must emit real bootstrap handoff output: an overall status word and
    # reload guidance. Either ready/partial/blocked is acceptable here.
    assert any(word in combined for word in ("ready", "partial", "blocked")), (
        f"premura bootstrap did not print an overall status:\n{combined}"
    )
    assert "reload" in combined, f"premura bootstrap did not print reload guidance:\n{combined}"


def test_bootstrap_module_is_importable() -> None:
    """Sanity: the CLI imports the real WP01 service symbol it delegates to."""
    mod = importlib.import_module("premura.cli")
    assert hasattr(mod, "run_bootstrap")
    assert mod.run_bootstrap is bootstrap_service.run_bootstrap
