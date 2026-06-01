"""WP02 — Premura-owned PubMed grounding provider contract tests.

These lock the Stage 3 PubMed grounding behavior *before* any MCP tool
registration (that is WP03's job). They drive the public surface of
:mod:`premura.mcp.pubmed` — ``pubmed_search`` / ``pubmed_fetch`` — and assert the
contract output fields, especially ``citation_status``.

The whole suite is offline and deterministic: every test injects a FAKE
transport (the HTTP/provider seam) so no test touches live NCBI E-utilities. The
fake speaks the same minimal interface the real transport implements — given an
E-utilities endpoint + params it returns canned response text — so the tests
exercise the real parsing/serialization code path, only the network is faked.

Contract invariants under test:

* search success → candidates carry ``pmid`` + ``source`` +
  ``citation_status == "candidate_only"``; a ``citation_rule`` is present.
* search no-results → ``status == "no_results"`` and an empty candidate list.
* fetch success → ``citation_status == "citeable_fetched_record"`` with ``pmid``,
  ``pubmed_url`` provenance, and ``provider == "ncbi-eutils"``.
* fetch with missing optional metadata → fields stay ``None`` / absent, never
  fabricated.
* invalid/unavailable PMID → a structured outcome (data), not an exception.
* search default limit is at most 20 candidates (clamped, not trusted).
"""

from __future__ import annotations

import pytest

from premura.mcp import pubmed

# --------------------------------------------------------------------------- #
# Deterministic E-utilities response fixtures
# --------------------------------------------------------------------------- #

_ESEARCH_THREE_HITS = """<?xml version="1.0" ?>
<eSearchResult>
  <Count>3</Count>
  <RetMax>3</RetMax>
  <IdList>
    <Id>40000001</Id>
    <Id>40000002</Id>
    <Id>40000003</Id>
  </IdList>
</eSearchResult>"""

_ESEARCH_NO_HITS = """<?xml version="1.0" ?>
<eSearchResult>
  <Count>0</Count>
  <RetMax>0</RetMax>
  <IdList/>
</eSearchResult>"""

# A summary doc with full metadata for the fetch-success path.
_ESUMMARY_FULL = """<?xml version="1.0" ?>
<eSummaryResult>
  <DocSum>
    <Id>40000001</Id>
    <Item Name="Title" Type="String">Sleep duration and resting heart rate</Item>
    <Item Name="FullJournalName" Type="String">Journal of Sleep Research</Item>
    <Item Name="PubDate" Type="Date">2024 Mar 15</Item>
    <Item Name="AuthorList" Type="List">
      <Item Name="Author" Type="String">Doe J</Item>
      <Item Name="Author" Type="String">Smith A</Item>
    </Item>
  </DocSum>
</eSummaryResult>"""

# A summary doc that omits journal / date / authors entirely. Missing optional
# fields must stay None, never invented.
_ESUMMARY_SPARSE = """<?xml version="1.0" ?>
<eSummaryResult>
  <DocSum>
    <Id>40000002</Id>
    <Item Name="Title" Type="String">A title with no other metadata</Item>
  </DocSum>
</eSummaryResult>"""

# An ESummary error doc — NCBI returns a DocSum carrying an <error> for an
# unknown / malformed UID rather than HTTP 4xx.
_ESUMMARY_ERROR = """<?xml version="1.0" ?>
<eSummaryResult>
  <DocSum>
    <Id>99999999</Id>
    <error>Invalid uid 99999999</error>
  </DocSum>
</eSummaryResult>"""

_ESUMMARY_EMPTY = """<?xml version="1.0" ?>
<eSummaryResult>
</eSummaryResult>"""

# A multi-record ESummary used to enrich search candidates with titles. Two of the
# three searched PMIDs are described; the third (40000003) is intentionally absent
# so its title must stay None (never fabricated).
_ESUMMARY_SEARCH_ENRICH = """<?xml version="1.0" ?>
<eSummaryResult>
  <DocSum>
    <Id>40000001</Id>
    <Item Name="Title" Type="String">Sleep duration and resting heart rate</Item>
    <Item Name="FullJournalName" Type="String">Journal of Sleep Research</Item>
    <Item Name="PubDate" Type="Date">2024 Mar 15</Item>
  </DocSum>
  <DocSum>
    <Id>40000002</Id>
    <Item Name="Title" Type="String">HRV and training load</Item>
  </DocSum>
</eSummaryResult>"""

