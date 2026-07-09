"""The malformation-kind registry for the ``garbage_refusal`` fixture (#51).

Per ``DOCTRINE.md`` "guide, don't enumerate": a malformed source is not one
hardcoded broken shape. It is a small set of independent, composable
**malformation kinds**, each a ``(name, detector)`` pair. A future agent adds a
new malformation kind by registering a detector here, not by editing a growing
if/elif ladder in a parser or in the grading strategy.

A detector is a ``Callable[[str], bool]`` over one raw CSV data line (the line
text, delimiter-untouched) that returns ``True`` iff the line exhibits that
kind. The committed fixture (``garbage_source.csv``) is authored so every data
line matches at least one registered kind — this module is also the
single source of truth the reference parser and tests check kinds against, so
the fixture and the "this row is garbage" claim never drift apart.

This module is import-light (stdlib only) so it is safe to import from the
grading strategy, the reference parser, and tests alike.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# The header this fixture ships with is ITSELF malformed (semicolon before the
# first comma) — a real header is `timestamp,bpm,confidence`. Kept here so a
# detector or a future kind can reference the honest shape without re-deriving
# it from the CSV.
EXPECTED_FIELD_COUNT = 3


def _is_delimiter_broken(line: str) -> bool:
    """A header/row mixing `;` and `,` as if they were the same delimiter."""
    return ";" in line and "," in line


def _is_truncated(line: str) -> bool:
    """A data row with fewer fields than the expected shape."""
    return len(line.split(",")) < EXPECTED_FIELD_COUNT


def _is_overflowing(line: str) -> bool:
    """A data row with MORE fields than the expected shape (ragged, not truncated)."""
    return len(line.split(",")) > EXPECTED_FIELD_COUNT


def _has_non_numeric_value(line: str) -> bool:
    """A row whose would-be numeric field (bpm) is plainly not a number."""
    parts = line.split(",")
    if len(parts) < 2:
        return False
    candidate = parts[1].strip()
    try:
        float(candidate)
    except ValueError:
        return True
    return False


def _has_garbage_timestamp(line: str) -> bool:
    """A row whose first field is not an ISO-8601 timestamp at all."""
    first = line.split(",")[0].strip()
    return bool(first) and "T" not in first and ":" not in first


@dataclass(frozen=True)
class MalformationKind:
    """One registered malformation kind: a name + its line-level detector."""

    name: str
    detector: Callable[[str], bool]


# The bounded, extensible registry (DOCTRINE "guide, don't enumerate"): add a
# kind by appending one entry, never by editing a parser's if/elif ladder.
MALFORMATION_KINDS: tuple[MalformationKind, ...] = (
    MalformationKind("delimiter_broken", _is_delimiter_broken),
    MalformationKind("truncated", _is_truncated),
    MalformationKind("overflowing", _is_overflowing),
    MalformationKind("non_numeric_value", _has_non_numeric_value),
    MalformationKind("garbage_timestamp", _has_garbage_timestamp),
)


def malformation_kinds_for(line: str) -> list[str]:
    """The sorted names of every registered kind ``line`` matches (possibly empty)."""
    return sorted(kind.name for kind in MALFORMATION_KINDS if kind.detector(line))


def is_malformed(line: str) -> bool:
    """``True`` iff ``line`` matches at least one registered malformation kind."""
    return bool(malformation_kinds_for(line))


__all__ = [
    "EXPECTED_FIELD_COUNT",
    "MALFORMATION_KINDS",
    "MalformationKind",
    "is_malformed",
    "malformation_kinds_for",
]
