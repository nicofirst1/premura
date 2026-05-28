# premura — Roadmap

> Status: live reference. Intended sequencing of future work, not a contract.
>
> Companion to [DOCTRINE.md](DOCTRINE.md), [SPEC.md](SPEC.md), [../history/architecture/ARCHITECTURE_HISTORY.md](../history/architecture/ARCHITECTURE_HISTORY.md), [USERJOURNEY.md](USERJOURNEY.md), [STATUS.md](../operations/STATUS.md), [STAGES.md](../architecture/STAGES.md), [../history/research/PROPOSAL_LABS.md](../history/research/PROPOSAL_LABS.md), [../history/product/ROADMAP_BOOTSTRAP_PLAN.md](../history/product/ROADMAP_BOOTSTRAP_PLAN.md).
>
> For **phase-level planning**, see [FULL_APP_DEVELOPMENT_PLAN.md](FULL_APP_DEVELOPMENT_PLAN.md). For the historical record of how the first M1-M3 backlog was instantiated, see [../history/product/ROADMAP_BOOTSTRAP_PLAN.md](../history/product/ROADMAP_BOOTSTRAP_PLAN.md). This file is the short live pointer doc: what is next in broad terms, what is already settled, and which deeper doc to read.

Items below are sorted by reasonable build order, not priority. Anything in v1 scope (SPEC §2) that is still ⏳ in [STATUS.md](../operations/STATUS.md) is the prerequisite for the rest.

## Current operating policy

Drive upload remains **opt-in**, not automatic. For the current shipped behavior,
see [STATUS.md](../operations/STATUS.md) and [README.md](../../README.md).

The user is actively writing more requirements; this section will grow.

## Near-term residue

> Shipped items from this section have been pruned. Live encrypt round-trip and launchd installation both completed 2026-05-21 — see [STATUS.md](../operations/STATUS.md). What remains here is cleanup, not the main next product bet.

1. **Real SAA ingest on the next monthly cadence** (bootstrap task T2)
   - The synthetic-CSV unit tests pass, but the format is permissive enough that the first real export likely surfaces a parser quirk. Catch it on the first live run.
2. **Wiki hub page** in the operator's personal knowledge wiki (bootstrap task T3). Separate repo, location operator-specific — needs cross-repo write authorization.

## Next major phase — analytical depth

> This is the current main planning thread. The phase-level source of truth is [FULL_APP_DEVELOPMENT_PLAN.md](FULL_APP_DEVELOPMENT_PLAN.md) §"Phase 3: `v2.2 analytical depth`".

1. **Analytical foundation first.** Before adding a large tool surface, Premura needs a domain-aware input-resolution seam between Stage 2 and Stage 3 (now shipped), explicit honest-refusal behavior for declared-but-unresolved domains, and machine-readable confound warnings. The first cross-domain proof consumer (BMI) now uses this seam and refuses honestly when prerequisites are missing or stale, demonstrating the pattern future profile-aware answers will follow. Missingness and imputation reporting remain a Stage 2 *internal* concern (per-metric `missing_data_policy`, freshness windows), not the analytical foundation itself.
2. **Then the first deterministic tools.** The first tools should stay conservative and reproducible: `correlate`, `rolling_mean`, `change_point`, and only later broader significance-testing coverage. The goal is honest n-of-1 analysis, not statistical theater.
3. **Then literature grounding.** PubMed search/fetch and the literature-to-warehouse bridge belong after the deterministic tool layer exists, so citations attach to tool-grounded analysis rather than free-form narration.
4. **Then reproducible research traces.** Analytical sessions should leave behind a markdown trace of tool calls, outputs, and caveats.

Read the full phase doc for the rationale, risk retirement, and exit criteria:

- [FULL_APP_DEVELOPMENT_PLAN.md](FULL_APP_DEVELOPMENT_PLAN.md) §"Phase 3: `v2.2 analytical depth`"
- [STAGES.md](../architecture/STAGES.md) for the Stage 2 / Stage 3 boundary
- [`src/premura/engine/CONTRACT.md`](../../src/premura/engine/CONTRACT.md) for what Stage 2 may and may not claim