# EFetch carrying an abstract (two labeled sections) for the fetch-abstract path.
_EFETCH_WITH_ABSTRACT = """<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <Abstract>
          <AbstractText Label="BACKGROUND">Sleep affects recovery.</AbstractText>
          <AbstractText Label="RESULTS">Longer sleep lowered resting heart rate.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""

# EFetch for a record with no abstract element — abstract must stay None.
_EFETCH_NO_ABSTRACT = """<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article/>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""


class FakeTransport:
    """A deterministic stand-in for the real HTTP transport seam.

    The real provider calls ``transport(endpoint, params)`` and gets back the raw
    response text. The fake routes on the endpoint (``esearch`` vs ``esummary``)
    and returns whichever canned document the test wired in, recording calls so a
    test can assert what was requested (e.g. the clamped ``retmax``).
    """

    def __init__(
        self,
        *,
        esearch: str | None = None,
        esummary: str | None = None,
        efetch: str | None = None,
    ) -> None:
        self._esearch = esearch
        self._esummary = esummary
        self._efetch = efetch
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, endpoint: str, params: dict[str, str]) -> str:
        self.calls.append((endpoint, dict(params)))
        if "esearch" in endpoint:
            if self._esearch is None:
                raise AssertionError("unexpected esearch call")
            return self._esearch
        if "efetch" in endpoint:
            # An EFetch fixture is preferred; fall back to the esummary doc so a
            # test that wires only esummary still gets a parseable (abstract-free)
            # response and the abstract stays None.
            if self._efetch is not None:
                return self._efetch
            if self._esummary is not None:
                return self._esummary
            raise AssertionError("unexpected efetch call")
        if "esummary" in endpoint:
            if self._esummary is None:
                raise AssertionError("unexpected esummary call")
            return self._esummary
        raise AssertionError(f"unexpected endpoint {endpoint!r}")


class ExplodingTransport:
    """Transport that raises a transport-layer error, as a flaky network would."""

    def __call__(self, endpoint: str, params: dict[str, str]) -> str:
        raise pubmed.PubMedTransportError("boom: network unreachable")


# --------------------------------------------------------------------------- #
# pubmed_search
# --------------------------------------------------------------------------- #


def test_search_success_returns_candidate_only_records() -> None:
    transport = FakeTransport(esearch=_ESEARCH_THREE_HITS, esummary=_ESUMMARY_SEARCH_ENRICH)
    result = pubmed.pubmed_search("sleep heart rate", transport=transport)

    assert result["status"] == "available"
    assert result["query"] == "sleep heart rate"
    assert result["count"] == 3
    assert len(result["candidates"]) == 3
    assert "citation_rule" in result and result["citation_rule"]

    for candidate in result["candidates"]:
        assert candidate["pmid"]
        assert candidate["source"]
        # The product invariant: search candidates are NEVER citeable.
        assert candidate["citation_status"] == "candidate_only"

    pmids = [c["pmid"] for c in result["candidates"]]
    assert pmids == ["40000001", "40000002", "40000003"]


def test_search_candidates_carry_human_readable_titles_when_available() -> None:
    # Scenario 1: search returns candidate PMIDs AND human-readable titles when
    # PubMed has matches. Titles come from a best-effort ESummary enrichment.
    transport = FakeTransport(esearch=_ESEARCH_THREE_HITS, esummary=_ESUMMARY_SEARCH_ENRICH)
    result = pubmed.pubmed_search("sleep heart rate", transport=transport)

    by_pmid = {c["pmid"]: c for c in result["candidates"]}
    assert by_pmid["40000001"]["title"] == "Sleep duration and resting heart rate"
    assert by_pmid["40000001"]["snippet"] == "Journal of Sleep Research, 2024 Mar 15"
    assert by_pmid["40000002"]["title"] == "HRV and training load"
    # A PMID the provider did not describe keeps a None title — never fabricated.
    assert by_pmid["40000003"]["title"] is None
    # Enrichment never changes the citation status.
    assert all(c["citation_status"] == "candidate_only" for c in result["candidates"])


