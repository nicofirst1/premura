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

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

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
def resting_hr_trend(conn: duckdb.DuckDBPyConnection) -> TrendResult:
    """Direction of resting HR over recent weeks, with carried-forward visible.

    resting_hr is a LOCF metric, so within-window missing days appear as
    carried-forward (imputed) points and are counted/caveated; days beyond the
    freshness window stay gaps. Sparse series report ``UNKNOWN`` direction.
    """
    return _trend("resting_hr_trend", "resting_hr", conn)


# --------------------------------------------------------------------------- #
# T009 — steps_trend
# --------------------------------------------------------------------------- #
def steps_trend(conn: duckdb.DuckDBPyConnection) -> TrendResult:
    """Direction of daily steps, with ZERO imputed points.

    steps has ``missing_data_policy: none`` — the shared helper therefore never
    carries a value forward. Missing days are visible as gaps, never invented
    continuity. (steps is an interval metric, read from hp.fact_interval.)
    """
    return _trend("steps_trend", "steps", conn)


# --------------------------------------------------------------------------- #
# T010 — weight_trend
# --------------------------------------------------------------------------- #
def weight_trend(conn: duckdb.DuckDBPyConnection) -> TrendResult:
    """Direction of body weight over the last month, carry-forward made visible.

    weight is a LOCF metric with a P1W validity window: a recent reading may be
    carried forward across in-between days (flagged as imputed + caveated), but
    a reading older than the window is NOT presented as current — those days
    become gaps. No BMI / body-composition / profile-dependent behavior.
    """
    return _trend("weight_trend", "weight", conn)


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
# present-tense candidate, the evaluator surfaces *why* (stale-for-question
# when the reading is past its window, or an unsupported-for-current-status
# verdict otherwise). Either way we fold one concise, descriptive sentence into
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

    policy_caveat = _resting_hr_policy_caveat(result)
    if policy_caveat is None:
        return result

    # Preserve the existing freshness caveat(s); append-only, de-duplicated.
    caveats = list(result.caveats)
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


def _resting_hr_policy_caveat(result: StatusResult) -> str | None:
    """Evaluate the stale resting-HR reading and derive one caveat sentence.

    Builds an :class:`EvidenceCandidate` from the already-computed status result
    and runs it through :func:`evaluate_evidence` for ``CURRENT_STATUS`` against
    the built-in family policies. Returns a short, descriptive caveat when the
    evaluator does not admit the reading as a current-status answer, else None.

    The evaluator is pure and reads nothing from the warehouse — we pass the
    reading's own timestamp as ``reference_time`` so the recency comparison is
    deterministic and the verdict reflects *this* reading's place in its family
    policy, not wall-clock drift between the query and now. The caveat is
    additional context only: it never replaces the freshness-window caveat and
    carries no diagnosis, reference range, population norm, or advice.
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
        reference_time=result.observed_at,
    )
    # If the policy layer were to admit this reading as a current-status answer
    # there would be no extra context to add. The baseline-relative resting-HR
    # family does not admit an absolute current-status answer, so in practice a
    # refusal is always present for a stale reading; guard regardless so the
    # verdict — not a hard-coded assumption — drives whether a caveat is added.
    if evaluation.admissible_evidence:
        return None
    return (
        "Resting-HR admissibility policy: a reading older than its freshness "
        "window cannot stand in for your resting HR right now, so it is not "
        "treated as a current-status answer."
    )


def _trend(
    signal_name: str,
    metric_id: str,
    conn: duckdb.DuckDBPyConnection,
) -> TrendResult:
    policy = _query.load_metric_policy(conn, metric_id)
    if policy is None:
        now = _query._naive_utc_now()
        return TrendResult(
            signal_name=signal_name,
            metric_id=metric_id,
            window_start=now - _TREND_SPAN,
            window_end=now,
            trend_direction=TrendDirection.UNKNOWN,
            current_freshness_state=FreshnessState.UNAVAILABLE,
            points=[],
            imputed_point_count=0,
            gap_count=0,
            caveats=[f"No metric definition found for {metric_id!r}."],
        ).validate()

    window = _query.ordered_window(conn, policy, span=_TREND_SPAN)
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


def _register(spec: SignalSpec) -> None:
    REGISTRY[spec.name] = spec


__all__ = [
    "resting_hr_status",
    "resting_hr_trend",
    "steps_trend",
    "weight_trend",
    "bmi",
    "register_builtin_signals",
]
