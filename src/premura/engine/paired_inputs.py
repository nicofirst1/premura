"""Stage 3 — the simple anchor-date before/after *paired-input* layer (WP03).

This module is the narrow preparation seam that the ``paired_t_test`` analytical
tool (WP04) needs before any paired estimate can run. Its single job is to turn
one already-admitted ordered :class:`~premura.engine.analytical_inputs.AnalyticalInputSeries`
plus a caller-declared :class:`BeforeAfterPairedRequest` (metric, anchor date,
before window, after window, expected direction) into either:

* a usable :class:`BeforeAfterPairedInput` carrying ordered, computation-ready
  matched pairs and enough span/imputation metadata for WP04 to report pair count
  and the admissible paired span (FR-006), **or**
* a first-class :class:`RefusalOutcome` and **no** pairs (FR-007).

It never computes the mean paired difference, the uncertainty, or the analytical
envelope — that is WP04's job. This layer produces a *prepared pair set or a
refusal*, full stop. The seam WP04 consumes is exactly
:func:`prepare_before_after_paired_input` (and :func:`before_after_pairs_for_computation`
to read pairs only when the input is usable).

The one fixed deterministic pairing rule (a *bounded abstraction* — "compare
metric M across declared anchor date D", applied to any admitted series — not a
metric-specific or condition-specific tool):

* The anchor ``anchor_date`` is a **local calendar date** ``D``. The before
  window is the ``before_days`` local calendar days strictly **before** ``D``;
  the after window is the ``after_days`` local calendar days strictly **after**
  ``D``. The anchor day itself belongs to neither side.
* Each admitted observation is keyed to its **local** calendar day
  (:func:`~premura.engine._localtime.local_calendar_day`, the same converter the
  correlate preparer uses, so a near-midnight observation lands on the day it
  actually belongs to). When two observations share a local day, the later one
  wins (last-write-wins, deterministic).
* Pairs are matched **nearest-to-anchor outward**: the before observation
  closest to the anchor is paired with the after observation closest to the
  anchor, the second-closest before with the second-closest after, and so on.
  ``pair_index`` is the rank from the anchor outward (0 = closest). The number of
  pairs is ``min(usable_before_days, usable_after_days)``; surplus observations on
  the longer side are unused — the preparer **never invents a value** to complete
  a pair.
* ``difference = after_value - before_value``.

What this layer deliberately does **not** do (scope guardrails, FR-014 / C-004
and the ``paired-t-test-contract``'s "Deferred Extension"): it does not scan
anchor dates, before/after windows, or pair-selection strategies; it does not
support ``condition_label`` pairing, arbitrary pair maps, or candidate-anchor/
candidate-window lists. The request shape carries none of those fields, so they
are a ``TypeError`` at construction; a request to "choose the best split" reaches
the preparer as an unsupported keyword and is refused before any pairing. Adding
condition-label pairing later requires a new mission with its own pairing
contract, identity fields, and refusal rules — it must not be smuggled into this
simple anchor-date request shape.

This module imports nothing from MCP and nothing from the warehouse/DuckDB
layer; it makes no network calls, holds no clock, and is fully deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from premura.engine._localtime import local_calendar_day
from premura.engine.analytical_contract import RefusalOutcome
from premura.engine.analytical_inputs import AnalyticalInputSeries

__all__ = [
    "BeforeAfterDirection",
    "BeforeAfterPairRefusalReason",
    "BeforeAfterPairedRequest",
    "BeforeAfterPair",
    "BeforeAfterPairedInput",
    "prepare_before_after_paired_input",
    "before_after_pairs_for_computation",
    "MAX_WINDOW_DAYS",
    "BEFORE_AFTER_MIN_PAIRS",
]


# ---------------------------------------------------------------------------
# Parameter bounds (mirrors the WP01 policy-layer raw-pair floor)
# ---------------------------------------------------------------------------

MAX_WINDOW_DAYS = 365
"""Upper bound on ``before_days`` / ``after_days``. A window beyond this — or a
zero/negative window — is out of bounds and refused rather than silently
truncated. A year of daily calendar days is a generous ceiling for a simple
anchor-date before/after comparison."""

BEFORE_AFTER_MIN_PAIRS = 8
"""The conservative raw *pair* floor for the simple anchor-date paired
comparison. Mirrors the WP01 policy-layer ``_PAIRED_DIFFERENCE_MIN_PAIRS`` so the
same number gates both the per-series admissibility evidence and the post-pairing
count: below this many usable matched pairs a single mean paired difference would
carry essentially no information, so the preparer refuses before WP04 can run.
The boundary is inclusive — exactly ``BEFORE_AFTER_MIN_PAIRS`` pairs is usable."""


# ---------------------------------------------------------------------------
# Closed vocabularies (agents branch on these without parsing prose)
# ---------------------------------------------------------------------------


class BeforeAfterDirection(StrEnum):
    """The closed, pre-registered expected sign of ``after - before`` (FR-005).

    The caller must declare this **before** the result exists — declaring the
    expected direction up front is the anti-p-hacking discipline FR-005 calls
    out. It is a closed vocabulary so an agent cannot smuggle a free-form
    ``"up a bit"``; WP04 compares the observed sign against this declared value.
    """

    INCREASE = "increase"
    DECREASE = "decrease"


class BeforeAfterPairRefusalReason(StrEnum):
    """Why a *before/after paired* input is unusable, before any computation.

    These are the paired-stage reasons, kept machine-distinct so an agent can
    branch on exactly what failed. When the *constituent* series is itself
    refused, the paired refusal propagates that series' admissibility reason
    verbatim (admissibility is the WP01 evidence policy's job, never
    reimplemented here); these reasons cover only the gates that exist because
    there is an anchor-date pairing request on top of an admitted series.
    """

    INVALID_REQUEST = "invalid_request"
    """The request is structurally invalid (e.g. its metric does not match the
    series it is paired against)."""

    MISSING_ANCHOR_DATE = "missing_anchor_date"
    """The anchor date is missing or not a real calendar date."""

    UNSUPPORTED_WINDOW = "unsupported_window"
    """``before_days`` or ``after_days`` is zero, negative, or beyond the
    supported maximum."""

    MISSING_DIRECTION = "missing_direction"
    """The expected direction is missing or outside the closed
    :class:`BeforeAfterDirection` set."""

    NO_VALID_PAIRS = "no_valid_pairs"
    """No matched before/after pair can be built (one side of the anchor has no
    observation inside its window)."""

    TOO_FEW_PAIRS = "too_few_pairs"
    """Fewer than :data:`BEFORE_AFTER_MIN_PAIRS` matched pairs remain."""

    UNSUPPORTED_REQUEST = "unsupported_request"
    """The caller asked for an out-of-scope shape (anchor/window scanning,
    best-split selection, condition pairing, or any other unsupported keyword)."""


# ---------------------------------------------------------------------------
# Request / pair / prepared-input shapes (data-model.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BeforeAfterPairedRequest:
    """The caller's declared simple before/after paired-comparison request.

    A ``paired_t_test`` call is *pre-registered*: the metric, the anchor date, the
    before/after window sizes, and the expected direction are all fixed inputs
    declared **before** the result exists (FR-005). The shape intentionally
    carries **no** ``condition_label``, ``anchor_dates`` list, ``before_days``/
    ``after_days`` option lists, ``pair_map``, or "choose best split" field — any
    such keyword is a ``TypeError`` at construction (FR-014 / C-004 scope
    guardrail). Adding condition-label pairing is a future mission with its own
    contract; it must not be smuggled into this shape.

    Construction is permissive about *value* validity (a missing anchor date or
    an out-of-set direction is a refusal the preparer surfaces, not an
    exception), so an agent's malformed request becomes a structured
    :class:`RefusalOutcome` rather than a crash. Only *structural* errors
    (unknown fields) raise.
    """

    metric_id: str
    anchor_date: date
    before_days: int
    after_days: int
    expected_direction: BeforeAfterDirection

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "anchor_date": (
                self.anchor_date.isoformat()
                if isinstance(self.anchor_date, date)
                else self.anchor_date
            ),
            "before_days": self.before_days,
            "after_days": self.after_days,
            "expected_direction": (
                self.expected_direction.value
                if isinstance(self.expected_direction, BeforeAfterDirection)
                else self.expected_direction
            ),
        }


@dataclass(frozen=True)
class BeforeAfterPair:
    """One matched before/after observation pair (data-model → BeforeAfterPair).

    ``pair_index`` is the deterministic rank from the anchor outward (0 = the pair
    nearest the anchor). ``before_day`` / ``after_day`` are the local calendar days
    used for matching; ``before_ts`` / ``after_ts`` are the source instants for
    traceability. The imputation flags are carried verbatim from the upstream
    accepted points (the layer never invents a value). ``difference`` is
    ``after_value - before_value``.
    """

    pair_index: int
    before_day: date
    after_day: date
    before_ts: datetime
    after_ts: datetime
    before_value: float
    after_value: float
    before_is_imputed: bool = False
    after_is_imputed: bool = False

    def __post_init__(self) -> None:
        if self.pair_index < 0:
            raise ValueError("BeforeAfterPair.pair_index must be non-negative")
        if not (isfinite(self.before_value) and isfinite(self.after_value)):
            raise ValueError("BeforeAfterPair values must be finite numbers")

    @property
    def difference(self) -> float:
        """``after_value - before_value`` (the paired difference)."""
        return self.after_value - self.before_value

    @property
    def is_imputed(self) -> bool:
        """True when either side of the pair is an imputed (carried-forward) value."""
        return self.before_is_imputed or self.after_is_imputed

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_index": self.pair_index,
            "before_day": self.before_day.isoformat(),
            "after_day": self.after_day.isoformat(),
            "before_ts": self.before_ts.isoformat(),
            "after_ts": self.after_ts.isoformat(),
            "before_value": self.before_value,
            "after_value": self.after_value,
            "before_is_imputed": self.before_is_imputed,
            "after_is_imputed": self.after_is_imputed,
            "difference": self.difference,
        }


@dataclass(frozen=True)
class BeforeAfterPairedInput:
    """The post-admissibility paired input consumed by ``paired_t_test`` (WP04).

    Exactly one of two states, distinguished by ``refusal``:

    * **usable** (``refusal is None``) — ``pairs`` are ordered by ``pair_index``
      and computation-ready, and both before/after window spans plus the raw pair
      count are populated. This is the only state in which
      :func:`before_after_pairs_for_computation` returns pairs.
    * **refused** (``refusal is not None``) — carries a first-class
      :class:`RefusalOutcome` and **no** pairs and a zero pair count, so a paired
      estimate can never run over an input that should not be analyzed.

    No estimate lives here. The structural guarantee mirrors the single-series
    :class:`AnalyticalInputSeries`: refusal short-circuits before computation.
    """

    metric_id: str
    request: BeforeAfterPairedRequest
    pairs: tuple[BeforeAfterPair, ...] = ()
    before_window_start: date | None = None
    before_window_end: date | None = None
    after_window_start: date | None = None
    after_window_end: date | None = None
    raw_pair_count: int = 0
    is_imputed_pct: float = 0.0
    freshness_status: str | None = None
    source_summary: dict[str, Any] = field(default_factory=dict)
    refusal: RefusalOutcome | None = None

    def __post_init__(self) -> None:
        if not self.metric_id or not self.metric_id.strip():
            raise ValueError("BeforeAfterPairedInput.metric_id must be a non-empty string")
        object.__setattr__(self, "source_summary", dict(self.source_summary))

        if self.refusal is not None:
            self.refusal.validate()
            if self.pairs:
                raise ValueError("a refused before/after paired input must not carry pairs")
            if self.raw_pair_count:
                raise ValueError("a refused before/after paired input must not report a pair count")
            return

        # Usable invariants.
        if not (0.0 <= self.is_imputed_pct <= 100.0):
            raise ValueError("BeforeAfterPairedInput.is_imputed_pct must be in [0.0, 100.0]")
        indices = [p.pair_index for p in self.pairs]
        if indices != sorted(indices):
            raise ValueError("BeforeAfterPairedInput.pairs must be ordered by pair_index")
        if self.raw_pair_count != len(self.pairs):
            raise ValueError("BeforeAfterPairedInput.raw_pair_count must match the number of pairs")
        if (
            self.before_window_start is None
            or self.before_window_end is None
            or self.after_window_start is None
            or self.after_window_end is None
        ):
            raise ValueError(
                "a usable BeforeAfterPairedInput must populate both before/after window spans"
            )
        if self.before_window_start > self.before_window_end:
            raise ValueError(
                "BeforeAfterPairedInput.before_window_start must not be after before_window_end"
            )
        if self.after_window_start > self.after_window_end:
            raise ValueError(
                "BeforeAfterPairedInput.after_window_start must not be after after_window_end"
            )

    @property
    def is_usable(self) -> bool:
        """True when the request was well-formed and the pair set passed the floor."""
        return self.refusal is None

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe summary (dates/timestamps rendered ISO-8601). Byte-stable."""
        return {
            "metric_id": self.metric_id,
            "request": self.request.to_dict(),
            "pairs": [p.to_dict() for p in self.pairs],
            "before_window_start": (
                self.before_window_start.isoformat() if self.before_window_start else None
            ),
            "before_window_end": (
                self.before_window_end.isoformat() if self.before_window_end else None
            ),
            "after_window_start": (
                self.after_window_start.isoformat() if self.after_window_start else None
            ),
            "after_window_end": (
                self.after_window_end.isoformat() if self.after_window_end else None
            ),
            "raw_pair_count": self.raw_pair_count,
            "is_imputed_pct": self.is_imputed_pct,
            "freshness_status": self.freshness_status,
            "source_summary": dict(self.source_summary),
            "refusal": self.refusal.to_dict() if self.refusal is not None else None,
        }


