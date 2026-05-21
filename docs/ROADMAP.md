# premura — Roadmap

> Status: live reference. Intended sequencing of future work, not a contract.
>
> Companion to [SPEC.md](SPEC.md), [ARCHITECTURE_HISTORY.md](ARCHITECTURE_HISTORY.md), [USERJOURNEY.md](USERJOURNEY.md), [STATUS.md](STATUS.md), [STAGES.md](STAGES.md), [PROPOSAL_LABS.md](PROPOSAL_LABS.md).

Items below are sorted by reasonable build order, not priority. Anything in v1 scope (SPEC §2) that is still ⏳ in [STATUS.md](STATUS.md) is the prerequisite for the rest.

## Current operating policy

Drive upload remains **opt-in**, not automatic. For the current shipped behavior,
see [STATUS.md](STATUS.md) and [README.md](../README.md).

The user is actively writing more requirements; this section will grow.

## Near-term — close out v1 barebone

1. **Live encrypt round-trip**
   - `hpipe export --month 2026-05` against the real warehouse, `age -d` decrypt, byte-diff against source warehouse. Verify SPEC FR-6.
2. **Launchd installation on the host Mac**
   - `hpipe install-launchd` then `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.premura.monthly.plist` (label is operator-configurable).
   - Drive a `launchctl kickstart` test, confirm the macOS notification fires.
3. **Real SAA ingest on the next monthly cadence**
   - The synthetic-CSV unit tests pass, but the format is permissive enough that the first real export likely surfaces a parser quirk. Catch it on the first live run.
4. **Wiki hub page** in the operator's personal knowledge wiki per PLAN §"Wiki integration". (Separate repo, location operator-specific — needs cross-repo write authorization.)
5. **Optional password-manager CLI helper** — wrap the recipe in bootstrap.sh into a small `ops/bw_backup_key.sh` so users don't have to copy-paste. Skip until requested; the manual recipe is fine for now.

## Mid-term — analytical layer

5. **Read-only DuckDB views** for common slices: daily summary join, sleep+HRV daily, training load + readiness, weight + body composition over time.
   - Lives as `migrations/002_views.sql`; analysts open the warehouse read-only and `SELECT * FROM hp.v_daily_summary` instead of memorizing the long-format schema.
