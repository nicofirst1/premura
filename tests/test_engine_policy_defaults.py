"""WP03 tests: built-in family defaults + the lightweight policy registry.

Two things are under test:

1. The defaults demonstrate the *abstraction level* the doctrine demands —
   broad family coverage mapped onto a strictly smaller set of reusable policy
   shapes (not one bespoke clinical rule per family).
2. The registry is deterministic and fails loudly on duplicate identity or
   duplicate family ownership, never silently overwriting.

Smoke tests drive the WP02 evaluator against the built-ins to prove the
end-to-end admissibility behavior the research note calls for.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from premura.engine.policies._defaults import (
    BUILTIN_POLICIES,
    builtin_policies,
)
from premura.engine.policies._evaluator import evaluate_evidence
from premura.engine.policies._model import (
    EvidenceStatus,
    PolicyShape,
    QuestionType,
    RejectionReason,
)
from premura.engine.policies._registry import (
    DuplicatePolicyError,
    PolicyRegistry,
    build_builtin_registry,
)

# A fixed reference time so every recency comparison is deterministic.
NOW = datetime(2026, 5, 29, 12, 0, 0)


# ---------------------------------------------------------------------------
# T014: registry coverage / doctrine tests
# ---------------------------------------------------------------------------


def _family_groups() -> set[str]:
    return {p.metric_family for p in builtin_policies()}


def _shapes() -> set[PolicyShape]:
    return {p.policy_shape for p in builtin_policies()}


def test_builtin_policies_cover_at_least_ten_family_groups() -> None:
    families = _family_groups()
    # No accidental duplicates collapsed the count.
    assert len(families) == len(builtin_policies())
    assert len(families) >= 10, f"need >=10 family groups, got {len(families)}"


def test_builtin_policies_reuse_policy_shapes() -> None:
    """The whole point of the WP: fewer shapes than families.

    If this fails it means someone wrote a bespoke shape per family — the #1
    rejection failure mode.
    """
    families = _family_groups()
    shapes = _shapes()
    assert len(shapes) < len(families), (
        f"policy shapes ({len(shapes)}) must be fewer than family groups "
        f"({len(families)}); a bespoke rule per family is not allowed"
    )


def test_some_shape_is_shared_by_multiple_families() -> None:
    """At least one shape must be reused, proving this is not a 1:1 matrix."""
    counts: dict[PolicyShape, int] = {}
    for policy in builtin_policies():
        counts[policy.policy_shape] = counts.get(policy.policy_shape, 0) + 1
    reused = {shape: n for shape, n in counts.items() if n > 1}
    assert reused, "expected at least one policy shape reused across families"
    # Concretely: long-term control and rolling/slow-trajectory families share.
    assert counts[PolicyShape.INTEGRATED_LONG_TERM_CONTROL] >= 2
    assert counts[PolicyShape.ROLLING_RECENT_PATTERN] >= 2
    assert counts[PolicyShape.SLOW_TRAJECTORY_METHOD_SENSITIVE] >= 2


def test_named_research_family_groups_are_covered() -> None:
    """The >=10 family groups named in the research note are all present."""
    families = _family_groups()
    expected = {
        "stable_profile_facts",
        "acute_spot_measures",
        "home_blood_pressure",
        "cgm",
        "a1c_like_control",
        "lipid_like_control",
        "sparse_lab_panels",
        "weight",
        "body_composition",
        "activity",
        "sleep",
        "hrv_resting_recovery",
    }
    missing = expected - families
    assert not missing, f"missing named family groups: {sorted(missing)}"


def test_hrv_resting_recovery_uses_warehouse_resting_hr_metric_id() -> None:
    registry = build_builtin_registry()
    policy = registry.get("hrv_resting_recovery")
    assert policy is not None
    assert "resting_hr" in policy.applies_to_metrics
    assert "resting_heart_rate" not in policy.applies_to_metrics


def test_no_per_question_duplicate_family_block() -> None:
    """No family is split into one declaration per question type.

    A family-level rule covers all its question types in one declaration; we
    must never see two policies for the same family (which CR-002 forbids and
    which the registry would reject anyway).
    """
    seen: set[str] = set()
    for policy in builtin_policies():
        assert policy.metric_family not in seen, (
            f"family {policy.metric_family!r} declared more than once — use one "
            "family-level policy with per-question rules instead"
        )
        seen.add(policy.metric_family)
        # Each family genuinely declares behavior for multiple questions.
        assert len(policy.question_rules) >= 1


def test_builtins_carry_rationale_and_source_notes() -> None:
    """T013: every built-in is explained (rationale + source notes)."""
    for policy in builtin_policies():
        assert policy.rationale.strip(), f"{policy.policy_id} missing rationale"
        assert policy.source_notes, f"{policy.policy_id} missing source notes"
        for note in policy.source_notes:
            assert note.strip()


def test_caveat_required_shapes_carry_standing_caveats() -> None:
    """Method-sensitive / baseline-relative families always carry caveats."""
    for policy in builtin_policies():
        if policy.policy_shape in (
            PolicyShape.BASELINE_RELATIVE,
            PolicyShape.SLOW_TRAJECTORY_METHOD_SENSITIVE,
        ):
            assert policy.standing_caveats, (
                f"{policy.policy_id} is a caveat-required shape but has no standing caveats"
            )


# ---------------------------------------------------------------------------
# T011: registry behavior tests
# ---------------------------------------------------------------------------


def test_registry_round_trips_and_is_deterministic() -> None:
    registry = build_builtin_registry()
    assert len(registry) == len(BUILTIN_POLICIES)
    # Lookup by family is exact and returns the owning policy.
    cgm = registry.get("cgm")
    assert cgm is not None and cgm.metric_family == "cgm"
    # Deterministic order == registration (declaration) order.
    assert registry.policies() == tuple(BUILTIN_POLICIES)
    assert registry.families() == tuple(p.metric_family for p in BUILTIN_POLICIES)


def test_registry_lookup_is_exact_not_fuzzy() -> None:
    registry = build_builtin_registry()
    assert registry.get("cg") is None  # prefix must not match
    assert registry.get("CGM") is None  # case must not match
    assert registry.get("unknown_family") is None
    assert "cgm" in registry
    assert "nope" not in registry


def test_duplicate_policy_id_fails() -> None:
    registry = PolicyRegistry()
    first = BUILTIN_POLICIES[0]
    registry.register(first)
    # Same id, different family -> still a hard failure.
    clash = replace(first, metric_family="some_other_family")
    with pytest.raises(DuplicatePolicyError, match="duplicate policy_id"):
        registry.register(clash)


def test_duplicate_metric_family_fails() -> None:
    registry = PolicyRegistry()
    first = BUILTIN_POLICIES[0]
    registry.register(first)
    # Same family, different id -> hard failure (no silent overwrite).
    clash = replace(first, policy_id="builtin.different_id.v1")
    with pytest.raises(DuplicatePolicyError, match="duplicate metric-family"):
        registry.register(clash)
    # The original is untouched.
    assert registry.get(first.metric_family) is first


def test_builtins_register_without_collision() -> None:
    """Packaging guard: the shipped built-ins must not collide with each other."""
    registry = PolicyRegistry()
    registry.register_all(BUILTIN_POLICIES)  # must not raise
    assert len(registry) == len(BUILTIN_POLICIES)


# ---------------------------------------------------------------------------
# T015: evaluator smoke tests using the WP02 evaluator
# ---------------------------------------------------------------------------


def _candidate(metric_family: str, **kwargs):  # type: ignore[no-untyped-def]
    from premura.engine.policies._model import EvidenceCandidate

    default_metric_ids = {
        "stable_profile_facts": "date_of_birth",
        "acute_spot_measures": "body_temperature",
        "home_blood_pressure": "systolic_bp",
        "cgm": "glucose_cgm",
        "a1c_like_control": "hba1c",
        "lipid_like_control": "ldl_cholesterol",
        "sparse_lab_panels": "vitamin_d",
        "weight": "body_weight",
        "body_composition": "body_fat_pct",
        "activity": "steps",
        "sleep": "sleep_duration",
        "hrv_resting_recovery": "resting_hr",
    }
    defaults = {
        "metric_id": kwargs.pop(
            "metric_id", default_metric_ids.get(metric_family, f"{metric_family}_metric")
        ),
        "metric_family": metric_family,
        "value_kind": kwargs.pop("value_kind", "scalar"),
    }
    defaults.update(kwargs)
    return EvidenceCandidate(**defaults)


def test_long_term_marker_rejected_for_current_status() -> None:
    registry = build_builtin_registry()
    a1c = _candidate("a1c_like_control", observed_at=NOW - timedelta(days=10))
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [a1c],
        registry.policies(),
        reference_time=NOW,
    )
    assert not result.admissible_evidence
    assert result.rejected_evidence
    assert RejectionReason.WRONG_EVIDENCE_KIND in result.rejected_evidence[0].rejection_reasons
    assert result.refusal is not None


def test_long_term_marker_admitted_for_long_term_control() -> None:
    registry = build_builtin_registry()
    a1c = _candidate("a1c_like_control", observed_at=NOW - timedelta(days=30))
    result = evaluate_evidence(
        QuestionType.LONG_TERM_CONTROL,
        [a1c],
        registry.policies(),
        reference_time=NOW,
    )
    assert result.admissible_evidence
    assert result.admissible_evidence[0].status is EvidenceStatus.ADMISSIBLE


def test_baseline_relative_current_status_rejects_stale_evidence() -> None:
    registry = build_builtin_registry()
    candidate = _candidate(
        "hrv_resting_recovery",
        metric_id="resting_hr",
        observed_at=NOW - timedelta(days=5),
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [candidate],
        registry.policies(),
        reference_time=NOW,
    )
    assert not result.admissible_evidence
    assert result.rejected_evidence
    rejected = result.rejected_evidence[0]
    assert RejectionReason.STALE_FOR_QUESTION in rejected.rejection_reasons
    assert rejected.caveats


def test_profile_fact_not_rejected_for_age_alone() -> None:
    registry = build_builtin_registry()
    # Five years old, but effective-dated -> still usable.
    fact = _candidate(
        "stable_profile_facts",
        observed_at=NOW - timedelta(days=365 * 5),
        source_id="profile_import",
    )
    result = evaluate_evidence(
        QuestionType.HISTORICAL_BASELINE,
        [fact],
        registry.policies(),
        reference_time=NOW,
    )
    assert result.admissible_evidence, "valid-until-superseded fact rejected for age"
    assert result.refusal is None


def test_method_sensitive_family_carries_caveats() -> None:
    registry = build_builtin_registry()
    bc = _candidate(
        "body_composition",
        observed_at=NOW - timedelta(days=5),
    )
    result = evaluate_evidence(
        QuestionType.RECENT_TREND,
        [bc],
        registry.policies(),
        reference_time=NOW,
    )
    assert result.admissible_evidence
    caveats = result.admissible_evidence[0].caveats
    assert caveats, "method-sensitive family must carry standing caveats"
    assert any("method-sensitive" in c for c in caveats)


def test_sparse_evidence_insufficient_where_density_required() -> None:
    registry = build_builtin_registry()
    # One lone lab value, trend question that requires repeats.
    lab = _candidate(
        "sparse_lab_panels",
        observed_at=NOW - timedelta(days=20),
        source_id="lab_import",
        point_count=1,
    )
    result = evaluate_evidence(
        QuestionType.RECENT_TREND,
        [lab],
        registry.policies(),
        reference_time=NOW,
    )
    assert not result.admissible_evidence
    assert result.insufficient_evidence
    assert RejectionReason.TOO_SPARSE in result.insufficient_evidence[0].rejection_reasons


def test_acute_spot_measure_stale_for_current_status() -> None:
    registry = build_builtin_registry()
    spot = _candidate(
        "acute_spot_measures",
        observed_at=NOW - timedelta(days=3),  # well outside the 12h window
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [spot],
        registry.policies(),
        reference_time=NOW,
    )
    assert result.rejected_evidence
    assert RejectionReason.STALE_FOR_QUESTION in result.rejected_evidence[0].rejection_reasons


def test_home_bp_single_reading_insufficient() -> None:
    registry = build_builtin_registry()
    bp = _candidate(
        "home_blood_pressure",
        observed_at=NOW - timedelta(days=1),
        point_count=1,  # below the serial minimum
    )
    result = evaluate_evidence(
        QuestionType.CURRENT_STATUS,
        [bp],
        registry.policies(),
        reference_time=NOW,
    )
    assert result.insufficient_evidence
    assert RejectionReason.TOO_SPARSE in result.insufficient_evidence[0].rejection_reasons
