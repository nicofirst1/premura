"""Stage 3 — the engine-owned analytical *input preparation* layer (WP03).

This module sits between the Stage 2 admissibility evaluator
(:mod:`premura.engine.policies._evaluator`) and the future Stage 3 proof tools
(``change_point`` / smoothed average). Its single job is to turn already-read
warehouse evidence into a **prepared analytical input series** — but *only after
admissibility passes*. If the evidence is missing, stale, inadmissible,
insufficient, or the request's parameter bounds make it unsupported, this layer
returns a first-class :class:`RefusalOutcome` and **no usable points**, so a
statistical method is never handed a series it should not compute over.

Why this layer is deliberately small (the "guide, don't enumerate" rule):

* It is **not** a generic query planner. It does not read DuckDB, does not pick
  metrics, does not invent windows. Callers (WP04 proof tools and their
  warehouse glue) pass explicit evidence — ordered points plus an
  :class:`EvidenceCandidate` and the family policy — exactly as the descriptive
  signals already do. This module owns one thing: the rule for *admitting* that
  evidence into the analytical input contract.
* It reuses the WP02 contract types rather than minting parallel ones. The
  refusal shape is :class:`RefusalOutcome` from
  :mod:`premura.engine.analytical_contract`; the closed analytical question
  vocabulary is :class:`AnalyticalQuestionType` from the same module. The
  admissibility verdict comes from the *existing* policy evaluator pattern —
  the analytical question type is mapped, through a closed table, onto the
  descriptive :class:`~premura.engine.policies.QuestionType` the evaluator
  already understands. No ad-hoc strings are ever passed through the evaluator.
* **Refusal happens before computation.** The prepared series only carries
  computation-ready points when ``refusal is None``. The public helper
  :func:`points_for_computation` enforces this at the seam: it raises rather
  than hand back points for a refused input, so a tool that forgets to branch
  on the refusal still cannot accidentally compute.

For single-series tools the overlap window equals the usable analysis window,
but the overlap fields are kept explicit so future multi-input tools inherit
the same contract without a shape change.

This module imports nothing from MCP and nothing from the warehouse/DuckDB
layer; it makes no network calls and persists nothing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Any

from premura.engine._localtime import local_calendar_day
from premura.engine.analytical_contract import AnalyticalQuestionType, RefusalOutcome
from premura.engine.policies._evaluator import PolicyInput, evaluate_evidence
from premura.engine.policies._model import (
    EvidenceCandidate,
    QuestionType,
    RejectionReason,
)

__all__ = [
    "InputRefusalReason",
    "PreparedPoint",
    "AnalyticalInputSeries",
    "ANALYTICAL_TO_POLICY_QUESTION",
    "prepare_input_series",
    "points_for_computation",
    # Paired preparation (WP02 — correlate lagged association)
    "ExpectedDirection",
    "PairedInputRefusalReason",
    "PreRegisteredAssociationHypothesis",
    "PairedObservation",
    "PairedAnalyticalInput",
    "prepare_paired_input",
    "paired_points_for_computation",
    "LAG_FREE_ABS_MAX",
    "LAG_JUSTIFIED_ABS_MAX",
    "MIN_PAIRED_OBSERVATIONS",
]


# ---------------------------------------------------------------------------
# Closed input-refusal vocabulary (machine-readable, agents branch on these)
# ---------------------------------------------------------------------------


class InputRefusalReason(StrEnum):
    """Why a prepared analytical input is unusable, before any computation.

    These are the input-preparation-stage reasons. They stay distinct so an
    agent can branch without parsing prose, and they map cleanly onto the
    :class:`RefusalOutcome.reason` the proof tool later surfaces. They are kept
    separate from the descriptive :class:`~premura.engine.policies.RejectionReason`
    because the analytical layer has its own concerns (parameter bounds,
    pre-computation refusal) the descriptive evaluator does not model.
    """

    EVIDENCE_MISSING = "evidence_missing"
    """No usable evidence was supplied for the requested input."""

    STALE_FOR_QUESTION = "stale_for_question"
    """The evidence is older than the admissibility window for the question."""

    INADMISSIBLE_FOR_QUESTION = "inadmissible_for_question"
    """The metric family is declared inadmissible / wrong-kind for the question."""

    INSUFFICIENT_DATA = "insufficient_data"
    """The evidence is too sparse to support the analytical method."""

    UNSUPPORTED_PARAMETER = "unsupported_parameter"
    """A requested parameter bound makes the analytical request unsupported."""

    UNSUPPORTED_QUESTION = "unsupported_question"
    """No admissibility policy/rule covers this analytical question."""


# The closed mapping from the contract-facing :class:`AnalyticalQuestionType`
# to the first-class policy :class:`QuestionType` of the same name. This is the
# wiring required by T011: the analytical enum is the public input, and the
# evaluator only ever sees a closed ``QuestionType`` — never an ad-hoc string.
# Per research note D4 each analytical question gates on its OWN question type
# (with its own freshness/sufficiency declared in the metric-family policy), not
# on a descriptive shape like ``recent_trend``. Adding an analytical question
# type is a reviewed change here, the same way confound keys are.
ANALYTICAL_TO_POLICY_QUESTION: Mapping[AnalyticalQuestionType, QuestionType] = MappingProxyType(
    {
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION: QuestionType.LEVEL_SHIFT_DETECTION,
        AnalyticalQuestionType.SMOOTHED_PATTERN: QuestionType.SMOOTHED_PATTERN,
        AnalyticalQuestionType.LAGGED_ASSOCIATION: QuestionType.LAGGED_ASSOCIATION,
        # finish-analytical-tool-set mission: rolling_mean and paired_t_test each
        # gate on their OWN first-class policy question type (with its own
        # freshness/sufficiency), never on a descriptive shape — identity-by-name
        # like every other entry above. The closed map MUST stay total over the
        # AnalyticalQuestionType enum, so adding the contract values without these
        # two entries would strand the new tools at input preparation.
        AnalyticalQuestionType.MOVING_WINDOW_PATTERN: QuestionType.MOVING_WINDOW_PATTERN,
        AnalyticalQuestionType.PAIRED_DIFFERENCE: QuestionType.PAIRED_DIFFERENCE,
        # m8 mission: condition_paired_t_test gates on its OWN first-class policy
        # question type (its paired unit is a declared on-condition episode, so it
        # carries an episode-count floor), never on the anchor-date paired shape.
        # The closed map MUST stay total over AnalyticalQuestionType.
        AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE: (
            QuestionType.CONDITION_PAIRED_DIFFERENCE
        ),
    }
)
"""Closed analytical→policy question map used to drive the evaluator.

