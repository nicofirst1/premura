"""Contract tests for the Stage 3 analytical-tool contract (WP02).

These exercise the bounded extension seam: registration + shared dispatch
(without a per-tool branch), the result-envelope serialization, and the
construction/validation invariants of the closed confound and question-type
vocabularies. Nothing here touches SQL, the warehouse, MCP, or the network —
the contract module is deliberately agnostic of all of those.

Everything is imported through the contract module's public surface, never a
private helper path.
"""

from __future__ import annotations

import pytest

from premura.engine.analytical_contract import (
    CONFOUND_KEYS,
    REGISTRY,
    AnalyticalQuestionType,
    AnalyticalResultEnvelope,
    AnalyticalStatus,
    AnalyticalToolSpec,
    ConfoundEntry,
    ConfoundKey,
    RefusalOutcome,
    Uncertainty,
    analytical_tool,
    dispatch,
    validate_confound_keys,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Each test starts and ends with an empty analytical registry.

    The registry is module-global, mirroring the Stage 2 signal/resolver
    registries; isolating it keeps these tests order-independent.
    """
    saved = dict(REGISTRY)
    REGISTRY.clear()
    try:
        yield
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)


def _available_envelope() -> AnalyticalResultEnvelope:
    """A valid non-refusal envelope used by serialization tests."""
    return AnalyticalResultEnvelope(
        tool_name="trivial",
        status=AnalyticalStatus.AVAILABLE,
        inputs=("metric:weight",),
        parameters={"window": 7},
        estimate={"value": 42.0, "method": "trivial@1"},
        uncertainty=Uncertainty.unavailable(),
        validity_status="current",
        is_imputed_pct=0.0,
        sample_size=30,
        confound_checklist=(
            ConfoundEntry(
                key=ConfoundKey.METHOD_UNCERTAINTY_UNAVAILABLE,
                detail="trailing mean has no natural interval",
            ),
        ),
        caveats=("describes your own series only",),
    ).validate()


# ---------------------------------------------------------------------------
# T008: trivial tool registration + dispatch (no per-tool branch)
# ---------------------------------------------------------------------------


def test_trivial_tool_registers_and_dispatches() -> None:
    @analytical_tool(
        name="trivial",
        description="A test-only trivial analytical tool.",
        input_shape="single_ordered_series",
        parameters=("window",),
        result_kind="trivial_estimate",
        confound_keys=("low_sample_size",),
        question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
    )
    def run_trivial(series: list[float]) -> AnalyticalResultEnvelope:
        return AnalyticalResultEnvelope(
            tool_name="trivial",
            status=AnalyticalStatus.AVAILABLE,
            inputs=("metric:test",),
            estimate={"value": sum(series) / len(series)},
            uncertainty=Uncertainty.unavailable(),
            validity_status="current",
            is_imputed_pct=0.0,
            sample_size=len(series),
            confound_checklist=(ConfoundEntry(key=ConfoundKey.LOW_SAMPLE_SIZE),),
        ).validate()

    assert "trivial" in REGISTRY
    spec = REGISTRY["trivial"]
    assert isinstance(spec, AnalyticalToolSpec)
    assert spec.question_type is AnalyticalQuestionType.SMOOTHED_PATTERN

    # Dispatch goes through the shared path — no per-tool branch exists.
    outcome = dispatch("trivial", [2.0, 4.0])
    assert outcome.status is AnalyticalStatus.AVAILABLE
    assert outcome.estimate == {"value": 3.0}


def test_dispatch_unknown_tool_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        dispatch("not_registered")


def test_dispatch_spec_without_fn_raises_runtimeerror() -> None:
    # A descriptor declared without a function body (test-only) cannot dispatch.
    REGISTRY["bodyless"] = AnalyticalToolSpec(
        name="bodyless",
        description="declared without an implementation",
        input_shape="single_ordered_series",
        parameters=(),
        result_kind="none",
        confound_keys=(),
        question_type=AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
    ).validate()
    with pytest.raises(RuntimeError):
        dispatch("bodyless")


# ---------------------------------------------------------------------------
# T008: serialization of a valid result envelope
# ---------------------------------------------------------------------------


def test_valid_envelope_serializes_to_json_safe_primitives() -> None:
    data = _available_envelope().to_dict()

    assert data["tool_name"] == "trivial"
    assert data["status"] == "available"
    assert data["estimate"] == {"value": 42.0, "method": "trivial@1"}
    assert data["uncertainty"] == {"available": False, "payload": None}
    assert data["validity_status"] == "current"
    assert data["is_imputed_pct"] == 0.0
    assert data["sample_size"] == 30
    assert data["confound_checklist"] == [
        {
            "key": "method_uncertainty_unavailable",
            "detail": "trailing mean has no natural interval",
        }
    ]
    assert data["refusal"] is None

    # JSON-safe: round-trips through the json module unchanged.
    import json

    assert json.loads(json.dumps(data)) == data


def test_refusal_envelope_serializes() -> None:
    envelope = AnalyticalResultEnvelope(
        tool_name="trivial",
        status=AnalyticalStatus.REFUSED,
        refusal=RefusalOutcome(
            reason="insufficient_observations",
            message="not enough usable points on both sides of any split",
            missing_or_bad_inputs=("metric:weight",),
        ),
    ).validate()
    data = envelope.to_dict()
    assert data["status"] == "refused"
    assert data["estimate"] is None
    assert data["refusal"]["reason"] == "insufficient_observations"


# ---------------------------------------------------------------------------
# T008: rejection of unknown confound key
# ---------------------------------------------------------------------------


def test_validate_confound_keys_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="unknown confound key"):
        validate_confound_keys(("low_sample_size", "probably_fine"))


def test_tool_descriptor_rejects_unknown_confound_key() -> None:
    with pytest.raises(ValueError, match="unknown confound key"):
        AnalyticalToolSpec(
            name="bad",
            description="declares a confound key outside the vocabulary",
            input_shape="single_ordered_series",
            parameters=(),
            result_kind="none",
            confound_keys=("made_up_key",),
            question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
        ).validate()


def test_committed_confound_vocabulary_is_the_closed_set() -> None:
    # The correlate mission (WP01) added ``common_cause_plausible`` as a reviewed
    # closed key (methodology research Q4). This locks the full committed set so
    # any further addition is a deliberate, reviewed vocabulary change.
    assert CONFOUND_KEYS == frozenset(
        {
            "high_imputation",
            "low_sample_size",
            "short_overlap_window",
            "parameter_at_limit",
            "vendor_estimate_input",
            "temporal_autocorrelation",
            "life_event_sensitive",
            "method_uncertainty_unavailable",
            "common_cause_plausible",
        }
    )


def test_analytical_question_types_are_the_closed_set() -> None:
    # The correlate mission added ``lagged_association`` as its own first-class
    # question type (ADR-0008); the finish-analytical-tool-set mission added
    # ``moving_window_pattern`` (rolling_mean) and ``paired_difference``
    # (paired_t_test). Each is a distinct reviewed value so its own
    # coverage/paired-sample sufficiency is never hidden behind another shape.
    # The m8 mission added ``condition_paired_difference``
    # (condition_paired_t_test) as its own first-class reviewed value so its
    # episode-count sufficiency is never hidden behind the anchor-date shape.
    assert {qt.value for qt in AnalyticalQuestionType} == {
        "level_shift_detection",
        "smoothed_pattern",
        "lagged_association",
        "moving_window_pattern",
        "paired_difference",
        "condition_paired_difference",
    }


# ---------------------------------------------------------------------------
# T008: rejection of refusal-with-estimate + missing metadata
# ---------------------------------------------------------------------------


def test_refusal_with_estimate_is_rejected() -> None:
    with pytest.raises(ValueError, match="refusal result must not include an estimate"):
        AnalyticalResultEnvelope(
            tool_name="trivial",
            status=AnalyticalStatus.REFUSED,
            estimate={"value": 1.0},
            refusal=RefusalOutcome(reason="stale", message="data too old"),
        ).validate()


def test_refusal_without_refusal_outcome_is_rejected() -> None:
    with pytest.raises(ValueError, match="must include a RefusalOutcome"):
        AnalyticalResultEnvelope(
            tool_name="trivial",
            status=AnalyticalStatus.REFUSED,
        ).validate()


def test_non_refusal_missing_metadata_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing required metadata"):
        AnalyticalResultEnvelope(
            tool_name="trivial",
            status=AnalyticalStatus.AVAILABLE,
            estimate={"value": 1.0},
            # missing uncertainty / validity_status / is_imputed_pct / sample_size
        ).validate()


def test_non_refusal_without_estimate_is_rejected() -> None:
    with pytest.raises(ValueError, match="must include an estimate"):
        AnalyticalResultEnvelope(
            tool_name="trivial",
            status=AnalyticalStatus.AVAILABLE,
            uncertainty=Uncertainty.unavailable(),
            validity_status="current",
            is_imputed_pct=0.0,
            sample_size=10,
        ).validate()


def test_out_of_range_imputation_pct_is_rejected() -> None:
    with pytest.raises(ValueError, match="is_imputed_pct"):
        AnalyticalResultEnvelope(
            tool_name="trivial",
            status=AnalyticalStatus.AVAILABLE,
            estimate={"value": 1.0},
            uncertainty=Uncertainty.unavailable(),
            validity_status="current",
            is_imputed_pct=150.0,
            sample_size=10,
        ).validate()


def test_uncertainty_available_requires_payload() -> None:
    with pytest.raises(ValueError, match="payload must be present"):
        Uncertainty(available=True, payload=None).validate()


def test_malformed_descriptor_empty_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        AnalyticalToolSpec(
            name="",
            description="empty name",
            input_shape="single_ordered_series",
            parameters=(),
            result_kind="none",
            confound_keys=(),
            question_type=AnalyticalQuestionType.SMOOTHED_PATTERN,
        ).validate()


# ---------------------------------------------------------------------------
# T008: deterministic repeated serialization
# ---------------------------------------------------------------------------


def test_repeated_serialization_is_byte_identical() -> None:
    import json

    envelope = _available_envelope()
    first = json.dumps(envelope.to_dict(), sort_keys=True)
    second = json.dumps(envelope.to_dict(), sort_keys=True)
    assert first == second

    # Two separately-constructed-but-equal envelopes serialize identically too.
    other = _available_envelope()
    assert json.dumps(other.to_dict(), sort_keys=True) == first
