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
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

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
    """

    ts: datetime
    value: float
    is_imputed: bool = False


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
