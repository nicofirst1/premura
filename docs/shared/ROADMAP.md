# premura — Roadmap

> Status: live reference. Intended sequencing of future work, not a contract.
>
> Companion to [DOCTRINE.md](DOCTRINE.md), [SPEC.md](SPEC.md), [../history/architecture/ARCHITECTURE_HISTORY.md](../history/architecture/ARCHITECTURE_HISTORY.md), [USERJOURNEY.md](../using/USERJOURNEY.md), [STATUS.md](STATUS.md), [STAGES.md](../building/architecture/STAGES.md), [../history/research/PROPOSAL_LABS.md](../history/research/PROPOSAL_LABS.md), [../history/product/ROADMAP_BOOTSTRAP_PLAN.md](../history/product/ROADMAP_BOOTSTRAP_PLAN.md).
>
> For **phase-level planning**, see [FULL_APP_DEVELOPMENT_PLAN.md](../building/product/FULL_APP_DEVELOPMENT_PLAN.md). For the historical record of how the first M1-M3 backlog was instantiated, see [../history/product/ROADMAP_BOOTSTRAP_PLAN.md](../history/product/ROADMAP_BOOTSTRAP_PLAN.md). This file is the short live pointer doc: what is next in broad terms, what is already settled, and which deeper doc to read.

Items below are sorted by reasonable build order, not priority. Anything in the original SPEC scope (§2) that is still ⏳ in [STATUS.md](STATUS.md) is the prerequisite for the rest.

## Current operating policy

Drive upload remains **opt-in**, not automatic. For the current shipped behavior,
see [STATUS.md](STATUS.md) and [README.md](../../README.md).

The user is actively writing more requirements; this section will grow.

## Near-term residue

> Shipped items from this section have been pruned. Live encrypt round-trip and launchd installation both completed 2026-05-21 — see [STATUS.md](STATUS.md). What remains here is cleanup, not the main next product bet.

1. **Real SAA ingest on the next monthly cadence** (bootstrap task T2)
   - The synthetic-CSV unit tests pass, but the format is permissive enough that the first real export likely surfaces a parser quirk. Catch it on the first live run.
2. **Wiki hub page** in the operator's personal knowledge wiki (bootstrap task T3). Separate repo, location operator-specific — needs cross-repo write authorization.

## Next major phase — analytical depth

> This is the current main planning thread. The phase-level source of truth is [FULL_APP_DEVELOPMENT_PLAN.md](../building/product/FULL_APP_DEVELOPMENT_PLAN.md) §"Phase 3: `v0.3 analytical depth`".

1. **Analytical foundation first — shipped.** Premura now has the domain-aware input-resolution seam between Stage 2 and Stage 3, explicit honest-refusal behavior for declared-but-unresolved domains, the deterministic evidence-admissibility policy layer (`evaluate_evidence` over a closed `QuestionType` vocabulary and per-family freshness/sufficiency rules), and a machine-readable closed confound vocabulary on the analytical result envelope. The first cross-domain proof consumer (BMI) uses the resolution seam; admissibility is decided before any tool computes. Missingness and imputation reporting remain a Stage 2 *internal* concern (per-metric `missing_data_policy`, freshness windows), not the analytical foundation itself.
2. **The first bounded analytical tool set — complete.** Five conservative, reproducible tools now sit on the default MCP surface: `change_point` (level-shift detection), `smoothed_average` (trailing smoothed pattern), `correlate` (the n-of-1 workhorse — a pre-registered, caller-declared whole-day-lagged Spearman *association* with an autocorrelation-corrected `N_eff` band, no p-value and no "significant"), `rolling_mean` (a declared moving-window summary with visible coverage/imputation, distinct from `smoothed_average`), and `paired_t_test` (a declared before/after anchor-date paired comparison reporting a paired difference and a descriptive uncertainty band — **not** a significance test, no p-value, names no cause). Each routes to its own first-class analytical `QuestionType` and returns the mandatory result envelope (estimate + validity metadata + confound checklist, including the `common_cause_plausible` key, or a first-class refusal); `engine.list_analytical_tools()` returns exactly these five. The locked architecture for the multi-input member is design decision note [0008](../building/adr/0008-correlate-pre-registered-lagged-association.md); the statistical choices are settled in [CORRELATE_METHODOLOGY_RESEARCH.md](../history/research/CORRELATE_METHODOLOGY_RESEARCH.md). **Still deferred:** `paired_t_test`'s broader **condition-label pairing** (anchor-date pairing only ships now), and only later any broader significance-testing coverage. The goal stays honest n-of-1 analysis, not statistical theater.
3. **Reproducible research trace / multiplicity disclosure — shipped.** Analytical sessions now leave behind a **session research trace**: an explicit, append-only ledger of the analytical calls dispatched in a session, recorded at the MCP boundary (the pure `premura.trace` service over `trace.*` tables; the analytical engine stayed stateless). Three default-surface tools (`research_trace_open`, `research_trace_mark_surfaced`, `research_trace_disclosure`) expose it, and each analytical tool takes an optional `session_id` to record into it. The disclosure is **measured** from the recorded rows — "K user-facing findings among N unique hypotheses examined", with exact retries collapsing and refusals still counting toward N; when no results are marked, the surfaced count is reported **surfaced unavailable**, never guessed. It frames search effort, never "significant results," and computes no multiplicity-corrected statistic. The locked architecture is design decision note [0009](../building/adr/0009-session-research-trace-and-multiplicity-disclosure.md). On-demand JSON/Markdown exports are generated views, never the canonical record. **Now also shipped:** the follow-on **research trace audit skill** — a Premura-specific agent skill that reads the trace's audit-consumer contract (read-only) and judges one final answer for search-effort disclosure, hidden refusals or unavailable-surfaced marks, and overclaims. It ships at `src/premura/skills/research-trace-audit/` (a prose `SKILL.md` + a bounded `AUDIT_RUBRIC.md` of four closed criteria categories plus the rule for adding a criterion + five synthetic fixtures), installed via the existing `hpipe install-skills` to `.claude/skills/` — the same project skill home both Claude Code and OpenCode read, so a separate OpenCode-style installer target was evaluated and deliberately rejected (one home serves both clients). It changed no trace counts or schema, and it is not a generic answer-audit product — it applies only to an answer built from a Premura session research trace.
4. **Then literature grounding — first slice shipped.** With the bounded analytical tool set complete, the first PubMed grounding slice has now landed on the default MCP surface: two tools, `pubmed_search` (returns **candidates only** — never citeable) and `pubmed_fetch` (returns a **citeable** record for one exact PMID, with PubMed provenance). They take the default surface to twenty tools. The candidate-vs-fetched citation rule is a Premura invariant owned by a Premura-owned adapter over NCBI E-utilities (no new HTTP dependency); see [STATUS.md](STATUS.md) §"PubMed literature grounding". This grounds citations in fetched records so they attach to tool-grounded analysis rather than free-form narration. **Still deferred (named so future work is not assumed shipped):** the **literature-to-warehouse bridge** and **concept-to-metric mapping** that would connect a fetched paper to the operator's own warehouse data; full-text retrieval, deep paper analysis, expansion to other sources (Europe PMC, Unpaywall), MeSH lookup, related-article discovery, and citation formatting. The shipped tools reach the literature only — they never diagnose, treat, name a cause, or compute over the user's health data. (Nutrition/supplement source adaptation and the teaching UI also remain deferred.)