Each reviewed analytical question maps to the first-class policy
:class:`QuestionType` of the same name, so admissibility is gated on the
analytical question's own declared rule — never collapsed onto a descriptive
shape (research note D4 rejected reusing ``recent_trend``). Keeping the map
closed (a ``MappingProxyType``) prevents callers from smuggling an arbitrary
question past the evaluator and keeps the analytical vocabulary the single
public input."""


# How a descriptive rejection reason collapses into an analytical input-refusal
# reason. The descriptive evaluator already produces distinct, closed reasons;
# this table re-expresses them in the analytical layer's vocabulary without
# inventing new branching logic.
_DESCRIPTIVE_TO_INPUT_REFUSAL: Mapping[RejectionReason, InputRefusalReason] = MappingProxyType(
    {
        RejectionReason.STALE_FOR_QUESTION: InputRefusalReason.STALE_FOR_QUESTION,
        RejectionReason.TOO_SPARSE: InputRefusalReason.INSUFFICIENT_DATA,
        RejectionReason.MISSING_TIMESTAMP: InputRefusalReason.INADMISSIBLE_FOR_QUESTION,
        RejectionReason.MISSING_REQUIRED_CONTEXT: InputRefusalReason.INADMISSIBLE_FOR_QUESTION,
        RejectionReason.WRONG_EVIDENCE_KIND: InputRefusalReason.INADMISSIBLE_FOR_QUESTION,
        RejectionReason.UNSUPPORTED_POLICY: InputRefusalReason.UNSUPPORTED_QUESTION,
    }
)


# ---------------------------------------------------------------------------
# Prepared input shapes (data-model.md → AnalyticalInputSeries)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreparedPoint:
    """One ordered point in a prepared analytical input series.

    ``is_imputed`` is True only for carried-forward points the upstream window
    extraction produced under a LOCF metric policy — the analytical layer never
    invents points, it only carries the ``is_imputed`` flag through so the
    imputation percentage and confound checklist stay honest.

    ``local_tz`` is the row's stored local-timezone descriptor (offset string,
    IANA name, or ``None``), carried so the paired preparer can resolve the
    *local* calendar day. It defaults to ``None`` (a backward-compatible end-of-
    record field) and is ignored by single-series tools.
    """

    ts: datetime
    value: float
    is_imputed: bool = False
    local_tz: str | None = None


@dataclass(frozen=True)
class AnalyticalInputSeries:
    """The engine-owned analytical input shape, prepared after admissibility.

    Exactly one of two states, distinguished by ``refusal``:

    * **usable** (``refusal is None``) — ``points`` are ordered and
      computation-ready, and every window/sample field is populated. This is the
      only state in which :func:`points_for_computation` will return points.
    * **refused** (``refusal is not None``) — carries a first-class
      :class:`RefusalOutcome` and **no** computation-ready points. The window
      and sample fields are left at their empty defaults.

    For single-series tools the overlap window equals the usable analysis
    window. The overlap fields are kept explicit (not derived on the fly) so a
    future multi-input tool that aligns several prepared series inherits the same
    contract without changing this shape.
    """

    metric_id: str
    question_type: AnalyticalQuestionType
    points: tuple[PreparedPoint, ...] = ()
    window_start: datetime | None = None
    window_end: datetime | None = None
    overlap_start: datetime | None = None
    overlap_end: datetime | None = None
    overlap_sample_size: int = 0
    sample_size: int = 0
    is_imputed_pct: float = 0.0
    freshness_status: str | None = None
    source_summary: Mapping[str, Any] = field(default_factory=dict)
    refusal: RefusalOutcome | None = None

    def __post_init__(self) -> None:
        if not self.metric_id or not self.metric_id.strip():
            raise ValueError("AnalyticalInputSeries.metric_id must be a non-empty string")
        if not isinstance(self.question_type, AnalyticalQuestionType):
            raise ValueError(
                "AnalyticalInputSeries.question_type must be an AnalyticalQuestionType value, "
                f"got {self.question_type!r}"
            )
        # Freeze the provenance summary so the prepared shape stays immutable.
        object.__setattr__(self, "source_summary", dict(self.source_summary))

        if self.refusal is not None:
            # A refused input must carry no computation-ready points and no
            # estimate-bearing metadata. This is the structural guarantee that
            # refusal short-circuits before computation.
            self.refusal.validate()
            if self.points:
                raise ValueError("a refused analytical input must not carry computation points")
            if self.sample_size or self.overlap_sample_size:
                raise ValueError("a refused analytical input must not report a sample size")
            return

        # Usable input invariants.
        if not (0.0 <= self.is_imputed_pct <= 100.0):
            raise ValueError("AnalyticalInputSeries.is_imputed_pct must be in [0.0, 100.0]")
        ordered = [p.ts for p in self.points]
        if ordered != sorted(ordered):
            raise ValueError("AnalyticalInputSeries.points must be ordered by timestamp")
        if self.sample_size != len(self.points):
            raise ValueError("AnalyticalInputSeries.sample_size must match the number of points")
        # Single-series default: the overlap window equals the usable window and
        # the overlap sample size equals the sample size unless a multi-input
        # caller narrows it.
        if self.overlap_sample_size > self.sample_size:
            raise ValueError("AnalyticalInputSeries.overlap_sample_size cannot exceed sample_size")
        # Usable inputs must carry their full window/overlap metadata. The
        # data-model contract (and this class's docstring) require every
        # window/overlap field populated for a non-refusal series; enforce it
        # here so a directly constructed series cannot bypass the input-series
        # metadata contract with null timestamps.
        if (
            self.window_start is None
            or self.window_end is None
            or self.overlap_start is None
            or self.overlap_end is None
        ):
            missing = [
                name
                for name, value in (
                    ("window_start", self.window_start),
                    ("window_end", self.window_end),
                    ("overlap_start", self.overlap_start),
                    ("overlap_end", self.overlap_end),
                )
                if value is None
            ]
            raise ValueError(
                "a usable AnalyticalInputSeries must populate its window/overlap "
                f"metadata; missing: {', '.join(missing)}"
            )
        if self.window_start > self.window_end:
            raise ValueError("AnalyticalInputSeries.window_start must not be after window_end")
        if self.overlap_start > self.overlap_end:
            raise ValueError("AnalyticalInputSeries.overlap_start must not be after overlap_end")
        if self.overlap_start < self.window_start or self.overlap_end > self.window_end:
            raise ValueError(
                "AnalyticalInputSeries overlap window must fall within the usable analysis window"
            )

    @property
    def is_usable(self) -> bool:
        """True when this input passed admissibility and carries usable points."""
        return self.refusal is None

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe summary (timestamps rendered ISO-8601). Byte-stable."""
        return {
            "metric_id": self.metric_id,
            "question_type": self.question_type.value,
            "points": [
                {
                    "ts": p.ts.isoformat(),
                    "value": p.value,
                    "is_imputed": p.is_imputed,
                }
                for p in self.points
            ],
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "overlap_start": self.overlap_start.isoformat() if self.overlap_start else None,
            "overlap_end": self.overlap_end.isoformat() if self.overlap_end else None,
            "overlap_sample_size": self.overlap_sample_size,
            "sample_size": self.sample_size,
            "is_imputed_pct": self.is_imputed_pct,
            "freshness_status": self.freshness_status,
            "source_summary": dict(self.source_summary),
            "refusal": self.refusal.to_dict() if self.refusal is not None else None,
        }


