"""Intake runtime contract checker (FR-010 / SC-008).

The intake analogue of the observation ``check_runtime_contract``
(:mod:`premura.parsers.contract_check`): a **pure function over captured
evidence** so the grader can *recompute* the runtime-valid subset of an intake
parser's contract and never *trust* a precomputed flag.

This is a **bounded** runtime tier — explicitly **NOT** the full parser-review
contract (``src/premura/parsers/CONTRACT.md``) and **NOT** a fake canonical-metric
mirror. ``IntakeBatch`` has no ``declared_metrics`` / ``emitted_metric_ids`` /
``dim_metric`` surface (those are ``IngestBatch`` only), so the observation
checker's three metric clauses (``no_derived_emitted``,
``declared_equals_emitted``, ``declared_exist_in_dim_metric``) have **no intake
counterpart by design**. The truthful intake declared/emitted coherence is on the
**source dimension** — declared = ``source_descriptors``, emitted = the
``source_id``s used on events — enforced by ``IntakeBatch.validate()``.

The three runtime-valid clauses are recomputed here; the checker derives each
fact itself (it re-runs ``validate()`` rather than trusting the runner raised)
so the grader's verdict never rests on a self-report. See
``contracts/intake-runtime-contract.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from premura.parsers.base import IntakeBatch
from premura.parsers.contract_check import ContractCheckResult

if TYPE_CHECKING:
    pass

# The exact, ordered clause names for the intake runtime tier. Pinned here so the
# contract test can assert the implementation's clause set matches the contract
# doc — and so the checker cannot silently drift toward the observation or full
# review contract (FR-010 invariant: names + count must match).
INTAKE_RUNTIME_CLAUSES: tuple[str, ...] = (
    "parser_imports_and_parses",
    "batch_validates",
    "persisted_without_raising",
)


def check_intake_runtime_contract(
    *,
    produced: Any,
    persisted_ok: bool,
    persist_error: str | None = None,
) -> ContractCheckResult:
    """Recompute the bounded intake ``runtime_valid`` subset from captured evidence.

    Mirrors the *shape* of :func:`premura.parsers.contract_check.check_runtime_contract`
    (same ``ContractCheckResult`` with a sorted ``violations`` list of
    ``"<clause>: <detail>"`` strings), but encodes the three intake clauses — not
    the four observation clauses.

    Args:
        produced: the object the operator's parser yielded for the intake seam.
            Clause ``parser_imports_and_parses`` records a violation if this is
            not an :class:`~premura.parsers.base.IntakeBatch` (import/parse
            *raising* is surfaced upstream by the harness as a parser error; this
            clause guards the "produced the wrong shape" case).
        persisted_ok: the captured outcome of the harness's persist step
            (``persist_intake_batch``). The checker does not itself persist — it
            grades the captured boolean, mirroring how the observation clause
            grades ``ingest_run`` success.
        persist_error: an optional captured detail for a persist failure, used in
            the ``persisted_without_raising`` violation message.

    Returns:
        A :class:`ContractCheckResult` with ``runtime_valid`` and a sorted
        ``violations`` list. Pure: no I/O, no persistence, no warehouse writes,
        no ids/timestamps in the output.
    """
    violations: list[str] = []

    # Clause 1 — parser_imports_and_parses: the parser produced an IntakeBatch
    # (the right shape). A bare raise on import/parse is surfaced by the harness;
    # this clause catches a parser that returned the wrong object.
    if not isinstance(produced, IntakeBatch):
        violations.append(
            f"parser_imports_and_parses: expected IntakeBatch, got {type(produced).__name__}"
        )
        # Without a real batch the validate clause cannot be witnessed; report it
        # as unwitnessed rather than dereferencing a wrong-shape object.
        violations.append("batch_validates: no IntakeBatch produced")
    else:
        # Clause 2 — batch_validates: re-run IntakeBatch.validate() ourselves so
        # the verdict derives the fact rather than trusting the runner. This is
        # the intake declared/emitted coherence on the SOURCE dimension (every
        # event source_id is covered by a source_descriptor) plus dedupe_key
        # uniqueness.
        try:
            produced.validate()
        except ValueError as exc:
            violations.append(f"batch_validates: {exc}")

    # Clause 3 — persisted_without_raising: grade the captured persist outcome
    # (the checker never runs persistence itself).
    if not persisted_ok:
        detail = persist_error or "persist_intake_batch failed"
        violations.append(f"persisted_without_raising: {detail}")

    violations.sort()
    return ContractCheckResult(runtime_valid=not violations, violations=violations)
