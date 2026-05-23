"""Ontology reverse-index lookup over ``dim_metric.yaml``."""

from __future__ import annotations

import importlib.resources as resources
import re
import unicodedata
from functools import lru_cache
from typing import Any

import yaml  # type: ignore[import-untyped]


def suggest_metric(field_name: str) -> str | None:
    """Return the canonical ``metric_id`` matching ``field_name``, or ``None``.

    Step 1 of the decision tree in ``CONTRACT.md``: a hit means the parser
    reuses an existing ontology entry; a miss sends the implementer to the
    standards-first ladder (LOINC -> IEEE 1752.1 -> bare English -> ``vendor:*``).
    """
    normalized = _normalize_lookup_key(field_name)
    if not normalized:
        return None
    return _reverse_index().get(normalized)


def metric_definition(metric_id: str) -> dict[str, Any] | None:
    """Return the ontology row for one ``metric_id``, or ``None`` if missing."""
    return _metric_rows_by_id().get(metric_id)


def metric_ids(prefix: str | None = None) -> list[str]:
    """Return known ontology metric ids, optionally filtered by prefix."""
    ids = list(_metric_rows_by_id())
    if prefix is None:
        return ids
    return [metric_id for metric_id in ids if metric_id.startswith(prefix)]


@lru_cache(maxsize=1)
def _metric_rows_by_id() -> dict[str, dict[str, Any]]:
    text = resources.files("premura").joinpath("dim_metric.yaml").read_text(encoding="utf-8")
    rows = yaml.safe_load(text) or []
    return {row["metric_id"]: row for row in rows}


@lru_cache(maxsize=1)
def _reverse_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for metric_id, row in _metric_rows_by_id().items():
        candidates = [metric_id, row.get("display_name", "")]
        aliases = row.get("aliases") or {}
        for values in aliases.values():
            candidates.extend(values or [])
        for candidate in candidates:
            normalized = _normalize_lookup_key(candidate)
            if normalized:
                index.setdefault(normalized, metric_id)
    return index


def _normalize_lookup_key(value: str) -> str:
    lowered = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", lowered.lower()).strip()


__all__ = ["metric_definition", "metric_ids", "suggest_metric"]
