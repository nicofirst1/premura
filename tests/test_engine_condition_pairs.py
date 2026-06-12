"""Tests for the condition-label paired-input layer (m8 WP1).

These exercise the narrow preparation seam ``condition_paired_t_test`` (WP2) needs
before any per-episode estimate can run: one already-admitted single-series
:class:`AnalyticalInputSeries` plus a caller-declared
:class:`ConditionLabelPairedRequest` (metric, operator-declared condition label,
declared non-overlapping episodes, before/after windows, expected direction)
becomes an ordered, per-episode :class:`ConditionLabelPairedInput` carrying one
off/on pair per usable episode and machine-readable per-episode exclusions — or a
first-class :class:`RefusalOutcome` with **no** pairs. This layer produces a
*prepared per-episode pair set or a refusal*, never an estimate.

The ONE fixed pairing rule under test (also stated in the module docstring/spec):

* An **episode** is a declared closed local-calendar-day range
  ``[start_day, end_day]``, ``end_day >= start_day``. Episodes must not overlap.
* Each episode contributes **one pair**:
  * **off value** = mean of usable observations on days in
    ``[start_day - before_days, start_day)`` that fall **outside every declared
    episode**;
  * **on value** = mean of usable observations on days in
    ``[start_day, min(start_day + after_days - 1, end_day)]``;
  * **difference = on - off**.
* Day keying / last-write-wins per local calendar day mirror ``paired_inputs.py``.
* An episode whose before-window intersects another declared episode, or that
  lacks at least one usable observation in either window, is **excluded with a
  per-episode disclosure**. Fewer than 2 usable episodes after exclusions → refuse.

Everything is fixture-backed; the layer reads no warehouse, so nothing here
touches SQL, DuckDB, MCP, the network, or a clock.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from premura.engine.analytical_contract import AnalyticalQuestionType, RefusalOutcome
from premura.engine.analytical_inputs import (
    AnalyticalInputSeries,
    PreparedPoint,
    prepare_input_series,
)
from premura.engine.condition_inputs import (
    CONDITION_MIN_EPISODES,
    ConditionEpisode,
    ConditionEpisodePair,
    ConditionLabelPairedInput,
    ConditionLabelPairedRequest,
    ConditionPairRefusalReason,
    condition_episode_pairs_for_computation,
    prepare_condition_label_paired_input,
)
from premura.engine.paired_inputs import (
    MAX_WINDOW_DAYS,
    BeforeAfterDirection,
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
LABEL = "on_magnesium"


# ---------------------------------------------------------------------------
# Fixture-backed evidence helpers (mirror the WP03 before/after style)
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


def _point(
    day: date,
    value: float,
    *,
    hour: int = 12,
    imputed: bool = False,
    local_tz: str | None = None,
) -> PreparedPoint:
    return PreparedPoint(
        ts=datetime(day.year, day.month, day.day, hour, 0, 0),
        value=value,
        is_imputed=imputed,
        local_tz=local_tz,
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


# Two clean, well-separated episodes, each with off-window and on-window data.
_EP1 = (date(2026, 4, 1), date(2026, 4, 5))
_EP2 = (date(2026, 5, 1), date(2026, 5, 5))


def _two_episode_series(
    *,
    off_value: float = 50.0,
    on_value: float = 60.0,
    before_days: int = 5,
) -> AnalyticalInputSeries:
    """Build a series with off-window + on-window data for both episodes."""
    points: list[PreparedPoint] = []
    for start, end in (_EP1, _EP2):
        # off-window: the before_days days strictly before start.
        for i in range(1, before_days + 1):
            points.append(_point(start - timedelta(days=i), off_value))
        # on-window: every day in the episode.
        day = start
        while day <= end:
            points.append(_point(day, on_value))
            day += timedelta(days=1)
    return _series(sorted(points, key=lambda p: p.ts))


# ===========================================================================
# Happy path — one off/on pair per usable episode (the fixed pairing rule)
# ===========================================================================


def test_two_clean_episodes_build_one_pair_each() -> None:
    series = _two_episode_series(off_value=50.0, on_value=60.0)
    request = _request(episodes=(_episode(*_EP1), _episode(*_EP2)))

    prepared = prepare_condition_label_paired_input(series, request)

    assert prepared.refusal is None
    assert prepared.is_usable
    assert prepared.episode_count_declared == 2
    assert prepared.episode_count_used == 2
    assert len(prepared.pairs) == 2
    assert prepared.excluded_episodes == ()
    first = prepared.pairs[0]
    assert isinstance(first, ConditionEpisodePair)
    assert first.episode_start == _EP1[0]
    assert first.off_value == pytest.approx(50.0)
    assert first.on_value == pytest.approx(60.0)
    assert first.difference == pytest.approx(10.0)  # on - off


def test_condition_label_is_echoed_verbatim() -> None:
    series = _two_episode_series()
    request = _request(episodes=(_episode(*_EP1), _episode(*_EP2)), label="post_surgery_rehab")
    prepared = prepare_condition_label_paired_input(series, request)
    assert prepared.refusal is None
    assert prepared.condition_label == "post_surgery_rehab"


def test_off_value_excludes_days_inside_any_episode() -> None:
    # An off-window day that happens to lie inside ANOTHER declared episode must
    # not be counted as an off observation.
    ep_a = (date(2026, 5, 10), date(2026, 5, 12))
    ep_b = (date(2026, 5, 14), date(2026, 5, 16))  # b's off-window overlaps a's days
    points: list[PreparedPoint] = []
    # off-window data for ep_a (clean, before ep_a).
    for i in range(1, 6):
        points.append(_point(ep_a[0] - timedelta(days=i), 50.0))
    # on-window data for ep_a and ep_b.
    for start, end in (ep_a, ep_b):
        day = start
        while day <= end:
            points.append(_point(day, 60.0))
            day += timedelta(days=1)
    # A contaminating point on ep_a's last on-day, which is inside ep_b's
    # before-window — it must be excluded from ep_b's off mean.
    series = _series(sorted(points, key=lambda p: p.ts))
    request = _request(episodes=(_episode(*ep_a), _episode(*ep_b)), before_days=3, after_days=5)
    prepared = prepare_condition_label_paired_input(series, request)
    # ep_b's off-window [11..13] all lie inside ep_a or are contaminated, leaving
    # no clean off observation -> ep_b excluded. With only ep_a usable (< floor of
    # 2) the request refuses, naming the exclusion.
    assert prepared.refusal is not None
    assert prepared.refusal.reason == ConditionPairRefusalReason.TOO_FEW_USABLE_EPISODES.value


def test_on_value_truncates_at_after_days() -> None:
    # An episode longer than after_days uses only the first after_days on-days.
    start, end = date(2026, 5, 1), date(2026, 5, 10)  # 10-day episode
    points: list[PreparedPoint] = []
    for i in range(1, 6):
        points.append(_point(start - timedelta(days=i), 50.0))
    # on-window: first 2 days value 60, later in-episode days value 200 (must be
    # ignored when after_days=2).
    points.append(_point(start, 60.0))
    points.append(_point(start + timedelta(days=1), 60.0))
    day = start + timedelta(days=2)
    while day <= end:
        points.append(_point(day, 200.0))
        day += timedelta(days=1)
    # A second clean episode so we clear the floor of 2.
    ep2 = (date(2026, 6, 1), date(2026, 6, 2))
    for i in range(1, 6):
        points.append(_point(ep2[0] - timedelta(days=i), 50.0))
    points.append(_point(ep2[0], 60.0))
    points.append(_point(ep2[1], 60.0))
    series = _series(sorted(points, key=lambda p: p.ts))
    request = _request(episodes=(_episode(start, end), _episode(*ep2)), before_days=5, after_days=2)
    prepared = prepare_condition_label_paired_input(series, request)
    assert prepared.refusal is None
    first = prepared.pairs[0]
    assert first.episode_start == start
    # Only the first 2 on-days (value 60) count; the 200s are past after_days.
    assert first.on_value == pytest.approx(60.0)


def test_preparation_is_deterministic() -> None:
    series = _two_episode_series()
    request = _request(episodes=(_episode(*_EP1), _episode(*_EP2)))
    a = prepare_condition_label_paired_input(series, request)
    b = prepare_condition_label_paired_input(series, request)
    assert a.to_dict() == b.to_dict()


def test_to_dict_is_json_safe() -> None:
    import json

    series = _two_episode_series()
    prepared = prepare_condition_label_paired_input(
        series, _request(episodes=(_episode(*_EP1), _episode(*_EP2)))
    )
    text = json.dumps(prepared.to_dict())
    assert METRIC in text
    assert LABEL in text


# ===========================================================================
# Per-episode exclusions (disclosure, not silent salvage)
# ===========================================================================


def test_episode_with_empty_on_window_is_excluded_with_disclosure() -> None:
    # ep2 has off data but no on-window observation -> excluded with a disclosure.
    # ep1 and ep3 are clean so the request still computes (2 usable >= floor).
    ep1 = (date(2026, 4, 1), date(2026, 4, 3))
    ep2 = (date(2026, 5, 1), date(2026, 5, 3))
    ep3 = (date(2026, 6, 1), date(2026, 6, 3))
    points: list[PreparedPoint] = []
    for start, end in (ep1, ep3):
        for i in range(1, 6):
            points.append(_point(start - timedelta(days=i), 50.0))
        day = start
        while day <= end:
            points.append(_point(day, 60.0))
            day += timedelta(days=1)
    # ep2: only off-window data, no on-window observation.
    for i in range(1, 6):
        points.append(_point(ep2[0] - timedelta(days=i), 50.0))
    series = _series(sorted(points, key=lambda p: p.ts))
    request = _request(episodes=(_episode(*ep1), _episode(*ep2), _episode(*ep3)))
    prepared = prepare_condition_label_paired_input(series, request)
    assert prepared.refusal is None
    assert prepared.episode_count_declared == 3
    assert prepared.episode_count_used == 2
    starts = {ex["episode_start"] for ex in prepared.excluded_episodes_as_dicts()}
    assert ep2[0].isoformat() in starts


def test_excluded_episode_carries_machine_readable_reason() -> None:
    ep1 = (date(2026, 4, 1), date(2026, 4, 3))
    ep2 = (date(2026, 5, 1), date(2026, 5, 3))  # no on-window data
    ep3 = (date(2026, 6, 1), date(2026, 6, 3))
    points: list[PreparedPoint] = []
    for start, end in (ep1, ep3):
        for i in range(1, 6):
            points.append(_point(start - timedelta(days=i), 50.0))
        day = start
        while day <= end:
            points.append(_point(day, 60.0))
            day += timedelta(days=1)
    for i in range(1, 6):
        points.append(_point(ep2[0] - timedelta(days=i), 50.0))
    series = _series(sorted(points, key=lambda p: p.ts))
    prepared = prepare_condition_label_paired_input(
        series, _request(episodes=(_episode(*ep1), _episode(*ep2), _episode(*ep3)))
    )
    assert prepared.refusal is None
    excl = [e for e in prepared.excluded_episodes if e.episode_start == ep2[0]]
    assert len(excl) == 1
    assert excl[0].reason  # a non-empty machine-readable reason string


# ===========================================================================
# Refusals (R1-R6 at the seam level): each distinct, no pairs
# ===========================================================================


def test_r1_refused_input_series_propagates_verbatim() -> None:
    refused = _series([_point(date(2026, 5, 1), 1.0)], min_observations=99)
    assert refused.refusal is not None  # precondition
    prepared = prepare_condition_label_paired_input(
        refused, _request(episodes=(_episode(*_EP1), _episode(*_EP2)))
    )
    assert prepared.refusal is not None
    assert prepared.pairs == ()
    assert prepared.refusal.reason == refused.refusal.reason


def test_r2_fewer_than_two_episodes_declared_refuses() -> None:
    series = _two_episode_series()
    prepared = prepare_condition_label_paired_input(series, _request(episodes=(_episode(*_EP1),)))
    assert prepared.refusal is not None
    assert prepared.refusal.reason == ConditionPairRefusalReason.TOO_FEW_EPISODES.value


def test_r3_overlapping_episodes_refuse_the_whole_request() -> None:
    series = _two_episode_series()
    ov1 = (date(2026, 5, 1), date(2026, 5, 10))
    ov2 = (date(2026, 5, 8), date(2026, 5, 15))  # overlaps ov1
    prepared = prepare_condition_label_paired_input(
        series, _request(episodes=(_episode(*ov1), _episode(*ov2)))
    )
    assert prepared.refusal is not None
    assert prepared.refusal.reason == ConditionPairRefusalReason.OVERLAPPING_EPISODES.value
    assert prepared.pairs == ()


def test_r4_invalid_episode_end_before_start_raises_at_construction() -> None:
    with pytest.raises(ValueError):
        ConditionEpisode(start_day=date(2026, 5, 10), end_day=date(2026, 5, 1))


def test_r4_invalid_window_non_positive_days_refuses() -> None:
    series = _two_episode_series()
    prepared = prepare_condition_label_paired_input(
        series, _request(episodes=(_episode(*_EP1), _episode(*_EP2)), before_days=0)
    )
    assert prepared.refusal is not None
    assert prepared.refusal.reason == ConditionPairRefusalReason.UNSUPPORTED_WINDOW.value
    assert prepared.refusal.parameter_name == "before_days"


@pytest.mark.parametrize("after_days", [0, -1, MAX_WINDOW_DAYS + 1])
def test_r4_out_of_bounds_after_days_refuses(after_days: int) -> None:
    series = _two_episode_series()
    prepared = prepare_condition_label_paired_input(
        series, _request(episodes=(_episode(*_EP1), _episode(*_EP2)), after_days=after_days)
    )
    assert prepared.refusal is not None
    assert prepared.refusal.reason == ConditionPairRefusalReason.UNSUPPORTED_WINDOW.value
    assert prepared.refusal.parameter_name == "after_days"


def test_r5_extra_scan_arg_refuses_before_pairing() -> None:
    series = _two_episode_series()
    prepared = prepare_condition_label_paired_input(
        series,
        _request(episodes=(_episode(*_EP1), _episode(*_EP2))),
        choose_best_episodes=True,
    )
    assert prepared.refusal is not None
    assert prepared.refusal.reason == ConditionPairRefusalReason.UNSUPPORTED_REQUEST.value


def test_r5_missing_direction_refuses() -> None:
    series = _two_episode_series()
    prepared = prepare_condition_label_paired_input(
        series, _request(episodes=(_episode(*_EP1), _episode(*_EP2)), direction=None)
    )
    assert prepared.refusal is not None
    assert prepared.refusal.reason == ConditionPairRefusalReason.MISSING_DIRECTION.value


def test_r6_too_few_usable_episodes_after_exclusions_refuses() -> None:
    # ep1 clean, ep2 has no on-window data -> only 1 usable -> refuse R6.
    ep1 = (date(2026, 4, 1), date(2026, 4, 3))
    ep2 = (date(2026, 5, 1), date(2026, 5, 3))
    points: list[PreparedPoint] = []
    for i in range(1, 6):
        points.append(_point(ep1[0] - timedelta(days=i), 50.0))
    day = ep1[0]
    while day <= ep1[1]:
        points.append(_point(day, 60.0))
        day += timedelta(days=1)
    for i in range(1, 6):
        points.append(_point(ep2[0] - timedelta(days=i), 50.0))
    series = _series(sorted(points, key=lambda p: p.ts))
    prepared = prepare_condition_label_paired_input(
        series, _request(episodes=(_episode(*ep1), _episode(*ep2)))
    )
    assert prepared.refusal is not None
    assert prepared.refusal.reason == ConditionPairRefusalReason.TOO_FEW_USABLE_EPISODES.value
    # The refusal names the exclusion that caused it.
    assert prepared.refusal.missing_or_bad_inputs


def test_refuses_metric_mismatch_between_request_and_series() -> None:
    series = _two_episode_series()
    bad = ConditionLabelPairedRequest(
        metric_id="some_other_metric",
        condition_label=LABEL,
        episodes=(_episode(*_EP1), _episode(*_EP2)),
        before_days=5,
        after_days=5,
        expected_direction=BeforeAfterDirection.INCREASE,
    )
    prepared = prepare_condition_label_paired_input(series, bad)
    assert prepared.refusal is not None
    assert prepared.refusal.reason == ConditionPairRefusalReason.INVALID_REQUEST.value


def test_refuses_empty_condition_label() -> None:
    series = _two_episode_series()
    prepared = prepare_condition_label_paired_input(
        series, _request(episodes=(_episode(*_EP1), _episode(*_EP2)), label="   ")
    )
    assert prepared.refusal is not None
    assert prepared.refusal.reason == ConditionPairRefusalReason.INVALID_REQUEST.value


# ===========================================================================
# Unknown-kwarg TypeErrors (frozen-dataclass scope guardrails, FR-2)
# ===========================================================================


def test_request_rejects_anchor_date_kwarg() -> None:
    with pytest.raises(TypeError):
        ConditionLabelPairedRequest(  # type: ignore[call-arg]
            metric_id=METRIC,
            condition_label=LABEL,
            episodes=(_episode(*_EP1), _episode(*_EP2)),
            before_days=5,
            after_days=5,
            expected_direction=BeforeAfterDirection.INCREASE,
            anchor_date=date(2026, 5, 1),
        )


def test_request_rejects_labels_list_kwarg() -> None:
    with pytest.raises(TypeError):
        ConditionLabelPairedRequest(  # type: ignore[call-arg]
            metric_id=METRIC,
            condition_label=LABEL,
            episodes=(_episode(*_EP1), _episode(*_EP2)),
            before_days=5,
            after_days=5,
            expected_direction=BeforeAfterDirection.INCREASE,
            labels=["a", "b"],
        )


def test_request_rejects_p_value_kwarg() -> None:
    with pytest.raises(TypeError):
        ConditionLabelPairedRequest(  # type: ignore[call-arg]
            metric_id=METRIC,
            condition_label=LABEL,
            episodes=(_episode(*_EP1), _episode(*_EP2)),
            before_days=5,
            after_days=5,
            expected_direction=BeforeAfterDirection.INCREASE,
            p_value=True,
        )


def test_episode_rejects_extra_kwarg() -> None:
    with pytest.raises(TypeError):
        ConditionEpisode(  # type: ignore[call-arg]
            start_day=date(2026, 5, 1),
            end_day=date(2026, 5, 5),
            label="x",
        )


# ===========================================================================
# computation-helper guard + direct-construction invariants
# ===========================================================================


def test_pairs_for_computation_raises_on_refused_input() -> None:
    series = _two_episode_series()
    prepared = prepare_condition_label_paired_input(series, _request(episodes=(_episode(*_EP1),)))
    assert prepared.refusal is not None
    with pytest.raises(RuntimeError):
        condition_episode_pairs_for_computation(prepared)


def test_pairs_for_computation_returns_pairs_when_usable() -> None:
    series = _two_episode_series()
    prepared = prepare_condition_label_paired_input(
        series, _request(episodes=(_episode(*_EP1), _episode(*_EP2)))
    )
    pairs = condition_episode_pairs_for_computation(prepared)
    assert pairs == prepared.pairs
    assert len(pairs) == 2


def test_direct_refused_input_rejects_carrying_pairs() -> None:
    pair = ConditionEpisodePair(
        episode_start=date(2026, 5, 1),
        episode_end=date(2026, 5, 5),
        off_value=50.0,
        on_value=60.0,
        off_count=5,
        on_count=5,
    )
    with pytest.raises(ValueError):
        ConditionLabelPairedInput(
            metric_id=METRIC,
            request=_request(episodes=(_episode(*_EP1), _episode(*_EP2))),
            condition_label=LABEL,
            pairs=(pair,),
            refusal=RefusalOutcome(reason="x", message="y"),
        )


def test_min_episodes_constant_is_two() -> None:
    assert CONDITION_MIN_EPISODES == 2


def test_direction_vocabulary_is_reused_not_reinvented() -> None:
    # The condition request reuses the existing closed BeforeAfterDirection set.
    assert {d.value for d in BeforeAfterDirection} == {"increase", "decrease"}
