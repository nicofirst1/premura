# premura — Roadmap

> Status: live reference. Intended sequencing of future work, not a contract.
>
> Companion to [DOCTRINE.md](DOCTRINE.md), [SPEC.md](SPEC.md), [ARCHITECTURE_HISTORY.md](../architecture/ARCHITECTURE_HISTORY.md), [USERJOURNEY.md](USERJOURNEY.md), [STATUS.md](../operations/STATUS.md), [STAGES.md](../architecture/STAGES.md), [PROPOSAL_LABS.md](../research/PROPOSAL_LABS.md), [ROADMAP_BOOTSTRAP_PLAN.md](ROADMAP_BOOTSTRAP_PLAN.md).
>
> For the **current planning surface** — milestones, missions, tasks, and their sequencing — see [ROADMAP_BOOTSTRAP_PLAN.md](ROADMAP_BOOTSTRAP_PLAN.md). This doc retains the prose narrative and the deferred-items backlog; missions and tasks are tracked there (and, once created, in GitHub issues). All future roadmap work should be read through the product stance in [DOCTRINE.md](DOCTRINE.md): agent-primary execution, human-primary purpose.

Items below are sorted by reasonable build order, not priority. Anything in v1 scope (SPEC §2) that is still ⏳ in [STATUS.md](../operations/STATUS.md) is the prerequisite for the rest.

## Current operating policy

Drive upload remains **opt-in**, not automatic. For the current shipped behavior,
see [STATUS.md](../operations/STATUS.md) and [README.md](../../README.md).

The user is actively writing more requirements; this section will grow.

## Near-term — close out v1 barebone

> Shipped items from this section have been pruned. Live encrypt round-trip and launchd installation both completed 2026-05-21 — see [STATUS.md](../operations/STATUS.md). The remaining open residue is tracked as `v1.1 closeout` in [ROADMAP_BOOTSTRAP_PLAN.md](ROADMAP_BOOTSTRAP_PLAN.md).

1. **Real SAA ingest on the next monthly cadence** (bootstrap task T2)
   - The synthetic-CSV unit tests pass, but the format is permissive enough that the first real export likely surfaces a parser quirk. Catch it on the first live run.
2. **Wiki hub page** in the operator's personal knowledge wiki (bootstrap task T3). Separate repo, location operator-specific — needs cross-repo write authorization.

## Mid-term — analytical layer

> Deferred from the first roadmap pass — see [ROADMAP_BOOTSTRAP_PLAN.md](ROADMAP_BOOTSTRAP_PLAN.md) §"Items I Would Not Pull Into The First Roadmap Pass." These are real future work, not abandoned.

1. **Read-only DuckDB views** for common slices: daily summary join, sleep+HRV daily, training load + readiness, weight + body composition over time.
   - Lives as `migrations/002_views.sql`; analysts open the warehouse read-only and `SELECT * FROM hp.v_daily_summary` instead of memorizing the long-format schema.
