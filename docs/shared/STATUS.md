# premura — Current Status

> Status: live reference. Snapshot of what is true and shipped today.
>
> Companion to [SPEC.md](SPEC.md), [../history/architecture/ARCHITECTURE_HISTORY.md](../history/architecture/ARCHITECTURE_HISTORY.md), [USERJOURNEY.md](../using/USERJOURNEY.md), [ROADMAP.md](ROADMAP.md).
> Snapshot date: **2026-06-05**.

## TL;DR

**Pre-`v1` foundation — historical tag `v1.0.0` exists, but the product line is now treated as `v0.x`.** The four-source ingest pipeline is **operational**. The DuckDB warehouse contains ~3.5 years of HC data plus the full set of Garmin-only metrics that [../history/architecture/ARCHITECTURE_HISTORY.md](../history/architecture/ARCHITECTURE_HISTORY.md) flagged as the original motivation: **HRV rMSSD overnight, stress, training load, training readiness, VO₂ max, skin temperature, hydration, sleep score, respiration**. Re-ingest of any source is idempotent. Going forward, `v1.0.0` is reserved for a coherent user-facing product across all four stages; internal milestones should tag as `v0.1.0`, `v0.2.0`, and so on.

**Policy change (2026-05-20)**: as the project starts looking like a real application for others, Drive upload is now **opt-in**, not part of the automated monthly run. `hpipe run-monthly` ends with the encrypted `.age` artifact sitting in `data/exports/YYYY-MM/`; the user decides whether to `hpipe upload` (or hand the file off to another sync mechanism). The `age` private key is stored locally by default, with a password-manager recipe (Bitwarden as a reference) in [`ops/bootstrap.sh`](../../ops/bootstrap.sh).

## Stage 2 / Stage 3 baseline (shipped after v1)

The first grounded analytical behavior now exists on top of the v1 ingest pipeline.

**Stage 2 — eight grounded signals.** `src/premura/engine/` ships eight freshness-aware answers over the user's own warehouse data (`descriptive_signals.py`, `comparative_signals.py`), registered through the static built-in module list and documented by `src/premura/engine/CONTRACT.md`:

| Signal | Family | Answers |
|---|---|---|
| `resting_hr_status` | status | "What is my resting HR right now, and can I trust it?" |
| `resting_hr_trend` | trend | "Is my resting HR going up / down / flat recently?" |
| `steps_trend` | trend | "Are my daily steps trending?" (never imputes missing days) |
| `weight_trend` | trend | "Is my weight rising / falling / flat?" (carry-forward flagged) |
| `sleep_deep_pct_baseline` | baseline | "Is my latest deep-sleep % below my **own** recent normal?" |
| `hrv_change_around_date` | change | "Did my overnight HRV shift after a date I name?" |
| `supplement_intake_adherence` | status | "How consistently have I logged a supplement I name, recently?" (coverage "logged on K of the last N days") |
| `nutrition_intake_trend` | trend | "Is my logged nutrient/energy field trending up / down / flat?" (never imputes missing days) |

The last two are the **usable-intake-dimensions** signals — see "Usable intake dimensions" below. These are descriptive/comparative only — no reference ranges, no diagnosis, no statistical significance, no causation. They return explicit stale / unavailable / insufficient-data states instead of presenting a misleading answer.

**BMI cross-domain proof consumer (shipped).** Stage 2 now hosts the first cross-domain signal: `bmi` (family `status`). It resolves a declared standing height from profile context plus a usable body-weight observation from observation history through the new input-resolution seam, computes `BMI = weight_kg / height_m**2`, and refuses honestly (`missing_input` / `stale_input` / `insufficient_data`) when either prerequisite is missing or stale. BMI is a **structural proof consumer**, not a clinical or diagnostic interpretation.

**Input-resolution seam (shipped).** `premura.engine.resolve_dependency`, `RESOLVERS`, and the `@resolver(domain=...)` decorator (re-exported from `premura.engine`) wire declared dependencies to domain-aware resolvers. All four `SEMANTIC_DOMAINS` now have concrete resolvers: `observation_history` (`premura/engine/views/observation.py`), `profile_context` (`premura/engine/views/profile.py`), and — added by the usable-intake-dimensions mission (see below) — `nutrition_intake` (`premura/engine/views/nutrition_intake.py`) and `supplement_intake` (`premura/engine/views/supplement_intake.py`). The old `unsupported_domain` outcome for the two intake domains is gone; a declared intake dependency with no matching, fresh row now resolves to an explicit missing / stale non-usable outcome and never substitutes a value from another domain.

**Stage 3 — two entrypoints, clean boundary.** `src/premura/mcp/` ships two entrypoints:

