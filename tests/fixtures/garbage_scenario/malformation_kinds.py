"""The malformation-kind registry for the ``garbage_refusal`` fixture (#69).

Per ``DOCTRINE.md`` "guide, don't enumerate": a malformed source is not one
hardcoded broken shape. It is a small set of independent, composable
**malformation kinds**, each a typed :class:`MalformationKind` (name +
detector). A future agent adds a new malformation kind by appending one entry
to :data:`MALFORMATION_KINDS`, not by editing a growing if/elif ladder in a
parser, a test, or a grader-only manifest kept in sync by hand.

This is the SINGLE SOURCE OF TRUTH: the reference parser
(``reference_refusing_parser.py``) classifies lines against it, the manifest
description (``garbage_manifest.yaml``) is generated from its kind names, and
the tests assert the committed fixture (``garbage_source.csv``) exhibits every
registered kind — all reading this one module, so registry and fixture can
never silently drift apart (no parallel manifest, no drift-guard test).

A detector is a ``Callable[[str], bool]`` over one raw CSV line (delimiter-
untouched) that returns ``True`` iff the line exhibits that kind. A single line
may match more than one kind — ``kinds_for`` returns all of them, so a
multi-kind line is fully classified rather than truncated at the first match.

Import-light (stdlib only) so it is safe to import from the reference parser,
the strategy, and tests alike.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


def _is_broken_header(line: str) -> bool:
    """A banner / sentinel line that is not a usable CSV header."""
    upper = line.upper()
    return "@@@" in line or "NOT A REAL EXPORT" in upper or ";;;" in line


def _is_garbage_value_row(line: str) -> bool:
    """A row whose cells are non-parseable noise (NaN, ???, %%%, FAKE tokens)."""
    tokens = ("NAN", "???", "%%%", "FAKE", "XYZZY", "PLUGH", "NOTHING-HERE")
    upper = line.upper()
    return any(token in upper for token in tokens)


def _is_truncated_row(line: str) -> bool:
    """A row cut short mid-record (an explicit truncation marker or a lone comma run)."""
    return "<<<TRUNCATED" in line.upper() or line.strip(", \n") == ""


def _is_inconsistent_delimiter_row(line: str) -> bool:
    """A row using a non-comma delimiter (';', '|', tab) the comma header does not."""
    return ";" in line or "|" in line or "\t" in line


@dataclass(frozen=True)
class MalformationKind:
    """One registered malformation kind: a name + its line-level detector."""

    name: str
    detector: Callable[[str], bool]


# The bounded, extensible registry (DOCTRINE "guide, don't enumerate"): add a
# kind by appending one entry, never by editing a parser's if/elif ladder or a
# second, hand-synced manifest list.
MALFORMATION_KINDS: tuple[MalformationKind, ...] = (
    MalformationKind("broken_header", _is_broken_header),
    MalformationKind("garbage_values", _is_garbage_value_row),
    MalformationKind("truncated_row", _is_truncated_row),
    MalformationKind("inconsistent_delimiter", _is_inconsistent_delimiter_row),
)


def kinds_for(line: str) -> list[str]:
    """The sorted names of every registered kind ``line`` matches (possibly empty)."""
    return sorted(kind.name for kind in MALFORMATION_KINDS if kind.detector(line))


def classify_line(line: str) -> str:
    """The first registered malformation kind ``line`` matches, or ``"unrecognized"``.

    Registry order breaks ties deterministically for diagnostics (a line
    matching several kinds is still honestly refused either way; the label is
    cosmetic). A line matching no registered kind is still refused, never
    fabricated — ``"unrecognized"`` is a valid, honest classification.
    """
    for kind in MALFORMATION_KINDS:
        if kind.detector(line):
            return kind.name
    return "unrecognized"


def is_malformed(line: str) -> bool:
    """``True`` iff ``line`` matches at least one registered malformation kind."""
    return bool(kinds_for(line))


__all__ = [
    "MALFORMATION_KINDS",
    "MalformationKind",
    "classify_line",
    "is_malformed",
    "kinds_for",
]
