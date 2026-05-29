"""Deterministic Stage 2 evidence evaluator (WP02).

This module owns *all* branching for evidence admissibility. The policy
declarations from :mod:`premura.engine.policies._model` are **parameters
only** — closed enum values, duration/count thresholds, required provenance
fields, and caveat strings. They never carry executable logic; this evaluator
is the single place that turns those parameters into outcomes. That separation
is the main guardrail against a future policy mini-language (see
``evidence-policy-contract.md`` CR-003).

The evaluator is *pure* over its supplied arguments:

* It reads nothing from DuckDB, the ``hp.*`` warehouse tables, PubMed, or any
  network service. Callers pass explicit :class:`EvidenceCandidate` data.
* It never calls :func:`datetime.now`. Recency is judged against an explicit
  ``reference_time`` argument, so identical inputs always produce identical
  results (determinism).
* It never emits diagnosis, treatment/medication advice, emergency guidance,
  population norms, p-values, confidence intervals, or causal claims. Messages
  are built from fixed plain-English templates plus declared caveat strings.

The public entrypoint is :func:`evaluate_evidence`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from premura.engine.policies._model import (
    Admissibility,
    EvaluationResult,
    EvidenceCandidate,
    EvidenceOutcome,
    EvidenceStatus,
    FreshnessMode,
    FreshnessRule,
    MetricFamilyPolicy,
    MissingDataBehavior,
    QuestionRule,
    QuestionType,
    RefusalMode,
    RejectionReason,
    SufficiencyRule,
)

__all__ = ["evaluate_evidence"]


# A mapping from metric family to its policy, or a flat iterable of policies.
PolicyInput = Mapping[str, MetricFamilyPolicy] | MetricFamilyPolicy | Sequence[MetricFamilyPolicy]


def _normalize_policies(policies: PolicyInput) -> dict[str, MetricFamilyPolicy]:
    """Build a deterministic family -> policy lookup from supported inputs.

    Accepts a single policy, a sequence of policies, or an explicit mapping.
    Lookup is keyed on :attr:`MetricFamilyPolicy.metric_family` so the evaluator
    never has to infer a family from a metric name.
    """
    if isinstance(policies, MetricFamilyPolicy):
        return {policies.metric_family: policies}
    if isinstance(policies, Mapping):
        # Trust caller keys but re-key on metric_family would risk hiding a
        # mismatch; keep the caller's mapping as-is.
        return dict(policies)
    # Sequence of policies.
    lookup: dict[str, MetricFamilyPolicy] = {}
    for policy in policies:
        lookup[policy.metric_family] = policy
    return lookup


def _provenance(candidate: EvidenceCandidate) -> dict[str, Any]:
    """Preserve candidate provenance verbatim on every outcome."""
    return {
        "metric_id": candidate.metric_id,
        "metric_family": candidate.metric_family,
        "value_kind": candidate.value_kind,
        "observed_at": candidate.observed_at,
        "source_id": candidate.source_id,
        "point_count": candidate.point_count,
        "coverage_pct": candidate.coverage_pct,
        "context": dict(candidate.context),
    }


def _unsupported_policy_outcome(
    candidate: EvidenceCandidate,
    question_type: QuestionType,
    *,
    detail: str,
    policy_id: str,
) -> EvidenceOutcome:
    """Reject a candidate whose family has no usable policy/rule."""
    return EvidenceOutcome(
        status=EvidenceStatus.REJECTED,
        question_type=question_type,
        metric_family=candidate.metric_family,
        policy_id=policy_id,
        message=(
            f"No applicable evidence policy for metric family "
            f"'{candidate.metric_family}' and question '{question_type.value}': "
            f"{detail}."
        ),
        rejection_reasons=(RejectionReason.UNSUPPORTED_POLICY,),
        provenance=_provenance(candidate),
    )


def _declared_caveats(policy: MetricFamilyPolicy, rule: QuestionRule) -> tuple[str, ...]:
    """Standing policy caveats plus question-specific caveats, de-duplicated."""
    refusal_caveats: tuple[str, ...]
    if rule.refusal_mode is RefusalMode.OFFER_WITH_CAVEATS:
        refusal_caveats = (
            "This evidence may still be useful as context, but it is not strong "
            "enough for the requested answer.",
        )
    elif rule.refusal_mode is RefusalMode.SUGGEST_DIFFERENT_QUESTION:
        refusal_caveats = (
            "This evidence may fit a different question type better than the one requested.",
        )
    else:
        refusal_caveats = ()
    return tuple(dict.fromkeys((*policy.standing_caveats, *rule.caveats, *refusal_caveats)))


def _missing_context_fields(
    candidate: EvidenceCandidate,
    policy: MetricFamilyPolicy,
    rule: QuestionRule,
) -> tuple[str, ...]:
    """Return declared required context/provenance fields the candidate lacks.

    ``observed_at`` and ``source_id`` are checked against the candidate's own
    attributes; any other required field is looked up in ``candidate.context``.
    Only declared fields are checked — the evaluator never invents requirements.
    """
    required = tuple(policy.required_provenance) + tuple(rule.required_context)
    missing: list[str] = []
    for fieldname in required:
        if fieldname == "observed_at":
            if candidate.observed_at is None:
                missing.append(fieldname)
        elif fieldname == "source_id":
            if candidate.source_id is None:
                missing.append(fieldname)
        elif fieldname not in candidate.context or candidate.context[fieldname] is None:
            missing.append(fieldname)
    return tuple(missing)


def _freshness_outcome(
    candidate: EvidenceCandidate,
    question_type: QuestionType,
    policy: MetricFamilyPolicy,
    rule: QuestionRule,
    freshness: FreshnessRule,
    *,
    reference_time: Any,
) -> tuple[EvidenceOutcome | None, tuple[str, ...]]:
    """Evaluate recency for one candidate.

    Returns ``(rejection_outcome_or_None, freshness_caveats)``. When the first
    element is ``None`` the candidate passes freshness (possibly with caveats);
    otherwise it is a rejected outcome to surface as-is.
    """
    caveats: list[str] = list(_declared_caveats(policy, rule))

    # caveat_only never silently passes: it always attaches its caveats and
    # never rejects for age.
    if freshness.mode is FreshnessMode.CAVEAT_ONLY:
        return None, tuple(caveats)

    # valid_until_superseded: effective-dated evidence is not rejected for age.
    if freshness.mode is FreshnessMode.VALID_UNTIL_SUPERSEDED:
        return None, tuple(caveats)

    # baseline_relative: recency is not the gate (sufficiency carries the
    # weight). Require a caveat but do not reject for age unless a window is
    # additionally declared.
    if freshness.mode is FreshnessMode.BASELINE_RELATIVE and freshness.max_age is None:
        return None, tuple(caveats)

    # Modes below need an age comparison, which needs a timestamp. A missing
    # timestamp is handled by the required-context check upstream, but guard
    # here too so we never compare against None.
    if candidate.observed_at is None:
        outcome = EvidenceOutcome(
            status=EvidenceStatus.REJECTED,
            question_type=question_type,
            metric_family=candidate.metric_family,
            policy_id=policy.policy_id,
            message=(
                f"Evidence for '{candidate.metric_family}' has no timestamp, so "
                f"its recency cannot be judged for question "
                f"'{question_type.value}'."
            ),
            rejection_reasons=(RejectionReason.MISSING_TIMESTAMP,),
            caveats=tuple(caveats),
            provenance=_provenance(candidate),
        )
        return outcome, tuple(caveats)

    age = reference_time - candidate.observed_at

    if freshness.mode is FreshnessMode.STRICT_WINDOW:
        # max_age is guaranteed present by FreshnessRule validation.
        assert freshness.max_age is not None
        if age > freshness.max_age:
            outcome = EvidenceOutcome(
                status=EvidenceStatus.REJECTED,
                question_type=question_type,
                metric_family=candidate.metric_family,
                policy_id=policy.policy_id,
                message=(
                    f"Evidence for '{candidate.metric_family}' is older than the "
                    f"allowed window for question '{question_type.value}', so it "
                    f"is not current enough to use."
                ),
                rejection_reasons=(RejectionReason.STALE_FOR_QUESTION,),
                caveats=tuple(caveats),
                provenance=_provenance(candidate),
            )
            return outcome, tuple(caveats)
        return None, tuple(caveats)

    if freshness.mode is FreshnessMode.PREFERRED_WINDOW:
        # Preferred windows never hard-reject for age: outside the preferred
        # window we attach a caveat rather than pretending the value is current.
        preferred = freshness.preferred_age or freshness.max_age
        if preferred is not None and age > preferred:
            caveats.append(
                "This evidence is older than the preferred recency window for "
                "this question; treat it as background rather than current."
            )
        return None, tuple(caveats)

    # baseline_relative WITH a declared max_age behaves like a strict window.
    if freshness.mode is FreshnessMode.BASELINE_RELATIVE:
        assert freshness.max_age is not None
        if age > freshness.max_age:
            outcome = EvidenceOutcome(
                status=EvidenceStatus.REJECTED,
                question_type=question_type,
                metric_family=candidate.metric_family,
                policy_id=policy.policy_id,
                message=(
                    f"Baseline evidence for '{candidate.metric_family}' is older "
                    f"than the allowed window for question "
                    f"'{question_type.value}', so it cannot anchor this question."
                ),
                rejection_reasons=(RejectionReason.STALE_FOR_QUESTION,),
                caveats=tuple(caveats),
                provenance=_provenance(candidate),
            )
            return outcome, tuple(caveats)
        return None, tuple(caveats)

    return None, tuple(caveats)


def _sufficiency_outcome(
    candidate: EvidenceCandidate,
    question_type: QuestionType,
    policy: MetricFamilyPolicy,
    sufficiency: SufficiencyRule,
    *,
    base_caveats: tuple[str, ...],
) -> EvidenceOutcome | None:
    """Evaluate evidence density/coverage for one candidate.

    Returns an ``insufficient`` outcome when the candidate is too sparse, else
    ``None``. ``too_sparse`` is kept distinct from ``stale_for_question``.
    """
    reasons: list[RejectionReason] = []
    problems: list[str] = []

    if sufficiency.min_observations is not None:
        if candidate.point_count is None or candidate.point_count < sufficiency.min_observations:
            reasons.append(RejectionReason.TOO_SPARSE)
            problems.append("not enough observations")

    if sufficiency.min_coverage_pct is not None:
        if candidate.coverage_pct is None or candidate.coverage_pct < sufficiency.min_coverage_pct:
            reasons.append(RejectionReason.TOO_SPARSE)
            problems.append("insufficient time coverage")

    if not reasons:
        return None

    # Deduplicate reasons while preserving order (both checks share TOO_SPARSE).
    distinct_reasons = tuple(dict.fromkeys(reasons))
    problem_text = " and ".join(dict.fromkeys(problems))
    return EvidenceOutcome(
        status=EvidenceStatus.INSUFFICIENT,
        question_type=question_type,
        metric_family=candidate.metric_family,
        policy_id=policy.policy_id,
        message=(
            f"Evidence for '{candidate.metric_family}' is too sparse for "
            f"question '{question_type.value}' ({problem_text}); there is not "
            f"enough data to answer reliably."
        ),
        rejection_reasons=distinct_reasons,
        caveats=base_caveats,
        provenance=_provenance(candidate),
    )


def _inadmissible_outcome(
    candidate: EvidenceCandidate,
    question_type: QuestionType,
    policy: MetricFamilyPolicy,
    rule: QuestionRule,
) -> EvidenceOutcome:
    """Reject a candidate whose family is declared inadmissible for the question.

    Uses the rule's configured ``default_rejection_reasons`` (guaranteed
    non-empty by ``QuestionRule`` validation for inadmissible rules); if none
    is the dedicated wrong-evidence-kind reason it still surfaces the declared
    reasons verbatim.
    """
    reasons = tuple(rule.default_rejection_reasons)
    return EvidenceOutcome(
        status=EvidenceStatus.REJECTED,
        question_type=question_type,
        metric_family=candidate.metric_family,
        policy_id=policy.policy_id,
        message=(
            f"Evidence for '{candidate.metric_family}' is not the right kind of "
            f"evidence to answer question '{question_type.value}'."
        ),
        rejection_reasons=reasons,
        caveats=_declared_caveats(policy, rule),
        provenance=_provenance(candidate),
    )


def _missing_context_outcome(
    candidate: EvidenceCandidate,
    question_type: QuestionType,
    policy: MetricFamilyPolicy,
    rule: QuestionRule,
    missing: tuple[str, ...],
) -> EvidenceOutcome:
    """Reject a candidate missing declared timestamp/context provenance."""
    # A missing timestamp gets its own distinct reason; other missing fields
    # are missing_required_context. Keep both reasons distinct when both apply.
    reasons: list[RejectionReason] = []
    if "observed_at" in missing:
        reasons.append(RejectionReason.MISSING_TIMESTAMP)
    if any(name != "observed_at" for name in missing):
        reasons.append(RejectionReason.MISSING_REQUIRED_CONTEXT)
    field_list = ", ".join(missing)
    return EvidenceOutcome(
        status=EvidenceStatus.REJECTED,
        question_type=question_type,
        metric_family=candidate.metric_family,
        policy_id=policy.policy_id,
        message=(
            f"Evidence for '{candidate.metric_family}' is missing required "
            f"information ({field_list}) needed to evaluate question "
            f"'{question_type.value}'."
        ),
        rejection_reasons=tuple(reasons),
        caveats=_declared_caveats(policy, rule),
        provenance=_provenance(candidate),
    )


def _wrong_metric_outcome(
    candidate: EvidenceCandidate,
    question_type: QuestionType,
    policy: MetricFamilyPolicy,
    rule: QuestionRule,
) -> EvidenceOutcome:
    """Reject a candidate whose metric is outside the family's declared scope."""
    return EvidenceOutcome(
        status=EvidenceStatus.REJECTED,
        question_type=question_type,
        metric_family=candidate.metric_family,
        policy_id=policy.policy_id,
        message=(
            f"Metric '{candidate.metric_id}' is not declared as evidence for "
            f"metric family '{candidate.metric_family}', so it is not used for "
            f"question '{question_type.value}'."
        ),
        rejection_reasons=(RejectionReason.WRONG_EVIDENCE_KIND,),
        caveats=_declared_caveats(policy, rule),
        provenance=_provenance(candidate),
    )


