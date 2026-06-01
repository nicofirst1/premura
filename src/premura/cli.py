"""`hpipe` CLI — entry point for the premura pipeline.

Verbs: bootstrap, ingest, status, export, upload, run-monthly, doctor, gc,
install-launchd, uninstall-launchd, install-skills.
"""

from __future__ import annotations

import hashlib
import importlib.resources as resources
import json
import logging
import shutil
import sys
import tarfile
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated, Protocol

import typer
from jinja2 import Template
from rich.console import Console
from rich.table import Table

from . import skills
from .bootstrap import (
    ActionResult,
    BootstrapRun,
    SummaryStatus,
    run_bootstrap,
)
from .config import settings
from .mcp import server as mcp_server
from .ops import encrypt, notify, upload
from .parsers.bmt import BMTParser
from .parsers.garmin_gdpr import GarminGDPRParser
from .parsers.health_connect import HealthConnectParser
from .parsers.lab_pdf import LabPdfParser
from .parsers.sleep_as_android import SleepAsAndroidParser
from .store import duck
from .store.loader import already_ingested, load

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Personal health data warehouse.",
)
console = Console()
log = logging.getLogger("hpipe")

READY_TIMEOUT_DAYS = 7
READY_POLL_SECS = 3600  # 1 hour


class _Parser(Protocol):
    def parse(self, path: Path): ...


PARSER_FACTORY = Callable[[], _Parser]

PARSER_REGISTRY: dict[str, tuple[PARSER_FACTORY, str]] = {
    "hc": (HealthConnectParser, "health_connect"),
    "garmin": (GarminGDPRParser, "garmin_gdpr"),
    "saa": (SleepAsAndroidParser, "sleep_as_android"),
    "bmt": (BMTParser, "bmt"),
    "lab": (LabPdfParser, "lab_pdf"),
}


# ============================================================================
# ingest
# ============================================================================


@app.command()
def ingest(
    source: Annotated[str, typer.Option(help="hc | garmin | saa | bmt | lab | all")] = "all",
    path: Annotated[
        Path | None,
        typer.Argument(help="Override file path; defaults to autodiscovery in data/inbox/"),
    ] = None,
) -> None:
    """Parse one or more sources into the warehouse."""
    settings.ensure_dirs()
    conn = duck.initialize(settings.warehouse_path)
    try:
        if source == "all":
            for key in PARSER_REGISTRY:
                _ingest_one(conn, key, None)
        elif source in PARSER_REGISTRY:
            _ingest_one(conn, source, path)
        else:
            raise typer.BadParameter(f"unknown source: {source}")
    finally:
        conn.close()


def _ingest_one(conn, source_key: str, override_path: Path | None) -> None:
    parser_cls, _source_kind = PARSER_REGISTRY[source_key]
    candidate = override_path if override_path else _discover_input(source_key)
    if candidate is None:
        console.print(f"[yellow]no input found for {source_key}; skipping[/yellow]")
        return
    if not candidate.is_file():
        console.print(f"[red]{candidate} not found; skipping {source_key}[/red]")
        return

    parser = parser_cls()
    console.print(f"[cyan]parsing[/cyan] {source_key} :: {candidate.name}")
    t0 = time.time()
    batch = parser.parse(candidate)
    parse_dt = time.time() - t0

    if already_ingested(conn, batch.source_sha256):
        console.print(f"  [dim]sha256 {batch.source_sha256[:12]}… already ingested; skipping[/dim]")
        return

    t1 = time.time()
    stats = load(conn, batch)
    load_dt = time.time() - t1
    console.print(
        f"  parse {parse_dt:.1f}s • load {load_dt:.1f}s • "
        f"inserted={stats.rows_inserted:,} dup_skip={stats.rows_skipped_dup:,} "
        f"priority_skip={stats.rows_skipped_priority:,}"
    )


