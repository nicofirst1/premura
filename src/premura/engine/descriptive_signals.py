"""Built-in descriptive Stage 2 signals (WP02).

The first wave of grounded, freshness-aware answers that replace raw-table
direct reads:

* ``resting_hr_status`` — status family: "What is my resting HR right now, and
  can I trust it?"
* ``resting_hr_trend``  — trend family: "Is my resting HR going up/down/flat?"
* ``steps_trend``       — trend family: "Are my daily steps trending?" (steps
  has ``missing_data_policy: none`` so it NEVER imputes — gaps stay gaps).
* ``weight_trend``      — trend family: "Is my weight rising/falling/flat?"
  (weight allows carry-forward within its freshness window; carried-forward
  points are visible and caveated).

Each function reads only the user's own warehouse data through the shared
Stage 2 query helpers in :mod:`premura.engine._query`, and returns one of the
shared result envelopes from :mod:`premura.engine._results`. They are
**descriptive only**: no reference ranges, no diagnosis, no significance, no
BMI/body-composition or profile-dependent behavior. Freshness, gaps, and
carried-forward points are made explicit so Stage 3 never overstates trust.

Registration follows the built-in module contract (CONTRACT.md): this module
exposes :func:`register_builtin_signals`, which the engine's static built-in
loader calls. See the WP02 report note about ``_BUILTIN_SIGNAL_MODULES``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

# WP03: import ``resolve_dependency`` and the declaration/request dataclasses at
# module load time, not inside :func:`bmi`. Two reasons:
#
# 1. BMI is the first cross-domain proof consumer; the seam is the contract, so
#    it must be visible at the top of the consumer module rather than buried in
#    a function body.
# 2. Tests need a stable monkeypatch target. Importing ``resolve_dependency``
#    here exposes ``premura.engine.descriptive_signals.resolve_dependency`` as a
#    module-level attribute that
#    ``unittest.mock.patch("premura.engine.descriptive_signals.resolve_dependency")``
#    can rebind, so the no-bypass guarantee (BMI calls the seam exactly twice
#    via the public surface) is exercised through a spy in
#    ``tests/test_bmi_signal.py``.
from . import _query, resolve_dependency
from ._registry import REGISTRY, SignalSpec
from ._resolution import DependencyDeclaration, ResolutionRequest
from ._results import (
    FreshnessState,
    MissingInputReport,
    StatusResult,
    TrendDirection,
    TrendPoint,
    TrendResult,
)

# WP05 — resting-HR proof integration. The status path for resting HR is the
# first existing Stage 2 signal to hand its latest evidence to the new
# evidence-admissibility evaluator (WP01–WP04). It is imported at module load
# time, like ``resolve_dependency`` above, because the policy seam is part of
# this consumer's contract and must be visible at the top of the module rather
# than buried in a function body. This import is cheap and side-effect-free:
# the policy package only pulls in frozen dataclasses, closed enums, and the
# pure evaluator/registry — it touches neither DuckDB nor the network.
from .policies import EvidenceCandidate, QuestionType
from .policies._defaults import builtin_policies
from .policies._evaluator import evaluate_evidence

if TYPE_CHECKING:
    import duckdb

# Default trend span: a few weeks of daily points, enough to read direction
# without overreaching. Plain, descriptive — not a clinical window.
_TREND_SPAN = timedelta(days=28)

# Minimum genuinely-observed points before we will name a direction at all.
# Below this we report UNKNOWN rather than turn a sparse series into a claim.
_MIN_TREND_OBSERVATIONS = 3

# Relative deadband: |last - first| must exceed this fraction of the baseline
# magnitude to count as up/down rather than flat. Keeps tiny wobble honest.
_FLAT_REL_TOLERANCE = 0.02


# --------------------------------------------------------------------------- #
# T007 — resting_hr_status
# --------------------------------------------------------------------------- #
def resting_hr_status(conn: duckdb.DuckDBPyConnection) -> StatusResult:
    """Latest usable resting HR with an honest freshness verdict.

    Refuses to present stale data as current: a present-but-old value comes back
    as ``STALE`` (value retained, but caveated), and an absent value as
    ``UNAVAILABLE`` (value omitted). No trend, reference-range, or training
    interpretation.

    WP05 proof integration: once the existing freshness verdict is computed, the
    latest reading is handed to the Stage 2 evidence-admissibility evaluator as
    a ``CURRENT_STATUS`` candidate (see :func:`_resting_hr_policy_caveat`). The
    evaluator's verdict is mapped back into *additional caveat context only* —
    the ``StatusResult`` shape, the freshness state, and the retained value are
    all unchanged. This proves the policy handoff for one existing signal
    without migrating trend signals or BMI.
    """
    result = _status("resting_hr_status", "resting_hr", conn)
    return _augment_resting_hr_status_with_policy(result)


# --------------------------------------------------------------------------- #
# T008 — resting_hr_trend
# --------------------------------------------------------------------------- #
def resting_hr_trend(
    conn: duckdb.DuckDBPyConnection, *, params: Mapping[str, Any] | None = None
) -> TrendResult:
    """Direction of resting HR over recent weeks, with carried-forward visible.

    resting_hr is a LOCF metric, so within-window missing days appear as
    carried-forward (imputed) points and are counted/caveated; days beyond the
    freshness window stay gaps. Sparse series report ``UNKNOWN`` direction.

    Accepts an optional ``window_days`` param (threaded through
    ``engine.compute(..., params=...)``, issue #98) to override the default
    trend span; omitted or invalid values fall back to :data:`_TREND_SPAN`.
    """
    return _trend("resting_hr_trend", "resting_hr", conn, params=params)


# --------------------------------------------------------------------------- #
# T009 — steps_trend
# --------------------------------------------------------------------------- #
def steps_trend(
    conn: duckdb.DuckDBPyConnection, *, params: Mapping[str, Any] | None = None
) -> TrendResult:
    """Direction of daily steps, with ZERO imputed points.

    steps has ``missing_data_policy: none`` — the shared helper therefore never
    carries a value forward. Missing days are visible as gaps, never invented
    continuity. (steps is an interval metric, read from hp.fact_interval.)

    Accepts an optional ``window_days`` param (issue #98); see
    :func:`resting_hr_trend`.
    """
    return _trend("steps_trend", "steps", conn, params=params)


# --------------------------------------------------------------------------- #
# T010 — weight_trend
# --------------------------------------------------------------------------- #
def weight_trend(
    conn: duckdb.DuckDBPyConnection, *, params: Mapping[str, Any] | None = None
) -> TrendResult:
    """Direction of body weight over the last month, carry-forward made visible.

    weight is a LOCF metric with a P1W validity window: a recent reading may be
    carried forward across in-between days (flagged as imputed + caveated), but
    a reading older than the window is NOT presented as current — those days
    become gaps. No BMI / body-composition / profile-dependent behavior.

    Accepts an optional ``window_days`` param (issue #98); see
    :func:`resting_hr_trend`.
    """
    return _trend("weight_trend", "weight", conn, params=params)


# --------------------------------------------------------------------------- #
# Shared implementation
# --------------------------------------------------------------------------- #
def _status(
    signal_name: str,
    metric_id: str,
    conn: duckdb.DuckDBPyConnection,
) -> StatusResult:
    policy = _query.load_metric_policy(conn, metric_id)
    if policy is None:
        # Metric not in dim_metric at all — nothing usable to report.
        return StatusResult(
            signal_name=signal_name,
            metric_id=metric_id,
            display_name=metric_id,
            unit="",
            freshness_state=FreshnessState.UNAVAILABLE,
            validity_window="unknown",
            value=None,
            observed_at=None,
            caveats=[f"No metric definition found for {metric_id!r}."],
        ).validate()

    window_text = policy.validity_window_text or "unspecified"
    latest = _query.latest_usable_value(conn, policy)

    if latest.freshness_state is FreshnessState.UNAVAILABLE:
        return StatusResult(
            signal_name=signal_name,
            metric_id=metric_id,
            display_name=policy.display_name,
            unit=policy.unit,
            freshness_state=FreshnessState.UNAVAILABLE,
            validity_window=window_text,
            value=None,
            observed_at=None,
            caveats=[f"No {policy.display_name.lower()} value has been recorded."],
        ).validate()

    assert latest.observation is not None  # narrow for type-checkers
    caveats: list[str] = []
    if latest.freshness_state is FreshnessState.STALE:
        caveats.append(
            f"Latest {policy.display_name.lower()} reading is older than its "
            f"{window_text} freshness window; it may no longer reflect now."
        )

    return StatusResult(
        signal_name=signal_name,
        metric_id=metric_id,
        display_name=policy.display_name,
        unit=policy.unit,
        freshness_state=latest.freshness_state,
        validity_window=window_text,
        value=latest.observation.value,
        observed_at=latest.observation.ts,
        caveats=caveats,
    ).validate()


# --------------------------------------------------------------------------- #
# WP05 — resting_hr_status policy-evaluator proof integration
# --------------------------------------------------------------------------- #
#
# This is the FIRST behavior-touching slice of the evidence-admissibility
# mission, and it is intentionally narrow: ONLY ``resting_hr_status`` consults
# the policy evaluator, and it does so purely to *add caveat context*. The
# freshness verdict and retained value computed by :func:`_status` stay
# authoritative; the policy layer never relabels CURRENT/STALE/UNAVAILABLE and
# never changes the result family.
#
# The resting-HR metric (``resting_hr``) belongs to the built-in
# ``hrv_resting_recovery`` family, declared as ``baseline_relative`` in
# ``policies/_defaults.py``. That family deliberately does NOT admit an absolute
# ``CURRENT_STATUS`` answer — resting HR is only honest read relative to the
# operator's own baseline. So when we evaluate a resting-HR reading as a
# present-tense candidate, the evaluator surfaces *why* stale evidence cannot
# support a current-status answer. We fold one concise, descriptive sentence into
# the caveats — no diagnosis, reference range, population norm, or advice.

_RESTING_HR_POLICY_FAMILY = "hrv_resting_recovery"
"""Metric family the resting-HR policy is keyed under (see ``_defaults.py``)."""


def _augment_resting_hr_status_with_policy(result: StatusResult) -> StatusResult:
    """Fold the evidence-admissibility verdict into a resting-HR status result.

    Returns the SAME ``StatusResult`` shape with at most one extra caveat. The
    proof scope is deliberately the STALE case: when a present-but-old reading
    is offered for a present-tense question, the policy layer is consulted and
    its verdict is folded into the caveats as additional context. A ``CURRENT``
    reading keeps its existing clean contract (no added caveat), and an
    ``UNAVAILABLE`` result has no candidate to judge — both are returned
    untouched so this proof does not widen into a behavior change for the
    healthy/fresh path.
    """
    if result.freshness_state is not FreshnessState.STALE or result.observed_at is None:
        return result

    policy_caveats = _resting_hr_policy_caveats(result)
    if not policy_caveats:
        return result

    # Preserve the existing freshness caveat(s); append-only, de-duplicated.
    caveats = list(result.caveats)
    for policy_caveat in policy_caveats:
        if policy_caveat not in caveats:
            caveats.append(policy_caveat)

    # Rebuild the frozen envelope with the augmented caveats; every other field
    # (including the freshness verdict and retained value) is carried verbatim.
    return StatusResult(
        signal_name=result.signal_name,
        metric_id=result.metric_id,
        display_name=result.display_name,
        unit=result.unit,
        freshness_state=result.freshness_state,
        validity_window=result.validity_window,
        value=result.value,
        observed_at=result.observed_at,
        caveats=caveats,
    ).validate()


def _resting_hr_policy_caveats(result: StatusResult) -> tuple[str, ...]:
    """Evaluate the stale resting-HR reading and derive caveat sentences.

    Builds an :class:`EvidenceCandidate` from the already-computed status result
    and runs it through :func:`evaluate_evidence` for ``CURRENT_STATUS`` against
    the built-in family policies. Returns short, descriptive caveats when the
    evaluator does not admit the reading as a current-status answer, else an
    empty tuple.

    The evaluator is pure and reads nothing from the warehouse. We pass the same
    naive-UTC clock helper used by the existing Stage 2 query code so a stale
    status result is actually judged stale for the current-status question. The
    caveat is additional context only: it never replaces the freshness-window
    caveat and carries no diagnosis, reference range, population norm, or advice.
    """
    candidate = EvidenceCandidate(
        metric_id=result.metric_id,
        metric_family=_RESTING_HR_POLICY_FAMILY,
        value_kind="point_in_time",
        observed_at=result.observed_at,
        point_count=1,
    )
    evaluation = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [candidate],
        builtin_policies(),
        reference_time=_query._naive_utc_now(),
    )
    # If the policy layer were to admit this reading as a current-status answer
    # there would be no extra context to add. Stale readings should not be
    # admitted; guard regardless so the verdict — not a hard-coded assumption —
    # drives whether caveats are added.
    if evaluation.admissible_evidence:
        return ()

    evaluator_caveats: tuple[str, ...] = ()
    if evaluation.rejected_evidence:
        evaluator_caveats = evaluation.rejected_evidence[0].caveats
    elif evaluation.insufficient_evidence:
        evaluator_caveats = evaluation.insufficient_evidence[0].caveats
    elif evaluation.refusal is not None:
        evaluator_caveats = evaluation.refusal.caveats

    return tuple(
        dict.fromkeys(
            (
                *evaluator_caveats,
                "Resting-HR admissibility policy: a reading older than its freshness "
                "window cannot stand in for your resting HR right now, so it is not "
                "treated as a current-status answer.",
            )
        )
    )


def _trend(
    signal_name: str,
    metric_id: str,
    conn: duckdb.DuckDBPyConnection,
    *,
    params: Mapping[str, Any] | None = None,
) -> TrendResult:
    span_days = _param_int(params or {}, "window_days", _TREND_SPAN.days)
    span = timedelta(days=span_days)

    policy = _query.load_metric_policy(conn, metric_id)
    if policy is None:
        now = _query._naive_utc_now()
        return TrendResult(
            signal_name=signal_name,
            metric_id=metric_id,
            window_start=now - span,
            window_end=now,
            trend_direction=TrendDirection.UNKNOWN,
            current_freshness_state=FreshnessState.UNAVAILABLE,
            points=[],
            imputed_point_count=0,
            gap_count=0,
            caveats=[f"No metric definition found for {metric_id!r}."],
        ).validate()

    window = _query.ordered_window(conn, policy, span=span)
    points = [TrendPoint(ts=p.ts, value=p.value, is_imputed=p.is_imputed) for p in window.points]

    direction = _direction(window.observed_count, window.points)
    caveats = _trend_caveats(policy, window, direction)

    return TrendResult(
        signal_name=signal_name,
        metric_id=metric_id,
        window_start=window.window_start,
        window_end=window.window_end,
        trend_direction=direction,
        current_freshness_state=window.latest_freshness,
        points=points,
        imputed_point_count=window.imputed_count,
        gap_count=window.gap_count,
        caveats=caveats,
    ).validate()


def _direction(
    observed_count: int,
    points: list[_query.WindowPoint],
) -> TrendDirection:
    """Plain up/down/flat direction; UNKNOWN when too sparse to trust.

    Uses only genuinely observed points to decide first/last; imputed
    (carried-forward) points must not manufacture a direction on their own.
    """
    if observed_count < _MIN_TREND_OBSERVATIONS:
        return TrendDirection.UNKNOWN
    observed = [p for p in points if not p.is_imputed]
    if len(observed) < 2:
        return TrendDirection.UNKNOWN
    first = observed[0].value
    last = observed[-1].value
    delta = last - first
    tolerance = abs(first) * _FLAT_REL_TOLERANCE
    if abs(delta) <= tolerance:
        return TrendDirection.FLAT
    return TrendDirection.UP if delta > 0 else TrendDirection.DOWN


def _trend_caveats(
    policy: _query.MetricPolicy,
    window: _query.TrendWindow,
    direction: TrendDirection,
) -> list[str]:
    caveats: list[str] = []
    if direction is TrendDirection.UNKNOWN:
        caveats.append("Not enough observed points in this window to describe a direction.")
    if window.imputed_count > 0:
        caveats.append(
            f"{window.imputed_count} point(s) are carried forward from an earlier "
            "reading (no new measurement that day), not freshly observed."
        )
    if window.gap_count > 0:
        caveats.append(
            f"{window.gap_count} day(s) in this window have no measurement and are "
            "left as gaps rather than filled in."
        )
    if window.latest_freshness is FreshnessState.STALE:
        caveats.append(
            "The most recent reading is older than its freshness window, so the "
            "latest point may not reflect now."
        )
    elif window.latest_freshness is FreshnessState.UNAVAILABLE:
        caveats.append("No readings fall within the requested window.")
    return caveats


# --------------------------------------------------------------------------- #
# WP03 — BMI (first cross-domain proof consumer)
# --------------------------------------------------------------------------- #
#
# BMI is intentionally narrow: it proves the Stage 2 input-resolution seam can
# carry one Stage 2 answer across two semantic domains honestly. It is NOT a
# clinical interpretation surface, a reference-range lookup, or a new answer
# family — it returns the existing ``StatusResult`` envelope so the four-family
# Stage 2 contract stays closed for this mission.
#
# Key design rules (see contracts/bmi-proof-consumer.yaml and the spec's FR-004
# / FR-005):
#
# * BMI declares its prerequisites through ``DependencyDeclaration`` and
#   resolves them through :func:`premura.engine.resolve_dependency`. It does
#   NOT call ``_query.latest_usable_value`` directly, does NOT read
#   ``hp.profile_context_assertion`` directly, and does NOT compose a one-off
#   warehouse query of its own.
# * Both dependencies must resolve as ``usable=True`` before BMI computes a
#   value. Otherwise a single :class:`MissingInputReport` names exactly which
#   prerequisites are missing or stale (no silent substitution, no hidden
#   fallback into measured height).
# * The freshness window of the answer is borrowed from the binding-constraint
#   domain — body weight — because that is the prerequisite whose freshness is
#   actually time-sensitive at the anchor.

_BMI_REQUIRED_INPUTS: list[str] = [
    "profile:standing_height_cm",
    "observation:weight",
]
"""Stable, declared inputs surfaced by :class:`MissingInputReport`.

These strings are the same form ``SignalSpec.inputs`` uses (a free-form
metric-id-like vocabulary). The existing engine helper
:func:`premura.engine.check_inputs_available` does not understand them natively
because BMI mixes two domains; that is acceptable for a proof consumer and is
documented in :func:`bmi`'s docstring. The honest refusal path is the
:class:`MissingInputReport` returned by :func:`bmi`, not a generic input-check.
"""

_BMI_PROOF_CAVEAT: str = (
    "BMI is a proof consumer for the Stage 2 input-resolution seam; not a "
    "clinical or diagnostic interpretation."
)


def bmi(
    conn: duckdb.DuckDBPyConnection,
    *,
    anchor_ts: datetime | None = None,
) -> StatusResult | MissingInputReport:
    """First cross-domain Stage 2 proof consumer.

    Resolves declared standing height from ``profile_context`` and body weight
    from ``observation_history`` through
    :func:`premura.engine.resolve_dependency`. Returns a :class:`StatusResult`
    only when BOTH dependencies resolve as usable; otherwise returns a
    :class:`MissingInputReport` naming the unmet prerequisite(s).

    This is intentionally narrow proof scope: ``BMI = weight_kg / height_m**2``.
    No reference ranges, no diagnostic interpretation, no opening a new answer
    family. See ``contracts/bmi-proof-consumer.yaml``.

    Parameters
    ----------
    conn:
        Live DuckDB connection. Required by both resolvers.
    anchor_ts:
        Time reference for the resolution. ``None`` defaults to
        ``datetime.now(tz=UTC)``. A naive datetime is assumed to already be
        UTC; the resolvers handle the naive-UTC coercion.
    """
    if anchor_ts is None:
        anchor_ts = datetime.now(tz=UTC)

    # Declare and resolve both prerequisites through the public seam. The two
    # declarations are exactly the pair listed in
    # ``contracts/bmi-proof-consumer.yaml`` — kept in this order so the
    # human-facing message lists prerequisites in the same order as the
    # contract.
    height_request = ResolutionRequest(
        anchor_ts=anchor_ts,
        dependency=DependencyDeclaration(
            consumer_name="bmi",
            depends_on_domain="profile_context",
            required_key="standing_height_cm",
            failure_mode="explicit_missing_input",
        ),
    )
    weight_request = ResolutionRequest(
        anchor_ts=anchor_ts,
        dependency=DependencyDeclaration(
            consumer_name="bmi",
            depends_on_domain="observation_history",
            required_key="weight",
            failure_mode="explicit_missing_or_stale_input",
        ),
    )

    height_result = resolve_dependency(conn=conn, request=height_request)
    weight_result = resolve_dependency(conn=conn, request=weight_request)

    # ---------------- Refusal path ----------------
    # If either dependency is unusable, refuse explicitly. A combined report is
    # returned when both fail, so the caller sees the complete picture in one
    # message rather than chasing a refusal at a time.
    if not (height_result.usable and weight_result.usable):
        return _build_missing_input_report(height_result, weight_result)

    # ---------------- Success path ----------------
    assert height_result.payload is not None  # narrow for type-checkers
    assert weight_result.payload is not None
    height_cm_raw = height_result.payload["resolved_value"]
    weight_kg_raw = weight_result.payload["resolved_value"]

    # The profile slot for ``standing_height_cm`` is QUANTITY -> value_num, and
    # the observation resolver returns the numeric ``value`` directly, so both
    # are expected to be ``float`` here. A defensive coerce keeps a wrong-typed
    # row from masquerading as a usable BMI input.
    if not isinstance(height_cm_raw, (int, float)) or not isinstance(weight_kg_raw, (int, float)):
        return MissingInputReport(
            tool_name="bmi",
            required_inputs=list(_BMI_REQUIRED_INPUTS),
            missing_inputs=list(_BMI_REQUIRED_INPUTS),
            message=(
                "BMI requires numeric height and weight values; the resolver "
                "returned a non-numeric payload, which is treated as missing "
                "rather than guessed."
            ),
        )

    height_cm = float(height_cm_raw)
    weight_kg = float(weight_kg_raw)
    height_m = height_cm / 100.0

    if height_m <= 0:
        # Programmer-error-shaped data (e.g. a zero or negative height landed in
        # profile context) is treated as missing rather than crashing the
        # engine. The caller still gets an explicit, named refusal.
        return MissingInputReport(
            tool_name="bmi",
            required_inputs=list(_BMI_REQUIRED_INPUTS),
            missing_inputs=["profile:standing_height_cm"],
            message=(
                "BMI requires a positive declared standing height; the resolved value is not valid."
            ),
        )

    bmi_value = weight_kg / (height_m**2)

    # Freshness is borrowed from the binding-constraint domain (body weight),
    # because that is the prerequisite whose freshness actually limits trust at
    # the anchor. Profile context is slowly changing and uses as-of semantics,
    # not a freshness window. The validity_window text is the metric's seeded
    # ``validity_window`` from ``hp.dim_metric``; we fall back to weight's
    # documented P1W window when the policy lookup is unexpectedly empty.
    weight_policy = _query.load_metric_policy(conn, "weight")
    validity_window = (
        weight_policy.validity_window_text
        if weight_policy is not None and weight_policy.validity_window_text is not None
        else "P1W"
    )
    observed_at = weight_result.payload["observed_at"]

    return StatusResult(
        signal_name="bmi",
        metric_id="bmi",
        display_name="Body Mass Index",
        unit="kg_per_m2",
        freshness_state=FreshnessState.CURRENT,
        validity_window=validity_window,
        value=round(bmi_value, 2),
        observed_at=observed_at,
        caveats=[_BMI_PROOF_CAVEAT],
    ).validate()


def _build_missing_input_report(
    height_result: object,
    weight_result: object,
) -> MissingInputReport:
    """Compose a single :class:`MissingInputReport` for the BMI refusal path.

    Walks each unresolved dependency and folds it into the right bucket:

    * a ``usable=False, absence_reason="missing"`` outcome adds the input to
      ``missing_inputs``;
    * any other unusable outcome (``"stale"``, ``"unknown_metric"``,
      ``"unsupported_domain"``, …) adds the input to ``stale_inputs`` — that
      bucket is the catch-all for "present-but-not-usable" so the caller can
      still tell missing-from-the-warehouse apart from data-was-found-but-old.

    A combined message lists each refusal reason in order so a caller sees the
    full picture instead of chasing one failure at a time.
    """
    missing_inputs: list[str] = []
    stale_inputs: list[str] = []
    message_parts: list[str] = []

    if not height_result.usable:  # type: ignore[attr-defined]
        reason = height_result.absence_reason  # type: ignore[attr-defined]
        if reason == "missing":
            missing_inputs.append("profile:standing_height_cm")
            message_parts.append(
                "BMI requires a declared standing height in profile context; "
                "no assertion is on file as of the anchor time."
            )
        else:
            stale_inputs.append("profile:standing_height_cm")
            message_parts.append(
                "BMI requires a usable declared standing height in profile "
                f"context; the resolver returned {reason!r} rather than a "
                "usable value."
            )

    if not weight_result.usable:  # type: ignore[attr-defined]
        reason = weight_result.absence_reason  # type: ignore[attr-defined]
        if reason == "missing":
            missing_inputs.append("observation:weight")
            message_parts.append(
                "BMI requires a usable body-weight observation; none is "
                "available within the validity window as of the anchor time."
            )
        elif reason == "stale":
            stale_inputs.append("observation:weight")
            message_parts.append(
                "BMI requires a usable body-weight observation; the most "
                "recent reading is outside the freshness window for the "
                "anchor time."
            )
        else:
            stale_inputs.append("observation:weight")
            message_parts.append(
                "BMI requires a usable body-weight observation; the resolver "
                f"returned {reason!r} rather than a usable value."
            )

    return MissingInputReport(
        tool_name="bmi",
        required_inputs=list(_BMI_REQUIRED_INPUTS),
        missing_inputs=missing_inputs,
        stale_inputs=stale_inputs,
        message=" ".join(message_parts),
    )


# --------------------------------------------------------------------------- #
# WP04 — Intake descriptive signals (one per intake domain)
# --------------------------------------------------------------------------- #
#
# Two descriptive, NON-DIAGNOSTIC signals that consume the WP03 intake resolvers
# through the *same* public seam BMI uses (``resolve_dependency``). They are
# parameterized: a caller threads a matcher/quantity-key + a bounded window (and
# optional freshness / sufficiency knobs) through the WP03-extended ``compute()``
# seam (T031), and each signal's ``fn`` declares a ``params`` keyword.
#
# Doctrine (NFR-001 / contract §5): these signals report ONLY what the data
# shows — coverage counts and a plain trend direction — and refuse honestly when
# the declared domain is empty, stale, or too thin. They never compute a
# reference range, never say "should", never report a p-value or "significance",
# and never make a causal/diagnostic claim. The nutrition trend NEVER imputes a
# missing day; gaps stay visible (the no-fallback / gap-visibility invariant
# WP03 establishes in the resolver payload).
#
# Day basis (NFR-006 / D4): both signals report the SAME ``day_basis`` the
# resolver computed on, and read coverage off the resolver's already-bucketed
# local-calendar-day points/days. There is no second path that recomputes
# day/window metadata from raw UTC.
#
# Refusal states are STRUCTURALLY DISTINCT (FR-005 / D5):
#
# * ``missing_input``    — the declared domain has no matching rows in the
#                          window (the resolver returned ``usable=False``).
# * ``stale_input``      — matching rows exist but the latest usable day is older
#                          than the caller's freshness rule.
# * ``insufficient_data``— enough freshness but too few distinct logged/observed
#                          days to answer honestly.

_DEFAULT_INTAKE_WINDOW_DAYS: int = 30
"""Repo-default bounded look-back window when the caller declares none.

Matches the resolver defaults (``views/*_intake.py``) so signal and resolver
agree on the window unless the caller overrides it."""

_DEFAULT_SUPPLEMENT_FRESHNESS_DAYS: int = 7
"""Default staleness cutoff for adherence: a latest logged day older than this
many days before the anchor is reported ``stale_input`` rather than presented as
current coverage."""

_DEFAULT_NUTRITION_FRESHNESS_DAYS: int = 7
"""Default staleness cutoff for the nutrition trend's latest observed day."""

_DEFAULT_MIN_LOGGED_DAYS: int = 1
"""Minimum distinct logged days before adherence coverage is answered."""

_MIN_TREND_DAYS: int = 2
"""Minimum distinct observed days before a nutrition direction is named."""


@dataclass(frozen=True)
class SupplementAdherenceResult:
    """Coverage answer for a caller-declared supplement matcher over a window.

    Descriptive only: "K of N days carried a logged dose". No adherence
    *judgement*, no recommendation, no reference range. ``status`` is one of the
    four structurally distinct states; the coverage fields are populated only
    when ``status == "available"`` (or retained for ``stale_input`` so the caller
    can see why it is stale)."""

    signal_name: str
    matcher: str
    status: str  # "available" | "missing_input" | "stale_input" | "insufficient_data"
    window_day_count: int
    logged_day_count: int
    coverage_fraction: float | None = None
    latest_logged_at: datetime | None = None
    day_basis: str | None = None
    logged_days: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": "status",
            "kind": "supplement_intake_adherence",
            "signal_name": self.signal_name,
            "matcher": self.matcher,
            "status": self.status,
            "window_day_count": self.window_day_count,
            "logged_day_count": self.logged_day_count,
            "coverage_fraction": self.coverage_fraction,
            "latest_logged_at": _iso(self.latest_logged_at),
            "day_basis": self.day_basis,
            "logged_days": list(self.logged_days),
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True)
class NutritionTrendResult:
    """Plain direction of a caller-declared nutrient/energy key over a window.

    Descriptive only: ``up`` / ``down`` / ``flat`` / ``unknown`` read off the
    resolver's visible daily points. Missing days are NEVER imputed — they stay
    gaps, surfaced in ``caveats``. No significance, no reference range, no causal
    claim."""

    signal_name: str
    quantity_key: str
    status: str  # "available" | "missing_input" | "stale_input" | "insufficient_data"
    trend_direction: str  # up | down | flat | unknown
    window_day_count: int
    days_with_data: int
    points: list[dict[str, Any]] = field(default_factory=list)
    latest_logged_at: datetime | None = None
    day_basis: str | None = None
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": "trend",
            "kind": "nutrition_intake_trend",
            "signal_name": self.signal_name,
            "quantity_key": self.quantity_key,
            "status": self.status,
            "trend_direction": self.trend_direction,
            "window_day_count": self.window_day_count,
            "days_with_data": self.days_with_data,
            "points": [dict(point) for point in self.points],
            "latest_logged_at": _iso(self.latest_logged_at),
            "day_basis": self.day_basis,
            "caveats": list(self.caveats),
        }


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _param_int(params: Mapping[str, Any], key: str, default: int) -> int:
    """Read a positive-int param, falling back to ``default`` on absence/bad value."""
    raw = params.get(key)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _anchor_naive_utc(params: Mapping[str, Any]) -> datetime:
    """Resolve the anchor as naive UTC (the basis the resolvers compute on)."""
    anchor = params.get("anchor_ts")
    if not isinstance(anchor, datetime):
        anchor = datetime.now(tz=UTC)
    if anchor.tzinfo is not None:
        return anchor.astimezone(UTC).replace(tzinfo=None)
    return anchor


def _intake_request(
    *,
    consumer_name: str,
    domain: str,
    required_key: str,
    anchor_ts: datetime | None,
    window_days: int,
) -> ResolutionRequest:
    """Build a ResolutionRequest threading the window through ``failure_mode``.

    The resolver protocol is fixed at ``(conn, request)``; WP03 pins the
    convention that callers thread an optional window through the declaration's
    ``failure_mode`` slot as ``window_days=<int>``. We reuse that exact rule
    rather than inventing a second channel."""
    if anchor_ts is None:
        anchor_ts = datetime.now(tz=UTC)
    return ResolutionRequest(
        anchor_ts=anchor_ts,
        dependency=DependencyDeclaration(
            consumer_name=consumer_name,
            depends_on_domain=domain,
            required_key=required_key,
            failure_mode=f"window_days={window_days}",
        ),
    )


# --------------------------------------------------------------------------- #
# T017 — supplement_intake_adherence (status/coverage family)
# --------------------------------------------------------------------------- #
def supplement_intake_adherence(
    conn: duckdb.DuckDBPyConnection,
    *,
    params: Mapping[str, Any],
) -> SupplementAdherenceResult:
    """Coverage "K of N days" for a caller-declared supplement matcher.

    Parameters threaded through ``compute(..., params=...)`` (T031):

    * ``matcher`` (required) — the supplement matcher, interpreted by the WP03
      resolver using the matcher semantics pinned in
      ``views/supplement_intake.py`` (case-insensitive substring,
      product-then-ingredient, AND across tokens). This signal never re-derives
      that rule.
    * ``window_days`` — bounded look-back window N (repo default).
    * ``anchor_ts`` — time reference (defaults to now, UTC).
    * ``freshness_days`` — staleness cutoff for the latest logged day.
    * ``min_logged_days`` — minimum distinct logged days before answering.

    Reads coverage off the resolver payload (``logged_day_count``,
    ``window_day_count``, ``logged_days``, ``latest_logged_at``, ``day_basis``)
    — it does NOT re-read the warehouse. Descriptive only: it reports the count
    and fraction of logged days, never whether that coverage is "good".
    """
    matcher = params.get("matcher")
    if not isinstance(matcher, str) or not matcher.strip():
        raise ValueError(
            f"supplement_intake_adherence requires a non-empty 'matcher' param; got {matcher!r}"
        )

    window_days = _param_int(params, "window_days", _DEFAULT_INTAKE_WINDOW_DAYS)
    freshness_days = _param_int(params, "freshness_days", _DEFAULT_SUPPLEMENT_FRESHNESS_DAYS)
    min_logged_days = _param_int(params, "min_logged_days", _DEFAULT_MIN_LOGGED_DAYS)
    anchor_ts = params.get("anchor_ts") if isinstance(params.get("anchor_ts"), datetime) else None
    anchor_naive = _anchor_naive_utc(params)

    resolved = resolve_dependency(
        conn=conn,
        request=_intake_request(
            consumer_name="supplement_intake_adherence",
            domain="supplement_intake",
            required_key=matcher,
            anchor_ts=anchor_ts,
            window_days=window_days,
        ),
    )

    # ---- missing_input: declared-but-empty domain (no matching rows) ----
    if not resolved.usable:
        return SupplementAdherenceResult(
            signal_name="supplement_intake_adherence",
            matcher=matcher,
            status="missing_input",
            window_day_count=window_days,
            logged_day_count=0,
            caveats=[
                f"No supplement intake matching {matcher!r} is logged in the "
                f"{window_days}-day window; this is an honest no-data refusal, "
                "not substituted from another source."
            ],
        )

    payload = resolved.payload or {}
    logged_day_count = int(payload.get("logged_day_count", 0))
    latest_logged_at = payload.get("latest_logged_at")
    day_basis = payload.get("day_basis")
    logged_days = list(payload.get("logged_days", []))

    # ---- stale_input: latest logged day older than the freshness rule ----
    if isinstance(latest_logged_at, datetime):
        age = anchor_naive - latest_logged_at
        if age > timedelta(days=freshness_days):
            return SupplementAdherenceResult(
                signal_name="supplement_intake_adherence",
                matcher=matcher,
                status="stale_input",
                window_day_count=window_days,
                logged_day_count=logged_day_count,
                latest_logged_at=latest_logged_at,
                day_basis=day_basis,
                logged_days=logged_days,
                caveats=[
                    f"The most recent matching dose is older than the {freshness_days}-day "
                    "freshness window, so current coverage is not reported."
                ],
            )

    # ---- insufficient_data: too few distinct logged days to answer ----
    if logged_day_count < min_logged_days:
        return SupplementAdherenceResult(
            signal_name="supplement_intake_adherence",
            matcher=matcher,
            status="insufficient_data",
            window_day_count=window_days,
            logged_day_count=logged_day_count,
            latest_logged_at=latest_logged_at if isinstance(latest_logged_at, datetime) else None,
            day_basis=day_basis,
            logged_days=logged_days,
            caveats=[
                f"Only {logged_day_count} distinct logged day(s); at least "
                f"{min_logged_days} are needed before coverage is reported."
            ],
        )

    # ---- available: report plain K-of-N coverage ----
    coverage_fraction = logged_day_count / window_days if window_days > 0 else None
    caveats = [
        f"Coverage is {logged_day_count} logged day(s) out of a {window_days}-day window; "
        "days without a logged dose are shown as gaps, not assumed taken."
    ]
    return SupplementAdherenceResult(
        signal_name="supplement_intake_adherence",
        matcher=matcher,
        status="available",
        window_day_count=window_days,
        logged_day_count=logged_day_count,
        coverage_fraction=coverage_fraction,
        latest_logged_at=latest_logged_at if isinstance(latest_logged_at, datetime) else None,
        day_basis=day_basis,
        logged_days=logged_days,
        caveats=caveats,
    )


# --------------------------------------------------------------------------- #
# T018 — nutrition_intake_trend (trend family)
# --------------------------------------------------------------------------- #
def nutrition_intake_trend(
    conn: duckdb.DuckDBPyConnection,
    *,
    params: Mapping[str, Any],
) -> NutritionTrendResult:
    """Plain up/down/flat direction of a caller-declared nutrient/energy key.

    Parameters threaded through ``compute(..., params=...)`` (T031):

    * ``quantity_key`` (required) — the nutrition quantity key the WP03 resolver
      interprets (e.g. ``"energy"``, ``"protein"``).
    * ``window_days`` — bounded look-back window (repo default).
    * ``anchor_ts`` — time reference (defaults to now, UTC).
    * ``freshness_days`` — staleness cutoff for the latest observed day.

    Reads the resolver's already-bucketed daily ``points`` (local-day basis) and
    names a plain direction from the first vs last OBSERVED point. Missing days
    are NEVER imputed — gaps stay visible and are named in ``caveats``. No
    significance, reference range, or causal claim.
    """
    quantity_key = params.get("quantity_key")
    if not isinstance(quantity_key, str) or not quantity_key.strip():
        raise ValueError(
            "nutrition_intake_trend requires a non-empty 'quantity_key' param; "
            f"got {quantity_key!r}"
        )

    window_days = _param_int(params, "window_days", _DEFAULT_INTAKE_WINDOW_DAYS)
    freshness_days = _param_int(params, "freshness_days", _DEFAULT_NUTRITION_FRESHNESS_DAYS)
    anchor_ts = params.get("anchor_ts") if isinstance(params.get("anchor_ts"), datetime) else None
    anchor_naive = _anchor_naive_utc(params)

    resolved = resolve_dependency(
        conn=conn,
        request=_intake_request(
            consumer_name="nutrition_intake_trend",
            domain="nutrition_intake",
            required_key=quantity_key,
            anchor_ts=anchor_ts,
            window_days=window_days,
        ),
    )

    # ---- missing_input: declared-but-empty domain (no matching rows) ----
    if not resolved.usable:
        return NutritionTrendResult(
            signal_name="nutrition_intake_trend",
            quantity_key=quantity_key,
            status="missing_input",
            trend_direction=TrendDirection.UNKNOWN.value,
            window_day_count=window_days,
            days_with_data=0,
            caveats=[
                f"No nutrition intake with quantity key {quantity_key!r} is logged in the "
                f"{window_days}-day window; this is an honest no-data refusal, not "
                "substituted from observation history."
            ],
        )

    payload = resolved.payload or {}
    points = list(payload.get("points", []))
    days_with_data = int(payload.get("days_with_data", len(points)))
    latest_logged_at = payload.get("latest_logged_at")
    day_basis = payload.get("day_basis")

    # ---- stale_input: latest observed day older than the freshness rule ----
    if isinstance(latest_logged_at, datetime):
        age = anchor_naive - latest_logged_at
        if age > timedelta(days=freshness_days):
            return NutritionTrendResult(
                signal_name="nutrition_intake_trend",
                quantity_key=quantity_key,
                status="stale_input",
                trend_direction=TrendDirection.UNKNOWN.value,
                window_day_count=window_days,
                days_with_data=days_with_data,
                points=points,
                latest_logged_at=latest_logged_at,
                day_basis=day_basis,
                caveats=[
                    f"The most recent logged day is older than the {freshness_days}-day "
                    "freshness window, so a current direction is not reported."
                ],
            )

    # ---- insufficient_data: too few observed days to name a direction ----
    if days_with_data < _MIN_TREND_DAYS:
        return NutritionTrendResult(
            signal_name="nutrition_intake_trend",
            quantity_key=quantity_key,
            status="insufficient_data",
            trend_direction=TrendDirection.UNKNOWN.value,
            window_day_count=window_days,
            days_with_data=days_with_data,
            points=points,
            latest_logged_at=latest_logged_at if isinstance(latest_logged_at, datetime) else None,
            day_basis=day_basis,
            caveats=[
                f"Only {days_with_data} observed day(s) in the window; at least "
                f"{_MIN_TREND_DAYS} are needed before a direction is named. Missing days "
                "are left as gaps, not filled in."
            ],
        )

    # ---- available: name a plain direction from observed endpoints ----
    direction = _intake_trend_direction(points)
    caveats = [
        "Direction reads the first and last logged day in the window; days without a "
        "logged entry are shown as gaps, not filled in."
    ]
    return NutritionTrendResult(
        signal_name="nutrition_intake_trend",
        quantity_key=quantity_key,
        status="available",
        trend_direction=direction.value,
        window_day_count=window_days,
        days_with_data=days_with_data,
        points=points,
        latest_logged_at=latest_logged_at if isinstance(latest_logged_at, datetime) else None,
        day_basis=day_basis,
        caveats=caveats,
    )


def _intake_trend_direction(points: list[dict[str, Any]]) -> TrendDirection:
    """Plain up/down/flat from the first vs last visible point's value.

    Reuses the same relative-deadband rule as the metric trends so tiny wobble
    reads ``flat``. Operates only on genuinely-logged points (the resolver never
    imputes), so a direction is never manufactured from filled-in days.
    """
    if len(points) < 2:
        return TrendDirection.UNKNOWN
    first = float(points[0]["value"])
    last = float(points[-1]["value"])
    delta = last - first
    tolerance = abs(first) * _FLAT_REL_TOLERANCE
    if abs(delta) <= tolerance:
        return TrendDirection.FLAT
    return TrendDirection.UP if delta > 0 else TrendDirection.DOWN


# --------------------------------------------------------------------------- #
# Built-in registration (CONTRACT.md built-in loading contract)
# --------------------------------------------------------------------------- #
def register_builtin_signals() -> None:
    """Register WP02's descriptive signals into :data:`REGISTRY`.

    Called by the engine's static built-in loader for every module listed in
    ``premura.engine._BUILTIN_SIGNAL_MODULES``. See the WP02 report: this module
    must be added to that list (one line, in WP01-owned ``__init__.py``) for
    production auto-discovery; until then tests invoke this function directly.
    """
    _register(
        SignalSpec(
            name="resting_hr_status",
            domain=["cardiovascular", "recovery"],
            inputs=["resting_hr"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=resting_hr_status,
            question="What is my resting heart rate right now, and can I trust it?",
            family="status",
            missing_input_hint=(
                "Connect a wearable that records daily resting heart rate to answer this."
            ),
        )
    )
    _register(
        SignalSpec(
            name="resting_hr_trend",
            domain=["cardiovascular", "recovery"],
            inputs=["resting_hr"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=resting_hr_trend,
            question="Is my resting heart rate going up, down, or flat recently?",
            family="trend",
            missing_input_hint=(
                "Connect a wearable that records daily resting heart rate to answer this."
            ),
        )
    )
    _register(
        SignalSpec(
            name="steps_trend",
            domain=["activity"],
            inputs=["steps"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=steps_trend,
            question="Are my daily steps trending up or down?",
            family="trend",
            missing_input_hint=("Connect a step-tracking source to answer this."),
            caveat_summary=("Step days with no record are shown as gaps, not zero days.",),
        )
    )
    _register(
        SignalSpec(
            name="weight_trend",
            domain=["body_composition"],
            inputs=["weight"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=weight_trend,
            question="Is my weight rising, falling, or flat over the last month?",
            family="trend",
            missing_input_hint=("Record body weight (e.g. from a smart scale) to answer this."),
            caveat_summary=(
                "Days without a new weigh-in reuse the last reading within its "
                "freshness window and are flagged as carried forward.",
            ),
        )
    )
    # WP03 — BMI proof consumer. Registered under the existing "status" family
    # so the four-family Stage 2 contract stays closed. The ``inputs`` list
    # uses the engine's free-form metric-id-like strings; these are NOT strict
    # ``dim_metric.metric_id`` values because BMI mixes two semantic domains
    # (a profile attribute key and an observation metric_id). The honest
    # refusal path is the :class:`MissingInputReport` returned by :func:`bmi`,
    # not :func:`check_inputs_available` — see :func:`bmi`'s docstring.
    _register(
        SignalSpec(
            name="bmi",
            domain=["body_composition", "cross_domain_proof"],
            inputs=["profile:standing_height_cm", "observation:weight"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=bmi,
            question="What is my BMI right now?",
            family="status",
            missing_input_hint=(
                "BMI needs a declared standing height (set it via profile "
                "capture) AND a recent body-weight observation."
            ),
            caveat_summary=(
                "BMI is a proof of the cross-domain resolver seam, not a "
                "clinical interpretation; it carries no reference-range or "
                "diagnostic claim.",
            ),
        )
    )
    # WP04 — parameterized intake descriptive signals. They are registered here
    # (no ``engine/__init__.py`` edit — this module is already in
    # ``_BUILTIN_SIGNAL_MODULES``) and are intentionally left out of the
    # ``_BUILTIN_SIGNAL_NAMES`` load-guard frozenset, which is a SUBSET check, not
    # the authoritative registry; ``REGISTRY`` is authoritative. Their ``fn``
    # declares a ``params`` keyword so ``compute(name, conn, params=...)`` threads
    # the caller's matcher/quantity-key + window through the T031 seam.
    _register(
        SignalSpec(
            name="supplement_intake_adherence",
            domain=["nutrition", "supplements", "intake"],
            inputs=["supplement_intake"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=supplement_intake_adherence,
            question="How many days did I log a supplement matching my filter, out of the window?",
            family="status",
            missing_input_hint=(
                "Log supplement intake (a product or ingredient your matcher selects) "
                "to answer this."
            ),
            caveat_summary=(
                "Reports logged-day coverage (K of N days) only; days without a "
                "logged dose are gaps, not assumed taken, and no adherence "
                "judgement or recommendation is made.",
            ),
        )
    )
    _register(
        SignalSpec(
            name="nutrition_intake_trend",
            domain=["nutrition", "intake"],
            inputs=["nutrition_intake"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=nutrition_intake_trend,
            question="Is a nutrient/energy key I name trending up, down, or flat over a window?",
            family="trend",
            missing_input_hint=(
                "Log nutrition intake carrying the quantity key you name "
                "(e.g. energy) to answer this."
            ),
            caveat_summary=(
                "Plain up/down/flat over your own logged days; missing days stay "
                "visible gaps and are never filled in.",
            ),
        )
    )


def _register(spec: SignalSpec) -> None:
    REGISTRY[spec.name] = spec


__all__ = [
    "resting_hr_status",
    "resting_hr_trend",
    "steps_trend",
    "weight_trend",
    "bmi",
    "supplement_intake_adherence",
    "nutrition_intake_trend",
    "SupplementAdherenceResult",
    "NutritionTrendResult",
    "register_builtin_signals",
]
