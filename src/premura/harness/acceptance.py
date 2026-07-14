"""Periodic acceptance rollup — a standing 0-1 score over the whole ladder (#56).

This is the reporting entry point that runs the WHOLE acceptance-scenario ladder
on demand and reports a single 0-1 acceptance score plus the per-(model, tier)
capability floor. It is the final slice of the graded-eval sequence: slices 1-5
built the individual tiers (one_shot, tool_loop, analyze_answer, install), each
of which already self-appends to the scoreboard; this slice runs them together
and rolls the scoreboard up into one standing number.

It is a REPORTING TOOL, never a CI gate. It never exits nonzero because the
acceptance score is low (a low floor is a finding to watch climb, not a build
failure). It exits nonzero only on a hard operational failure — no scoreboard
entries could be produced at all.

Run it directly::

    uv run python -m premura.harness.acceptance
    uv run python -m premura.harness.acceptance --n 3
    OLLAMA_MODEL=qwen2.5-coder:7b,llama3.1:8b uv run python -m premura.harness.acceptance

The model-backed tiers need a running local Ollama; if it is unavailable they are
skipped with a clear message and the model-agnostic install rung still runs.

The extension point: :data:`TIER_RUNNERS`
-----------------------------------------
Each tier's runner has a genuinely different call shape — one_shot / tool_loop
take ``(scenario, model)``; analyze_answer takes ``(seed, question_kind,
operator)``; install takes nothing and is model-agnostic. So the tiers cannot
share one loop body. :data:`TIER_RUNNERS` is the deliberate, documented seam
(the same "guide, don't enumerate" shape as the parser/scenario registries in
DOCTRINE): it pairs a tier name with the callable that plans+runs it, so adding a
future tier is "register one entry", not "add another ``if tier == ...`` branch".

This hand-wired dict of tier keys is the ONE allowed literal-name surface — it is
the registry itself, not enumeration over it. Everything a tier iterates INSIDE
its runner still comes from the real registries, never a literal name list:

* scenarios — :func:`premura.harness.scenario_registry.all_scenarios`
* models — the ``OLLAMA_MODEL`` env var (comma-separated), the codebase's only
  model-configuration surface (there is no models.yaml); falls back to
  ``[live_trial_ollama.DEFAULT_MODEL]`` when unset.
* question kinds — :func:`premura.harness.answer_task.list_question_kinds`
"""

from __future__ import annotations

import argparse
import os
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from premura.config import REPO_ROOT
from premura.harness import answer_task, scenario_registry
from premura.harness.adversarial_eval import ADVERSARIAL_TIER, run_adversarial_eval
from premura.harness.answer_ollama import OllamaAnswerOperator
from premura.harness.answer_trial import run_answer_trial
from premura.harness.install_tier import INSTALL_TIER, run_install_tier
from premura.harness.live_trial_ollama import (
    DEFAULT_MODEL,
    ollama_available,
    run_live_trial_ollama,
)
from premura.harness.live_trial_tool_loop import run_live_trial_tool_loop
from premura.harness.scenario import Scenario
from premura.harness.scoreboard import (
    SCOREBOARD_PATH,
    ScoreboardEntry,
    _format_floor,
    current_floor,
    read_scoreboard,
)

#: Env var carrying the N-repetitions knob (a ``--n`` CLI flag overrides it).
ACCEPTANCE_N_ENV = "PREMURA_ACCEPTANCE_N"

#: Cheap by default: this is a runnable-on-demand report, not a slow-by-default
#: suite. One rep per (scenario, tier, model) unless the caller asks for more.
DEFAULT_N = 1


def resolve_models() -> list[str]:
    """The models to grade, read from the ``OLLAMA_MODEL`` env var (contract §"models").

    Comma-separated, whitespace-trimmed; an unset/empty var falls back to the
    single-element ``[DEFAULT_MODEL]`` (the same default every tier's runner uses).
    This reads the codebase's existing model-configuration surface — there is no
    separate model registry — so it is NOT a hardcoded model list.
    """
    raw = os.environ.get("OLLAMA_MODEL", "")
    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models or [DEFAULT_MODEL]


