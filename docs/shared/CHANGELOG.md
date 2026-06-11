# premura — Changelog

> Status: append-only history. One entry per mission (or comparable unit of
> work), newest first, written when the work merges and **never edited
> afterward** — corrections get their own entry. The current-state snapshot
> (counts, tables, what works today) lives in [STATUS.md](STATUS.md); this file
> holds the narratives. When a mission lands: add an entry here, then rewrite
> the affected STATUS.md lines (STATUS has a hard line cap enforced by
> `tests/test_docs_structure.py`).

## 2026-06-11 — Tag hygiene: `v1.0.0` retagged as `v0.1.0` (audit R6)

The first local-ingest pipeline's restore point (commit `538aaf1`) was tagged
`v1.0.0` before the release-line policy settled on `v0.x` until the
user-facing threshold; that made a bare tag listing sort it as the latest
release. Retagged `v0.1.0` (the milestone number it actually was — annotated
tag records the rename) and the old `v1.0.0` deleted locally and on origin.
Earlier entries and history docs that say "tagged v1.0.0" describe what was
true when written. Also removed the last stale branch
(`docs/split-by-audience`, merged) from origin.

## 2026-06-11 — First real vendor intake parser: MyFitnessPal

The platform-meets-reality milestone the roadmap called for: the first *real*
vendor export adapted onto the intake path shipped by the
usable-intake-dimensions mission. `src/premura/parsers/myfitnesspal.py` reads
the official MyFitnessPal file export (zip of summary CSVs, or the bare
`Nutrition-Summary-*.csv`) and emits an **intake-only** `ParseOutput` — one
`NutritionIntakeInput` per (diary date, meal) row with event-level quantities
(`energy`, `protein`, `fat_*`, `carbohydrate`, …; 17 keys).

- **Two-seam discipline held.** Exercise-Summary (expended kcal — observation
  meaning, and typically synced *from* the wearable already ingested) is
  deliberately not emitted: ladder-resolving columns surface as `skipped_rows`
  with the double-count reason, homeless ones as `vendor:myfitnesspal:*`
  entries in `unmapped_metrics`. Nothing is dropped silently.
- **No invented data.** Empty cells are unknown (never zero); the four
  unit-unlabeled columns (vitamins/calcium/iron) carry `unit=None`; the bare
  diary date becomes a midnight timestamp with `local_tz=None`, so the
  resolver's UTC-day fallback reproduces the MyFitnessPal diary date verbatim.
- **Routing.** Registered as `hpipe ingest --source mfp`; inbox autodiscovery
  sniffs MFP zips (so the Garmin zip glob skips them) and MFP CSVs (so they no
  longer fall through to BMT).
- **Proven on real data (build-and-use, no review).** The operator's real
  export loaded 37 events; re-ingest is a clean no-op (37 dup-skips);
  `nutrition_intake_trend` answers `available` over the loaded window with
  gaps named, not filled. Tests are synthetic-only; no real rows enter the
  repo.

## 2026-06-11 — Docs restructure: CHANGELOG + slim STATUS, single-home facts

Issue #21 / audit §5. STATUS.md had become a changelog wearing a snapshot's
clothes (~500 lines, every mission appending a narrative section). This change:

- created this CHANGELOG.md and moved the per-mission narratives here verbatim;
- rewrote STATUS.md as a short, fully rewritable snapshot with a **hard line
  cap** pinned by `tests/test_docs_structure.py`;
- made STATUS.md the **single home** for shipped-state counts — STAGES.md,
  ROADMAP.md, and FULL_APP_DEVELOPMENT_PLAN.md now link instead of restating
  (the plan doc was already stale at "twenty tools");
- moved the **audit-consumer contract** to its live home
  `docs/building/architecture/AUDIT_CONSUMER_CONTRACT.md` (a pointer remains at
  the old `kitty-specs/.../contracts/` path) and reframed the
  `CORRELATE_METHODOLOGY_RESEARCH.md` citations so the operative statistical
  rules are normative in `src/premura/engine/CONTRACT.md` and the frozen
  research note holds the rationale;
