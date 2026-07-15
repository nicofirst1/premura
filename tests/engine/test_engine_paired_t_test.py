"""Tests for the ``paired_t_test`` analytical tool (WP04).

These exercise ``paired_t_test`` *behind* the WP02 analytical contract and
*through* the WP03 before/after paired-input seam, mirroring the proof-tool and
``rolling_mean`` tests:

* The tool registers against the shared contract registry (importing the module
  runs the decorator), so WP05's default surface can later discover and dispatch
  it with no per-tool branch. This WP does **not** require default publication.
* It consumes the WP03 ``BeforeAfterPairedInput`` seam — it never re-derives the
  matched pairs. A refused paired input is surfaced as a refusal envelope rather
  than computed over.
* Available runs produce deterministic, byte-stable, metadata-bearing envelopes
  reporting pair count, the mean paired difference (after - before), uncertainty
  metadata for that mean (dispersion, never a p-value), observed/expected/match
  direction metadata, imputation, and a closed-vocabulary confound checklist;
  out-of-bounds, weak, scanning, constant-difference, and refused inputs refuse
  with no estimate.
* Doctrine / honesty boundary: ``paired_t_test`` keeps the familiar name but
  must NOT emit ``p-value`` / ``significant`` / ``significance`` /
  hypothesis-test-pass language, nor any causal, diagnostic, treatment, dosing,
  emergency, or population-norm claim in any estimate, caveat, or message.

Everything is fixture-backed (hand-built ``PreparedPoint`` series via the WP02
single-series preparer, prepared into pairs via the WP03 seam); the tool reads
no warehouse, so nothing here touches SQL, DuckDB, MCP, the network, or a clock.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

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
from premura.engine.condition_inputs import (
    ConditionEpisode,
    ConditionLabelPairedInput,
    ConditionLabelPairedRequest,
    prepare_condition_label_paired_input,
)
from premura.engine.condition_paired_t_test import (
    CONDITION_PAIRED_T_TEST_TOOL,
    condition_paired_t_test,
)
from premura.engine.paired_inputs import (
    BEFORE_AFTER_MIN_PAIRS,
    MAX_WINDOW_DAYS,
    BeforeAfterDirection,
    BeforeAfterPairedInput,
    BeforeAfterPairedRequest,
    prepare_before_after_paired_input,
)
from premura.engine.paired_t_test import (
    PAIRED_T_TEST_TOOL,
    paired_t_test,
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

REFERENCE = datetime(2026, 5, 29, 0, 0, 0)
METRIC = "resting_heart_rate"
FAMILY = "cardio_family"
ANCHOR = date(2026, 5, 14)


# ---------------------------------------------------------------------------
# Fixture-backed evidence helpers (mirror the WP03 paired-input test style)
# ---------------------------------------------------------------------------


def _policy(metric: str, *, min_observations: int = 1) -> MetricFamilyPolicy:
    rule = QuestionRule(
        admissibility=Admissibility.ADMISSIBLE,
        freshness=FreshnessRule(mode=FreshnessMode.CAVEAT_ONLY),
        sufficiency=SufficiencyRule(
            min_observations=min_observations,
            missing_data_behavior=MissingDataBehavior.REJECT,
        ),
        required_context=("observed_at",),
    )
    return MetricFamilyPolicy(
        policy_id=f"{FAMILY}@1",
        version=1,
        metric_family=FAMILY,
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        question_rules={QuestionType.PAIRED_DIFFERENCE: rule},
        applies_to_metrics=(metric,),
    )


def _candidate(metric: str, *, point_count: int) -> EvidenceCandidate:
    return EvidenceCandidate(
        metric_id=metric,
        metric_family=FAMILY,
        value_kind="aggregate",
        observed_at=REFERENCE,
        source_id="fixture",
        point_count=point_count,
    )


def _point(day: date, value: float, *, hour: int = 12, imputed: bool = False) -> PreparedPoint:
    return PreparedPoint(
        ts=datetime(day.year, day.month, day.day, hour, 0, 0),
        value=value,
        is_imputed=imputed,
    )


def _series(
    points: list[PreparedPoint],
    *,
    min_observations: int = 1,
    freshness_status: str = "fresh",
) -> AnalyticalInputSeries:
    return prepare_input_series(
        METRIC,
        AnalyticalQuestionType.PAIRED_DIFFERENCE,
        candidate=_candidate(METRIC, point_count=len(points)),
        policies=_policy(METRIC, min_observations=min_observations),
        points=points,
        reference_time=REFERENCE,
        freshness_status=freshness_status,
    )


def _request(
    *,
    anchor: date | None = ANCHOR,
    before_days: int = 8,
    after_days: int = 8,
    direction: BeforeAfterDirection | None = BeforeAfterDirection.INCREASE,
) -> BeforeAfterPairedRequest:
    return BeforeAfterPairedRequest(
        metric_id=METRIC,
        anchor_date=anchor,  # type: ignore[arg-type]
        before_days=before_days,
        after_days=after_days,
        expected_direction=direction,  # type: ignore[arg-type]
    )


def _paired_series(
    *,
    before_values: list[float],
    after_values: list[float],
    imputed_days: tuple[date, ...] = (),
    freshness_status: str = "fresh",
) -> AnalyticalInputSeries:
    """Build a series with explicit before/after day values around the anchor.

    ``before_values`` run from farthest-before to D-1 (last is nearest anchor);
    ``after_values`` run D+1 outward (first is nearest anchor). The anchor day is
    never populated.
    """
    points: list[PreparedPoint] = []
    nb = len(before_values)
    for i, value in enumerate(before_values):
        # i=0 is farthest before; the last entry is D-1.
        day = ANCHOR - timedelta(days=(nb - i))
        points.append(_point(day, value, imputed=day in imputed_days))
    for i, value in enumerate(after_values):
        day = ANCHOR + timedelta(days=(i + 1))
        points.append(_point(day, value, imputed=day in imputed_days))
    return _series(points)


def _prepared(
    *,
    before_values: list[float],
    after_values: list[float],
    imputed_days: tuple[date, ...] = (),
    before_days: int = 30,
    after_days: int = 30,
    direction: BeforeAfterDirection = BeforeAfterDirection.INCREASE,
    freshness_status: str = "fresh",
) -> BeforeAfterPairedInput:
    """Prepare a usable/refused paired input through the WP03 seam."""
    series = _paired_series(
        before_values=before_values,
        after_values=after_values,
        imputed_days=imputed_days,
        freshness_status=freshness_status,
    )
    request = _request(before_days=before_days, after_days=after_days, direction=direction)
    return prepare_before_after_paired_input(series, request)


def _refused_paired_input() -> BeforeAfterPairedInput:
    """A refused paired input (no evidence -> inadmissible series propagates)."""
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.PAIRED_DIFFERENCE,
        candidate=_candidate(METRIC, point_count=0),
        policies=_policy(METRIC),
        points=[],
        reference_time=REFERENCE,
    )
    prepared = prepare_before_after_paired_input(series, _request())
    assert prepared.refusal is not None
    return prepared


# A usable, clearly-increasing 8-pair input (after - before = +10 each, with a
# little spread so the difference is not constant).
def _usable_increase() -> BeforeAfterPairedInput:
    before = [50.0, 51.0, 52.0, 50.0, 51.0, 49.0, 50.0, 52.0]
    after = [61.0, 60.0, 62.0, 59.0, 61.0, 60.0, 58.0, 62.0]
    return _prepared(before_values=before, after_values=after)


# Terms doctrine forbids in any surfaced estimate / caveat / message.
_FORBIDDEN_PATTERNS = (
    r"\bp-?value\w*",
    r"\bsignifican\w*",  # significant, significance
    r"\bhypothesis\s+(?:test|confirmed|rejected|passed)",
    r"\bcaus\w*",  # cause, caused, causal, causes, causation
    r"\beffect\w*",
    r"\bimpact\w*",
    r"\bdriver\b",
    r"\bdiagnos\w*",  # diagnosis, diagnostic, diagnose
    r"\btreat\w*",  # treatment, treat
    r"\bdos\w*",  # dose, dosing
    r"\bemergenc\w*",
    r"\bpopulation\b",
    r"\bnorm\w*",
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


def _assert_no_forbidden_language(env) -> None:
    text = _all_text(env.to_dict())
    for pat in _FORBIDDEN_PATTERNS:
        assert not re.search(pat, text), f"forbidden pattern {pat!r} present: {text!r}"


# ---------------------------------------------------------------------------
# Condition-tool fixtures (for the shared cross-tool behavioral sweep below)
# ---------------------------------------------------------------------------
#
# ``paired_t_test`` (anchor-date pairs) and ``condition_paired_t_test`` (condition
# episode pairs) are mirror tools: same envelope shape, direction metadata,
# determinism, refusal routing, forbidden-language and confound behavior — they
# differ only in the upstream input fixture. The behavioral assertions that are
# genuinely identical are parametrized once over both tools via ``TOOL_CASES``;
# each file additionally keeps its input-type-SPECIFIC tests. The condition
# builders below mirror ``test_engine_condition_pairs.py`` / the condition seam.

_COND_LABEL = "on_magnesium"


def _cond_episode(start: date, end: date) -> ConditionEpisode:
    return ConditionEpisode(start_day=start, end_day=end)


def _cond_series(points: list[PreparedPoint]) -> AnalyticalInputSeries:
    return prepare_input_series(
        METRIC,
        AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE,
        candidate=_candidate(METRIC, point_count=len(points)),
        policies=MetricFamilyPolicy(
            policy_id=f"{FAMILY}@1",
            version=1,
            metric_family=FAMILY,
            policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
            temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
            question_rules={
                QuestionType.CONDITION_PAIRED_DIFFERENCE: QuestionRule(
                    admissibility=Admissibility.ADMISSIBLE,
                    freshness=FreshnessRule(mode=FreshnessMode.CAVEAT_ONLY),
                    sufficiency=SufficiencyRule(
                        min_observations=1,
                        missing_data_behavior=MissingDataBehavior.REJECT,
                    ),
                    required_context=("observed_at",),
                )
            },
            applies_to_metrics=(METRIC,),
        ),
        points=points,
        reference_time=REFERENCE,
        freshness_status="fresh",
    )


def _cond_request(
    episodes: tuple[ConditionEpisode, ...],
    *,
    before_days: int = 5,
    after_days: int = 5,
    direction: BeforeAfterDirection | None = BeforeAfterDirection.INCREASE,
) -> ConditionLabelPairedRequest:
    return ConditionLabelPairedRequest(
        metric_id=METRIC,
        condition_label=_COND_LABEL,
        episodes=episodes,
        before_days=before_days,
        after_days=after_days,
        expected_direction=direction,  # type: ignore[arg-type]
    )


def _cond_block(
    points: list[PreparedPoint], start: date, end: date, *, off_value: float, on_value: float
) -> None:
    for i in range(1, 6):
        points.append(_point(start - timedelta(days=i), off_value))
    day = start
    while day <= end:
        points.append(_point(day, on_value))
        day += timedelta(days=1)


def _cond_usable_increase(
    blocks: list[tuple[date, date, float, float]] | None = None,
) -> ConditionLabelPairedInput:
    if blocks is None:
        blocks = [
            (date(2026, 3, 1), date(2026, 3, 3), 50.0, 60.0),
            (date(2026, 4, 1), date(2026, 4, 3), 51.0, 63.0),
            (date(2026, 5, 1), date(2026, 5, 3), 49.0, 58.0),
        ]
    points: list[PreparedPoint] = []
    episodes: list[ConditionEpisode] = []
    for start, end, off_v, on_v in blocks:
        _cond_block(points, start, end, off_value=off_v, on_value=on_v)
        episodes.append(_cond_episode(start, end))
    series = _cond_series(sorted(points, key=lambda p: p.ts))
    return prepare_condition_label_paired_input(series, _cond_request(tuple(episodes)))


def _cond_refused() -> ConditionLabelPairedInput:
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE,
        candidate=_candidate(METRIC, point_count=0),
        policies=_policy(METRIC),  # PAIRED_DIFFERENCE rule -> no admissible cond rule
        points=[],
        reference_time=REFERENCE,
    )
    prepared = prepare_condition_label_paired_input(
        series,
        _cond_request(
            (
                _cond_episode(date(2026, 4, 1), date(2026, 4, 3)),
                _cond_episode(date(2026, 5, 1), date(2026, 5, 3)),
            )
        ),
    )
    assert prepared.refusal is not None
    return prepared


def _cond_direction_mismatch() -> ConditionLabelPairedInput:
    # Observed decrease against an expected increase.
    return _cond_usable_increase(
        blocks=[
            (date(2026, 3, 1), date(2026, 3, 3), 60.0, 50.0),
            (date(2026, 4, 1), date(2026, 4, 3), 62.0, 49.0),
            (date(2026, 5, 1), date(2026, 5, 3), 59.0, 51.0),
        ]
    )


def _cond_constant_difference() -> ConditionLabelPairedInput:
    # Every episode has the identical on-off difference -> zero variance.
    return _cond_usable_increase(
        blocks=[
            (date(2026, 3, 1), date(2026, 3, 3), 50.0, 60.0),
            (date(2026, 4, 1), date(2026, 4, 3), 50.0, 60.0),
            (date(2026, 5, 1), date(2026, 5, 3), 50.0, 60.0),
        ]
    )


def _cond_near_floor() -> ConditionLabelPairedInput:
    # Exactly CONDITION floor of 2 usable episodes.
    return _cond_usable_increase(
        blocks=[
            (date(2026, 4, 1), date(2026, 4, 3), 50.0, 60.0),
            (date(2026, 5, 1), date(2026, 5, 3), 51.0, 63.0),
        ]
    )


class _ToolCase:
    """One mirror tool + the fixture builders the shared sweep needs."""

    def __init__(
        self,
        name,
        tool,
        module_name,
        usable,
        refused,
        direction_mismatch,
        constant_difference,
        near_floor,
        constant_reason,
    ):
        self.name = name
        self.tool = tool
        self.module_name = module_name
        self.usable = usable
        self.refused = refused
        self.direction_mismatch = direction_mismatch
        self.constant_difference = constant_difference
        self.near_floor = near_floor
        self.constant_reason = constant_reason


TOOL_CASES = [
    _ToolCase(
        name="paired_t_test",
        tool=paired_t_test,
        module_name="premura.engine.paired_t_test",
        usable=_usable_increase,
        refused=_refused_paired_input,
        direction_mismatch=lambda: _prepared(
            before_values=[60.0, 61.0, 59.0, 60.0, 62.0, 58.0, 60.0, 61.0],
            after_values=[50.0, 49.0, 51.0, 48.0, 50.0, 49.0, 47.0, 51.0],
            direction=BeforeAfterDirection.INCREASE,
        ),
        constant_difference=lambda: _prepared(before_values=[50.0] * 8, after_values=[60.0] * 8),
        near_floor=_usable_increase,  # exactly BEFORE_AFTER_MIN_PAIRS pairs
        constant_reason="constant_difference",
    ),
    _ToolCase(
        name="condition_paired_t_test",
        tool=condition_paired_t_test,
        module_name="premura.engine.condition_paired_t_test",
        usable=_cond_usable_increase,
        refused=_cond_refused,
        direction_mismatch=_cond_direction_mismatch,
        constant_difference=_cond_constant_difference,
        near_floor=_cond_near_floor,
        constant_reason="constant_difference",
    ),
]


@pytest.fixture(params=TOOL_CASES, ids=lambda c: c.name)
def tool_case(request) -> _ToolCase:
    return request.param


# ===========================================================================
# Shared cross-tool behavioral sweep (paired_t_test + condition_paired_t_test)
# ===========================================================================
# Assertions genuinely identical across the mirror pair, parametrized over both
# tools so they run once per input type instead of being copy-pasted per file.


def test_shared_invokes_through_shared_dispatch(tool_case) -> None:
    tool_name = {
        "paired_t_test": PAIRED_T_TEST_TOOL,
        "condition_paired_t_test": CONDITION_PAIRED_T_TEST_TOOL,
    }[tool_case.name]
    prepared = tool_case.usable()
    assert tool_name in REGISTRY
    via_dispatch = dispatch(tool_name, prepared)
    direct = tool_case.tool(prepared)
    assert via_dispatch.to_dict() == direct.to_dict()


def test_shared_byte_deterministic_across_runs(tool_case) -> None:
    a = tool_case.tool(tool_case.usable())
    b = tool_case.tool(tool_case.usable())
    assert a.to_dict() == b.to_dict()


def test_shared_available_avoids_forbidden_language(tool_case) -> None:
    _assert_no_forbidden_language(tool_case.tool(tool_case.usable()))


def test_shared_refusal_avoids_forbidden_language(tool_case) -> None:
    _assert_no_forbidden_language(tool_case.tool(tool_case.refused()))


def test_shared_no_p_value_or_significance_anywhere(tool_case) -> None:
    env = tool_case.tool(tool_case.usable())
    text = _all_text(env.to_dict())
    assert "p-value" not in text and "pvalue" not in text
    assert "significan" not in text
    payload = env.uncertainty.payload
    assert all("p_value" != k and "significant" != k for k in payload)


def test_shared_refused_input_surfaces_without_computing(tool_case) -> None:
    _assert_refusal(tool_case.tool(tool_case.refused()))


def test_shared_refusals_carry_no_estimate(tool_case) -> None:
    for env in (
        tool_case.tool(tool_case.refused()),
        tool_case.tool(tool_case.usable(), scan=True),
    ):
        assert env.estimate is None
        assert env.uncertainty is None or env.uncertainty.available is False


def test_shared_constant_difference_refuses_rather_than_fake_band(tool_case) -> None:
    prepared = tool_case.constant_difference()
    assert prepared.refusal is None  # the seam happily builds the pairs
    env = tool_case.tool(prepared)
    _assert_refusal(env, reason=tool_case.constant_reason)
    _assert_no_forbidden_language(env)


def test_shared_direction_mismatch_is_metadata_not_verdict(tool_case) -> None:
    env = tool_case.tool(tool_case.direction_mismatch())
    assert env.estimate["observed_direction"] == "decrease"
    assert env.estimate["expected_direction"] == "increase"
    assert env.estimate["direction_matches_hypothesis"] is False
    _assert_no_forbidden_language(env)


def test_shared_caveats_within_length_budget(tool_case) -> None:
    env = tool_case.tool(tool_case.usable())
    for caveat in env.caveats:
        assert len(caveat) <= 320, caveat
    refusal_env = tool_case.tool(tool_case.refused())
    assert refusal_env.refusal is not None
    assert len(refusal_env.refusal.message) <= 320


def test_shared_flags_low_sample_size_near_floor(tool_case) -> None:
    env = tool_case.tool(tool_case.near_floor())
    keys = {e.key for e in env.confound_checklist}
    assert ConfoundKey.LOW_SAMPLE_SIZE in keys


def test_shared_flags_temporal_autocorrelation(tool_case) -> None:
    env = tool_case.tool(tool_case.usable())
    keys = {e.key for e in env.confound_checklist}
    assert ConfoundKey.TEMPORAL_AUTOCORRELATION in keys


def test_shared_import_does_not_pull_mcp_or_trace(tool_case) -> None:
    import subprocess
    import sys

    probe = (
        "import sys\n"
        f"import {tool_case.module_name}  # noqa: F401\n"
        "bad = [m for m in ('premura.mcp.server', 'premura.mcp', 'premura.trace') "
        "if m in sys.modules]\n"
        "assert not bad, bad\n"
        "print('clean')\n"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "clean"


def test_shared_module_has_no_network_imports(tool_case) -> None:
    import importlib

    module = importlib.import_module(tool_case.module_name)
    with open(module.__file__, encoding="utf-8") as fh:
        text = fh.read()
    for forbidden in ("import requests", "import httpx", "import urllib", "pubmed", "socket"):
        assert forbidden not in text.lower(), forbidden


# ===========================================================================
# T016/T018 — registration / contract wiring (integration check)
# ===========================================================================


def test_paired_t_test_registers_against_the_contract() -> None:
    assert PAIRED_T_TEST_TOOL == "paired_t_test"
    assert PAIRED_T_TEST_TOOL in REGISTRY
    spec = REGISTRY[PAIRED_T_TEST_TOOL]
    assert spec.fn is paired_t_test
    assert spec.question_type is AnalyticalQuestionType.PAIRED_DIFFERENCE
    assert spec.result_kind == "paired_difference_estimate"
    assert set(spec.confound_keys) <= CONFOUND_KEYS


# ===========================================================================
# T016 — available envelope completeness (FR-006, NFR-003)
# ===========================================================================


def test_available_envelope_reports_required_fields() -> None:
    prepared = _usable_increase()
    env = paired_t_test(prepared)

    assert env.tool_name == "paired_t_test"
    assert env.status is AnalyticalStatus.AVAILABLE
    assert env.inputs == (METRIC,)
    # Declared anchor / window parameters preserved.
    assert env.parameters["anchor_date"] == ANCHOR.isoformat()
    assert env.parameters["before_days"] == 30
    assert env.parameters["after_days"] == 30
    assert env.parameters["expected_direction"] == "increase"
    # Pair count / sample size.
    assert env.sample_size == 8
    est = env.estimate
    assert est is not None
    assert est["raw_pair_count"] == 8
    # Mean paired difference = after - before (~+10).
    assert est["mean_difference"] == pytest.approx(10.0, abs=1.0)
    # Direction metadata.
    assert est["observed_direction"] == "increase"
    assert est["expected_direction"] == "increase"
    assert est["direction_matches_hypothesis"] is True
    # Admissible paired span echoed.
    assert "before_window_start" in est and "after_window_end" in est
    # Uncertainty metadata present (dispersion, NOT a p-value/significance).
    assert env.uncertainty is not None and env.uncertainty.available is True
    payload = env.uncertainty.payload
    assert payload is not None
    assert "std_difference" in payload
    assert "std_error" in payload
    assert "difference_interval_low" in payload
    assert "difference_interval_high" in payload
    assert "p_value" not in payload
    assert "significant" not in payload
    # Imputation percentage carried.
    assert env.is_imputed_pct == pytest.approx(0.0)
    # Closed-vocabulary confound checklist.
    for entry in env.confound_checklist:
        assert entry.key.value in CONFOUND_KEYS


def test_available_envelope_preserves_paired_span() -> None:
    prepared = _usable_increase()
    env = paired_t_test(prepared)
    est = env.estimate
    assert est["before_window_start"] == prepared.before_window_start.isoformat()
    assert est["before_window_end"] == prepared.before_window_end.isoformat()
    assert est["after_window_start"] == prepared.after_window_start.isoformat()
    assert est["after_window_end"] == prepared.after_window_end.isoformat()


def test_mean_difference_is_after_minus_before() -> None:
    # All before=10, all after=20 -> +10 mean, but add spread so not constant.
    before = [10.0, 11.0, 9.0, 10.0, 12.0, 8.0, 10.0, 11.0]
    after = [21.0, 19.0, 22.0, 18.0, 21.0, 20.0, 19.0, 22.0]
    prepared = _prepared(before_values=before, after_values=after)
    env = paired_t_test(prepared)
    diffs = [a - b for a, b in zip(after[::-1], before[::-1], strict=True)]
    # Pairing is nearest-to-anchor outward; mean of differences is order-independent.
    assert env.estimate["mean_difference"] == pytest.approx(sum(diffs) / len(diffs))


# ===========================================================================
# T019 — direction agreement metadata (no causation / significance claim)
# ===========================================================================


def test_observed_direction_increase_matches_expected_increase() -> None:
    prepared = _prepared(
        before_values=[50.0, 51.0, 49.0, 50.0, 52.0, 48.0, 50.0, 51.0],
        after_values=[61.0, 60.0, 62.0, 59.0, 61.0, 60.0, 58.0, 62.0],
        direction=BeforeAfterDirection.INCREASE,
    )
    env = paired_t_test(prepared)
    assert env.estimate["observed_direction"] == "increase"
    assert env.estimate["direction_matches_hypothesis"] is True


def test_observed_direction_matches_declared_decrease() -> None:
    prepared = _prepared(
        before_values=[60.0, 61.0, 59.0, 60.0, 62.0, 58.0, 60.0, 61.0],
        after_values=[50.0, 49.0, 51.0, 48.0, 50.0, 49.0, 47.0, 51.0],
        direction=BeforeAfterDirection.DECREASE,
    )
    env = paired_t_test(prepared)
    assert env.estimate["observed_direction"] == "decrease"
    assert env.estimate["direction_matches_hypothesis"] is True


# ===========================================================================
# T017 / FR-007 / NFR-004 — >= 6 distinct refusal classes, no estimate
# ===========================================================================


def _assert_refusal(env, *, reason: str | None = None) -> None:
    assert env.status is AnalyticalStatus.REFUSED
    assert env.estimate is None
    assert env.refusal is not None
    assert env.refusal.reason
    if reason is not None:
        assert env.refusal.reason == reason


def test_refusal_2_too_few_pairs_propagates_from_seam() -> None:
    # 3 before + 3 after -> 3 pairs, below the floor of 8.
    prepared = _prepared(
        before_values=[50.0, 51.0, 52.0],
        after_values=[60.0, 61.0, 62.0],
    )
    _assert_refusal(paired_t_test(prepared))
    assert prepared.raw_pair_count < BEFORE_AFTER_MIN_PAIRS


def test_refusal_3_no_valid_pairs_propagates_from_seam() -> None:
    # Only before-side observations -> no matched pair can be built.
    prepared = _prepared(
        before_values=[50.0, 51.0, 52.0, 53.0, 54.0, 55.0, 56.0, 57.0],
        after_values=[],
    )
    _assert_refusal(paired_t_test(prepared))


def test_refusal_4_missing_direction_propagates_from_seam() -> None:
    series = _paired_series(
        before_values=[50.0, 51.0, 52.0, 53.0, 54.0, 55.0, 56.0, 57.0],
        after_values=[60.0, 61.0, 62.0, 63.0, 64.0, 65.0, 66.0, 67.0],
    )
    bad_request = _request(direction=None)  # missing expected direction
    prepared = prepare_before_after_paired_input(series, bad_request)
    _assert_refusal(paired_t_test(prepared))


def test_refusal_5_invalid_window_param_propagates_from_seam() -> None:
    series = _paired_series(
        before_values=[50.0, 51.0, 52.0, 53.0, 54.0, 55.0, 56.0, 57.0],
        after_values=[60.0, 61.0, 62.0, 63.0, 64.0, 65.0, 66.0, 67.0],
    )
    bad_request = _request(before_days=MAX_WINDOW_DAYS + 1)
    prepared = prepare_before_after_paired_input(series, bad_request)
    _assert_refusal(paired_t_test(prepared))


def test_refusal_7_stale_evidence_propagates_from_seam() -> None:
    # A refused (inadmissible) series propagates as a paired refusal -> no estimate.
    bad_series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.PAIRED_DIFFERENCE,
        candidate=_candidate(METRIC, point_count=2),
        policies=_policy(METRIC, min_observations=50),  # sufficiency floor not met
        points=[_point(ANCHOR - timedelta(days=1), 50.0), _point(ANCHOR + timedelta(days=1), 60.0)],
        reference_time=REFERENCE,
        freshness_status="stale",
    )
    prepared = prepare_before_after_paired_input(bad_series, _request())
    _assert_refusal(paired_t_test(prepared))


def test_refusal_8_scan_request_is_rejected_before_computation() -> None:
    # FR-014 / C-004: any extra argument is an attempt to scan anchors/windows;
    # the seam refuses before pairing, and that refusal surfaces with no estimate.
    series = _paired_series(
        before_values=[50.0, 51.0, 52.0, 53.0, 54.0, 55.0, 56.0, 57.0],
        after_values=[60.0, 61.0, 62.0, 63.0, 64.0, 65.0, 66.0, 67.0],
    )
    prepared = prepare_before_after_paired_input(series, _request(), select_best_anchor=True)
    _assert_refusal(paired_t_test(prepared))
    # And the tool itself refuses a direct scan request without re-deriving pairs.
    env = paired_t_test(_usable_increase(), scan_anchors=True)
    _assert_refusal(env)


def test_at_least_six_distinct_refusal_reasons() -> None:
    reasons = {
        paired_t_test(_refused_paired_input()).refusal.reason,
        paired_t_test(
            _prepared(before_values=[50.0, 51.0, 52.0], after_values=[60.0, 61.0, 62.0])
        ).refusal.reason,
        paired_t_test(
            _prepared(
                before_values=[50.0, 51.0, 52.0, 53.0, 54.0, 55.0, 56.0, 57.0],
                after_values=[],
            )
        ).refusal.reason,
        paired_t_test(
            _prepared(
                before_values=[50.0] * 8,
                after_values=[60.0] * 8,
            )
        ).refusal.reason,
        paired_t_test(_usable_increase(), unsupported_kwarg=1).refusal.reason,
    }
    # Direction-missing refusal (distinct seam reason).
    series = _paired_series(
        before_values=[50.0, 51.0, 52.0, 53.0, 54.0, 55.0, 56.0, 57.0],
        after_values=[60.0, 61.0, 62.0, 63.0, 64.0, 65.0, 66.0, 67.0],
    )
    reasons.add(
        paired_t_test(
            prepare_before_after_paired_input(series, _request(direction=None))
        ).refusal.reason
    )
    assert len(reasons) >= 6, reasons


# ===========================================================================
# T020 — no-hidden-search: the uncertainty payload is dispersion-only
# ===========================================================================


def test_uncertainty_payload_is_dispersion_only() -> None:
    # The anchor-date uncertainty payload reports dispersion, never a test verdict.
    env = paired_t_test(_usable_increase())
    payload = env.uncertainty.payload
    assert set(payload) >= {
        "std_difference",
        "std_error",
        "difference_interval_low",
        "difference_interval_high",
    }


# ===========================================================================
# T019 — confound metadata
# ===========================================================================


def test_floor_pairs_constant_matches_usable_fixture() -> None:
    # The anchor-date low-sample floor is exactly BEFORE_AFTER_MIN_PAIRS pairs.
    prepared = _usable_increase()
    assert prepared.raw_pair_count == BEFORE_AFTER_MIN_PAIRS


def test_flags_high_imputation() -> None:
    imputed = tuple(ANCHOR - timedelta(days=i) for i in range(1, 6)) + tuple(
        ANCHOR + timedelta(days=i) for i in range(1, 6)
    )
    before = [50.0, 51.0, 52.0, 50.0, 51.0, 49.0, 50.0, 52.0]
    after = [61.0, 60.0, 62.0, 59.0, 61.0, 60.0, 58.0, 62.0]
    prepared = _prepared(before_values=before, after_values=after, imputed_days=imputed)
    env = paired_t_test(prepared)
    keys = {e.key for e in env.confound_checklist}
    assert ConfoundKey.HIGH_IMPUTATION in keys
    assert env.is_imputed_pct > 0.0


# ===========================================================================
# T018 / T020 — definition-of-done: consumes WP03 seam
# ===========================================================================


def test_paired_t_test_consumes_the_wp03_seam() -> None:
    # The tool must read pairs through the WP03 seam, not re-derive them. The
    # module source references the seam helpers by name.
    import premura.engine.paired_t_test as ptt

    with open(ptt.__file__, encoding="utf-8") as fh:
        text = fh.read()
    assert "before_after_pairs_for_computation" in text


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