# --------------------------------------------------------------------------- #
# Ladder plan — a pure, executes-nothing description of the run set (testable).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PlannedRun:
    """One planned rung of the ladder — WHAT would run, not the running of it.

    ``tier`` names the :data:`TIER_RUNNERS` entry. For the model-backed tiers
    ``model`` is set; ``scenario`` names a scenario (one_shot / tool_loop) or
    ``question_kind`` names a kind (analyze_answer). The install rung is
    model-agnostic and carries none of these. ``rep`` is the 1-based repetition
    index (1..n).
    """

    tier: str
    model: str | None = None
    scenario: str | None = None
    question_kind: str | None = None
    rep: int = 1


def _plan_ladder(
    scenarios: Sequence[Scenario],
    models: Sequence[str],
    question_kinds: Sequence[str],
    n: int,
) -> list[PlannedRun]:
    """Enumerate the whole ladder as :class:`PlannedRun` items — pure, runs nothing.

    Reads scenarios/models/question-kinds straight from the registries the caller
    passes in (so a test can shrink/grow a fake registry and watch the plan
    change). The plan mirrors the execution:

    * ``one_shot`` and ``tool_loop`` — one run per (scenario, model, rep);
    * ``analyze_answer`` — one run per (question_kind, model, rep) [no scenarios];
    * ``install`` — exactly ONE model-agnostic rung, regardless of ``n``, because
      it is deterministic and repeating it would be pointless noise.
    """
    plan: list[PlannedRun] = []
    for tier in ("one_shot", "tool_loop"):
        for scenario in scenarios:
            for model in models:
                for rep in range(1, n + 1):
                    plan.append(PlannedRun(tier=tier, model=model, scenario=scenario.name, rep=rep))
    for kind in question_kinds:
        for model in models:
            for rep in range(1, n + 1):
                plan.append(
                    PlannedRun(tier="analyze_answer", model=model, question_kind=kind, rep=rep)
                )
    # The adversarial-narration tier (#12) iterates its OWN prompt-category registry
    # internally, so it plans one run per (model, rep) — no scenario/kind loop here.
    for model in models:
        for rep in range(1, n + 1):
            plan.append(PlannedRun(tier=ADVERSARIAL_TIER, model=model, rep=rep))
    # The install tier is a distinct, model-agnostic rung: one run per rollup.
    plan.append(PlannedRun(tier=INSTALL_TIER))
    return plan


# --------------------------------------------------------------------------- #
# Tier runners — the extension point (see module docstring). Each runner takes
# ONE PlannedRun and executes it; every runner's underlying tier self-appends to
# the scoreboard, so a runner returns None and never appends itself.
# --------------------------------------------------------------------------- #


def _scenario_by_name(name: str) -> Scenario:
    """Resolve a planned scenario name back to its registered Scenario object."""
    for scenario in scenario_registry.all_scenarios():
        if scenario.name == name:
            return scenario
    raise KeyError(f"no registered scenario named {name!r}")


def _run_one_shot(run: PlannedRun) -> None:
    """One-shot tier for one (scenario, model): delegates to the self-appending runner."""
    assert run.scenario is not None and run.model is not None  # noqa: S101
    run_live_trial_ollama(model=run.model, scenario=_scenario_by_name(run.scenario))


def _run_tool_loop(run: PlannedRun) -> None:
    """Tool-loop tier for one (scenario, model): delegates to the self-appending runner."""
    assert run.scenario is not None and run.model is not None  # noqa: S101
    run_live_trial_tool_loop(model=run.model, scenario=_scenario_by_name(run.scenario))