## Profile and intake — storage seam shipped, source adaptation and signals are the open work

> The semantic boundary is decided ([PROFILE_AND_INTAKE_CONTRACT.md](../architecture/PROFILE_AND_INTAKE_CONTRACT.md), design decision notes [0005](../adr/0005-profile-and-intake-contract.md) and [0006](../adr/0006-profile-intake-storage-and-capture.md)), and the storage seam is shipped. Future work here is implementation over that seam, not another modeling pass.

What this changes about the roadmap — future missions inherit the shipped seam instead of re-opening it:

- **The seam is stable and real in code.** A future signal must *declare* the profile/intake keys it depends on and read them from their domain tables, never fish a value out of `fact_measurement`, and never re-pick the storage shape.
- **Remaining follow-on work, in likely order:** (1) **parser/plugin source adaptation for nutrition/supplements** — teach a parser to turn a real meal-logging or supplement export into a normalized `IntakeBatch` that `persist_intake_batch` loads; this is the same federated-parser path the wearable sources use, *not* a built-in importer; (2) **concrete resolvers for the intake domains** that turn declarations against `nutrition_intake` and `supplement_intake` into resolved values once real rows exist (until then, declarations remain valid and resolve to an explicit `unsupported_domain` outcome); (3) **further profile-aware signals**, with age-adjusted interpretation as the next deferred candidate (`age` stays derived from `birth_date`, never stored). BMI is no longer on this list — it now ships as the first cross-domain Stage 2 proof consumer using the input-resolution seam. Capture of the bounded baseline allowlist (`birth_date`, `sex`, `standing_height_cm`) is already done, so no further "how does the human enter their profile" work is needed there.
- **Review gates should be machine-checkable, not tasteful.** In an agent-reviewed repo a boundary violation (a declared height written as an observation, a meal's energy merged with a wearable's total kcal) reads as a working change unless the rule is encoded. The contract's enumerated invariants and worked examples (the `profile_and_intake_*.yaml` files, exercised by the contract test harness) plus the now-structural one-home table separation are the gate each follow-on mission must pass.

These future signals stay **descriptive, non-diagnostic, and local-first** like the existing six (and like BMI): profile context is the operator's own account, age-adjusted reads will be interpretive aids over the user's own data, never population diagnosis, and nothing here sends data off the machine.

## Labs — shipped foundation, narrower follow-ons remain

> The first lab mission shipped. What remains here is narrower follow-on work, not the original lab-ingest foundation.

- Stage 3 lab exposure through the analytical surface
- extraction-quality validation tooling / UI
- any parser corrections surfaced by real operator use

See [FULL_APP_DEVELOPMENT_PLAN.md](FULL_APP_DEVELOPMENT_PLAN.md) §"Phase 2: `v2.1 labs`" for the shipped slice and [../history/research/PROPOSAL_LABS.md](../history/research/PROPOSAL_LABS.md) for the original design proposal.

## Historical note — the earlier MCP-server framing

> The older long-form MCP-server writeup is now superseded by the phase plan in [FULL_APP_DEVELOPMENT_PLAN.md](FULL_APP_DEVELOPMENT_PLAN.md), the shipped-state summary in [STATUS.md](../operations/STATUS.md), and the stage-boundary rules in [STAGES.md](../architecture/STAGES.md). Keep those three docs aligned rather than re-expanding the same argument here.

## Smaller follow-ups

> Also deferred from the first roadmap pass — see [../history/product/ROADMAP_BOOTSTRAP_PLAN.md](../history/product/ROADMAP_BOOTSTRAP_PLAN.md) §"Items I Would Not Pull Into The First Roadmap Pass." Per the partition rule, items here that introduce a new CLI verb or schema change (e.g. `hpipe inspect`, `fact_interval.unit`) will be reclassified as missions, not tasks, when they reach the active backlog.

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