# ---------------------------------------------------------------------------
# Preparation (admissibility → prepared input or refusal)
# ---------------------------------------------------------------------------


def _refused_series(
    metric_id: str,
    question_type: AnalyticalQuestionType,
    refusal: RefusalOutcome,
) -> AnalyticalInputSeries:
    return AnalyticalInputSeries(
        metric_id=metric_id,
        question_type=question_type,
        refusal=refusal,
    )


def _input_refusal_reason(reasons: Sequence[RejectionReason]) -> InputRefusalReason:
    """Collapse the evaluator's distinct rejection reasons to one input reason.

    Reasons stay machine-distinct; this picks the most specific analytical
    refusal reason the descriptive verdict implies, preferring sparsity and
    staleness (the gate-failing reasons) over the structural ones.
    """
    mapped = [
        _DESCRIPTIVE_TO_INPUT_REFUSAL[r] for r in reasons if r in _DESCRIPTIVE_TO_INPUT_REFUSAL
    ]
    if not mapped:
        return InputRefusalReason.INADMISSIBLE_FOR_QUESTION
    # Prefer the most actionable analytical reason if several apply.
    for preferred in (
        InputRefusalReason.INSUFFICIENT_DATA,
        InputRefusalReason.STALE_FOR_QUESTION,
        InputRefusalReason.UNSUPPORTED_QUESTION,
        InputRefusalReason.INADMISSIBLE_FOR_QUESTION,
    ):
        if preferred in mapped:
            return preferred
    return mapped[0]


