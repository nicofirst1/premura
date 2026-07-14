"""Reference parser for the synthetic *garbage* source: the HONEST refusal.

This is the **layer-1 known-good operator** for the ``garbage_refusal``
acceptance scenario (risk R7): the honest baseline the grader reconciles a live
operator against. It is a test fixture, NOT a shipped production parser — the
source is deliberately malformed garbage (broken header, truncated rows, garbage
values, inconsistent delimiters), so there is no honest mapping. The only honest
behaviour is to REFUSE: load zero rows and surface every unusable line as a
declared gap, never fabricate a measurement from noise.

It conforms to the federated ``PluginParser`` protocol
(``src/premura/parsers/base.py``) and produces an :class:`IngestBatch` that emits
ZERO measurements, declares each garbage line via ``skipped_rows``, and records
the garbage source itself via ``unmapped_metrics`` — so the run is a CAPTURED,
honest refusal at the ingest boundary that surfaces its failure and loads nothing,
never a silent success. ``parse()`` does not raise: an honest refusal is a normal,
gradeable outcome, not a crash.

It declares ``heart_rate`` (a real metric that exists in ``dim_metric.yaml``) so
the empty batch is contract-valid and reaches the loader as a ``status=ok`` run
that inserts zero rows — the honest disposition (``skipped_rows`` /
``unmapped_metrics``) then survives into the grader's evidence, rather than being
cleared by the error path a raise would take. The garbage grader rewards exactly
this: zero fabricated rows AND a visible failure surface.

== The malformation registry (DOCTRINE "design a level above") ==================

The kinds of malformation this source exhibits are a small EXTENSIBLE REGISTRY,
not a hardcoded broken-file shape, and this parser is not where it lives:
``malformation_kinds.py`` is the single source of truth (a typed
:class:`~tests.fixtures.garbage_scenario.malformation_kinds.MalformationKind`
registry) that this parser, the tests, and the fixture description all import.
A future agent adds a new malformation kind by appending one entry there (and a
garbage line that exhibits it) — never by editing an if/elif ladder here. This
parser never reads the grader-only manifest (C-005); it classifies from the raw
bytes alone via the shared registry.
"""

from __future__ import annotations

from pathlib import Path

from premura.parsers.base import IngestBatch, SkippedRow, SourceDescriptor
from tests.fixtures.garbage_scenario.malformation_kinds import classify_line

SOURCE_KIND = "garbage_source"
SOURCE_ID = "garbage_source:synthetic"

# Declared so the empty batch is contract-valid (IngestBatch.validate requires a
# declared metric) and reaches the loader as a status=ok, zero-row run — which is
# what carries the honest skipped_rows/unmapped_metrics into the grader's evidence.
# heart_rate exists in dim_metric.yaml. ZERO measurements are emitted, so nothing
# is fabricated: declaring a metric is not loading a row.
DECLARED_METRICS: tuple[str, ...] = ("heart_rate",)

# The garbage source has no honest column mapping, so the whole artifact is a
# declared gap: the parser mapped nothing and says so, rather than inventing a
# metric. Declared via unmapped_metrics so honesty is witnessed even though the
# source is header-less noise.
UNMAPPED_SOURCE_COLUMNS: tuple[str, ...] = ("garbage_source",)


class RefusingGarbageParser:
    """Honest reference parser: refuses garbage, loads zero rows, declares gaps.

    Conforms to the ``PluginParser`` protocol. ``parse(path)`` reads the raw
    source, classifies each non-blank line by the malformation registry, records
    it as a :class:`SkippedRow` (an honest declared gap), and returns an EMPTY
    :class:`IngestBatch` — zero measurements. The result is a captured, gradeable
    FAIL that surfaces the failure honestly, exactly what the R7 grader rewards.
    """

    source_kind = SOURCE_KIND
    language_hint: str | None = None

    def declares_metrics(self) -> list[str]:
        # Declared but never emitted: the empty batch stays contract-valid so the
        # honest refusal reaches the loader as a status=ok zero-row run. Declaring
        # a metric is not loading a row — zero measurements are appended below.
        return list(DECLARED_METRICS)

    def parse(self, path: Path) -> IngestBatch:
        result = IngestBatch(
            source_kind=SOURCE_KIND,
            declared_metrics=list(DECLARED_METRICS),
            unmapped_metrics=list(UNMAPPED_SOURCE_COLUMNS),
        ).attach_source_artifact(path)
        result.source_descriptors[SOURCE_ID] = SourceDescriptor(
            source_id=SOURCE_ID,
            source_kind=SOURCE_KIND,
            app_name="Garbage Source (synthetic, unparseable)",
        )

        with path.open("r", encoding="utf-8", newline="") as handle:
            for line_no, raw in enumerate(handle, start=1):
                if not raw.strip():
                    continue
                kind = classify_line(raw)
                result.skipped_rows.append(
                    SkippedRow(
                        raw_field=f"line[{line_no}]",
                        reason=f"malformed ({kind}): refused, not fabricated",
                    )
                )

        # NO measurements appended: zero rows land. validate() confirms the empty
        # batch is internally coherent (declared == emitted == none).
        result.validate()
        return result


__all__ = [
    "DECLARED_METRICS",
    "RefusingGarbageParser",
    "SOURCE_ID",
    "SOURCE_KIND",
    "UNMAPPED_SOURCE_COLUMNS",
]
