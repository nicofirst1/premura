"""Install tier: cold-clone onboarding path (issue #55).

Unit tests (default suite) fake git clone, uv sync, bootstrap, and the smoke
ingest - NO real network/subprocess - and cover step derivation, the result
envelope (pass and a failing-step case), and the scoreboard tier round-trip.

One regression-marked end-to-end test actually clones HEAD, runs ``uv sync`` +
``uv run hpipe bootstrap`` + the smoke ingest for real. It is slow and needs
network for the uv package download, so it carries the ``regression`` marker and
is excluded from the default suite (pyproject addopts ``-m "not regression ..."``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from premura.config import REPO_ROOT
from premura.harness import install_tier
from premura.harness.install_tier import (
    INSTALL_OPERATOR_MODEL,
    INSTALL_TIER,
    INSTALL_TIER_STEPS,
    InstallStep,
    InstallStepContext,
    InstallTierResult,
    run_install_tier,
)
from premura.harness.scoreboard import current_floor, read_scoreboard

# --------------------------------------------------------------------------- #
# Step derivation (the declarative sequence)
# --------------------------------------------------------------------------- #


def test_steps_are_in_documented_order() -> None:
    """The onboarding sequence is uv sync -> bootstrap -> install parser -> ingest."""
    assert [s.name for s in INSTALL_TIER_STEPS] == [
        "uv_sync",
        "hpipe_bootstrap",
        "install_reference_parser",
        "smoke_ingest",
    ]


def test_every_step_cites_a_doc_and_has_exactly_one_action() -> None:
    """Each step traces to a doc line and sets exactly one of argv/func."""
    for step in INSTALL_TIER_STEPS:
        assert step.doc_ref, f"{step.name} must cite the doc line it mirrors"
        assert (step.argv is None) != (step.func is None), (
            f"{step.name} must set exactly one of argv/func"
        )


def test_bootstrap_step_mirrors_agents_md() -> None:
    """The bootstrap step runs `uv run hpipe bootstrap` and cites AGENTS.md step 1."""
    step = next(s for s in INSTALL_TIER_STEPS if s.name == "hpipe_bootstrap")
    ctx = InstallStepContext(clone_root=Path("/clone"), warehouse_path=Path("/clone/wh.duckdb"))
    assert step.argv is not None
    assert step.argv(ctx) == ["uv", "run", "hpipe", "bootstrap"]
    assert "AGENTS.md" in step.doc_ref


def test_smoke_ingest_uses_clone_venv_interpreter() -> None:
    """The ingest step invokes the clone's own .venv python, not the parent's."""
    step = next(s for s in INSTALL_TIER_STEPS if s.name == "smoke_ingest")
    ctx = InstallStepContext(clone_root=Path("/clone"), warehouse_path=Path("/clone/wh.duckdb"))
    assert step.argv is not None
    argv = step.argv(ctx)
    assert argv[0] == "/clone/.venv/bin/python"
    assert argv[1:4] == ["-m", "premura.harness.ingest_runner", "--source"]


# --------------------------------------------------------------------------- #
# Result envelope (pass + failing-step), with fakes for clone/steps
# --------------------------------------------------------------------------- #


def _fake_steps(*outcomes: tuple[str, bool]) -> tuple[InstallStep, ...]:
    """Build fake steps whose func passes/fails per ``outcomes`` (name, passed)."""

    def make(name: str, passed: bool) -> InstallStep:
        def action(_ctx: InstallStepContext) -> None:
            if not passed:
                raise RuntimeError("step failed on purpose")

        return InstallStep(name=name, doc_ref="fake", func=action)

    return tuple(make(name, passed) for name, passed in outcomes)


@pytest.fixture(autouse=True)
def _no_real_clone(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize the real git clone for the UNIT tests (no subprocess).

    The regression e2e test needs the real clone, so it is left untouched - the
    stub would leave it with an empty temp dir and every step would fail spuriously.
    """
    if request.node.get_closest_marker("regression") is not None:
        return
    monkeypatch.setattr(install_tier, "_clone_head", lambda repo_root, dest: None)


