# premura — Current Status

> Status: live reference. A bounded, fully rewritable **snapshot** of what is
> true and shipped today — current counts and tables only. Mission narratives
> live in [CHANGELOG.md](CHANGELOG.md) and are never appended here. This file
> has a **hard line cap** pinned by `tests/test_docs_structure.py`; when it
> grows, prune it.
>
> This file is also the **single home for shipped-state counts** (tool counts,
> signal lists). Other docs link here instead of restating them.
>
> Companion to [SPEC.md](SPEC.md), [CHANGELOG.md](CHANGELOG.md),
> [ROADMAP.md](ROADMAP.md), [USERJOURNEY.md](../using/USERJOURNEY.md).
> Snapshot date: **2026-06-12**.

## TL;DR

**Pre-`v1` foundation — the product line is `v0.x`; the first-pipeline
restore point is tagged `v0.1.0` (formerly `v1.0.0`, retagged 2026-06-11).**
The ingest pipeline is operational across the four
observation sources (Health Connect, Garmin GDPR, Sleep as Android, BMT) plus
the MyFitnessPal nutrition-intake source; the DuckDB
warehouse holds ~3.5 years of data including the Garmin-only metrics that
motivated the project (HRV rMSSD overnight, stress, training load/readiness,
VO₂ max, skin temperature, hydration, sleep score, respiration). Re-ingest is
idempotent. On top of it: a Stage 2 engine of nine grounded signals behind a
deterministic evidence-admissibility layer, the six-tool Stage 3
analytical set with session research trace + audit skill, PubMed literature
grounding, agent-mediated profile capture, usable nutrition/supplement intake
dimensions, and the session-log substrate with a hardened cheap-model
live-trial path. CI runs all quality gates (tests, ruff, mypy, lockfile, data
guard) on every push. Drive upload is **opt-in**, never automatic. `v1.0.0` is
reserved for a coherent user-facing product across all four stages.

## Shipped surface — the counts live here

### Stage 2 signals (nine registered)

| Signal | Family | Answers |
|---|---|---|
| `resting_hr_status` | status | "What is my resting HR right now, and can I trust it?" |
| `resting_hr_trend` | trend | "Is my resting HR going up / down / flat recently?" |
| `steps_trend` | trend | "Are my daily steps trending?" (never imputes missing days) |
| `weight_trend` | trend | "Is my weight rising / falling / flat?" (carry-forward flagged) |
| `sleep_deep_pct_baseline` | baseline | "Is my latest deep-sleep % below my **own** recent normal?" |
| `hrv_change_around_date` | change | "Did my overnight HRV shift after a date I name?" |
| `supplement_intake_adherence` | status | "How consistently have I logged a supplement I name?" |
| `nutrition_intake_trend` | trend | "Is my logged nutrient/energy field trending?" (never imputes) |
| `bmi` | status | First cross-domain signal: declared height + usable weight via the input-resolution seam. |

All are descriptive/comparative only — no reference ranges, no diagnosis, no
significance, no causation. They return explicit stale / unavailable /
insufficient-data states instead of a misleading answer. The first eight are
exposed one-to-one as MCP signal tools; `bmi` is engine-registered.

### Stage 3 analytical tools (six — `engine.list_analytical_tools()` returns exactly these)

`change_point` (level-shift detection), `smoothed_average` (trailing smoothed
pattern), `correlate` (pre-registered, caller-declared whole-day-lagged
Spearman *association*; `N_eff`-corrected band; no p-value, no "significant"),
`rolling_mean` (declared moving-window summary with visible
coverage/imputation), `paired_t_test` (declared before/after anchor-date
paired difference; **not** a significance test), `condition_paired_t_test`
(declared **condition-label** paired difference over off-vs-on declared
episodes of one operator's series; one off/on pair per usable episode, the
label is operator-declared and only splits the windows; **not** a significance
test, names no cause). Every tool passes the admissibility gate before
computation and returns the mandatory result envelope (estimate + validity
metadata + closed `ConfoundKey` checklist) or a first-class refusal. Operative
rules: [`src/premura/engine/CONTRACT.md`](../../src/premura/engine/CONTRACT.md).

### MCP surfaces

- **Default agent surface (`premura-mcp`) — twenty-three tools:** 2
  catalog/summary (`list_metrics`, `metric_summary`), 8 signal-backed (table
  above), 2 profile-capture (`profile_context_supported_fields`,
  `profile_context_record`), 6 analytical, 3 session research trace
  (`research_trace_open`, `research_trace_mark_surfaced`,
  `research_trace_disclosure`), 2 PubMed (`pubmed_search` — candidates only,
  never citeable; `pubmed_fetch` — the only citeable record). No tool on this
  surface reads `hp.*` directly; the trace tools read only derived `trace.*`
  rows; the PubMed tools reach only the literature. Signal tools return the
  four-state envelope (`available` / `missing_input` / `stale_input` /
  `insufficient_data`) with a structured `missing_input` report a caller can
  branch on.
