# Phase 0 Research: PubMed Grounding Tools

## Decision 1: Use an adopt-vs-wrap-vs-build gate before implementation

**Decision**: Implementation must begin with an explicit comparison of existing PubMed MCP servers and adjacent PubMed integration options, then choose one of three paths: adopt directly, wrap behind a Premura-owned contract, or build minimal native support. This research gate (WP01) resolves that choice so WP02 inherits a single path, not an open question.

**Rationale**: The maintainer found multiple existing PubMed MCP servers and asked Phase 0 to look beyond the three named ones. Premura should not build a custom integration without checking prior art, but it also should not expose a third-party MCP surface directly if that surface bypasses Premura's citation rule or stage boundaries.

**Alternatives considered**:
- Build native first without a survey: simpler to control, but ignores existing working MCP tools and risks reinventing solved E-utilities plumbing.
- Adopt an existing MCP server directly: fastest, but (as the survey below shows) every surveyed server is broader than two tools and hard to constrain to Premura's product contract.
- Wrap or adapt: preserves Premura's contract while allowing reuse where appropriate.

## Decision 2: Candidates evaluated (seed + broadened survey)

**Decision**: Phase 0 evaluated the three maintainer-supplied candidates and broadened the search to additional PubMed/biomedical MCP servers and PubMed client libraries. The comparison below is against Premura's contract (two narrow tools, candidate-vs-fetched citation rule, local-first, no out-of-scope tools on the default surface), **not** against feature richness.

**Seed candidates**:
- `https://mcpservers.org/servers/aeghnnsw/pubmed-mcp`
- `https://github.com/JackKuo666/PubMed-MCP-Server`
- `https://github.com/cyanheads/pubmed-mcp-server`

### Search routes attempted (2026-06)

- `WebSearch` for "PubMed MCP server biomedical literature model context protocol" — succeeded; surfaced `aeghnnsw`, `cyanheads`, `JackKuo666`, plus new candidates `genomoncology/biomcp`, `augmented-nature/pubmed-mcp-server`, and `wavelovey` PubMed Search MCP.
- `WebSearch` for PubMed Python client libraries — succeeded; surfaced Biopython `Bio.Entrez`, `entrezpy`, `metapub`, `pymed` (and its maintained fork `pymed-paperscraper`), `pubmed-api`, `pmidcite`, `suppevo-pubmed-mcp`.
- Direct GitHub repository search (`gh search repos` / GitHub UI) returned HTTP 429 during the original planning pass. It was **not** re-run in this pass because the two WebSearch routes already produced a sufficient candidate set. Lower-noise follow-up if a future pass needs primary-source confirmation: `gh search repos pubmed mcp --limit 30` from an authenticated shell, or fetch each candidate's `README` / PyPI page directly rather than the GitHub search API.

### MCP server candidates

| Candidate | Search→PMID | Exact PMID fetch | Candidate vs fetched distinction | Constrainable to exactly 2 default tools | New runtime / package-manager cost | Deterministic offline tests | Out-of-scope tools exposed by default |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `aeghnnsw/pubmed-mcp` (Python, E-utilities) | Yes | Yes | No (no citeability concept) | No — also exposes download, summaries, batch ops | None beyond Python | Possible only if reworked | Full-content download, batch operations |
| `JackKuo666/PubMed-MCP-Server` (Python) | Yes | Yes (metadata by PMID) | No | No — bundles PDF download + deep paper analysis | None beyond Python | Possible only if reworked | PDF/full-text download, deep paper analysis |
| `cyanheads/pubmed-mcp-server` (TypeScript) | Yes | Yes | No (formats citations regardless of provenance) | No — broad tool set | Adds Node/Bun/TypeScript runtime | Provider seam unclear; tests are TS-side | Europe PMC, Unpaywall, MeSH, related-article, full text, citation formatting, hosted-server option |
| `genomoncology/biomcp` (Python, MIT) | Yes (`article_searcher`) | Partial (article getter) | No | No — 21 tools across trials, variants, articles | None beyond Python, but large surface | Not designed for offline determinism | Clinical trials, genomic variants (CIViC/ClinVar/COSMIC/dbSNP), full-text retrieval |
| `augmented-nature/pubmed-mcp-server` | Yes | Yes | No | No — analysis/citation-export oriented | Likely Node | Unknown | Citation export, analysis helpers |
| `wavelovey` PubMed Search MCP / `pubmed-search-mcp` (PyPI) | Yes | Partial | No | Closer (search-centric) but still not the 2-tool contract | None beyond Python | Unknown | Search-analysis helpers; no citeability gate |

