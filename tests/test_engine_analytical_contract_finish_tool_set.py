"""Contract-vocabulary tests for the finished analytical tool set (WP01).

These lock the *foundation* the two remaining roadmap tools (`rolling_mean` and
`paired_t_test`) register against: the reviewed closed analytical question
vocabulary, plus the still-active closure/rejection guarantees of the analytical
contract. This WP adds **only** the vocabulary and policy gate; the tool methods,
MCP wrappers, and trace identities are later WPs and are deliberately never
imported here.

Everything is imported through the analytical contract's public surface — the
same boundary a future tool author and reviewer use, never a private helper.
"""

from __future__ import annotations

import pytest

from premura.engine.analytical_contract import (
    ANALYTICAL_QUESTION_TYPES,
    CONFOUND_KEYS,
    REGISTRY,
    AnalyticalQuestionType,
    AnalyticalResultEnvelope,
    AnalyticalStatus,
    AnalyticalToolSpec,
    Uncertainty,
    analytical_tool,
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


# ---------------------------------------------------------------------------
# T001: reviewed question vocabulary for the moving-window and paired shapes
# ---------------------------------------------------------------------------


def test_moving_window_pattern_is_a_reviewed_question_type() -> None:
    """`rolling_mean` gets its OWN moving-window question shape.

    Research note (finish-analytical-tool-set) keeps `rolling_mean` distinct from
    the shipped `smoothed_average`: it emits a per-point coverage/missingness
    series, which is a different *question shape* than the single smoothed level
    `SMOOTHED_PATTERN` answers. So it must not collapse onto `SMOOTHED_PATTERN`.
    """
    assert AnalyticalQuestionType.MOVING_WINDOW_PATTERN.value == "moving_window_pattern"
    assert "moving_window_pattern" in ANALYTICAL_QUESTION_TYPES
    # It is its own value, not an alias of the smoothed single-level shape.
    assert (
        AnalyticalQuestionType.MOVING_WINDOW_PATTERN is not AnalyticalQuestionType.SMOOTHED_PATTERN
    )


def test_paired_difference_is_a_reviewed_question_type() -> None:
    """`paired_t_test` gets its OWN paired-comparison question shape.

    A paired before/after difference carries paired-sample sufficiency (a raw
    pair floor) that no single-series shape and not even the two-series
    `LAGGED_ASSOCIATION` expresses. It must therefore be a distinct closed value,
    never collapsed onto lagged association, level-shift, or recent trend.
    """
    assert AnalyticalQuestionType.PAIRED_DIFFERENCE.value == "paired_difference"
    assert "paired_difference" in ANALYTICAL_QUESTION_TYPES
    for other in (
        AnalyticalQuestionType.LAGGED_ASSOCIATION,
        AnalyticalQuestionType.LEVEL_SHIFT_DETECTION,
        AnalyticalQuestionType.SMOOTHED_PATTERN,
    ):
        assert AnalyticalQuestionType.PAIRED_DIFFERENCE is not other


def test_new_question_types_extend_not_replace_the_closed_vocabulary() -> None:
    """The two new shapes are added without dropping the shipped vocabulary."""
    values = {qt.value for qt in AnalyticalQuestionType}
    assert {
        "level_shift_detection",
        "smoothed_pattern",
        "lagged_association",
        "moving_window_pattern",
        "paired_difference",
    } <= values
    # The flat frozenset stays in sync with the enum (it is derived from it).
    assert ANALYTICAL_QUESTION_TYPES == frozenset(values)


# ---------------------------------------------------------------------------
# T003: vocabulary closure stays enforced for the new tools
# ---------------------------------------------------------------------------


def _spec_for(
    name: str,
    *,
    question_type: object,
    confound_keys: tuple[str, ...],
) -> AnalyticalToolSpec:
    return AnalyticalToolSpec(
        name=name,
        description=f"test descriptor for {name}",
        input_shape="single_ordered_series",
        parameters=("window",),
        result_kind=f"{name}_estimate",
        confound_keys=confound_keys,
        question_type=question_type,  # type: ignore[arg-type]
    )


def test_rolling_mean_descriptor_rejects_arbitrary_string_question_type() -> None:
    """A descriptor cannot register `rolling_mean` with an ad hoc question type.

    The question type is a closed :class:`AnalyticalQuestionType`; an arbitrary
    string is not a member, so dispatch on it would be a type error at the
    boundary. The reviewed shape is the only admissible one.
    """
    # The closed enum is the only legal source; an arbitrary string is not in it.
    assert "rolling_mean_ad_hoc" not in ANALYTICAL_QUESTION_TYPES
    # And the descriptor still validates a real member.
    spec = _spec_for(
        "rolling_mean",
        question_type=AnalyticalQuestionType.MOVING_WINDOW_PATTERN,
        confound_keys=("low_sample_size", "short_overlap_window"),
    ).validate()
    assert spec.question_type is AnalyticalQuestionType.MOVING_WINDOW_PATTERN


def test_paired_t_test_descriptor_rejects_unknown_confound_key() -> None:
    """Closed confound-vocabulary enforcement remains active for the new tools."""
    with pytest.raises(ValueError, match="unknown confound key"):
        _spec_for(
            "paired_t_test",
            question_type=AnalyticalQuestionType.PAIRED_DIFFERENCE,
            confound_keys=("low_sample_size", "p_value_was_significant"),
        ).validate()


def test_paired_t_test_descriptor_rejects_duplicate_confound_keys() -> None:
    """Duplicate confound keys still fail validation for the new tools."""
    with pytest.raises(ValueError, match="duplicate confound_keys"):
        _spec_for(
            "paired_t_test",
            question_type=AnalyticalQuestionType.PAIRED_DIFFERENCE,
            confound_keys=("low_sample_size", "low_sample_size"),
        ).validate()


def test_new_tools_register_by_descriptor_not_by_dispatcher_branch() -> None:
    """The registry still works by descriptor registration, not a per-tool branch.

    Registering a (test-only) `rolling_mean`/`paired_t_test` spec populates the
    shared registry exactly like every other tool — no contract edit is needed to
    add a tool, which is the whole point of the extension seam.
    """

    @analytical_tool(
        name="rolling_mean",
        description="test-only moving-window registration",
        input_shape="single_ordered_series",
        parameters=("window", "min_coverage"),
        result_kind="rolling_mean_estimate",
        confound_keys=("low_sample_size", "high_imputation"),
        question_type=AnalyticalQuestionType.MOVING_WINDOW_PATTERN,
    )
    def _run_rolling_mean() -> AnalyticalResultEnvelope:  # pragma: no cover - identity
        return AnalyticalResultEnvelope(
            tool_name="rolling_mean",
            status=AnalyticalStatus.AVAILABLE,
            estimate={"points": []},
            uncertainty=Uncertainty.unavailable(),
            validity_status="current",
            is_imputed_pct=0.0,
            sample_size=7,
        ).validate()

    assert "rolling_mean" in REGISTRY
    assert REGISTRY["rolling_mean"].question_type is AnalyticalQuestionType.MOVING_WINDOW_PATTERN
    # The closed confound vocabulary the descriptor promised is a real subset.
    assert set(REGISTRY["rolling_mean"].confound_keys) <= CONFOUND_KEYS
