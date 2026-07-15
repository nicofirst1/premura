"""Tests for the ``condition_paired_t_test`` analytical tool (m8 WP2).

These exercise ``condition_paired_t_test`` *behind* the analytical contract and
*through* the m8 condition-label paired-input seam, mirroring the
``paired_t_test`` tests:

* the tool registers against the shared contract registry (importing the module
  runs the decorator), so the default surface can discover and dispatch it;
* it consumes the m8 ``ConditionLabelPairedInput`` seam — it never re-derives the
  per-episode pairs; a refused paired input is surfaced as a refusal envelope;
* available runs produce deterministic, byte-stable, metadata-bearing envelopes
  reporting mean per-episode difference (on - off), observed/expected/match
  direction, the echoed label, episode_count_declared / episode_count_used,
  per-episode exclusions, window parameters, method revision, the descriptive
  dispersion band, and a closed-vocabulary confound checklist; weak, constant,
  scanning, stale, and refused inputs refuse with no estimate;
* honesty boundary: no p-value / significant / hypothesis-pass / causal /
  diagnostic / treatment / dosing / emergency / population-norm language in any
  estimate, caveat, or message.

Everything is fixture-backed; the tool reads no warehouse, so nothing here
touches SQL, DuckDB, MCP, the network, or a clock.
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
from premura.engine.paired_inputs import BeforeAfterDirection
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
LABEL = "on_magnesium"


# ---------------------------------------------------------------------------
# Fixture-backed evidence helpers
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
        question_rules={QuestionType.CONDITION_PAIRED_DIFFERENCE: rule},
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
        AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE,
        candidate=_candidate(METRIC, point_count=len(points)),
        policies=_policy(METRIC, min_observations=min_observations),
        points=points,
        reference_time=REFERENCE,
        freshness_status=freshness_status,
    )


def _episode(start: date, end: date) -> ConditionEpisode:
    return ConditionEpisode(start_day=start, end_day=end)


def _request(
    *,
    episodes: tuple[ConditionEpisode, ...],
    before_days: int = 5,
    after_days: int = 5,
    label: str = LABEL,
    direction: BeforeAfterDirection | None = BeforeAfterDirection.INCREASE,
) -> ConditionLabelPairedRequest:
    return ConditionLabelPairedRequest(
        metric_id=METRIC,
        condition_label=label,
        episodes=episodes,
        before_days=before_days,
        after_days=after_days,
        expected_direction=direction,  # type: ignore[arg-type]
    )


def _episode_block(
    points: list[PreparedPoint],
    start: date,
    end: date,
    *,
    off_value: float,
    on_value: float,
    before_days: int = 5,
    imputed_off: bool = False,
    imputed_on: bool = False,
) -> None:
    for i in range(1, before_days + 1):
        points.append(_point(start - timedelta(days=i), off_value, imputed=imputed_off))
    day = start
    while day <= end:
        points.append(_point(day, on_value, imputed=imputed_on))
        day += timedelta(days=1)


def _usable_increase() -> ConditionLabelPairedInput:
    """3 clean increasing episodes (on - off > 0, with spread so not constant)."""
    blocks = [
        (date(2026, 3, 1), date(2026, 3, 3), 50.0, 60.0),
        (date(2026, 4, 1), date(2026, 4, 3), 51.0, 63.0),
        (date(2026, 5, 1), date(2026, 5, 3), 49.0, 58.0),
    ]
    points: list[PreparedPoint] = []
    episodes: list[ConditionEpisode] = []
    for start, end, off_v, on_v in blocks:
        _episode_block(points, start, end, off_value=off_v, on_value=on_v)
        episodes.append(_episode(start, end))
    series = _series(sorted(points, key=lambda p: p.ts))
    return prepare_condition_label_paired_input(series, _request(episodes=tuple(episodes)))


# Terms doctrine forbids in any surfaced estimate / caveat / message.
_FORBIDDEN_PATTERNS = (
    r"\bp-?value\w*",
    r"\bsignifican\w*",
    r"\bhypothesis\s+(?:test|confirmed|rejected|passed)",
    r"\bcaus\w*",
    r"\beffect\w*",
    r"\bimpact\w*",
    r"\bdriver\b",
    r"\bdiagnos\w*",
    r"\btreat\w*",
    r"\bdos\w*",
    r"\bemergenc\w*",
    r"\bpopulation\b",
    r"\bnorm\w*",
)


def _all_text(envelope_dict: dict) -> str:
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


# ===========================================================================
# Registration / contract wiring
# ===========================================================================


def test_tool_registers_against_the_contract() -> None:
    assert CONDITION_PAIRED_T_TEST_TOOL == "condition_paired_t_test"
    assert CONDITION_PAIRED_T_TEST_TOOL in REGISTRY
    spec = REGISTRY[CONDITION_PAIRED_T_TEST_TOOL]
    assert spec.fn is condition_paired_t_test
    assert spec.question_type is AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE
    assert spec.result_kind == "condition_paired_difference_estimate"
    assert spec.revision == "1"
    assert set(spec.confound_keys) <= CONFOUND_KEYS


# NOTE: dispatch equivalence, determinism, forbidden-language, no-p-value,
# refused-input-surfaces, refusals-carry-no-estimate, constant-difference
# refusal, direction-mismatch metadata, caveat-length budget, low-sample &
# temporal-autocorrelation confound flags, and MCP/trace/network import
# isolation are all identical across the mirror pair and are asserted once,
# parametrized over BOTH tools, in ``test_engine_paired_t_test.py`` (the shared
# cross-tool sweep). This file keeps only condition-input-SPECIFIC coverage.


# ===========================================================================
# Available envelope completeness (FR-3)
# ===========================================================================


def test_available_envelope_reports_required_fields() -> None:
    prepared = _usable_increase()
    env = condition_paired_t_test(prepared)

    assert env.tool_name == "condition_paired_t_test"
    assert env.status is AnalyticalStatus.AVAILABLE
    assert env.inputs == (METRIC,)
    # Declared window parameters + label preserved.
    assert env.parameters["condition_label"] == LABEL
    assert env.parameters["before_days"] == 5
    assert env.parameters["after_days"] == 5
    assert env.parameters["expected_direction"] == "increase"
    est = env.estimate
    assert est is not None
    # Mean per-episode difference (on - off), positive here.
    assert est["mean_difference"] > 0
    assert est["observed_direction"] == "increase"
    assert est["expected_direction"] == "increase"
    assert est["direction_matches_hypothesis"] is True
    # Label echoed + episode counts.
    assert est["condition_label"] == LABEL
    assert est["episode_count_declared"] == 3
    assert est["episode_count_used"] == 3
    assert est["per_episode_exclusions"] == []
    assert est["before_days"] == 5
    assert est["after_days"] == 5
    assert est["method_revision"] == "1"
    # sample size is the usable episode count (the paired unit).
    assert env.sample_size == 3
    # Uncertainty: descriptive dispersion band, NOT a p-value.
    assert env.uncertainty is not None and env.uncertainty.available is True
    payload = env.uncertainty.payload
    assert payload is not None
    assert "std_difference" in payload
    assert "std_error" in payload
    assert "difference_interval_low" in payload
    assert "difference_interval_high" in payload
    assert payload["interval_kind"] == "descriptive_dispersion_band"
    assert "p_value" not in payload
    # Closed-vocabulary confound checklist.
    for entry in env.confound_checklist:
        assert entry.key.value in CONFOUND_KEYS
    # Two required caveats.
    assert len(env.caveats) == 2


def test_mean_difference_is_mean_of_per_episode_on_minus_off() -> None:
    prepared = _usable_increase()
    env = condition_paired_t_test(prepared)
    diffs = [p.difference for p in prepared.pairs]
    assert env.estimate["mean_difference"] == pytest.approx(sum(diffs) / len(diffs))


# ===========================================================================
# Refusals (R1-R8): >= 6 distinct reasons, no estimate
# ===========================================================================


def _assert_refusal(env, *, reason: str | None = None) -> None:
    assert env.status is AnalyticalStatus.REFUSED
    assert env.estimate is None
    assert env.refusal is not None
    assert env.refusal.reason
    if reason is not None:
        assert env.refusal.reason == reason


def _refused_input() -> ConditionLabelPairedInput:
    series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE,
        candidate=_candidate(METRIC, point_count=0),
        policies=_policy(METRIC),
        points=[],
        reference_time=REFERENCE,
    )
    prepared = prepare_condition_label_paired_input(
        series,
        _request(
            episodes=(
                _episode(date(2026, 4, 1), date(2026, 4, 3)),
                _episode(date(2026, 5, 1), date(2026, 5, 3)),
            )
        ),
    )
    assert prepared.refusal is not None
    return prepared


def test_r8_stale_evidence_propagates_from_seam() -> None:
    bad_series = prepare_input_series(
        METRIC,
        AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE,
        candidate=_candidate(METRIC, point_count=2),
        policies=_policy(METRIC, min_observations=50),  # sufficiency floor not met
        points=[_point(date(2026, 5, 1), 50.0), _point(date(2026, 5, 2), 60.0)],
        reference_time=REFERENCE,
        freshness_status="stale",
    )
    prepared = prepare_condition_label_paired_input(
        bad_series,
        _request(
            episodes=(
                _episode(date(2026, 4, 1), date(2026, 4, 3)),
                _episode(date(2026, 5, 1), date(2026, 5, 3)),
            )
        ),
    )
    _assert_refusal(condition_paired_t_test(prepared))


def test_scan_request_is_rejected_before_computation() -> None:
    # Any extra argument to the tool is an unsupported scan request.
    env = condition_paired_t_test(_usable_increase(), scan_labels=True)
    _assert_refusal(env, reason="unsupported_parameter")
    _assert_no_forbidden_language(env)


def test_at_least_six_distinct_refusal_reasons() -> None:
    series = _series(
        sorted(
            (
                lambda pts: [
                    *(_point(date(2026, 4, 1) - timedelta(days=i), 50.0) for i in range(1, 6)),
                    _point(date(2026, 4, 1), 60.0),
                    *(_point(date(2026, 6, 1) - timedelta(days=i), 50.0) for i in range(1, 6)),
                    _point(date(2026, 6, 1), 60.0),
                ]
            )(None),
            key=lambda p: p.ts,
        )
    )
    reasons = set()
    # R1 upstream-refused
    reasons.add(condition_paired_t_test(_refused_input()).refusal.reason)
    # R2 too few declared episodes
    reasons.add(
        condition_paired_t_test(
            prepare_condition_label_paired_input(
                series, _request(episodes=(_episode(date(2026, 4, 1), date(2026, 4, 3)),))
            )
        ).refusal.reason
    )
    # R3 overlapping episodes
    reasons.add(
        condition_paired_t_test(
            prepare_condition_label_paired_input(
                series,
                _request(
                    episodes=(
                        _episode(date(2026, 5, 1), date(2026, 5, 10)),
                        _episode(date(2026, 5, 8), date(2026, 5, 15)),
                    )
                ),
            )
        ).refusal.reason
    )
    # R5 missing direction
    reasons.add(
        condition_paired_t_test(
            prepare_condition_label_paired_input(
                series,
                _request(
                    episodes=(
                        _episode(date(2026, 4, 1), date(2026, 4, 3)),
                        _episode(date(2026, 6, 1), date(2026, 6, 3)),
                    ),
                    direction=None,
                ),
            )
        ).refusal.reason
    )
    # R7 constant differences (tool-level)
    const_pts: list[PreparedPoint] = []
    const_eps: list[ConditionEpisode] = []
    for start, end in (
        (date(2026, 3, 1), date(2026, 3, 3)),
        (date(2026, 4, 1), date(2026, 4, 3)),
        (date(2026, 5, 1), date(2026, 5, 3)),
    ):
        _episode_block(const_pts, start, end, off_value=50.0, on_value=60.0)
        const_eps.append(_episode(start, end))
    reasons.add(
        condition_paired_t_test(
            prepare_condition_label_paired_input(
                _series(sorted(const_pts, key=lambda p: p.ts)),
                _request(episodes=tuple(const_eps)),
            )
        ).refusal.reason
    )
    # unsupported scan
    reasons.add(condition_paired_t_test(_usable_increase(), bad_kwarg=1).refusal.reason)
    assert len(reasons) >= 6, reasons


# ===========================================================================
# Spec-named edge cases (E1, E2, E4) — each requires an end-to-end test
# ===========================================================================


def test_e1_before_window_contamination_excludes_episode_2() -> None:
    # 3 declared episodes where episode 2's before-window overlaps episode 1.
    # ep2 excluded with disclosure; result computed from the other 2.
    ep1 = (date(2026, 5, 1), date(2026, 5, 5))
    ep2 = (date(2026, 5, 8), date(2026, 5, 10))  # before-window [5..7] touches ep1
    ep3 = (date(2026, 6, 1), date(2026, 6, 3))
    points: list[PreparedPoint] = []
    # ep1: clean off + on
    _episode_block(points, *ep1, off_value=50.0, on_value=60.0)
    # ep2: on data present, but its before-window has no CLEAN off day (all inside
    # ep1 or its on-tail) -> excluded.
    day = ep2[0]
    while day <= ep2[1]:
        points.append(_point(day, 70.0))
        day += timedelta(days=1)
    # ep3: clean off + on
    _episode_block(points, *ep3, off_value=51.0, on_value=62.0)
    series = _series(sorted(points, key=lambda p: p.ts))
    request = _request(
        episodes=(_episode(*ep1), _episode(*ep2), _episode(*ep3)),
        before_days=3,
        after_days=5,
    )
    prepared = prepare_condition_label_paired_input(series, request)
    env = condition_paired_t_test(prepared)
    assert env.status is AnalyticalStatus.AVAILABLE
    est = env.estimate
    assert est["episode_count_declared"] == 3
    assert est["episode_count_used"] == 2
    excl_starts = {ex["episode_start"] for ex in est["per_episode_exclusions"]}
    assert ep2[0].isoformat() in excl_starts


def test_e2_exclusion_drops_usable_below_floor_refuses_naming_exclusion() -> None:
    # 2 declared episodes, one has an empty on-window -> refusal, and the refusal
    # payload names the exclusion that caused it.
    ep1 = (date(2026, 4, 1), date(2026, 4, 3))
    ep2 = (date(2026, 5, 1), date(2026, 5, 3))  # off-only, empty on-window
    points: list[PreparedPoint] = []
    _episode_block(points, *ep1, off_value=50.0, on_value=60.0)
    for i in range(1, 6):
        points.append(_point(ep2[0] - timedelta(days=i), 50.0))
    series = _series(sorted(points, key=lambda p: p.ts))
    prepared = prepare_condition_label_paired_input(
        series, _request(episodes=(_episode(*ep1), _episode(*ep2)))
    )
    env = condition_paired_t_test(prepared)
    _assert_refusal(env, reason="too_few_usable_episodes")
    # The refusal names the excluded episode.
    assert ep2[0].isoformat() in env.refusal.message or any(
        ep2[0].isoformat() in s for s in env.refusal.missing_or_bad_inputs
    )


def test_e4_episode_truncated_by_after_days_uses_only_first_on_days() -> None:
    # An episode longer than after_days uses only the first after_days on-days.
    start, end = date(2026, 5, 1), date(2026, 5, 10)
    points: list[PreparedPoint] = []
    for i in range(1, 6):
        points.append(_point(start - timedelta(days=i), 50.0))
    points.append(_point(start, 60.0))
    points.append(_point(start + timedelta(days=1), 60.0))
    day = start + timedelta(days=2)
    while day <= end:
        points.append(_point(day, 500.0))  # must be excluded by after_days=2
        day += timedelta(days=1)
    # second clean episode to clear the floor, with a DIFFERENT difference so the
    # per-episode differences are not constant (which would refuse).
    ep2 = (date(2026, 6, 1), date(2026, 6, 2))
    _episode_block(points, *ep2, off_value=50.0, on_value=64.0)
    series = _series(sorted(points, key=lambda p: p.ts))
    prepared = prepare_condition_label_paired_input(
        series,
        _request(episodes=(_episode(start, end), _episode(*ep2)), before_days=5, after_days=2),
    )
    env = condition_paired_t_test(prepared)
    assert env.status is AnalyticalStatus.AVAILABLE
    # The first episode's on-mean is 60 (the 500s past after_days=2 are excluded);
    # if they leaked in, the first episode's difference would be hugely inflated.
    # diffs: ep1 = 60-50 = 10, ep2 = 64-50 = 14 -> mean 12.
    assert prepared.pairs[0].on_value == pytest.approx(60.0)
    assert env.estimate["mean_difference"] == pytest.approx(12.0)


# ===========================================================================
# Confound metadata (condition-input-specific: episode floor + life-event split)
# ===========================================================================


def test_flags_low_sample_size_at_episode_floor() -> None:
    # Exactly 2 usable episodes (the condition floor) -> low sample size confound.
    blocks = [
        (date(2026, 4, 1), date(2026, 4, 3), 50.0, 60.0),
        (date(2026, 5, 1), date(2026, 5, 3), 51.0, 63.0),
    ]
    points: list[PreparedPoint] = []
    episodes: list[ConditionEpisode] = []
    for start, end, off_v, on_v in blocks:
        _episode_block(points, start, end, off_value=off_v, on_value=on_v)
        episodes.append(_episode(start, end))
    series = _series(sorted(points, key=lambda p: p.ts))
    prepared = prepare_condition_label_paired_input(series, _request(episodes=tuple(episodes)))
    assert prepared.episode_count_used == 2
    env = condition_paired_t_test(prepared)
    keys = {e.key for e in env.confound_checklist}
    assert ConfoundKey.LOW_SAMPLE_SIZE in keys


def test_flags_life_event_sensitive() -> None:
    # A condition-label split is inherently life-event sensitive.
    env = condition_paired_t_test(_usable_increase())
    keys = {e.key for e in env.confound_checklist}
    assert ConfoundKey.LIFE_EVENT_SENSITIVE in keys


# ===========================================================================
# NFR-2 — engine isolation (condition-specific: consumes the condition seam)
# ===========================================================================


def test_tool_consumes_the_condition_seam() -> None:
    import premura.engine.condition_paired_t_test as tool

    with open(tool.__file__, encoding="utf-8") as fh:
        text = fh.read()
    assert "condition_episode_pairs_for_computation" in text


# ===========================================================================
# NFR-4 — paired_t_test public behavior byte-for-byte unchanged
# ===========================================================================


def test_anchor_date_paired_t_test_is_unchanged() -> None:
    # The new tool is a distinct registry entry; the anchor-date tool still exists
    # and is a different name/question type.
    from premura.engine import load_builtin_analytical_tools

    load_builtin_analytical_tools()
    assert "paired_t_test" in REGISTRY
    assert "condition_paired_t_test" in REGISTRY
    assert REGISTRY["paired_t_test"].question_type is AnalyticalQuestionType.PAIRED_DIFFERENCE
    assert (
        REGISTRY["condition_paired_t_test"].question_type
        is AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
