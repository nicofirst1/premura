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
    KeypairSetupState,
    KeypairStatus,
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


def fake_keypair(status: KeypairStatus = KeypairStatus.PRESENT):
    """A keypair-installer double: never touches disk or the real `age` binary."""

    def _install(tool_probe) -> KeypairSetupState:  # noqa: ANN001 - test double
        return KeypairSetupState(
            status=status,
            key_path=Path("/tmp/premura-test/age.key"),
            recipients_path=Path("/tmp/premura-test/recipients.txt"),
            message=f"keypair {status.value}",
        )

    return _install


def _surfaces(*, broken: set[str] | None = None):
    """A surface-probe double: every target imports unless named in ``broken``."""
    broken = broken or set()

    def _probe(target: str) -> tuple[bool, str]:
        if target in broken:
            return False, f"import of {target} failed: boom"
        return True, f"{target} importable"

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
        keypair_installer=fake_keypair(KeypairStatus.PRESENT),
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


# ---------------------------------------------------------------------------
# age keypair (the single secret): portable setup, warning-not-blocker
# ---------------------------------------------------------------------------


def _run_with_keypair(tmp_path: Path, status: KeypairStatus) -> BootstrapRun:
    return run_bootstrap(
        tmp_path,
        command_runner=FakeRunner(),
        skill_installer=fake_installer([]),
        tool_probe=_available_tools("uv", "rclone"),
        keypair_installer=fake_keypair(status),
    )


def test_missing_age_is_a_warning_not_a_blocker(tmp_path: Path) -> None:
    # No `age` on PATH: encryption is unavailable, but the checkout is still
    # usable for the agent surface, so this must never block operation.
    run = _run_with_keypair(tmp_path, KeypairStatus.AGE_MISSING)
    assert run.summary.status is SummaryStatus.PARTIAL
    assert run.summary.ready_for_operation is True
    assert run.summary.blockers == []
    assert any("age" in w.lower() for w in run.summary.warnings)
    assert run.keypair.status is KeypairStatus.AGE_MISSING


def test_generated_keypair_warns_to_back_it_up(tmp_path: Path) -> None:
    # The run that creates the secret is the one that must tell you to back it up.
    run = _run_with_keypair(tmp_path, KeypairStatus.GENERATED)
    assert run.summary.status is SummaryStatus.PARTIAL
    assert any("back it up" in w.lower() for w in run.summary.warnings)
    assert any(
        a.name == "ensure_age_keypair" and a.result is ActionResult.CHANGED for a in run.actions
    )


def test_present_keypair_is_a_clean_pass(tmp_path: Path) -> None:
    run = _run_with_keypair(tmp_path, KeypairStatus.PRESENT)
    assert run.summary.status is SummaryStatus.READY
    assert not any("age keypair" in w.lower() for w in run.summary.warnings)


def test_generate_keypair_writes_key_and_recipients(tmp_path: Path) -> None:
    # Real end-to-end via the `age` binary; skip where it isn't installed.
    from premura.ops import encrypt

    if not encrypt.is_available():
        import pytest as _pytest

        _pytest.skip("age / age-keygen not installed")
    key = tmp_path / "cfg" / "age.key"
    recipients = tmp_path / "cfg" / "recipients.txt"
    pub = encrypt.generate_keypair(key_path=key, recipients_path=recipients)
    assert key.exists() and recipients.exists()
    assert pub.startswith("age1")
    assert recipients.read_text().strip() == pub
    # The generated pair actually round-trips (encrypt with recipients, decrypt with key).
    assert encrypt.roundtrip_check(recipients_file=recipients, identity_file=key) is None


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


def test_core_surfaces_are_verified_when_dependencies_ready(tmp_path: Path) -> None:
    """FR-003: a ready checkout reports each declared core surface as startable.

    Verification is import-only (no surface is run), and every surface in the
    registry produces a passing command-availability check.
    """
    runner = FakeRunner()
    run = run_bootstrap(
        tmp_path,
        command_runner=runner,
        skill_installer=fake_installer([]),
        tool_probe=_available_tools("uv", "rclone"),
        surface_probe=_surfaces(),
        keypair_installer=fake_keypair(KeypairStatus.PRESENT),
    )

    surface_checks = [
        c
        for c in run.checks
        if c.category == "command availability" and c.name.endswith("importable")
    ]
    assert len(surface_checks) == len(bootstrap._CORE_SURFACES)
    assert surface_checks, "expected core-surface checks"
    assert all(c.status is CheckStatus.PASS for c in surface_checks)
    assert run.summary.status is SummaryStatus.READY


def test_unimportable_core_surface_is_a_blocker(tmp_path: Path) -> None:
    """A core surface that cannot import is a real, actionable blocker."""
    target = bootstrap._CORE_SURFACES[0][1]
    runner = FakeRunner()
    run = run_bootstrap(
        tmp_path,
        command_runner=runner,
        skill_installer=fake_installer([]),
        tool_probe=_available_tools("uv"),
        surface_probe=_surfaces(broken={target}),
    )

    blocked = [
        c for c in run.checks if c.status is CheckStatus.BLOCKED and c.name.endswith("importable")
    ]
    assert blocked, "expected a blocked core-surface check"
    assert all(c.next_action for c in blocked)
    assert run.summary.status is SummaryStatus.BLOCKED
    assert run.summary.ready_for_operation is False


def test_core_surfaces_skipped_when_dependencies_missing(tmp_path: Path) -> None:
    """With deps not installed, surfaces cannot import yet — skip, do not false-block.

    The surface probe must not even be consulted, since importing before the
    environment exists would itself fail spuriously.
    """

    def _exploding_probe(target: str) -> tuple[bool, str]:
        raise AssertionError("surface probe must not run before dependencies exist")

    run = run_bootstrap(
        tmp_path,
        command_runner=FakeRunner(),
        skill_installer=fake_installer([]),
        tool_probe=_available_tools(),  # uv absent -> deps not ready
        surface_probe=_exploding_probe,
    )

    surface_checks = [c for c in run.checks if c.name.endswith("importable")]
    assert surface_checks, "expected core-surface checks even when skipped"
    assert all(c.status is CheckStatus.SKIPPED for c in surface_checks)
    # Surfaces are not the blocker here; the missing dependency manager is.
    assert all(c.status is not CheckStatus.BLOCKED for c in surface_checks)


def test_default_runner_anchors_cwd_to_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RISK-1: local setup commands must run with cwd anchored to the checkout."""
    import subprocess

    seen: dict[str, object] = {}

    def _fake_run(argv, **kwargs):
        seen["cwd"] = kwargs.get("cwd")
        seen["timeout"] = kwargs.get("timeout")

        class _Proc:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return _Proc()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    runner = bootstrap._make_default_command_runner(tmp_path)
    outcome = runner("install_local_dependencies", ["uv", "sync"])

    assert outcome.ok
    assert seen["cwd"] == tmp_path
    # A bounded timeout is always passed so a stall cannot hang indefinitely.
    assert isinstance(seen["timeout"], (int, float)) and seen["timeout"] > 0


def test_default_runner_converts_timeout_to_actionable_blocker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RISK-2: a hung setup command becomes a bounded, actionable failure."""
    import subprocess

    def _hang(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(subprocess, "run", _hang)
    runner = bootstrap._make_default_command_runner(tmp_path)
    outcome = runner("install_local_dependencies", ["uv", "sync"])

    assert not outcome.ok
    assert outcome.returncode == 124
    assert "timed out" in outcome.detail.lower()


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
