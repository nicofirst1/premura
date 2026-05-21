"""Language detection and translation boundary — local-only, Phase 1 stub.

This package reserves the home for federated parsers that need to identify
the human language of a vendor's field labels or free-text fields before
mapping them to canonical metric IDs. All work here is "local-only": no
external API calls of any kind are permitted, neither for detection nor for
translation. This boundary exists to enforce Premura's offline-first privacy
constraint (constitution rule C-001) at the parser layer.

Translation is explicitly a TODO. Phase 1 ships the detection stub only; the
eventual implementation may add a local translation layer (for example via a
small offline model packaged with the parser plugin) but MUST NOT introduce
network calls to translation services, machine-translation APIs, or any
hosted endpoint. Reviewers should reject any future PR here that adds
dependencies such as ``langdetect`` and ``pycld3``, or translation libraries
of any kind, until the local-only constraint is reconfirmed by spec.

See ``src/premura/parsers/CONTRACT.md`` for how language detection feeds
``IngestBatch.language_detected``.
"""

from __future__ import annotations

__all__ = ["detect_language"]


def detect_language(text: str) -> str:
    """Return the detected ISO 639-1 language code for ``text``.

    Phase 1 stub. Raises :class:`NotImplementedError` until a future mission
    wires up a local-only detector. Implementations MUST run entirely
    on-device; outbound network calls are forbidden here.
    """
    raise NotImplementedError(
        "detect_language is a Phase 1 stub; local-only language detection "
        "ships in a later implementation mission."
    )