5. **Loggable session substrate — slice one shipped.** The
   `session-log-substrate-01KT45S1` mission (slice one) merged to master on
   2026-06-02 (commit `798493b`), landing the per-run **session log** (a local,
   PHI-bearing DuckDB store recording sessions, steps, and ingest provenance) plus
   the runtime-contract checker, sandbox/ingest runner, reference parsers +
   fixtures, deterministic grader, an offline repeatable check, and a live-trial
   seam (real-model wiring is a named follow-up) — the substrate a future
   end-to-end agent-acceptance harness reads. The grader recomputes every rule from
   ground truth and never trusts a parser's self-report, so a silently-dropped
   field is caught by reconciliation. It also carried a **doctrine clarification**
   (FR-130): the settled runtime build-and-use parser rule — an agent may build a
   parser and use it immediately for the operator's own data with no reviewer; only
   contributing it back as a public PR is reviewed — is now stated consistently
   across `operating-agent-roles.md`, ADR 0010, and [DOCTRINE.md](DOCTRINE.md), and
   pinned by a test (see [STATUS.md](STATUS.md) §"Runtime build-and-use parser boundary").
   The **real cheap-model live trial has since shipped** (the
   `cheap-operator-live-trial-01KT6PSA` mission), and a follow-up
   (`live-trial-follow-up-hardening`, 2026-06-04) closed the seam's deferred
   real-model factories for real, added structured per-attempt telemetry,
   enforced the local-only model backend in code, and added an opt-in,
   synthetic-only retained-sandbox inspection mode. **Still deferred (named so
   future work is not assumed shipped):** a tool-using / multiturn operator tier,
   conversation-turn capture, the judge AI, the improvement hook, the fixture
   auto-generator, and the analyze-and-answer slice.

Read the full phase doc for the rationale, risk retirement, and exit criteria:

- [FULL_APP_DEVELOPMENT_PLAN.md](../building/product/FULL_APP_DEVELOPMENT_PLAN.md) §"Phase 3: `v0.3 analytical depth`"
- [STAGES.md](../building/architecture/STAGES.md) for the Stage 2 / Stage 3 boundary
- [`src/premura/engine/CONTRACT.md`](../../src/premura/engine/CONTRACT.md) for what Stage 2 may and may not claim

## Profile and intake — storage seam shipped, source adaptation and signals are the open work

> The semantic boundary is decided ([PROFILE_AND_INTAKE_CONTRACT.md](../building/architecture/PROFILE_AND_INTAKE_CONTRACT.md), design decision notes [0005](../building/adr/0005-profile-and-intake-contract.md) and [0006](../building/adr/0006-profile-intake-storage-and-capture.md)), and the storage seam is shipped. Future work here is implementation over that seam, not another modeling pass.

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

See [FULL_APP_DEVELOPMENT_PLAN.md](../building/product/FULL_APP_DEVELOPMENT_PLAN.md) §"Phase 2: `v0.2 labs`" for the shipped slice and [../history/research/PROPOSAL_LABS.md](../history/research/PROPOSAL_LABS.md) for the original design proposal.

## Historical note — the earlier MCP-server framing

> The older long-form MCP-server writeup is now superseded by the phase plan in [FULL_APP_DEVELOPMENT_PLAN.md](../building/product/FULL_APP_DEVELOPMENT_PLAN.md), the shipped-state summary in [STATUS.md](STATUS.md), and the stage-boundary rules in [STAGES.md](../building/architecture/STAGES.md). Keep those three docs aligned rather than re-expanding the same argument here.

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