- **Default agent surface (`premura-mcp`)** — twenty-two tools: two validity-gated catalog/summary helpers (`list_metrics`, `metric_summary`) that delegate entirely to the Stage 2 engine, the eight signal-backed tools listed above (the six originals plus `supplement_intake_adherence` and `nutrition_intake_trend`), two agent-mediated profile-capture tools (`profile_context_supported_fields`, `profile_context_record`), the five Stage 3 analytical tools (`change_point`, `smoothed_average`, `correlate`, `rolling_mean`, `paired_t_test` — see "Stage 3 analytical tools" below), the three session research trace tools (`research_trace_open`, `research_trace_mark_surfaced`, `research_trace_disclosure` — see "Session research trace" below), and the two PubMed grounding tools (`pubmed_search`, `pubmed_fetch` — see "PubMed literature grounding" below). No tool on this surface reads `hp.*` directly; catalog/signal access goes through the engine, profile capture goes through the bounded `record_profile_context` store boundary, the trace tools read only derived `trace.*` rows, and the PubMed tools reach only the external literature (never `hp.*` health rows). This is the fully validity-gated / bounded default path.
- **Operator surface (`premura-mcp-operator`)** — all twenty-two default tools plus `query_warehouse` (raw SQL escape hatch), for twenty-three total. Lower-guarantee: `query_warehouse` returns raw rows without Stage 2 validity, freshness, or imputation guarantees. Agent use requires explicit user approval, enforced by surface separation plus an explicit launch acknowledgment (`--ack` / `PREMURA_OPERATOR_ACK`) the operator entrypoint demands before exposing the raw-SQL tool.

The signal-backed tools return a structured payload whose `status` is `available` / `missing_input` / `stale_input` / `insufficient_data`. When an answer is unavailable the payload's `message` carries the signal's authored missing-input guidance, and `missing_input` / `stale_input` responses attach a structured `missing_input` report (`required_inputs` / `missing_inputs` / `stale_inputs`) a caller can branch on.

## Profile and intake storage + agent-mediated capture (shipped 2026-05-27)

The `implement-profile-and-intake-storage-01KSMWV1` mission gave the profile/intake **meaning contract** ([PROFILE_AND_INTAKE_CONTRACT.md](../building/architecture/PROFILE_AND_INTAKE_CONTRACT.md)) a concrete storage adapter and the first write path. What now works end-to-end:

- **Concrete domain tables.** Migration `src/premura/store/migrations/004_profile_intake.sql` adds dedicated `hp.*` homes: `hp.profile_capture_session` + `hp.profile_context_assertion` (profile); `hp.nutrition_intake_event` → `hp.nutrition_intake_item` → `hp.nutrition_quantity` (nutrition); `hp.supplement_intake_event` → `hp.supplement_item` → `hp.supplement_dose` (supplements). One-home separation is structural — no JSON catch-all bucket, and nothing back-fills these meanings into `fact_measurement` / `fact_interval` / note storage.
- **Agent-mediated profile capture works.** A bounded, closed allowlist (`src/premura/profile_fields.py`: `birth_date`, `sex`, `standing_height_cm`) is written one fact at a time through `record_profile_context` (`src/premura/store/profile_intake.py`), which appends/supersedes (history kept, never overwritten) and stamps `source_kind="agent_profile_capture"`. Surfaced as the default MCP tools `profile_context_supported_fields` / `profile_context_record` and the expert CLI verbs `hpipe profile-fields` / `hpipe profile-record`. Unsupported or derived keys (e.g. `age`) are rejected at the store boundary, not stored.
- **Normalized intake load path works.** `persist_intake_batch` loads a normalized `IntakeBatch` (the intake counterpart of `IngestBatch`) idempotently — re-running the same source artifact is a no-op via the per-event `dedupe_key UNIQUE` constraint.

**Explicitly not shipped (still follow-on work):**

- **No built-in nutrition/supplement importer.** The intake tables and load path exist, but adapting a *specific* source (a meal-logging app export, a supplement log) into them is parser/plugin work, exactly like the wearable sources. There is no built-in MyFitnessPal-style importer.
- **Age-adjusted interpretation remains deferred.** `age` stays derived from `birth_date` at evaluation time, never stored. BMI is no longer in the deferred set — it now ships as the first cross-domain Stage 2 proof consumer using the input-resolution seam (see "Stage 2 / Stage 3 baseline" above). Issue `#6`'s "profile-dependent signals" framing is **partially** satisfied by BMI; the remaining deferred items under that thread are age-adjusted interpretation and any further profile-dependent signal that requires a new declared dependency type.

## Evidence-admissibility foundation (shipped 2026-05-29)

The `stage-2-evidence-admissibility-foundation-01KSSR40` mission turned the
research note's central finding — *the dangerous failure is using the wrong
evidence for the question, especially old evidence presented as if it described
the present* — into a deterministic policy layer that decides which evidence is
admissible **before** any later tool uses it:

- **Closed question-type vocabulary.** `premura.engine.policies.QuestionType`
  classifies a request before evidence selection. The descriptive members
  (`current_status`, `recent_trend`, `long_term_control`, `historical_baseline`)
  ship alongside the two first-class analytical members added by the analytical
  mission (`level_shift_detection`, `smoothed_pattern` — see below).
- **Metric-family policies declare what each family can honestly support.**
  Freshness windows and per-question-type sufficiency rules live in
  `src/premura/engine/policies/` (`_model.py`, `_defaults.py`), declared per
  family rather than hardcoded per metric.