def prepare_input_series(
    metric_id: str,
    question_type: AnalyticalQuestionType,
    *,
    candidate: EvidenceCandidate,
    policies: PolicyInput,
    points: Sequence[PreparedPoint],
    reference_time: datetime,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    min_observations: int | None = None,
    freshness_status: str | None = None,
    source_summary: Mapping[str, Any] | None = None,
) -> AnalyticalInputSeries:
    """Prepare one analytical input series, refusing before any computation.

    This is the single entry point WP04 proof tools call to obtain a usable
    series. It:

    1. Maps the reviewed :class:`AnalyticalQuestionType` onto the first-class
       analytical :class:`~premura.engine.policies.QuestionType` of the same
       name through the closed :data:`ANALYTICAL_TO_POLICY_QUESTION` table, then
       runs the **existing** policy evaluator (:func:`evaluate_evidence`) over
       the supplied ``candidate``/``policies``. The evaluator gates on the
       analytical question's own declared rule; no ad-hoc string ever reaches
       it, and the question is never collapsed onto a descriptive shape.
    2. Refuses — returning a series carrying a :class:`RefusalOutcome` and no
       computation points — when evidence is missing, the evaluator finds it
       inadmissible/stale/insufficient, the question is unsupported, or a
       requested parameter bound (``min_observations``) makes the request
       unsupported.
    3. Only on an admissible verdict builds the usable, ordered input series
       with overlap metadata (overlap == usable window for single-series tools).

    Parameters
    ----------
    metric_id:
        Canonical metric identifier this input series is for.
    question_type:
        The reviewed analytical question (closed :class:`AnalyticalQuestionType`).
    candidate:
        The evidence candidate the descriptive evaluator inspects. Callers build
        this from the same warehouse read that produced ``points``.
    policies:
        Family policies for the evaluator (single, sequence, or mapping).
    points:
        Already-read ordered points (the analytical layer never reads the
        warehouse). Order is validated, not assumed.
    reference_time:
        Explicit "now" for the evaluator's recency math (determinism).
    window_start / window_end:
        Usable analysis window. Defaults to the span of ``points`` when omitted.
    min_observations:
        Optional analytical parameter bound. When the usable point count is
        below it, the request is refused as ``unsupported_parameter`` *before*
        computation — this is the parameter-bound refusal the data model calls
        out, kept here rather than inside a statistical method.
    freshness_status:
        Current freshness/admissibility status string for the result envelope.
    source_summary:
        Machine-readable provenance/source summary carried onto the series.
    """
    summary: dict[str, Any] = dict(source_summary or {})

    # Parameter-bound guard is a refusal reason in its own right, but evidence
    # admissibility comes first: a missing/stale/inadmissible input is refused
    # for *that* reason, not silently reclassified as a parameter problem.

    # 1. Map the analytical question onto its first-class policy question type.
    policy_question = ANALYTICAL_TO_POLICY_QUESTION.get(question_type)
    if policy_question is None:
        return _refused_series(
            metric_id,
            question_type,
            RefusalOutcome(
                reason=InputRefusalReason.UNSUPPORTED_QUESTION.value,
                message=(
                    f"Analytical question '{question_type.value}' has no admissibility "
                    f"mapping, so its inputs cannot be prepared."
                ),
                missing_or_bad_inputs=(metric_id,),
            ),
        )

    # No evidence at all: refuse before touching the evaluator or any method.
    if not points:
        return _refused_series(
            metric_id,
            question_type,
            RefusalOutcome(
                reason=InputRefusalReason.EVIDENCE_MISSING.value,
                message=(
                    f"No usable evidence is available for metric '{metric_id}', so the "
                    f"'{question_type.value}' input series cannot be prepared."
                ),
                missing_or_bad_inputs=(metric_id,),
            ),
        )

    # 2. Run the EXISTING evaluator pattern over the supplied evidence.
    result = evaluate_evidence(
        policy_question,
        (candidate,),
        policies,
        reference_time=reference_time,
    )
    if not result.admissible_evidence:
        # The evaluator already produced distinct, machine-readable reasons.
        refusal_source = result.refusal
        reasons: tuple[RejectionReason, ...] = (
            refusal_source.rejection_reasons if refusal_source is not None else ()
        )
        input_reason = _input_refusal_reason(reasons)
        message = (
            refusal_source.message
            if refusal_source is not None
            else (
                f"Evidence for metric '{metric_id}' is not admissible for '{question_type.value}'."
            )
        )
        return _refused_series(
            metric_id,
            question_type,
            RefusalOutcome(
                reason=input_reason.value,
                message=message,
                missing_or_bad_inputs=(metric_id,),
            ),
        )

    # 3. Admissible. Parameter-bound check happens here, still before computation.
    ordered_points = tuple(sorted(points, key=lambda p: p.ts))
    sample_size = len(ordered_points)
    if min_observations is not None and sample_size < min_observations:
        return _refused_series(
            metric_id,
            question_type,
            RefusalOutcome(
                reason=InputRefusalReason.UNSUPPORTED_PARAMETER.value,
                message=(
                    f"The request needs at least {min_observations} usable observations "
                    f"but only {sample_size} are available for metric '{metric_id}'."
                ),
                missing_or_bad_inputs=(metric_id,),
                parameter_name="min_observations",
            ),
        )

    imputed = sum(1 for p in ordered_points if p.is_imputed)
    is_imputed_pct = (imputed / sample_size) * 100.0 if sample_size else 0.0

    resolved_start = window_start if window_start is not None else ordered_points[0].ts
    resolved_end = window_end if window_end is not None else ordered_points[-1].ts

    admissible = result.admissible_evidence[0]
    # Provenance preserved from the evaluator verdict, plus caller-supplied keys.
    summary.setdefault("policy_id", admissible.policy_id)
    summary.setdefault("metric_family", admissible.metric_family)
    if admissible.caveats:
        summary.setdefault("caveats", list(admissible.caveats))

    return AnalyticalInputSeries(
        metric_id=metric_id,
        question_type=question_type,
        points=ordered_points,
        window_start=resolved_start,
        window_end=resolved_end,
        # Single-series tools: overlap window == usable window. Kept explicit so
        # a future multi-input tool can narrow it without a shape change.
        overlap_start=resolved_start,
        overlap_end=resolved_end,
        overlap_sample_size=sample_size,
        sample_size=sample_size,
        is_imputed_pct=is_imputed_pct,
        freshness_status=freshness_status,
        source_summary=summary,
    )


def points_for_computation(series: AnalyticalInputSeries) -> tuple[PreparedPoint, ...]:
    """Return the computation-ready points, or refuse to.

    This is the seam that makes "refusal before computation" structural rather
    than a convention: a proof tool obtains its points *only* through this
    helper, which raises :class:`RuntimeError` for a refused input. A tool that
    forgets to branch on ``series.refusal`` therefore still cannot compute over
    a series it should not.
    """
    if series.refusal is not None:
        raise RuntimeError(
            f"refused analytical input for metric '{series.metric_id}' "
            f"(reason={series.refusal.reason!r}) must not be passed to computation"
        )
    return series.points