def _evaluate_candidate(
    candidate: EvidenceCandidate,
    question_type: QuestionType,
    lookup: Mapping[str, MetricFamilyPolicy],
    *,
    reference_time: Any,
) -> EvidenceOutcome:
    """Evaluate one candidate to exactly one outcome. All branching lives here."""
    policy = lookup.get(candidate.metric_family)
    if policy is None:
        return _unsupported_policy_outcome(
            candidate,
            question_type,
            detail="no policy is registered for this family",
            policy_id="",
        )

    rule = policy.question_rules.get(question_type)
    if rule is None:
        return _unsupported_policy_outcome(
            candidate,
            question_type,
            detail="the policy declares no rule for this question type",
            policy_id=policy.policy_id,
        )

    if policy.applies_to_metrics and candidate.metric_id not in policy.applies_to_metrics:
        return _wrong_metric_outcome(candidate, question_type, policy, rule)

    # Inadmissible families are wrong-evidence-kind for this question.
    if rule.admissibility is Admissibility.INADMISSIBLE:
        return _inadmissible_outcome(candidate, question_type, policy, rule)

    # Required timestamp / context provenance must be present before we judge
    # freshness or sufficiency. A value alone is not enough.
    missing = _missing_context_fields(candidate, policy, rule)
    if missing:
        return _missing_context_outcome(candidate, question_type, policy, rule, missing)

    # Freshness.
    freshness_caveats: tuple[str, ...] = _declared_caveats(policy, rule)
    if rule.freshness is not None:
        freshness_reject, freshness_caveats = _freshness_outcome(
            candidate,
            question_type,
            policy,
            rule,
            rule.freshness,
            reference_time=reference_time,
        )
        if freshness_reject is not None:
            return freshness_reject

    # Sufficiency.
    if rule.sufficiency is not None:
        insufficient = _sufficiency_outcome(
            candidate,
            question_type,
            policy,
            rule.sufficiency,
            base_caveats=freshness_caveats,
        )
        if insufficient is not None:
            # missing_data_behavior may downgrade a hard insufficiency into a
            # caveat-only pass when the rule says the density is not required.
            if rule.sufficiency.missing_data_behavior is MissingDataBehavior.IGNORE_IF_NOT_REQUIRED:
                pass  # fall through to admissible below; density was optional
            elif rule.sufficiency.missing_data_behavior is MissingDataBehavior.CAVEAT:
                freshness_caveats = tuple(
                    dict.fromkeys(
                        (
                            *freshness_caveats,
                            "Evidence density is below the preferred threshold for "
                            "this question; treat the result as caveated context.",
                        )
                    )
                )
            else:
                return insufficient

    # Admissible. Standing caveats from the policy always travel with the
    # result, plus any freshness/question caveats accumulated above.
    caveats = tuple(dict.fromkeys(freshness_caveats))
    return EvidenceOutcome(
        status=EvidenceStatus.ADMISSIBLE,
        question_type=question_type,
        metric_family=candidate.metric_family,
        policy_id=policy.policy_id,
        message=(
            f"Evidence for '{candidate.metric_family}' is admissible for "
            f"question '{question_type.value}'."
        ),
        caveats=caveats,
        provenance=_provenance(candidate),
    )


