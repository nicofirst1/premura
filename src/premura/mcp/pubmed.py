"""Premura-owned PubMed grounding provider (Stage 3).

This module is the executable core of the PubMed grounding contract. It exposes
exactly two operations behind a Premura-owned adapter:

* :func:`pubmed_search` — find candidate literature records. Candidates are
  discovery hints only and carry ``citation_status = "candidate_only"``; they are
  **never** citeable.
* :func:`pubmed_fetch` — retrieve one record by exact PMID. Only a fetched record
  carries ``citation_status = "citeable_fetched_record"`` and the PubMed
  provenance (``pubmed_url`` + ``provider``) an honest citation needs.

The candidate-vs-fetched citation rule is a *Premura* invariant, not a provider
feature, so this adapter owns it (research.md, "Final Decision"). The provider
behind the adapter is NCBI E-utilities — ESearch to find PMIDs, ESummary to read
the structured record (and to enrich search candidates with human-readable
titles), and EFetch to retrieve the abstract of a fetched record when one is
available — called over the Python standard library (``urllib``) so no HTTP
dependency is added. The candidate-title and abstract enrichments are
best-effort: if the enriching call fails, search still returns its PMIDs and a
fetched record still returns its structured metadata, with the missing piece
left explicitly absent rather than fabricated.

Design notes that the tests lock:

* **Injectable transport seam.** Every network call goes through a ``Transport``
  callable (``transport(endpoint, params) -> str``). The default real transport
  uses ``urllib``; tests inject a fake that returns canned E-utilities XML, so the
  default suite is fully offline and deterministic and exercises the real parsing
  path. There is no network call at import time and no background activity.
* **Ordinary failures are data, not exceptions.** No-results, an invalid/unknown
  PMID, and provider/transport errors all return a structured outcome dict with a
  machine-branchable ``status``. Exceptions are reserved for caller programming
  errors (empty query / empty PMID) and unexpected transport faults that the
  adapter then catches and converts to a ``provider_error`` outcome.
* **Missingness is explicit.** Absent optional metadata stays ``None`` (or an
  empty list for authors). Abstracts, authors, journals, and dates are never
  fabricated.

Out of scope by contract: full-text retrieval, deep paper analysis, Europe PMC /
Unpaywall, MeSH / related-article / spell-check / id-conversion, and any computed
claim about the user's own warehouse data. This module reads no ``hp.*`` rows.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from xml.etree import ElementTree as ET

#: Stable provider label recorded on fetched records. The first slice uses a
#: single native NCBI E-utilities provider; the field stays present so additional
#: providers can be distinguished later without a schema change (data-model.md).
PROVIDER_NAME = "ncbi-eutils"

#: Source label for candidate records.
SOURCE_LABEL = "PubMed"

#: Default and hard cap on the number of candidates a search may return. The cap
#: is enforced (clamped), not trusted from the caller.
DEFAULT_SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 20

#: Plain statement attached to every search result so a narrating agent always
#: sees the citation rule alongside the candidates.
CITATION_RULE = (
    "These are candidate search results and are NOT citeable. Fetch a record by "
    "exact PMID with pubmed_fetch to obtain a citeable record before citing it."
)

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_ESEARCH_ENDPOINT = f"{_EUTILS_BASE}/esearch.fcgi"
_ESUMMARY_ENDPOINT = f"{_EUTILS_BASE}/esummary.fcgi"
_EFETCH_ENDPOINT = f"{_EUTILS_BASE}/efetch.fcgi"
_PUBMED_RECORD_BASE = "https://pubmed.ncbi.nlm.nih.gov"
_HTTP_TIMEOUT_SECONDS = 15


class PubMedTransportError(RuntimeError):
    """Raised by a transport when the provider could not be reached/queried.

    The adapter catches this and converts it into a structured ``provider_error``
    outcome, so callers of :func:`pubmed_search` / :func:`pubmed_fetch` see data,
    not an exception, for an ordinary provider/network failure.
    """


class Transport(Protocol):
    """The injectable HTTP/provider seam.

    A transport is any callable that, given an E-utilities endpoint URL and a
    mapping of query parameters, returns the raw response text. The default real
    implementation (:func:`_urllib_transport`) uses ``urllib``; tests inject a
    fake that returns canned XML.
    """

    def __call__(self, endpoint: str, params: dict[str, str]) -> str: ...


# --------------------------------------------------------------------------- #
# Typed records
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PubMedCandidate:
    """A search hit. Useful for discovery, never citeable."""

    pmid: str
    title: str | None = None
    snippet: str | None = None
    source: str = SOURCE_LABEL
    citation_status: str = "candidate_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pmid": self.pmid,
            "title": self.title,
            "snippet": self.snippet,
            "source": self.source,
            "citation_status": self.citation_status,
        }


@dataclass(frozen=True)
class PubMedFetchedRecord:
    """A record fetched by exact PMID — the only citeable shape."""

    pmid: str
    pubmed_url: str
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    journal: str | None = None
    publication_date: str | None = None
    abstract: str | None = None
    provider: str = PROVIDER_NAME
    fetched_at: str | None = None
    citation_status: str = "citeable_fetched_record"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pmid": self.pmid,
            "title": self.title,
            "authors": list(self.authors),
            "journal": self.journal,
            "publication_date": self.publication_date,
            "abstract": self.abstract,
            "pubmed_url": self.pubmed_url,
            "provider": self.provider,
            "fetched_at": self.fetched_at,
            "citation_status": self.citation_status,
        }


# --------------------------------------------------------------------------- #
# Public operations
# --------------------------------------------------------------------------- #


def pubmed_search(
    query: str,
    *,
    limit: int = DEFAULT_SEARCH_LIMIT,
    sort: str | None = None,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Search PubMed for candidate records (``citation_status = candidate_only``).

    ``query`` must be non-empty after trimming (empty input is a caller error and
    raises ``ValueError``). ``limit`` is clamped to at most
    :data:`MAX_SEARCH_LIMIT` — the cap is enforced, not trusted.

    Ordinary outcomes are returned as data, never raised:

    * ``status == "available"`` with a ``candidates`` list (each
      ``candidate_only``), a ``count``, and the ``citation_rule``.
    * ``status == "no_results"`` with an empty ``candidates`` list and a message.
    * ``status == "provider_error"`` with an empty list and a message when the
      transport could not reach the provider.
    """
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("query must not be empty")

    effective_limit = _clamp_limit(limit)
    send = transport or _urllib_transport

    params = {
        "db": "pubmed",
        "term": cleaned,
        "retmax": str(effective_limit),
        "retmode": "xml",
    }
    if sort:
        params["sort"] = sort

    try:
        raw = send(_ESEARCH_ENDPOINT, params)
        pmids = _parse_esearch_ids(raw)
    except PubMedTransportError as exc:
        return {
            "status": "provider_error",
            "query": cleaned,
            "candidates": [],
            "count": 0,
            "message": f"PubMed search could not be completed: {exc}",
            "retryable": True,
        }
    except ET.ParseError as exc:
        return {
            "status": "provider_error",
            "query": cleaned,
            "candidates": [],
            "count": 0,
            "message": f"PubMed returned an unparseable search response: {exc}",
            "retryable": True,
        }

    if not pmids:
        return {
            "status": "no_results",
            "query": cleaned,
            "candidates": [],
            "count": 0,
            "message": "No PubMed records matched this query.",
        }

    selected = pmids[:effective_limit]
    # Best-effort enrichment: ESummary gives each candidate a human-readable title
    # (and a short journal/date snippet) so an agent can choose which PMID to fetch
    # instead of fetching blind. If the summary call fails we still return the
    # PMIDs — the core search contract — with titles left explicitly absent.
    titles = _candidate_summaries(selected, send)
    candidates = [
        PubMedCandidate(
            pmid=pmid,
            title=titles.get(pmid, (None, None))[0],
            snippet=titles.get(pmid, (None, None))[1],
        )
        for pmid in selected
    ]
    return {
        "status": "available",
        "query": cleaned,
        "candidates": [c.to_dict() for c in candidates],
        "count": len(candidates),
        "citation_rule": CITATION_RULE,
    }