- **Operator surface (`premura-mcp-operator`) — twenty-four tools:** all
  default tools plus `query_warehouse` (raw SQL escape hatch, no Stage 2
  guarantees). Requires explicit launch acknowledgment (`--ack` /
  `PREMURA_OPERATOR_ACK`).

The pinned inventory test is `tests/test_mcp_server.py`.

### Foundations under the tools

- **Input-resolution seam**: `resolve_dependency` + `@resolver(domain=...)`;
  all four `SEMANTIC_DOMAINS` (`observation_history`, `profile_context`,
  `nutrition_intake`, `supplement_intake`) have concrete resolvers; a declared
  dependency with no matching fresh row resolves to an explicit non-usable
  outcome, never a cross-domain substitute.
- **Evidence admissibility**: deterministic `evaluate_evidence` over a closed
  `QuestionType` vocabulary with per-family freshness/sufficiency policies.
- **Session research trace**: append-only `trace.*` ledger at the MCP boundary;
  measured "K findings among N unique hypotheses" disclosure; consumer surface
  is the [audit-consumer contract](../building/architecture/AUDIT_CONSUMER_CONTRACT.md),
  read by the research-trace-audit skill
  (`src/premura/skills/research-trace-audit/`).
- **Session-log substrate + live trial**: local session-log store, contract
  checker, sandbox runner, deterministic grader, hardened local-only
  cheap-model live-trial seam (`live_trial` marker, never in CI). The trial
  now has two tiers in the codebase: the shipped constrained one-shot floor,
  and a multiturn tool-loop tier **in progress on the
  `tool-loop-live-trial-tier-01KTVG26` mission lanes (not yet merged)** —
  detail in `kitty-specs/tool-loop-live-trial-tier-01KTVG26/`. Two opt-in
  post-run steps now stand on the recorded session (both default OFF, both
  guarded so failure never flips the verdict): the **AI judge** assesses the
  operator's process against a versioned rubric into `log_judgment`, and the
  **improvement hook** consumes those judgments to derive durable proposals into
  `log_improvement` via a versioned playbook (it proposes, never acts) — both
  merged in `v0.4.0`. A **synthetic fixture auto-generator**
  (`premura.harness.fixture_gen`, runnable as `python -m premura.harness.fixture_gen`)
  fabricates fresh, never-seen synthetic vendor fixtures (CSV + grader-only
  manifest) deterministically from a seed — canonical metrics drawn from the
  committed registry, byte-identical per seed, recognized synthetic by the harness's
  persistence gate via a writer-controlled marker (additive, not a loosening) — so
  the harness is no longer limited to its two handwritten fixtures (merged in
  `v0.4.0`). The harness now grades a **second task kind, analyze-and-answer**
  (`premura.harness.answer_task`, runnable as `python -m premura.harness.answer_task`):
  over a deterministically seeded synthetic warehouse an operator answers a question
  through a bounded engine-backed analytical surface (no connection/path/SQL), and a
  deterministic grader recomputes ground truth itself to band honesty (no forbidden
  statistical claims), grounding, and refusal fidelity; the exchange is captured
  through the sole-writer session log and a scoreboard line under the open
  `analyze_answer` tier — one worked question-kind (`level_shift`) behind an
  add-a-kind registry, with the real-model analyze operator and cross-session
  aggregation named-deferred (merged in `v0.4.0`).
- **Runtime build-and-use boundary**: an agent may build a parser and use it
  immediately on the operator's own data with no reviewer; only a
  contribute-back PR is reviewed. Pinned by
  `tests/test_doctrine_build_and_use.py`.

## What's working end-to-end

