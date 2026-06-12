"""Stage 3 — the condition-label paired-input layer (m8 WP1).

This module is the narrow preparation seam the ``condition_paired_t_test``
analytical tool (m8 WP2) needs before any per-episode paired estimate can run. It
is the **condition-label sibling** of
:mod:`~premura.engine.paired_inputs` (the simple anchor-date layer): the engine
CONTRACT's deferred-extension rule required condition-label pairing to ship as a
*new pairing contract* with new trace-identity fields and new refusal rules
rather than being smuggled into the anchor-date request shape, and this is that
reviewed addition. The anchor-date layer is **not** modified.

Its single job is to turn one already-admitted ordered
:class:`~premura.engine.analytical_inputs.AnalyticalInputSeries` plus a
caller-declared :class:`ConditionLabelPairedRequest` (metric, one
operator-declared condition label, a set of non-overlapping declared episodes,
before/after windows, expected direction) into either:

* a usable :class:`ConditionLabelPairedInput` carrying one ordered off/on
  :class:`ConditionEpisodePair` per usable episode plus per-episode exclusion
  disclosures, **or**
* a first-class :class:`~premura.engine.analytical_contract.RefusalOutcome` and
  **no** pairs.

It never computes the mean per-episode difference, the uncertainty, or the
analytical envelope — that is the tool's job (WP2). This layer produces a
*prepared per-episode pair set or a refusal*, full stop.

The one fixed deterministic pairing rule (a *bounded abstraction* — "compare
metric M between off-label and on-label declared periods", applied to any admitted
series — not a metric-specific or condition-specific tool; the condition *label*
is operator vocabulary, never an enum):

* An **episode** is a declared closed local-calendar-day range
  ``[start_day, end_day]`` with ``end_day >= start_day`` (an end before a start is
  a construction error). Episodes must be declared explicitly and must not overlap
  one another (overlap = declaration error = refusal of the whole request).
* Each episode contributes **one pair**:

  * **off value** = mean of usable observations on days in
    ``[start_day - before_days, start_day)`` that fall **outside every declared
    episode**;
  * **on value** = mean of usable observations on days in
    ``[start_day, min(start_day + after_days - 1, end_day)]``;
  * **difference = on - off** (the analog of after - before).

* Each admitted observation is keyed to its **local** calendar day
  (:func:`~premura.engine._localtime.local_calendar_day`, the same converter the
  anchor-date preparer uses). When two observations share a local day, the later
  one wins (last-write-wins, deterministic). The before/after window bounds reuse
  :data:`~premura.engine.paired_inputs.MAX_WINDOW_DAYS`; the expected-direction
  vocabulary is the existing closed
  :class:`~premura.engine.paired_inputs.BeforeAfterDirection`.
* An episode whose before-window intersects another declared episode, or that
  lacks at least one usable observation in either window, is **excluded with a
  per-episode disclosure** (episode start + machine-readable reason). No silent
  salvage, no invented values.
* The paired unit is the **episode**. Fewer than :data:`CONDITION_MIN_EPISODES`
  usable episodes after exclusions → refusal (dispersion undefined below that).

This module imports nothing from MCP and nothing from the warehouse/DuckDB layer;
it makes no network calls, holds no clock, and is fully deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from math import isfinite
from typing import Any

from premura.engine._localtime import local_calendar_day
from premura.engine.analytical_contract import RefusalOutcome
from premura.engine.analytical_inputs import AnalyticalInputSeries
from premura.engine.paired_inputs import MAX_WINDOW_DAYS, BeforeAfterDirection

__all__ = [
    "ConditionPairRefusalReason",
    "ConditionEpisode",
    "ConditionLabelPairedRequest",
    "ConditionEpisodePair",
    "ConditionEpisodeExclusion",
    "ConditionLabelPairedInput",
    "prepare_condition_label_paired_input",
    "condition_episode_pairs_for_computation",
    "CONDITION_MIN_EPISODES",
]


CONDITION_MIN_EPISODES = 2
"""The conservative minimum count of usable on-condition episodes. The paired unit
is the episode, so the mean per-episode difference and its descriptive dispersion
band are meaningless below two usable episodes — the preparer refuses there. The
boundary is inclusive: exactly two usable episodes is usable."""

_ONE_DAY = timedelta(days=1)


def _days(n: int) -> timedelta:
    """``n`` whole calendar days as a :class:`~datetime.timedelta`."""
    return timedelta(days=n)


# ---------------------------------------------------------------------------
# Closed refusal vocabulary (agents branch on these without parsing prose)
# ---------------------------------------------------------------------------


class ConditionPairRefusalReason(StrEnum):
    """Why a *condition-label paired* input is unusable, before any computation.

    These are the condition-stage reasons, kept machine-distinct so an agent can
    branch on exactly what failed. When the *constituent* series is itself
    refused, the paired refusal propagates that series' admissibility reason
    verbatim (admissibility is the evidence policy's job, never reimplemented
    here); these reasons cover only the gates that exist because there is a
    condition-label pairing request on top of an admitted series.
    """

    INVALID_REQUEST = "invalid_request"
    """The request is structurally invalid (metric mismatch, empty condition
    label, or a non-:class:`ConditionEpisode` in the declared set)."""

    TOO_FEW_EPISODES = "too_few_episodes"
    """Fewer than :data:`CONDITION_MIN_EPISODES` episodes were declared at all."""

    OVERLAPPING_EPISODES = "overlapping_episodes"
    """Two declared episodes overlap one another — a declaration error that
    refuses the whole request rather than silently salvaging a subset."""

    UNSUPPORTED_WINDOW = "unsupported_window"
    """``before_days`` or ``after_days`` is zero, negative, or beyond the
    supported maximum."""

    MISSING_DIRECTION = "missing_direction"
    """The expected direction is missing or outside the closed
    :class:`~premura.engine.paired_inputs.BeforeAfterDirection` set."""

    TOO_FEW_USABLE_EPISODES = "too_few_usable_episodes"
    """Fewer than :data:`CONDITION_MIN_EPISODES` episodes remain usable after
    per-episode exclusions (empty windows / before-window contamination)."""

    UNSUPPORTED_REQUEST = "unsupported_request"
    """The caller asked for an out-of-scope shape (a label list, candidate episode
    sets, window lists, a significance/p-value request, or any other unsupported
    keyword) — refused before any pairing."""


# ---------------------------------------------------------------------------
# Request / episode / pair / prepared-input shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConditionEpisode:
    """One declared closed on-condition local-calendar-day range ``[start, end]``.

    An episode is a caller-declared assertion that the operator was in the labeled
    condition from ``start_day`` through ``end_day`` inclusive. ``end_day`` before
    ``start_day`` is a programming/declaration error and raises at construction
    (the request can never carry a backwards episode); overlap *between* episodes
    is a seam refusal, not a construction error, because it depends on the whole
    declared set. The shape carries no label of its own — the single condition
    label lives on the request, never per-episode — and no extra fields: an
    unknown keyword is a ``TypeError`` at construction.
    """

    start_day: date
    end_day: date

    def __post_init__(self) -> None:
        if not isinstance(self.start_day, date) or isinstance(self.start_day, datetime):
            raise ValueError("ConditionEpisode.start_day must be a local calendar date")
        if not isinstance(self.end_day, date) or isinstance(self.end_day, datetime):
            raise ValueError("ConditionEpisode.end_day must be a local calendar date")
        if self.end_day < self.start_day:
            raise ValueError("ConditionEpisode.end_day must not be before start_day")

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_day": self.start_day.isoformat(),
            "end_day": self.end_day.isoformat(),
        }


@dataclass(frozen=True)
class ConditionLabelPairedRequest:
    """The caller's declared condition-label paired-comparison request.

    A ``condition_paired_t_test`` call is *pre-registered*: the metric, the single
    operator-declared condition label, the declared episode set, the before/after
    window sizes, and the expected direction are all fixed inputs declared
    **before** the result exists. The shape intentionally carries **no** anchor
    date, no ``labels`` list, no candidate-episode lists, no ``p_value`` flag, and
    no "choose best episodes" field — any such keyword is a ``TypeError`` at
    construction (the no-scanning scope guardrail). The condition label is operator
    vocabulary: any non-empty string, never validated against an enum or registry.

    Construction is permissive about *value* validity (a missing direction, an
    overlapping episode set, or an out-of-bounds window is a refusal the preparer
    surfaces, not an exception), so an agent's malformed request becomes a
    structured :class:`RefusalOutcome` rather than a crash. Only *structural*
    errors (unknown fields) raise.
    """

    metric_id: str
    condition_label: str
    episodes: tuple[ConditionEpisode, ...]
    before_days: int
    after_days: int
    expected_direction: BeforeAfterDirection

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "condition_label": self.condition_label,
            "episodes": [
                ep.to_dict() if isinstance(ep, ConditionEpisode) else ep for ep in self.episodes
            ],
            "before_days": self.before_days,
            "after_days": self.after_days,
            "expected_direction": (
                self.expected_direction.value
                if isinstance(self.expected_direction, BeforeAfterDirection)
                else self.expected_direction
            ),
        }


@dataclass(frozen=True)
class ConditionEpisodePair:
    """One usable episode's off/on pair (the per-episode paired unit).

    ``off_value`` is the mean of usable off-window observations outside every
    declared episode; ``on_value`` is the mean of usable on-window observations.
    ``off_count`` / ``on_count`` are the observation counts behind each mean (for
    traceability and confound flags). ``difference`` is ``on_value - off_value``.
    """

    episode_start: date
    episode_end: date
    off_value: float
    on_value: float
    off_count: int
    on_count: int
    off_is_imputed: bool = False
    on_is_imputed: bool = False

    def __post_init__(self) -> None:
        if not (isfinite(self.off_value) and isfinite(self.on_value)):
            raise ValueError("ConditionEpisodePair values must be finite numbers")
        if self.off_count < 1 or self.on_count < 1:
            raise ValueError("ConditionEpisodePair off_count/on_count must be >= 1")

    @property
    def difference(self) -> float:
        """``on_value - off_value`` (the per-episode paired difference)."""
        return self.on_value - self.off_value

    @property
    def is_imputed(self) -> bool:
        return self.off_is_imputed or self.on_is_imputed

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_start": self.episode_start.isoformat(),
            "episode_end": self.episode_end.isoformat(),
            "off_value": self.off_value,
            "on_value": self.on_value,
            "off_count": self.off_count,
            "on_count": self.on_count,
            "off_is_imputed": self.off_is_imputed,
            "on_is_imputed": self.on_is_imputed,
            "difference": self.difference,
        }


@dataclass(frozen=True)
class ConditionEpisodeExclusion:
    """One per-episode exclusion disclosure (episode start + machine reason).

    The preparer never silently drops a declared episode: every episode it cannot
    pair is surfaced here so the tool (and the narrating agent) can disclose
    exactly which declared periods were left out and why.
    """

    episode_start: date
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"episode_start": self.episode_start.isoformat(), "reason": self.reason}


@dataclass(frozen=True)
class ConditionLabelPairedInput:
    """The post-admissibility condition-label paired input consumed by the tool (WP2).

    Exactly one of two states, distinguished by ``refusal``:

    * **usable** (``refusal is None``) — ``pairs`` are ordered by episode start and
      computation-ready, ``episode_count_used == len(pairs)``, and any per-episode
      exclusions are disclosed in ``excluded_episodes``. This is the only state in
      which :func:`condition_episode_pairs_for_computation` returns pairs.
    * **refused** (``refusal is not None``) — carries a first-class
      :class:`RefusalOutcome` and **no** pairs, so a paired estimate can never run
      over an input that should not be analyzed.

    No estimate lives here. The structural guarantee mirrors
    :class:`~premura.engine.paired_inputs.BeforeAfterPairedInput`.
    """

    metric_id: str
    request: ConditionLabelPairedRequest
    condition_label: str
    pairs: tuple[ConditionEpisodePair, ...] = ()
    excluded_episodes: tuple[ConditionEpisodeExclusion, ...] = ()
    episode_count_declared: int = 0
    is_imputed_pct: float = 0.0
    freshness_status: str | None = None
    source_summary: dict[str, Any] = field(default_factory=dict)
    refusal: RefusalOutcome | None = None

    def __post_init__(self) -> None:
        if not self.metric_id or not self.metric_id.strip():
            raise ValueError("ConditionLabelPairedInput.metric_id must be a non-empty string")
        object.__setattr__(self, "source_summary", dict(self.source_summary))

        if self.refusal is not None:
            self.refusal.validate()
            if self.pairs:
                raise ValueError("a refused condition-label paired input must not carry pairs")
            return

        # Usable invariants.
        if not (0.0 <= self.is_imputed_pct <= 100.0):
            raise ValueError("ConditionLabelPairedInput.is_imputed_pct must be in [0.0, 100.0]")
        starts = [p.episode_start for p in self.pairs]
        if starts != sorted(starts):
            raise ValueError("ConditionLabelPairedInput.pairs must be ordered by episode_start")

    @property
    def is_usable(self) -> bool:
        return self.refusal is None

    @property
    def episode_count_used(self) -> int:
        """The number of usable episodes that produced a pair."""
        return len(self.pairs)

    def excluded_episodes_as_dicts(self) -> list[dict[str, Any]]:
        return [ex.to_dict() for ex in self.excluded_episodes]

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe summary (dates rendered ISO-8601). Byte-stable."""
        return {
            "metric_id": self.metric_id,
            "request": self.request.to_dict(),
            "condition_label": self.condition_label,
            "pairs": [p.to_dict() for p in self.pairs],
            "excluded_episodes": [ex.to_dict() for ex in self.excluded_episodes],
            "episode_count_declared": self.episode_count_declared,
            "episode_count_used": self.episode_count_used,
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
    request: ConditionLabelPairedRequest,
    refusal: RefusalOutcome,
) -> ConditionLabelPairedInput:
    return ConditionLabelPairedInput(
        metric_id=metric_id,
        request=request,
        condition_label=request.condition_label,
        episode_count_declared=len(request.episodes),
        refusal=refusal.validate(),
    )


