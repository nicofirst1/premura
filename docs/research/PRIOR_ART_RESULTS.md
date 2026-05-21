# Prior-Art Research — Results
> Status: proposal/archive. Research output used for strategy, not a runtime contract.
>
> Research brief: [`PRIOR_ART_BRIEF.md`](PRIOR_ART_BRIEF.md)
>
> Generated: 2026-05-20
> Time budget used: ~45 minutes
> Phases completed: 1 / 2 / 3 / 4

---

## TL;DR

No existing open-source project satisfies all five adoption criteria simultaneously. The closest contenders — Gadgetbridge (device sync, AGPLv3, actively maintained) and Open Wearables (multi-vendor API, MIT, active as of May 2026) — each cover two or three pillars well but miss local encryption at rest and the AI-tutor teaching layer entirely. Build standalone, with deliberate borrowing from GarminDB (schema patterns), healthcare-mcp-public (PubMed tooling), and the DuckDB MCP servers (query layer).

---

## Section 1: Tier-A Competitive Matrix

| Candidate | Open / self-hostable | Locally encrypted | Vendor-agnostic schema | User-extensible | No telemetry / GDPR | Verdict |
|---|:---:|:---:|:---:|:---:|:---:|---|
| Open Humans | ⚠️ | ❌ | ⚠️ | ⚠️ | ❌ | Inform only |
| Open mHealth | ⚠️ | ❌ | ✅ | ⚠️ | ⚠️ | Inform only (dormant) |
| Gadgetbridge | ✅ | ❌ | ⚠️ | ⚠️ | ✅ | Inform / plugin candidate |

### Open Humans (A1)

**What it does:** Open Humans is a citizen-science platform where members connect data sources (Fitbit, Spotify, location) and share them with research projects. It is primarily a hosted SaaS service at openhumans.org.

