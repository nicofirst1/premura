"""Kept run record + append-only capability-floor scoreboard (FR-006/007/011/012).

The durable, **local-only** outputs of a live trial. Two artifacts:

* a **per-run kept record** — the harness-written session-log DuckDB plus the
  final ``verdict.json`` (no ids/timestamps, slice-one determinism), kept under
  ``data/live_trials/<ts>-<model_slug>/``;
* an **append-only capability-floor scoreboard** — one JSON line per run in
  ``data/live_trials/scoreboard.jsonl`` recording, per operator model tier, the
  **first-attempt** and **final** pass verdicts so the capability floor (issue
  #10) can be read and watched climb over time (FR-011/FR-014).

Two hard boundaries this module enforces:

* **Real-data no-persist (FR-012 / NFR-002 / C-001)** — a run pointed at real
  operator data persists **nothing**. :func:`persist_run` returns ``None`` and
  writes zero files when ``is_synthetic`` is false. No PHI ever lands on disk.
* **Append-only integrity (NFR-005)** — :func:`append_scoreboard` only ever
  appends one parseable JSON line; it never rewrites prior lines, so a crash
  mid-run cannot corrupt earlier history. A malformed line is skipped on read
  with a warning, never dropping the rest or raising.

This module is **pure storage**: it holds no model/operator/driver logic and
never syncs, uploads, or exports any artifact off the machine.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Repo root resolved from this module's location, NOT the process cwd, so kept
# artifacts always land under the checkout regardless of where the harness runs.
# scoreboard.py -> harness -> premura -> src -> <repo-root>.
_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Default directory for all kept live-trial artifacts (git-ignored, C-001).
DATA_DIR = _REPO_ROOT / "data" / "live_trials"

#: Default append-only scoreboard path.
SCOREBOARD_PATH = DATA_DIR / "scoreboard.jsonl"

#: The slice-one grader verdict is a plain dict ``{"passed": bool, "rules": ...}``.
Verdict = dict[str, Any]


def _model_slug(model: str) -> str:
    """Filesystem-safe slug for a model identity (e.g. ``qwen2.5-coder:7b``)."""
    return model.replace(":", "-").replace("/", "-")


@dataclass(slots=True)
class LiveTrialRunRecord:
    """The per-run kept record (FR-006/FR-014).

    Persisted (synthetic runs only) alongside the harness-written
    ``session_log.duckdb`` and the final ``verdict.json`` in the run dir. The
    verdicts are the slice-one grader :data:`Verdict` dicts; ``run_kind`` is the
    slice-one schema tag.

    ``tier`` is the comparison axis FR-007 introduces: ``"one_shot"`` is the
    constrained floor probe, ``"tool_loop"`` the multiturn tool tier. ``run_kind``
    stays ``"live_trial"`` for both because both ARE live trials; ``tier`` is the
    open string axis they are compared on (it is not a closed set — do not add a
    whitelist).
    """

    operator_model: str
    driver_model: str
    attempts_used: int
    first_attempt_verdict: Verdict
    final_verdict: Verdict
    run_kind: str = "live_trial"
    tier: str = "one_shot"


@dataclass(slots=True)
class ScoreboardEntry:
    """One append-only scoreboard line (FR-007/FR-011, NFR-005).

    ``first_attempt_pass`` / ``final_pass`` are the top-level ``verdict["passed"]``
    of attempt 1 (un-nagged) and the final attempt respectively.

    ``tier`` is the comparison axis FR-007 introduces (``"one_shot"`` floor vs
    ``"tool_loop"``). It is an open string axis; a line written without it parses
    back as ``"one_shot"`` so every pre-existing scoreboard line stays valid and
    the file is never rewritten (contract §5).
    """

    ts: str
    operator_model: str
    driver_model: str
    attempts_used: int
    first_attempt_pass: bool
    final_pass: bool
    tier: str = "one_shot"

    def to_json_line(self) -> str:
        """Serialize to a single, independently-parseable JSON line (no newline)."""
        return json.dumps(
            {
                "ts": self.ts,
                "operator_model": self.operator_model,
                "driver_model": self.driver_model,
                "attempts_used": self.attempts_used,
                "first_attempt_pass": self.first_attempt_pass,
                "final_pass": self.final_pass,
                "tier": self.tier,
            },
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, obj: dict[str, Any]) -> ScoreboardEntry:
        """Reconstruct an entry from a parsed JSON object.

        A missing ``tier`` key defaults to ``"one_shot"`` so every pre-existing
        (tier-less) scoreboard line parses unchanged (contract §5).
        """
        return cls(
            ts=str(obj["ts"]),
            operator_model=str(obj["operator_model"]),
            driver_model=str(obj["driver_model"]),
            attempts_used=int(obj["attempts_used"]),
            first_attempt_pass=bool(obj["first_attempt_pass"]),
            final_pass=bool(obj["final_pass"]),
            tier=str(obj.get("tier", "one_shot")),
        )


def persist_run(
    record: LiveTrialRunRecord,
    *,
    kept_session_log: Path,
    verdict: Verdict,
    is_synthetic: bool,
    runs_dir: Path = DATA_DIR,
) -> Path | None:
    """Keep the per-run artifacts — ONLY for a synthetic-fixture run.

    Real-data guard (FR-012 / NFR-002 / C-001): when ``is_synthetic`` is false this
    writes **nothing** — no directory, no copy, no verdict — and returns ``None``.
    A real-data run leaves zero new files under the repo.

    For a synthetic run it creates ``<runs_dir>/<ts>-<model_slug>/``, copies the
    harness-written ``kept_session_log`` DuckDB to ``session_log.duckdb``, writes
    the final ``verdict.json`` (``sort_keys=True`` — the verdict carries no
    ids/timestamps, so this stays byte-stable), and returns the run dir.

    ``runs_dir`` defaults to the repo-root :data:`DATA_DIR`; tests pass an explicit
    override (e.g. ``tmp_path``) so they never touch the real ``data/`` dir.
    """
    if not is_synthetic:
        # Hard PHI boundary: persist nothing for a real-data run.
        return None

    # The verdict is deliberately id/timestamp-free (slice-one determinism), so the
    # kept run dir is timestamped at persist time. Kept local-only.
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = runs_dir / f"{ts}-{_model_slug(record.operator_model)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(kept_session_log, run_dir / "session_log.duckdb")
    (run_dir / "verdict.json").write_text(json.dumps(verdict, sort_keys=True), encoding="utf-8")
    return run_dir


def append_scoreboard(
    entry: ScoreboardEntry,
    *,
    path: Path = SCOREBOARD_PATH,
) -> None:
    """Append exactly one scoreboard line (NFR-005).

    Opens in append mode and writes ``entry.to_json_line() + "\\n"`` — never
    truncating or rewriting prior lines, so a crash mid-run cannot corrupt earlier
    history. Creates the parent dir and file if missing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(entry.to_json_line() + "\n")