# ---------------------------------------------------------------------------
# Preparation (admitted series + declared request → paired input or refusal)
# ---------------------------------------------------------------------------


def _refused(
    metric_id: str,
    request: BeforeAfterPairedRequest,
    refusal: RefusalOutcome,
) -> BeforeAfterPairedInput:
    return BeforeAfterPairedInput(
        metric_id=metric_id,
        request=request,
        refusal=refusal.validate(),
    )


@dataclass(frozen=True)
class _DayObservation:
    """One admitted observation keyed to a local calendar day (internal)."""

    day: date
    ts: datetime
    value: float
    is_imputed: bool


def prepare_before_after_paired_input(
    series: AnalyticalInputSeries,
    request: BeforeAfterPairedRequest,
    *args: object,
    **kwargs: object,
) -> BeforeAfterPairedInput:
    """Prepare a simple anchor-date before/after paired input, or refuse.

    This is the single seam ``paired_t_test`` (WP04) calls to obtain a usable
    matched-pair set. It produces a :class:`BeforeAfterPairedInput` carrying
    ordered pairs and span metadata, or a :class:`RefusalOutcome` and no pairs —
    it **never** computes the mean paired difference, the uncertainty, or an
    estimate (WP04 owns those).

    The supported surface is exactly ``(series, request)``. Any extra positional
    or keyword argument is a request to scan/select a split (or some other
    out-of-scope shape) and is refused **before** any pairing (FR-014 / C-004).

    Pairing follows the one fixed rule documented in the module docstring:
    local-calendar-day keying, anchor day excluded, nearest-to-anchor-outward
    matching, ``min`` of the two usable sides, no invented values.

    Refuses (no estimate) when:

    * an extra/unsupported argument is supplied (anchor/window scan, best-split);
    * the input ``series`` is itself refused/inadmissible/stale (the upstream
      admissibility reason is propagated verbatim);
    * the request's ``metric_id`` does not match the series;
    * the anchor date is missing or not a real calendar date;
    * ``before_days`` or ``after_days`` is zero, negative, or beyond
      :data:`MAX_WINDOW_DAYS`;
    * the expected direction is missing or outside :class:`BeforeAfterDirection`;
    * no matched pair can be built (one side has no observation in its window);
    * fewer than :data:`BEFORE_AFTER_MIN_PAIRS` matched pairs remain.
    """
    metric_id = (
        request.metric_id if isinstance(request, BeforeAfterPairedRequest) else series.metric_id
    )

    # 0. Forbidden-request gate: refuse BEFORE any pairing. The supported surface
    #    is exactly (series, request); any extra argument is an attempt to widen
    #    the tool past its one declared anchor split (FR-014 / C-004).
    if args or kwargs:
        offending = [f"positional[{i}]" for i in range(len(args))] + sorted(kwargs)
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=BeforeAfterPairRefusalReason.UNSUPPORTED_REQUEST.value,
                message=(
                    "paired_t_test prepares one declared anchor-date split only and "
                    "accepts no extra parameters. It will not scan anchor dates or "
                    "windows, select the best split, or pair by condition label. "
                    f"Unsupported argument(s): {offending}."
                ),
                missing_or_bad_inputs=(metric_id,),
                parameter_name=offending[0] if offending else None,
            ),
        )

    # 1. Refused/inadmissible input series short-circuits, propagating its reason
    #    verbatim (admissibility is the WP01 evidence policy's job, never redone).
    if series.refusal is not None:
        src = series.refusal
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=src.reason,
                message=(
                    f"Before/after paired input cannot be prepared: the series for metric "
                    f"'{series.metric_id}' is not admissible — {src.message}"
                ),
                missing_or_bad_inputs=src.missing_or_bad_inputs or (series.metric_id,),
                parameter_name=src.parameter_name,
            ),
        )

    # 2. Request structural check: the request must be for the series' metric.
    if request.metric_id != series.metric_id:
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=BeforeAfterPairRefusalReason.INVALID_REQUEST.value,
                message=(
                    f"Paired request metric '{request.metric_id}' does not match the prepared "
                    f"series metric '{series.metric_id}'."
                ),
                missing_or_bad_inputs=(request.metric_id, series.metric_id),
            ),
        )

    # 3. Anchor-date presence + type.
    if not isinstance(request.anchor_date, date) or isinstance(request.anchor_date, datetime):
        # A datetime is not a calendar *date*; require a plain local calendar date
        # so the before/after split is unambiguous.
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=BeforeAfterPairRefusalReason.MISSING_ANCHOR_DATE.value,
                message=(
                    "A local calendar anchor_date (a date, not a datetime or string) is "
                    "required before a before/after paired input can be prepared."
                ),
                missing_or_bad_inputs=(metric_id,),
                parameter_name="anchor_date",
            ),
        )

    # 4. Window bounds.
    for name, value in (("before_days", request.before_days), ("after_days", request.after_days)):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 1
            or value > MAX_WINDOW_DAYS
        ):
            return _refused(
                metric_id,
                request,
                RefusalOutcome(
                    reason=BeforeAfterPairRefusalReason.UNSUPPORTED_WINDOW.value,
                    message=(
                        f"{name} must be a whole-day integer in 1..{MAX_WINDOW_DAYS}; "
                        f"{name}={value!r} is out of bounds."
                    ),
                    missing_or_bad_inputs=(metric_id,),
                    parameter_name=name,
                ),
            )

    # 5. Expected direction (closed vocabulary, declared before computation).
    if not isinstance(request.expected_direction, BeforeAfterDirection):
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=BeforeAfterPairRefusalReason.MISSING_DIRECTION.value,
                message=(
                    "expected_direction must be declared before computation and be one of "
                    f"{sorted(d.value for d in BeforeAfterDirection)}."
                ),
                missing_or_bad_inputs=(metric_id,),
                parameter_name="expected_direction",
            ),
        )

    anchor = request.anchor_date

    # 6. Key admitted observations to their local calendar day and split by the
    #    anchor. Within a window the later observation wins per local day
    #    (last-write-wins, deterministic). The anchor day itself is excluded.
    before_by_day: dict[date, _DayObservation] = {}
    after_by_day: dict[date, _DayObservation] = {}
    for point in series.points:
        local_day, _used_fallback = local_calendar_day(point.ts, point.local_tz)
        if local_day == anchor:
            continue
        delta = (local_day - anchor).days
        obs = _DayObservation(
            day=local_day, ts=point.ts, value=point.value, is_imputed=point.is_imputed
        )
        if -request.before_days <= delta < 0:
            before_by_day[local_day] = obs
        elif 0 < delta <= request.after_days:
            after_by_day[local_day] = obs

    # 7. Nearest-to-anchor outward matching. Before days closest to the anchor are
    #    the largest (nearest D); after days closest are the smallest. Zip by rank;
    #    surplus on the longer side is unused — never invent a value to fill a pair.
    before_sorted = sorted(before_by_day.values(), key=lambda o: o.day, reverse=True)
    after_sorted = sorted(after_by_day.values(), key=lambda o: o.day)
    pair_count = min(len(before_sorted), len(after_sorted))

    if pair_count == 0:
        # One side of the anchor has no observation inside its window.
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=BeforeAfterPairRefusalReason.NO_VALID_PAIRS.value,
                message=(
                    f"No matched before/after pair can be built for metric '{metric_id}' "
                    f"around anchor {anchor.isoformat()}: "
                    f"{len(before_sorted)} usable before-day(s) and {len(after_sorted)} "
                    "usable after-day(s) inside the declared windows."
                ),
                missing_or_bad_inputs=(metric_id,),
            ),
        )

    if pair_count < BEFORE_AFTER_MIN_PAIRS:
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=BeforeAfterPairRefusalReason.TOO_FEW_PAIRS.value,
                message=(
                    f"Only {pair_count} matched before/after pair(s) for metric '{metric_id}' "
                    f"around anchor {anchor.isoformat()}, below the minimum of "
                    f"{BEFORE_AFTER_MIN_PAIRS} required for a usable paired comparison."
                ),
                missing_or_bad_inputs=(metric_id,),
                parameter_name="min_pairs",
            ),
        )

    pairs = tuple(
        BeforeAfterPair(
            pair_index=i,
            before_day=before_sorted[i].day,
            after_day=after_sorted[i].day,
            before_ts=before_sorted[i].ts,
            after_ts=after_sorted[i].ts,
            before_value=before_sorted[i].value,
            after_value=after_sorted[i].value,
            before_is_imputed=before_sorted[i].is_imputed,
            after_is_imputed=after_sorted[i].is_imputed,
        )
        for i in range(pair_count)
    )

    # 8. Usable bundle. Window spans reflect the actual paired days used (so the
    #    admissible paired span WP04 reports under FR-006 is honest). Imputation
    #    percentage counts pairs where EITHER side is imputed.
    used_before_days = [pairs[i].before_day for i in range(pair_count)]
    used_after_days = [pairs[i].after_day for i in range(pair_count)]
    before_window_start = min(used_before_days)
    before_window_end = max(used_before_days)
    after_window_start = min(used_after_days)
    after_window_end = max(used_after_days)

    imputed_pairs = sum(1 for p in pairs if p.is_imputed)
    is_imputed_pct = (imputed_pairs / pair_count) * 100.0

    source_summary: dict[str, Any] = {
        "metric_id": metric_id,
        "anchor_date": anchor.isoformat(),
        "before_days": request.before_days,
        "after_days": request.after_days,
        "expected_direction": request.expected_direction.value,
        "pairing_rule": "nearest_to_anchor_outward",
        "min_pairs": BEFORE_AFTER_MIN_PAIRS,
        "series_sample_size": series.sample_size,
        "series_freshness_status": series.freshness_status,
        "policy_id": series.source_summary.get("policy_id"),
        "metric_family": series.source_summary.get("metric_family"),
    }

    return BeforeAfterPairedInput(
        metric_id=metric_id,
        request=request,
        pairs=pairs,
        before_window_start=before_window_start,
        before_window_end=before_window_end,
        after_window_start=after_window_start,
        after_window_end=after_window_end,
        raw_pair_count=pair_count,
        is_imputed_pct=is_imputed_pct,
        freshness_status=series.freshness_status,
        source_summary=source_summary,
    )


def before_after_pairs_for_computation(
    paired: BeforeAfterPairedInput,
) -> tuple[BeforeAfterPair, ...]:
    """Return the computation-ready pairs, or refuse to.

    The before/after twin of
    :func:`~premura.engine.analytical_inputs.points_for_computation`: a refused
    paired input raises :class:`RuntimeError` rather than hand back pairs, so the
    WP04 paired-difference step cannot accidentally compute over an input that did
    not pass the paired gates even if it forgets to branch on ``paired.refusal``.
    """
    if paired.refusal is not None:
        raise RuntimeError(
            f"refused before/after paired input for metric '{paired.metric_id}' "
            f"(reason={paired.refusal.reason!r}) must not be passed to computation"
        )
    return paired.pairs