- **Admissibility is a deterministic decision, not a vibe.** `evaluate_evidence`
  decides admissible / rejected / insufficient for the question, preserves
  provenance, timestamps, caveats, and rejection reasons, and **refuses clearly**
  when no admissible evidence remains. `resting_hr_status` is wired through this
  path as the proof integration (`StatusResult` shape preserved).

## Stage 3 analytical tools (shipped 2026-05-30)

The `stage-3-analytical-tools-01KST48C` mission landed the first slice of
**Phase 3 (`v0.3 analytical depth`)**: a bounded analytical contract plus two
deterministic proof tools on top of the admissibility foundation.
`src/premura/engine/analytical_contract.py`, `analytical_inputs.py`, and
`analytical_tools.py` define the surface; `docs/history/research/STAGE3_ANALYTICAL_TOOLS_RESEARCH.md`
records the design.

- **Five deterministic tools, on the default MCP surface.** The first bounded
  analytical tool set is now complete: `change_point`
  (level-shift detection — "did this metric step to a new level, and when?"),
  `smoothed_average` (conservative trailing smoothed pattern), `correlate`
  (the pre-registered, lagged *association* tool — see "Correlation as a
  pre-registered lagged association" below), `rolling_mean` (a declared
  moving-window summary — see "Finished analytical tool set" below), and
  `paired_t_test` (a declared before/after anchor-date paired comparison — see
  "Finished analytical tool set" below). `engine.list_analytical_tools()`
  returns exactly these five. All are exposed through
  `premura-mcp` (the default validity-gated surface — now **twenty** tools after
  the PubMed grounding slice; see "PubMed literature grounding" below),
  delegate entirely to the engine, perform no statistics in the MCP layer, and
  **name no cause** — no causation, diagnosis, or treatment claims.
- **Analytical question types are first-class.** Each tool routes to its own
  `QuestionType` (`change_point` → `level_shift_detection`,
  `smoothed_average` → `smoothed_pattern`, `correlate` → `lagged_association`)
  with analytical `QuestionRules` declared on the relevant family policies. They
  are **not** collapsed onto `recent_trend` — the research note (D4) rejected
  that, and the mission-review fix (`42b0880`) made the separation real and
  lock-tested.
- **Admissibility gate before computation.** `prepare_input_series` builds an
  `AnalyticalInputSeries` whose window/overlap metadata is enforced non-null and
  ordered for any non-refusal series; inadmissible / stale / insufficient /
  out-of-bounds inputs flow straight through as a first-class **refusal** with no
  estimate.
- **Mandatory result envelope with validity, not just point estimates.** A
  non-refusal `available` result must carry the estimate **plus** required
  validity metadata and a **confound checklist** drawn from a closed,
  runtime-owned vocabulary (`ConfoundKey`: `high_imputation`, `low_sample_size`,
  `short_overlap_window`, `parameter_at_limit`, `vendor_estimate_input`,
  `temporal_autocorrelation`, `life_event_sensitive`,
  `method_uncertainty_unavailable`, and `common_cause_plausible` — the
  lurking/common-cause key added by the `correlate` mission). Agents cannot mint
  their own quality labels; keys outside the set are rejected at registration.
  This directly addresses the surfacing half of risk `R7` — confounds ship
  *alongside* the estimate.

### Correlation as a pre-registered lagged association (shipped 2026-05-30)

The `correlate-lagged-association-01KSWKV0` mission landed `correlate`, the first
**multi-input** analytical tool, on the same default MCP surface. Its locked
architecture is design decision note
[`0008`](../building/adr/0008-correlate-pre-registered-lagged-association.md) and its
statistical choices are settled in
[`CORRELATE_METHODOLOGY_RESEARCH.md`](../history/research/CORRELATE_METHODOLOGY_RESEARCH.md).

- **Association, never significance.** `correlate` reports a signed Spearman's-rho
  *association* with an effect size and an honest plausible **range** — it never
  computes or returns a p-value or the word "significant," and names no cause.
  Any request for a forbidden quantity (a p-value, a significance test, a
  tolerance window, a lag scan) is refused *before* computation.
- **Caller-declared, directional, whole-day lag.** The relationship is "left at
  day *D* associates with right at day *D + lag*"; the engine shifts the
  responding series by that whole number of days and pairs on the same local
  calendar day. Lag is asymmetric, defaults to 0, and is **never scanned** for the
  best fit. The pre-registered hypothesis (metric pair, lag, expected direction)
  is a mandatory input.
- **Paired inputs through `prepare_paired_input`.** Two already-admitted series
  are aligned same-day-after-lag, the overlap window is narrowed to the actual
  paired days, and the imputed-pair fraction plus a reproducible paired source
  summary are recorded. The uncertainty band is computed on an
  autocorrelation-corrected effective sample size (`N_eff`), not the raw count,
  and the tool refuses below the conservative paired-sample / `N_eff` floor rather
  than show a confident-looking spurious association.

