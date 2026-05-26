"""Built-in comparative Stage 2 signals (WP03).

The two more caveat-heavy grounded answers that sit closer to the boundary with
interpretation — but stay strictly descriptive and strictly user-relative:

* ``sleep_deep_pct_baseline`` — baseline family: "Is the latest deep-sleep
  percentage below my *own* recent normal?" Compares the latest usable value to
  the mean of the user's own recent nightly values. There is NO population or
  clinical reference range and NO profile-dependent behavior — the only thing it
  knows is the user's own history.
* ``hrv_change_around_date`` — change family: "Did my overnight HRV shift after
  a date I name?" Splits the user's own observations into a window before and a
  window after a user-supplied anchor date, reports the two simple means, their
  counts, and the plain delta. It refuses to answer (``sufficient_data=False``)
  when either side is too thin. It NEVER reports p-values, confidence intervals,
  or any causal / significance language.

Both functions read only the user's own warehouse data through the shared
Stage 2 query helpers in :mod:`premura.engine._query`, and return one of the
shared result envelopes from :mod:`premura.engine._results`
(:class:`BaselineComparisonResult` / :class:`ChangeAroundDateResult`).

Anchor-date handling
--------------------
The engine's :func:`premura.engine.compute` invokes a signal as ``spec.fn(conn)``
— there is no parameter-passing channel for a user-supplied anchor date. Rather
than invent a parallel invocation system, this module follows the WP02 pattern:
each signal is a plain module-level public function. ``hrv_change_around_date``
exposes an explicit ``anchor_date`` parameter (the user-facing call), and the
registered ``fn`` is a zero-extra-arg wrapper that defaults the anchor to the
midpoint of the user's observed HRV span so it still resolves through
``engine.compute`` (no KeyError, returns a valid envelope). Callers that have a
real anchor date use the public function directly.

Registration follows the built-in module contract (CONTRACT.md): this module
exposes :func:`register_builtin_signals`, which the engine's static built-in
loader calls. See the WP02 report note about ``_BUILTIN_SIGNAL_MODULES``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from . import _query
from ._registry import REGISTRY, SignalSpec
from ._results import (
    BaselineComparisonResult,
    ChangeAroundDateResult,
    ComparisonState,
    FreshnessState,
)

if TYPE_CHECKING:
    import duckdb

# --------------------------------------------------------------------------- #
# Tuning constants — plain, descriptive, NOT clinical thresholds.
# --------------------------------------------------------------------------- #

# How far back the own-baseline window reaches. A few weeks of the user's own
# recent nights — enough to describe a personal normal without overreaching.
_BASELINE_SPAN = timedelta(days=30)
_BASELINE_WINDOW_TEXT = "last 30 days"

# Minimum prior observations (excluding the latest value itself) required before
# we will name a baseline at all. Below this we say UNKNOWN rather than turn one
# or two nights into a "normal".
_MIN_BASELINE_OBSERVATIONS = 3

# Relative deadband around the baseline mean. The latest value must differ from
# the baseline by more than this fraction of the baseline magnitude to count as
# below/above rather than within. Keeps ordinary night-to-night wobble honest.
_BASELINE_REL_TOLERANCE = 0.05

# Before/after windows around the anchor date for change detection.
_CHANGE_SPAN = timedelta(days=14)

# Minimum usable observations required on EACH side of the anchor before we are
# willing to call the comparison sufficient to answer.
_MIN_CHANGE_OBSERVATIONS = 3


# --------------------------------------------------------------------------- #
# T012 — own-baseline comparison primitives
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _BaselineComputation:
    """Outcome of an own-baseline comparison.

    ``comparison_state`` is UNKNOWN whenever there is no trustworthy baseline
    (too few prior values) — the honest "not enough data" verdict.
    """

    freshness_state: FreshnessState
    latest_value: float | None
    baseline_mean: float | None
    baseline_count: int
    comparison_state: ComparisonState


def _compute_own_baseline(
    conn: duckdb.DuckDBPyConnection,
    policy: _query.MetricPolicy,
    *,
    span: timedelta,
    now: datetime | None = None,
) -> _BaselineComputation:
    """Compare the latest usable value to the mean of the user's own prior values.

    Strictly user-relative: the baseline is the mean of the user's OWN
    observations within ``span`` (excluding the single latest value, which is
    the thing being compared). No reference ranges, no profile data.

    The comparison is UNKNOWN — never a guess — when there is no usable latest
    value or when fewer than :data:`_MIN_BASELINE_OBSERVATIONS` prior values
    exist to form a baseline.
    """
    reference = _query._naive_utc_now() if now is None else now
    latest = _query.latest_usable_value(conn, policy, now=reference)

    if latest.observation is None:
        return _BaselineComputation(
            freshness_state=FreshnessState.UNAVAILABLE,
            latest_value=None,
            baseline_mean=None,
            baseline_count=0,
            comparison_state=ComparisonState.UNKNOWN,
        )

    latest_value = latest.observation.value
    latest_ts = latest.observation.ts

    window_start = reference - span
    # Prior values forming the baseline: own observations inside the window,
    # excluding the single latest observation that we are comparing.
    prior = [
        obs.value
        for obs in _query.fetch_observations(conn, policy, since=window_start)
        if obs.ts < latest_ts
    ]

    if len(prior) < _MIN_BASELINE_OBSERVATIONS:
        return _BaselineComputation(
            freshness_state=latest.freshness_state,
            latest_value=latest_value,
            baseline_mean=None,
            baseline_count=len(prior),
            comparison_state=ComparisonState.UNKNOWN,
        )

    baseline_mean = sum(prior) / len(prior)
    comparison_state = _classify_against_baseline(latest_value, baseline_mean)
    return _BaselineComputation(
        freshness_state=latest.freshness_state,
        latest_value=latest_value,
        baseline_mean=baseline_mean,
        baseline_count=len(prior),
        comparison_state=comparison_state,
    )


def _classify_against_baseline(
    latest_value: float,
    baseline_mean: float,
) -> ComparisonState:
    """Place ``latest_value`` below / within / above the user's own baseline.

    A relative deadband around the baseline mean keeps trivial wobble as
    ``within`` rather than manufacturing a below/above movement.
    """
    tolerance = abs(baseline_mean) * _BASELINE_REL_TOLERANCE
    delta = latest_value - baseline_mean
    if abs(delta) <= tolerance:
        return ComparisonState.WITHIN
    return ComparisonState.ABOVE if delta > 0 else ComparisonState.BELOW


# --------------------------------------------------------------------------- #
# T013 — sleep_deep_pct_baseline
# --------------------------------------------------------------------------- #
def sleep_deep_pct_baseline(
    conn: duckdb.DuckDBPyConnection,
) -> BaselineComparisonResult:
    """Compare the latest deep-sleep percentage to the user's own recent normal.

    Answers "Was last night's deep-sleep percentage below my own recent normal?"
    using only the user's own history. The comparison is reported as
    ``below`` / ``within`` / ``above`` relative to the user's own baseline mean,
    or ``unknown`` when there is no usable value or too few prior nights to form
    a baseline. This is a device-estimate-based own-baseline comparison — NOT a
    medical threshold.
    """
    return _baseline_comparison("sleep_deep_pct_baseline", "sleep_deep_pct", conn)


def _baseline_comparison(
    signal_name: str,
    metric_id: str,
    conn: duckdb.DuckDBPyConnection,
) -> BaselineComparisonResult:
    policy = _query.load_metric_policy(conn, metric_id)
    if policy is None:
        return BaselineComparisonResult(
            signal_name=signal_name,
            metric_id=metric_id,
            latest_value=0.0,
            baseline_mean=0.0,
            baseline_window=_BASELINE_WINDOW_TEXT,
            comparison_state=ComparisonState.UNKNOWN,
            freshness_state=FreshnessState.UNAVAILABLE,
            caveats=[
                f"No metric definition found for {metric_id!r}.",
                _DEVICE_ESTIMATE_CAVEAT,
            ],
        )

    computed = _compute_own_baseline(conn, policy, span=_BASELINE_SPAN)
    caveats = _baseline_caveats(policy, computed)

    # When there is no trustworthy baseline (or no latest value), comparison is
    # UNKNOWN. The envelope still requires numeric latest/baseline fields, so we
    # surface what we have (or 0.0) and let the caveats + state carry the truth.
    return BaselineComparisonResult(
        signal_name=signal_name,
        metric_id=metric_id,
        latest_value=computed.latest_value if computed.latest_value is not None else 0.0,
        baseline_mean=computed.baseline_mean if computed.baseline_mean is not None else 0.0,
        baseline_window=_BASELINE_WINDOW_TEXT,
        comparison_state=computed.comparison_state,
        freshness_state=computed.freshness_state,
        caveats=caveats,
    )


# Standing caveat: deep-sleep percentage is a vendor/device estimate, and this
# comparison is purely against the user's own history — never a clinical rule.
_DEVICE_ESTIMATE_CAVEAT = (
    "Deep-sleep percentage is a device/vendor estimate compared only against "
    "your own recent nights; it is not a clinical or medical threshold."
)


def _baseline_caveats(
    policy: _query.MetricPolicy,
    computed: _BaselineComputation,
) -> list[str]:
    caveats: list[str] = [_DEVICE_ESTIMATE_CAVEAT]
    if computed.freshness_state is FreshnessState.UNAVAILABLE:
        caveats.append(
            f"No {policy.display_name.lower()} value has been recorded, so there "
            "is nothing to compare."
        )
        return caveats
    if computed.comparison_state is ComparisonState.UNKNOWN:
        caveats.append(
            f"Only {computed.baseline_count} prior night(s) are available in the "
            f"{_BASELINE_WINDOW_TEXT}; that is too few to describe your own "
            "baseline, so no comparison is made."
        )
    if computed.freshness_state is FreshnessState.STALE:
        window_text = policy.validity_window_text or "freshness window"
        caveats.append(
            f"The latest reading is older than its {window_text} freshness "
            "window, so it may not reflect last night."
        )
    return caveats


# --------------------------------------------------------------------------- #
# T014 — before/after comparison primitives
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _ChangeComputation:
    """Outcome of a before/after comparison around an anchor date.

    ``sufficient_data`` is False whenever EITHER window is too thin to answer.
    When it is False, ``delta`` / ``before_mean`` / ``after_mean`` stay None so
    the envelope never over-claims.
    """

    before_count: int
    after_count: int
    sufficient_data: bool
    before_mean: float | None
    after_mean: float | None
    delta: float | None


def _compute_change_around_date(
    conn: duckdb.DuckDBPyConnection,
    policy: _query.MetricPolicy,
    *,
    anchor_date: date,
    span: timedelta,
) -> _ChangeComputation:
    """Select pre/post windows around ``anchor_date`` and compute simple means.

    The before window is ``[anchor - span, anchor)`` and the after window is
    ``(anchor, anchor + span]``. Observations exactly on the anchor date are
    excluded from both sides (the boundary belongs to neither window). Only the
    user's own observations are read; no imputation, no fabricated points.

    Returns ``sufficient_data=False`` (and None means/delta) unless BOTH sides
    have at least :data:`_MIN_CHANGE_OBSERVATIONS` usable observations.
    """
    anchor_start = datetime.combine(anchor_date, time.min)
    anchor_end = datetime.combine(anchor_date, time.max)
    window_start = anchor_start - span
    window_end = anchor_end + span

    before: list[float] = []
    after: list[float] = []
    for obs in _query.fetch_observations(conn, policy, since=window_start):
        if obs.ts > window_end:
            continue
        if obs.ts < anchor_start:
            before.append(obs.value)
        elif obs.ts > anchor_end:
            after.append(obs.value)
        # Observations on the anchor day itself belong to neither window.

    sufficient = (
        len(before) >= _MIN_CHANGE_OBSERVATIONS
        and len(after) >= _MIN_CHANGE_OBSERVATIONS
    )
    if not sufficient:
        return _ChangeComputation(
            before_count=len(before),
            after_count=len(after),
            sufficient_data=False,
            before_mean=None,
            after_mean=None,
            delta=None,
        )

    before_mean = sum(before) / len(before)
    after_mean = sum(after) / len(after)
    return _ChangeComputation(
        before_count=len(before),
        after_count=len(after),
        sufficient_data=True,
        before_mean=before_mean,
        after_mean=after_mean,
        delta=after_mean - before_mean,
    )


# --------------------------------------------------------------------------- #
# T015 — hrv_change_around_date
# --------------------------------------------------------------------------- #
def hrv_change_around_date(
    conn: duckdb.DuckDBPyConnection,
    anchor_date: date | None = None,
) -> ChangeAroundDateResult:
    """Report how overnight HRV compares before vs after a user-named date.

    Answers "Did my overnight HRV shift after a date I name?" by computing the
    simple mean of the user's own ``hrv_rmssd_overnight`` observations in the two
    weeks before the anchor and the two weeks after it, plus the plain delta.

    ``anchor_date`` is the user-supplied change date. When called through
    :func:`premura.engine.compute` (which only passes ``conn``) it defaults to
    the midpoint of the observed HRV span so the signal still resolves and
    returns a valid envelope; user-facing callers pass an explicit date.

    HARD BOUNDARY: this never reports p-values, confidence intervals, or any
    causal / significance language. It only states the two means, their counts,
    and whether there was enough data to answer at all.
    """
    return _change_around_date(
        "hrv_change_around_date",
        "hrv_rmssd_overnight",
        conn,
        anchor_date=anchor_date,
    )


def _change_around_date(
    signal_name: str,
    metric_id: str,
    conn: duckdb.DuckDBPyConnection,
    *,
    anchor_date: date | None,
) -> ChangeAroundDateResult:
    policy = _query.load_metric_policy(conn, metric_id)
    if policy is None:
        return ChangeAroundDateResult(
            signal_name=signal_name,
            metric_id=metric_id,
            anchor_date=anchor_date or _query._naive_utc_now().date(),
            before_count=0,
            after_count=0,
            sufficient_data=False,
            caveats=[
                f"No metric definition found for {metric_id!r}.",
                _CHANGE_DISCLAIMER,
            ],
        ).validate()

    resolved_anchor = (
        anchor_date
        if anchor_date is not None
        else _default_anchor_date(conn, policy)
    )

    computed = _compute_change_around_date(
        conn, policy, anchor_date=resolved_anchor, span=_CHANGE_SPAN
    )
    caveats = _change_caveats(policy, computed)

    return ChangeAroundDateResult(
        signal_name=signal_name,
        metric_id=metric_id,
        anchor_date=resolved_anchor,
        before_count=computed.before_count,
        after_count=computed.after_count,
        sufficient_data=computed.sufficient_data,
        before_mean=computed.before_mean,
        after_mean=computed.after_mean,
        delta=computed.delta,
        caveats=caveats,
    ).validate()


def _default_anchor_date(
    conn: duckdb.DuckDBPyConnection,
    policy: _query.MetricPolicy,
) -> date:
    """Midpoint date of the user's observed span, used only as a fallback.

    Lets ``hrv_change_around_date`` resolve through ``engine.compute`` (which
    cannot pass an anchor). When no observations exist, falls back to today.
    """
    observations = _query.fetch_observations(conn, policy)
    if not observations:
        return _query._naive_utc_now().date()
    first = observations[0].ts
    last = observations[-1].ts
    midpoint = first + (last - first) / 2
    return midpoint.date()


# Standing disclaimer for the change family: descriptive only, never causal or
# statistical-significance language.
_CHANGE_DISCLAIMER = (
    "This is a plain before/after average of your own overnight HRV around the "
    "date you named. It does not test statistical significance and does not "
    "imply that anything on that date caused a change."
)


def _change_caveats(
    policy: _query.MetricPolicy,
    computed: _ChangeComputation,
) -> list[str]:
    caveats: list[str] = [_CHANGE_DISCLAIMER]
    if not computed.sufficient_data:
        caveats.append(
            f"Not enough overnight HRV readings around this date "
            f"({computed.before_count} before, {computed.after_count} after; "
            f"at least {_MIN_CHANGE_OBSERVATIONS} are needed on each side) to "
            "answer, so no before/after averages are reported."
        )
    return caveats


# --------------------------------------------------------------------------- #
# Built-in registration (CONTRACT.md built-in loading contract)
# --------------------------------------------------------------------------- #
def register_builtin_signals() -> None:
    """Register WP03's comparative signals into :data:`REGISTRY`.

    Called by the engine's static built-in loader for every module listed in
    ``premura.engine._BUILTIN_SIGNAL_MODULES`` (this module is added there, one
    line, in WP01-owned ``__init__.py``). The ``hrv_change_around_date`` entry
    registers a zero-extra-arg wrapper so it resolves through ``engine.compute``;
    user-facing callers pass an explicit anchor via the public function.
    """
    _register(
        SignalSpec(
            name="sleep_deep_pct_baseline",
            domain=["sleep", "recovery"],
            inputs=["sleep_deep_pct"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=sleep_deep_pct_baseline,
            question=(
                "Is my latest deep-sleep percentage below my own recent normal?"
            ),
            family="baseline",
            missing_input_hint=(
                "Connect a wearable that records nightly sleep stages to "
                "answer this."
            ),
            caveat_summary=(
                "Deep-sleep percentage is a device estimate compared only "
                "against your own recent nights, not a clinical threshold.",
            ),
        )
    )
    _register(
        SignalSpec(
            name="hrv_change_around_date",
            domain=["cardiovascular", "recovery"],
            inputs=["hrv_rmssd_overnight"],
            output=None,
            priority="normal",
            auto_safe=False,
            revision="1",
            fn=hrv_change_around_date,
            question="Did my overnight HRV shift after a date I name?",
            family="change",
            missing_input_hint=(
                "Connect a wearable that records overnight HRV (rMSSD) to "
                "answer this."
            ),
            caveat_summary=(
                "A plain before/after average of your own overnight HRV — not a "
                "significance test and not a causal claim.",
            ),
        )
    )


def _register(spec: SignalSpec) -> None:
    REGISTRY[spec.name] = spec


__all__ = [
    "sleep_deep_pct_baseline",
    "hrv_change_around_date",
    "register_builtin_signals",
]