# ===========================================================================
# Paired input preparation (WP02 — correlate lagged association, ADR-0008)
# ===========================================================================
#
# This is the *two-series* preparation seam. It deliberately reuses the
# single-series contract above rather than forking it: both inputs are ordinary
# :class:`AnalyticalInputSeries` values produced by :func:`prepare_input_series`,
# so per-series admissibility/freshness/sufficiency is already gated by the WP01
# evidence policy (``evaluate_evidence``). This module does **not** re-run the
# evaluator — it delegates by inspecting each series' ``refusal`` and propagating
# it. The only new gates here are the ones that exist solely because there are
# two series and a pre-registered hypothesis: lag validity, same-day pairing,
# overlap existence, and the raw paired-sample floor.
#
# No coefficient is computed here (that is WP03). The effective-sample-size floor
# (N_eff >= 12) is likewise a compute-time check WP03 owns; WP02 stops at a
# validated, refusal-aware, imputation-annotated paired bundle.


# Lag bands (see ADR-0008): |lag| <= 3 is free;
# 4..14 requires a stated justification the agent supplies; > 14 is refused.
LAG_FREE_ABS_MAX = 3
LAG_JUSTIFIED_ABS_MAX = 14

# The conservative raw paired-sample floor (research note Q3). Below this a
# correlation point estimate carries essentially no information; the paired
# preparer refuses before any coefficient can run. Mirrors the policy-layer
# ``_LAGGED_ASSOCIATION_MIN_PAIRED`` so the same number gates both the
# per-series admissibility evidence and the post-pairing count.
MIN_PAIRED_OBSERVATIONS = 20


class ExpectedDirection(StrEnum):
    """The closed, pre-registered expected sign of an association (ADR-0008).

    The caller must declare this *before* the result exists — declaring the
    expected direction up front is the anti-p-hacking discipline the ADR calls
    out. It is a closed vocabulary so an agent cannot smuggle a free-form
    ``"up a bit"``; WP03 compares the observed sign against this declared value.
    """

    POSITIVE = "positive"
    NEGATIVE = "negative"


class PairedInputRefusalReason(StrEnum):
    """Why a *paired* analytical input is unusable, before any computation.

    These are the paired-stage reasons, distinct from the single-series
    :class:`InputRefusalReason` so an agent can branch on exactly what failed in
    the two-series alignment. When a *constituent* series is itself refused, the
    paired refusal propagates that series' :class:`InputRefusalReason` verbatim
    (admissibility is the WP01 policy's job, never reimplemented here); these
    paired reasons cover only the gates that exist because there are two series
    and a pre-registered hypothesis.
    """

    MISSING_HYPOTHESIS = "missing_hypothesis"
    """No pre-registered hypothesis was supplied, or it is malformed."""

    INVALID_LAG = "invalid_lag"
    """The requested lag is outside the supported band (``abs(lag) > 14``)."""

    MISSING_LAG_JUSTIFICATION = "missing_lag_justification"
    """A 4..14 day lag was requested without the required justification."""

    NO_PAIRED_OVERLAP = "no_paired_overlap"
    """Zero observations pair on the same calendar day after applying the lag."""

    WEAK_PAIRED_SUPPORT = "weak_paired_support"
    """Fewer than :data:`MIN_PAIRED_OBSERVATIONS` paired days remain."""


@dataclass(frozen=True)
class PreRegisteredAssociationHypothesis:
    """The caller's declared question, recorded before computation (data-model).

    A correlate call is *pre-registered*: the metric pair, the integer-day lag,
    and the expected direction are mandatory inputs fixed before the result
    exists. ``lag_justification`` is required only for a 4..14 day lag; common
    cause candidates stay open and caller-supplied (never an enumerated
    built-in catalog), per "guide, don't enumerate".
    """

    left_metric_id: str
    right_metric_id: str
    lag_days: int
    expected_direction: ExpectedDirection
    lag_justification: str | None = None
    common_cause_candidates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Normalise candidate tuple so the frozen shape stays hashable/JSON-safe.
        object.__setattr__(self, "common_cause_candidates", tuple(self.common_cause_candidates))

    def validate(self) -> PreRegisteredAssociationHypothesis:
        """Reject a malformed hypothesis. Returns ``self`` for fluent use.

        Enforces the lag bands here (the typed preparation contract), so an
        invalid hypothesis is caught before any pairing is attempted:

        * both metric identifiers non-empty;
        * ``expected_direction`` is a real :class:`ExpectedDirection`;
        * ``lag_days`` is an integer;
        * ``abs(lag_days) <= 3`` is free; ``4..14`` requires
          ``lag_justification``; ``> 14`` is refused.
        """
        if not self.left_metric_id or not self.left_metric_id.strip():
            raise ValueError("PreRegisteredAssociationHypothesis.left_metric_id must be non-empty")
        if not self.right_metric_id or not self.right_metric_id.strip():
            raise ValueError("PreRegisteredAssociationHypothesis.right_metric_id must be non-empty")
        if not isinstance(self.expected_direction, ExpectedDirection):
            raise ValueError(
                "PreRegisteredAssociationHypothesis.expected_direction must be an "
                f"ExpectedDirection value, got {self.expected_direction!r}"
            )
        if isinstance(self.lag_days, bool) or not isinstance(self.lag_days, int):
            raise ValueError(
                "PreRegisteredAssociationHypothesis.lag_days must be a whole-day integer"
            )
        magnitude = abs(self.lag_days)
        if magnitude > LAG_JUSTIFIED_ABS_MAX:
            raise ValueError(
                f"lag_days={self.lag_days} exceeds the supported band "
                f"(abs(lag) <= {LAG_JUSTIFIED_ABS_MAX}); a larger lag is refused"
            )
        if magnitude > LAG_FREE_ABS_MAX and not (
            self.lag_justification and self.lag_justification.strip()
        ):
            raise ValueError(
                f"lag_days={self.lag_days} (abs(lag) in "
                f"{LAG_FREE_ABS_MAX + 1}..{LAG_JUSTIFIED_ABS_MAX}) requires a "
                "lag_justification supplied by the caller"
            )
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_metric_id": self.left_metric_id,
            "right_metric_id": self.right_metric_id,
            "lag_days": self.lag_days,
            "expected_direction": self.expected_direction.value,
            "lag_justification": self.lag_justification,
            "common_cause_candidates": list(self.common_cause_candidates),
        }