- added the single-home rule to DOCTRINE.md's design self-checks.

## 2026-06-11 — Engineering safety net: CI, mypy burndown, data guard, doctor checks

Issues #16, #18, #19, #20, from the
[2026-06-10 software-development health audit](../history/audits/2026-06-10-software-development-health-audit.md).
Not a spec-kitty mission — direct, machine-verifiable ops hardening:

- **CI on every push/PR** (`.github/workflows/ci.yml`): `uv lock --check`,
  `ruff check`, `ruff format --check`, `mypy src/`, and the default pytest
  suite, all blocking, with `age` installed on the runner so the encrypt
  round-trip tests run instead of skipping.
- **All 13 mypy errors burned down** (`types-python-dateutil` stubs; explicit
  kwargs replace the type-defeating `**dict` unpacking in
  `health_connect.py`; guards in `garmin_gdpr.py` / `engine/_query.py`).
  `mypy src/` is clean and now a blocking gate.
- **Tracked-data guard** (`ops/check_no_tracked_data.sh`, in CI and
  pre-commit): no data-like file (`.duckdb` / `.db` / `.sqlite*` / `.age`,
  `data/`) can be tracked or staged. The one-time scan of full git history
  came back clean — no data-like path was ever committed.
- **`hpipe doctor` now proves the backup story**: the age key check reads the
  key (not just stats it), and a new `backup round-trip` check encrypts a probe
  with the recipients file and decrypts it with the on-disk key, so a
  rotated/mismatched pair fails loudly while both files still exist.

## 2026-06-04 — Usable intake dimensions (`usable-intake-dimensions-01KT950A`)

Mission #19, merged `4d9a12e`. Turned the two intake domains from
*storable-but-unreadable* into first-class, agent-usable dimensions. Before it,
`nutrition_intake` / `supplement_intake` had storage tables and a load path but
every declared dependency resolved to `unsupported_domain`, and there was no
parser path from a source export to `IntakeBatch`. All six work packages merged
and done. What it shipped:

- **Both intake domains resolve through the existing seam.** Concrete resolvers
  (`engine/views/nutrition_intake.py`, `engine/views/supplement_intake.py`) ride
  the same `@resolver(domain=...)` seam as observation/profile — no new
  abstraction layer, no per-domain branch in the shared resolution path (asserted
  structurally by `tests/test_intake_resolvers.py`). A "no matching row" case
  returns an explicit missing / stale outcome and **never** falls back to a
  same-named observation row.
- **Two new descriptive signals, on the default surface.**
  `supplement_intake_adherence` (family `status`) answers "logged on K of the
  last N days" for a caller-declared supplement matcher; `nutrition_intake_trend`
  (family `trend`) answers up/down/flat for a caller-declared nutrient/energy key
  and **never imputes** missing days. Both return the standard four-state
  envelope and are exposed as default-surface tools (taking that surface to
  twenty-two).
- **A real runtime intake-parser path.** The parser contract and the
  `parser-generator` skill were updated together so a runtime agent can
  **build-and-use** an intake parser (`parse → IntakeBatch → persist`) for the
  operator's own data with no review — the same build-and-use boundary settled
  for observation parsers. A minimal reference intake parser + synthetic fixture
  prove the path end-to-end (FR-007/008).
- **The generalization is written down, not just asserted.**
  `docs/building/architecture/INTAKE_DIMENSIONS.md` records the four
  domain-agnostic steps for making any declared intake dimension usable,
  validated by both shipped domains; the go/no-go on a dedicated
  intake-dimension contract (deliberately **not** built — constraint C-003) is
  reasoned in
  `docs/building/planning/intake-dimension-contract-recommendation.md`.

Still deferred after this mission: adapting a *specific real vendor export* (an
actual meal-logging or supplement-log file) — fill-in-the-blank parser work
against the documented path — and age-adjusted interpretation.

## 2026-06-04 — Cheap-model live trial: seam closed and hardened (`cheap-operator-live-trial-01KT6PSA` + `live-trial-follow-up-hardening`)