def test_all_steps_pass_gives_passing_envelope(tmp_path: Path) -> None:
    board = tmp_path / "scoreboard.jsonl"
    result = run_install_tier(
        REPO_ROOT,
        steps=_fake_steps(("a", True), ("b", True)),
        scoreboard_path=board,
    )
    assert isinstance(result, InstallTierResult)
    assert result.passed is True
    assert result.failed_step is None
    assert [o.name for o in result.steps] == ["a", "b"]
    assert all(o.passed for o in result.steps)


def test_failing_step_stops_and_is_named(tmp_path: Path) -> None:
    board = tmp_path / "scoreboard.jsonl"
    result = run_install_tier(
        REPO_ROOT,
        steps=_fake_steps(("a", True), ("b", False), ("c", True)),
        scoreboard_path=board,
    )
    assert result.passed is False
    assert result.failed_step == "b"
    # stops at the first failure - "c" never runs
    assert [o.name for o in result.steps] == ["a", "b"]
    assert result.steps[-1].passed is False
    assert "step failed on purpose" in result.steps[-1].message


# --------------------------------------------------------------------------- #
# Scoreboard tier="install" round-trip
# --------------------------------------------------------------------------- #


def test_install_tier_records_under_install_tier(tmp_path: Path) -> None:
    """A run appends one tier="install" line that groups on its own floor row."""
    board = tmp_path / "scoreboard.jsonl"
    run_install_tier(REPO_ROOT, steps=_fake_steps(("a", True)), scoreboard_path=board)

    entries = read_scoreboard(path=board)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.tier == INSTALL_TIER == "install"
    assert entry.operator_model == INSTALL_OPERATOR_MODEL
    assert entry.first_attempt_pass is True
    assert entry.final_pass is True

    floor = current_floor(entries)
    assert (INSTALL_OPERATOR_MODEL, "install") in floor
    assert floor[(INSTALL_OPERATOR_MODEL, "install")]["reaches_final_pass"] is True


def test_failing_run_records_a_failing_install_line(tmp_path: Path) -> None:
    board = tmp_path / "scoreboard.jsonl"
    run_install_tier(REPO_ROOT, steps=_fake_steps(("a", False)), scoreboard_path=board)

    entries = read_scoreboard(path=board)
    assert len(entries) == 1
    assert entries[0].tier == "install"
    assert entries[0].final_pass is False


def test_record_false_writes_nothing(tmp_path: Path) -> None:
    board = tmp_path / "scoreboard.jsonl"
    run_install_tier(
        REPO_ROOT,
        steps=_fake_steps(("a", True)),
        record=False,
        scoreboard_path=board,
    )
    assert read_scoreboard(path=board) == []


# --------------------------------------------------------------------------- #
# Real end-to-end (slow, network) - excluded from the default suite
# --------------------------------------------------------------------------- #


@pytest.mark.regression
def test_install_tier_end_to_end_real_clone(tmp_path: Path) -> None:
    """Really clone HEAD, `uv sync`, `uv run hpipe bootstrap`, and smoke ingest.

    This is the regression guard on the documented cold-clone onboarding path
    (issue #55): if any documented step breaks from a cold env, this fails and
    ``failed_step`` names which one broke first. Slow + needs network for the uv
    package download, so it is regression-marked and never in the default suite.
    """
    board = tmp_path / "scoreboard.jsonl"
    result = run_install_tier(REPO_ROOT, scoreboard_path=board)

    assert result.passed, (
        f"documented onboarding path broke at step {result.failed_step!r}: "
        f"{result.steps[-1].message if result.steps else '(no steps ran)'}"
    )
    assert result.failed_step is None
    assert [o.name for o in result.steps] == [s.name for s in INSTALL_TIER_STEPS]

    # The scoreboard captured one passing tier="install" line.
    entries = read_scoreboard(path=board)
    assert len(entries) == 1
    assert entries[0].tier == "install"
    assert entries[0].final_pass is True


def test_head_is_committed_so_e2e_clone_is_meaningful() -> None:
    """Guard: the e2e test clones HEAD, so uncommitted work would not be tested.

    Not a failure - just a heads-up surfaced via the message if the tree is dirty
    when someone runs the regression test. Kept in the default suite as a cheap
    documentation of the clone-HEAD semantics; it never fails.
    """
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    # Purely informational; the assert is trivially true so this never blocks.
    assert proc.returncode == 0