def test_search_degrades_to_pmids_when_title_enrichment_unavailable() -> None:
    # If the ESummary enrichment call fails, search still returns its PMIDs (the
    # core contract) with titles left explicitly absent.
    class EsearchOnlyTransport:
        def __call__(self, endpoint: str, params: dict[str, str]) -> str:
            if "esearch" in endpoint:
                return _ESEARCH_THREE_HITS
            raise pubmed.PubMedTransportError("summary unavailable")

    result = pubmed.pubmed_search("sleep heart rate", transport=EsearchOnlyTransport())

    assert result["status"] == "available"
    assert [c["pmid"] for c in result["candidates"]] == ["40000001", "40000002", "40000003"]
    assert all(c["title"] is None for c in result["candidates"])
    assert all(c["citation_status"] == "candidate_only" for c in result["candidates"])


def test_search_no_results_is_structured_not_empty_success() -> None:
    transport = FakeTransport(esearch=_ESEARCH_NO_HITS)
    result = pubmed.pubmed_search("no such topic xyzzy", transport=transport)

    assert result["status"] == "no_results"
    assert result["candidates"] == []
    assert result["query"] == "no such topic xyzzy"
    assert result["message"]


def test_search_clamps_default_limit_to_at_most_20() -> None:
    transport = FakeTransport(esearch=_ESEARCH_THREE_HITS, esummary=_ESUMMARY_SEARCH_ENRICH)
    pubmed.pubmed_search("anything", transport=transport)

    # The provider must request no more than the default cap from the provider.
    endpoint, params = transport.calls[0]
    assert "esearch" in endpoint
    assert int(params["retmax"]) <= 20


def test_search_clamps_caller_supplied_oversized_limit() -> None:
    transport = FakeTransport(esearch=_ESEARCH_THREE_HITS, esummary=_ESUMMARY_SEARCH_ENRICH)
    pubmed.pubmed_search("anything", limit=10_000, transport=transport)

    _endpoint, params = transport.calls[0]
    assert int(params["retmax"]) <= 20


def test_search_rejects_empty_query() -> None:
    transport = FakeTransport(esearch=_ESEARCH_THREE_HITS)
    with pytest.raises(ValueError):
        pubmed.pubmed_search("   ", transport=transport)


def test_search_provider_error_is_data_not_exception() -> None:
    result = pubmed.pubmed_search("anything", transport=ExplodingTransport())
    assert result["status"] == "provider_error"
    assert result["candidates"] == []
    assert result["message"]


# --------------------------------------------------------------------------- #
# pubmed_fetch
# --------------------------------------------------------------------------- #


def test_fetch_success_returns_citeable_record_with_provenance() -> None:
    transport = FakeTransport(esummary=_ESUMMARY_FULL)
    result = pubmed.pubmed_fetch("40000001", transport=transport)

    assert result["status"] == "available"
    record = result["record"]
    assert record["pmid"] == "40000001"
    # The product invariant: only an exact PMID fetch yields a citeable record.
    assert record["citation_status"] == "citeable_fetched_record"

    # Provenance must be preserved for honest citation.
    assert record["pubmed_url"].endswith("/40000001/")
    assert "40000001" in record["pubmed_url"]
    assert record["provider"] == "ncbi-eutils"

    # Present metadata is surfaced, not dropped.
    assert record["title"] == "Sleep duration and resting heart rate"
    assert record["journal"] == "Journal of Sleep Research"
    assert record["publication_date"] == "2024 Mar 15"
    assert record["authors"] == ["Doe J", "Smith A"]


def test_fetch_includes_abstract_when_available() -> None:
    # FR-004 / Scenario 2: a fetched record includes abstract text when PubMed has
    # one. Structured metadata comes from ESummary; the abstract from EFetch.
    transport = FakeTransport(esummary=_ESUMMARY_FULL, efetch=_EFETCH_WITH_ABSTRACT)
    result = pubmed.pubmed_fetch("40000001", transport=transport)

    assert result["status"] == "available"
    record = result["record"]
    assert record["citation_status"] == "citeable_fetched_record"
    assert record["abstract"] == (
        "BACKGROUND: Sleep affects recovery.\n\nRESULTS: Longer sleep lowered resting heart rate."
    )
    # Structured ESummary fields are still present alongside the EFetch abstract.
    assert record["title"] == "Sleep duration and resting heart rate"