def read_scoreboard(*, path: Path = SCOREBOARD_PATH) -> list[ScoreboardEntry]:
    """Read the scoreboard in order, tolerating malformed lines (NFR-005).

    Parses line by line; a malformed (unparseable or incomplete) line is skipped
    with a ``logging.warning`` and never drops the rest or raises. Returns the
    valid entries in file order. A missing file yields an empty list.
    """
    if not path.exists():
        return []

    entries: list[ScoreboardEntry] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                entries.append(ScoreboardEntry.from_json(obj))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                logger.warning(
                    "scoreboard: skipping malformed line %d in %s: %s",
                    lineno,
                    path,
                    exc,
                )
    return entries


def current_floor(
    entries: list[ScoreboardEntry],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Compute the capability floor per ``(operator_model, tier)`` (FR-011/FR-007).

    Groups by the ``(operator_model, tier)`` pair so the constrained one-shot
    floor and the tool-loop tier for the same model are reported side by side and
    never overwrite each other (SC-002). The tier is whatever the entry carries —
    legacy (tier-less) rows arrive as ``"one_shot"`` from
    :meth:`ScoreboardEntry.from_json`; the grouping rule does not enumerate a
    fixed tier set. Reports per group::

        {runs, final_pass_runs, first_attempt_pass_runs, last_ts,
         reaches_final_pass}

    ``reaches_final_pass`` is true iff at least one run for that group reached a
    passing final verdict. The first-attempt vs final counts expose how the
    retry loop lifts a group over its un-nagged starting point (FR-014).
    """
    floor: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        group = floor.setdefault(
            (entry.operator_model, entry.tier),
            {
                "runs": 0,
                "final_pass_runs": 0,
                "first_attempt_pass_runs": 0,
                "last_ts": entry.ts,
                "reaches_final_pass": False,
            },
        )
        group["runs"] += 1
        if entry.final_pass:
            group["final_pass_runs"] += 1
            group["reaches_final_pass"] = True
        if entry.first_attempt_pass:
            group["first_attempt_pass_runs"] += 1
        group["last_ts"] = entry.ts  # entries are append-ordered; last wins
    return floor


def _format_floor(floor: dict[tuple[str, str], dict[str, Any]]) -> str:
    """Render a compact per-``(model, tier)`` floor table for the CLI (quickstart.md).

    Rows are sorted by ``(operator_model, tier)`` for deterministic output.
    """
    if not floor:
        return "scoreboard empty — no live-trial runs recorded yet."

    header = (
        f"{'operator_model':<28} {'tier':<10} {'runs':>5} {'first✓':>7} "
        f"{'final✓':>7} {'floor':>6}  last_ts"
    )
    lines = [header, "-" * len(header)]
    for model, tier in sorted(floor):
        t = floor[(model, tier)]
        lines.append(
            f"{model:<28} {tier:<10} {t['runs']:>5} {t['first_attempt_pass_runs']:>7} "
            f"{t['final_pass_runs']:>7} {('yes' if t['reaches_final_pass'] else 'no'):>6}  "
            f"{t['last_ts']}"
        )
    return "\n".join(lines)


def _main() -> None:
    """Read the scoreboard and print the per-tier capability floor."""
    entries = read_scoreboard()
    print(_format_floor(current_floor(entries)))


if __name__ == "__main__":
    _main()