### PubMed client-library candidates (for the native/wrap path)

| Library | Search→PMID | Exact PMID fetch | New runtime / dependency cost | Maintenance signal | Fit for a 2-tool Premura adapter |
| --- | --- | --- | --- | --- | --- |
| NCBI E-utilities over plain HTTP (ESearch / EFetch / ESummary) | Yes (ESearch returns UIDs) | Yes (EFetch/ESummary by PMID) | None — `httpx`/`urllib` + XML parse already viable | Stable, NCBI-maintained API | Best — exactly the two operations, nothing more |
| Biopython `Bio.Entrez` | Yes | Yes | Heavy — pulls the full Biopython bioinformatics suite for two calls | Actively maintained | Poor fit — large dependency for a narrow slice |
| `entrezpy` | Yes | Yes | New dependency, but stdlib-only and caches locally | Published library, low churn | Usable, but adds a dependency where raw E-utilities suffice |
| `metapub` | Yes | Yes (rich PubMed objects) | New dependency; abstracts MedGen/ClinVar/CrossRef too | Maintained | Broader than needed; pulls adjacent databases |
| `pymed` | Yes | Yes | Original archived 2020 | Archived; fork `pymed-paperscraper` maintained but bundles a scraping toolchain | Poor — dead upstream or over-scoped fork |
| `pubmed-api` / `pmidcite` | Yes | Partial | New dependency | Smaller utilities | No citeability model; no clear advantage over raw E-utilities |

**Rationale**: Every surveyed MCP server solves more than Premura's first slice and bundles out-of-scope tools (full text, deep analysis, Europe PMC, Unpaywall, MeSH, related-article, clinical trials, genomic variants). None models the candidate-vs-fetched citeability distinction that is the heart of Premura's contract. On the library side, raw NCBI E-utilities (ESearch + EFetch/ESummary) maps one-to-one onto the two operations Premura needs with no heavy new dependency, while every wrapper library either over-scopes (metapub, pymed-paperscraper, biomcp) or adds weight for no marginal benefit (Biopython, entrezpy).

## Decision 3: Citeability is a Premura concern, not a provider concern

**Decision**: The candidate-vs-fetched citation rule must be enforced by Premura's own adapter, regardless of provider, because no surveyed candidate enforces it.

**Rationale**: A broad third-party MCP surface makes it too easy for agents to cite search-only records, use full-text/deep-analysis tools, or blur literature context with local analysis. The two narrow guarantees Premura needs — search returns candidates (`candidate_only`), fetch-by-PMID returns citeable records (`citeable_fetched_record`) — are product invariants Premura must own at the MCP boundary.

## Decision 4: Baseline provider is NCBI E-utilities

**Decision**: The provider behind the adapter is NCBI E-utilities: ESearch for finding PMIDs, EFetch/ESummary for retrieving records by exact PMID.

**Rationale**: NCBI documentation defines ESearch for finding PMIDs and EFetch/ESummary for retrieving records. It supports the exact first slice: search returns UIDs, and fetch/summary returns metadata for exact IDs. This maps directly to Premura's candidate-vs-fetched citation rule, requires no heavy new dependency, and keeps the system local-first (no hosted third-party server).