Shipped the real cheap-model live trial over the session-log substrate's seam,
and a follow-up finished the cleanup the seam still carried:

- **Seam closed for real (FR-001/002).** `live_trial.real_model_operator()` /
  `real_model_driver()` are fully closed delegated factories — a bare call
  defaults to the committed synthetic fixture / default local model and returns
  a working object instead of raising `NotImplementedError`.
- **Inspection-grade attempt telemetry (FR-003).** Each attempt records a
  structured `SelfReconciliationResult` (source columns, accounted, unaccounted)
  plus any parser import/parse error carried separately, so a local inspector
  can see *why* an attempt failed, not just that it did.
- **Local-only backend enforced in code (FR-005 / NFR-002).** A non-local
  `OLLAMA_URL` is rejected before any network request, so prompt data and
  source samples cannot leave the machine through config drift.
- **Opt-in, synthetic-only inspection mode (FR-004 / NFR-004).**
  `keep_sandboxes` retains kept-sandbox trees for inspection, but **only** for a
  synthetic source; a real-data run always tears its sandbox down.

The matching real-model test stays behind the `live_trial` marker and runs
locally against Ollama; the default suite needs no model server and the
live-trial path can never block CI (NFR-001 / NFR-005).

## 2026-06-02 — Session-log substrate slice one + build-and-use doctrine (`session-log-substrate-01KT45S1`)

Merged to master in `798493b` with all eight work packages approved. Landed the
per-run **session log** (a local, PHI-bearing DuckDB store recording sessions,
steps, and ingest provenance) plus the runtime-contract checker, sandbox/ingest
runner, synthetic fixtures + good/dishonest reference parsers, a deterministic
three-rule grader, an offline repeatable check, and the live-trial seam (real
wiring was a named follow-up, closed 2026-06-04). The grader recomputes every
rule from ground truth (warehouse + fixture manifest) and never trusts a
parser's self-report, so a parser that silently drops a field is graded
**fail** by reconciliation even when its own metadata looks clean.

It also carried the **runtime build-and-use doctrine clarification** (FR-130).
The maintainer settled the runtime/dev-time boundary the docs previously
contradicted: at runtime an agent may build a parser and **use it immediately
for the operator's own data, with no reviewer** — this is part of using an
installed Premura. Review enters **only if the human consents to contribute
that parser back** as a public PR. Three docs now agree
(`operating-agent-roles.md` §"Dev-time boundary", ADR 0010,
[DOCTRINE.md](DOCTRINE.md)); "operating role" still means narrowly *a job the
orchestrator dispatches through Premura's MCP tools* — parser-building is
file-editing and not an MCP operating role. Pinned by
`tests/test_doctrine_build_and_use.py` (SC-007) so the docs cannot silently
revert to review-before-use.

## 2026-06-01 — Finished analytical tool set (`finish-analytical-tool-set-01KT0Y95`)

Completed the first bounded analytical tool set by adding the last two
deterministic tools, both on the default MCP surface and routed through the
same admissibility gate, result envelope, and trace recording as the earlier
three:

- **`rolling_mean` — a declared moving-window summary.** A moving level over
  one admitted ordered series across a **caller-declared window**, with visible
  per-point coverage and imputation counts. The window is fixed before the
  result exists; the tool never scans windows. Distinct from `smoothed_average`,
  not a rename. Refuses on a refused/stale/missing input, a bad window,
  insufficient coverage, or any window-scan request.
- **`paired_t_test` — a declared before/after anchor-date comparison.** Reports
  a **paired difference** (mean of after minus before) around one
  caller-declared anchor date, with observed vs expected direction, a
  descriptive **uncertainty band**, imputation visibility, and a confound
  checklist. **Not a significance test**: no p-value, no significance verdict,
  names no cause. Refuses on malformed anchors, out-of-bounds windows, too few
  valid pairs, constant differences, or any request for condition-label
  pairing, arbitrary pair maps, or anchor/window scanning.