@dataclass(frozen=True)
class PairedObservation:
    """One paired day used for association (data-model → PairedObservation).

    ``paired_day`` is the local calendar day the pair is keyed to (the *left*
    series day after lag alignment). ``left_ts`` / ``right_ts`` keep the source
    timestamps for traceability. A pair counts as imputed when *either* side is
    imputed — that drives both the imputation percentage and the later
    half-weighted effective support WP03 computes.
    """

    paired_day: date
    left_ts: datetime
    right_ts: datetime
    left_value: float
    right_value: float
    left_is_imputed: bool = False
    right_is_imputed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.paired_day, date):
            raise ValueError("PairedObservation.paired_day must be a date")
        if not (isfinite(self.left_value) and isfinite(self.right_value)):
            raise ValueError("PairedObservation values must be finite numbers")

    @property
    def is_imputed(self) -> bool:
        """True when either side of the pair is an imputed (carried-forward) value."""
        return self.left_is_imputed or self.right_is_imputed

    def to_dict(self) -> dict[str, Any]:
        return {
            "paired_day": self.paired_day.isoformat(),
            "left_ts": self.left_ts.isoformat(),
            "right_ts": self.right_ts.isoformat(),
            "left_value": self.left_value,
            "right_value": self.right_value,
            "left_is_imputed": self.left_is_imputed,
            "right_is_imputed": self.right_is_imputed,
        }