def _run_analyze_answer(run: PlannedRun) -> None:
    """Analyze-answer tier for one (question_kind, model).

    Needs its own synthetic warehouse + session log; both land in a temp dir that
    is removed on exit (nothing persists under the repo). The seed is the rep
    index so repetitions vary deterministically. ``run_answer_trial`` self-appends
    to the real scoreboard.
    """
    assert run.question_kind is not None and run.model is not None  # noqa: S101
    with tempfile.TemporaryDirectory(prefix="premura-acceptance-answer-") as tmp:
        tmp_dir = Path(tmp)
        run_answer_trial(
            seed=run.rep,
            question_kind=run.question_kind,
            operator=OllamaAnswerOperator(model_id=run.model),
            warehouse_path=tmp_dir / "warehouse.duckdb",
            session_log_path=tmp_dir / "session_log.duckdb",
        )


def _run_adversarial(run: PlannedRun) -> None:
    """Adversarial-narration tier for one model (#12): delegates to the self-appending eval.

    ``run_adversarial_eval`` iterates the prompt-category registry, judges every
    narration against the DISCLOSURE_RUBRIC boundary_integrity criteria, and appends
    one ``tier=adversarial_narration`` scoreboard line itself — so, like every other
    tier runner, this returns None and never appends.
    """
    assert run.model is not None  # noqa: S101
    run_adversarial_eval(model=run.model)


def _run_install(run: PlannedRun) -> None:  # noqa: ARG001 - model-agnostic rung
    """Install tier — the ladder's model-agnostic rung (REQUIRED FIX for #56).

    This is the FIRST time ``run_install_tier`` reaches the REAL scoreboard: until
    now its only caller was its own test, against a scratch tmp_path board, so the
    ``install`` tier never appeared in ``current_floor``. Runs a real git clone +
    uv sync, so it needs network/uv but no Ollama. It self-appends one tier=
    ``install`` line to :data:`SCOREBOARD_PATH`.
    """
    run_install_tier(REPO_ROOT, scoreboard_path=SCOREBOARD_PATH)


#: The tier-runner registry — the documented extension point (module docstring).
#: A future tier is added by registering one entry here; the rollup loop stays a
#: pure ``TIER_RUNNERS[run.tier](run)`` dispatch with no per-tier branch.
TIER_RUNNERS: dict[str, Callable[[PlannedRun], None]] = {
    "one_shot": _run_one_shot,
    "tool_loop": _run_tool_loop,
    "analyze_answer": _run_analyze_answer,
    ADVERSARIAL_TIER: _run_adversarial,
    INSTALL_TIER: _run_install,
}

#: The tiers that need a live Ollama model. The install rung is deliberately NOT
#: here — it is deterministic and model-agnostic and must run even offline.
_MODEL_BACKED_TIERS = frozenset({"one_shot", "tool_loop", "analyze_answer", ADVERSARIAL_TIER})


# --------------------------------------------------------------------------- #
# Score — the single 0-1 acceptance number, defined explicitly.
# --------------------------------------------------------------------------- #


def acceptance_score(entries: Sequence[ScoreboardEntry]) -> float:
    """The standing 0-1 acceptance score: overall final-pass rate.

    DEFINITION (stated explicitly because "acceptance score" is ambiguous):
    ``sum(final_pass_runs) / sum(runs)`` across EVERY (model, tier) group in the
    scoreboard — i.e. the fraction of all recorded runs that reached a passing
    final verdict, over the whole ladder's history. This reuses the exact
    per-(model, tier) grouping ``current_floor`` already computes, then flattens
    it into one number. An empty scoreboard scores 0.0.
    """
    floor = current_floor(list(entries))
    total_runs = sum(group["runs"] for group in floor.values())
    if total_runs == 0:
        return 0.0
    total_final_pass = sum(group["final_pass_runs"] for group in floor.values())
    return total_final_pass / total_runs


# --------------------------------------------------------------------------- #
# Rollup + report.
# --------------------------------------------------------------------------- #


