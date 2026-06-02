"""Contract tests for the `correlate` lagged-association vocabulary (WP01).

These pin the *public contract* `correlate` needs before any paired computation
exists: a reviewed closed analytical question type for lagged association, the
new ``common_cause_plausible`` confound key, and the extension seam that lets a
multi-input tool descriptor declare the paired input shape without a dispatcher
branch. Everything is observed through the contract module's public surface;
nothing here touches SQL, the warehouse, MCP, PubMed, or the network.

Subtasks covered: T001 (failing vocabulary contract) and T004 (paired
input-shape + forbidden-confound-key validation at the extension seam).
"""

from __future__ import annotations

import pytest

from premura.engine.analytical_contract import (
    ANALYTICAL_QUESTION_TYPES,
    CONFOUND_KEYS,
    REGISTRY,
    AnalyticalQuestionType,
    AnalyticalToolSpec,
    ConfoundEntry,
    ConfoundKey,
    analytical_tool,
    validate_confound_keys,
)

# The literal contract identifiers correlate's later WPs and the audit-trace
# mission count on. Pinning the *string values* (not just enum identity) guards
# against a rename silently breaking the pre-registered-hypothesis identity and
# the cross-WP wiring in ``ANALYTICAL_TO_POLICY_QUESTION``.
LAGGED_ASSOCIATION_VALUE = "lagged_association"
COMMON_CAUSE_PLAUSIBLE_VALUE = "common_cause_plausible"
PAIRED_INPUT_SHAPE = "paired_ordered_daily_series"


@pytest.fixture(autouse=True)
def _clean_registry():
    """Isolate the module-global analytical registry per test."""
    saved = dict(REGISTRY)
    REGISTRY.clear()
    try:
        yield
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)


# ---------------------------------------------------------------------------
# T001: lagged-association is reviewed closed vocabulary
# ---------------------------------------------------------------------------


def test_lagged_association_is_a_closed_analytical_question_value() -> None:
    """The analytical question vocabulary contains a reviewed lagged-association
    value, exposed as a real ``AnalyticalQuestionType`` member with the contract
    string value (not a free-form string)."""
    assert AnalyticalQuestionType.LAGGED_ASSOCIATION.value == LAGGED_ASSOCIATION_VALUE
    assert LAGGED_ASSOCIATION_VALUE in ANALYTICAL_QUESTION_TYPES


def test_lagged_association_is_distinct_from_single_series_questions() -> None:
    """Lagged association must NOT collapse onto a single-series question type;
    the ADR forbids reusing a descriptive/single-series shape for two-series
    association."""
    assert (
        AnalyticalQuestionType.LAGGED_ASSOCIATION
        is not AnalyticalQuestionType.LEVEL_SHIFT_DETECTION
    )
    assert AnalyticalQuestionType.LAGGED_ASSOCIATION is not AnalyticalQuestionType.SMOOTHED_PATTERN
    values = {qt.value for qt in AnalyticalQuestionType}
    # The three reviewed question types are all distinct closed values.
    assert {"level_shift_detection", "smoothed_pattern", LAGGED_ASSOCIATION_VALUE} <= values


def test_common_cause_plausible_is_a_closed_confound_key() -> None:
    """The confound vocabulary contains ``common_cause_plausible`` as a reviewed
    closed key, mirrored in the flat ``CONFOUND_KEYS`` frozenset."""
    assert ConfoundKey.COMMON_CAUSE_PLAUSIBLE.value == COMMON_CAUSE_PLAUSIBLE_VALUE
    assert COMMON_CAUSE_PLAUSIBLE_VALUE in CONFOUND_KEYS


def test_confound_validator_accepts_common_cause_plausible() -> None:
    """The shared confound validator admits the new key like any other member."""
    # Must not raise.
    validate_confound_keys((COMMON_CAUSE_PLAUSIBLE_VALUE,), context="correlate test")


def test_confound_validator_rejects_unreviewed_strings() -> None:
    """A confound key outside the committed vocabulary is still rejected, so an
    agent cannot mint an ad-hoc 'lurking_variable'/'confounded' string."""
    with pytest.raises(ValueError, match="unknown confound key"):
        validate_confound_keys(("lurking_variable",), context="correlate test")
    with pytest.raises(ValueError, match="unknown confound key"):
        validate_confound_keys(("confounded",), context="correlate test")


def test_common_cause_plausible_usable_in_a_confound_entry() -> None:
    """The new key is usable in a ``ConfoundEntry`` and serializes to its value."""
    entry = ConfoundEntry(
        key=ConfoundKey.COMMON_CAUSE_PLAUSIBLE,
        detail="A third variable could drive both series.",
    )
    assert entry.to_dict()["key"] == COMMON_CAUSE_PLAUSIBLE_VALUE


# ---------------------------------------------------------------------------
# T004: paired input shape + confound key at the extension seam, no dispatch
#        branch required
# ---------------------------------------------------------------------------