def _build_refusal(
    question_type: QuestionType,
    rejected: Sequence[EvidenceOutcome],
    insufficient: Sequence[EvidenceOutcome],
) -> EvidenceOutcome:
    """Derive a refusal outcome from the absence of admissible evidence.

    This is not a hand-coded special case: it summarizes the distinct reasons
    seen across all evaluated candidates. The message is plain English and
    non-diagnostic — it describes *why nothing was usable*, never advice.
    """
    reasons: list[RejectionReason] = []
    for outcome in (*rejected, *insufficient):
        for reason in outcome.rejection_reasons:
            if reason not in reasons:
                reasons.append(reason)

    if not reasons:
        # No candidates at all were supplied.
        message = (
            f"No evidence was available to answer question "
            f"'{question_type.value}', so no answer can be given."
        )
        # An outcome requires at least one reason; an empty input is an
        # unsupported request for this question.
        reasons = [RejectionReason.UNSUPPORTED_POLICY]
    else:
        reason_phrases = ", ".join(r.value.replace("_", " ") for r in reasons)
        message = (
            f"No admissible evidence remains for question "
            f"'{question_type.value}', so no answer can be given. "
            f"Reasons across the evidence considered: {reason_phrases}."
        )

    return EvidenceOutcome(
        status=EvidenceStatus.REJECTED,
        question_type=question_type,
        metric_family="",
        policy_id="",
        message=message,
        rejection_reasons=tuple(reasons),
        provenance={},
    )