6. **HRV/respiration sample-level expansion** from Garmin (currently we only have daily aggregates from `healthStatusData`; the per-3-min or per-minute samples live in other files we haven't decoded yet — surface them via the "unhandled files" log already in the parser).
7. **Per-activity FIT-file decoding** (PLAN §"Out of scope (v1)" — explicitly deferred). Brings power, cadence, GPS, lap structure into `fact_interval`.
8. **Backfill historical Garmin dumps** — Garmin's 2-year health / 5-year activity horizon means each monthly dump still contains older rows. The `dedupe_key UNIQUE` + cross-source priority already make this safe to do today; just need a script that walks a `data/archive/garmin/*.zip` directory.

## New source class — clinical labs (blood / urine / stool)

See [PROPOSAL_LABS.md](PROPOSAL_LABS.md) for the full proposal. Summary:

- Adds a new source class — clinical lab PDFs — alongside the four wearable/app sources. Schema-free (existing long-format star already accepts it).
- Prior art: an operator-local standalone OCR repo has already extracted a real multi-year, multi-language lab-PDF corpus into structured rows. We adopt its **name-normalisation maps, date heuristics, and value-quirk handlers** verbatim, but **not** its extraction engine wholesale — we first spike **[docling](https://github.com/docling-project/docling)** as a local-only, table-aware alternative to the prior repo's Claude-vision pipeline (which sends PHI to the Anthropic API; in tension with VISION Pillar 6).
- Forces two real signal-processing rules: per-metric **`validity_window`** in `dim_metric` (lab values stale after weeks to months, not seconds), and per-metric **`missing_data_policy`** with lab markers defaulting to `none` (never impute across multi-month gaps). Both are general — once introduced for blood, they apply to all existing metrics.
- First derived signals: `derived:ldl_hdl_ratio`, `derived:ast_alt_ratio`, `derived:tg_hdl_ratio`.

Estimated effort: 4–5 days once a docling spike confirms extraction quality on a real lab-PDF corpus.

## Big idea — health-research MCP server

A single MCP server that exposes:

1. **Read-only DuckDB query** (parameterized + safe; no DDL).
2. **A curated set of deterministic stat tools** — Pearson/Spearman correlation, partial correlation, paired/unpaired t-test, Mann-Whitney, linear and mixed-effects regression, rolling-window means, change-point detection, lag-correlation. The LLM picks the test; the tool runs the computation; the answer comes back with effect size + CI + sample size so the LLM can't fudge magnitudes.
3. **PubMed search + fetch** (E-utilities is free, no key required for low volume) — keyword, MeSH, author. Returns abstract + DOI; never the full paper.
4. **PubMed → personal-data bridge** — a tool that turns a PubMed-cited finding into a parameterized query against the warehouse ("paper says deep-sleep% correlates with weekly HRV in 30-50yo males; check it in my data over 2024-2026").

### Does this exist already?

- **DuckDB-over-MCP**: yes. `motherduck/mcp-server-motherduck` is the closest match — it speaks DuckDB locally too, not just MotherDuck Cloud. Several community DuckDB MCP servers exist as well.
- **PubMed-over-MCP**: yes. `andybrandt/mcp-simple-pubmed` wraps NCBI Entrez.
- **The combination** (personal health DuckDB + stats tools + PubMed cross-reference, opinionated for a single user) — not that I'm aware of. The two halves are stitched-together free MCP servers; nobody seems to be building the **opinionated middle layer** that makes self-experimentation actually rigorous.

### My take

Worth building, with two caveats:

1. **Determinism via tools, not narration.** The LLM should call `correlate(metric_a="hrv_rmssd_overnight", metric_b="sleep_deep_pct", window_days=90)` and receive `{r=0.42, n=78, p=0.0001, ci=[0.21, 0.59]}`. Never let it report effect sizes from inside its own head. Code is the ground truth.
2. **PubMed retrieval is the easy part. Citing it accurately is the hard part.** The LLM will invent DOIs if you let it. Force every claim to round-trip through `pubmed_fetch(pmid=...)`; reject any cited finding the tool can't echo back.

### Concrete build order, if pursued

1. New module `src/premura/mcp_server.py` using the `mcp` Python SDK. Tools: `query_warehouse`, `list_metrics`, `metric_summary`.
2. Add `stats.py` with `correlate`, `paired_t_test`, `rolling_mean`, `change_point` — each returning a structured dict.
3. Add `pubmed.py` wrapper around Entrez (`esearch`, `efetch`); keep responses ≤25 hits.
4. Expose all of the above through the MCP server. Configure Claude Desktop to load it.
5. Add a "research notebook" mode: each Q&A round emits a markdown trace into `data/research/YYYY-MM-DD.md` with the tool calls + responses, so findings are reproducible.

This would turn the warehouse from a passive store into an **inferential** workbench — the original payoff of bypassing Health Connect.

## Smaller follow-ups

- **`hpipe inspect <file>`** subcommand that runs each parser's dispatcher in dry-run mode and prints the file→handler routing + any unhandled-filename log. Replaces the inline-Python exploration that built the v1 Garmin handler set.
- **`hpipe gc` extension** to also prune `data/raw/` (currently only `data/exports/`), with a `--dry-run` flag.
- **`hp.fact_interval.unit`** column added via `migrations/003_interval_unit.sql`. Backfill from `dim_metric.canonical_unit`. Drop the in-memory-only `unit` field on `Interval`.
- **Daily HC pickup** (PLAN §"Automation — optional second agent") — HC auto-exports daily to Drive; pull and ingest without the encrypt+upload tail.
- **Cross-source priority reconsidered**: currently `garmin_gdpr > health_connect > sleep_as_android > bmt`. The sleep_session join might be better served by `sleep_as_android > garmin_gdpr` for actigraphy fidelity. Empirical question — defer until we have two months of overlap.

## Anti-roadmap

These are not coming, by design (SPEC §2 "Out of scope" + PLAN §"Out of scope (explicit)"):

- Live-API scrapes (`python-garminconnect`, Google Fit REST, Apple HealthKit).
- HC re-injection.
- Mobile/Android app.
- Multi-user.
- Streaming / real-time ingestion.
- Apple Health (v1 operator is on Android; YAGNI).
- Web dashboard (the warehouse is the artifact; bring your own SQL).
