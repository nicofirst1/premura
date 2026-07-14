"""Throwaway sandbox for parser-build ingest isolation (FR-020).

A :class:`Sandbox` is a temp copy of the **tracked** repo tree (from
``git ls-files``, never a blind recursive copy) with the warehouse and the
session-log paths redirected into the temp dir. It lets an agent edit parser
files and run a real ingest without ever touching the real repo or the real
warehouse; teardown removes everything so no extracted data persists (NFR-004).

The runner that consumes a sandbox lives in
:mod:`premura.harness.ingest_runner`; this module only builds and disposes the
isolation boundary.

**Isolation scope (slice-one).** The sandbox provides REPO-TREE and
WAREHOUSE/LOG-FILE isolation only: a throwaway temp copy of the tracked repo tree
with the DuckDB warehouse and session-log paths redirected into the temp dir. It
is NOT OS-level or home-directory sandboxing — the ingest subprocess still runs as
the host user and can read the host environment (``PATH``/``HOME`` are passed
through to resolve the interpreter). Stronger OS-level isolation (containers,
namespaces, a restricted filesystem) is out of slice-one scope.
"""

from __future__ import annotations

import importlib.metadata
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from ulid import ULID

# Tracked paths whose top-level segment matches one of these are never copied
# into the sandbox: they are either huge, derived, or noise that breaks
# reproducibility from a clean clone (R2 / NFR-002). ``.git`` and ``.venv``
# never appear in ``git ls-files``; ``kitty-specs`` / ``.worktrees`` / ``data``
# can, so they are filtered explicitly.
EXCLUDED_TOP_LEVEL: frozenset[str] = frozenset(
    {".git", ".venv", "data", "kitty-specs", ".worktrees"}
)


def _premura_version() -> str:
    try:
        return importlib.metadata.version("premura")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover - dev fallback
        return "0+unknown"


def _git_paths(repo_root: Path, *git_args: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo_root), *git_args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def _tracked_files(repo_root: Path) -> list[str]:
    """Return the working-tree paths to copy (relative, POSIX).

    Tracked files only (``git ls-files``) so the sandbox input is deterministic
    from a clean checkout (R2 / NFR-002) and never scoops up arbitrary
    untracked scratch from the parent working tree (NFR-004 containment). The
    explicit :data:`EXCLUDED_TOP_LEVEL` filter then drops the huge/derived trees
    (``data``, ``kitty-specs``, ``.worktrees``, …) that git may still track in a
    given checkout. Reference parsers and agent edits arrive *into* the sandbox
    via :func:`install_parser` and in-sandbox edits — never by copying parent
    untracked files in.
    """
    paths = _git_paths(repo_root, "ls-files")
    kept: list[str] = []
    seen: set[str] = set()
    for rel in paths:
        if rel in seen:
            continue
        seen.add(rel)
        top = rel.split("/", 1)[0]
        if top in EXCLUDED_TOP_LEVEL:
            continue
        kept.append(rel)
    return kept


@dataclass(slots=True)
class Sandbox:
    """A throwaway copy of the tracked repo tree with redirected data paths.

    ``root`` is the temp copy; ``warehouse_path`` and ``session_log_path`` point
    at (not-yet-created) temp files inside it so a real ingest can run without
    touching the real warehouse or the real session log.
    """

    root: Path
    warehouse_path: Path
    session_log_path: Path
    isolation_tag: str
    premura_version: str

    def teardown(self) -> None:
        """Recursively remove the entire sandbox tree (NFR-004 PHI containment)."""
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> Sandbox:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.teardown()