**Alternatives considered**:
- Europe PMC or Unpaywall: useful later, but broader than PubMed grounding and not necessary for the first citation contract.
- Full-text retrieval: deferred because this mission focuses on citation grounding, not paper analysis.
- Third-party hosted MCP server: rejected for the default local-first path unless explicitly approved later.

## Decision 5: Testing posture

**Decision**: Tests must not depend on live PubMed availability. Use deterministic provider fixtures or mocked provider responses for ordinary tests, and keep any live/network check optional and explicitly marked if added.

**Rationale**: Premura's default test loop must stay fast and reproducible. PubMed failures, no-results, invalid PMID, partial metadata, and fetched-record success can all be tested through the provider seam without live network. A native E-utilities client behind a Premura interface gives a clean seam to inject fixtures; this is harder with a third-party MCP server whose tests live on its own side.

**Alternatives considered**:
- Live PubMed tests in the default suite: rejected because they add network flakiness and violate the local-first default.
- No integration-like tests: rejected because citation safety and MCP surface behavior are product-critical.

## Final Decision: minimal native build on NCBI E-utilities behind a Premura-owned adapter

**Decision** — **WP02 must build a minimal native PubMed provider on NCBI E-utilities, behind a Premura-owned adapter that exposes exactly two default MCP tools: `pubmed_search` (returns `candidate_only` records) and `pubmed_fetch` (returns `citeable_fetched_record` records).** This is the single path. WP02 does **not** adopt or wrap any third-party MCP server, and does **not** add a PubMed client library (Biopython, entrezpy, metapub, pymed) as a runtime dependency unless a later spec change justifies it. The native client calls ESearch and EFetch/ESummary directly over the project's existing HTTP/XML capability.

**Rationale**:
- **Citation safety.** The candidate-vs-fetched distinction is the product invariant. No surveyed candidate models it; a native adapter is the only way to guarantee `pubmed_search` results are never marked citeable and only `pubmed_fetch` results are.
- **Stage 3 boundary.** A Premura-owned adapter keeps PubMed network access confined to user-initiated Stage 3 MCP tooling. Adopting a third-party server (especially the TypeScript `cyanheads` or the 21-tool `biomcp`) would drag in a broad tool surface and a foreign runtime, making the Stage 3 boundary harder to audit and tempting scope creep into full text / Europe PMC / variants.
- **Smallest correct surface.** The needed search+fetch behavior is smaller than integrating any surveyed server. Raw E-utilities is two endpoints; every server and most libraries are strictly larger and bring out-of-scope tools by default.
- **Local-first, deterministic tests.** Native client + provider seam gives reproducible offline tests with fixtures, with no new runtime or package manager.

**Alternatives considered (and why each lost)**:
- **(a) Directly expose a third-party MCP surface** (`aeghnnsw`, `JackKuo666`, `cyanheads`, `biomcp`, `augmented-nature`, `wavelovey`): rejected. Every candidate is broader than two tools and ships out-of-scope tools (full text, deep analysis, Europe PMC, Unpaywall, MeSH, related-article, clinical trials, variants) on its default surface, and none enforces the candidate-vs-fetched citeability rule. Direct exposure would violate the bounded-default-surface goal and the citation contract; `cyanheads`/`biomcp` would also add a foreign runtime.
- **(b) Wrap a third-party MCP server or client library behind Premura's two tools**: rejected as unnecessary. Wrapping a server means running and trusting a broad foreign surface just to call two operations; wrapping a library (metapub/biopython/entrezpy/pymed) adds a dependency that either over-scopes or weighs more than the raw E-utilities calls it would make. Wrapping buys nothing over a native client for a two-endpoint slice.
- **(c) Native E-utilities build** (chosen): the minimal surface that satisfies the contract, owns citeability, stays inside the Stage 3 boundary, and tests deterministically.

If WP02 later finds the native E-utilities calls are materially more work than expected, the documented fallback is to wrap a single narrow library (entrezpy, stdlib-only) behind the *same* two-tool adapter — never to expose a third-party MCP surface and never to widen the default tool set.