def _paired_spec(**overrides) -> AnalyticalToolSpec:
    """A correlate-shaped descriptor. Defaults match the locked contract."""
    base = dict(
        name="correlate",
        description="Pre-registered lagged association between two daily series.",
        input_shape=PAIRED_INPUT_SHAPE,
        parameters=("lag_days", "expected_direction", "method_revision"),
        result_kind="correlate_association_estimate",
        confound_keys=(
            ConfoundKey.COMMON_CAUSE_PLAUSIBLE.value,
            ConfoundKey.TEMPORAL_AUTOCORRELATION.value,
            ConfoundKey.HIGH_IMPUTATION.value,
            ConfoundKey.LOW_SAMPLE_SIZE.value,
            ConfoundKey.SHORT_OVERLAP_WINDOW.value,
        ),
        question_type=AnalyticalQuestionType.LAGGED_ASSOCIATION,
    )
    base.update(overrides)
    return AnalyticalToolSpec(**base)


def test_descriptor_declares_paired_input_shape_and_validates() -> None:
    """A tool descriptor can declare the paired input shape and the new confound
    key, and validates without registration — no per-tool dispatcher branch is
    needed for the descriptor to exist (it is plain metadata)."""
    spec = _paired_spec().validate()
    assert spec.input_shape == PAIRED_INPUT_SHAPE
    assert spec.question_type is AnalyticalQuestionType.LAGGED_ASSOCIATION
    assert COMMON_CAUSE_PLAUSIBLE_VALUE in spec.confound_keys


def test_descriptor_exists_without_a_dispatch_branch() -> None:
    """A descriptor is constructable/validatable with no ``fn`` and the registry
    stays untouched: existence does not require dispatch wiring. This protects
    the extension seam before the paired-input implementation lands."""
    spec = _paired_spec().validate()
    assert spec.fn is None
    assert "correlate" not in REGISTRY  # validating a spec does not register it


def test_descriptor_rejects_unknown_confound_key() -> None:
    """An unreviewed confound key in a paired descriptor is rejected at the seam."""
    with pytest.raises(ValueError, match="unknown confound key"):
        _paired_spec(confound_keys=("lurking_variable",)).validate()


def test_descriptor_rejects_duplicate_confound_keys() -> None:
    """Duplicate confound keys are still rejected for a paired descriptor."""
    with pytest.raises(ValueError, match="duplicate confound_keys"):
        _paired_spec(
            confound_keys=(
                ConfoundKey.COMMON_CAUSE_PLAUSIBLE.value,
                ConfoundKey.COMMON_CAUSE_PLAUSIBLE.value,
            )
        ).validate()


def test_paired_descriptor_can_register_through_the_shared_decorator() -> None:
    """Registration goes through the shared decorator with no dispatcher edit:
    the paired shape and lagged-association question register exactly like a
    single-series tool would."""

    @analytical_tool(
        name="correlate",
        description="Pre-registered lagged association between two daily series.",
        input_shape=PAIRED_INPUT_SHAPE,
        parameters=("lag_days", "expected_direction"),
        result_kind="correlate_association_estimate",
        confound_keys=(ConfoundKey.COMMON_CAUSE_PLAUSIBLE.value,),
        question_type=AnalyticalQuestionType.LAGGED_ASSOCIATION,
    )
    def _correlate(series_a, series_b, **params):  # pragma: no cover - not invoked here
        raise NotImplementedError

    assert "correlate" in REGISTRY
    spec = REGISTRY["correlate"]
    assert spec.input_shape == PAIRED_INPUT_SHAPE
    assert spec.question_type is AnalyticalQuestionType.LAGGED_ASSOCIATION


# ---------------------------------------------------------------------------
# T005: no runtime network / PubMed dependency reachable from the contract
# ---------------------------------------------------------------------------


def test_contract_import_does_not_require_pubmed_or_network() -> None:
    """Importing the analytical contract surface in a clean interpreter must not
    pull in PubMed/MCP/HTTP/DuckDB/network modules. Run in a subprocess so a
    sibling MCP test in the same process cannot mask a regression."""
    import subprocess
    import sys

    code = (
        "import sys;"
        "import premura.engine.analytical_contract as c;"
        "from premura.engine.analytical_contract import ("
        " AnalyticalQuestionType, ConfoundKey, validate_confound_keys);"
        # touch the new vocabulary so a lazy import would have to have happened
        "assert AnalyticalQuestionType.LAGGED_ASSOCIATION.value == 'lagged_association';"
        "assert ConfoundKey.COMMON_CAUSE_PLAUSIBLE.value == 'common_cause_plausible';"
        "forbidden = ('pubmed', 'mcp', 'entrez', 'httpx', 'aiohttp', 'duckdb', 'requests');"
        "leaked = sorted(n for n in sys.modules"
        " if any(t in n.lower() for t in forbidden));"
        "assert leaked == [], 'contract import leaked: ' + repr(leaked);"
        "print('ok')"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"
