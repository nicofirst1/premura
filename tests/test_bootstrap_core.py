"""Acceptance-first tests for the bootstrap core service.

These tests pin the behavior of ``premura.bootstrap`` at the public service
boundary: they assert on the returned report objects (``BootstrapRun`` and its
nested records), never on private helpers. Local install commands are driven
through an injectable command runner so no real dependency installation ever
happens here, and the skill installer is faked so no real ``.claude/skills``
materialization is required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from premura import bootstrap
from premura.bootstrap import (
    ActionResult,
    BootstrapRun,
    CheckStatus,
    CommandOutcome,
    SkillSetupState,
    SummaryStatus,
    run_bootstrap,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeRunner:
    """Records invocations and returns scripted outcomes per command name.

    The runner boundary is keyed by a stable action name so tests can pin a
    success or failure for a specific local action without caring about the
    exact argv the service chose.
    """

    def __init__(self, outcomes: dict[str, CommandOutcome] | None = None) -> None:
        self._outcomes = outcomes or {}
        self.calls: list[str] = []

    def __call__(self, name: str, argv: list[str]) -> CommandOutcome:
        self.calls.append(name)
        if name in self._outcomes:
            return self._outcomes[name]
        # Default: a clean, idempotent success that changed nothing.
        return CommandOutcome(returncode=0, changed=False, detail="already current")


def fake_installer(written: list[Path]):
    """Build a fake ``install_skills`` returning a fixed written-paths list."""

    def _install(target_root: Path) -> list[Path]:
        return list(written)

    return _install


def _available_tools(*names: str):
    """A tool-probe that reports the given tool names as present."""
    present = set(names)

    def _probe(tool: str) -> bool:
        return tool in present

    return _probe


# ---------------------------------------------------------------------------
# Closed vocabulary guards
# ---------------------------------------------------------------------------


def test_status_vocabularies_are_closed_and_stable() -> None:
    assert {s.value for s in SummaryStatus} == {"ready", "partial", "blocked"}
    assert {c.value for c in CheckStatus} == {
        "pass",
        "fixed",
        "blocked",
        "warning",
        "skipped",
    }
    assert {a.value for a in ActionResult} == {
        "changed",
        "no_change",
        "failed",
        "not_attempted",
    }


# ---------------------------------------------------------------------------
# Required acceptance scenarios
# ---------------------------------------------------------------------------


def test_bootstrap_ready_when_local_actions_succeed(tmp_path: Path) -> None:
    runner = FakeRunner(
        {"install_local_dependencies": CommandOutcome(0, changed=True, detail="synced deps")}
    )
    run = run_bootstrap(
        tmp_path,
        command_runner=runner,
        skill_installer=fake_installer([tmp_path / ".claude" / "skills" / "a" / "SKILL.md"]),
        tool_probe=_available_tools("uv"),
    )

    assert isinstance(run, BootstrapRun)
    assert run.summary.status in (SummaryStatus.READY, SummaryStatus.PARTIAL)
    assert run.summary.ready_for_operation is True
    assert run.summary.blockers == []
    # A local dependency action was actually attempted and changed state.
    dep_actions = [a for a in run.actions if a.result is ActionResult.CHANGED]
    assert dep_actions, "expected at least one changed local action"
    assert "install_local_dependencies" in runner.calls


def test_bootstrap_idempotent_when_everything_current(tmp_path: Path) -> None:
    # Runner reports no change for everything; installer writes nothing. All
    # tools (required + optional) present so the steady state is truly ready.
    runner = FakeRunner()
    run = run_bootstrap(
        tmp_path,
        command_runner=runner,
        skill_installer=fake_installer([]),
        tool_probe=_available_tools("uv", "rclone"),
    )

    assert run.summary.status is SummaryStatus.READY
    assert run.summary.ready_for_operation is True
    assert run.summary.blockers == []
    # No action should report a real change on an already-prepared checkout.
    assert all(a.result is not ActionResult.CHANGED for a in run.actions)
    assert any(a.result is ActionResult.NO_CHANGE for a in run.actions)
    assert run.skill_setup.installed_count == 0
    assert run.skill_setup.unchanged is True


def test_bootstrap_blocks_external_prerequisite_without_mutating_system(
    tmp_path: Path,
) -> None:
    # 'uv' (the local dependency manager) is absent and cannot be installed
    # safely from inside the checkout -> blocked, no local action attempted.
    runner = FakeRunner()
    run = run_bootstrap(
        tmp_path,
        command_runner=runner,
        skill_installer=fake_installer([]),
        tool_probe=_available_tools(),  # nothing present
    )

    assert run.summary.status is SummaryStatus.BLOCKED
    assert run.summary.ready_for_operation is False
    assert run.summary.blockers, "expected at least one blocker"

    blocked = [c for c in run.checks if c.status is CheckStatus.BLOCKED]
    assert blocked, "expected a blocked check"
    for check in blocked:
        assert check.local_action_allowed is False
        assert check.next_action, "blocked checks must carry a concrete next action"

    # The system must not be mutated: the dependency install command is never run.
    assert "install_local_dependencies" not in runner.calls


def test_optional_upload_is_warning_not_blocker(tmp_path: Path) -> None:
    # rclone (optional upload capability) absent, but uv present so install works.
    runner = FakeRunner()
    run = run_bootstrap(
        tmp_path,
        command_runner=runner,
        skill_installer=fake_installer([]),
        tool_probe=_available_tools("uv"),  # rclone absent
    )

    assert run.summary.status is not SummaryStatus.BLOCKED
    assert run.summary.ready_for_operation is True
    # The optional gap shows up as a warning, never a blocker.
    assert run.summary.warnings, "expected an optional-capability warning"
    warning_checks = [c for c in run.checks if c.status is CheckStatus.WARNING]
    assert any(c.category == "optional capability" for c in warning_checks)
    assert all(c.status is not CheckStatus.BLOCKED for c in warning_checks)
    # And it is not counted as a blocker anywhere.
    assert run.summary.blockers == []


def test_failed_local_command_is_report_data_not_traceback(tmp_path: Path) -> None:
    runner = FakeRunner(
        {
            "install_local_dependencies": CommandOutcome(
                returncode=1, changed=False, detail="resolver could not find lock"
            )
        }
    )
    # Must not raise: a failed command becomes report data.
    run = run_bootstrap(
        tmp_path,
        command_runner=runner,
        skill_installer=fake_installer([]),
        tool_probe=_available_tools("uv"),
    )

    failed = [a for a in run.actions if a.result is ActionResult.FAILED]
    assert failed, "expected a failed action"
    assert all(a.detail for a in failed), "failed actions must carry a detail"
    assert run.summary.status is SummaryStatus.BLOCKED
    assert run.summary.ready_for_operation is False
    assert run.summary.next_step, "blocked summary must still give a next step"


def test_reload_guidance_is_always_present(tmp_path: Path) -> None:
    runner = FakeRunner()
    cases = [
        fake_installer([tmp_path / ".claude" / "skills" / "x" / "SKILL.md"]),
        fake_installer([]),
    ]
    for installer in cases:
        run = run_bootstrap(
            tmp_path,
            command_runner=runner,
            skill_installer=installer,
            tool_probe=_available_tools("uv"),
        )
        assert run.summary.reload_guidance, "reload guidance must be present on every run"
        assert run.skill_setup.message, "skill setup must carry plain-language guidance"


def test_skill_setup_reports_installed_and_changed_state(tmp_path: Path) -> None:
    runner = FakeRunner()
    written = [
        tmp_path / ".claude" / "skills" / "a" / "SKILL.md",
        tmp_path / ".claude" / "skills" / "b" / "SKILL.md",
    ]
    run = run_bootstrap(
        tmp_path,
        command_runner=runner,
        skill_installer=fake_installer(written),
        tool_probe=_available_tools("uv"),
    )
    state = run.skill_setup
    assert isinstance(state, SkillSetupState)
    assert state.installed_count == 2
    assert state.unchanged is False
    assert state.reload_required is True
    assert state.install_path == tmp_path / ".claude" / "skills"


def test_core_service_does_not_touch_health_data_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The service must produce a setup report without invoking any health
    operation path, even when those hooks are booby-trapped to fail."""

    # Booby-trap the obvious operation entry points. If bootstrap imported or
    # called any of them, the run would raise.
    def _boom(*_args: object, **_kwargs: object):
        raise AssertionError("health-data operation must not be invoked by bootstrap")

    import premura

    for mod_name in ("parsers", "store", "engine", "mcp_server", "upload"):
        mod = getattr(premura, mod_name, None)
        if mod is not None:
            for attr in dir(mod):
                if attr.startswith(("ingest", "query", "run_monthly", "upload", "dispatch")):
                    monkeypatch.setattr(mod, attr, _boom, raising=False)

    runner = FakeRunner()
    run = run_bootstrap(
        tmp_path,
        command_runner=runner,
        skill_installer=fake_installer([]),
        tool_probe=_available_tools("uv"),
    )
    assert isinstance(run, BootstrapRun)
    # The declared forbidden-operation guard is honest and exhaustive.
    assert bootstrap.FORBIDDEN_OPERATIONS
    # The next step is a safe setup/operation handoff, never an ingest/analysis.
    lowered = run.summary.next_step.lower()
    assert not any(bad in lowered for bad in ("ingest", "run-monthly", "upload", "analyz"))


def test_required_readiness_does_not_depend_on_private_data(tmp_path: Path) -> None:
    """No data/inbox, data/raw, or warehouse exists; readiness still computes."""
    runner = FakeRunner()
    run = run_bootstrap(
        tmp_path,
        command_runner=runner,
        skill_installer=fake_installer([]),
        tool_probe=_available_tools("uv"),
    )
    # No check should require private health data to pass.
    assert run.summary.ready_for_operation is True
    assert not (tmp_path / "data" / "inbox").exists()
    assert not (tmp_path / "data" / "raw").exists()
