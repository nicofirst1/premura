"""Acceptance rollup (#56): score computation, registry-driven plan, install rung.

Fully deterministic and default-suite — NO live Ollama call, NO real git clone /
uv sync. Heavy operations are monkeypatched (the tier runners, the availability
probe, ``run_install_tier``); the score is pinned against hand-computed fakes.
Follows ``tests/test_sandbox_install_tier.py`` conventions (tmp_path scoreboards,
monkeypatched subprocess/clone paths).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from premura.harness import acceptance
from premura.harness.install_tier import INSTALL_TIER
from premura.harness.scoreboard import (
    ScoreboardEntry,
    append_scoreboard,
    read_scoreboard,
)

# --------------------------------------------------------------------------- #
# Score computation — pinned against injected FAKE entries (no runner touched).
# --------------------------------------------------------------------------- #


def _entry(model: str, tier: str, *, final_pass: bool) -> ScoreboardEntry:
    return ScoreboardEntry(
        ts="20260714T000000Z",
        operator_model=model,
        driver_model="drv",
        attempts_used=1,
        first_attempt_pass=final_pass,
        final_pass=final_pass,
        tier=tier,
    )


def test_score_is_overall_final_pass_rate() -> None:
    """5 runs, 3 passing across a mix of tiers/models -> 0.6 (hand-computed)."""
    entries = [
        _entry("m1", "one_shot", final_pass=True),
        _entry("m1", "one_shot", final_pass=False),
        _entry("m1", "tool_loop", final_pass=True),
        _entry("m2", "analyze_answer", final_pass=True),
        _entry("deterministic", INSTALL_TIER, final_pass=False),
    ]
    assert acceptance.acceptance_score(entries) == pytest.approx(0.6)


def test_score_empty_scoreboard_is_zero() -> None:
    assert acceptance.acceptance_score([]) == 0.0


def test_score_all_pass_is_one() -> None:
    entries = [
        _entry("m1", "one_shot", final_pass=True),
        _entry("m1", "install", final_pass=True),
    ]
    assert acceptance.acceptance_score(entries) == pytest.approx(1.0)


def test_score_reads_a_written_scoreboard(tmp_path: Path) -> None:
    """The score also matches when computed off a real scoreboard.jsonl round-trip."""
    board = tmp_path / "scoreboard.jsonl"
    append_scoreboard(_entry("m1", "one_shot", final_pass=True), path=board)
    append_scoreboard(_entry("m1", "one_shot", final_pass=False), path=board)
    assert acceptance.acceptance_score(read_scoreboard(path=board)) == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# Enumeration reads the registries, not hardcoded lists.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _FakeScenario:
    name: str


def _plan_tiers(plan: list[acceptance.PlannedRun], tier: str) -> list[acceptance.PlannedRun]:
    return [run for run in plan if run.tier == tier]


def test_plan_scales_with_the_scenario_registry() -> None:
    """Shrinking/growing the fake scenario list changes the planned run count."""
    models = ["m1"]
    kinds = ["level_shift"]

    one_scenario = acceptance._plan_ladder([_FakeScenario("a")], models, kinds, n=1)
    two_scenarios = acceptance._plan_ladder(
        [_FakeScenario("a"), _FakeScenario("b")], models, kinds, n=1
    )

    # one_shot + tool_loop each get one run per (scenario, model): +2 per new scenario.
    assert len(_plan_tiers(one_scenario, "one_shot")) == 1
    assert len(_plan_tiers(two_scenarios, "one_shot")) == 2
    assert len(_plan_tiers(two_scenarios, "tool_loop")) == 2
    # analyze_answer does not iterate scenarios, so its count is unchanged.
    assert len(_plan_tiers(one_scenario, "analyze_answer")) == 1
    assert len(_plan_tiers(two_scenarios, "analyze_answer")) == 1


def test_plan_scales_with_models_and_question_kinds() -> None:
    scenarios = [_FakeScenario("a")]
    two_models = ["m1", "m2"]

    plan = acceptance._plan_ladder(scenarios, two_models, ["k1", "k2"], n=1)
    # one_shot: scenarios(1) * models(2) = 2
    assert len(_plan_tiers(plan, "one_shot")) == 2
    # analyze_answer: kinds(2) * models(2) = 4
    assert len(_plan_tiers(plan, "analyze_answer")) == 4


def test_plan_n_reps_multiply_model_tiers_but_not_install() -> None:
    scenarios = [_FakeScenario("a")]
    plan = acceptance._plan_ladder(scenarios, ["m1"], ["k1"], n=3)
    assert len(_plan_tiers(plan, "one_shot")) == 3
    assert len(_plan_tiers(plan, "analyze_answer")) == 3
    # install is exactly one rung regardless of n (deterministic; no repeat noise).
    assert len(_plan_tiers(plan, INSTALL_TIER)) == 1


def test_resolve_models_reads_ollama_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Models come from OLLAMA_MODEL (comma-separated), falling back to DEFAULT_MODEL."""
    monkeypatch.setenv("OLLAMA_MODEL", " a , b ,, c ")
    assert acceptance.resolve_models() == ["a", "b", "c"]

    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    assert acceptance.resolve_models() == [acceptance.DEFAULT_MODEL]


