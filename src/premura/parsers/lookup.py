"""Ontology reverse-index lookup — Phase 1 stub.

This module reserves the location that future federated-parser code (and the
``parser-generator`` Claude Code skill) calls first when resolving a vendor
field name to a canonical ``metric_id``. The eventual implementation will
build a reverse index over ``dim_metric.yaml``'s canonical IDs and the
``aliases`` collection on each row, normalising casing/punctuation/whitespace
so that, for example, ``"Resting Heart Rate"``, ``"rhr"`` and
``"resting_hr"`` all resolve to the same canonical metric.

Phase 1 ships the symbol only — no YAML loading, no alias-index construction,
and no fallback heuristics. See ``src/premura/parsers/CONTRACT.md`` for the
full decision tree this lookup anchors.
"""

from __future__ import annotations


def suggest_metric(field_name: str) -> str | None:
    """Return the canonical ``metric_id`` matching ``field_name``, or ``None``.

    Step 1 of the decision tree in ``CONTRACT.md``: a hit means the parser
    reuses an existing ontology entry; a miss sends the implementer to the
    standards-first ladder (LOINC → IEEE 1752.1 → bare English → ``vendor:*``).

    Phase 1 stub. Raises :class:`NotImplementedError` until a future mission
    materialises the reverse index over ``dim_metric.yaml``.
    """
    raise NotImplementedError(
        "suggest_metric is a Phase 1 stub; the reverse index over "
        "dim_metric.yaml ships in a later implementation mission."
    )
