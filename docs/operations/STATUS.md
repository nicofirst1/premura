# premura — Current Status

> Status: live reference. Snapshot of what is true and shipped today.
>
> Companion to [SPEC.md](../product/SPEC.md), [ARCHITECTURE_HISTORY.md](../architecture/ARCHITECTURE_HISTORY.md), [USERJOURNEY.md](../product/USERJOURNEY.md), [ROADMAP.md](../product/ROADMAP.md).
> Snapshot date: **2026-05-26**.

## TL;DR

**v1 closed 2026-05-21 — tagged `v1.0.0`.** The four-source ingest pipeline is **operational**. The DuckDB warehouse contains ~3.5 years of HC data plus the full set of Garmin-only metrics that [ARCHITECTURE_HISTORY.md](../architecture/ARCHITECTURE_HISTORY.md) flagged as the original motivation: **HRV rMSSD overnight, stress, training load, training readiness, VO₂ max, skin temperature, hydration, sleep score, respiration**. Re-ingest of any source is idempotent.

**Policy change (2026-05-20)**: as the project starts looking like a real application for others, Drive upload is now **opt-in**, not part of the automated monthly run. `hpipe run-monthly` ends with the encrypted `.age` artifact sitting in `data/exports/YYYY-MM/`; the user decides whether to `hpipe upload` (or hand the file off to another sync mechanism). The `age` private key is stored locally by default, with a password-manager recipe (Bitwarden as a reference) in [`ops/bootstrap.sh`](../../ops/bootstrap.sh).

## Stage 2 / Stage 3 baseline (shipped after v1)

The first grounded analytical behavior now exists on top of the v1 ingest pipeline.

**Stage 2 — six grounded signals.** `src/premura/engine/` ships six freshness-aware answers over the user's own warehouse data (`descriptive_signals.py`, `comparative_signals.py`), registered through the static built-in module list and documented by `src/premura/engine/CONTRACT.md`:

| Signal | Family | Answers |
|---|---|---|
| `resting_hr_status` | status | "What is my resting HR right now, and can I trust it?" |
| `resting_hr_trend` | trend | "Is my resting HR going up / down / flat recently?" |
| `steps_trend` | trend | "Are my daily steps trending?" (never imputes missing days) |
| `weight_trend` | trend | "Is my weight rising / falling / flat?" (carry-forward flagged) |
| `sleep_deep_pct_baseline` | baseline | "Is my latest deep-sleep % below my **own** recent normal?" |
| `hrv_change_around_date` | change | "Did my overnight HRV shift after a date I name?" |

These are descriptive/comparative only — no reference ranges, no diagnosis, no statistical significance, no causation. They return explicit stale / unavailable / insufficient-data states instead of presenting a misleading answer. Profile-dependent answers (BMI, age-adjusted interpretation) remain deferred to issue `#6`.

**Stage 3 — two entrypoints, clean boundary.** `src/premura/mcp/` ships two entrypoints:

- **Default agent surface (`premura-mcp`)** — eight tools: two validity-gated catalog/summary helpers (`list_metrics`, `metric_summary`) that delegate entirely to the Stage 2 engine, plus the six signal-backed tools listed above. No tool on this surface reads `hp.*` directly; all catalog and signal access goes through the engine. This is the fully validity-gated default path.
- **Operator surface (`premura-mcp-operator`)** — all eight default tools plus `query_warehouse` (raw SQL escape hatch). Lower-guarantee: `query_warehouse` returns raw rows without Stage 2 validity, freshness, or imputation guarantees. Agent use requires explicit user approval, enforced by surface separation plus an explicit launch acknowledgment (`--ack` / `PREMURA_OPERATOR_ACK`) the operator entrypoint demands before exposing the raw-SQL tool.

The signal-backed tools return a structured payload whose `status` is `available` / `missing_input` / `stale_input` / `insufficient_data`. When an answer is unavailable the payload's `message` carries the signal's authored missing-input guidance, and `missing_input` / `stale_input` responses attach a structured `missing_input` report (`required_inputs` / `missing_inputs` / `stale_inputs`) a caller can branch on.

## What's working end-to-end

| Component | State | Evidence |
|---|---|---|
| Warehouse schema (`hp.*`) | ✅ | 5 tables, 43 seeded metrics, FK-safe auto-seed for unknown metric IDs (e.g. `bmt_custom:hips`). |
| Health Connect parser | ✅ | ~900k rows from a real ~200 MB v20 export in ~13 s parse+load. |
| Garmin GDPR parser | ✅ | Handles UDS, sleepData, healthStatusData, BloodPressureFile, HydrationLogFile, MetricsAcuteTrainingLoad, MetricsMaxMetData, TrainingReadinessDTO, summarizedActivities. Surfaces unknown filenames in `ingest_run.notes`. |
| Sleep as Android parser | ✅ | Synthetic-fixture tests; per-minute actigraphy walk with DST-safe wall-clock advancement. |
| BMT parser | ✅ | Detects long vs wide format from header. Long-format (current app) respects per-row `Unit`; custom metrics (`hips`, `waist`, `neck`, …) routed to `bmt_custom:*`. |
| Loader (batch insert) | ✅ | Polars→DuckDB temp-table registration, single `INSERT … SELECT … WHERE NOT EXISTS`. Native-key dedupe + cross-source priority dedupe done as set-based SQL. |
| CLI (`hpipe`) | ✅ | All 9 verbs surfaced: `ingest`, `status`, `export`, `upload`, `doctor`, `gc`, `run-monthly`, `install-launchd`, `uninstall-launchd`. |
| Idempotency | ✅ | sha256 skip in `hp.ingest_run`, plus `dedupe_key UNIQUE` + intra-batch Polars `.unique()`. |
| CSV autodiscovery | ✅ | Header-sniffs SAA vs BMT (no naming convention required). |
| Export artifact encryption | ✅ | Live round-trip verified 2026-05-21 against `~/.config/premura/age.key`; decrypted snapshot byte-identical to `data/duck/health.duckdb` (`diff` empty). Per-test keypair regression in `tests/test_encrypt_roundtrip.py`. |
| Drive upload (now OPT-IN, not auto) | ⚠️ Code complete, not live | `hpipe upload` only runs on explicit invocation. `run-monthly` no longer pushes to Drive — it stops after the encrypted artifact lands locally. |
| Launchd plist | ✅ | Bootstrapped 2026-05-21 (`com.nbrandizzi.premura.monthly`). `kickstart` fired the macOS notification, `run-monthly` reached the `_wait_for_ready` loop without ingesting (no `.ready`), exited cleanly on SIGTERM. Plist render covered by `tests/test_launchd_plist.py` (incl. `plutil -lint`). |
| Tests | ✅ | 134/134 pytest pass, incl. a real-data HC regression that round-trips ~900k rows, the FR-6 `age` round-trip suite, FR-8 plist render + `plutil -lint`, and full Stage 2 engine + Stage 3 signal-tool coverage (all six signal-backed tools exercised end-to-end through the public entrypoint). |

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
| FR-2 Garmin GDPR | ✅ | All metrics listed in `ARCHITECTURE_HISTORY.md`'s per-source table now appear at least once — see counts above. |
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
- **No FIT-file (per-activity stream) ingestion** — `ARCHITECTURE_HISTORY.md` marks this as out of scope for v1.
- **`fact_interval` has no `unit` column**; we carry it in memory only. Fine for now; would need a migration if downstream queries want it.

## Operations

See [OPERATIONS.md](OPERATIONS.md) for the current operator command surface and
day-to-day runbook.
