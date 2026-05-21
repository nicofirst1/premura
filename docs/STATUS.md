# premura — Current Status

> Companion to [SPEC.md](SPEC.md), [PLAN.md](PLAN.md), [USERJOURNEY.md](USERJOURNEY.md), [ROADMAP.md](ROADMAP.md).
> Snapshot date: **2026-05-20**.

## TL;DR

The four-source ingest pipeline is **operational**. The DuckDB warehouse contains ~3.5 years of HC data plus the full set of Garmin-only metrics that PLAN.md flagged as the original motivation: **HRV rMSSD overnight, stress, training load, training readiness, VO₂ max, skin temperature, hydration, sleep score, respiration**. Re-ingest of any source is idempotent.

**Policy change (2026-05-20)**: as the project starts looking like a real application for others, Drive upload is now **opt-in**, not part of the automated monthly run. `hpipe run-monthly` ends with the encrypted `.age` artifact sitting in `data/exports/YYYY-MM/`; the user decides whether to `hpipe upload` (or hand the file off to another sync mechanism). The `age` private key is stored locally by default, with a password-manager recipe (Bitwarden as a reference) in [`ops/bootstrap.sh`](../ops/bootstrap.sh).

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
| Encryption (always-on) | ⚠️ Code complete, not live | `age` shells out; round-trip not exercised against a real key this session. |
| Drive upload (now OPT-IN, not auto) | ⚠️ Code complete, not live | `hpipe upload` only runs on explicit invocation. `run-monthly` no longer pushes to Drive — it stops after the encrypted artifact lands locally. |
| Launchd plist | ⚠️ Renders OK | Not yet `bootstrap`'d on a host. |
| Tests | ✅ | 17/17 pytest pass, incl. a real-data HC regression that round-trips ~900k rows. |

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
| FR-2 Garmin GDPR | ✅ | All metrics listed in PLAN's per-source table now appear at least once — see counts above. |
| FR-3 Sleep as Android | ✅ | Parser + unit tests pass; not yet exercised on a real export this session. |
| FR-4 BMT with config-driven units | ✅ | Long-format file uses per-row units; wide-format fallback still respects `parsers.bmt.weight_unit` config. |
| FR-5 Dedupe within + across | ✅ | Demonstrated: re-ingest same file → 0 inserted; loader skips lower-priority overlapping rows. |
| FR-6 `age` round-trip | ⏳ | `encrypt.py` is in place; not exercised this session. |
| FR-7 `rclone` upload + verify | ⏳ (scope change) | `upload.py` in place but **upload is now opt-in, not part of `run-monthly`**. User decides when (and whether) to push. |
| FR-8 launchd | ⏳ | `install-launchd` writes the plist; not yet `launchctl bootstrap`'d. |
| FR-9 Idempotency by sha256 | ✅ | Loader returns `rows_inserted=0` on second pass. |
| FR-10 History preservation | ✅ | Append-only; `ingest_batch` (ULID) tagged on every row. |

## Known limitations

- **Health Connect HR-series uniqueness collisions**: parser emits ~3 rows that share `parent_uuid + epoch_millis` with siblings; Polars dedupes them before insert (in-batch). Counted as `rows_inserted` minus actual table delta — currently invisible in stats. Cosmetic only.
- **Wide-format BMT** with no `Time` column: timestamps land at 00:00:00 local; not a regression vs PLAN but worth flagging.
- **No FIT-file (per-activity stream) ingestion** — PLAN §"Out of scope (v1)" calls this out explicitly.
- **`fact_interval` has no `unit` column**; we carry it in memory only. Fine for now; would need a migration if downstream queries want it.

## How to use it today

```bash
# put inputs in data/inbox/ (HC .db, Garmin GDPR .zip, SAA/BMT .csv), then:
uv run hpipe ingest                      # autodiscovers all four sources
uv run hpipe status                      # current row counts
uv run hpipe export --month 2026-05      # snapshot + tarball + age-encrypt
uv run hpipe upload --month 2026-05      # rclone to gdrive:<your-configured-remote-path>/2026/05/
uv run hpipe doctor                      # preflight checks
uv run hpipe install-launchd             # macOS scheduled run on day 1 @ 10:00
```

Direct SQL:
```bash
duckdb -readonly data/duck/health.duckdb
```