- **Scope is anchor-date pairing only.** Broader condition-label pairing is a
  deliberately deferred extension requiring a new pairing contract, new
  trace-identity fields, and new refusal rules (see
  [`src/premura/engine/CONTRACT.md`](../../src/premura/engine/CONTRACT.md)).

## 2026-06-01 — PubMed literature grounding (`pubmed-grounding-tools-01KT1BPM`)

The first **literature grounding** slice: two Stage 3 tools on the default MCP
surface that let an agent find and cite published research, living in
`src/premura/mcp/pubmed.py` (a Premura-owned adapter):

- **`pubmed_search` returns candidates only.** Every hit carries
  `citation_status = candidate_only`; a search candidate is **never** citeable,
  even with a PMID. Search finds records to fetch, not to cite.
- **`pubmed_fetch` returns a citeable record.** Given one exact PMID, returns
  `citation_status = citeable_fetched_record` plus `pubmed_url` and `provider`
  provenance. A final answer may cite **only** a fetched record.
- **One native provider, no new dependency.** Both delegate to a minimal
  adapter over NCBI E-utilities (provider label `ncbi-eutils`) via the Python
  standard library. The candidate-vs-fetched rule is a *Premura* invariant.
  Provider/network failures return a structured `provider_error`, never an
  exception; tests are deterministic and offline.
- **Literature, not the user's data.** These tools never read, diagnose over,
  or compute on the operator's own `hp.*` health data, and run no SQL.

Explicitly not in this slice: full-text retrieval, deep paper analysis, other
sources (Europe PMC, Unpaywall), MeSH lookup, related-article discovery,
citation formatting, concept-to-metric mapping, and the
literature-to-warehouse bridge.

## 2026-06-01 — Fresh-clone bootstrap (`uv run hpipe bootstrap`)

Setup-only behavior for a freshly cloned checkout: prepares and verifies the
local environment + bundled skills, confirms the core surfaces (`hpipe`,
`premura-mcp`, `premura-mcp-operator`) import, and reports whether an
agent-session reload is needed. Never ingests, queries, analyzes, or uploads.

## 2026-05-31 — Research trace audit skill (`research-trace-audit-skill-01KSZC2J`)

A Premura-specific agent skill that consumes the audit-consumer contract
(read-only) to judge one final analytical answer against its session research
trace disclosure. Not a generic answer-audit product; it issues no network call
at runtime.

- Ships at `src/premura/skills/research-trace-audit/`: a prose `SKILL.md`
  (when-to-invoke, the two required inputs — the structured Session Disclosure
  object plus the final answer text — the review procedure, and the
  `pass` / `needs_revision` / `blocked` output shape) beside a bounded
  `AUDIT_RUBRIC.md`.
- **Bounded rubric, not a banned-phrase list**: criteria under four closed
  categories (search-effort disclosure, refused/unavailable handling,
  contradiction handling, overclaim boundary) plus the **rule for adding a
  criterion** — per DOCTRINE, it defines how the list grows.
- Five synthetic calibration fixtures (`pass`, `omitted-search-effort`,
  `hidden-refusal`, `surfaced-unavailable`, `overclaim`); no real `hp.*` rows.
- Installs via the existing `hpipe install-skills` to `.claude/skills/` — the
  one project skill home both Claude Code and OpenCode discover. A separate
  OpenCode installer target was evaluated and deliberately rejected.
- Reads the trace; changes no trace counts, schema, or analytical math.

## 2026-05-31 — Session research trace and multiplicity disclosure (`session-research-trace-01KSYT4A`)

An explicit, append-only ledger at the MCP boundary recording the analytical
calls an agent dispatches in a research session, deriving a *measured*
multiplicity disclosure. Locked architecture: design decision note
[`0009`](../building/adr/0009-session-research-trace-and-multiplicity-disclosure.md).
The stateful trace lives in `src/premura/trace.py` (pure, MCP-agnostic,
engine-agnostic) over `trace.*` tables (migration `005_trace_audit.sql`); the
analytical **engine stayed pure and stateless** — recording happens *around*
dispatch.