def build_sandbox(repo_root: Path) -> Sandbox:
    """Build a sandbox from the tracked tree of ``repo_root``.

    Copies only ``git ls-files`` paths (minus :data:`EXCLUDED_TOP_LEVEL`) into a
    fresh temp dir, preserving relative structure, and redirects the warehouse
    and session-log paths into ``<root>/data/``.
    """
    repo_root = repo_root.resolve()
    root = Path(tempfile.mkdtemp(prefix="premura-sandbox-"))

    for rel in _tracked_files(repo_root):
        src = repo_root / rel
        if not src.is_file():
            # tracked path that is absent in this checkout (e.g. a submodule
            # gitlink) — nothing to copy.
            continue
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    return Sandbox(
        root=root,
        warehouse_path=data_dir / "warehouse.duckdb",
        session_log_path=data_dir / "session_log.duckdb",
        isolation_tag=str(ULID()),
        premura_version=_premura_version(),
    )


# The scoreboard tier under which a fresh-clone install run is recorded (issue #55).
INSTALL_TIER = "install"

# The bundled synthetic scenario fixture + committed reference parser the smoke
# ingest runs, mirroring the observation acceptance scenario. Both are tracked, so
# they exist in a fresh clone; the reference parser lives under ``tests/`` which is
# importable in the cloned tree. Kept here (not imported from ``scenario.py``) so
# this module stays import-light and free of the grader import graph.
_SMOKE_FIXTURE_RELPATH = "tests/fixtures/session_log/fitbit_heart_rate_synthetic.csv"
_SMOKE_PARSER_SPEC = "tests.fixtures.session_log.parsers.good_fitbit_hr:GoodFitbitHrParser"


@dataclass(slots=True)
class InstallStep:
    """One scripted onboarding step and its captured outcome (issue #55).

    ``name`` is the documented step (e.g. ``"uv sync"``); ``ok`` is whether it
    succeeded; ``detail`` carries a short human-readable note (the failing tail of
    stderr, or a row count) for the assertion message when a step breaks.
    """

    name: str
    ok: bool
    detail: str


@dataclass(slots=True)
class InstallTierResult:
    """Result of the deterministic install-from-docs tier (issue #55).

    ``passed`` is true iff every scripted onboarding step worked from the cold
    clone. ``steps`` records each step in order so a failure names *which*
    documented step broke first (the expected Premura finding).
    """

    passed: bool
    steps: list[InstallStep]
    rows_inserted: int

    @property
    def first_failure(self) -> InstallStep | None:
        return next((s for s in self.steps if not s.ok), None)


def _run_step(
    name: str, cmd: list[str], cwd: Path, *, env: dict[str, str] | None = None
) -> InstallStep:
    """Run one onboarding command and capture it as an :class:`InstallStep`."""
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env)
    if proc.returncode == 0:
        return InstallStep(name=name, ok=True, detail="")
    # Keep only the failing tail so the assertion message stays legible.
    tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-8:]
    return InstallStep(name=name, ok=False, detail="\n".join(tail))


