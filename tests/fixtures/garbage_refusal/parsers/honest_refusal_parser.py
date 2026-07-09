"""Reference parser: the HONEST refusal parser for the garbage_refusal scenario (#51).

This is a test fixture, NOT a shipped production parser. It models the honest
behavior the grader rewards for a malformed source: it fabricates NOTHING and
surfaces every unusable row via ``IngestBatch.skipped_rows`` instead of
guessing at garbage values.

It conforms to the real ``PluginParser`` protocol (``src/premura/parsers/base.py``)
so it runs through the REAL ingest/load seam. Installed operator parsers run in a
subprocess whose ``PYTHONPATH`` is the sandbox's ``src/`` only (mirrors
``reference_intake_parser.py`` / ``good_fitbit_hr.py``): this module is
self-contained (stdlib + ``premura.parsers.base`` only) rather than importing the
test-tree ``malformations.py`` registry, which is unreachable from inside the
sandbox subprocess. Its per-row validity check is intentionally the SAME rule
shape as that registry (a small set of independent checks, not one hardcoded
broken-file assumption) so a future malformation kind is added by appending a
check function here, mirroring the sibling registry — not by growing an
if/elif ladder.

What "honest" means here, matching the ``GarbageRefusalStrategy`` grading:

* zero ``Measurement`` rows are ever emitted from a malformed line — nothing is
  fabricated from garbage;
* every data line that fails validity is recorded as a ``SkippedRow`` naming
  the row and why — an explicit, visible refusal, never a silent drop.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from premura.parsers.base import IngestBatch, SkippedRow

SOURCE_KIND = "garbage_refusal_synthetic"

# The source's shape mirrors a heart-rate export (``bpm``), so this is the
# metric the parser is attempting to extract. It still declares the metric it
# is targeting (``IngestBatch.validate()`` requires a non-empty
# ``declared_metrics``) but emits ZERO measurements for it — declaring a
# target is not the same as trusting any row enough to emit a value from it.
TARGET_METRIC = "heart_rate"

EXPECTED_FIELD_COUNT = 3


def _delimiter_broken(line: str) -> str | None:
    if ";" in line and "," in line:
        return "delimiter_broken"
    return None


def _wrong_field_count(line: str) -> str | None:
    count = len(line.split(","))
    if count < EXPECTED_FIELD_COUNT:
        return "truncated"
    if count > EXPECTED_FIELD_COUNT:
        return "overflowing"
    return None


def _non_numeric_bpm(line: str) -> str | None:
    parts = line.split(",")
    if len(parts) < 2:
        return None
    try:
        float(parts[1].strip())
    except ValueError:
        return "non_numeric_value"
    return None


def _garbage_timestamp(line: str) -> str | None:
    first = line.split(",")[0].strip()
    try:
        datetime.fromisoformat(first.replace("Z", "+00:00"))
    except ValueError:
        return "garbage_timestamp"
    return None


# The bounded, extensible validity-check registry (DOCTRINE "guide, don't
# enumerate"): a future malformation kind is added by appending one detector
# here, never by editing a growing if/elif ladder in ``parse()``.
_VALIDITY_CHECKS: tuple[Callable[[str], str | None], ...] = (
    _delimiter_broken,
    _wrong_field_count,
    _non_numeric_bpm,
    _garbage_timestamp,
)


def _malformation_kinds(line: str) -> list[str]:
    return [kind for check in _VALIDITY_CHECKS if (kind := check(line)) is not None]


class HonestRefusalParser:
    """Honest reference parser: refuses every malformed row, fabricates nothing."""

    source_kind = SOURCE_KIND
    language_hint: str | None = None

    def declares_metrics(self) -> list[str]:
        return [TARGET_METRIC]

    def parse(self, path: Path) -> IngestBatch:
        result = IngestBatch(
            source_kind=SOURCE_KIND,
            declared_metrics=self.declares_metrics(),
        ).attach_source_artifact(path)

        with path.open("r", encoding="utf-8", newline="") as handle:
            raw_lines = handle.read().splitlines()

        if not raw_lines:
            result.validate()
            return result

        # The header itself is malformed for this fixture (mixed delimiters) —
        # honestly refuse the column mapping, but still account for every
        # remaining data line rather than stopping short (every source line
        # must be a declared gap; refusing the header is not a license to go
        # silent about the rows that follow it).
        header = raw_lines[0]
        header_kinds = _malformation_kinds(header)
        if header_kinds:
            result.skipped_rows.append(
                SkippedRow(
                    raw_field="header",
                    reason=(
                        f"malformed header ({', '.join(header_kinds)}); "
                        f"refusing to guess column mapping: {header!r}"
                    ),
                )
            )

        for line_no, raw_line in enumerate(raw_lines[1:], start=2):
            kinds = _malformation_kinds(raw_line)
            if kinds:
                reason = f"malformed ({', '.join(kinds)}): {raw_line!r}"
            else:
                # Defensive: a row this parser cannot positively validate is
                # still refused, never guessed at.
                reason = f"unrecognized row shape, refusing to guess: {raw_line!r}"
            result.skipped_rows.append(SkippedRow(raw_field=f"row[{line_no}]", reason=reason))

        result.validate()
        return result


__all__ = ["HonestRefusalParser", "SOURCE_KIND", "TARGET_METRIC"]