@dataclass(frozen=True)
class _DayObservation:
    """One admitted observation keyed to a local calendar day (internal)."""

    day: date
    ts: datetime
    value: float
    is_imputed: bool


def _episodes_overlap(a: ConditionEpisode, b: ConditionEpisode) -> bool:
    """True when two closed day ranges share at least one day."""
    return a.start_day <= b.end_day and b.start_day <= a.end_day


def prepare_condition_label_paired_input(
    series: AnalyticalInputSeries,
    request: ConditionLabelPairedRequest,
    *args: object,
    **kwargs: object,
) -> ConditionLabelPairedInput:
    """Prepare a condition-label per-episode paired input, or refuse.

    This is the single seam ``condition_paired_t_test`` (WP2) calls to obtain a
    usable per-episode off/on pair set. It produces a
    :class:`ConditionLabelPairedInput` carrying one ordered pair per usable episode
    plus per-episode exclusion disclosures, or a :class:`RefusalOutcome` and no
    pairs — it **never** computes the mean per-episode difference, the uncertainty,
    or an estimate (WP2 owns those).

    The supported surface is exactly ``(series, request)``. Any extra positional or
    keyword argument is a request to scan/select episodes (or some other
    out-of-scope shape) and is refused **before** any pairing.

    Pairing follows the one fixed rule documented in the module docstring:
    local-calendar-day keying, off-window outside every declared episode, on-window
    truncated at ``after_days`` and the episode end, no invented values.

    Refuses (no estimate) when: an extra/unsupported argument is supplied; the
    input ``series`` is itself refused/inadmissible/stale (propagated verbatim);
    the request's ``metric_id`` does not match the series, or the condition label
    is blank, or a declared item is not a real episode; fewer than
    :data:`CONDITION_MIN_EPISODES` episodes are declared; any two declared episodes
    overlap; ``before_days`` or ``after_days`` is out of bounds; the expected
    direction is missing or outside the closed set; or fewer than
    :data:`CONDITION_MIN_EPISODES` episodes remain usable after exclusions.
    """
    metric_id = (
        request.metric_id if isinstance(request, ConditionLabelPairedRequest) else series.metric_id
    )

    # 0. Forbidden-request gate: refuse BEFORE any pairing. The supported surface
    #    is exactly (series, request); any extra argument is an attempt to widen
    #    the tool past its one declared label/episode-set (no scanning).
    if args or kwargs:
        offending = [f"positional[{i}]" for i in range(len(args))] + sorted(kwargs)
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=ConditionPairRefusalReason.UNSUPPORTED_REQUEST.value,
                message=(
                    "condition_paired_t_test prepares one declared label and episode "
                    "set only and accepts no extra parameters. It will not scan "
                    "labels, candidate episode sets, or windows, select the best "
                    "episodes, or return a significance verdict. "
                    f"Unsupported argument(s): {offending}."
                ),
                missing_or_bad_inputs=(metric_id,),
                parameter_name=offending[0] if offending else None,
            ),
        )

    # 1. Refused/inadmissible input series short-circuits, propagating its reason
    #    verbatim (admissibility is the evidence policy's job, never redone).
    if series.refusal is not None:
        src = series.refusal
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=src.reason,
                message=(
                    f"Condition-label paired input cannot be prepared: the series for metric "
                    f"'{series.metric_id}' is not admissible — {src.message}"
                ),
                missing_or_bad_inputs=src.missing_or_bad_inputs or (series.metric_id,),
                parameter_name=src.parameter_name,
            ),
        )

    # 2. Request structural checks: metric match, non-empty label, real episodes.
    if request.metric_id != series.metric_id:
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=ConditionPairRefusalReason.INVALID_REQUEST.value,
                message=(
                    f"Condition request metric '{request.metric_id}' does not match the prepared "
                    f"series metric '{series.metric_id}'."
                ),
                missing_or_bad_inputs=(request.metric_id, series.metric_id),
            ),
        )
    if not request.condition_label or not request.condition_label.strip():
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=ConditionPairRefusalReason.INVALID_REQUEST.value,
                message=(
                    "condition_label must be a non-empty operator-declared string before a "
                    "condition-label paired input can be prepared."
                ),
                missing_or_bad_inputs=(metric_id,),
                parameter_name="condition_label",
            ),
        )
    if not all(isinstance(ep, ConditionEpisode) for ep in request.episodes):
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=ConditionPairRefusalReason.INVALID_REQUEST.value,
                message="Every declared episode must be a ConditionEpisode (start/end days).",
                missing_or_bad_inputs=(metric_id,),
                parameter_name="episodes",
            ),
        )

    # 3. Minimum declared-episode count (the paired unit is the episode).
    if len(request.episodes) < CONDITION_MIN_EPISODES:
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=ConditionPairRefusalReason.TOO_FEW_EPISODES.value,
                message=(
                    f"Only {len(request.episodes)} condition episode(s) declared for metric "
                    f"'{metric_id}', below the minimum of {CONDITION_MIN_EPISODES} required for a "
                    "usable condition-label paired comparison."
                ),
                missing_or_bad_inputs=(metric_id,),
                parameter_name="episodes",
            ),
        )

    # 4. No two declared episodes may overlap (declaration error → refuse whole).
    episodes = list(request.episodes)
    for i in range(len(episodes)):
        for j in range(i + 1, len(episodes)):
            if _episodes_overlap(episodes[i], episodes[j]):
                return _refused(
                    metric_id,
                    request,
                    RefusalOutcome(
                        reason=ConditionPairRefusalReason.OVERLAPPING_EPISODES.value,
                        message=(
                            "Declared condition episodes must not overlap; episodes starting "
                            f"{episodes[i].start_day.isoformat()} and "
                            f"{episodes[j].start_day.isoformat()} intersect."
                        ),
                        missing_or_bad_inputs=(metric_id,),
                        parameter_name="episodes",
                    ),
                )

    # 5. Window bounds.
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
                    reason=ConditionPairRefusalReason.UNSUPPORTED_WINDOW.value,
                    message=(
                        f"{name} must be a whole-day integer in 1..{MAX_WINDOW_DAYS}; "
                        f"{name}={value!r} is out of bounds."
                    ),
                    missing_or_bad_inputs=(metric_id,),
                    parameter_name=name,
                ),
            )

    # 6. Expected direction (closed vocabulary, declared before computation).
    if not isinstance(request.expected_direction, BeforeAfterDirection):
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=ConditionPairRefusalReason.MISSING_DIRECTION.value,
                message=(
                    "expected_direction must be declared before computation and be one of "
                    f"{sorted(d.value for d in BeforeAfterDirection)}."
                ),
                missing_or_bad_inputs=(metric_id,),
                parameter_name="expected_direction",
            ),
        )

    # 7. Key admitted observations to their local calendar day (last-write-wins).
    by_day: dict[date, _DayObservation] = {}
    for point in series.points:
        local_day, _used_fallback = local_calendar_day(point.ts, point.local_tz)
        by_day[local_day] = _DayObservation(
            day=local_day, ts=point.ts, value=point.value, is_imputed=point.is_imputed
        )

    # The union of all declared episode days — an off-window observation that lands
    # inside ANY declared episode is excluded from the off mean.
    episode_days: set[date] = set()
    for ep in episodes:
        day = ep.start_day
        while day <= ep.end_day:
            episode_days.add(day)
            day += _ONE_DAY

    # 8. Per-episode off/on means (in declared-start order for determinism).
    pairs: list[ConditionEpisodePair] = []
    exclusions: list[ConditionEpisodeExclusion] = []
    for ep in sorted(episodes, key=lambda e: e.start_day):
        off_obs: list[_DayObservation] = []
        day = ep.start_day - _days(request.before_days)
        while day < ep.start_day:
            if day not in episode_days and day in by_day:
                off_obs.append(by_day[day])
            day += _ONE_DAY

        on_end = min(ep.start_day + _days(request.after_days - 1), ep.end_day)
        on_obs: list[_DayObservation] = []
        day = ep.start_day
        while day <= on_end:
            if day in by_day:
                on_obs.append(by_day[day])
            day += _ONE_DAY

        if not off_obs and not on_obs:
            reason = "no usable observation in either window"
        elif not off_obs:
            reason = "no usable off-window observation outside every declared episode"
        elif not on_obs:
            reason = "no usable on-window observation"
        else:
            reason = ""

        if reason:
            exclusions.append(ConditionEpisodeExclusion(episode_start=ep.start_day, reason=reason))
            continue

        off_value = sum(o.value for o in off_obs) / len(off_obs)
        on_value = sum(o.value for o in on_obs) / len(on_obs)
        pairs.append(
            ConditionEpisodePair(
                episode_start=ep.start_day,
                episode_end=ep.end_day,
                off_value=off_value,
                on_value=on_value,
                off_count=len(off_obs),
                on_count=len(on_obs),
                off_is_imputed=any(o.is_imputed for o in off_obs),
                on_is_imputed=any(o.is_imputed for o in on_obs),
            )
        )

    # 9. Minimum usable-episode count after exclusions.
    if len(pairs) < CONDITION_MIN_EPISODES:
        excluded_starts = [ex.episode_start.isoformat() for ex in exclusions]
        return _refused(
            metric_id,
            request,
            RefusalOutcome(
                reason=ConditionPairRefusalReason.TOO_FEW_USABLE_EPISODES.value,
                message=(
                    f"Only {len(pairs)} usable condition episode(s) for metric '{metric_id}' "
                    f"after exclusions, below the minimum of {CONDITION_MIN_EPISODES}. "
                    f"Excluded episode start(s): {excluded_starts}."
                ),
                missing_or_bad_inputs=(metric_id, *excluded_starts),
                parameter_name="episodes",
            ),
        )

    imputed_pairs = sum(1 for p in pairs if p.is_imputed)
    is_imputed_pct = (imputed_pairs / len(pairs)) * 100.0

    source_summary: dict[str, Any] = {
        "metric_id": metric_id,
        "condition_label": request.condition_label,
        "before_days": request.before_days,
        "after_days": request.after_days,
        "expected_direction": request.expected_direction.value,
        "pairing_rule": "per_episode_off_vs_on",
        "min_episodes": CONDITION_MIN_EPISODES,
        "series_sample_size": series.sample_size,
        "series_freshness_status": series.freshness_status,
        "policy_id": series.source_summary.get("policy_id"),
        "metric_family": series.source_summary.get("metric_family"),
    }

    return ConditionLabelPairedInput(
        metric_id=metric_id,
        request=request,
        condition_label=request.condition_label,
        pairs=tuple(pairs),
        excluded_episodes=tuple(exclusions),
        episode_count_declared=len(episodes),
        is_imputed_pct=is_imputed_pct,
        freshness_status=series.freshness_status,
        source_summary=source_summary,
    )


def condition_episode_pairs_for_computation(
    paired: ConditionLabelPairedInput,
) -> tuple[ConditionEpisodePair, ...]:
    """Return the computation-ready per-episode pairs, or refuse to.

    The condition-label twin of
    :func:`~premura.engine.paired_inputs.before_after_pairs_for_computation`: a
    refused paired input raises :class:`RuntimeError` rather than hand back pairs,
    so the WP2 estimate step cannot accidentally compute over an input that did not
    pass the condition gates even if it forgets to branch on ``paired.refusal``.
    """
    if paired.refusal is not None:
        raise RuntimeError(
            f"refused condition-label paired input for metric '{paired.metric_id}' "
            f"(reason={paired.refusal.reason!r}) must not be passed to computation"
        )
    return paired.pairs