def pubmed_fetch(
    pmid: str,
    *,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Fetch one PubMed record by exact PMID (``citeable_fetched_record``).

    ``pmid`` must be non-empty after trimming (empty input is a caller error and
    raises ``ValueError``). Ordinary outcomes are returned as data, never raised:

    * ``status == "available"`` with a citeable ``record`` carrying ``pmid``,
      ``pubmed_url`` provenance, and ``provider``.
    * ``status == "invalid_pmid"`` when the provider reports the UID is invalid.
    * ``status == "unavailable"`` when the provider returns no record.
    * ``status == "provider_error"`` when the transport could not reach the
      provider.

    Missing optional metadata stays ``None`` / empty — never fabricated.
    """
    cleaned = pmid.strip()
    if not cleaned:
        raise ValueError("pmid must not be empty")

    send = transport or _urllib_transport
    params = {"db": "pubmed", "id": cleaned, "retmode": "xml"}

    try:
        raw = send(_ESUMMARY_ENDPOINT, params)
        parsed = _parse_esummary(raw, cleaned)
    except PubMedTransportError as exc:
        return {
            "status": "provider_error",
            "pmid": cleaned,
            "message": f"PubMed record could not be fetched: {exc}",
            "retryable": True,
        }
    except ET.ParseError as exc:
        return {
            "status": "provider_error",
            "pmid": cleaned,
            "message": f"PubMed returned an unparseable fetch response: {exc}",
            "retryable": True,
        }

    if parsed.error is not None:
        return {
            "status": "invalid_pmid",
            "pmid": cleaned,
            "message": parsed.error,
            "retryable": False,
        }
    if not parsed.found:
        return {
            "status": "unavailable",
            "pmid": cleaned,
            "message": f"No PubMed record was returned for PMID {cleaned}.",
            "retryable": True,
        }

    # ESummary carries the structured citation metadata but not the abstract, so we
    # make a best-effort EFetch call for the abstract text. The spec requires the
    # abstract "when available": if EFetch fails or the record has no abstract, it
    # stays None rather than being fabricated, and the fetch still succeeds.
    abstract = _fetch_abstract(cleaned, send)

    record = PubMedFetchedRecord(
        pmid=cleaned,
        pubmed_url=_pubmed_url(cleaned),
        title=parsed.title,
        authors=parsed.authors,
        journal=parsed.journal,
        publication_date=parsed.publication_date,
        abstract=abstract,
        fetched_at=datetime.now(UTC).isoformat(),
    )
    return {"status": "available", "record": record.to_dict()}


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _clamp_limit(limit: int) -> int:
    """Clamp the requested candidate count into ``1..MAX_SEARCH_LIMIT``."""
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    if limit < 1:
        return 1
    return min(limit, MAX_SEARCH_LIMIT)


def _pubmed_url(pmid: str) -> str:
    return f"{_PUBMED_RECORD_BASE}/{pmid}/"


def _parse_esearch_ids(raw: str) -> list[str]:
    """Extract the PMID list from an ESearch XML response (order preserved)."""
    root = ET.fromstring(raw)
    return [el.text.strip() for el in root.findall(".//IdList/Id") if el.text and el.text.strip()]


@dataclass(frozen=True)
class _ParsedSummary:
    """Internal parse result for one ESummary DocSum.

    The abstract is intentionally absent here: ESummary does not carry it, so it is
    sourced separately via EFetch in :func:`pubmed_fetch`.
    """

    found: bool
    error: str | None = None
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    journal: str | None = None
    publication_date: str | None = None


def _parse_esummary(raw: str, pmid: str) -> _ParsedSummary:
    """Parse an ESummary XML response for one expected PMID.

    Missingness is preserved: a field absent from the DocSum stays ``None`` (or an
    empty author list). An NCBI ``<error>`` inside the DocSum is surfaced as an
    invalid-PMID signal; a missing DocSum is surfaced as not-found.
    """
    root = ET.fromstring(raw)
    docsum = root.find(".//DocSum")
    if docsum is None:
        return _ParsedSummary(found=False)

    error_el = docsum.find("error")
    if error_el is not None:
        message = (error_el.text or "").strip() or f"Invalid PMID {pmid}."
        return _ParsedSummary(found=False, error=message)

    title = _item_text(docsum, "Title")
    journal = _item_text(docsum, "FullJournalName") or _item_text(docsum, "Source")
    publication_date = _item_text(docsum, "PubDate")
    authors = _author_list(docsum)

    return _ParsedSummary(
        found=True,
        title=title,
        authors=authors,
        journal=journal,
        publication_date=publication_date,
    )


def _candidate_summaries(
    pmids: list[str], send: Transport
) -> dict[str, tuple[str | None, str | None]]:
    """Best-effort map ``pmid -> (title, snippet)`` for search candidates.

    Calls ESummary once for all selected PMIDs. Any transport/parse failure
    degrades to an empty map so the caller falls back to PMID-only candidates;
    titles are never fabricated for a PMID the provider did not describe.
    """
    if not pmids:
        return {}
    try:
        raw = send(
            _ESUMMARY_ENDPOINT,
            {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
        )
        root = ET.fromstring(raw)
    except (PubMedTransportError, ET.ParseError):
        return {}

    summaries: dict[str, tuple[str | None, str | None]] = {}
    for docsum in root.findall(".//DocSum"):
        id_el = docsum.find("Id")
        pmid = (id_el.text or "").strip() if id_el is not None and id_el.text else ""
        if not pmid or docsum.find("error") is not None:
            continue
        title = _item_text(docsum, "Title")
        journal = _item_text(docsum, "FullJournalName") or _item_text(docsum, "Source")
        publication_date = _item_text(docsum, "PubDate")
        snippet_parts = [part for part in (journal, publication_date) if part]
        snippet = ", ".join(snippet_parts) if snippet_parts else None
        summaries[pmid] = (title, snippet)
    return summaries


def _fetch_abstract(pmid: str, send: Transport) -> str | None:
    """Best-effort abstract text for one PMID via EFetch.

    Returns the joined ``AbstractText`` sections (labels preserved when present),
    or ``None`` when EFetch fails or the record carries no abstract. The abstract
    is "when available" per the contract, so a failure here is not a fetch error.
    """
    try:
        raw = send(
            _EFETCH_ENDPOINT,
            {"db": "pubmed", "id": pmid, "retmode": "xml", "rettype": "abstract"},
        )
        root = ET.fromstring(raw)
    except (PubMedTransportError, ET.ParseError):
        return None

    parts: list[str] = []
    for el in root.findall(".//Abstract/AbstractText"):
        text = "".join(el.itertext()).strip()
        if not text:
            continue
        label = el.get("Label")
        parts.append(f"{label}: {text}" if label else text)
    return "\n\n".join(parts) if parts else None


def _item_text(docsum: ET.Element, name: str) -> str | None:
    """Return the trimmed text of a named top-level ``<Item>`` or ``None``."""
    for item in docsum.findall("Item"):
        if item.get("Name") == name:
            text = (item.text or "").strip()
            return text or None
    return None


def _author_list(docsum: ET.Element) -> list[str]:
    """Collect author names from the ``AuthorList`` item; empty when absent."""
    for item in docsum.findall("Item"):
        if item.get("Name") == "AuthorList":
            names = [
                (sub.text or "").strip()
                for sub in item.findall("Item")
                if sub.get("Name") == "Author" and (sub.text or "").strip()
            ]
            return names
    return []


def _urllib_transport(endpoint: str, params: dict[str, str]) -> str:
    """Default real transport: GET ``endpoint?params`` over stdlib ``urllib``.

    Transport-level failures (network, HTTP error, timeout) are normalized to
    :class:`PubMedTransportError` so the adapter can convert them into a
    structured ``provider_error`` outcome rather than leaking an arbitrary
    exception type to the caller.
    """
    url = f"{endpoint}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "premura-pubmed/0.1"})
    try:
        with urllib.request.urlopen(  # noqa: S310 - fixed https NCBI host only
            request, timeout=_HTTP_TIMEOUT_SECONDS
        ) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PubMedTransportError(str(exc)) from exc


__all__ = [
    "CITATION_RULE",
    "DEFAULT_SEARCH_LIMIT",
    "MAX_SEARCH_LIMIT",
    "PROVIDER_NAME",
    "PubMedCandidate",
    "PubMedFetchedRecord",
    "PubMedTransportError",
    "Transport",
    "pubmed_fetch",
    "pubmed_search",
]