| Component | State | Evidence |
|---|---|---|
| Warehouse schema (`hp.*`, `trace.*`) | ✅ | Migrations 001–005; observation/note, profile/intake, and trace tables; 191 seeded metrics; FK-safe auto-seed for unknown metric IDs. |
| Health Connect parser | ✅ | ~900k rows from a real ~200 MB v20 export in ~13 s parse+load. |
| Garmin GDPR parser | ✅ | UDS, sleepData, healthStatus, BP, hydration, training load/readiness, max-met, summarizedActivities; unknown filenames surfaced in `ingest_run.notes`. |
| Sleep as Android parser | ✅ | Synthetic-fixture tests; DST-safe per-minute actigraphy walk. |
| BMT parser | ✅ | Long/wide format detection; per-row units; custom metrics → `bmt_custom:*`. |
| MyFitnessPal intake parser | ✅ | First real vendor intake source: per-meal nutrition aggregates → intake seam (`hpipe ingest --source mfp`); exercise/measurement columns surfaced as declared gaps, never observation rows. |
| Loader (batch insert) | ✅ | Polars→DuckDB set-based insert; native-key + cross-source priority dedupe. |
| CLI (`hpipe`) | ✅ | `bootstrap`, `ingest`, `inspect` (read-only routing preview), `status`, `export`, `upload`, `doctor` (incl. age-key + backup round-trip checks), `gc` (`--dry-run`, opt-in `--raw`), `run-monthly`, launchd install/uninstall, `install-skills`, `profile-fields` / `profile-record`. |
| Idempotency | ✅ | sha256 skip in `hp.ingest_run` + `dedupe_key UNIQUE` + intra-batch dedupe. |
| Export artifact encryption | ✅ | Live round-trip verified 2026-05-21; per-test keypair regression suite; `doctor` re-proves the key/recipients pair on demand. |
| Drive upload (opt-in) | ⚠️ Code complete, not auto | `hpipe upload` runs only on explicit invocation. |
| launchd monthly run | ✅ | `com.nbrandizzi.premura.monthly` bootstrapped and verified 2026-05-21. |
| CI quality gates | ✅ | GitHub Actions on every push/PR: pytest (default suite), `ruff check`, `ruff format --check`, `mypy src/` (clean), `uv lock --check`, tracked-data guard. |
| Tests | ✅ | 1,044 default-suite tests green in CI (the `regression` / `live_trial` marked tests run locally only, by design). |

## Warehouse contents (shape illustration, one operator's run)

Run `uv run hpipe status` for live numbers. `hp.fact_measurement` coverage:
heart_rate, spo2, resting_hr, hrv_rmssd_overnight (Garmin-only), stress,
resp_rate, training_readiness, training_load, sleep_rating, sleep_deep_pct,
skin_temperature, intensity_minutes, weight, hydration, bmr, bp_systolic /
bp_diastolic, bmt_custom:hips/waist/neck, height, vo2_max.
`hp.fact_interval`: steps, distance, total_kcal, sleep_stage,
exercise_session, sleep_session, daily_wellness, active_kcal.

## Calibration vs SPEC §3 (Functional Requirements)

| FR | Met? | Notes |
|---|:---:|---|
| FR-1 HC ingestion | ✅ | Verified against a real `health_connect_export.db`. |
| FR-2 Garmin GDPR | ✅ | All per-source metrics appear at least once. |
| FR-3 Sleep as Android | ✅ | Synthetic fixtures pass; live-SAA exercise dropped from v1 scope. |
| FR-4 BMT config-driven units | ✅ | Long format per-row units; wide-format fallback respects config. |
| FR-5 Dedupe within + across | ✅ | Re-ingest → 0 inserted; lower-priority overlaps skipped. |
| FR-6 `age` round-trip | ✅ | Live 2026-05-21 + regression suite + `doctor` round-trip check. |
| FR-7 `rclone` upload + verify | ⏳ (scope change) | Upload is opt-in, not part of `run-monthly`. |
| FR-8 launchd | ✅ | Verified 2026-05-21; plist render + `plutil -lint` tested. |
| FR-9 Idempotency by sha256 | ✅ | Second pass returns `rows_inserted=0`. |
| FR-10 History preservation | ✅ | Append-only; `ingest_batch` (ULID) on every row. |

## Known limitations

- **HC HR-series uniqueness collisions**: ~3 sibling rows share
  `parent_uuid + epoch_millis`; deduped in-batch, invisible in stats. Cosmetic.
- **Wide-format BMT without `Time`**: timestamps land at 00:00:00 local.
- **No FIT-file (per-activity stream) ingestion** — out of scope for v1.

## Setup and operations

`uv run hpipe bootstrap` prepares and verifies a fresh clone (environment +
bundled skills; setup-only — it never ingests, uploads, or touches the
warehouse). Day-to-day runbook: [OPERATIONS.md](../using/OPERATIONS.md).

## Where the detail lives

- Mission-by-mission narratives: [CHANGELOG.md](CHANGELOG.md)
- Stage boundaries and tool semantics: [STAGES.md](../building/architecture/STAGES.md)
- Engine rules (what Stage 2/3 may claim): [`src/premura/engine/CONTRACT.md`](../../src/premura/engine/CONTRACT.md)
- Profile/intake meaning contract: [PROFILE_AND_INTAKE_CONTRACT.md](../building/architecture/PROFILE_AND_INTAKE_CONTRACT.md)
- Intake-dimension recipe: [INTAKE_DIMENSIONS.md](../building/architecture/INTAKE_DIMENSIONS.md)
- Trace consumer surface: [AUDIT_CONSUMER_CONTRACT.md](../building/architecture/AUDIT_CONSUMER_CONTRACT.md)
- Design decision notes: [docs/building/adr/](../building/adr/)