- **Explicit session lifecycle.** `research_trace_open` returns a stable
  `session_id` plus the warehouse fingerprint and schema version. The three
  trace tools live on the **default** surface because the trace IS the
  supported agent workflow.
- **Opt-in, byte-identical recording.** Each analytical tool gained an optional
  `session_id`; passing it records the call and attaches a `trace` object
  **beside** the unchanged engine envelope; omitting it writes nothing and the
  envelope is byte-identical.
- **Measured multiplicity disclosure.** `research_trace_disclosure` derives the
  raw call count and the **unique hypotheses examined** (N) from recorded rows —
  exact retries collapse, refusals still count. Framing is "K user-facing
  findings among N unique hypotheses examined"; never "significant results";
  no multiplicity-corrected statistics. JSON canonical; Markdown on demand.
- **Surfaced is an explicit agent mark.** `research_trace_mark_surfaced`
  records which calls the agent actually used. Calls but no marks → surfaced
  reported **unavailable** with an explicit message, never a guessed `0`.
- **Provenance, not health facts.** The trace stores call/result references,
  hashes, and a bounded validity summary — never raw `hp.*` rows. The stable
  structured surface is the
  [audit-consumer contract](../building/architecture/AUDIT_CONSUMER_CONTRACT.md).

## 2026-05-30 — Correlate as a pre-registered lagged association (`correlate-lagged-association-01KSWKV0`)

`correlate`, the first **multi-input** analytical tool, on the default MCP
surface. Locked architecture: design decision note
[`0008`](../building/adr/0008-correlate-pre-registered-lagged-association.md);
operative statistical rules in
[`src/premura/engine/CONTRACT.md`](../../src/premura/engine/CONTRACT.md)
(rationale in the frozen
[`CORRELATE_METHODOLOGY_RESEARCH.md`](../history/research/CORRELATE_METHODOLOGY_RESEARCH.md)).

- **Association, never significance.** A signed Spearman's-rho *association*
  with an effect size and an honest plausible **range** — never a p-value or
  the word "significant", names no cause. Forbidden quantities are refused
  *before* computation.
- **Caller-declared, directional, whole-day lag**, default 0, **never scanned**.
  The pre-registered hypothesis (metric pair, lag, expected direction) is a
  mandatory input.
- **Paired inputs through `prepare_paired_input`**: same-day-after-lag pairing,
  overlap narrowed to actual paired days, imputed-pair fraction recorded. The
  uncertainty band uses an autocorrelation-corrected effective sample size
  (`N_eff`); the tool refuses below the conservative floor. Added the
  `common_cause_plausible` confound key to the closed vocabulary.

## 2026-05-30 — Stage 3 analytical tools, first slice (`stage-3-analytical-tools-01KST48C`)

The first slice of Phase 3 (`v0.3 analytical depth`): a bounded analytical
contract plus two deterministic proof tools on the admissibility foundation.
`src/premura/engine/analytical_contract.py`, `analytical_inputs.py`, and
`analytical_tools.py` define the surface;
`docs/history/research/STAGE3_ANALYTICAL_TOOLS_RESEARCH.md` records the design.

- `change_point` (level-shift detection) and `smoothed_average` (conservative
  trailing smoothed pattern) shipped first; all tools delegate entirely to the
  engine, perform no statistics in the MCP layer, and **name no cause**.
- **Analytical question types are first-class.** Each tool routes to its own
  `QuestionType` with analytical `QuestionRules` on the family policies — not
  collapsed onto `recent_trend` (research note D4 rejected that; mission-review
  fix `42b0880` made the separation real and lock-tested).
- **Admissibility gate before computation.** `prepare_input_series` builds an
  `AnalyticalInputSeries`; inadmissible / stale / insufficient inputs flow
  through as a first-class **refusal** with no estimate.
- **Mandatory result envelope**: estimate **plus** validity metadata and a
  confound checklist from a closed, runtime-owned vocabulary (`ConfoundKey`).
  Agents cannot mint their own quality labels (addresses risk `R7`).

## 2026-05-29 — Evidence-admissibility foundation (`stage-2-evidence-admissibility-foundation-01KSSR40`)

