# premura — User Journey

> Status: authoritative. Source of truth for the intended human experience over time.
>
> Companion to [SPEC.md](SPEC.md) (what the system must do), [ARCHITECTURE_HISTORY.md](../architecture/ARCHITECTURE_HISTORY.md) (how it was built), [STATUS.md](../operations/STATUS.md) (what works today), and [ROADMAP.md](ROADMAP.md) (what's next).
> This document is the source of truth for **the human experience over time**.

## Persona

**Nicolò** — single user, single subject, single operator. EU resident (GDPR jurisdiction applies). Wears a Garmin watch daily, logs body measurements in BMT, sleeps tracked by Sleep as Android, Android phone with Health Connect installed. Comfortable on the macOS terminal; runs Python and SQL day-to-day; familiar with `age`, `rclone`, and DuckDB. Does NOT want to: build an Android app, run a server, pay a SaaS, depend on a third-party bridge that might disappear or be acquired.

Wears four hats over the system's lifetime:

| Hat | When | What they care about |
|---|---|---|
| **Subject** | Continuously, passively | Their data exists and is accurate |
| **Operator** | Once per month, ~10 min | Pipeline runs cleanly, low ceremony |
| **Analyst** | Anytime, ad-hoc | Fast SQL/Polars over years of metrics |
| **Recovery actor** | Rarely, on lost hardware | Encrypted Drive backups + the age key are enough to rebuild |

## Pain points this system solves

1. **Garmin gatekeeps the data** — HRV, respiratory rate, stress, Body Battery, training load: never bridged to Health Connect by Garmin's policy.
2. **Health Connect's schema has gaps** — no Body Battery, no waist/hip circumference, no training load.
3. **Body Measurement Tracker only bridges weight + height** — body fat %, lean mass, waist measurements stay trapped in the app.
4. **No single place to query everything** — Garmin Connect, HC, Sleep as Android, BMT each have their own UI and silo.
5. **No durable backup** — if the phone dies, years of training and sleep data could be gone.
6. **Vendor lock-in risk** — every cloud health platform is one acquisition or policy change away from a forced migration.

## Journey 1 — First-time setup (~30 minutes, once)

### Goal
Get to "the pipeline can run end-to-end" with no remaining manual steps for the monthly path.

### Steps

1. **Clone / open the repo** at `~/repos/personal/premura/`.
2. **Run bootstrap**: `bash ops/bootstrap.sh`. This:
   - `brew install age rclone`
   - `uv sync` to install Python deps
   - Creates `~/.config/premura/` (mode 700)
   - Generates an `age` keypair at `~/.config/premura/age.key` (mode 600), writes the public recipient to `~/.config/premura/recipients.txt`
   - **Prompts: "Back up `~/.config/premura/age.key` to your password manager now. WITHOUT IT YOUR BACKUPS ARE UNRECOVERABLE. [press Enter when done]"**
   - Walks user through `rclone config` for a `gdrive` remote with `drive.file` scope
3. **Run `hpipe doctor`** — verifies `age`, `rclone`, `uv`, DuckDB warehouse path, age key fingerprint, rclone remote reachability. All green = ready.
4. **First HC ingest** (sanity check): drop the latest HC export (e.g. `~/Downloads/health_connect_export.db`) into `data/inbox/`, run `hpipe ingest --source hc`. Expect hundreds of thousands of rows + a printed coverage summary by metric.
5. **Install launchd agent**: `hpipe install-launchd`. The agent is now scheduled for the 1st of every month at 10:00 local.
6. **(Optional) Open your project wiki hub page** — if you keep a personal knowledge wiki, add a hub page for this project per PLAN §"Wiki integration".

### Success criteria
- `hpipe status` shows non-zero row counts.
- `launchctl list | grep premura` shows the agent loaded.
- A test row from a known weight measurement queries correctly: `SELECT ts_utc, value_num, unit FROM hp.fact_measurement WHERE metric_id='weight' ORDER BY ts_utc DESC LIMIT 5;`

### Common stumbles to anticipate
- Forgetting to back up the `age.key`. The bootstrap script blocks until the user types `confirmed`.
- Picking `drive` (full) instead of `drive.file` (app-sandboxed) scope during `rclone config`. The bootstrap prompts explicitly.
- Python version drift if uv picks a different interpreter than expected. The `.python-version` file pins to 3.11.

## Journey 2 — Monthly run (~10 minutes user time, every month)

### Trigger
On the 1st at 10:00 local, launchd fires `hpipe run-monthly`. A macOS notification appears: *"Premura: request fresh Garmin GDPR dump, drop SAA + BMT exports in `data/inbox/`, then `touch data/inbox/.ready`."*

### Steps the user performs

1. **Garmin GDPR request** (~1 min): open `account.garmin.com/datamanagement/exportdata/`, click "Request Data Export". Email arrives within 24–48 h (sometimes up to 30 days for old accounts). When the email arrives, download the zip — **it expires in 3 days**.
2. **Sleep as Android export** (~1 min): open SAA → Settings → Backup → Export to file → save the CSV to `~/repos/personal/premura/data/inbox/`.
3. **Body Measurement Tracker export** (~1 min): open BMT → Settings → Export → CSV → save to `data/inbox/`.
4. **Drop Garmin zip into inbox**: move the downloaded zip to `data/inbox/`.
5. **Health Connect**: nothing to do — HC's own auto-export deposits a fresh `.db` daily into a Drive folder; the pipeline pulls the latest before processing.
6. **Mark ready**: `touch data/inbox/.ready`.
7. **Wait**: pipeline polls hourly. On next tick it ingests everything, runs cross-source dedupe, snapshots the warehouse, encrypts with `age`, uploads to `gdrive:/backups/premura/YYYY/MM/`, garbage-collects local exports older than 3 months, and emits a "Done: N rows added" notification.

### Steps the system performs (invisible to user)

```
ingest hc      → ingest garmin → ingest saa → ingest bmt
   ↓
dedupe (cross-source priority)
   ↓
write to hp.fact_measurement + hp.fact_interval (idempotent)
   ↓
export snapshot  →  age encrypt  →  rclone upload  →  verify lsl  →  notify
```

### Success notification
*"Premura 2026-05: +X rows · HRV+Y · HR+Z · sleep+W. Backup at gdrive:/backups/premura/2026/05/"*

### Failure modes
- **No `.ready` after 7 days**: agent renotifies and exits. No data ingested. User must re-trigger when ready.
- **Garmin zip never arrived**: skip Garmin this month; HC + SAA + BMT still get ingested. Next month's Garmin GDPR will cover the gap (Garmin always exports a rolling window).
- **rclone auth expired**: pipeline fails at upload step. Notification: *"Upload failed: rclone reauth needed. Run `rclone config reconnect gdrive:`"*. The warehouse is already updated locally — re-run `hpipe upload` after fixing auth.
- **Disk full**: pipeline halts before encrypting. `hpipe gc --keep 1` frees ~2 months of local exports.

## Journey 3 — Ad-hoc analysis (anytime)

### Goal
Answer a personal question against years of unified data.

### Example questions the warehouse should make trivial

| Question | Sketch |
|---|---|
| "How does my HRV correlate with deep-sleep minutes over the last 90 days?" | Join `fact_measurement WHERE metric_id='hrv_rmssd_overnight'` with `fact_interval WHERE metric_id='sleep_stage' AND value_text='deep'` on `date_trunc('day', ts_utc) = date_trunc('day', start_utc)`. |
| "What was my weight trajectory during the January-to-April 2026 cut?" | `SELECT date_trunc('week', ts_utc), avg(value_num) FROM fact_measurement WHERE metric_id='weight' AND ts_utc BETWEEN '2026-01-01' AND '2026-05-01' GROUP BY 1 ORDER BY 1;` |
| "On which days did Body Battery cross 50 by 09:00 vs. 12:00?" | Filter `metric_id='body_battery'` to first reading per day in each hour window. |
| "Which weeks had the highest avg respiratory rate? Were those also high-stress weeks?" | Two CTEs, weekly avg per metric, joined on week. |

### Tools the user picks
- Quick: `duckdb data/duck/health.duckdb` in the shell.
- Notebook: `import duckdb; con = duckdb.connect("data/duck/health.duckdb", read_only=True)` then Polars/Plotly.
- Dashboard (deferred to v2): export to Parquet, point Grafana/Metabase at it.

### Constraint
Read-only access during analysis — never let analytics writes touch the warehouse. The pipeline owns writes; analysis is `read_only=True` by convention.

## Journey 4 — Catastrophic recovery (rare, critical)

### Scenario
The Mac dies. The user buys a new one.

### Steps
1. New Mac: `brew install age rclone uv`.
2. Restore `~/.config/premura/age.key` from password manager (this is the single secret without which the backups are dead).
3. `rclone config` a fresh `gdrive` remote with `drive.file` scope.
4. `git clone` this repo to a working directory of your choice.
5. `rclone copy gdrive:/backups/premura/$(date +%Y/%m)/ data/exports/restore/` — fetch the latest encrypted snapshot.
6. `age -d -i ~/.config/premura/age.key data/exports/restore/health.duckdb.age > data/duck/health.duckdb`.
7. `hpipe doctor` to verify.
8. Resume monthly cadence.

**Time to recovery**: roughly 30 minutes plus Drive download time. **Data lost**: at most one monthly window if recovery happens before the next scheduled run.

### What recovery does NOT depend on
- Garmin Connect being online
- Sleep as Android still existing
- Health Connect schema being unchanged
- The Apple ID, the Google Account, or any single SaaS

The encrypted Drive snapshot + the age key + this repo are sufficient. That's the durability story.

## Anti-journeys (we deliberately don't optimize for these)

- **"Show me my data on my phone"** — out of scope. Use Garmin Connect / HC apps; this system is for the analyst hat.
- **"Push corrections back into Health Connect"** — out of scope. HC has no documented import path; we'd need an Android app.
- **"Real-time alerts"** — out of scope. Monthly cadence by design; alerting belongs to Garmin Connect.
- **"Share my data with X"** — out of scope. Single-user system; sharing means custom decrypt + extract per ask.
- **"Sync between two Macs"** — out of scope for v1. The encrypted Drive blob is the rendezvous; pull manually if needed.

## Touchpoints summary

| Touchpoint | Frequency | User effort |
|---|---|---|
| `bash ops/bootstrap.sh` | once | 15 min |
| Password-manager backup of age.key | once | 2 min |
| `rclone config` for gdrive | once | 5 min |
| `hpipe install-launchd` | once | <1 min |
| Garmin GDPR request → download | monthly | 2 min request + wait |
| SAA export → drop in inbox | monthly | 1 min |
| BMT export → drop in inbox | monthly | 1 min |
| `touch data/inbox/.ready` | monthly | <1 min |
| Read success notification | monthly | passive |
| Ad-hoc query | as needed | varies |
| Catastrophic recovery | rare | 30 min + bandwidth |

Total recurring user-time burden: **~5 minutes per month** after the first setup. Everything else is automated or already-in-the-app behaviour.

## Implicit user contract

By using this system the user accepts:

1. **They are the custody-of-record holder of the `age` private key.** No vendor, no recovery service, no key escrow exists. Lose the key → lose the encrypted history.
2. **Monthly cadence is good enough.** No live insight from the warehouse.
3. **Garmin GDPR exports are manual.** No realistic way to automate the request-click without violating Garmin's ToS.
4. **The pipeline can drift if a source's format changes.** Defensive parsers buy time but not invulnerability. The fix is "open an issue, write a parser patch, ingest catches up."
5. **The project wiki hub page (if maintained) is the canonical project record.** When in doubt about design intent, the wiki is the answer, not buried commit messages.