@dataclass(frozen=True)
class PairedAnalyticalInput:
    """The two-series post-admissibility input consumed by ``correlate`` (WP03).

    Exactly one of two states, distinguished by ``refusal``:

    * **usable** (``refusal is None``) — ``pairs`` are ordered by paired day and
      computation-ready, and the overlap metadata is narrowed to the actual
      paired days. This is the only state in which
      :func:`paired_points_for_computation` returns pairs.
    * **refused** (``refusal is not None``) — carries a first-class
      :class:`RefusalOutcome` and **no** pairs and no overlap sample size, so a
      coefficient can never run over an input that should not be analyzed.

    No coefficient lives here. The structural guarantee mirrors the single-series
    :class:`AnalyticalInputSeries`: refusal short-circuits before computation.
    """

    left_metric_id: str
    right_metric_id: str
    question_type: AnalyticalQuestionType
    pairs: tuple[PairedObservation, ...] = ()
    window_start: date | None = None
    window_end: date | None = None
    overlap_start: date | None = None
    overlap_end: date | None = None
    overlap_sample_size: int = 0
    is_imputed_pct: float = 0.0
    freshness_status: str | None = None
    source_summary: Mapping[str, Any] = field(default_factory=dict)
    refusal: RefusalOutcome | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("left_metric_id", self.left_metric_id),
            ("right_metric_id", self.right_metric_id),
        ):
            if not value or not value.strip():
                raise ValueError(f"PairedAnalyticalInput.{name} must be a non-empty string")
        if not isinstance(self.question_type, AnalyticalQuestionType):
            raise ValueError(
                "PairedAnalyticalInput.question_type must be an AnalyticalQuestionType value, "
                f"got {self.question_type!r}"
            )
        object.__setattr__(self, "source_summary", dict(self.source_summary))

        if self.refusal is not None:
            self.refusal.validate()
            if self.pairs:
                raise ValueError("a refused paired analytical input must not carry pairs")
            if self.overlap_sample_size:
                raise ValueError("a refused paired analytical input must not report a sample size")
            return

        # Usable invariants.
        if not (0.0 <= self.is_imputed_pct <= 100.0):
            raise ValueError("PairedAnalyticalInput.is_imputed_pct must be in [0.0, 100.0]")
        ordered_days = [p.paired_day for p in self.pairs]
        if ordered_days != sorted(ordered_days):
            raise ValueError("PairedAnalyticalInput.pairs must be ordered by paired day")
        if self.overlap_sample_size != len(self.pairs):
            raise ValueError(
                "PairedAnalyticalInput.overlap_sample_size must match the number of pairs"
            )
        if (
            self.window_start is None
            or self.window_end is None
            or self.overlap_start is None
            or self.overlap_end is None
        ):
            raise ValueError(
                "a usable PairedAnalyticalInput must populate its window/overlap metadata"
            )
        if self.window_start > self.window_end:
            raise ValueError("PairedAnalyticalInput.window_start must not be after window_end")
        if self.overlap_start > self.overlap_end:
            raise ValueError("PairedAnalyticalInput.overlap_start must not be after overlap_end")

    @property
    def is_usable(self) -> bool:
        """True when both inputs were admissible and the pair set passed the floor."""
        return self.refusal is None

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe summary (dates rendered ISO-8601). Byte-stable."""
        return {
            "left_metric_id": self.left_metric_id,
            "right_metric_id": self.right_metric_id,
            "question_type": self.question_type.value,
            "pairs": [p.to_dict() for p in self.pairs],
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "overlap_start": self.overlap_start.isoformat() if self.overlap_start else None,
            "overlap_end": self.overlap_end.isoformat() if self.overlap_end else None,
            "overlap_sample_size": self.overlap_sample_size,
            "is_imputed_pct": self.is_imputed_pct,
            "freshness_status": self.freshness_status,
            "source_summary": dict(self.source_summary),
            "refusal": self.refusal.to_dict() if self.refusal is not None else None,
        }


def _refused_paired(
    refusal: RefusalOutcome,
    *,
    left_metric_id: str,
    right_metric_id: str,
) -> PairedAnalyticalInput:
    return PairedAnalyticalInput(
        left_metric_id=left_metric_id,
        right_metric_id=right_metric_id,
        question_type=AnalyticalQuestionType.LAGGED_ASSOCIATION,
        refusal=refusal,
    )


def _series_source_summary(series: AnalyticalInputSeries) -> dict[str, Any]:
    """A JSON-safe per-series provenance block for the paired source summary."""
    return {
        "metric_id": series.metric_id,
        "sample_size": series.sample_size,
        "freshness_status": series.freshness_status,
        "policy_id": series.source_summary.get("policy_id"),
        "metric_family": series.source_summary.get("metric_family"),
    }


def prepare_paired_input(
    left_series: AnalyticalInputSeries,
    right_series: AnalyticalInputSeries,
    hypothesis: PreRegisteredAssociationHypothesis,
    *,
    min_paired_observations: int = MIN_PAIRED_OBSERVATIONS,
) -> PairedAnalyticalInput:
    """Prepare a paired analytical input from two usable series + a hypothesis.

    The single seam ``correlate`` (WP03) and its MCP wrapper (WP04) call. It:

    1. Refuses if the pre-registered hypothesis is missing or malformed (invalid
       lag / missing required justification) — returned as a structured
       :class:`RefusalOutcome` envelope, never a raised exception.
    2. Refuses if *either* constituent series is itself refused, **propagating
       that series' admissibility reason verbatim** — the WP01 evidence policy
       already decided admissibility/freshness/sufficiency when the series was
       prepared, so this never re-runs or reimplements the evaluator.
    3. Applies the caller-declared integer-day lag to the **right** (responding)
       series, then pairs observations that fall on the same local calendar day.
       The lag is asymmetric and directional — never a tolerance window and never
       a scan. The hypothesis reads "left at day D associates with right at day
       D + lag", so a right observation taken on day ``D + lag`` aligns onto the
       left day ``D``; the pair is keyed to the left day.
    4. Refuses when zero pairs remain, or when the raw paired count is below
       ``min_paired_observations`` (the conservative paired-sample floor).
    5. Otherwise returns a usable bundle with overlap metadata narrowed to the
       actual paired days, the imputed-pair percentage, and a paired source
       summary that records both inputs and the lag (enough to reproduce the
       pair set). No coefficient is computed.

    This reads no warehouse, calls no network, and holds no clock — the only
    "now" the layer ever needed was consumed upstream by ``prepare_input_series``.
    """
    left_metric = left_series.metric_id
    right_metric = right_series.metric_id

    # 1. Hypothesis presence + validity (the typed preparation contract).
    if hypothesis is None:
        return _refused_paired(
            RefusalOutcome(
                reason=PairedInputRefusalReason.MISSING_HYPOTHESIS.value,
                message=(
                    "A pre-registered association hypothesis (metric pair, lag, and "
                    "expected direction) is required before a paired input can be prepared."
                ),
                missing_or_bad_inputs=(left_metric, right_metric),
            ),
            left_metric_id=left_metric,
            right_metric_id=right_metric,
        )
    try:
        hypothesis.validate()
    except ValueError as exc:
        message = str(exc)
        lower = message.lower()
        if "justification" in lower:
            reason = PairedInputRefusalReason.MISSING_LAG_JUSTIFICATION
        elif "lag" in lower:
            reason = PairedInputRefusalReason.INVALID_LAG
        else:
            reason = PairedInputRefusalReason.MISSING_HYPOTHESIS
        parameter_name = (
            "lag_days" if reason is not PairedInputRefusalReason.MISSING_HYPOTHESIS else None
        )
        return _refused_paired(
            RefusalOutcome(
                reason=reason.value,
                message=message,
                missing_or_bad_inputs=(left_metric, right_metric),
                parameter_name=parameter_name,
            ),
            left_metric_id=left_metric,
            right_metric_id=right_metric,
        )

    # 2. Delegate per-series admissibility to the WP01 evidence policy: a series
    #    is already refused if the policy found it inadmissible/stale/sparse. We
    #    propagate that verdict rather than re-deciding it here.
    for series in (left_series, right_series):
        if series.refusal is not None:
            src = series.refusal
            return _refused_paired(
                RefusalOutcome(
                    reason=src.reason,
                    message=(
                        f"Paired input cannot be prepared: the series for metric "
                        f"'{series.metric_id}' is not admissible — {src.message}"
                    ),
                    missing_or_bad_inputs=src.missing_or_bad_inputs or (series.metric_id,),
                    parameter_name=src.parameter_name,
                ),
                left_metric_id=left_metric,
                right_metric_id=right_metric,
            )

    # 3. Same-LOCAL-day pairing after the caller-declared lag. Each point's local
    #    calendar day is resolved from its naive-UTC ts plus its stored local_tz
    #    (DRIFT-1: keying on the UTC day shifted near-midnight observations onto
    #    the wrong day for non-UTC operators). The right (responding) series is
    #    shifted earlier by lag_days so its local day D+lag aligns onto the left
    #    local day D; pairs are keyed to the left local day. ``left_ts``/
    #    ``right_ts`` stay the UTC instants for provenance. Iteration is
    #    time-ordered and last-write-wins per local day, so a repeated day stays
    #    deterministic. We track which points used a UTC fallback (missing or
    #    unparseable local_tz) so the count can be surfaced honestly downstream.
    lag = hypothesis.lag_days
    left_by_day: dict[date, tuple[PreparedPoint, bool]] = {}
    for point in left_series.points:
        local_day, used_fallback = local_calendar_day(point.ts, point.local_tz)
        left_by_day[local_day] = (point, used_fallback)
    right_by_aligned_day: dict[date, tuple[PreparedPoint, bool]] = {}
    for point in right_series.points:
        local_day, used_fallback = local_calendar_day(point.ts, point.local_tz)
        aligned = local_day - timedelta(days=lag)
        right_by_aligned_day[aligned] = (point, used_fallback)

    shared_days = sorted(set(left_by_day) & set(right_by_aligned_day))
    pairs = tuple(
        PairedObservation(
            paired_day=day,
            left_ts=left_by_day[day][0].ts,
            right_ts=right_by_aligned_day[day][0].ts,
            left_value=left_by_day[day][0].value,
            right_value=right_by_aligned_day[day][0].value,
            left_is_imputed=left_by_day[day][0].is_imputed,
            right_is_imputed=right_by_aligned_day[day][0].is_imputed,
        )
        for day in shared_days
    )
    # A paired day "used the UTC fallback" when EITHER contributing side could not
    # resolve its local day from local_tz; its calendar-day key may be off by one.
    utc_fallback_paired_days = sum(
        1 for day in shared_days if left_by_day[day][1] or right_by_aligned_day[day][1]
    )

    # 4. No-overlap and weak-support refusals (before any computation).
    if not pairs:
        return _refused_paired(
            RefusalOutcome(
                reason=PairedInputRefusalReason.NO_PAIRED_OVERLAP.value,
                message=(
                    f"No observations of '{left_metric}' and '{right_metric}' fall on the "
                    f"same local calendar day after applying a lag of {lag} day(s); there "
                    "is nothing to correlate."
                ),
                missing_or_bad_inputs=(left_metric, right_metric),
            ),
            left_metric_id=left_metric,
            right_metric_id=right_metric,
        )
    if len(pairs) < min_paired_observations:
        return _refused_paired(
            RefusalOutcome(
                reason=PairedInputRefusalReason.WEAK_PAIRED_SUPPORT.value,
                message=(
                    f"Only {len(pairs)} paired day(s) remain after lag alignment, below the "
                    f"minimum of {min_paired_observations} required for a usable association."
                ),
                missing_or_bad_inputs=(left_metric, right_metric),
                parameter_name="min_paired_observations",
            ),
            left_metric_id=left_metric,
            right_metric_id=right_metric,
        )

    # 5. Usable bundle. Overlap metadata is narrowed to the actual paired days;
    #    the window is the same paired span (the usable analysis window for the
    #    correlation run).
    imputed_pairs = sum(1 for p in pairs if p.is_imputed)
    is_imputed_pct = (imputed_pairs / len(pairs)) * 100.0
    overlap_start = pairs[0].paired_day
    overlap_end = pairs[-1].paired_day

    freshness = (
        "; ".join(
            f"{s.metric_id}={s.freshness_status}"
            for s in (left_series, right_series)
            if s.freshness_status
        )
        or None
    )

    source_summary: dict[str, Any] = {
        "lag_days": lag,
        "expected_direction": hypothesis.expected_direction.value,
        "lag_justification": hypothesis.lag_justification,
        "common_cause_candidates": list(hypothesis.common_cause_candidates),
        # Paired days that fell back to the UTC calendar day because at least one
        # contributing observation lacked a parseable local_tz. The WP03 correlate
        # tool reads this to emit an honest caveat (those days may be off by one
        # calendar day); 0 means every paired day resolved a real local day.
        "utc_fallback_paired_days": utc_fallback_paired_days,
        "left": _series_source_summary(left_series),
        "right": _series_source_summary(right_series),
    }

    return PairedAnalyticalInput(
        left_metric_id=left_metric,
        right_metric_id=right_metric,
        question_type=AnalyticalQuestionType.LAGGED_ASSOCIATION,
        pairs=pairs,
        window_start=overlap_start,
        window_end=overlap_end,
        overlap_start=overlap_start,
        overlap_end=overlap_end,
        overlap_sample_size=len(pairs),
        is_imputed_pct=is_imputed_pct,
        freshness_status=freshness,
        source_summary=source_summary,
    )


def paired_points_for_computation(
    paired: PairedAnalyticalInput,
) -> tuple[PairedObservation, ...]:
    """Return the computation-ready pairs, or refuse to.

    The paired twin of :func:`points_for_computation`: a refused paired input
    raises rather than hand back pairs, so the WP03 coefficient step cannot
    accidentally compute over an input that did not pass the paired gates even if
    it forgets to branch on ``paired.refusal``.
    """
    if paired.refusal is not None:
        raise RuntimeError(
            f"refused paired analytical input for "
            f"'{paired.left_metric_id}'/'{paired.right_metric_id}' "
            f"(reason={paired.refusal.reason!r}) must not be passed to computation"
        )
    return paired.pairs
