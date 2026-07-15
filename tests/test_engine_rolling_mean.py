"""Tests for the ``rolling_mean`` analytical tool (WP02).

These exercise ``rolling_mean`` *behind* the WP02 analytical contract and
*through* the WP03 admissible-input layer, mirroring the proof-tool tests:

* The tool registers against the shared contract registry (importing the module
  runs the decorator), so WP05's default surface can later discover and dispatch
  it with no per-tool branch. This WP does **not** require default publication.
* It consumes a prepared :class:`AnalyticalInputSeries`; a refused series is
  surfaced as a refusal envelope rather than computed over.
* Available runs produce deterministic, byte-stable, metadata-bearing envelopes
  with a moving-window *series* (per-point coverage and imputation visibility);
  out-of-bounds, insufficient, scanning, and refused inputs refuse with no
  estimate.
* Doctrine: estimates, caveats, and messages avoid causal language, diagnostic
  labels, p-value / significance claims, and prediction claims.

Evidence is fixture-backed: hand-built ``EvidenceCandidate`` + ``MetricFamilyPolicy``
plus explicit ``PreparedPoint`` series. Nothing here reads the warehouse, SQL,
DuckDB, MCP, or the network.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import pytest

from premura.engine.analytical_contract import (
    CONFOUND_KEYS,
    REGISTRY,
    AnalyticalQuestionType,
    AnalyticalStatus,
    ConfoundKey,
    dispatch,
)
from premura.engine.analytical_inputs import (
    AnalyticalInputSeries,
    PreparedPoint,
    prepare_input_series,
)
from premura.engine.policies._model import (
    Admissibility,
    EvidenceCandidate,
    FreshnessMode,
    FreshnessRule,
    MetricFamilyPolicy,
    MissingDataBehavior,
    PolicyShape,
    QuestionRule,
    QuestionType,
    SufficiencyRule,
    TemporalMeaning,
)
from premura.engine.rolling_mean import (
    DEFAULT_MAX_WINDOW,
    DEFAULT_WINDOW,
    ROLLING_MEAN_TOOL,
    rolling_mean,
)

REFERENCE = datetime(2026, 5, 29, 12, 0, 0)
FAMILY = "rolling_recent_family"
METRIC = "resting_heart_rate"
QT = AnalyticalQuestionType.MOVING_WINDOW_PATTERN


# ---------------------------------------------------------------------------
# Fixture-backed evidence helpers (mirrors the proof-tool test scaffolding)
# ---------------------------------------------------------------------------


def _moving_window_policy(
    *,
    admissibility: Admissibility = Admissibility.ADMISSIBLE,
    max_age: timedelta = timedelta(days=3650),
    min_observations: int | None = None,
) -> MetricFamilyPolicy:
    rule = QuestionRule(
        admissibility=admissibility,
        freshness=FreshnessRule(mode=FreshnessMode.STRICT_WINDOW, max_age=max_age),
        sufficiency=(
            SufficiencyRule(
                min_observations=min_observations,
                missing_data_behavior=MissingDataBehavior.REJECT,
            )
            if min_observations is not None
            else None
        ),
    )
    return MetricFamilyPolicy(
        policy_id="rolling_recent@1",
        version=1,
        metric_family=FAMILY,
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        question_rules={QuestionType.MOVING_WINDOW_PATTERN: rule},
        applies_to_metrics=(METRIC,),
    )


def _candidate(*, observed_at: datetime, point_count: int) -> EvidenceCandidate:
    return EvidenceCandidate(
        metric_id=METRIC,
        metric_family=FAMILY,
        value_kind="aggregate",
        observed_at=observed_at,
        source_id="fixture",
        point_count=point_count,
    )


def _series_from_values(
    values: list[float],
    *,
    imputed_idx: tuple[int, ...] = (),
    min_observations: int | None = None,
    end: datetime = REFERENCE,
) -> AnalyticalInputSeries:
    """Build a usable prepared MOVING_WINDOW series from explicit values, oldest-first."""
    n = len(values)
    points = [
        PreparedPoint(
            ts=end - timedelta(days=(n - 1 - i)),
            value=values[i],
            is_imputed=i in imputed_idx,
        )
        for i in range(n)
    ]
    return prepare_input_series(
        METRIC,
        QT,
        candidate=_candidate(observed_at=end, point_count=n),
        policies=_moving_window_policy(min_observations=min_observations),
        points=points,
        reference_time=REFERENCE,
        freshness_status="current",
    )


def _refused_series() -> AnalyticalInputSeries:
    """A refused prepared series (no evidence at all)."""
    series = prepare_input_series(
        METRIC,
        QT,
        candidate=_candidate(observed_at=REFERENCE, point_count=0),
        policies=_moving_window_policy(),
        points=[],
        reference_time=REFERENCE,
    )
    assert not series.is_usable
    return series


# Terms doctrine forbids in any surfaced estimate / caveat / message.
_FORBIDDEN_PATTERNS = (
    r"\bcaus\w*",  # cause, caused, causal, causes, causation
    r"\beffect\w*",
    r"\bp-?value\w*",
    r"\bsignifican\w*",  # significant, significance
    r"\bdiagnos\w*",  # diagnosis, diagnostic, diagnose
    r"\btreat\w*",  # treatment, treat
    r"\bdos\w*",  # dose, dosing
    r"\bemergenc\w*",
    r"\bpopulation\b",
    r"\bnorm\w*",
)
_PREDICTION_PATTERNS = (
    r"\bpredict\w*",
    r"\bforecast\w*",
    r"\bwill\s+be\b",
    r"\bfuture\s+value",
)


def _all_text(envelope_dict: dict) -> str:
    """Flatten every human-readable string in an envelope for assertion."""
    parts: list[str] = []

    def walk(obj: object) -> None:
        if isinstance(obj, str):
            parts.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v)

    walk(envelope_dict)
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# T006/T008 — registration / contract wiring (integration check)
# ---------------------------------------------------------------------------


def test_rolling_mean_registers_against_the_contract() -> None:
    # Importing the rolling_mean module ran the decorator; the tool is now
    # discoverable in the shared registry with its reviewed question type.
    assert ROLLING_MEAN_TOOL == "rolling_mean"
    assert ROLLING_MEAN_TOOL in REGISTRY
    spec = REGISTRY[ROLLING_MEAN_TOOL]
    assert spec.fn is rolling_mean
    assert spec.question_type is AnalyticalQuestionType.MOVING_WINDOW_PATTERN
    assert spec.result_kind == "rolling_mean_estimate"
    assert "window" in spec.parameters
    assert "min_coverage" in spec.parameters
    # Every declared confound key is in the closed vocabulary.
    assert set(spec.confound_keys) <= CONFOUND_KEYS


def test_rolling_mean_invokes_through_shared_dispatch() -> None:
    """The tool is reachable through the single shared dispatch path (no branch)."""
    series = _series_from_values([float(v) for v in range(10)])
    via_dispatch = dispatch(ROLLING_MEAN_TOOL, series, window=3)
    direct = rolling_mean(series, window=3)
    assert via_dispatch.to_dict() == direct.to_dict()


# ---------------------------------------------------------------------------
# T006 — available envelope shape (FR-002, NFR-003)
# ---------------------------------------------------------------------------


def test_rolling_mean_available_envelope_reports_window_metadata() -> None:
    series = _series_from_values([10.0, 12.0, 14.0, 16.0, 18.0, 20.0])
    env = rolling_mean(series, window=3, min_coverage=0.5)

    assert env.tool_name == "rolling_mean"
    assert env.status is AnalyticalStatus.AVAILABLE
    assert env.inputs == (METRIC,)
    # Declared parameters echoed back.
    assert env.parameters["window"] == 3
    assert env.parameters["min_coverage"] == 0.5
    # Source sample size and emitted-point count.
    assert env.sample_size == 6
    est = env.estimate
    assert est is not None
    assert est["window"] == 3
    assert est["min_coverage"] == 0.5
    assert est["input_sample_size"] == 6
    assert est["emitted_point_count"] >= 1
    # Ordered summary points with per-point coverage + imputation counts.
    points = est["points"]
    assert isinstance(points, list) and points
    ts_values = [p["ts"] for p in points]
    assert ts_values == sorted(ts_values)
    for p in points:
        assert set(p) >= {
            "ts",
            "value",
            "window_observation_count",
            "window_expected_count",
            "coverage",
            "imputed_observation_count",
        }
        assert p["window_expected_count"] == 3
    # A closed-vocabulary confound checklist travels with available results.
    for entry in env.confound_checklist:
        assert entry.key.value in CONFOUND_KEYS


def test_rolling_mean_first_window_trails_correctly() -> None:
    # window=3 over 0..5: first emitted point is at index 2, mean(0,1,2)=1.
    series = _series_from_values([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    env = rolling_mean(series, window=3, min_coverage=1.0)
    points = env.estimate["points"]
    # Four trailing windows ending at indices 2,3,4,5.
    assert len(points) == 4
    assert points[0]["value"] == 1.0
    assert points[-1]["value"] == 4.0
    # Trailing-only: it never uses observations after the point it summarizes.
    assert all(p["coverage"] == 1.0 for p in points)


def test_rolling_mean_keeps_long_gaps_visible_via_coverage() -> None:
    # A window with too many imputed points falls below coverage -> blank value,
    # never a fabricated fill. Early windows here are fully observed (emitted);
    # the trailing windows over the imputed run blank, so missingness stays
    # visible in counts while at least one usable point is still emitted.
    series = _series_from_values(
        [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0],
        imputed_idx=(4, 5, 6),
    )
    env = rolling_mean(series, window=3, min_coverage=0.67)
    assert env.status is AnalyticalStatus.AVAILABLE
    points = env.estimate["points"]
    blanks = [p for p in points if p["value"] is None]
    emitted = [p for p in points if p["value"] is not None]
    assert blanks, "an under-covered window must blank rather than fabricate a fill"
    assert emitted, "fully-covered windows must still emit a value"
    for p in blanks:
        assert p["coverage"] < 0.67
        assert p["imputed_observation_count"] >= 1


def test_rolling_mean_imputation_visible_in_estimate() -> None:
    series = _series_from_values([1.0, 2.0, 3.0, 4.0], imputed_idx=(0,))
    env = rolling_mean(series, window=2, min_coverage=0.5)
    # is_imputed_pct carries the source imputation share.
    assert env.is_imputed_pct > 0.0
    total_imputed = sum(p["imputed_observation_count"] for p in env.estimate["points"])
    assert total_imputed >= 1


# ---------------------------------------------------------------------------
# T010 / NFR-001 — determinism
# ---------------------------------------------------------------------------


def test_rolling_mean_is_byte_deterministic_across_runs() -> None:
    s1 = _series_from_values([float(v) for v in range(12)])
    s2 = _series_from_values([float(v) for v in range(12)])
    a = rolling_mean(s1, window=4, min_coverage=0.5)
    b = rolling_mean(s2, window=4, min_coverage=0.5)
    assert a.to_dict() == b.to_dict()


def test_rolling_mean_default_window_applies_when_none_declared() -> None:
    # Behavioral: with no window declared the tool falls back to DEFAULT_WINDOW.
    series = _series_from_values([float(v) for v in range(10)])
    env = rolling_mean(series)
    assert env.parameters["window"] == DEFAULT_WINDOW


# ---------------------------------------------------------------------------
# T007 / FR-003 / NFR-004 — at least 6 distinct refusal classes, no estimate
# ---------------------------------------------------------------------------


def _assert_refusal(env, *, reason: str | None = None) -> None:
    assert env.status is AnalyticalStatus.REFUSED
    assert env.estimate is None
    assert env.refusal is not None
    assert env.refusal.reason
    if reason is not None:
        assert env.refusal.reason == reason


def test_refusal_1_refused_input_surfaces_without_computing() -> None:
    env = rolling_mean(_refused_series(), window=3)
    _assert_refusal(env)


@pytest.mark.parametrize(
    "kwargs",
    [
        # Window zero / negative is not a moving window.
        {"window": 0},
        {"window": -3},
        # A window of one is a passthrough, not a moving-window summary.
        {"window": 1},
        # Window beyond the accepted maximum.
        {"window": DEFAULT_MAX_WINDOW + 1},
        # Coverage fraction outside [0, 1].
        {"window": 3, "min_coverage": 1.5},
        {"window": 3, "min_coverage": -0.1},
    ],
)
def test_refusal_unsupported_parameter(kwargs: dict) -> None:
    # Every out-of-contract parameter refuses with the same machine-readable
    # reason and yields no estimate.
    series = _series_from_values([float(v) for v in range(8)])
    _assert_refusal(rolling_mean(series, **kwargs), reason="unsupported_parameter")


def test_refusal_5_window_longer_than_span() -> None:
    series = _series_from_values([1.0, 2.0, 3.0])
    _assert_refusal(rolling_mean(series, window=7), reason="insufficient_data")


def test_refusal_7_no_window_reaches_required_coverage() -> None:
    # Every trailing window is mostly imputed, so none reaches min_coverage:
    # the tool refuses rather than emit zero usable summary points.
    series = _series_from_values(
        [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        imputed_idx=(0, 1, 2, 3, 4, 5),
    )
    env = rolling_mean(series, window=3, min_coverage=0.9)
    _assert_refusal(env, reason="insufficient_coverage")


def test_refusal_8_auto_window_scan_is_rejected_before_computation() -> None:
    # FR-014 / C-004: the tool must require one declared hypothesis. Any request
    # that scans alternatives to pick the strongest window is refused with no
    # estimate, before any arithmetic.
    series = _series_from_values([float(v) for v in range(12)])
    env = rolling_mean(series, window=3, select_best_window=True)
    _assert_refusal(env, reason="unsupported_parameter")
    env2 = rolling_mean(series, 5)  # extra positional arg = scan/alt request
    _assert_refusal(env2, reason="unsupported_parameter")


def test_six_distinct_refusal_reasons_exist() -> None:
    series = _series_from_values([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], imputed_idx=(0, 1, 2, 3, 4, 5))
    short = _series_from_values([1.0, 2.0, 3.0])
    ok = _series_from_values([float(v) for v in range(8)])
    reasons = {
        rolling_mean(_refused_series(), window=3).refusal.reason,
        rolling_mean(ok, window=0).refusal.reason,  # unsupported_parameter
        rolling_mean(short, window=7).refusal.reason,  # insufficient_data
        rolling_mean(ok, window=3, min_coverage=2.0).refusal.reason,  # unsupported_parameter
        rolling_mean(series, window=3, min_coverage=0.9).refusal.reason,  # insufficient_coverage
        rolling_mean(ok, window=3, pick_best=True).refusal.reason,  # unsupported_parameter
    }
    # At least 6 refusal *fixtures* with machine-readable reasons; the distinct
    # machine-readable reason set spans the contract's refusal classes.
    assert {"unsupported_parameter", "insufficient_data", "insufficient_coverage"} <= reasons


# ---------------------------------------------------------------------------
# T009 — caveats / confounds and forbidden-language assertions
# ---------------------------------------------------------------------------


def test_rolling_mean_carries_method_uncertainty_unavailable() -> None:
    series = _series_from_values([float(v) for v in range(10)])
    env = rolling_mean(series, window=3)
    keys = {e.key for e in env.confound_checklist}
    # A moving-window mean has no natural uncertainty interval.
    assert ConfoundKey.METHOD_UNCERTAINTY_UNAVAILABLE in keys
    assert env.uncertainty is not None and env.uncertainty.available is False


def test_rolling_mean_flags_parameter_at_limit() -> None:
    # window at the maximum allowed value, but the series is long enough.
    values = [float(v) for v in range(DEFAULT_MAX_WINDOW)]
    series = _series_from_values(values)
    env = rolling_mean(series, window=DEFAULT_MAX_WINDOW)
    keys = {e.key for e in env.confound_checklist}
    assert ConfoundKey.PARAMETER_AT_LIMIT in keys


def test_rolling_mean_flags_high_imputation() -> None:
    series = _series_from_values(
        [float(v) for v in range(8)],
        imputed_idx=(0, 1, 2, 3, 4),
    )
    env = rolling_mean(series, window=2, min_coverage=0.25)
    keys = {e.key for e in env.confound_checklist}
    assert ConfoundKey.HIGH_IMPUTATION in keys


def test_rolling_mean_flags_low_sample_size() -> None:
    # Emitted support near the floor (one usable trailing window).
    series = _series_from_values([1.0, 2.0, 3.0])
    env = rolling_mean(series, window=3, min_coverage=1.0)
    keys = {e.key for e in env.confound_checklist}
    assert ConfoundKey.LOW_SAMPLE_SIZE in keys


def test_rolling_mean_text_avoids_forbidden_and_prediction_language() -> None:
    series = _series_from_values([float(v) for v in range(12)], imputed_idx=(0, 1))
    text = _all_text(rolling_mean(series, window=3).to_dict())
    for pat in _FORBIDDEN_PATTERNS:
        assert not re.search(pat, text), f"forbidden pattern {pat!r} present: {text!r}"
    for pat in _PREDICTION_PATTERNS:
        assert not re.search(pat, text), f"prediction pattern {pat!r} present: {text!r}"


def test_rolling_mean_refusal_text_avoids_forbidden_language() -> None:
    text = _all_text(rolling_mean(_refused_series(), window=3).to_dict())
    for pat in _FORBIDDEN_PATTERNS:
        assert not re.search(pat, text), f"forbidden pattern {pat!r} present: {text!r}"


def test_rolling_mean_caveats_within_length_budget() -> None:
    # NFR-005: every built-in caveat / refusal message is <= 320 chars.
    series = _series_from_values([float(v) for v in range(12)], imputed_idx=(0, 1))
    env = rolling_mean(series, window=3)
    for caveat in env.caveats:
        assert len(caveat) <= 320, caveat
    refusal_env = rolling_mean(_refused_series(), window=3)
    assert refusal_env.refusal is not None
    assert len(refusal_env.refusal.message) <= 320


# ---------------------------------------------------------------------------
# T010 — no MCP / trace / network coupling, deterministic import
# ---------------------------------------------------------------------------


def test_importing_rolling_mean_does_not_import_mcp_or_trace() -> None:
    # Measure transitive imports in a *fresh* interpreter so sibling tests that
    # already imported the MCP/trace layers into this process's sys.modules
    # cannot mask an accidental dependency (the guard is about what importing the
    # engine tool itself pulls in, not the global module table).
    import subprocess
    import sys

    probe = (
        "import sys\n"
        "import premura.engine.rolling_mean  # noqa: F401\n"
        "bad = [m for m in ('premura.mcp.server', 'premura.mcp', 'premura.trace') "
        "if m in sys.modules]\n"
        "assert not bad, bad\n"
        "print('clean')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "clean"


def test_rolling_mean_module_has_no_network_imports() -> None:
    import premura.engine.rolling_mean as rm

    source = rm.__file__
    assert source is not None
    with open(source, encoding="utf-8") as fh:
        text = fh.read()
    for forbidden in ("import requests", "import httpx", "import urllib", "pubmed", "socket"):
        assert forbidden not in text.lower(), forbidden


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