def test_run_acceptance_plan_reflects_faked_registries(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rollup's executed plan tracks the (faked) registries, not a hardcoded set."""
    monkeypatch.setattr(
        acceptance.scenario_registry,
        "all_scenarios",
        lambda: [_FakeScenario("solo")],
    )
    monkeypatch.setattr(acceptance.answer_task, "list_question_kinds", lambda: ["k1"])
    monkeypatch.setattr(acceptance, "resolve_models", lambda: ["m1"])
    # No live model, so model-backed tiers are skipped -> only install would run;
    # but we also stub install so nothing heavy runs, and capture the plan.
    monkeypatch.setattr(acceptance, "ollama_available", lambda: True)

    captured: list[acceptance.PlannedRun] = []

    def _capture(run: acceptance.PlannedRun) -> None:
        captured.append(run)

    monkeypatch.setattr(
        acceptance,
        "TIER_RUNNERS",
        {tier: _capture for tier in acceptance.TIER_RUNNERS},
    )
    board = tmp_board(monkeypatch)
    monkeypatch.setattr(acceptance, "SCOREBOARD_PATH", board)

    acceptance.run_acceptance(n=1)

    tiers = {run.tier for run in captured}
    assert tiers == {"one_shot", "tool_loop", "analyze_answer", INSTALL_TIER}
    # one scenario * one model per live-trial tier; one kind * one model for answer.
    assert len([r for r in captured if r.tier == "one_shot"]) == 1
    assert len([r for r in captured if r.tier == INSTALL_TIER]) == 1


def tmp_board(monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp scoreboard path (avoids touching the real data/ board in the offline test)."""
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="premura-acceptance-test-"))
    return tmp / "scoreboard.jsonl"


# --------------------------------------------------------------------------- #
# Install rung reaches the real code path (deterministically; no real clone).
# --------------------------------------------------------------------------- #


def test_install_rung_appends_exactly_one_install_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The install runner calls run_install_tier with a real scoreboard path.

    We monkeypatch ``run_install_tier`` to append a fake install line (no real
    clone) and pin that running the install rung produces exactly one tier=
    ``install`` scoreboard line — i.e. the rollup does not skip or no-op install.
    """
    board = tmp_path / "scoreboard.jsonl"
    calls: list[Path] = []

    def _fake_install(repo_root: Path, *, scoreboard_path: Path, **_kw: object) -> None:
        calls.append(scoreboard_path)
        line = _entry("deterministic", INSTALL_TIER, final_pass=True)
        append_scoreboard(line, path=scoreboard_path)

    monkeypatch.setattr(acceptance, "run_install_tier", _fake_install)
    # Point the runner's real-scoreboard constant at the tmp board.
    monkeypatch.setattr(acceptance, "SCOREBOARD_PATH", board)

    acceptance._run_install(acceptance.PlannedRun(tier=INSTALL_TIER))

    assert calls == [board]  # called with a real scoreboard path, not skipped
    entries = read_scoreboard(path=board)
    assert len(entries) == 1
    assert entries[0].tier == INSTALL_TIER


def test_offline_run_skips_model_tiers_but_runs_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ollama unavailable -> model tiers skipped, install still executed + reported."""
    board = tmp_path / "scoreboard.jsonl"
    monkeypatch.setattr(acceptance, "ollama_available", lambda: False)
    monkeypatch.setattr(acceptance.scenario_registry, "all_scenarios", lambda: [_FakeScenario("a")])
    monkeypatch.setattr(acceptance.answer_task, "list_question_kinds", lambda: ["k1"])
    monkeypatch.setattr(acceptance, "resolve_models", lambda: ["m1"])

    ran: list[str] = []

    def _fake_install(run: acceptance.PlannedRun) -> None:
        ran.append(run.tier)
        append_scoreboard(_entry("deterministic", INSTALL_TIER, final_pass=True), path=board)

    def _should_not_run(run: acceptance.PlannedRun) -> None:  # pragma: no cover
        raise AssertionError(f"model-backed tier {run.tier!r} ran while offline")

    monkeypatch.setattr(
        acceptance,
        "TIER_RUNNERS",
        {
            "one_shot": _should_not_run,
            "tool_loop": _should_not_run,
            "analyze_answer": _should_not_run,
            INSTALL_TIER: _fake_install,
        },
    )

    monkeypatch.setattr(acceptance, "SCOREBOARD_PATH", board)
    report = acceptance.run_acceptance(n=1)

    assert ran == [INSTALL_TIER]
    assert "Ollama unavailable" in report
    assert "acceptance score" in report
    # The one install line lands and the score reflects it (1 run, 1 pass -> 1.0).
    assert "1.000" in report
