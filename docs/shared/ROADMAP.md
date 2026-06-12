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

**The acceptance harness is frozen at current capability (2026-06-12).** It
runs end-to-end; further harness work must be paid for by findings about
Premura itself (the findings-per-effort rule), and overnight mission selection
must not default to harness work because it is safe. Decision note:
[`0012-acceptance-harness-freeze-findings-per-effort.md`](../building/adr/0012-acceptance-harness-freeze-findings-per-effort.md).

**Frontier-window operating mode (2026-06-12 → ~2026-06-22).** The maintainer
has Anthropic's most capable model (Fable 5) available for roughly ten days
and has decided that **spec-kitty is not used during this window**. Work runs
as directly-driven missions instead: each mission still gets a proper written
specification first (goal, functional requirements, acceptance criteria,
out-of-scope), the implementing session builds it, an **independent reviewer
context** checks it, and — per the consolidated-review-ceiling lesson in the
[2026-06-12 audit](../history/audits/2026-06-12-v040-first-full-stack-live-trial.md)
— every mission ends with **one real end-to-end exercise**, never review
alone. Spec-kitty resumes after the window for work that needs its lane
machinery.

## Near-term roadmap (the frontier window and after)

Sequenced by build order; the freeze and the two governing rules apply
throughout.

1. **#23 — supplement/medication recall ingest** — **shipped 2026-06-12**
   (CHANGELOG entry of that date): the AI-chat recall interchange contract
   (`premura.ai_chat_recall.v1`), reference paste-prompt, and the `aichat`
   intake parser.
2. **Condition-episode persistence** — **shipped 2026-06-12** (CHANGELOG
   entry of that date): operator-declared episodes persist in
   `hp.condition_episode` via agent-mediated capture
   (record/list/retract, supersede-with-history), and
   `condition_paired_t_test` consumes the stored declaration when
   `episodes` is omitted — off/on questions stop re-declaring episodes per
   request. The engine stayed stateless and unchanged.
3. **Stage 4 — operating-roles spec, then first slice** (the strategic
   thread; the only remaining stage gap). Promote
   [`operating-agent-roles.md`](../building/planning/operating-agent-roles.md)
   from DRAFT pre-spec to a real specification (a maintainer
   design-interview session, since decisions get locked there), then build
   the first slice: the runtime orchestrator skeleton and the **mandatory
   `answer_audit` gate** — the piece whose absence means nothing today
   structurally stops an unaudited health answer. Concept locked by decision
   note [0010](../building/adr/0010-runtime-orchestrator-and-operating-roles.md).
4. **Dogfooding as standing practice, not a queue item.** Real monthly
   ingest (the T2 residue above), real questions through the six tools.
   Per decision note 0012 this is the acceptance evaluation that costs
   nothing and yields the most.
5. **Outward readiness, parallel filler:** #15 (Apache-2.0 license,
   mechanical), #9 (RESULT_FAMILIES extension trigger, one contract
   paragraph), #22 (per-agent setup recipes), #14 (README rework —
   `ready-for-human`, the maintainer's).

**Parked, deliberately:** #24 and #27 (harness defects — frozen; fix only
when they block a run someone needs), #12 (adversarial narration eval — rig
work under the freeze), #10 (the acceptance-sandbox umbrella — standing
infrastructure, stays open by design), #4 (lab validator UI — a visual
layer, which is a deliberate later destination, not v1).

The user is actively writing more requirements; this section will grow.

## Near-term residue

> Shipped items from this section have been pruned. Live encrypt round-trip and launchd installation both completed 2026-05-21 — see [STATUS.md](STATUS.md). What remains here is cleanup, not the main next product bet.

1. **Real SAA ingest on the next monthly cadence** (bootstrap task T2)
   - The synthetic-CSV unit tests pass, but the format is permissive enough that the first real export likely surfaces a parser quirk. Catch it on the first live run.
2. **Wiki hub page** in the operator's personal knowledge wiki (bootstrap task T3). Separate repo, location operator-specific — needs cross-repo write authorization.

## Next major phase — analytical depth

> This is the current main planning thread. The phase-level source of truth is [FULL_APP_DEVELOPMENT_PLAN.md](../building/product/FULL_APP_DEVELOPMENT_PLAN.md) §"Phase 3: `v0.3 analytical depth`".