def test_fetch_abstract_absent_stays_none_when_efetch_has_no_abstract() -> None:
    transport = FakeTransport(esummary=_ESUMMARY_FULL, efetch=_EFETCH_NO_ABSTRACT)
    result = pubmed.pubmed_fetch("40000001", transport=transport)

    assert result["status"] == "available"
    # No abstract element in EFetch → explicit None, never fabricated.
    assert result["record"]["abstract"] is None


def test_fetch_succeeds_with_none_abstract_when_efetch_fails() -> None:
    # The abstract is "when available": if the EFetch call fails, the fetch still
    # returns a citeable record with the structured metadata and abstract = None.
    class EsummaryOnlyTransport:
        def __call__(self, endpoint: str, params: dict[str, str]) -> str:
            if "esummary" in endpoint:
                return _ESUMMARY_FULL
            raise pubmed.PubMedTransportError("efetch unavailable")

    result = pubmed.pubmed_fetch("40000001", transport=EsummaryOnlyTransport())

    assert result["status"] == "available"
    assert result["record"]["citation_status"] == "citeable_fetched_record"
    assert result["record"]["title"] == "Sleep duration and resting heart rate"
    assert result["record"]["abstract"] is None


def test_fetch_missing_optional_metadata_is_none_not_fabricated() -> None:
    transport = FakeTransport(esummary=_ESUMMARY_SPARSE)
    result = pubmed.pubmed_fetch("40000002", transport=transport)

    assert result["status"] == "available"
    record = result["record"]
    assert record["pmid"] == "40000002"
    assert record["citation_status"] == "citeable_fetched_record"
    assert record["title"] == "A title with no other metadata"

    # Absent optional metadata stays explicitly None — never invented.
    assert record["journal"] is None
    assert record["publication_date"] is None
    assert record["abstract"] is None
    assert record["authors"] == []


def test_fetch_invalid_pmid_is_structured_outcome_not_exception() -> None:
    transport = FakeTransport(esummary=_ESUMMARY_ERROR)
    result = pubmed.pubmed_fetch("99999999", transport=transport)

    assert result["status"] in {"invalid_pmid", "unavailable"}
    assert result["pmid"] == "99999999"
    assert result["message"]
    # No fabricated citeable record on failure.
    assert "record" not in result or result.get("record") is None


def test_fetch_empty_result_is_unavailable_outcome() -> None:
    transport = FakeTransport(esummary=_ESUMMARY_EMPTY)
    result = pubmed.pubmed_fetch("40000001", transport=transport)

    assert result["status"] in {"unavailable", "invalid_pmid"}
    assert result["pmid"] == "40000001"
    assert result["message"]


def test_fetch_rejects_empty_pmid() -> None:
    transport = FakeTransport(esummary=_ESUMMARY_FULL)
    with pytest.raises(ValueError):
        pubmed.pubmed_fetch("   ", transport=transport)


def test_fetch_provider_error_is_data_not_exception() -> None:
    result = pubmed.pubmed_fetch("40000001", transport=ExplodingTransport())
    assert result["status"] == "provider_error"
    assert result["pmid"] == "40000001"
    assert result["message"]


# --------------------------------------------------------------------------- #
# Module hygiene — no live network / background activity at import time
# --------------------------------------------------------------------------- #


def test_module_exposes_only_the_two_contract_operations() -> None:
    # The public surface is exactly the two contract operations (plus the typed
    # error and provider label); no third-party tool names, no extra capabilities.
    assert hasattr(pubmed, "pubmed_search")
    assert hasattr(pubmed, "pubmed_fetch")
    for forbidden in ("full_text", "europe_pmc", "mesh_lookup", "related_articles"):
        assert not hasattr(pubmed, forbidden)


def test_provider_label_is_stable() -> None:
    assert pubmed.PROVIDER_NAME == "ncbi-eutils"
