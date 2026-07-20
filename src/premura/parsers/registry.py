"""The parser registry — the one place that maps a source to its parser.

Each entry binds a CLI ``source_key`` to a ``(parser factory, source_kind)``
pair. ``source_kind`` is the stable identifier a parser declares (CONTRACT.md:
``PluginParser.source_kind``) and the identity every downstream seam keys on.

This lives in the parsers package, not the CLI, because it is the authoritative
set of sources Premura can ingest — the CLI ``ingest`` command reads it, and so
does the Stage-4 device-interview safety rail (:func:`registered_source_kinds`),
which refuses to guide a human toward data no registered parser can read. Both
consumers derive from this single map so neither hardcodes a second copy of the
source list (DOCTRINE.md rule 2).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from .ai_chat_recall import AiChatRecallParser
from .bmt import BMTParser
from .fitbit_takeout import FitbitTakeoutParser
from .garmin_gdpr import GarminGDPRParser
from .health_connect import HealthConnectParser
from .lab_pdf import LabPdfParser
from .lab_xlsx import LabXlsxParser
from .myfitnesspal import MyFitnessPalParser
from .sleep_as_android import SleepAsAndroidParser
from .withings import WithingsParser


class _Parser(Protocol):
    def parse(self, path: Path): ...


PARSER_FACTORY = Callable[[], _Parser]

PARSER_REGISTRY: dict[str, tuple[PARSER_FACTORY, str]] = {
    "hc": (HealthConnectParser, "health_connect"),
    "garmin": (GarminGDPRParser, "garmin_gdpr"),
    "saa": (SleepAsAndroidParser, "sleep_as_android"),
    "bmt": (BMTParser, "bmt"),
    "lab": (LabPdfParser, "lab_pdf"),
    "labsheet": (LabXlsxParser, "labsheet"),
    "mfp": (MyFitnessPalParser, "myfitnesspal"),
    "aichat": (AiChatRecallParser, "ai_chat_recall"),
    "withings": (WithingsParser, "withings"),
    "fitbit": (FitbitTakeoutParser, "fitbit_takeout"),
}


def registered_source_kinds() -> frozenset[str]:
    """The live set of ``source_kind`` identifiers Premura has a parser for."""
    return frozenset(source_kind for _factory, source_kind in PARSER_REGISTRY.values())


__all__ = ["PARSER_FACTORY", "PARSER_REGISTRY", "registered_source_kinds"]