**Explicitly not shipped here (Phase 3 follow-on tracked elsewhere):** the
PubMed grounding tools shipped in a *later* mission, not in this analytical line
— see "PubMed literature grounding" below. The literature-to-warehouse bridge,
nutrition/supplement source adaptation, and the teaching UI all remain deferred.
The **research trace audit skill** — the interpretation work that reads the
trace's audit-consumer contract — **has now shipped**; see "Research trace audit
skill" below. The session research trace / multiplicity disclosure itself **has
now shipped** — see "Session research trace" below. With `rolling_mean` and
`paired_t_test` now shipped (see "Finished analytical tool set" below), all five
built-in analytical tools are available over the now-stable analytical contract.

### Finished analytical tool set (shipped 2026-06-01)

The `finish-analytical-tool-set-01KT0Y95` mission completed the first bounded
analytical tool set by adding the last two deterministic tools, both on the
default MCP surface and both routed through the same admissibility gate, result
envelope, and trace recording as the earlier three.

- **`rolling_mean` — a declared moving-window summary.** It reports a moving
  level over one admitted ordered series across a **caller-declared window**, with
  visible per-point coverage and imputation counts. The window is fixed before the
  result exists; the tool never scans windows or keeps the strongest-looking one.
  It is distinct from `smoothed_average` — a moving-window summary with explicit
  coverage/imputation metadata, not a rename of the trailing-smoothed pattern. It
  refuses (no estimate) on a refused/stale/missing input, a zero/negative/too-large
  window, out-of-range coverage, insufficient coverage, or any window-scan request.
- **`paired_t_test` — a declared before/after anchor-date comparison.** It reports
  a **paired difference** (mean of after minus before) around one caller-declared
  anchor date, with observed vs expected direction, a descriptive **uncertainty
  band** (dispersion of the paired differences), imputation visibility, and a
  confound checklist. It is **not a significance test**: it computes and returns
  **no p-value and no significance verdict**, and names no cause — the anchor date
  is a comparison boundary, never a stated cause of any change. It refuses on a
  refused/stale/missing input, a missing/malformed anchor date, out-of-bounds
  before/after windows, a missing expected direction, too few valid pairs, constant
  paired differences, or any request for condition-label pairing, arbitrary pair
  maps, or anchor/window scanning.
- **Scope is anchor-date pairing only.** Broader **condition-label pairing** is a
  deliberately deferred future extension; adding it requires a new pairing
  contract, new trace-identity fields, and new refusal rules, not a quiet widening
  of the anchor-date request shape (see
  [`src/premura/engine/CONTRACT.md`](../../src/premura/engine/CONTRACT.md)).

## Session research trace and multiplicity disclosure (shipped 2026-05-31)

The `session-research-trace-01KSYT4A` mission landed the **session research
trace**: an explicit, append-only ledger at the MCP boundary that records the
analytical calls an agent dispatches in a research session and derives a
*measured* multiplicity disclosure. Its locked architecture is design decision
note [`0009`](../building/adr/0009-session-research-trace-and-multiplicity-disclosure.md).
The stateful trace lives in `src/premura/trace.py` (a pure, MCP-agnostic,
engine-agnostic service) over `trace.*` tables added by migration
`005_trace_audit.sql`; the analytical **engine stayed pure and
stateless** — recording happens *around* dispatch, never inside it.

- **Explicit session lifecycle.** `research_trace_open(client_label=None)` opens
  a session and returns a stable `session_id` plus the warehouse fingerprint and
  schema version the disclosure is computed against. The three trace tools live
  on the **default** agent-safe surface because the trace IS the supported agent
  workflow.
- **Opt-in, byte-identical recording.** Each analytical tool (`change_point`,
  `smoothed_average`, `correlate`) gained an optional `session_id`. Passing it
  records the call and attaches a top-level `trace` object **beside** the
  unchanged engine envelope; omitting it writes no trace row and returns a
  byte-identical envelope. Trace metadata never enters the engine output.
- **Measured multiplicity disclosure.** `research_trace_disclosure(session_id,
  format="json", include_calls=True)` derives the raw analytical-call count and
  the **unique hypotheses examined** (N) from the recorded rows — exact retries
  collapse to one hypothesis, refusals still count toward N. The framing is
  "K user-facing findings among N unique hypotheses examined"; it never says
  "significant results" and Premura computes **no** multiplicity-corrected
  statistics. JSON is the default; a `markdown` export is generated on demand and
  is **not** the canonical record.
- **Surfaced is an explicit agent mark.** `research_trace_mark_surfaced(session_id,
  call_id, role, rationale)` records which recorded calls the agent actually used
  in the user-facing answer. When a session has calls but no marks, the surfaced
  count is reported **surfaced unavailable** with an explicit message, never a
  guessed `0`.
- **Provenance, not health facts.** The trace stores only call/result references,
  hashes, and a bounded validity-metadata summary — never raw `hp.*` health rows.
  The audit-consumer contract (`kitty-specs/session-research-trace-01KSYT4A/contracts/audit-consumer-contract.md`)
  is the stable structured surface the research trace audit skill reads (now
  shipped — see below).

## Research trace audit skill (shipped 2026-05-31)

