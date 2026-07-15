"""Tests for the simple anchor-date before/after paired-input layer (WP03).

These exercise the narrow preparation seam ``paired_t_test`` (WP04) needs before
any paired estimate can run: one already-admitted single-series
:class:`AnalyticalInputSeries` plus a caller-declared
:class:`BeforeAfterPairedRequest` (metric, anchor date, before/after windows, and
expected direction) becomes an ordered, span-narrowed
:class:`BeforeAfterPairedInput` — or a first-class :class:`RefusalOutcome` with
**no** pairs. This layer produces a *prepared pair set or a refusal*, never an
estimate; the mean paired difference, uncertainty, and envelope are WP04's job.

The fixed deterministic pairing rule under test (also stated in the module
docstring/data-model):

* The anchor is a local calendar date ``D``. The before window is the
  ``before_days`` local calendar days strictly before ``D``; the after window is
  the ``after_days`` local calendar days strictly after ``D``. The anchor day
  itself belongs to neither side.
* Within each window observations are keyed to their *local* calendar day
  (last-write-wins per day, mirroring the correlate preparer), so a day never
  contributes twice.
* Pairs are formed **nearest-to-anchor outward**: the before observation closest
  to the anchor is matched with the after observation closest to the anchor, the
  second-closest before with the second-closest after, and so on. ``pair_index``
  is the rank from the anchor outward (0 = closest). The number of pairs is the
  minimum of the usable before-day count and the usable after-day count; surplus
  observations on the longer side are unused (never invented to fill a pair).

Everything is fixture-backed (hand-built ``PreparedPoint`` series via the WP02
single-series preparer); the layer reads no warehouse, so nothing here touches
SQL, DuckDB, MCP, the network, or a clock. The tests deliberately do **not**
depend on the eventual paired t-test — WP03 stops at a validated paired bundle.
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
from premura.engine.paired_inputs import (
    BEFORE_AFTER_MIN_PAIRS,
    MAX_WINDOW_DAYS,
    BeforeAfterDirection,
    BeforeAfterPair,
    BeforeAfterPairedInput,
    BeforeAfterPairedRequest,
    BeforeAfterPairRefusalReason,
    before_after_pairs_for_computation,
    prepare_before_after_paired_input,
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
# Fixture-backed evidence helpers (mirror the single-series / correlate style)
# ---------------------------------------------------------------------------


def _policy(metric: str, *, min_observations: int = 1) -> MetricFamilyPolicy:
    """A family policy that admits the paired-difference question for ``metric``."""
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


def _point(
    day: date,
    value: float,
    *,
    hour: int = 12,
    imputed: bool = False,
    local_tz: str | None = None,
) -> PreparedPoint:
    """One point at ``day`` at local noon (so local-day keying is unambiguous)."""
    return PreparedPoint(
        ts=datetime(day.year, day.month, day.day, hour, 0, 0),
        value=value,
        is_imputed=imputed,
        local_tz=local_tz,
    )


def _series(points: list[PreparedPoint], *, min_observations: int = 1) -> AnalyticalInputSeries:
    """Prepare a usable single-series input through the shared preparer."""
    return prepare_input_series(
        METRIC,
        AnalyticalQuestionType.PAIRED_DIFFERENCE,
        candidate=_candidate(METRIC, point_count=len(points)),
        policies=_policy(METRIC, min_observations=min_observations),
        points=points,
        reference_time=REFERENCE,
        freshness_status="fresh",
    )


def _request(
    *,
    anchor: date | None = ANCHOR,
    before_days: int = 5,
    after_days: int = 5,
    direction: BeforeAfterDirection | None = BeforeAfterDirection.INCREASE,
) -> BeforeAfterPairedRequest:
    return BeforeAfterPairedRequest(
        metric_id=METRIC,
        anchor_date=anchor,  # type: ignore[arg-type]
        before_days=before_days,
        after_days=after_days,
        expected_direction=direction,  # type: ignore[arg-type]
    )


def _symmetric_series(
    *,
    before_count: int,
    after_count: int,
    before_base: float = 50.0,
    after_base: float = 60.0,
    imputed_days: tuple[date, ...] = (),
) -> AnalyticalInputSeries:
    """A series with ``before_count`` days before the anchor and ``after_count`` after.

    Before days run …, D-2, D-1 (closest to anchor last); after days run D+1,
    D+2, … (closest to anchor first). The anchor day itself is skipped.
    """
    points: list[PreparedPoint] = []
    for i in range(before_count, 0, -1):
        day = ANCHOR - timedelta(days=i)
        points.append(_point(day, before_base, imputed=day in imputed_days))
    for i in range(1, after_count + 1):
        day = ANCHOR + timedelta(days=i)
        points.append(_point(day, after_base, imputed=day in imputed_days))
    return _series(points)


# ===========================================================================
# T011 — happy-path: deterministic anchor-date pairing
# ===========================================================================


def test_balanced_windows_build_nearest_to_anchor_pairs() -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    request = _request(before_days=8, after_days=8)

    prepared = prepare_before_after_paired_input(series, request)

    assert prepared.refusal is None
    assert prepared.is_usable
    assert prepared.raw_pair_count == 8
    assert len(prepared.pairs) == 8
    # Pair 0 is the nearest-to-anchor pair: before day D-1, after day D+1.
    first = prepared.pairs[0]
    assert first.pair_index == 0
    assert first.before_day == ANCHOR - timedelta(days=1)
    assert first.after_day == ANCHOR + timedelta(days=1)
    assert first.before_ts.date() == ANCHOR - timedelta(days=1)
    assert first.after_ts.date() == ANCHOR + timedelta(days=1)
    # difference = after - before
    assert first.difference == pytest.approx(first.after_value - first.before_value)
    assert first.difference == pytest.approx(10.0)
    # Pair indices are a deterministic 0..n-1 run.
    assert [p.pair_index for p in prepared.pairs] == list(range(8))
    # Window spans reflect the *actual* paired days used.
    assert prepared.before_window_start == ANCHOR - timedelta(days=8)
    assert prepared.before_window_end == ANCHOR - timedelta(days=1)
    assert prepared.after_window_start == ANCHOR + timedelta(days=1)
    assert prepared.after_window_end == ANCHOR + timedelta(days=8)
    assert prepared.is_imputed_pct == pytest.approx(0.0)


def test_span_metadata_uses_local_days_when_utc_dates_differ() -> None:
    """Reported spans must match the local calendar days used for pairing."""
    points: list[PreparedPoint] = []
    for i in range(8, 0, -1):
        local_day = ANCHOR - timedelta(days=i)
        utc_day = local_day + timedelta(days=1)
        points.append(_point(utc_day, 50.0 + i, hour=2, local_tz="-05:00"))
    for i in range(1, 9):
        local_day = ANCHOR + timedelta(days=i)
        utc_day = local_day + timedelta(days=1)
        points.append(_point(utc_day, 60.0 + i, hour=2, local_tz="-05:00"))
    series = _series(points)

    prepared = prepare_before_after_paired_input(series, _request(before_days=8, after_days=8))

    assert prepared.refusal is None
    assert prepared.before_window_start == ANCHOR - timedelta(days=8)
    assert prepared.before_window_end == ANCHOR - timedelta(days=1)
    assert prepared.after_window_start == ANCHOR + timedelta(days=1)
    assert prepared.after_window_end == ANCHOR + timedelta(days=8)
    first = prepared.pairs[0]
    assert first.before_day == ANCHOR - timedelta(days=1)
    assert first.after_day == ANCHOR + timedelta(days=1)
    # The raw UTC dates differ from the local days; this guards against using
    # timestamp.date() for user-facing span metadata.
    assert first.before_ts.date() == ANCHOR
    assert first.after_ts.date() == ANCHOR + timedelta(days=2)


def test_pairs_carry_imputation_flags_and_pct() -> None:
    imputed = (ANCHOR - timedelta(days=1), ANCHOR + timedelta(days=2))
    series = _symmetric_series(before_count=8, after_count=8, imputed_days=imputed)
    request = _request(before_days=8, after_days=8)

    prepared = prepare_before_after_paired_input(series, request)

    assert prepared.refusal is None
    # Pair 0 (before D-1) has its before side imputed.
    assert prepared.pairs[0].before_is_imputed is True
    assert prepared.pairs[0].after_is_imputed is False
    # Exactly two of eight pairs touch an imputed side -> 25%.
    imputed_pairs = sum(1 for p in prepared.pairs if p.before_is_imputed or p.after_is_imputed)
    assert imputed_pairs == 2
    assert prepared.is_imputed_pct == pytest.approx(25.0)


def test_uneven_windows_pair_only_the_shorter_side_count() -> None:
    # 10 before days, 8 after days -> 8 pairs (the shorter side); 2 before days
    # furthest from the anchor are unused. Never invent a pair to fill the gap.
    series = _symmetric_series(before_count=10, after_count=8)
    request = _request(before_days=10, after_days=10)

    prepared = prepare_before_after_paired_input(series, request)

    assert prepared.refusal is None
    assert prepared.raw_pair_count == 8
    # The unused before days are the two furthest from the anchor.
    used_before_days = {p.before_ts.date() for p in prepared.pairs}
    assert ANCHOR - timedelta(days=10) not in used_before_days
    assert ANCHOR - timedelta(days=9) not in used_before_days
    assert ANCHOR - timedelta(days=1) in used_before_days


def test_observations_outside_the_declared_windows_are_ignored() -> None:
    # Build 8/8 inside the windows, plus stray points far outside before_days/
    # after_days that must not be paired.
    series = _symmetric_series(before_count=8, after_count=8)
    extra = list(series.points)
    extra.append(_point(ANCHOR - timedelta(days=40), 1.0))
    extra.append(_point(ANCHOR + timedelta(days=40), 99.0))
    wide_series = _series(sorted(extra, key=lambda p: p.ts))
    request = _request(before_days=8, after_days=8)

    prepared = prepare_before_after_paired_input(wide_series, request)

    assert prepared.refusal is None
    assert prepared.raw_pair_count == 8
    days = {p.before_ts.date() for p in prepared.pairs} | {
        p.after_ts.date() for p in prepared.pairs
    }
    assert ANCHOR - timedelta(days=40) not in days
    assert ANCHOR + timedelta(days=40) not in days


def test_anchor_day_observation_is_excluded_from_both_sides() -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    extra = list(series.points)
    extra.append(_point(ANCHOR, 500.0))  # the anchor day itself
    with_anchor = _series(sorted(extra, key=lambda p: p.ts))
    request = _request(before_days=8, after_days=8)

    prepared = prepare_before_after_paired_input(with_anchor, request)

    assert prepared.refusal is None
    assert prepared.raw_pair_count == 8
    all_days = {p.before_ts.date() for p in prepared.pairs} | {
        p.after_ts.date() for p in prepared.pairs
    }
    assert ANCHOR not in all_days


def test_preparation_is_deterministic() -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    request = _request(before_days=8, after_days=8)
    a = prepare_before_after_paired_input(series, request)
    b = prepare_before_after_paired_input(series, request)
    assert a.to_dict() == b.to_dict()


# ===========================================================================
# T012 — refusals: malformed requests and weak pairs (no estimate)
# ===========================================================================


def test_refuses_when_input_series_already_refused() -> None:
    # A series too sparse for its own admissibility policy is already refused.
    refused = _series([_point(ANCHOR - timedelta(days=1), 1.0)], min_observations=99)
    assert refused.refusal is not None  # precondition

    prepared = prepare_before_after_paired_input(refused, _request())

    assert prepared.refusal is not None
    assert prepared.pairs == ()
    assert prepared.raw_pair_count == 0
    # Propagates the upstream admissibility reason verbatim.
    assert prepared.refusal.reason == refused.refusal.reason


def test_refuses_missing_anchor_date() -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    prepared = prepare_before_after_paired_input(series, _request(anchor=None))
    assert prepared.refusal is not None
    assert prepared.refusal.reason == BeforeAfterPairRefusalReason.MISSING_ANCHOR_DATE.value
    assert prepared.pairs == ()


def test_refuses_non_date_anchor() -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    bad = _request()
    object.__setattr__(bad, "anchor_date", "2026-05-14")  # a string, not a date
    prepared = prepare_before_after_paired_input(series, bad)
    assert prepared.refusal is not None
    assert prepared.refusal.reason == BeforeAfterPairRefusalReason.MISSING_ANCHOR_DATE.value


@pytest.mark.parametrize("before_days", [0, -1, MAX_WINDOW_DAYS + 1])
def test_refuses_out_of_bounds_before_days(before_days: int) -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    prepared = prepare_before_after_paired_input(series, _request(before_days=before_days))
    assert prepared.refusal is not None
    assert prepared.refusal.reason == BeforeAfterPairRefusalReason.UNSUPPORTED_WINDOW.value
    assert prepared.refusal.parameter_name == "before_days"


@pytest.mark.parametrize("after_days", [0, -1, MAX_WINDOW_DAYS + 1])
def test_refuses_out_of_bounds_after_days(after_days: int) -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    prepared = prepare_before_after_paired_input(series, _request(after_days=after_days))
    assert prepared.refusal is not None
    assert prepared.refusal.reason == BeforeAfterPairRefusalReason.UNSUPPORTED_WINDOW.value
    assert prepared.refusal.parameter_name == "after_days"


def test_refuses_missing_expected_direction() -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    prepared = prepare_before_after_paired_input(series, _request(direction=None))
    assert prepared.refusal is not None
    assert prepared.refusal.reason == BeforeAfterPairRefusalReason.MISSING_DIRECTION.value


def test_refuses_unknown_expected_direction() -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    bad = _request()
    object.__setattr__(bad, "expected_direction", "sideways")
    prepared = prepare_before_after_paired_input(series, bad)
    assert prepared.refusal is not None
    assert prepared.refusal.reason == BeforeAfterPairRefusalReason.MISSING_DIRECTION.value


def test_refuses_no_values_before_the_anchor() -> None:
    # Only after-side observations exist.
    series = _symmetric_series(before_count=0, after_count=10)
    prepared = prepare_before_after_paired_input(series, _request(before_days=8, after_days=10))
    assert prepared.refusal is not None
    assert prepared.refusal.reason == BeforeAfterPairRefusalReason.NO_VALID_PAIRS.value
    assert prepared.pairs == ()


def test_refuses_no_values_after_the_anchor() -> None:
    series = _symmetric_series(before_count=10, after_count=0)
    prepared = prepare_before_after_paired_input(series, _request(before_days=10, after_days=8))
    assert prepared.refusal is not None
    assert prepared.refusal.reason == BeforeAfterPairRefusalReason.NO_VALID_PAIRS.value


def test_refuses_too_few_valid_pairs() -> None:
    # Below the WP01 raw-pair floor (BEFORE_AFTER_MIN_PAIRS == 8).
    series = _symmetric_series(before_count=4, after_count=4)
    prepared = prepare_before_after_paired_input(series, _request(before_days=8, after_days=8))
    assert prepared.refusal is not None
    assert prepared.refusal.reason == BeforeAfterPairRefusalReason.TOO_FEW_PAIRS.value
    assert prepared.refusal.parameter_name == "min_pairs"
    assert prepared.pairs == ()


def test_exactly_floor_pairs_is_usable() -> None:
    # Exactly BEFORE_AFTER_MIN_PAIRS pairs is admitted (boundary is inclusive).
    series = _symmetric_series(
        before_count=BEFORE_AFTER_MIN_PAIRS, after_count=BEFORE_AFTER_MIN_PAIRS
    )
    prepared = prepare_before_after_paired_input(
        series, _request(before_days=BEFORE_AFTER_MIN_PAIRS, after_days=BEFORE_AFTER_MIN_PAIRS)
    )
    assert prepared.refusal is None
    assert prepared.raw_pair_count == BEFORE_AFTER_MIN_PAIRS


def test_refuses_metric_mismatch_between_request_and_series() -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    bad = BeforeAfterPairedRequest(
        metric_id="some_other_metric",
        anchor_date=ANCHOR,
        before_days=8,
        after_days=8,
        expected_direction=BeforeAfterDirection.INCREASE,
    )
    prepared = prepare_before_after_paired_input(series, bad)
    assert prepared.refusal is not None
    assert prepared.refusal.reason == BeforeAfterPairRefusalReason.INVALID_REQUEST.value


def test_points_for_computation_raises_on_refused_input() -> None:
    series = _symmetric_series(before_count=4, after_count=4)
    prepared = prepare_before_after_paired_input(series, _request(before_days=8, after_days=8))
    assert prepared.refusal is not None
    with pytest.raises(RuntimeError):
        before_after_pairs_for_computation(prepared)


def test_points_for_computation_returns_pairs_when_usable() -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    prepared = prepare_before_after_paired_input(series, _request(before_days=8, after_days=8))
    pairs = before_after_pairs_for_computation(prepared)
    assert pairs == prepared.pairs
    assert len(pairs) == 8


# ===========================================================================
# T015 — out-of-scope guardrails: no condition pairing / scanning
# ===========================================================================


def test_request_rejects_condition_label_kwarg() -> None:
    # The request shape carries no condition_label parameter at all.
    with pytest.raises(TypeError):
        BeforeAfterPairedRequest(  # type: ignore[call-arg]
            metric_id=METRIC,
            anchor_date=ANCHOR,
            before_days=8,
            after_days=8,
            expected_direction=BeforeAfterDirection.INCREASE,
            condition_label="post_surgery",
        )


def test_request_rejects_candidate_anchor_list_kwarg() -> None:
    with pytest.raises(TypeError):
        BeforeAfterPairedRequest(  # type: ignore[call-arg]
            metric_id=METRIC,
            anchor_dates=[ANCHOR, ANCHOR + timedelta(days=1)],
            before_days=8,
            after_days=8,
            expected_direction=BeforeAfterDirection.INCREASE,
        )


def test_request_rejects_window_list_kwarg() -> None:
    with pytest.raises(TypeError):
        BeforeAfterPairedRequest(  # type: ignore[call-arg]
            metric_id=METRIC,
            anchor_date=ANCHOR,
            before_days_options=[3, 5, 7],
            after_days=8,
            expected_direction=BeforeAfterDirection.INCREASE,
        )


def test_request_rejects_arbitrary_pair_map_kwarg() -> None:
    with pytest.raises(TypeError):
        BeforeAfterPairedRequest(  # type: ignore[call-arg]
            metric_id=METRIC,
            anchor_date=ANCHOR,
            before_days=8,
            after_days=8,
            expected_direction=BeforeAfterDirection.INCREASE,
            pair_map={"a": "b"},
        )


def test_preparer_rejects_extra_positional_or_keyword_scan_args() -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    request = _request(before_days=8, after_days=8)
    # A "best split" / scan flag is not part of the supported surface.
    prepared = prepare_before_after_paired_input(series, request, choose_best_split=True)
    assert prepared.refusal is not None
    assert prepared.refusal.reason == BeforeAfterPairRefusalReason.UNSUPPORTED_REQUEST.value


def test_direction_vocabulary_is_closed() -> None:
    assert {d.value for d in BeforeAfterDirection} == {"increase", "decrease"}


def test_direct_pair_construction_rejects_non_finite_values() -> None:
    # Direct construction of a shape with a bad value is a programming error.
    with pytest.raises(ValueError):
        BeforeAfterPair(
            pair_index=0,
            before_day=date(2026, 5, 13),
            after_day=date(2026, 5, 15),
            before_ts=datetime(2026, 5, 13, 12),
            after_ts=datetime(2026, 5, 15, 12),
            before_value=float("nan"),
            after_value=10.0,
        )


def test_direct_refused_input_rejects_carrying_pairs() -> None:
    # A refused BeforeAfterPairedInput must not carry computation-ready pairs.
    pair = BeforeAfterPair(
        pair_index=0,
        before_day=date(2026, 5, 13),
        after_day=date(2026, 5, 15),
        before_ts=datetime(2026, 5, 13, 12),
        after_ts=datetime(2026, 5, 15, 12),
        before_value=1.0,
        after_value=2.0,
    )
    with pytest.raises(ValueError):
        BeforeAfterPairedInput(
            metric_id=METRIC,
            request=_request(),
            pairs=(pair,),
            refusal=RefusalOutcome(reason="x", message="y"),
        )


# A small sanity check that the prepared input never carries an estimate-shaped
# field — this layer prepares pairs, the paired t-test (WP04) computes the mean.
def test_prepared_input_has_no_estimate_field() -> None:
    series = _symmetric_series(before_count=8, after_count=8)
    prepared = prepare_before_after_paired_input(series, _request(before_days=8, after_days=8))
    payload = prepared.to_dict()
    for forbidden in ("mean_difference", "estimate", "p_value", "uncertainty"):
        assert forbidden not in payload