2. **HRV/respiration sample-level expansion** from Garmin (currently we only have daily aggregates from `healthStatusData`; the per-3-min or per-minute samples live in other files we haven't decoded yet — surface them via the "unhandled files" log already in the parser).
3. **Per-activity FIT-file decoding** (PLAN §"Out of scope (v1)" — explicitly deferred). Brings power, cadence, GPS, lap structure into `fact_interval`.
4. **Backfill historical Garmin dumps** — Garmin's 2-year health / 5-year activity horizon means each monthly dump still contains older rows. The `dedupe_key UNIQUE` + cross-source priority already make this safe to do today; just need a script that walks a `data/archive/garmin/*.zip` directory.

## New source class — clinical labs (blood / urine / stool)

> Tracked as mission **M3** in [ROADMAP_BOOTSTRAP_PLAN.md](ROADMAP_BOOTSTRAP_PLAN.md). See [PROPOSAL_LABS.md](../research/PROPOSAL_LABS.md) for the full design proposal. Summary:

- Adds a new source class — clinical lab PDFs — alongside the four wearable/app sources. Schema-free (existing long-format star already accepts it).
- Prior art: an operator-local standalone OCR repo has already extracted a real multi-year, multi-language lab-PDF corpus into structured rows. We adopt its **name-normalisation maps, date heuristics, and value-quirk handlers** verbatim, but **not** its extraction engine wholesale — we first spike **[docling](https://github.com/docling-project/docling)** as a local-only, table-aware alternative to the prior repo's Claude-vision pipeline (which sends PHI to the Anthropic API; in tension with VISION Pillar 6).
- Forces two real signal-processing rules: per-metric **`validity_window`** in `dim_metric` (lab values stale after weeks to months, not seconds), and per-metric **`missing_data_policy`** with lab markers defaulting to `none` (never impute across multi-month gaps). Both are general — once introduced for blood, they apply to all existing metrics.
- First derived signals: `derived:ldl_hdl_ratio`, `derived:ast_alt_ratio`, `derived:tg_hdl_ratio`.

Estimated effort: 4–5 days once a docling spike confirms extraction quality on a real lab-PDF corpus.

## Big idea — health-research MCP server

> Tracked as missions **M1** (boundary spike) and **M2** (first analytical server, warehouse-query tools only — stats and PubMed deferred to follow-on missions) in [ROADMAP_BOOTSTRAP_PLAN.md](ROADMAP_BOOTSTRAP_PLAN.md). The full surface described below is the long-term shape, not the M2 scope.
>
> **Shipped since:** the first MCP query surface (`query_warehouse`, `list_metrics`, `metric_summary`) now exists, and a later mission added six grounded Stage 2 signals plus six signal-backed Stage 3 tools that route through them (current resting HR, resting-HR trend, steps trend, weight trend, deep-sleep vs own baseline, overnight-HRV change around a date — see [STATUS.md](../operations/STATUS.md) and [STAGES.md](../architecture/STAGES.md)). Those six question shapes are no longer hypothetical and no longer depend on raw-table reads. Everything else in this section — deterministic stats tools, PubMed, the literature↔warehouse bridge, the signal selector — remains future work. Profile-dependent answers (BMI, age-adjusted interpretation) stay deferred to issue `#6`.

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

### Concrete build order

1. ✅ **Done.** `src/premura/mcp/server.py` (+ `entrypoint.py`) using the `mcp` Python SDK. Raw tools `query_warehouse`, `list_metrics`, `metric_summary` shipped, then six signal-backed tools that delegate to the Stage 2 engine for the six approved question shapes.
2. **Next — `stats.py`** with `correlate`, `paired_t_test`, `rolling_mean`, `change_point` — each returning a structured dict. Not started; this is the statistics layer the current mission deliberately did **not** build.
3. Add `pubmed.py` wrapper around Entrez (`esearch`, `efetch`); keep responses ≤25 hits.
4. Expose all of the above through the MCP server. Configure Claude Desktop to load it.
5. Add a "research notebook" mode: each Q&A round emits a markdown trace into `data/research/YYYY-MM-DD.md` with the tool calls + responses, so findings are reproducible.

Default boundary assumption for the first pass: MCP opens the local warehouse in read-only mode, while `age` remains the protection for exported and uploaded artifacts rather than the live working DuckDB file.

This would turn the warehouse from a passive store into an **inferential** workbench — the original payoff of bypassing Health Connect.

## Smaller follow-ups

> Also deferred from the first roadmap pass — see [ROADMAP_BOOTSTRAP_PLAN.md](ROADMAP_BOOTSTRAP_PLAN.md) §"Items I Would Not Pull Into The First Roadmap Pass." Per the partition rule, items here that introduce a new CLI verb or schema change (e.g. `hpipe inspect`, `fact_interval.unit`) will be reclassified as missions, not tasks, when they reach the active backlog.

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