The `research-trace-audit-skill-01KSZC2J` mission landed the **research trace
audit skill**: a Premura-specific agent skill that consumes the audit-consumer
contract (read-only) to judge one final analytical answer against its session
research trace disclosure. It is **not** a generic answer-audit product — it
applies only to an answer built from a Premura Session Disclosure object, and it
issues no network call at runtime.

- **Folder + prose `SKILL.md`.** The skill ships at
  `src/premura/skills/research-trace-audit/` as a conformant Agent Skill: a prose
  `SKILL.md` (when-to-invoke, the two required inputs — the structured Session
  Disclosure object plus the final answer text — the review procedure, and the
  `pass` / `needs_revision` / `blocked` output shape with evidence refs) beside a
  bounded `AUDIT_RUBRIC.md`.
- **Bounded rubric, not a banned-phrase list.** `AUDIT_RUBRIC.md` is a registry
  of criteria under **four closed categories** (search-effort disclosure,
  refused/unavailable handling, contradiction handling, overclaim boundary) plus
  the **rule for adding a criterion** — per DOCTRINE (guide, don't enumerate), it
  defines the rule for growing the list rather than freezing a word list.
- **Five synthetic fixtures.** `fixtures/` holds five calibration examples —
  `pass`, `omitted-search-effort`, `hidden-refusal`, `surfaced-unavailable`, and
  `overclaim` — each a synthetic Session Disclosure + answer + expected verdict,
  with no real `hp.*` rows or PHI.
- **Installs via the existing installer.** The skill is installed by the existing
  `hpipe install-skills` to `.claude/skills/`, the same project skill home both
  Claude Code and OpenCode discover. A separate OpenCode-style installer target
  was **evaluated and deliberately rejected**: live OpenCode docs confirm it scans
  the same `.claude/skills/` path, so one home serves both clients and a second
  writer would only create redundant on-disk copies. This kept the mission purely
  additive — one new skill directory, **no** change to `install_skills()`.
- **Reads the trace; changes nothing in it.** The skill consumes the
  audit-consumer contract read-only. It changed **no** trace counts, no trace
  schema, and no analytical tool math; the trace remains measurement, and the
  skill supplies the separate interpretation step.

## PubMed literature grounding (shipped 2026-06-01)

The `pubmed-grounding-tools-01KT1BPM` mission landed the first **literature
grounding** slice: two Stage 3 tools on the default MCP surface that let an agent
find and cite published research. They take the default surface from eighteen to
**twenty** tools. The tools live in `src/premura/mcp/pubmed.py` (a Premura-owned
adapter) and are wrapped on the server in `src/premura/mcp/server.py`.

- **`pubmed_search` returns candidates only.** A search reaches PubMed for
  discovery hints. Every hit carries `citation_status = candidate_only`, and the
  payload restates the citation rule: a search candidate is **never** citeable,
  even when it includes a PMID. Search is for finding records to fetch, not for
  citing.
- **`pubmed_fetch` returns a citeable record.** Given one exact PMID, it returns a
  record with `citation_status = citeable_fetched_record` plus the `pubmed_url`
  and `provider` provenance an honest citation needs. A final answer may cite
  **only** a fetched record obtained this way — never a search candidate.
- **One native provider, no new dependency.** Both tools delegate to a minimal
  Premura-owned adapter over NCBI E-utilities (provider label `ncbi-eutils`),
  called over the Python standard library so no HTTP dependency is added. The
  adapter owns the candidate-vs-fetched citation rule as a *Premura* invariant,
  not a provider feature. Provider/network failures come back as a structured
  `provider_error` outcome, never an exception; the tests are deterministic and
  offline (a fake transport returns canned E-utilities responses).
- **Literature, not the user's data.** These tools fetch bibliographic records
  about the published literature. They do **not** read, diagnose over, treat,
  name a cause from, or compute over the operator's own `hp.*` health data, and
  they run no SQL.

**Explicitly not in this first slice (still deferred):** full-text retrieval,
deep paper analysis, expansion to other sources (Europe PMC, Unpaywall), MeSH
lookup, related-article discovery, and citation formatting are all out of scope
here. The **concept-to-metric mapping** and the **literature-to-warehouse
bridge** — connecting a fetched paper to the operator's own warehouse queries —
also remain future work. This slice grounds citations in fetched records; it does
not yet tie literature to personal data.

## Runtime build-and-use parser boundary (settled 2026-06-02)

The `session-log-substrate-01KT45S1` mission (slice one — the loggable session
substrate) is **shipped** — merged to master on 2026-06-02 (commit `798493b`).
Its doctrine-facing change is a clarification (FR-130). The maintainer settled the runtime/dev-time boundary the
docs previously contradicted: at runtime an agent may build a parser and **use
it immediately for the operator's own data, with no reviewer** — this is part of
using an installed Premura. Review enters **only if the human consents to
contribute that parser back** as a public PR; the PR (not the local use) goes
through the existing development/review process.

- **Three docs now agree.** `docs/building/planning/operating-agent-roles.md`
  §"Dev-time boundary", `docs/building/adr/0010-runtime-orchestrator-and-operating-roles.md`,
  and `docs/shared/DOCTRINE.md` state the build-and-use-now rule consistently; no
  remaining sentence requires review before a parser is used on the operator's
  own data.
- **Operating-role definition unchanged.** "Operating role" still means narrowly
  *a job the orchestrator dispatches through Premura's MCP tools*; parser-building
  is file-editing and remains **not** an MCP operating role. Only the
  review-before-use clause changed. This sits inside charter risk-boundary #4
  (internal work autonomous; PR-back is the human-approved external action), so no
  charter amendment was needed.
- **Pinned by a test.** `tests/test_doctrine_build_and_use.py` asserts on the file
  bytes (SC-007) so the three docs cannot silently revert to review-before-use.
- **Merged and green.** The full session-log substrate slice — the session
  log store (its own local DuckDB file), runtime contract checker, sandbox/ingest
  runner, synthetic fixtures + good/dishonest reference parsers, deterministic
  three-rule grader, offline repeatable check, and the live-trial seam (its
  real-model wiring was a named follow-up, **since closed and hardened** — see
  "Cheap-model live trial" below) — landed in `798493b` with all eight work packages
  approved and merged. The deterministic grader recomputes every rule from ground
  truth (warehouse + fixture manifest), so a parser that silently drops a field is
  graded **fail** by reconciliation even when its own metadata looks clean.

## Cheap-model live trial — seam closed and hardened (shipped 2026-06-04)

The `cheap-operator-live-trial-01KT6PSA` mission shipped the real cheap-model
live trial over the session-log substrate's seam, and a follow-up
(`live-trial-follow-up-hardening`) finished the cleanup the seam still carried:

- **Seam closed for real (FR-001/002).** `live_trial.real_model_operator()` /
  `real_model_driver()` are now fully closed delegated factories — a bare call
  defaults to the committed synthetic fixture / default local model and returns a
  working object instead of raising `NotImplementedError`. The seam no longer
  describes itself as a deferred placeholder probe.
- **Inspection-grade attempt telemetry (FR-003).** Each attempt records a
  structured `SelfReconciliationResult` (source columns, accounted, unaccounted)
  plus any parser import/parse error carried separately, so a local inspector can
  see *why* an attempt failed, not just that it did.
- **Local-only backend enforced in code (FR-005 / NFR-002).** A non-local
  `OLLAMA_URL` is rejected before any network request, so prompt data and source
  samples cannot leave the machine through config drift — the local-model
  boundary is a code check, not just prose.
- **Opt-in, synthetic-only inspection mode (FR-004 / NFR-004).** `keep_sandboxes`
  retains the kept-sandbox trees for inspection, but **only** for a synthetic
  source; a real-data run always tears its sandbox down, so the no-persist rule
  for real local data still holds. Default behavior is unchanged (teardown).

The matching real-model test stays behind the `live_trial` marker and runs
locally against Ollama; the default suite still needs no model server and the
live-trial path can never block CI (NFR-001 / NFR-005).

## Usable intake dimensions (shipped 2026-06-04)

The `usable-intake-dimensions-01KT950A` mission (mission #19, merged `4d9a12e`)
turned the two intake domains from *storable-but-unreadable* into first-class,
agent-usable dimensions. Before it, `nutrition_intake` / `supplement_intake` had
storage tables and a load path but every declared dependency resolved to
`unsupported_domain`, and there was no parser path from a source export to
`IntakeBatch`. All six work packages are merged and done. What now works:

- **Both intake domains resolve through the existing seam.** Concrete resolvers
  (`engine/views/nutrition_intake.py`, `engine/views/supplement_intake.py`) ride
  the same `@resolver(domain=...)` seam as observation/profile — no new
  abstraction layer, no per-domain branch in the shared resolution path (asserted
  structurally by `tests/test_intake_resolvers.py`). A "no matching row" case
  returns an explicit missing / stale outcome and **never** falls back to a
  same-named observation row.
- **Two new descriptive signals, on the default surface.**
  `supplement_intake_adherence` (family `status`) answers "logged on K of the last
  N days" for a caller-declared supplement matcher; `nutrition_intake_trend`
  (family `trend`) answers up/down/flat for a caller-declared nutrient/energy key
  and **never imputes** missing days. Both return the standard four-state envelope
  and are exposed as default-surface tools (taking it to twenty-two).
- **A real runtime intake-parser path.** The parser contract and the
  `parser-generator` skill were updated together so a runtime agent can
  **build-and-use** an intake parser (`parse → IntakeBatch → persist`) for the
  operator's own data with no review — the same build-and-use boundary settled for
  observation parsers. A minimal reference intake parser + synthetic fixture prove
  the path end-to-end (FR-007/008).
- **The generalization is written down, not just asserted.**
  `docs/building/architecture/INTAKE_DIMENSIONS.md` records the four
  domain-agnostic steps for making any declared intake dimension usable, validated
  by both shipped domains; the go/no-go on a dedicated intake-dimension contract
  (deliberately **not** built — constraint C-003) is reasoned in
  `docs/building/planning/intake-dimension-contract-recommendation.md`.

**Still deferred (named so it is not assumed shipped):** adapting a *specific real
vendor export* (an actual meal-logging or supplement-log file) is now
fill-in-the-blank parser work against the documented path — the foundation is
done, a concrete real-source parser is not yet written. Age-adjusted
interpretation also remains deferred.

## What's working end-to-end

| Component | State | Evidence |
|---|---|---|
| Warehouse schema (`hp.*`) | ✅ | Observation/note tables (migrations 001–003) plus the profile/intake domain tables from migration `004_profile_intake.sql`, 191 seeded metrics, FK-safe auto-seed for unknown metric IDs (e.g. `bmt_custom:hips`). |
| Health Connect parser | ✅ | ~900k rows from a real ~200 MB v20 export in ~13 s parse+load. |
| Garmin GDPR parser | ✅ | Handles UDS, sleepData, healthStatusData, BloodPressureFile, HydrationLogFile, MetricsAcuteTrainingLoad, MetricsMaxMetData, TrainingReadinessDTO, summarizedActivities. Surfaces unknown filenames in `ingest_run.notes`. |
| Sleep as Android parser | ✅ | Synthetic-fixture tests; per-minute actigraphy walk with DST-safe wall-clock advancement. |
| BMT parser | ✅ | Detects long vs wide format from header. Long-format (current app) respects per-row `Unit`; custom metrics (`hips`, `waist`, `neck`, …) routed to `bmt_custom:*`. |
| Loader (batch insert) | ✅ | Polars→DuckDB temp-table registration, single `INSERT … SELECT … WHERE NOT EXISTS`. Native-key dedupe + cross-source priority dedupe done as set-based SQL. |
| CLI (`hpipe`) | ✅ | Ingest/ops verbs (`ingest`, `status`, `export`, `upload`, `doctor`, `gc`, `run-monthly`, `install-launchd`, `uninstall-launchd`, `install-skills`) plus the bounded profile-capture verbs `profile-fields` / `profile-record` (expert mirror of the agent capture tools). |
| Idempotency | ✅ | sha256 skip in `hp.ingest_run`, plus `dedupe_key UNIQUE` + intra-batch Polars `.unique()`. |
| CSV autodiscovery | ✅ | Header-sniffs SAA vs BMT (no naming convention required). |
| Export artifact encryption | ✅ | Live round-trip verified 2026-05-21 against `~/.config/premura/age.key`; decrypted snapshot byte-identical to `data/duck/health.duckdb` (`diff` empty). Per-test keypair regression in `tests/test_encrypt_roundtrip.py`. |
| Drive upload (now OPT-IN, not auto) | ⚠️ Code complete, not live | `hpipe upload` only runs on explicit invocation. `run-monthly` no longer pushes to Drive — it stops after the encrypted artifact lands locally. |
| Launchd plist | ✅ | Bootstrapped 2026-05-21 (`com.nbrandizzi.premura.monthly`). `kickstart` fired the macOS notification, `run-monthly` reached the `_wait_for_ready` loop without ingesting (no `.ready`), exited cleanly on SIGTERM. Plist render covered by `tests/test_launchd_plist.py` (incl. `plutil -lint`). |
| Tests | ✅ | 1000/1000 default-suite pytest pass (the `live_trial`-marked real-model test is excluded from the default suite and runs locally against Ollama), incl. a real-data HC regression that round-trips ~900k rows, the FR-6 `age` round-trip suite, FR-8 plist render + `plutil -lint`, full Stage 2 engine + Stage 3 signal-tool coverage (all eight signal-backed tools end-to-end, including the `supplement_intake_adherence` / `nutrition_intake_trend` intake signals — `tests/test_intake_resolvers.py`, `tests/test_intake_signals.py` — with a local-midnight fixture and a no-cross-domain-fallback regression), the profile/intake contract harness, profile capture append/supersede + allowlist enforcement, idempotent intake-batch loading, the Stage 2 input-resolution seam + BMI proof-consumer coverage, the evidence-admissibility policy layer, the Stage 3 analytical contract + `change_point`/`smoothed_average` end-to-end (admissibility gate, result envelope, closed confound vocabulary, first-class analytical question types), the `correlate` lagged-association tool end-to-end (paired-input preparation, same-day-after-lag pairing, Spearman + `N_eff` band, paired-sample floor refusals, forbidden-parameter refusals, `common_cause_plausible`, and the thin MCP wrapper), the completed `rolling_mean` and `paired_t_test` tools end-to-end (declared-window moving summary with coverage/imputation metadata; before/after anchor-date paired difference with descriptive uncertainty and no significance/causation claim; their refusal classes, trace identities, and thin MCP wrappers; the exactly-five-tool public catalog), and the session research trace end-to-end (the `005_trace_audit.sql` migration + `trace.*` ownership, the pure `premura.trace` service — raw-vs-N counting, exact-retry collapse, refusal breakdown, surfaced-unavailable fallback, engine-purity byte-identical envelopes — and the three trace MCP tools on the default/operator surfaces), and the cheap-model live-trial seam hardening (closed real-model factories, structured per-attempt `SelfReconciliationResult` with parser-error telemetry carried separately, local-only `OLLAMA_URL` rejection, and the synthetic-only retained-sandbox inspection mode). |

## Warehouse contents (current snapshot)

Row counts shown here are *shape illustrations* from a single operator's pipeline run, not a benchmark. Run `uv run hpipe status` against your own warehouse for live numbers.

`hp.fact_measurement` (per-metric coverage, source columns indicate which parsers contribute):

| metric | source coverage |
|---|---|
| heart_rate | HC (Garmin bridge) + Garmin GDPR BP-pulse |
| spo2 | HC + Garmin sleep-summary averages |
| resting_hr | HC + Garmin UDS daily |
| hrv_rmssd_overnight | Garmin-only (HC table is empty in observed data) |
| stress | Garmin healthStatus + UDS allDayStress + sleep avg |
| resp_rate | Garmin healthStatus + sleep avg |
| training_readiness | Garmin TrainingReadinessDTO |
| training_load | Garmin MetricsAcuteTrainingLoad |
| sleep_rating, sleep_deep_pct | Garmin sleepData |
| skin_temperature | Garmin healthStatus |
| intensity_minutes | Garmin UDS (weighted: mod + 2×vig) |
| weight | HC + BMT |
| hydration | Garmin sweat-loss estimates |
| bmr | HC |
| bp_systolic / bp_diastolic | Garmin BP file |
| bmt_custom:hips / waist / neck | BMT (long format) |
| height | HC + BMT |
| vo2_max | Garmin MetricsMaxMetData |

`hp.fact_interval` includes: steps, distance, total_kcal, sleep_stage, exercise_session, sleep_session, daily_wellness, active_kcal.

## Calibration vs SPEC §3 (Functional Requirements)

| FR | Met? | Notes |
|---|:---:|---|
| FR-1 HC ingestion | ✅ | Verified against a real `health_connect_export.db`; row counts match the parser's coverage report. |
| FR-2 Garmin GDPR | ✅ | All metrics listed in `docs/history/architecture/ARCHITECTURE_HISTORY.md`'s per-source table now appear at least once — see counts above. |
| FR-3 Sleep as Android | ✅ | Parser + unit tests pass on synthetic fixtures (per-minute actigraphy, DST-safe wall-clock advancement). Live-SAA exercise dropped from v1 scope (operator no longer plans to export from SAA). |
| FR-4 BMT with config-driven units | ✅ | Long-format file uses per-row units; wide-format fallback still respects `parsers.bmt.weight_unit` config. |
| FR-5 Dedupe within + across | ✅ | Demonstrated: re-ingest same file → 0 inserted; loader skips lower-priority overlapping rows. |
| FR-6 `age` round-trip | ✅ | Live round-trip 2026-05-21: `hpipe export --month 2026-05` → `age -d` → `diff` against source = empty. Regression suite: `tests/test_encrypt_roundtrip.py`. |
| FR-7 `rclone` upload + verify | ⏳ (scope change) | `upload.py` in place but **upload is now opt-in, not part of `run-monthly`**. User decides when (and whether) to push. |
| FR-8 launchd | ✅ | Bootstrapped 2026-05-21 (`com.nbrandizzi.premura.monthly`, `gui/$(id -u)`). `launchctl kickstart` triggered the macOS notification and `run-monthly` waited at `_wait_for_ready` without ingesting; clean shutdown on SIGTERM. Uninstall verified. Currently loaded; next fire 2026-06-01 10:00. Plist render covered by `tests/test_launchd_plist.py`. |
| FR-9 Idempotency by sha256 | ✅ | Loader returns `rows_inserted=0` on second pass. |
| FR-10 History preservation | ✅ | Append-only; `ingest_batch` (ULID) tagged on every row. |

## Known limitations

- **Health Connect HR-series uniqueness collisions**: parser emits ~3 rows that share `parent_uuid + epoch_millis` with siblings; Polars dedupes them before insert (in-batch). Counted as `rows_inserted` minus actual table delta — currently invisible in stats. Cosmetic only.
- **Wide-format BMT** with no `Time` column: timestamps land at 00:00:00 local; not a regression vs the historical architecture plan but worth flagging.
- **No FIT-file (per-activity stream) ingestion** — `docs/history/architecture/ARCHITECTURE_HISTORY.md` marks this as out of scope for v1.
- **`fact_interval` has no `unit` column**; we carry it in memory only. Fine for now; would need a migration if downstream queries want it.

## Fresh-clone setup (shipped 2026-06-01)

`uv run hpipe bootstrap` is shipped, **setup-only** behavior for a freshly cloned
checkout on the maintainer's supported macOS local workstation. It prepares and
verifies the local checkout (environment + bundled skills), confirms the core
project surfaces (`hpipe`, `premura-mcp`, `premura-mcp-operator`) import, and
reports whether an agent-session reload is needed before normal operation. The
`uv run` prefix is required because `hpipe` is a console script that does not
exist on a fresh clone until the package is installed. It is **not** a runtime
health-data operation: it does not ingest source artifacts, query the warehouse,
run analysis, or upload anything. See README "Quick start" for the fresh-clone
entry point.

## Operations

See [OPERATIONS.md](../using/OPERATIONS.md) for the current operator command surface and
day-to-day runbook.