def run_install_tier(repo_root: Path) -> InstallTierResult:
    """Run the documented onboarding path from a cold clone + cold env (issue #55).

    The deterministic first rung of the install tier: hands nothing but a fresh
    clone and asserts each documented onboarding step works from a cold
    environment. It, in order:

    1. ``git clone <repo_root> <temp>`` — clones the current checkout's HEAD into a
       temp dir (a local clone, so it reuses objects and needs no network for the
       clone itself);
    2. ``uv sync --extra dev`` — builds a fresh ``uv`` environment in the clone
       (reusing the uv cache is fine; network for package download is acceptable);
    3. ``uv run hpipe bootstrap`` — the agent-facing onboarding entrypoint from the
       root docs (AGENTS.md / README.md), setup-only;
    4. a smoke ingest of the bundled synthetic scenario fixture through the shipped
       ``premura.harness.ingest_runner`` seam, asserting rows actually land.

    Deterministic and scripted: the steps are derived from the root docs, not from
    a model reading them. A model-driven variant is a deliberate follow-up (out of
    scope, issue #55). The caller records the result under :data:`INSTALL_TIER` in
    the scoreboard — this function does not touch the scoreboard so it stays pure
    and testable.

    Slow by construction (a real clone + a real ``uv sync``): the test that drives
    it is ``regression``-marked and excluded from the default suite.
    """
    repo_root = repo_root.resolve()
    root = Path(tempfile.mkdtemp(prefix="premura-install-tier-"))
    clone = root / "clone"
    steps: list[InstallStep] = []
    rows_inserted = 0
    try:
        # Step 1: cold clone of HEAD (local clone reuses objects, no network).
        steps.append(_run_step("git clone", ["git", "clone", str(repo_root), str(clone)], cwd=root))
        if not steps[-1].ok:
            return InstallTierResult(passed=False, steps=steps, rows_inserted=0)

        # Step 2: fresh uv env. Steps 2-4 run from inside the clone via `uv run`,
        # exactly as the docs instruct a fresh agent.
        steps.append(_run_step("uv sync", ["uv", "sync", "--extra", "dev"], cwd=clone))
        if not steps[-1].ok:
            return InstallTierResult(passed=False, steps=steps, rows_inserted=0)

        # Step 3: the documented agent-facing onboarding entrypoint.
        steps.append(_run_step("hpipe bootstrap", ["uv", "run", "hpipe", "bootstrap"], cwd=clone))
        if not steps[-1].ok:
            return InstallTierResult(passed=False, steps=steps, rows_inserted=0)

        # Step 4: smoke ingest of the bundled synthetic fixture through the shipped
        # ingest seam. The runner writes ONLY its JSON envelope to stdout.
        warehouse = root / "warehouse.duckdb"
        smoke = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "premura.harness.ingest_runner",
                "--source",
                str(clone / _SMOKE_FIXTURE_RELPATH),
                "--parser",
                _SMOKE_PARSER_SPEC,
                "--warehouse",
                str(warehouse),
            ],
            cwd=str(clone),
            capture_output=True,
            text=True,
        )
        ok, detail, rows_inserted = _grade_smoke_ingest(
            smoke.returncode, smoke.stdout, smoke.stderr
        )
        steps.append(InstallStep(name="smoke ingest", ok=ok, detail=detail))

        return InstallTierResult(
            passed=all(s.ok for s in steps), steps=steps, rows_inserted=rows_inserted
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _grade_smoke_ingest(returncode: int, stdout: str, stderr: str) -> tuple[bool, str, int]:
    """Grade the smoke-ingest envelope: ok iff it parsed, status ok, and rows landed."""
    import json

    if returncode != 0 and not stdout.strip():
        tail = (stderr or "").strip().splitlines()[-8:]
        return False, "\n".join(tail), 0
    try:
        env = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return False, f"unparseable ingest envelope: {exc}", 0
    if env.get("status") != "ok":
        return False, f"ingest status={env.get('status')} error={env.get('error')}", 0
    rows = int((env.get("load_stats") or {}).get("rows_inserted", 0))
    if rows <= 0:
        return False, f"ingest landed {rows} rows (expected > 0)", rows
    return True, f"{rows} rows", rows


def install_parser(sandbox: Sandbox, parser_src: Path, dest_relpath: str) -> Path:
    """Copy a reference parser module into the sandbox tree (models an agent edit).

    ``dest_relpath`` is relative to the sandbox root, e.g.
    ``"src/premura/parsers/<name>.py"``. Returns the installed absolute path.

    Note on dim_metric: slice-one reference parsers only emit ``heart_rate``,
    which already exists in ``dim_metric.yaml``, so no append is needed. A parser
    declaring a NEW canonical metric would also require the agent to append a row
    to the sandbox's ``src/premura/dim_metric.yaml`` before the ingest seam would
    validate it — out of scope for the committed reference parsers.
    """
    dest = sandbox.root / dest_relpath
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(parser_src, dest)
    return dest


__all__ = [
    "EXCLUDED_TOP_LEVEL",
    "INSTALL_TIER",
    "InstallStep",
    "InstallTierResult",
    "Sandbox",
    "build_sandbox",
    "install_parser",
    "run_install_tier",
]