def _execute_plan(plan: Sequence[PlannedRun], *, skip_model_tiers: bool) -> int:
    """Execute each planned run through :data:`TIER_RUNNERS`; return runs executed.

    When ``skip_model_tiers`` is set (Ollama unavailable) the model-backed rungs
    are skipped and only the model-agnostic install rung runs. The underlying
    tiers self-append to the scoreboard; this just dispatches.
    """
    executed = 0
    for run in plan:
        if skip_model_tiers and run.tier in _MODEL_BACKED_TIERS:
            continue
        TIER_RUNNERS[run.tier](run)
        executed += 1
    return executed


def run_acceptance(*, n: int) -> str:
    """Run the whole ladder, then report over the FULL scoreboard. Returns the report.

    Enumerates the ladder from the real registries, runs each rung (skipping the
    model-backed tiers when Ollama is unavailable, but always running install),
    then reads the WHOLE scoreboard back and renders the per-(model, tier) floor
    table plus the single 0-1 acceptance score. Reporting over the full history
    (not just this invocation's fresh lines) is deliberate: the score is a
    STANDING number that climbs across runs.

    Reads and writes always share the one module-level :data:`SCOREBOARD_PATH` —
    every tier runner self-appends to it (see :data:`TIER_RUNNERS`), so there is
    no caller-supplied override to thread through. Tests that need isolation
    should monkeypatch :data:`SCOREBOARD_PATH` or use the pure scoring functions
    (:func:`acceptance_score`, :func:`current_floor`) directly.
    """
    scenarios = scenario_registry.all_scenarios()
    models = resolve_models()
    question_kinds = answer_task.list_question_kinds()
    plan = _plan_ladder(scenarios, models, question_kinds, n)

    live = ollama_available()
    lines: list[str] = []
    if not live:
        lines.append(
            "Ollama unavailable, skipping model-backed tiers (one_shot / tool_loop / "
            "analyze_answer); running the model-agnostic install rung only."
        )
    _execute_plan(plan, skip_model_tiers=not live)

    entries = read_scoreboard(path=SCOREBOARD_PATH)
    lines.append(_format_floor(current_floor(entries)))
    lines.append("")
    lines.append(f"acceptance score (overall final-pass rate): {acceptance_score(entries):.3f}")
    return "\n".join(lines)


def _main(argv: Sequence[str] | None = None) -> int:
    """CLI: run the rollup and print the report.

    Exit 0 on a normal report (even a low/zero score — this is a report, not a
    gate). Exit 1 ONLY on the hard operational failure that no scoreboard entries
    could be produced at all.
    """
    parser = argparse.ArgumentParser(
        prog="python -m premura.harness.acceptance",
        description=(
            "Run the whole acceptance-scenario ladder and report a standing 0-1 "
            "acceptance score + the per-(model, tier) floor. A reporting tool, "
            "never a CI gate."
        ),
    )
    default_n = _env_int(ACCEPTANCE_N_ENV, DEFAULT_N)
    parser.add_argument(
        "--n",
        type=int,
        default=default_n,
        help=f"repetitions per (scenario/kind, tier, model) run (default: {default_n}; "
        f"env {ACCEPTANCE_N_ENV})",
    )
    args = parser.parse_args(argv)

    report = run_acceptance(n=max(1, args.n))
    print(report)

    if not read_scoreboard():
        print("\nacceptance: no scoreboard entries could be produced at all.")
        return 1
    return 0


def _env_int(name: str, default: int) -> int:
    """Read a positive int from the environment, falling back on any bad value."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


__all__ = [
    "ACCEPTANCE_N_ENV",
    "DEFAULT_N",
    "TIER_RUNNERS",
    "PlannedRun",
    "acceptance_score",
    "resolve_models",
    "run_acceptance",
]


if __name__ == "__main__":
    raise SystemExit(_main())