**Criterion scores:**
1. **Open / self-hostable ⚠️** — The codebase is MIT-licensed on GitHub ([github.com/OpenHumans/open-humans](https://github.com/OpenHumans/open-humans), last updated Feb 21 2025) and includes local dev setup with PostgreSQL, but no documented production self-hosting path exists. The About page describes the site as "an open source project" without self-hosting instructions.
2. **Locally encrypted at rest ❌** — Data is stored on Open Humans' own US-based servers. No `age`/client-side encryption is mentioned anywhere in the codebase or documentation.
3. **Vendor-agnostic schema ⚠️** — Integrations exist for Fitbit, Withings, and GitHub ([oh-fitbit-integration](https://github.com/OpenHumans/oh-fitbit-integration), [oh-withings-integration](https://github.com/OpenHumans/oh-withings-integration)), but there is no unified, queryable warehouse schema. Each integration is a separate data-donation flow, not a normalized star schema.
4. **User-extensible ⚠️** — Third-party projects can be built as Open Humans "activities" (OAuth-style integrations), but this requires hosting your own web app and registering with the central platform. No offline/local plugin mechanism exists.
5. **No telemetry / GDPR ❌** — Open Humans is a data-sharing platform by design; members donate their data to research. This is antithetical to the local-first, no-upsell requirement.

**License:** MIT | **Last commit:** Feb 21, 2025 | **Verdict:** Dismiss for adoption; not architecturally compatible.

---

### Open mHealth (A2)

**What it does:** A nonprofit (2011) that published a JSON schema standard for personal health data and built Shimmer, a reference parser that converts third-party wearable APIs (Fitbit, Google Fit, iHealth, Withings, Runkeeper, Misfit) into Open mHealth compliant format.

**Criterion scores:**
1. **Open / self-hostable ⚠️** — Shimmer is Apache-2.0 ([github.com/openmhealth/shimmer](https://github.com/openmhealth/shimmer)); however, **Shimmer's last release was v0.6.0, October 2017**. The schemas repo ([github.com/openmhealth/schemas](https://github.com/openmhealth/schemas)) was updated Feb 25, 2026, but only to reference IEEE 1752.1. Most other repos (web-visualizations, OMH-on-FHIR) are dormant since 2018–2019; `pulse` is archived.
2. **Locally encrypted at rest ❌** — Shimmer is a REST proxy that authenticates against vendor OAuth APIs. No local-first storage or encryption layer exists.
3. **Vendor-agnostic schema ✅** — The Open mHealth schema is the strongest point: it defines typed, vendor-neutral JSON schemas for physical activity, sleep, heart rate, blood pressure, etc. ([openmhealth.org/features/integrations](https://www.openmhealth.org/features/integrations/)). The copyright notice still shows 2011–2019.
4. **User-extensible ⚠️** — Adding a new vendor requires writing a Shimmer shim, but the framework is effectively unmaintained since 2017.
5. **No telemetry / GDPR ⚠️** — Shimmer makes live OAuth calls to vendor APIs; it is not a GDPR-export-ingest tool. No telemetry policy documented.

**License:** Apache-2.0 (Shimmer) | **Last significant activity:** 2017 (Shimmer) / Feb 2026 (schema-only update) | **Verdict:** Inform only; schema concepts are worth borrowing, but the tooling is dead.

---

### Gadgetbridge (A3)

**What it does:** An Android app (AGPLv3) that pairs directly with 100+ wearable devices — including Garmin watches, Garmin HRM, Garmin GPS/bike computers, Amazfit, Xiaomi, Pebble, and many others — without requiring the vendor's proprietary app. It also integrates with Sleep as Android and Android Health Connect.

**Criterion scores:**
1. **Open / self-hostable ✅** — AGPLv3 licensed; fully self-contained Android app. Last commit: May 19, 2026 ([codeberg.org/Freeyourgadget/Gadgetbridge](https://codeberg.org/Freeyourgadget/Gadgetbridge)). Actively maintained.
2. **Locally encrypted at rest ❌** — Data is stored in a plain SQLite database on the Android device at local storage. No encryption layer (`age` or equivalent) is mentioned in documentation.
3. **Vendor-agnostic schema ⚠️** — The SQLite database uses **device-specific tables** (e.g., `MI_BAND_ACTIVITY_SAMPLE`, `PEBBLE_HEALTH_ACTIVITY_SAMPLE`, `GARMIN_*`), not a normalized vendor-agnostic star schema ([gadgetbridge.org/internals/development/data-management/](https://gadgetbridge.org/internals/development/data-management/)). A `BASE_ACTIVITY_SUMMARY` table exists but does not unify all metrics.
4. **User-extensible ⚠️** — New device support requires adding a device protocol implementation in Java/Kotlin and merging to the main repo. There is no documented plugin API for external contributors to add parsers without forking.
5. **No telemetry / GDPR ✅** — Explicitly privacy-focused; vendor app is never required; no network calls to third-party servers except Bluetooth to the device.

**License:** AGPLv3 | **Last commit:** May 19, 2026 | **Verdict:** Valuable as a **data collection source** (Gadgetbridge exports become an ingestion target for premura), not as a warehouse replacement. The device-specific SQLite schema is a plugin candidate, not a competitor.

---

## Section 2: GitHub Topic Crawl — Additional Candidates

| Candidate | Open? | Local-encrypted? | Vendor-agnostic? | User-extensible? | No-telemetry? | Verdict |
|---|:---:|:---:|:---:|:---:|:---:|---|
| GarminDB | ✅ | ❌ | ⚠️ | ❌ | ✅ | Inform / schema reference |
| Open Wearables | ✅ | ❌ | ✅ | ✅ | ✅ | Build alongside (API layer) |
| OpenHealth | ✅ | ⚠️ | ❌ | ❌ | ✅ | Inform only |
| Fasten | ✅ | ❌ | ❌ | ❌ | ✅ | Inform only (FHIR/EHR focus) |
| QS Ledger | ✅ | ❌ | ⚠️ | ⚠️ | ✅ | Inform only (notebooks only) |

### GarminDB

A Python tool (GPL-2.0, 3.1k stars, v3.8.0 released May 14, 2026) that downloads and parses Garmin Connect data and some Fitbit/MS Health CSVs into local SQLite databases, analyzable via Jupyter notebooks. The schema is **Garmin-centric** — tables like `monitoring_hr`, `sleep`, `activities` are built around Garmin's data model. Fitbit CSV import exists but is secondary. No encryption at rest, no plugin API, no AI layer. Source: [github.com/tcgoetz/GarminDB](https://github.com/tcgoetz/GarminDB). **Most relevant as a schema reference** for how to model Garmin GDPR exports into SQLite/DuckDB.

### Open Wearables

A self-hosted FastAPI + PostgreSQL + React platform (MIT, last release v0.5.2 May 20, 2026) that exposes a **unified API** for Garmin, Suunto, Polar, Apple HealthKit, Samsung Health, and Google Health Connect. Supports live-sync via OAuth and SDK (not GDPR-dump ingest). Architecture is vendor-agnostic by design; new adapters can be added. No `age`-encryption of the database — uses PostgreSQL with Redis. No AI analytical layer yet ("AI Health Assistant" is listed as "coming soon"). Source: [github.com/the-momentum/open-wearables](https://github.com/the-momentum/open-wearables). **Score: 3/5** — useful as an optional live-sync companion but does not replace the GDPR-dump ingest pipeline or the AI-tutor layer.

### OpenHealth

An AGPL-3.0 AI health assistant (275 commits, last release v0.2.0 Feb 21, 2025) that centralizes health data and provides LLM-powered chat. Supports Oura, Whoop, Garmin, Apple Health, Google Fit. Uses Prisma ORM and an `ENCRYPTION_KEY` env var suggesting some encryption at rest. However: it connects to **live vendor APIs only** (no GDPR-dump ingest), has no formal star schema for multi-vendor data, and the AI layer is a chat wrapper rather than deterministic statistical tools with citation round-trips. Source: [github.com/OpenHealthForAll/open-health](https://github.com/OpenHealthForAll/open-health). **Score: 2/5.**

### Fasten

An open-source, GPL-3.0 self-hosted personal EHR manager (Docker Compose, v1.1.3 Oct 2024) focused entirely on **FHIR medical records** from insurers and hospitals. Does not support wearable data (Garmin, Fitbit, Apple Health exports). Explicitly stated: "Fasten Onprem is not able to import data from healthcare providers directly." Source: [github.com/fastenhealth/fasten-onprem](https://github.com/fastenhealth/fasten-onprem). Informational; addresses a different problem (clinical records, not wearable fitness data).

### QS Ledger

An MIT-licensed Python/Jupyter Notebooks project (1.1k stars) that downloads data from 17+ services including Apple Health, Fitbit, Oura, and Strava. No persistent database, no encryption, no AI layer — outputs Pandas DataFrames for ad-hoc analysis. Source: [github.com/markwk/qs_ledger](https://github.com/markwk/qs_ledger). Last commit date unclear; appears dormant. **Plugin-ecosystem signal only.**

### Plugin-ecosystem signal

Numerous single-vendor Python parsers exist and are potential plugin candidates for premura v2:
- Apple Health XML: [alxdrcirilo/apple-health-parser](https://github.com/alxdrcirilo/apple-health-parser), [tdda/applehealthdata](https://github.com/tdda/applehealthdata)
- Fitbit Takeout: [kev-m/FitOut](https://github.com/kev-m/FitOut), [Z37K/fitbit-takeout-extractor](https://github.com/Z37K/fitbit-takeout-extractor)
- Garmin API: [arpanghosh8453/garmin-grafana](https://github.com/arpanghosh8453/garmin-grafana), [diegoscarabelli/garmin-health-data](https://github.com/diegoscarabelli/garmin-health-data)
- Withings: [oh-withings-integration](https://github.com/OpenHumans/oh-withings-integration)

None of these write to a shared vendor-agnostic warehouse.

---

## Section 3: Analytical Layer / MCP Scan

| Candidate | Open? | Deterministic stats? | PubMed citations? | Works with local DuckDB? | Verdict |
|---|:---:|:---:|:---:|:---:|---|
| apple-health-mcp-server | ✅ | ❌ (NL only) | ❌ | ✅ (DuckDB) | Fork candidate for query layer |
| healthcare-mcp-public | ✅ | ❌ | ✅ | ❌ | Adopt for PubMed tooling |
| mcp-server-duckdb | ✅ | ❌ | ❌ | ✅ | Adopt as query transport |
| garmin-connect-mcp | ✅ | ❌ | ❌ | ❌ | Plugin candidate (live API) |
| health_mcp (Marholoubek) | ✅ | ❌ | ❌ | ❌ | Plugin candidate (Whoop/Strava) |

### apple-health-mcp-server (the-momentum)

MIT-licensed MCP server that puts Apple Health XML data into a DuckDB database and answers natural language queries ([github.com/the-momentum/apple-health-mcp-server](https://github.com/the-momentum/apple-health-mcp-server), last release Oct 22, 2025). The same org maintains Open Wearables. This is a **natural language → SQL → DuckDB** pipeline, not a deterministic stats layer. No PubMed integration. Good proof-of-concept that the DuckDB + MCP pattern is validated.

### healthcare-mcp-public (Cicatriiz)

MIT-licensed Node.js MCP server exposing nine tools: FDA drug lookup, **PubMed search** (returns PMIDs + titles + abstracts + URLs), medRxiv search, clinical trials search, ICD-10, DICOM metadata, BMI calculator ([github.com/Cicatriiz/healthcare-mcp-public](https://github.com/Cicatriiz/healthcare-mcp-public)). Docker-deployable. The PubMed tool returns structured verifiable citations — no hallucinated DOIs. **This is directly reusable for Pillar 3's citation round-trip requirement.**

### mcp-server-duckdb (ktanaka101)

MIT-licensed MCP server implementation for local DuckDB ([github.com/ktanaka101/mcp-server-duckdb](https://github.com/ktanaka101/mcp-server-duckdb)). Provides SQL query tools over any DuckDB database. Can be adopted directly as the transport layer between Claude and premura's warehouse; no health-specific logic included.

### Vendor AI coaching products (closed)

- **WHOOP Coach** (powered by OpenAI/GPT-4): closed SaaS, subscription required, no self-hosting, data stays on WHOOP servers. Source: [whoop.com/thelocker/introducing-whoop-coach-powered-by-openai](https://www.whoop.com/us/en/thelocker/introducing-whoop-coach-powered-by-openai/).
- **Oura Advisor**: closed, runs on Oura's proprietary foundation model hosted on Oura servers, not available for self-hosting. Source: [trendingtopics.eu/oura-launches-first-proprietary-ai-model](https://www.trendingtopics.eu/oura-launches-first-proprietary-ai-model-for-womens-health-insights/). An unofficial [Oura MCP Server](https://skywork.ai/skypage/en/oura-mcp-server-ai-engineer/1981578321872392192) (MIT, 32 stars) exists but is a live-API wrapper, not a local warehouse tool.

**Gap confirmed:** No open MCP server combines deterministic statistical tests (correlation, t-test, change-point detection) + PubMed citation round-trip + local DuckDB on a vendor-agnostic health warehouse. This is the unsolved Pillar 3.

---

## Section 4: Per-Pillar Coverage

| Pillar | Best existing candidate | Score (1–5) | Gap if we build it ourselves |
|---|---|:---:|---|
| 1 — Plugin parsers | GarminDB + single-vendor parsers (apple-health-parser, FitOut, etc.) | 2 | No unified plugin discovery mechanism (Claude Code skill format). Each parser is standalone with its own output format. |
| 2 — One DB, many sources | Open mHealth schema (concept) / Open Wearables (live API) | 2 | No GDPR-dump ingest into a local vendor-agnostic DuckDB star schema exists anywhere. |
| 3 — AI tools that don't lie | healthcare-mcp-public (PubMed) + mcp-server-duckdb (query) | 2 | Deterministic stat tools (t-test, change-point) layered over health warehouse don't exist as open MCP tools. |
| 4 — Interview-driven onboarding | None found | 1 | Completely absent from all surveyed projects. |
| 5 — Teaching layer (Nielsen/CLT/Victor) | None found | 1 | No project applies pedagogical UX principles to health data explanation. |
| 6 — Privacy (local-first, age-encrypted) | Gadgetbridge (local, no encryption) | 2 | `age`-encrypted DuckDB with user-held key is not implemented anywhere surveyed. |

---

## Section 5: Recommendation

**Choice: Build standalone**, learning from GarminDB, Open Wearables, and healthcare-mcp-public.

No surveyed project satisfies three or more of the five adoption criteria simultaneously when evaluated against the full v2 specification. The nearest miss is **Open Wearables** (3/5: open, vendor-agnostic, extensible), which is worth watching as a live-sync companion for users who want real-time data alongside periodic GDPR dumps; however, it uses live OAuth APIs rather than GDPR-export ingest, uses PostgreSQL without `age` encryption, and has no analytical or teaching layer.

**Adopt these components directly:**
- `healthcare-mcp-public` PubMed tools (MIT) — wire into Pillar 3's citation round-trip as-is or as a reference implementation.
- `mcp-server-duckdb` (MIT) — use as the SQL query transport between Claude and the warehouse for Pillar 3.
- Single-vendor parsers (apple-health-parser, FitOut, garmin-health-data) — ingest as community plugin candidates for Pillar 1; they need a thin adapter to write into the `fact_measurement` / `dim_metric` schema.

**Learn schema patterns from:**
- GarminDB (how Garmin GDPR zip fields map to typed SQLite columns).
- Open mHealth schemas (vendor-neutral metric names and units for physical activity, sleep, heart rate, blood pressure).

**Build fresh:**
- The `age`-encrypted DuckDB layer (Pillar 6) — no precedent found.
- The vendor-agnostic star schema with GDPR-dump ingest (Pillar 2) — only live-API alternatives exist.
- Deterministic stat MCP tools: correlation, t-test, change-point (Pillar 3) — gap confirmed.
- Interview-driven onboarding and teaching layer (Pillars 4 & 5) — entirely absent in all surveyed projects.

---

## Section 6: Open Questions

- **Open Wearables live-sync + premura GDPR-dump**: could these be complementary ingestion paths into the same DuckDB? Worth a spike to test if Open Wearables' PostgreSQL schema is close enough to the v1 star schema to justify a bridge.
- **Gadgetbridge as a data source**: Gadgetbridge already syncs many Garmin devices locally and can export an SQLite ZIP. A premura Gadgetbridge parser plugin would let users avoid Garmin Connect entirely — verify whether the Gadgetbridge SQLite schema is stable enough to parse reliably.
- **FHIR scope**: Fasten, Mere Medical, and the HL7 community occupy the clinical-records space. premura explicitly excludes this, but if users ask for lab results or doctor visit notes, Fasten's FHIR import could be a complement rather than a competitor.
- **Open mHealth IEEE 1752.1 migration**: the schema repo was updated in Feb 2026 to reference IEEE 1752.1. Worth checking whether IEEE 1752.1 is freely available and whether its metric definitions should inform the `dim_metric` vocabulary in the premura star schema.
- **GarminDB v3.8.0 schema stability**: the May 2026 release suggests active maintenance. Confirm whether the Garmin GDPR zip format (used by premura v1) maps cleanly to GarminDB's table columns, which would allow borrowing column definitions rather than rediscovering them.
- **mcp-server-duckdb encryption support**: confirm whether `mcp-server-duckdb` can open an `age`-encrypted DuckDB file (via HTTPFS or a pre-decrypted in-memory mount) without exposing the plaintext to disk.
