"""Tests for the deterministic ``correlate`` lagged-association engine tool (WP03).

The tool consumes a WP02 :class:`PairedAnalyticalInput` (two already-admitted
single series aligned by same local calendar day after one declared integer-day
lag) plus the pre-registered hypothesis, and returns an
:class:`AnalyticalResultEnvelope`: an available association estimate (Spearman's
rho, an honest *association band* widened for autocorrelation, raw and effective
sample counts, direction alignment, a closed-vocabulary confound checklist) or a
first-class refusal carrying **no** estimate.

Everything is fixture-backed; the tool reads no warehouse and touches no clock,
no network, no DuckDB, no MCP. These tests are the observable behavior contract
(T011) and the honesty boundary (T016): the tool must NEVER compute or return a
p-value, the word "significant", causal language, a diagnosis, or perform a lag
scan (ADR-0008).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from premura.engine.analytical_contract import (
    REGISTRY,
    AnalyticalQuestionType,
    AnalyticalResultEnvelope,
    AnalyticalStatus,
    ConfoundKey,
    RefusalOutcome,
    dispatch,
)
from premura.engine.analytical_inputs import (
    AnalyticalInputSeries,
    ExpectedDirection,
    PairedAnalyticalInput,
    PreparedPoint,
    PreRegisteredAssociationHypothesis,
    prepare_input_series,
    prepare_paired_input,
)
from premura.engine.analytical_tools import CORRELATE_TOOL, correlate
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
LEFT_METRIC = "resting_heart_rate"
RIGHT_METRIC = "hrv_overnight"
LEFT_FAMILY = "left_family"
RIGHT_FAMILY = "right_family"


# ---------------------------------------------------------------------------
# Fixture helpers (mirror the WP02 paired-input test style)
# ---------------------------------------------------------------------------


def _policy(family: str, metric: str, *, min_observations: int = 1) -> MetricFamilyPolicy:
    rule = QuestionRule(
        admissibility=Admissibility.ADMISSIBLE,
        freshness=FreshnessRule(mode=FreshnessMode.CAVEAT_ONLY),
        sufficiency=SufficiencyRule(
            min_observations=min_observations,
            missing_data_behavior=MissingDataBehavior.REJECT,
        ),
    )
    return MetricFamilyPolicy(
        policy_id=f"{family}@1",
        version=1,
        metric_family=family,
        policy_shape=PolicyShape.ROLLING_RECENT_PATTERN,
        temporal_meaning=TemporalMeaning.ROLLING_RECENT_PATTERN,
        question_rules={QuestionType.LAGGED_ASSOCIATION: rule},
        applies_to_metrics=(metric,),
    )


def _candidate(metric: str, family: str, *, point_count: int) -> EvidenceCandidate:
    return EvidenceCandidate(
        metric_id=metric,
        metric_family=family,
        value_kind="aggregate",
        observed_at=REFERENCE,
        source_id="fixture",
        point_count=point_count,
    )


def _series_from_values(
    metric: str,
    family: str,
    values: list[float],
    *,
    start: datetime,
    imputed_idx: tuple[int, ...] = (),
) -> AnalyticalInputSeries:
    """Build a usable single series with one point per consecutive calendar day."""
    points = [
        PreparedPoint(ts=start + timedelta(days=i), value=v, is_imputed=i in imputed_idx)
        for i, v in enumerate(values)
    ]
    return prepare_input_series(
        metric,
        AnalyticalQuestionType.LAGGED_ASSOCIATION,
        candidate=_candidate(metric, family, point_count=len(points)),
        policies=_policy(family, metric),
        points=points,
        reference_time=REFERENCE,
    )


def _hypothesis(**overrides) -> PreRegisteredAssociationHypothesis:
    base = dict(
        left_metric_id=LEFT_METRIC,
        right_metric_id=RIGHT_METRIC,
        lag_days=0,
        expected_direction=ExpectedDirection.POSITIVE,
    )
    base.update(overrides)
    return PreRegisteredAssociationHypothesis(**base)


def _paired_from_values(
    left_values: list[float],
    right_values: list[float],
    *,
    lag_days: int = 0,
    expected_direction: ExpectedDirection = ExpectedDirection.POSITIVE,
    left_imputed_idx: tuple[int, ...] = (),
    right_imputed_idx: tuple[int, ...] = (),
    common_cause_candidates: tuple[str, ...] = (),
    lag_justification: str | None = None,
    start: datetime | None = None,
) -> PairedAnalyticalInput:
    """Prepare a paired input from two raw value lists through the WP02 preparer.

    ``left`` and ``right`` share the same start day so a lag-0 hypothesis pairs
    every index. For a positive ``lag_days`` the right series is constructed one
    declared lag later so it re-aligns onto the left day under ``correlate``.
    """
    n = len(left_values)
    assert len(right_values) == n, "left/right value lists must be equal length"
    start = start or (REFERENCE - timedelta(days=n - 1))
    left = _series_from_values(
        LEFT_METRIC, LEFT_FAMILY, left_values, start=start, imputed_idx=left_imputed_idx
    )
    right_start = start + timedelta(days=lag_days)
    right = _series_from_values(
        RIGHT_METRIC, RIGHT_FAMILY, right_values, start=right_start, imputed_idx=right_imputed_idx
    )
    hypothesis = _hypothesis(
        lag_days=lag_days,
        expected_direction=expected_direction,
        common_cause_candidates=common_cause_candidates,
        lag_justification=lag_justification,
    )
    return prepare_paired_input(left, right, hypothesis)


# A deterministic, LOW-autocorrelation sequence (a fixed pseudo-random shuffle of
# 0..n-1). Used identically for both sides it gives a clean monotone association
# (Spearman rho = +-1) while the rank series carries little serial correlation, so
# the effective sample size stays above the floor and an available estimate is
# produced. A pure monotone ramp is instead maximally autocorrelated and is
# exercised by the refusal/N_eff tests, where N_eff correctly collapses.
def _low_autocorr(n: int, *, sign: float = 1.0, seed: int = 12345) -> list[float]:
    import random

    rng = random.Random(seed)
    vals = list(range(n))
    rng.shuffle(vals)
    return [sign * float(v) for v in vals]


# left "up-ish", right "down-ish": a clean NEGATIVE association (Spearman
# rho = -1) with low rank autocorrelation, so it stays available.
def _negative_monotone(n: int) -> tuple[list[float], list[float]]:
    left = _low_autocorr(n, sign=1.0)
    right = _low_autocorr(n, sign=-1.0)
    return left, right


# ===========================================================================
# T011 — available correlate output (lag 1, expected negative direction)
# ===========================================================================


def test_available_negative_association_at_lag_one() -> None:
    left, right = _negative_monotone(30)
    paired = _paired_from_values(
        left, right, lag_days=1, expected_direction=ExpectedDirection.NEGATIVE
    )
    assert paired.is_usable

    env = correlate(paired, _hypothesis(lag_days=1, expected_direction=ExpectedDirection.NEGATIVE))
    assert isinstance(env, AnalyticalResultEnvelope)
    assert env.status is AnalyticalStatus.AVAILABLE
    assert env.tool_name == CORRELATE_TOOL
    env.validate()  # contract invariants hold

    data = env.to_dict()
    est = data["estimate"]
    # Spearman rho of a strictly negative monotone is exactly -1.
    assert est["coefficient"] == pytest.approx(-1.0)
    assert est["coefficient_method"] == "spearman_rho"
    assert est["observed_direction"] == "negative"
    assert est["expected_direction"] == "negative"
    assert est["direction_matches_hypothesis"] is True
    assert est["lag_days"] == 1
    assert "method_revision" in est

    # Required serialized keys.
    assert data["tool_name"] == "correlate"
    assert data["inputs"] == [LEFT_METRIC, RIGHT_METRIC]
    assert data["parameters"]["lag_days"] == 1
    assert data["parameters"]["expected_direction"] == "negative"
    # Raw paired count is the envelope's sample_size; the effective sample size
    # lives in the estimate (and the uncertainty payload), since the shared
    # AnalyticalResultEnvelope has no separate effective-sample field.
    assert data["sample_size"] == 30
    assert est["raw_paired_sample_size"] == 30
    assert est["effective_sample_size"] is not None
    assert data["uncertainty"]["payload"]["effective_sample_size"] == est["effective_sample_size"]
    # Association band: present, ordered, bounded in [-1, 1], NOT called a CI.
    band = est["association_band"]
    assert -1.0 <= band["lower"] <= band["upper"] <= 1.0
    assert data["is_imputed_pct"] == 0.0
    # Paired overlap metadata is carried (in parameters) for narration.
    assert data["parameters"]["overlap_start"] is not None
    assert data["parameters"]["overlap_end"] is not None
    assert data["validity_status"] is not None
    # Confound checklist is a list (possibly with low_sample_size for 30 pairs).
    assert isinstance(data["confound_checklist"], list)


def test_positive_monotone_matches_positive_hypothesis() -> None:
    base = _low_autocorr(30)
    left = base
    right = [2.0 * v for v in base]  # same ranks -> rho +1, low autocorrelation
    paired = _paired_from_values(left, right, expected_direction=ExpectedDirection.POSITIVE)
    env = correlate(paired, _hypothesis(expected_direction=ExpectedDirection.POSITIVE))
    assert env.status is AnalyticalStatus.AVAILABLE
    est = env.to_dict()["estimate"]
    assert est["coefficient"] == pytest.approx(1.0)
    assert est["observed_direction"] == "positive"
    assert est["direction_matches_hypothesis"] is True


def test_observed_direction_can_mismatch_expected() -> None:
    # Observed positive association, but caller pre-registered a negative expectation.
    base = _low_autocorr(30)
    paired = _paired_from_values(base, base, expected_direction=ExpectedDirection.NEGATIVE)
    env = correlate(paired, _hypothesis(expected_direction=ExpectedDirection.NEGATIVE))
    assert env.status is AnalyticalStatus.AVAILABLE
    est = env.to_dict()["estimate"]
    assert est["coefficient"] == pytest.approx(1.0)
    assert est["observed_direction"] == "positive"
    assert est["expected_direction"] == "negative"
    assert est["direction_matches_hypothesis"] is False


def test_ties_use_midranks_deterministically() -> None:
    # Left has a tied block; midrank handling must be deterministic. Two repeated
    # invocations must produce byte-identical envelopes. Build a low-autocorrelation
    # right series so the pair stays available despite the ties.
    tail = _low_autocorr(25, sign=1.0)
    # Shift the tail above the tied block's value range so the tie stays a tie.
    left = [-1.0, -1.0, -1.0] + [v + 100.0 for v in tail]
    right = _low_autocorr(len(left), sign=1.0, seed=999)
    paired = _paired_from_values(left, right)
    assert paired.is_usable
    a = correlate(paired, _hypothesis()).to_dict()
    b = correlate(paired, _hypothesis()).to_dict()
    assert a == b
    # rho is well-defined and finite (no NaN) despite ties.
    assert a["status"] == "available"
    assert -1.0 <= a["estimate"]["coefficient"] <= 1.0


# ===========================================================================
# DRIFT-1 — UTC-fallback caveat is surfaced honestly in the correlate envelope
# ===========================================================================


def _series_with_tz(
    metric: str,
    family: str,
    values: list[float],
    *,
    start: datetime,
    local_tz: str | None,
) -> AnalyticalInputSeries:
    points = [
        PreparedPoint(ts=start + timedelta(days=i), value=v, local_tz=local_tz)
        for i, v in enumerate(values)
    ]
    return prepare_input_series(
        metric,
        AnalyticalQuestionType.LAGGED_ASSOCIATION,
        candidate=_candidate(metric, family, point_count=len(points)),
        policies=_policy(family, metric),
        points=points,
        reference_time=REFERENCE,
    )


def test_utc_fallback_caveat_emitted_when_local_tz_missing() -> None:
    # Both series lack a local_tz -> every paired day falls back to the UTC day,
    # and correlate must surface that honestly as a caveat (not a new confound key).
    left, right = _negative_monotone(30)
    start = REFERENCE - timedelta(days=29)
    left_series = _series_with_tz(LEFT_METRIC, LEFT_FAMILY, left, start=start, local_tz=None)
    right_series = _series_with_tz(RIGHT_METRIC, RIGHT_FAMILY, right, start=start, local_tz=None)
    paired = prepare_paired_input(
        left_series, right_series, _hypothesis(expected_direction=ExpectedDirection.NEGATIVE)
    )
    assert paired.source_summary["utc_fallback_paired_days"] == 30

    env = correlate(paired, _hypothesis(expected_direction=ExpectedDirection.NEGATIVE))
    assert env.status is AnalyticalStatus.AVAILABLE
    caveats = env.to_dict()["caveats"]
    assert any("fell back to UTC" in c and "30 of 30" in c for c in caveats)
    # The fallback is a caveat, NOT a confound-checklist key.
    keys = {c["key"] for c in env.to_dict()["confound_checklist"]}
    assert all("utc" not in k.lower() for k in keys)


def test_no_utc_fallback_caveat_when_local_tz_present() -> None:
    # Real offsets on both series -> no fallback, so the fallback caveat is absent.
    left, right = _negative_monotone(30)
    start = REFERENCE - timedelta(days=29)
    left_series = _series_with_tz(LEFT_METRIC, LEFT_FAMILY, left, start=start, local_tz="+02:00")
    right_series = _series_with_tz(
        RIGHT_METRIC, RIGHT_FAMILY, right, start=start, local_tz="+02:00"
    )
    paired = prepare_paired_input(
        left_series, right_series, _hypothesis(expected_direction=ExpectedDirection.NEGATIVE)
    )
    assert paired.source_summary["utc_fallback_paired_days"] == 0

    env = correlate(paired, _hypothesis(expected_direction=ExpectedDirection.NEGATIVE))
    assert env.status is AnalyticalStatus.AVAILABLE
    caveats = env.to_dict()["caveats"]
    assert not any("fell back to UTC" in c for c in caveats)


# ===========================================================================
# T011 — core refusal classes (refusals carry no estimate)
# ===========================================================================


def _assert_refusal(env: AnalyticalResultEnvelope, *, reason: str | None = None) -> None:
    assert env.status is AnalyticalStatus.REFUSED
    data = env.to_dict()
    assert data["estimate"] is None
    assert data["refusal"] is not None
    if reason is not None:
        assert data["refusal"]["reason"] == reason


def test_refuses_below_twenty_raw_pairs() -> None:
    # 15 raw pairs is below the floor of 20: WP02 already refuses, and correlate
    # must surface that refusal with no estimate.
    left = [float(i) for i in range(15)]
    right = [float(i) for i in range(15)]
    paired = _paired_from_values(left, right)
    assert not paired.is_usable  # WP02 floor
    env = correlate(paired, _hypothesis())
    _assert_refusal(env)


def _near_random_walk_pair(n: int, *, seed: int = 42) -> tuple[list[float], list[float]]:
    """A deterministic strongly-autocorrelated near-random-walk pair.

    Each side is a cumulative sum of small bounded steps, so consecutive days are
    highly serially correlated (rank autocorrelation stays high) while the two
    sides are NOT constant — exactly the regime where the raw paired count is fine
    (N >= 20) but the *independent* information is scarce (N_eff < 12). Built from
    a fixed seed so the fixture is byte-stable across runs.
    """
    import random

    rng = random.Random(seed)
    left: list[float] = []
    right: list[float] = []
    lv = 0.0
    rv = 0.0
    for _ in range(n):
        lv += rng.uniform(-1.0, 1.0)
        rv += rng.uniform(-1.0, 1.0)
        left.append(lv)
        right.append(rv)
    return left, right


def test_refuses_below_effective_sample_floor() -> None:
    # RISK-1: lock FR-010. A strongly autocorrelated near-random-walk pair has
    # raw N = 30 (>= 20, clearing the raw floor and reaching the tool) but drives
    # the effective sample size below 12. The tool MUST refuse with the
    # effective-sample-floor reason and carry no estimate. This test fails if the
    # refusal is removed (it does not accept an available-with-confound fallback).
    n = 30
    left, right = _near_random_walk_pair(n)
    paired = _paired_from_values(left, right)
    assert paired.is_usable  # raw paired floor (>= 20) is met -> reaches the tool

    env = correlate(paired, _hypothesis())
    assert env.status is AnalyticalStatus.REFUSED
    _assert_refusal(env, reason="insufficient_effective_sample")
    # The refusal carries no estimate and the effective sample really is < 12.
    data = env.to_dict()
    assert data["estimate"] is None
    # Sanity: the raw paired count cleared the floor, so this is genuinely an
    # N_eff refusal and not the raw-floor path.
    assert paired.overlap_sample_size >= 20


def test_refuses_constant_series() -> None:
    # A constant right series has no rank variation -> refuse, never a fake zero.
    left = [float(i) for i in range(25)]
    right = [7.0] * 25
    paired = _paired_from_values(left, right)
    env = correlate(paired, _hypothesis())
    _assert_refusal(env)
    assert env.to_dict()["estimate"] is None


def test_refuses_malformed_hypothesis_metric_mismatch() -> None:
    # The hypothesis must describe the same metric pair as the paired input.
    left = [float(i) for i in range(25)]
    right = [float(i) for i in range(25)]
    paired = _paired_from_values(left, right)
    bad = _hypothesis(left_metric_id="something_else")
    env = correlate(paired, bad)
    _assert_refusal(env)


def test_refuses_refused_paired_input() -> None:
    # A paired input that WP02 already refused must short-circuit to a refusal.
    refused = PairedAnalyticalInput(
        left_metric_id=LEFT_METRIC,
        right_metric_id=RIGHT_METRIC,
        question_type=AnalyticalQuestionType.LAGGED_ASSOCIATION,
        refusal=RefusalOutcome(
            reason="no_paired_overlap",
            message="no overlap after lag",
        ),
    )
    env = correlate(refused, _hypothesis())
    _assert_refusal(env)
    assert env.to_dict()["estimate"] is None


# ===========================================================================
# T013 — N_eff + association band behavior
# ===========================================================================


def _moderate_autocorr(n: int, *, seed: int = 7) -> list[float]:
    """An AR(1)-like sequence: more serial correlation than ``_low_autocorr`` but
    still enough independent information to clear the effective-sample floor."""
    import random

    rng = random.Random(seed)
    out: list[float] = []
    x = 0.0
    for _ in range(n):
        x = 0.7 * x + rng.uniform(-1.0, 1.0)
        out.append(x)
    return out


def test_autocorrelated_series_has_lower_neff_and_wider_band() -> None:
    # Two paired inputs with the SAME (perfect) rho but different rank-series
    # autocorrelation. The more autocorrelated one must have a LOWER effective
    # sample size and a WIDER association band — switching to ranks does not fix
    # autocorrelation, so the band widens regardless.
    n = 60

    low = _low_autocorr(n)
    moderate = _moderate_autocorr(n)

    env_low = correlate(_paired_from_values(low, low), _hypothesis())
    env_mod = correlate(_paired_from_values(moderate, moderate), _hypothesis())

    assert env_low.status is AnalyticalStatus.AVAILABLE
    assert env_mod.status is AnalyticalStatus.AVAILABLE

    neff_low = env_low.to_dict()["estimate"]["effective_sample_size"]
    neff_mod = env_mod.to_dict()["estimate"]["effective_sample_size"]
    # The more-autocorrelated series carries less independent information.
    assert neff_mod < neff_low <= n

    def band_width(env: AnalyticalResultEnvelope) -> float:
        band = env.to_dict()["estimate"]["association_band"]
        return band["upper"] - band["lower"]

    assert band_width(env_mod) >= band_width(env_low)


def test_band_stays_within_unit_interval() -> None:
    left, right = _negative_monotone(40)
    paired = _paired_from_values(left, right, expected_direction=ExpectedDirection.NEGATIVE)
    env = correlate(paired, _hypothesis(expected_direction=ExpectedDirection.NEGATIVE))
    band = env.to_dict()["estimate"]["association_band"]
    assert -1.0 <= band["lower"] <= band["upper"] <= 1.0


def test_imputed_pairs_downweight_effective_support() -> None:
    # Same series; one variant has a chunk of imputed pairs. The imputed variant
    # must have effective support <= the clean variant and flag high_imputation
    # at >= 20% imputed pairs.
    n = 50

    base = _low_autocorr(n)
    clean = _paired_from_values(base, base)
    # Mark 15 of the left points imputed -> 30% imputed pairs.
    imputed = _paired_from_values(base, base, left_imputed_idx=tuple(range(15)))

    env_clean = correlate(clean, _hypothesis())
    env_imp = correlate(imputed, _hypothesis())
    assert env_clean.status is AnalyticalStatus.AVAILABLE
    assert env_imp.status is AnalyticalStatus.AVAILABLE

    assert (
        env_imp.to_dict()["estimate"]["effective_sample_size"]
        <= env_clean.to_dict()["estimate"]["effective_sample_size"]
    )
    keys = {c["key"] for c in env_imp.to_dict()["confound_checklist"]}
    assert ConfoundKey.HIGH_IMPUTATION.value in keys
    assert env_imp.to_dict()["is_imputed_pct"] >= 20.0


# ===========================================================================
# T014 — confound checklist trigger policy
# ===========================================================================


def test_low_sample_size_confound_for_marginal_raw_pairs() -> None:
    # 25 raw pairs -> in the 20-49 marginal band -> low_sample_size confound.
    base = _low_autocorr(25)
    paired = _paired_from_values(base, base)
    env = correlate(paired, _hypothesis())
    assert env.status is AnalyticalStatus.AVAILABLE
    keys = {c["key"] for c in env.to_dict()["confound_checklist"]}
    assert ConfoundKey.LOW_SAMPLE_SIZE.value in keys


def test_short_overlap_window_confound_under_28_days() -> None:
    # 24 paired days spans 24 calendar days < 28 -> short_overlap_window.
    base = _low_autocorr(24)
    paired = _paired_from_values(base, base)
    env = correlate(paired, _hypothesis())
    assert env.status is AnalyticalStatus.AVAILABLE
    keys = {c["key"] for c in env.to_dict()["confound_checklist"]}
    assert ConfoundKey.SHORT_OVERLAP_WINDOW.value in keys


def test_common_cause_plausible_only_when_candidate_supplied() -> None:
    base = _low_autocorr(60)

    without = _paired_from_values(base, base)
    env_without = correlate(without, _hypothesis())
    assert env_without.status is AnalyticalStatus.AVAILABLE
    keys_without = {c["key"] for c in env_without.to_dict()["confound_checklist"]}
    assert ConfoundKey.COMMON_CAUSE_PLAUSIBLE.value not in keys_without

    hyp = _hypothesis(common_cause_candidates=("ambient temperature",))
    with_cc = _paired_from_values(
        base, base, common_cause_candidates=("ambient temperature",)
    )
    env_with = correlate(with_cc, hyp)
    keys_with = {c["key"] for c in env_with.to_dict()["confound_checklist"]}
    assert ConfoundKey.COMMON_CAUSE_PLAUSIBLE.value in keys_with


def test_caveats_are_short_and_present() -> None:
    left, right = _negative_monotone(40)
    paired = _paired_from_values(left, right, expected_direction=ExpectedDirection.NEGATIVE)
    env = correlate(paired, _hypothesis(expected_direction=ExpectedDirection.NEGATIVE))
    caveats = env.to_dict()["caveats"]
    assert caveats  # at least one
    for c in caveats:
        assert len(c) <= 280


# ===========================================================================
# T015 — registration + reachability through the shared dispatch path
# ===========================================================================


def test_correlate_is_registered() -> None:
    assert CORRELATE_TOOL == "correlate"
    assert "correlate" in REGISTRY
    spec = REGISTRY["correlate"]
    assert spec.fn is not None
    assert spec.input_shape == "paired_ordered_daily_series"
    assert spec.result_kind == "correlate_association_estimate"
    assert spec.question_type is AnalyticalQuestionType.LAGGED_ASSOCIATION


def test_dispatch_reaches_correlate_with_paired_input() -> None:
    left, right = _negative_monotone(30)
    paired = _paired_from_values(
        left, right, lag_days=1, expected_direction=ExpectedDirection.NEGATIVE
    )
    hyp = _hypothesis(lag_days=1, expected_direction=ExpectedDirection.NEGATIVE)
    env = dispatch("correlate", paired, hyp)
    assert env.status is AnalyticalStatus.AVAILABLE
    assert env.tool_name == "correlate"


def test_correlate_exported_from_engine_package() -> None:
    import premura.engine as engine

    engine.load_builtin_analytical_tools()
    names = {spec.name for spec in engine.list_analytical_tools()}
    assert "correlate" in names
    # Public input types a WP04 caller needs are exported from the package.
    assert hasattr(engine, "PreRegisteredAssociationHypothesis")
    assert hasattr(engine, "PairedAnalyticalInput")
    assert hasattr(engine, "prepare_paired_input")


# ===========================================================================
# T016 — forbidden-output guards (the health-honesty boundary)
# ===========================================================================

# Causal / clinical vocabulary that must NEVER appear in correlate output. Note
# the legitimate closed confound key ``common_cause_plausible`` and any
# caller-supplied common-cause candidate text intentionally contain "cause"; the
# guard below tests the engine-authored prose only (caveats, messages, keys),
# after removing the contract's own confound-key tokens and the caller's verbatim
# candidates, so a genuine causal narration cannot hide behind that allowance.
# Matched as whole words (so "effective" is NOT a false positive for "effect",
# and "carried" is not for the bare word ... ). Each is a regex tested with
# word boundaries against the engine prose.
_FORBIDDEN_WORD_PATTERNS = (
    r"p-?values?",
    r"significan\w*",  # significant / significance
    r"confidence intervals?",
    r"causal",
    r"causes?",
    r"caused",
    r"effects?",  # the noun/verb "effect", but NOT "effective"
    r"impacts?",
    r"drivers?",
    r"diagnos\w*",  # diagnose / diagnosis / diagnostic
    r"treatments?",
    r"dosing",
    r"doses?",
    r"emergency",
    r"normal range",
    r"population norms?",
)


def _engine_prose(env: AnalyticalResultEnvelope) -> str:
    """Lowercased engine-authored prose: caveats + confound details + messages.

    Deliberately excludes the parameters block (which echoes the caller's
    verbatim hypothesis, including any common-cause candidate text) and the
    closed confound-key tokens, so the guard catches engine narration only.
    """
    parts: list[str] = list(env.caveats)
    for entry in env.confound_checklist:
        if entry.detail:
            parts.append(entry.detail)
    if env.refusal is not None:
        parts.append(env.refusal.message)
    return " ".join(parts).lower()


def json_dumps_lower(obj: object) -> str:
    """Flatten any JSON-safe payload into one lowercase string."""
    import json

    return json.dumps(obj, default=str).lower()


def _assert_no_forbidden_words(prose: str) -> None:
    import re

    for pattern in _FORBIDDEN_WORD_PATTERNS:
        match = re.search(rf"\b{pattern}\b", prose)
        assert match is None, f"forbidden word {pattern!r} leaked ({match}): {prose}"


def test_available_envelope_has_no_forbidden_substrings() -> None:
    left, right = _negative_monotone(40)
    paired = _paired_from_values(
        left,
        right,
        expected_direction=ExpectedDirection.NEGATIVE,
        common_cause_candidates=("ambient temperature",),
    )
    hyp = _hypothesis(
        expected_direction=ExpectedDirection.NEGATIVE,
        common_cause_candidates=("ambient temperature",),
    )
    env = correlate(paired, hyp)
    assert env.status is AnalyticalStatus.AVAILABLE
    _assert_no_forbidden_words(_engine_prose(env))
    # "confidence interval" / p-value / significance must not appear ANYWHERE in
    # the full serialized blob (keys or values), not just the prose.
    blob = json_dumps_lower(env.to_dict())
    assert "confidence interval" not in blob
    assert "p-value" not in blob and "pvalue" not in blob and "p_value" not in blob
    assert "significan" not in blob


def test_refusal_envelope_has_no_forbidden_substrings() -> None:
    left = [float(i) for i in range(25)]
    right = [7.0] * 25  # constant -> refusal
    paired = _paired_from_values(left, right)
    env = correlate(paired, _hypothesis())
    _assert_no_forbidden_words(_engine_prose(env))
    blob = json_dumps_lower(env.to_dict())
    assert "p-value" not in blob and "pvalue" not in blob and "significan" not in blob


def test_no_pvalue_or_significance_key_anywhere() -> None:
    left, right = _negative_monotone(40)
    paired = _paired_from_values(left, right, expected_direction=ExpectedDirection.NEGATIVE)
    data = correlate(paired, _hypothesis(expected_direction=ExpectedDirection.NEGATIVE)).to_dict()

    def walk_keys(obj: object):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from walk_keys(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from walk_keys(item)

    keys = [k.lower() for k in walk_keys(data)]
    for k in keys:
        assert "p_value" not in k
        assert "pvalue" not in k
        assert "significan" not in k


def test_request_for_pvalue_is_refused_before_computation() -> None:
    # The caller cannot smuggle a p-value/significance request through kwargs.
    left, right = _negative_monotone(30)
    paired = _paired_from_values(left, right, expected_direction=ExpectedDirection.NEGATIVE)
    hyp = _hypothesis(expected_direction=ExpectedDirection.NEGATIVE)
    env = correlate(paired, hyp, want_p_value=True)
    _assert_refusal(env, reason="unsupported_parameter")
    assert env.to_dict()["estimate"] is None


def test_request_for_significance_is_refused() -> None:
    left, right = _negative_monotone(30)
    paired = _paired_from_values(left, right, expected_direction=ExpectedDirection.NEGATIVE)
    hyp = _hypothesis(expected_direction=ExpectedDirection.NEGATIVE)
    env = correlate(paired, hyp, report_significance=True)
    _assert_refusal(env, reason="unsupported_parameter")


def test_request_for_lag_scan_is_refused() -> None:
    left, right = _negative_monotone(30)
    paired = _paired_from_values(left, right, expected_direction=ExpectedDirection.NEGATIVE)
    hyp = _hypothesis(expected_direction=ExpectedDirection.NEGATIVE)
    env = correlate(paired, hyp, scan_lags=True)
    _assert_refusal(env, reason="unsupported_parameter")


def test_request_for_tolerance_pairing_is_refused() -> None:
    left, right = _negative_monotone(30)
    paired = _paired_from_values(left, right, expected_direction=ExpectedDirection.NEGATIVE)
    hyp = _hypothesis(expected_direction=ExpectedDirection.NEGATIVE)
    env = correlate(paired, hyp, tolerance_days=2)
    _assert_refusal(env, reason="unsupported_parameter")
