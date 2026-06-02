"""Reference parser: a parser whose ``parse()`` RAISES before producing a batch.

This is a test fixture, NOT a shipped production parser. It is the adversary for
the ingest-failure path (spec edge case "parser raises / never produces a batch",
FR-080): a real ``PluginParser`` whose ``parse()`` raises before any
:class:`IngestBatch` exists, so the in-sandbox ingest runner never reaches
``duck.initialize(warehouse)`` and NO warehouse file is created.

When installed and run through the harness it must yield a CAPTURED, GRADED FAIL
— the ``ingest_run`` step status is ``error``, a provenance row is recorded, the
session is finished, and the grader returns ``passed == False`` (no partial
credit) — never an uncaught crash that aborts the run.
"""

from __future__ import annotations

from pathlib import Path

from premura.parsers.base import IngestBatch

SOURCE_KIND = "fitbit_heart_rate"


class RaisingFitbitHrParser:
    """A parser that raises before producing a batch (models a buggy/failing parser)."""

    source_kind = SOURCE_KIND
    language_hint: str | None = None

    def declares_metrics(self) -> list[str]:
        return ["heart_rate"]

    def parse(self, path: Path) -> IngestBatch:  # noqa: ARG002 - never produces a batch
        raise ValueError("synthetic parser failure")


__all__ = ["RaisingFitbitHrParser", "SOURCE_KIND"]