def evaluate_evidence(
    question_type: QuestionType,
    candidates: Sequence[EvidenceCandidate],
    policies: PolicyInput,
    *,
    reference_time: Any,
) -> EvaluationResult:
    """Evaluate evidence candidates against family policies for one question.

    Parameters
    ----------
    question_type:
        The kind of question being answered (closed :class:`QuestionType`).
    candidates:
        Explicit evidence candidates to evaluate, in priority/display order.
        The evaluator never reads the warehouse — callers pass the data.
    policies:
        A single :class:`MetricFamilyPolicy`, a sequence of them, or a mapping
        from metric family to policy. Lookup is by ``metric_family``.
    reference_time:
        The "now" used for recency comparisons. Passed explicitly so results
        are deterministic; the evaluator never calls :func:`datetime.now`.

    Returns
    -------
    EvaluationResult
        With admissible, rejected, and insufficient outcomes kept in separate
        buckets (each preserving the input order of ``candidates``) and a
        refusal outcome whenever no admissible evidence remains.
    """
    lookup = _normalize_policies(policies)

    admissible: list[EvidenceOutcome] = []
    rejected: list[EvidenceOutcome] = []
    insufficient: list[EvidenceOutcome] = []

    for candidate in candidates:
        outcome = _evaluate_candidate(
            candidate,
            question_type,
            lookup,
            reference_time=reference_time,
        )
        if outcome.status is EvidenceStatus.ADMISSIBLE:
            admissible.append(outcome)
        elif outcome.status is EvidenceStatus.REJECTED:
            rejected.append(outcome)
        else:
            insufficient.append(outcome)

    # Refusal is derived only after every candidate has been evaluated, from
    # the absence of admissible evidence — not a special case for any one input.
    refusal = None
    if not admissible:
        refusal = _build_refusal(question_type, rejected, insufficient)

    return EvaluationResult(
        question_type=question_type,
        admissible_evidence=tuple(admissible),
        rejected_evidence=tuple(rejected),
        insufficient_evidence=tuple(insufficient),
        refusal=refusal,
    )
