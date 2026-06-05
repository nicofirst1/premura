"""Tests for the bounded intake ``runtime_valid`` checker (WP02 / FR-010 / SC-008).

Stance: black-box over the public checker plus the contract doc. We assert the
three intake clauses fire on the right evidence, the result is a
``ContractCheckResult`` with sorted violations, and — the FR-010 invariant — the
clause set is exactly the three intake clauses with NO observation/full-review
clause, and matches the contract markdown so the spec cannot drift from code.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from premura.harness.intake_contract_check import (
    INTAKE_RUNTIME_CLAUSES,
    check_intake_runtime_contract,
)
from premura.parsers.base import (
    IntakeBatch,
    NutritionIntakeInput,
    SourceDescriptor,
)
from premura.parsers.contract_check import ContractCheckResult

TS = datetime(2026, 1, 1, 8, 0, 0)

# The contract doc the checker must stay pinned to (FR-010 invariant).
_CONTRACT_DOC = (
    Path(__file__).resolve().parents[1]
    / "kitty-specs"
    / "intake-parser-acceptance-scenario-01KTBT72"
    / "contracts"
    / "intake-runtime-contract.md"
)


def _nutrition_event(
    *, source_id: str = "diet_app", dedupe_key: str = "evt-1"
) -> NutritionIntakeInput:
    return NutritionIntakeInput(
        source_id=source_id,
        source_kind="diet_app",
        start_utc=TS,
        dedupe_key=dedupe_key,
    )


def _descriptor(source_id: str = "diet_app") -> SourceDescriptor:
    return SourceDescriptor(source_id=source_id, source_kind="diet_app")


def _clean_batch() -> IntakeBatch:
    return IntakeBatch(
        source_descriptors={"diet_app": _descriptor()},
        nutrition_events=[_nutrition_event()],
    )


def _violating_clauses(result: ContractCheckResult) -> set[str]:
    return {v.split(":", 1)[0] for v in result.violations}


# --------------------------------------------------------------------------- #
# T008.1 — clean batch
# --------------------------------------------------------------------------- #
def test_clean_intake_batch_is_runtime_valid() -> None:
    result = check_intake_runtime_contract(produced=_clean_batch(), persisted_ok=True)
    assert isinstance(result, ContractCheckResult)
    assert result.runtime_valid is True
    assert result.violations == []


# --------------------------------------------------------------------------- #
# T008.2 — missing source descriptor → batch_validates
# --------------------------------------------------------------------------- #
def test_missing_source_descriptor_fails_batch_validates() -> None:
    batch = IntakeBatch(
        source_descriptors={},  # event references diet_app but it is undeclared
        nutrition_events=[_nutrition_event()],
    )
    result = check_intake_runtime_contract(produced=batch, persisted_ok=True)
    assert result.runtime_valid is False
    assert _violating_clauses(result) == {"batch_validates"}
    assert any("diet_app" in v for v in result.violations)


# --------------------------------------------------------------------------- #
# T008.3 — duplicate dedupe_key → batch_validates
# --------------------------------------------------------------------------- #
def test_duplicate_dedupe_key_fails_batch_validates() -> None:
    batch = IntakeBatch(
        source_descriptors={"diet_app": _descriptor()},
        nutrition_events=[
            _nutrition_event(dedupe_key="dup"),
            _nutrition_event(dedupe_key="dup"),
        ],
    )
    result = check_intake_runtime_contract(produced=batch, persisted_ok=True)
    assert result.runtime_valid is False
    assert _violating_clauses(result) == {"batch_validates"}
    assert any("dedupe_key" in v for v in result.violations)


# --------------------------------------------------------------------------- #
# T008.4 — simulated persist failure → persisted_without_raising
# --------------------------------------------------------------------------- #
def test_persist_failure_fails_persisted_without_raising() -> None:
    result = check_intake_runtime_contract(
        produced=_clean_batch(),
        persisted_ok=False,
        persist_error="disk full",
    )
    assert result.runtime_valid is False
    assert _violating_clauses(result) == {"persisted_without_raising"}
    assert any("disk full" in v for v in result.violations)


def test_wrong_shape_fails_parser_imports_and_parses() -> None:
    # A parser that yielded the wrong object (not an IntakeBatch) fails clause 1.
    result = check_intake_runtime_contract(produced=object(), persisted_ok=True)
    assert result.runtime_valid is False
    assert "parser_imports_and_parses" in _violating_clauses(result)


def test_violations_are_sorted() -> None:
    # A batch that fails validate AND persist → multiple clauses, sorted order.
    bad = IntakeBatch(
        source_descriptors={},
        nutrition_events=[_nutrition_event()],
    )
    result = check_intake_runtime_contract(produced=bad, persisted_ok=False, persist_error="boom")
    assert result.violations == sorted(result.violations)
    assert result.runtime_valid is False


# --------------------------------------------------------------------------- #
# T008.5 — clause-set assertion (FR-010 / SC-008): exactly the three intake
# clauses, NO observation / full-review clause; pinned to the contract doc.
# --------------------------------------------------------------------------- #
def test_clause_set_is_exactly_the_three_intake_clauses() -> None:
    assert INTAKE_RUNTIME_CLAUSES == (
        "parser_imports_and_parses",
        "batch_validates",
        "persisted_without_raising",
    )
    assert len(INTAKE_RUNTIME_CLAUSES) == 3
    assert len(set(INTAKE_RUNTIME_CLAUSES)) == 3

    # No drift toward the observation or full parser-review contract.
    forbidden = {
        "no_derived_emitted",
        "declared_equals_emitted",
        "declared_exist_in_dim_metric",
        "produced_batch_without_raising",
    }
    assert forbidden.isdisjoint(INTAKE_RUNTIME_CLAUSES)


def test_clause_names_match_contract_doc() -> None:
    """The contract markdown's intake clause names equal the implementation's.

    Guards FR-010: the spec cannot drift from the checker. We extract the three
    numbered backticked clause names from the "Intake form" section.
    """
    text = _CONTRACT_DOC.read_text(encoding="utf-8")
    intake_section = text.split("## Intake form", 1)[1].split("## Invariants", 1)[0]
    # Numbered clauses are written as "1. `clause_name` — ...".
    doc_clauses = tuple(re.findall(r"^\d+\.\s+`([a-z_]+)`", intake_section, re.MULTILINE))
    assert doc_clauses == INTAKE_RUNTIME_CLAUSES


def test_every_emitted_violation_clause_is_a_known_clause() -> None:
    # Any clause the checker can emit must be one of the declared clause names.
    bad = IntakeBatch(source_descriptors={}, nutrition_events=[_nutrition_event()])
    cases = [
        check_intake_runtime_contract(produced=object(), persisted_ok=True),
        check_intake_runtime_contract(produced=bad, persisted_ok=False),
        check_intake_runtime_contract(produced=_clean_batch(), persisted_ok=False),
    ]
    for result in cases:
        assert _violating_clauses(result) <= set(INTAKE_RUNTIME_CLAUSES)


# --------------------------------------------------------------------------- #
# T030 — the runner WITNESSES intake parse/validate/persist with a stage-tagged
# error. This is the producer half of the WP02 seam: a failure tells the grader
# WHICH stage broke, and that tag is exactly what the checker reads as evidence.
# We drive the runner in-process so a stage failure is deterministic.
# --------------------------------------------------------------------------- #
from premura.harness import ingest_runner  # noqa: E402


class _ParseRaisingParser:
    source_kind = "diet_app"
    language_hint = None

    def declares_metrics(self) -> list[str]:
        return []

    def parse(self, path: Path):  # type: ignore[no-untyped-def]
        raise ValueError("bad source bytes")


def _intake_output(intake: IntakeBatch):  # type: ignore[no-untyped-def]
    from premura.parsers.base import ParseOutput

    return ParseOutput(intake=intake)


class _ValidateFailParser:
    source_kind = "diet_app"
    language_hint = None

    def declares_metrics(self) -> list[str]:
        return []

    def parse(self, path: Path):  # type: ignore[no-untyped-def]
        # Event references an undeclared source_id → validate() raises.
        return _intake_output(
            IntakeBatch(source_descriptors={}, nutrition_events=[_nutrition_event()])
        )


class _CleanIntakeParser:
    source_kind = "diet_app"
    language_hint = None

    def declares_metrics(self) -> list[str]:
        return []

    def parse(self, path: Path):  # type: ignore[no-untyped-def]
        return _intake_output(_clean_batch())


def _run_intake(monkeypatch, parser_obj, tmp_path: Path, *, persist_raises: bool = False):  # type: ignore[no-untyped-def]
    source = tmp_path / "src.csv"
    source.write_text("x\n", encoding="utf-8")
    warehouse = tmp_path / "wh.duckdb"

    # Inject the in-test parser without touching the import machinery.
    monkeypatch.setattr(
        ingest_runner,
        "_load_parser",
        lambda spec: ("DietApp", parser_obj),
    )
    if persist_raises:

        def _boom(conn, batch):  # type: ignore[no-untyped-def]
            raise RuntimeError("warehouse offline")

        monkeypatch.setattr("premura.store.profile_intake.persist_intake_batch", _boom)
    return ingest_runner.run(source=source, parser_spec="x:DietApp", warehouse=warehouse)


def test_runner_clean_intake_yields_status_ok(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    env = _run_intake(monkeypatch, _CleanIntakeParser(), tmp_path)
    assert env["status"] == "ok"
    assert env["error"] is None


def test_runner_parse_stage_failure_is_tagged(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    env = _run_intake(monkeypatch, _ParseRaisingParser(), tmp_path)
    assert env["status"] == "error"
    assert env["error"]["message"].startswith("parse: ")
    assert "bad source bytes" in env["error"]["message"]


def test_runner_validate_stage_failure_is_tagged(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    env = _run_intake(monkeypatch, _ValidateFailParser(), tmp_path)
    assert env["status"] == "error"
    assert env["error"]["message"].startswith("validate: ")


def test_runner_persist_stage_failure_is_tagged(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    env = _run_intake(monkeypatch, _CleanIntakeParser(), tmp_path, persist_raises=True)
    assert env["status"] == "error"
    assert env["error"]["message"].startswith("persist: ")
    assert "warehouse offline" in env["error"]["message"]


def test_runner_stage_tag_feeds_the_checker(monkeypatch, tmp_path) -> None:
    """End-to-end seam: the runner's stage tag is exactly what the checker reads.

    A validate-stage error from the runner maps to the checker's
    ``batch_validates`` clause — proving producer and consumer agree on stages.
    """
    env = _run_intake(monkeypatch, _ValidateFailParser(), tmp_path)
    stage = env["error"]["message"].split(":", 1)[0]
    assert stage == "validate"

    # The consumer side, fed the same broken batch, fails the matching clause.
    bad = IntakeBatch(source_descriptors={}, nutrition_events=[_nutrition_event()])
    result = check_intake_runtime_contract(produced=bad, persisted_ok=True)
    assert "batch_validates" in _violating_clauses(result)
