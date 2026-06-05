"""Manifest-blind self-reconciliation gate (FR-003 / C-005).

The runtime-faithful honesty gate the operator retry loop uses. It is the
answer-key-free twin of :func:`premura.harness.grader._grade_honest_about_gaps`:
where the grader enumerates source-field names from the committed fixture
manifest, this gate reads the **same** names directly from the source file's
header/structure — so it needs **no** ground-truth manifest and must never read
one (C-005).

The honesty rule both sides share is *loaded-or-declared*: a source column is
honest iff the parser consumed it (mapped) or declared it as a gap
(``unmapped_metrics`` / ``skipped_rows``). Anything else is a silent drop.

Non-goal: this gate does NOT judge mapping *correctness* (whether ``bpm`` should
map to ``heart_rate``). That residual is the independent grader's job and is a
legitimate capability-floor finding, never a loop failure.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from premura.parsers.base import IngestBatch, IntakeBatch


@dataclass(frozen=True, slots=True)
class SelfReconciliationResult:
    """Outcome of the manifest-blind honesty gate (FR-003).

    Invariant: ``passed == (bool(source_columns) and unaccounted == [])`` — an
    empty/headerless source cannot witness honesty, so it never silently passes.
    ``source_columns`` and ``unaccounted`` are sorted for determinism;
    ``accounted`` is a frozenset.
    """

    passed: bool
    source_columns: list[str]
    accounted: frozenset[str]
    unaccounted: list[str]


def _read_source_columns(source_path: Path) -> list[str]:
    """Read the full ground set of raw columns from the source file's header.

    The ground set is the FILE's structure, never the columns the parser chose
    to inspect — that is what closes the "lazy parser skips a column" loophole.
    Slice-one scope is the heart-rate CSV: the header is the first row.

    An empty, headerless, or unreadable file yields an empty list, which the
    gate treats as a hard fail (it cannot prove honesty), never a silent pass.
    """
    try:
        with source_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
    except (OSError, UnicodeDecodeError):
        return []
    if not header:
        return []
    return [column.strip() for column in header if column.strip()]


def self_reconcile(
    source_path: Path,
    batch: IngestBatch | IntakeBatch,
    mapped_columns: Iterable[str],
) -> SelfReconciliationResult:
    """Check that every raw source column is mapped or declared (FR-003 / C-005).

    Args:
        source_path: the source artifact. Its header/structure is the ground set
            of raw columns — read here, NOT inferred from the parser's behaviour.
        batch: the parser's own :class:`~premura.parsers.base.IngestBatch` **or**
            :class:`~premura.parsers.base.IntakeBatch`. Only its declared gaps are
            consulted: ``unmapped_metrics`` and each ``skipped_rows`` entry's
            ``raw_field`` — both fields are present on either batch type, so the
            gate is drawer-agnostic with **no logic change** (FR-008 / D9).
        mapped_columns: the source columns the parser consumed to emit its
            metrics. An **explicit** caller input (the WP03 operator supplies it,
            tests pass it directly); the gate never infers it from the batch.

    Returns:
        A :class:`SelfReconciliationResult`. A column is *accounted* iff it is in
        ``mapped_columns`` OR ``batch.unmapped_metrics`` OR a ``skipped_rows``
        ``raw_field``. ``passed`` iff ``source_columns ⊆ accounted``;
        ``unaccounted`` is the sorted difference, fed back to the operator
        verbatim on failure.

    An empty, headerless, or unreadable source (no ground set) is a hard fail,
    never a silent pass: honesty cannot be proven without columns to reconcile.

    This never reads, imports, or accepts the fixture manifest or any
    ground-truth mapping (C-005): its only inputs are the source artifact and the
    parser's own batch. It is pure and deterministic.
    """
    source_columns = _read_source_columns(source_path)

    accounted: frozenset[str] = frozenset(
        set(mapped_columns)
        | set(batch.unmapped_metrics)
        | {row.raw_field for row in batch.skipped_rows}
    )

    unaccounted = sorted(set(source_columns) - accounted)
    # An empty ground set cannot witness honesty -> fail, never a silent pass.
    passed = bool(source_columns) and not unaccounted
    return SelfReconciliationResult(
        passed=passed,
        source_columns=sorted(source_columns),
        accounted=accounted,
        unaccounted=unaccounted,
    )