Turned the research note's central finding — *the dangerous failure is using
the wrong evidence for the question, especially old evidence presented as if it
described the present* — into a deterministic policy layer deciding which
evidence is admissible **before** any later tool uses it:

- **Closed question-type vocabulary.** `premura.engine.policies.QuestionType`
  classifies a request before evidence selection (descriptive members plus the
  analytical members added later).
- **Metric-family policies** declare freshness windows and per-question-type
  sufficiency rules in `src/premura/engine/policies/`, per family rather than
  per metric.
- **Admissibility is a deterministic decision.** `evaluate_evidence` decides
  admissible / rejected / insufficient, preserves provenance and rejection
  reasons, and **refuses clearly** when no admissible evidence remains.
  `resting_hr_status` wired through as the proof integration.

## 2026-05-27 — Profile and intake storage + agent-mediated capture (`implement-profile-and-intake-storage-01KSMWV1`)

Gave the profile/intake meaning contract
([PROFILE_AND_INTAKE_CONTRACT.md](../building/architecture/PROFILE_AND_INTAKE_CONTRACT.md))
a concrete storage adapter and the first write path:

- **Concrete domain tables** (migration `004_profile_intake.sql`):
  `hp.profile_capture_session` + `hp.profile_context_assertion` (profile);
  event → item → quantity/dose chains for nutrition and supplements. One-home
  separation is structural — no JSON catch-all, nothing back-fills these
  meanings into `fact_measurement` / `fact_interval`.
- **Agent-mediated profile capture.** A bounded, closed allowlist
  (`birth_date`, `sex`, `standing_height_cm`) written one fact at a time
  through `record_profile_context` (append/supersede, history kept), stamped
  `source_kind="agent_profile_capture"`. Surfaced as the default MCP tools
  `profile_context_supported_fields` / `profile_context_record` and the expert
  CLI verbs `hpipe profile-fields` / `hpipe profile-record`. Unsupported or
  derived keys (e.g. `age`) rejected at the store boundary.
- **Normalized intake load path.** `persist_intake_batch` loads an
  `IntakeBatch` idempotently via the per-event `dedupe_key UNIQUE` constraint.

The BMI cross-domain proof consumer and the input-resolution seam
(`resolve_dependency`, `RESOLVERS`, `@resolver(domain=...)`) shipped on this
foundation, making BMI the first cross-domain Stage 2 signal — computed from
declared standing height plus a usable body-weight observation, refusing
honestly when either prerequisite is missing or stale.

## 2026-05-21 — Live encrypt round-trip + launchd installation verified

`hpipe export --month 2026-05` → `age -d` → `diff` against source = empty
(regression suite `tests/test_encrypt_roundtrip.py`, per-test keypair). The
launchd agent `com.nbrandizzi.premura.monthly` was bootstrapped, kickstarted
(macOS notification fired, `run-monthly` waited at `_wait_for_ready` without
ingesting, clean SIGTERM shutdown), and uninstall verified. Plist render
covered by `tests/test_launchd_plist.py` (incl. `plutil -lint`).

## 2026-05-20 — Drive upload becomes opt-in (policy change)

As the project starts looking like a real application for others, Drive upload
is **opt-in**, not part of the automated monthly run. `hpipe run-monthly` ends
with the encrypted `.age` artifact in `data/exports/YYYY-MM/`; the user decides
whether to `hpipe upload`. The `age` private key stays local by default, with a
password-manager recipe (Bitwarden as reference) in `ops/bootstrap.sh`.

## Earlier — v1 ingest foundation

The four-source ingest pipeline (Health Connect, Garmin GDPR, Sleep as
Android, BMT) into a local DuckDB warehouse with idempotent re-ingest,
cross-source dedupe, encrypted export artifacts, and the `hpipe` CLI. The
historical tag `v1.0.0` marks this foundation as a restore point; the product
line is treated as `v0.x` going forward. See
[ARCHITECTURE_HISTORY.md](../history/architecture/ARCHITECTURE_HISTORY.md) for
the per-source design record.