1. **Analytical foundation first — shipped.** Premura now has the domain-aware input-resolution seam between Stage 2 and Stage 3, explicit honest-refusal behavior for declared-but-unresolved domains, the deterministic evidence-admissibility policy layer (`evaluate_evidence` over a closed `QuestionType` vocabulary and per-family freshness/sufficiency rules), and a machine-readable closed confound vocabulary on the analytical result envelope. The first cross-domain proof consumer (BMI) uses the resolution seam; admissibility is decided before any tool computes. Missingness and imputation reporting remain a Stage 2 *internal* concern (per-metric `missing_data_policy`, freshness windows), not the analytical foundation itself.
2. **The bounded analytical tool set — complete, now six tools.** Six conservative, reproducible tools sit on the default MCP surface: `change_point` (level-shift detection), `smoothed_average` (trailing smoothed pattern), `correlate` (the n-of-1 workhorse — a pre-registered, caller-declared whole-day-lagged Spearman *association* with an autocorrelation-corrected `N_eff` band, no p-value and no "significant"), `rolling_mean` (a declared moving-window summary with visible coverage/imputation, distinct from `smoothed_average`), `paired_t_test` (a declared before/after anchor-date paired comparison reporting a paired difference and a descriptive uncertainty band — **not** a significance test, no p-value, names no cause), and now `condition_paired_t_test` (the reviewed **condition-label pairing** extension `paired_t_test` deferred: a declared off-vs-on paired difference over one operator-declared condition label and a set of non-overlapping declared episodes, one off/on pair per usable episode, with per-episode exclusion disclosures — same honesty boundary, the label only splits the windows and is never a cause). Each routes to its own first-class analytical `QuestionType` and returns the mandatory result envelope (estimate + validity metadata + confound checklist, including the `common_cause_plausible` key, or a first-class refusal); `engine.list_analytical_tools()` returns exactly these six. The locked architecture for the multi-input member is design decision note [0008](../building/adr/0008-correlate-pre-registered-lagged-association.md); the operative statistical rules live in [`src/premura/engine/CONTRACT.md`](../../src/premura/engine/CONTRACT.md), with the investigation's rationale recorded in the frozen research note [CORRELATE_METHODOLOGY_RESEARCH.md](../history/research/CORRELATE_METHODOLOGY_RESEARCH.md). **Since shipped (2026-06-12):** warehouse storage of condition periods — operator-declared episodes persist in `hp.condition_episode` via agent-mediated capture, and `condition_paired_t_test` consumes the stored declaration when `episodes` is omitted (see STATUS §"MCP surfaces"); the engine stayed stateless. **Still deferred (named so future work is not assumed shipped):** multi-label contrasts, episode auto-detection, and any scanning; and only later any broader significance-testing coverage. The goal stays honest n-of-1 analysis, not statistical theater.
3. **Reproducible research trace / multiplicity disclosure — shipped.** Analytical sessions now leave behind a **session research trace**: an explicit, append-only ledger of the analytical calls dispatched in a session, recorded at the MCP boundary (the pure `premura.trace` service over `trace.*` tables; the analytical engine stayed stateless). Three default-surface tools (`research_trace_open`, `research_trace_mark_surfaced`, `research_trace_disclosure`) expose it, and each analytical tool takes an optional `session_id` to record into it. The disclosure is **measured** from the recorded rows — "K user-facing findings among N unique hypotheses examined", with exact retries collapsing and refusals still counting toward N; when no results are marked, the surfaced count is reported **surfaced unavailable**, never guessed. It frames search effort, never "significant results," and computes no multiplicity-corrected statistic. The locked architecture is design decision note [0009](../building/adr/0009-session-research-trace-and-multiplicity-disclosure.md). On-demand JSON/Markdown exports are generated views, never the canonical record. **Now also shipped:** the follow-on **research trace audit skill** — a Premura-specific agent skill that reads the trace's audit-consumer contract (read-only) and judges one final answer for search-effort disclosure, hidden refusals or unavailable-surfaced marks, and overclaims. It ships at `src/premura/skills/research-trace-audit/` (a prose `SKILL.md` + a bounded `AUDIT_RUBRIC.md` of four closed criteria categories plus the rule for adding a criterion + five synthetic fixtures), installed via the existing `hpipe install-skills` to `.claude/skills/` — the same project skill home both Claude Code and OpenCode read, so a separate OpenCode-style installer target was evaluated and deliberately rejected (one home serves both clients). It changed no trace counts or schema, and it is not a generic answer-audit product — it applies only to an answer built from a Premura session research trace.
4. **Then literature grounding — first slice shipped.** With the bounded analytical tool set complete, the first PubMed grounding slice has now landed on the default MCP surface: two tools, `pubmed_search` (returns **candidates only** — never citeable) and `pubmed_fetch` (returns a **citeable** record for one exact PMID, with PubMed provenance). The live tool inventory and counts are in [STATUS.md](STATUS.md) §"Shipped surface". The candidate-vs-fetched citation rule is a Premura invariant owned by a Premura-owned adapter over NCBI E-utilities (no new HTTP dependency); see the [CHANGELOG.md](CHANGELOG.md) 2026-06-01 entry. This grounds citations in fetched records so they attach to tool-grounded analysis rather than free-form narration. **Still deferred (named so future work is not assumed shipped):** the **literature-to-warehouse bridge** and **concept-to-metric mapping** that would connect a fetched paper to the operator's own warehouse data; full-text retrieval, deep paper analysis, expansion to other sources (Europe PMC, Unpaywall), MeSH lookup, related-article discovery, and citation formatting. The shipped tools reach the literature only — they never diagnose, treat, name a cause, or compute over the user's health data. (Nutrition/supplement intake source adaptation has since shipped, including the first real vendor parser — MyFitnessPal, 2026-06-11 — see §"Profile and intake" below; the teaching UI remains deferred.)

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
   pinned by a test (see [CHANGELOG.md](CHANGELOG.md) 2026-06-02 entry).
   The **real cheap-model live trial has since shipped** (the
   `cheap-operator-live-trial-01KT6PSA` mission), and a follow-up
   (`live-trial-follow-up-hardening`, 2026-06-04) closed the seam's deferred
   real-model factories for real, added structured per-attempt telemetry,
   enforced the local-only model backend in code, and added an opt-in,
   synthetic-only retained-sandbox inspection mode. The [tool-using / multiturn
   operator tier](../building/planning/tool-loop-live-trial-tier.md) is **no
   longer parked**: its queue gate (intake source-adaptation) cleared
   2026-06-11, and the tier shipped as mission
   `tool-loop-live-trial-tier-01KTVG26` (merged to master 2026-06-11,
   `7d2c6a3` — what it adds is recorded in the [CHANGELOG.md](CHANGELOG.md)
   2026-06-11 entry). **Conversation-turn capture has since landed** (the
   `conversation-turn-capture` mission, merged in `v0.4.0`): the session
   log now persists the operator's actual chat history per run — a new additive
   `log_turn` table written through the same sole-writer harness, fed by a
   structural `transcript()` capability that both the tool-loop and one-shot
   tiers expose, so the judge AI has the turns to read (see the
   [CHANGELOG.md](CHANGELOG.md) 2026-06-11 entry). **The judge AI has since
   shipped** (the `judge-ai` mission, merged in `v0.4.0`): a harness-side
   evaluator now assembles a read-only **session dossier** (metadata, the
   grader's recomputed facts, per-attempt telemetry, and the transcript), asks a
   **local** model to assess the operator's *process* against a versioned,
   bounded **rubric** (four closed criterion categories plus the rule for adding
   a criterion), and persists a structured, descriptive judgment into a new
   additive `log_judgment` table through the same sole-writer surface. It is
   wired as an **opt-in, default-off** post-run step of the live trial; the judge
   evaluates the grader's facts but can never alter `contract_pass`, the
   scoreboard, or the trial verdict, and its failure never raises out of the
   harness (see the [CHANGELOG.md](CHANGELOG.md) 2026-06-11 entry). **The
   improvement hook has since shipped** (the `improvement-hook` mission, merged in
   `v0.4.0`): a deterministic, rule-based scan now *consumes* those judgments
   — it reads `log_judgment` rows (plus the rubric for criterion→category lookup),
   maps each weak band / failed judgment / off-rubric criterion to an improvement
   area via a versioned, bounded **playbook** (`IMPROVEMENT_PLAYBOOK.md`: one area
   per closed rubric category plus the two hook-owned areas `harness_reliability`
   and `rubric_drift`, plus the rule for adding an area), and persists durable,
   agent-readable **improvement proposals** into a new additive `log_improvement`
   table through the same sole-writer surface, read back through a strictly
   read-only surface. It **proposes; it never acts** — no prompt/harness/rubric/skill
   edit, and it never changes a run's verdict — and it is wired as an **opt-in,
   default-off** post-run step (`improve_run`, gated on `judge_run`) whose failure
   never raises out of the harness (see the [CHANGELOG.md](CHANGELOG.md)
   2026-06-12 entry). **The fixture auto-generator has since shipped** (the
   `fixture-auto-generator` mission, merged in `v0.4.0`): a deterministic,
   seeded, offline generator (`premura.harness.fixture_gen`) now fabricates fresh,
   never-seen **synthetic** vendor fixtures — a CSV plus its grader-only ground-truth
   manifest — on demand, so the acceptance harness is no longer limited to its two
   handwritten fixtures. Same seed → byte-identical pair; canonical metrics are drawn
   from the committed registry (never hardcoded); the observation challenge is fair
   by construction (seed-chosen timestamp encoding, distinct mapped metrics, a
   declared-gap decoy); drawer behaviour / naming weirdness / timestamp encodings are
   each a registry with a documented add rule; the harness's persistence gate
   (`is_synthetic_source`) recognizes a generated source as synthetic via an explicit
   writer-controlled marker — additive, without loosening the committed-source rule;
   and it is invocable as `python -m premura.harness.fixture_gen`.
   With it never invoked, every existing fixture and live-trial test is byte-for-byte
   unaffected (see the [CHANGELOG.md](CHANGELOG.md) 2026-06-12 entry). **The
   analyze-and-answer slice has since shipped** (the `analyze-and-answer` mission,
   merged in `v0.4.0`): the harness now grades a *second* task kind — given a
   deterministically seeded synthetic warehouse and a question, an operator must reach
   the data **only through the engine's analytical surfaces** and return an answer a
   deterministic grader verifies for **honesty** (no forbidden statistical claims —
   no "significant", no p-value, no cause, no population norm, per the engine
   contract), **grounding** (claimed structured estimates match the grader's own
   recomputation, which it computes itself and never trusts the operator's tool-call
   report for), and **refusal fidelity** (only a refusal that mirrors the engine's
   refusal passes; a refusal where the engine computed a result fails). It ships a
   question-kind registry with one worked kind (`level_shift` over `change_point`)
   and a documented add-a-kind rule, a forbidden-claims pattern registry with an
   add-a-pattern rule, a bounded engine-backed tool surface the operator drives
   (never a connection, path, or raw SQL), scripted honest/dishonest reference
   operators, full session-log capture of the exchange through the existing
   sole-writer surfaces (so `build_dossier` shows it) and a scoreboard line under the
   open tier axis (`analyze_answer`, synthetic), a judge-rubric + playbook extension
   made by their own add rules (no engine/judge/scan code edit), and a
   `python -m premura.harness.answer_task` offline runner (see the
   [CHANGELOG.md](CHANGELOG.md) 2026-06-12 entry). **Still
   deferred (named so future work is not assumed shipped):** acting on proposals
   (issue/PR creation, prompt editing, any self-modification), lifecycle tooling for
   the `dismissed`/`addressed` transitions, model-generated proposal prose,
   cross-session trend aggregation, and — for the analyze-and-answer slice
   specifically — the **real-model (Ollama) analyze operator** and its
   prompt/tool-loop work, **cross-session trend aggregation**, MCP exposure of the
   session log, multi-turn or multi-question sessions, natural-language question
   parsing, model-generated answer prose, and new analytical tools in the engine; and, for the fixture
   auto-generator specifically — the **`intake` drawer strategy** (the drawer-strategy
   seam ships; the second strategy is follow-on), **non-CSV fixture formats**
   (JSON/SQLite/zip exports), **auto-generated reference parsers**, and
   **difficulty-tier / curriculum policies**; and — out of the tier mission's scope by
   design — multi-model tournaments, tier auto-selection / capability-routing policies,
   and any frontier or cloud model requirement.

Read the full phase doc for the rationale, risk retirement, and exit criteria:

- [FULL_APP_DEVELOPMENT_PLAN.md](../building/product/FULL_APP_DEVELOPMENT_PLAN.md) §"Phase 3: `v0.3 analytical depth`"
- [STAGES.md](../building/architecture/STAGES.md) for the Stage 2 / Stage 3 boundary
- [`src/premura/engine/CONTRACT.md`](../../src/premura/engine/CONTRACT.md) for what Stage 2 may and may not claim

## Profile and intake — seam, resolvers, and first signals shipped; only a real-vendor parser + age-adjusted reads remain

> The semantic boundary is decided ([PROFILE_AND_INTAKE_CONTRACT.md](../building/architecture/PROFILE_AND_INTAKE_CONTRACT.md), design decision notes [0005](../building/adr/0005-profile-and-intake-contract.md) and [0006](../building/adr/0006-profile-intake-storage-and-capture.md)), and the storage seam is shipped. Future work here is implementation over that seam, not another modeling pass.

What this changes about the roadmap — future missions inherit the shipped seam instead of re-opening it:

- **The seam is stable and real in code.** A future signal must *declare* the profile/intake keys it depends on and read them from their domain tables, never fish a value out of `fact_measurement`, and never re-pick the storage shape.
- **Most of this follow-on work has now shipped** in the
  `usable-intake-dimensions-01KT950A` mission (mission #19, merged 2026-06-04 —
  see the [CHANGELOG.md](CHANGELOG.md) 2026-06-04 entry). Status of the original
  three items: (1) **parser/plugin source adaptation for nutrition/supplements** —
  ✅ shipped end-to-end: the intake parser contract, the `parser-generator`
  skill's intake path, a reference parser/fixture proving `parse → IntakeBatch →
  persist`, and now the first *real vendor* parser (**MyFitnessPal**, 2026-06-11
  — see the [CHANGELOG.md](CHANGELOG.md) entry); still **not** a built-in
  importer — further vendors remain parser/plugin work; (2) **concrete
  resolvers for the intake domains** — ✅ shipped; both `nutrition_intake` and
  `supplement_intake` resolve through the existing `@resolver` seam, and the
  `unsupported_domain` outcome is gone; (3) **further profile-aware signals** —
  ✅ the first two intake signals shipped (`supplement_intake_adherence`,
  `nutrition_intake_trend`); **age-adjusted interpretation remains the next
  deferred candidate** (`age` stays derived from `birth_date`, never stored). BMI
  was never on this list — it ships as the first cross-domain Stage 2 proof
  consumer using the input-resolution seam. Capture of the bounded baseline
  allowlist (`birth_date`, `sex`, `standing_height_cm`) is already done. The
  generalized "add an intake dimension" rule is written down in
  [INTAKE_DIMENSIONS.md](../building/architecture/INTAKE_DIMENSIONS.md); whether a
  dedicated intake-dimension contract is ever worth building is reasoned in
  [intake-dimension-contract-recommendation.md](../building/planning/intake-dimension-contract-recommendation.md).
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

- **`hpipe inspect <file>`** — shipped (mission `small-follow-ups`). A read-only routing-preview verb resolves the parser with the same discovery logic `ingest` uses, enumerates member names without ingesting, and prints file→handler routing + an unhandled summary, via a structural `preview_routing` capability any parser may expose. Garmin implements it tonight by delegating to its existing dispatcher; other parsers adopt the capability in their own follow-up. Replaces the inline-Python exploration that built the v1 Garmin handler set.
- **`hpipe gc` extension** — shipped (mission `small-follow-ups`). gc gained `--dry-run` (previews, removes nothing, both roots) and opt-in `--raw` pruning of `data/raw/` top-level entries older than the same `--keep` cutoff (one rule, two roots). `--raw` defaults OFF; defaulting it on inside the unattended `run_monthly` job is a deliberate human decision, deferred.
- **`hp.fact_interval.unit`** — shipped (mission `small-follow-ups`) via `migrations/006_interval_unit.sql` (003 was taken). The column is backfilled from `dim_metric.canonical_unit` and the load path populates new rows from the metric registry — the warehouse is the single source of unit truth, never a parser string. The in-memory-only `unit` field on `Interval` is dropped.
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