def _discover_input(source_key: str) -> Path | None:
    """Find the most recent file in data/inbox/ that matches the source.

    File-extension routing for .db (HC) and .zip (Garmin). For .csv we header-sniff
    because SAA and BMT both export CSVs with no agreed naming convention.
    """
    inbox = settings.inbox_dir
    if not inbox.is_dir():
        return None
    if source_key == "hc":
        candidates = sorted(inbox.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    elif source_key == "garmin":
        candidates = sorted(inbox.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    elif source_key in ("saa", "bmt"):
        csvs = sorted(inbox.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        candidates = [p for p in csvs if _csv_kind(p) == source_key]
    elif source_key == "lab":
        candidates = sorted(inbox.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    else:
        return None
    return candidates[0] if candidates else None


def _csv_kind(path: Path) -> str:
    """Return 'saa' or 'bmt' by sniffing the first line of a CSV.

    SAA headers always contain the literal tokens 'Id', 'Tz', 'From', 'To' on row one.
    Everything else is treated as BMT.
    """
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as f:
            first = f.readline()
    except OSError:
        return "bmt"
    cols = {c.strip() for c in first.split(",")}
    if {"Id", "Tz", "From", "To"}.issubset(cols):
        return "saa"
    return "bmt"


# ============================================================================
# status
# ============================================================================


@app.command()
def status() -> None:
    """Summary of ingest_run + row counts per metric."""
    if not settings.warehouse_path.exists():
        console.print("[yellow]warehouse does not exist yet — run `hpipe ingest` first[/yellow]")
        raise typer.Exit(code=0)
    conn = duck.connect(settings.warehouse_path, read_only=True)
    try:
        runs = conn.execute(
            """
            SELECT batch_id, source_kind, started_at, finished_at, rows_inserted, rows_skipped_dup
            FROM hp.ingest_run
            ORDER BY started_at DESC
            LIMIT 10
            """
        ).fetchall()
        tbl = Table(title="Recent ingest runs")
        for col in ("batch_id", "source_kind", "started_at", "finished_at", "ins", "dup"):
            tbl.add_column(col)
        for r in runs:
            tbl.add_row(
                (str(r[0])[:8] + "…") if r[0] else "—",
                str(r[1]),
                str(r[2]),
                str(r[3]) if r[3] else "—",
                f"{r[4] or 0:,}",
                f"{r[5] or 0:,}",
            )
        console.print(tbl)

        rows = conn.execute(
            """
            SELECT metric_id, COUNT(*) AS n,
                   MIN(ts_utc)::VARCHAR AS earliest,
                   MAX(ts_utc)::VARCHAR AS latest
            FROM hp.fact_measurement
            GROUP BY metric_id
            ORDER BY n DESC
            """
        ).fetchall()
        m_tbl = Table(title="hp.fact_measurement")
        for col in ("metric_id", "rows", "earliest", "latest"):
            m_tbl.add_column(col)
        for r in rows:
            m_tbl.add_row(r[0], f"{r[1]:,}", r[2] or "—", r[3] or "—")
        console.print(m_tbl)

        rows = conn.execute(
            """
            SELECT metric_id, COUNT(*) AS n
            FROM hp.fact_interval
            GROUP BY metric_id
            ORDER BY n DESC
            """
        ).fetchall()
        i_tbl = Table(title="hp.fact_interval")
        for col in ("metric_id", "rows"):
            i_tbl.add_column(col)
        for r in rows:
            i_tbl.add_row(r[0], f"{r[1]:,}")
        console.print(i_tbl)
    finally:
        conn.close()


# ============================================================================
# export (snapshot + raw tarball)
# ============================================================================


@app.command()
def export(
    month: Annotated[str, typer.Option(help="YYYY-MM, defaults to current month")] = "",
) -> None:
    """Snapshot the warehouse + tarball staged raws, encrypt with age."""
    settings.ensure_dirs()
    if not month:
        month = datetime.now().strftime("%Y-%m")
    out_dir = settings.exports_dir / month
    out_dir.mkdir(parents=True, exist_ok=True)
    db_src = settings.warehouse_path
    if not db_src.exists():
        console.print(f"[red]no warehouse at {db_src}[/red]")
        raise typer.Exit(code=1)

    # 1. warehouse snapshot
    db_snap = out_dir / "health.duckdb"
    shutil.copy2(db_src, db_snap)

    # 2. raw tarball
    tar_path = out_dir / "raw.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        if settings.raw_dir.exists():
            tar.add(settings.raw_dir, arcname=".")

    # 3. encrypt both
    if not encrypt.is_available():
        console.print("[red]age CLI not installed — run ops/bootstrap.sh first[/red]")
        raise typer.Exit(code=1)
    if not settings.age_recipients_file.exists():
        console.print(f"[red]recipients file missing: {settings.age_recipients_file}[/red]")
        raise typer.Exit(code=1)
    db_enc = out_dir / "health.duckdb.age"
    tar_enc = out_dir / "raw.tar.gz.age"
    encrypt.encrypt_file(db_snap, db_enc, recipients_file=settings.age_recipients_file)
    encrypt.encrypt_file(tar_path, tar_enc, recipients_file=settings.age_recipients_file)

    # 4. manifest
    manifest = {
        "month": month,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "age_recipient": encrypt.recipient_fingerprint(settings.age_recipients_file),
        "files": [
            {
                "name": db_enc.name,
                "size_bytes": db_enc.stat().st_size,
                "sha256": _sha256_file(db_enc),
            },
            {
                "name": tar_enc.name,
                "size_bytes": tar_enc.stat().st_size,
                "sha256": _sha256_file(tar_enc),
            },
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # 5. wipe cleartext copies
    for p in (db_snap, tar_path):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    console.print(f"[green]exported[/green] → {out_dir}")


# ============================================================================
# upload
# ============================================================================


def _do_upload(month: str) -> None:
    if not month:
        month = datetime.now().strftime("%Y-%m")
    local_dir = settings.exports_dir / month
    if not local_dir.is_dir():
        console.print(
            f"[red]no export dir {local_dir} — run `hpipe export --month {month}` first[/red]"
        )
        raise typer.Exit(code=1)
    if not upload.is_available():
        console.print("[red]rclone not installed[/red]")
        raise typer.Exit(code=1)
    year, mo = month.split("-")
    dst = upload.upload_directory(
        local_dir,
        remote=settings.rclone_remote,
        remote_prefix=settings.rclone_backup_prefix,
        year=year,
        month=mo,
    )
    console.print(f"[green]uploaded[/green] → {dst}")
    items = upload.list_remote(dst)
    for size, name in items:
        console.print(f"  {size:>12,} bytes  {name}")


@app.command(name="upload")
def upload_cmd(
    month: Annotated[str, typer.Option("--month", help="YYYY-MM")] = "",
) -> None:
    """rclone copy the month's encrypted artifacts to the configured remote."""
    _do_upload(month)


# ============================================================================
# doctor
# ============================================================================


@app.command()
def doctor() -> None:
    """Environment + config preflight."""
    rows: list[tuple[str, str, str]] = []

    def add(label: str, ok: bool, detail: str = "") -> None:
        rows.append((label, "[green]ok[/green]" if ok else "[red]FAIL[/red]", detail))

    add("age", encrypt.is_available(), shutil.which("age") or "")
    add("rclone", upload.is_available(), shutil.which("rclone") or "")
    add("uv", shutil.which("uv") is not None, shutil.which("uv") or "")
    add("warehouse file", settings.warehouse_path.exists(), str(settings.warehouse_path))
    add("age key", settings.age_key_file.exists(), str(settings.age_key_file))
    add(
        "age recipients",
        settings.age_recipients_file.exists(),
        str(settings.age_recipients_file),
    )
    fp = (
        encrypt.recipient_fingerprint(settings.age_recipients_file)
        if settings.age_recipients_file.exists()
        else None
    )
    add("age recipient fp", bool(fp), fp or "")
    if upload.is_available():
        add(
            "rclone remote",
            upload.remote_reachable(settings.rclone_remote),
            f"{settings.rclone_remote}:",
        )
    target = settings.data_dir.parent if settings.data_dir.exists() else Path.home()
    free_gb = shutil.disk_usage(target).free / 1e9
    add("free disk", free_gb > 1.0, f"{free_gb:.1f} GB")

    tbl = Table()
    for col in ("check", "status", "detail"):
        tbl.add_column(col)
    for label, st, detail in rows:
        tbl.add_row(label, st, detail)
    console.print(tbl)
    if any("FAIL" in s for _, s, _ in rows):
        raise typer.Exit(code=1)


# ============================================================================
# gc
# ============================================================================


@app.command()
def gc(
    keep: Annotated[int, typer.Option("--keep", help="months of exports to keep locally")] = 3,
) -> None:
    """Drop local export dirs older than N months."""
    if not settings.exports_dir.exists():
        console.print("[yellow]no exports dir[/yellow]")
        return
    cutoff = time.time() - keep * 31 * 24 * 3600
    removed = 0
    for child in sorted(settings.exports_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.stat().st_mtime < cutoff:
            shutil.rmtree(child)
            removed += 1
            console.print(f"  removed {child.name}")
    console.print(f"[green]gc removed {removed} dir(s)[/green]")


# ============================================================================
# run-monthly
# ============================================================================


@app.command(name="run-monthly")
def run_monthly() -> None:
    """Full monthly pipeline. Entry point for the launchd agent."""
    settings.ensure_dirs()
    notify.notify(
        title="Premura",
        body=(
            "Request fresh Garmin GDPR export at account.garmin.com/datamanagement/, "
            "drop SAA + BMT exports in data/inbox/, then `touch data/inbox/.ready`."
        ),
    )
    if not _wait_for_ready():
        notify.notify(
            title="Premura",
            body=f".ready not seen in {READY_TIMEOUT_DAYS} days; aborting this month.",
        )
        raise typer.Exit(code=0)

    try:
        ingest("all", None)
        month = datetime.now().strftime("%Y-%m")
        export(month=month)
        gc(keep=3)
        out_dir = settings.exports_dir / month
        notify.notify(
            title="Premura",
            body=(
                f"{month}: ingest + encrypt done. Encrypted artifact ready at "
                f"{out_dir}. Run `hpipe upload --month {month}` to push to Drive when ready."
            ),
        )
    finally:
        try:
            settings.ready_sentinel.unlink()
        except FileNotFoundError:
            pass


def _wait_for_ready() -> bool:
    deadline = time.time() + READY_TIMEOUT_DAYS * 24 * 3600
    while time.time() < deadline:
        if settings.ready_sentinel.exists():
            return True
        time.sleep(READY_POLL_SECS)
    return False


# ============================================================================
# install-launchd / uninstall-launchd
# ============================================================================


@app.command(name="install-launchd")
def install_launchd() -> None:
    """Render and load the macOS launchd agent for the monthly run."""
    if sys.platform != "darwin":
        console.print("[yellow]install-launchd is macOS-only[/yellow]")
        raise typer.Exit(code=1)
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / f"{settings.launchd_label}.plist"
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    template_text = resources.files("premura.ops").joinpath("launchd.plist.j2").read_text()
    program = shutil.which("uv") or "/opt/homebrew/bin/uv"
    rendered = Template(template_text).render(
        label=settings.launchd_label,
        program_args=[program, "run", "hpipe", "run-monthly"],
        working_dir=str(Path.cwd()),
        log_out=str(settings.log_dir / "out.log"),
        log_err=str(settings.log_dir / "err.log"),
    )
    plist_path.write_text(rendered)
    console.print(f"[green]wrote[/green] {plist_path}")
    console.print("Run: launchctl bootstrap gui/$(id -u) " + str(plist_path))


@app.command(name="uninstall-launchd")
def uninstall_launchd() -> None:
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{settings.launchd_label}.plist"
    if plist_path.exists():
        plist_path.unlink()
        console.print(f"[green]removed[/green] {plist_path}")
    else:
        console.print(f"[yellow]no plist at {plist_path}[/yellow]")


# ============================================================================
# install-skills
# ============================================================================


@app.command(name="install-skills")
def install_skills() -> None:
    """Copy bundled Claude Code skills into ``./.claude/skills/``.

    Idempotent: re-running prints ``no changes`` when on-disk files already
    match the shipped package data (sha256-compared). Intended to be invoked
    from a project root; ``bootstrap.sh`` calls this automatically on
    interactive shells unless ``HPIPE_SKIP_SKILLS=1``.
    """
    written = skills.install_skills(Path.cwd())
    if not written:
        console.print("no changes")
        return
    for path in written:
        console.print(str(path))


# ============================================================================
# bootstrap (fresh-clone setup readiness — thin presenter over the service)
# ============================================================================
#
# This command is a *presentation layer* over ``premura.bootstrap.run_bootstrap``
# (WP01). It performs no setup orchestration of its own: it calls the service,
# renders the data-shaped report for a terminal handoff, and maps the summary
# status to an exit code so an agent can branch reliably. It is setup-only — it
# never ingests, queries the warehouse, uploads, or runs the monthly pipeline.


@app.command(name="bootstrap")
def bootstrap() -> None:
    """Prepare and verify a freshly cloned checkout for operation (setup only).

    Runs install-and-verify against the current project root: prepares the local
    environment, installs/verifies bundled skills, and reports readiness. This is
    fresh-clone setup readiness, NOT data ingest or analysis — bootstrap never
    touches health data, the warehouse, uploads, or the monthly pipeline.

    Prints an overall status, the local actions taken, required blockers kept
    separate from optional warnings, reload guidance, and one safe next step.
    Exits 0 when the checkout is ready for normal operation (including a
    ``partial`` result whose only remaining items are optional warnings), and
    non-zero when a required prerequisite is still blocked.
    """
    run = run_bootstrap(Path.cwd())
    _render_bootstrap_run(run)
    raise typer.Exit(code=_bootstrap_exit_code(run))


def _bootstrap_exit_code(run: BootstrapRun) -> int:
    """Map a bootstrap summary to a shell exit code.

    * ``ready``  -> 0 (checkout is ready).
    * ``partial`` -> 0 only when operation is safe and just optional warnings /
      visibility guidance remain (``summary.ready_for_operation``).
    * ``blocked`` (or any state where required readiness is absent) -> 1.

    The mapping keys on ``ready_for_operation`` rather than re-deriving status,
    so the service stays the single source of truth.
    """
    return 0 if run.summary.ready_for_operation else 1


_ACTION_GLYPH = {
    ActionResult.CHANGED: "changed",
    ActionResult.NO_CHANGE: "no change",
    ActionResult.FAILED: "FAILED",
    ActionResult.NOT_ATTEMPTED: "not attempted",
}

_STATUS_STYLE = {
    SummaryStatus.READY: "green",
    SummaryStatus.PARTIAL: "yellow",
    SummaryStatus.BLOCKED: "red",
}


def _render_bootstrap_run(run: BootstrapRun) -> None:
    """Render a BootstrapRun as a concise terminal handoff.

    Output stays well under the 200-line success-path budget: a fixed header,
    one line per local action, then the (usually short) blocker and warning
    lists, reload guidance, and a single next step. Blockers are printed in their
    own clearly-labeled section *before* optional warnings so they are never
    buried among them.
    """
    summary = run.summary
    style = _STATUS_STYLE.get(summary.status, "white")

    # 1) Overall status near the top.
    console.print(f"[bold]bootstrap[/bold]: [{style}]{summary.status.value.upper()}[/{style}]")

    # 2) Local actions: changed vs. no-change vs. failed.
    console.print("[bold]actions[/bold]:")
    for action in run.actions:
        console.print(f"  - {action.name}: {_ACTION_GLYPH[action.result]} ({action.detail})")

    # 3) Required blockers — their own section, first, distinct from warnings.
    if summary.blockers:
        console.print("[bold red]blockers (required)[/bold red]:")
        for blocker in summary.blockers:
            console.print(f"  - {blocker}")
    else:
        console.print("[bold]blockers (required)[/bold]: none")

    # 4) Optional warnings — clearly marked as non-blocking, after the blockers.
    if summary.warnings:
        console.print("[bold yellow]warnings (optional)[/bold yellow]:")
        for warning in summary.warnings:
            console.print(f"  - {warning}")
    else:
        console.print("[bold]warnings (optional)[/bold]: none")

    # 5) Reload guidance — always printed.
    console.print(f"[bold]reload guidance[/bold]: {summary.reload_guidance}")

    # 6) One safe next step near the bottom.
    console.print(f"[bold]next step[/bold]: {summary.next_step}")


# ============================================================================
# profile capture (thin CLI mirror of the agent-safe MCP surface)
# ============================================================================
#
# These commands are a narrow expert/testing entry path. They call the SAME
# runtime helpers the default MCP surface uses (premura.mcp.server), so the CLI
# never forks the capture/validation logic — it only formats the JSON-safe
# result for the terminal. The bounded allowlist is still enforced at the store
# boundary; the CLI surfaces a rejection visibly rather than swallowing it.


@app.command(name="profile-fields")
def profile_fields() -> None:
    """List the bounded baseline-profile attributes that can be captured."""
    schema = mcp_server.supported_profile_fields()
    tbl = Table(title="Supported profile fields")
    for col in ("attribute_key", "value_kind", "unit", "allowed_values", "description"):
        tbl.add_column(col)
    for field in schema["fields"]:
        allowed = field["allowed_values"]
        tbl.add_row(
            field["attribute_key"],
            field["value_kind"],
            field["unit"] or "—",
            ", ".join(allowed) if allowed else "—",
            field["description"],
        )
    console.print(tbl)


@app.command(name="profile-record")
def profile_record(
    attribute_key: Annotated[
        str,
        typer.Argument(help="Supported profile key: birth_date | sex | standing_height_cm"),
    ],
    value: Annotated[
        str, typer.Argument(help="Value for the attribute (ISO date, enum, or number)")
    ],
    effective_start: Annotated[
        str | None,
        typer.Option("--effective-start", help="ISO-8601 instant the fact becomes effective"),
    ] = None,
    source_ref: Annotated[
        str | None, typer.Option("--source-ref", help="Optional provenance reference")
    ] = None,
    notes: Annotated[
        str | None, typer.Option("--notes", help="Optional capture-session bookkeeping note")
    ] = None,
) -> None:
    """Record one bounded baseline profile fact (agent-mediated capture path).

    Unsupported or derived keys (e.g. ``age``) are rejected visibly with a
    non-zero exit code rather than reported as a vague success.
    """
    result = mcp_server.record_profile_context(
        attribute_key,
        _coerce_profile_value(value),
        effective_start_utc=effective_start,
        source_ref=source_ref,
        notes=notes,
    )
    console.print_json(json.dumps(result))
    if result["status"] == "rejected":
        raise typer.Exit(code=1)


def _coerce_profile_value(raw: str) -> str | float:
    """Best-effort coerce a CLI string to a number when it parses as one.

    Date and enum fields stay strings; numeric fields (e.g. height) accept a
    plain number. The store boundary still owns type validation, so a mismatch
    is rejected there rather than guessed here.
    """
    try:
        return float(raw)
    except ValueError:
        return raw


# ============================================================================
# helpers
# ============================================================================


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


if __name__ == "__main__":
    app()
