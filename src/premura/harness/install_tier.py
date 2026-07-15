"""Install tier: prove the documented cold-clone onboarding path works (issue #55).

The existing :func:`premura.harness.sandbox.build_sandbox` copies the tracked tree
into a temp dir but runs it inside the SAME interpreter/venv as the parent. That
tests parser isolation, not onboarding: it never exercises "a fresh agent is
handed nothing but a clone and the root docs". Issue #10's install tier requires
exactly that colder start - a real ``git clone`` of HEAD, a fresh ``uv`` env, and
the onboarding steps a fresh agent would run from AGENTS.md / CONTRIBUTING.md.

This module sits beside ``build_sandbox`` and runs that path as a small
**declarative sequence** (:data:`INSTALL_TIER_STEPS`): each step names the doc +
section it mirrors, so if the docs and this script drift a maintainer can trace
the failing step straight back to the doc line it claims to mirror. The tier is
deterministic (scripted, no LLM operator); a model-driven variant that reads the
docs and improvises is an explicit follow-up, out of scope here.

The result is recorded on the existing capability-floor scoreboard under tier
``"install"`` (the ``tier`` field is an open string axis, so this is a new tier
value, not a schema change). This tier only ever runs a synthetic bundled
fixture, so it is inherently ``is_synthetic=True``; there is no LLM operator, so
``operator_model`` is the constant :data:`INSTALL_OPERATOR_MODEL` ("deterministic").
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from premura.harness.scoreboard import (
    SCOREBOARD_PATH,
    ScoreboardEntry,
    append_scoreboard,
)

#: This tier has no LLM operator - the steps are a fixed script - so the
#: scoreboard operator identity is a constant, not a model name.
INSTALL_OPERATOR_MODEL = "deterministic"

#: The scoreboard tier axis value for this rung (open string axis, contract §5).
INSTALL_TIER = "install"

#: Where the bundled synthetic intake fixture lives, relative to a clone root.
#: Mirrors ``premura.harness.intake_strategy`` (which reads it from REPO_ROOT).
_FIXTURE_RELDIR = Path("tests") / "fixtures" / "intake_scenario"
_FIXTURE_SOURCE_REL = _FIXTURE_RELDIR / "alien_intake.csv"
_FIXTURE_PARSER_REL = _FIXTURE_RELDIR / "reference_intake_parser.py"
#: The reference parser copied into the clone's parsers tree (models an agent
#: edit), then imported by the smoke ingest via this module:attr spec.
_INSTALLED_PARSER_REL = Path("src") / "premura" / "parsers" / "_install_tier_intake.py"
_INSTALLED_PARSER_SPEC = "premura.parsers._install_tier_intake:AlienIntakeReferenceParser"


@dataclass(frozen=True, slots=True)
class InstallStepContext:
    """Paths a step needs to act on the clone (built once per run)."""

    clone_root: Path
    warehouse_path: Path

    @property
    def venv_python(self) -> Path:
        """The clone's own interpreter, created by the ``uv sync`` step."""
        return self.clone_root / ".venv" / "bin" / "python"


@dataclass(frozen=True, slots=True)
class InstallStep:
    """One declarative onboarding step, tied to the doc line it mirrors.

    ``doc_ref`` is not decoration: it is the trace back to the documented
    onboarding line this step asserts still works, so a drift between the docs
    and this script is diagnosable from the failing step alone.

    Exactly one of ``argv`` / ``func`` is set. ``argv`` builds a subprocess
    command run with ``cwd=clone_root`` (the common case); ``func`` is a
    filesystem-only action (the parser copy) that needs no subprocess.
    """

    name: str
    doc_ref: str
    argv: Callable[[InstallStepContext], list[str]] | None = None
    func: Callable[[InstallStepContext], None] | None = None


def _copy_reference_parser(ctx: InstallStepContext) -> None:
    """Copy the bundled reference parser into the clone's parsers tree.

    Mirrors :func:`premura.harness.sandbox.install_parser` (an agent edit lands a
    parser into ``src/premura/parsers/``), adapted to the clone root.
    """
    src = ctx.clone_root / _FIXTURE_PARSER_REL
    dst = ctx.clone_root / _INSTALLED_PARSER_REL
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


#: The onboarding path as a fixed sequence. Each step cites the doc + section it
#: mirrors (issue #55: docs-and-script drift must be traceable to a doc line).
INSTALL_TIER_STEPS: tuple[InstallStep, ...] = (
    InstallStep(
        name="uv_sync",
        # CONTRIBUTING.md bootstrap path: `uv sync --extra dev` builds the env.
        doc_ref="CONTRIBUTING.md bootstrap path (uv sync --extra dev)",
        argv=lambda ctx: ["uv", "sync", "--extra", "dev"],
    ),
    InstallStep(
        name="premura_bootstrap",
        # AGENTS.md "First steps in this clone" step 1: `uv run premura bootstrap`.
        doc_ref="AGENTS.md First steps in this clone step 1 (uv run premura bootstrap)",
        argv=lambda ctx: ["uv", "run", "premura", "bootstrap"],
    ),
    InstallStep(
        name="install_reference_parser",
        # Mirrors sandbox.install_parser: an agent edit lands a parser under
        # src/premura/parsers/ before the smoke ingest can import it.
        doc_ref="sandbox.install_parser (agent lands a parser in src/premura/parsers/)",
        func=_copy_reference_parser,
    ),
    InstallStep(
        name="smoke_ingest",
        # Reuses the subprocess ingest-runner pattern (tests/test_sandbox.py
        # _run_runner) over the bundled synthetic intake fixture, in the clone's
        # own venv so nothing loads the parent's already-imported premura.
        doc_ref="tests/test_sandbox.py _run_runner smoke ingest over the bundled fixture",
        argv=lambda ctx: [
            str(ctx.venv_python),
            "-m",
            "premura.harness.ingest_runner",
            "--source",
            str(ctx.clone_root / _FIXTURE_SOURCE_REL),
            "--parser",
            _INSTALLED_PARSER_SPEC,
            "--warehouse",
            str(ctx.warehouse_path),
        ],
    ),
)


@dataclass(slots=True)
class StepOutcome:
    """The per-step result: which step, pass/fail, and a short captured message."""

    name: str
    doc_ref: str
    passed: bool
    #: stdout/stderr tail or a short explanation; kept small (this is a log line,
    #: not the ingest-runner's schema-validated JSON envelope).
    message: str


@dataclass(slots=True)
class InstallTierResult:
    """The install-tier run envelope: overall pass/fail + one outcome per step.

    ``failed_step`` is the name of the first step that failed (``None`` on a full
    pass). ``steps`` holds every outcome up to and including the failure, so a
    scoreboard entry and a human both see which documented step broke first.
    """

    passed: bool
    failed_step: str | None
    steps: list[StepOutcome] = field(default_factory=list)


def _clone_head(repo_root: Path, dest: Path) -> None:
    """``git clone`` the current checkout's HEAD into ``dest`` (a real clone).

    A real clone, not a copy-tree: the destination gets its own ``.git`` and a
    fully independent working tree, exactly what a fresh agent would be handed.
    """
    subprocess.run(
        ["git", "clone", "--quiet", str(repo_root), str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )


def _run_step(step: InstallStep, ctx: InstallStepContext) -> StepOutcome:
    """Execute one declarative step and capture a small pass/fail outcome."""
    if step.func is not None:
        try:
            step.func(ctx)
        except Exception as exc:  # noqa: BLE001 - any failure is a graded step fail
            return StepOutcome(step.name, step.doc_ref, passed=False, message=str(exc))
        return StepOutcome(step.name, step.doc_ref, passed=True, message="ok")

    assert step.argv is not None  # one of argv/func is always set (dataclass invariant)
    proc = subprocess.run(
        step.argv(ctx),
        cwd=ctx.clone_root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        # Keep the tail only - full logs are large; the failing step + tail is
        # enough to trace back to the doc line it mirrors.
        tail = (proc.stderr or proc.stdout)[-2000:]
        return StepOutcome(step.name, step.doc_ref, passed=False, message=tail)
    return StepOutcome(step.name, step.doc_ref, passed=True, message=(proc.stdout or "ok")[-500:])


def run_install_tier(
    repo_root: Path,
    *,
    steps: tuple[InstallStep, ...] = INSTALL_TIER_STEPS,
    record: bool = True,
    scoreboard_path: Path = SCOREBOARD_PATH,
) -> InstallTierResult:
    """Run the documented cold-clone onboarding path and record the result.

    Clones ``repo_root``'s HEAD into a fresh temp dir, then runs ``steps`` in
    order inside the clone, stopping at the first failure. The clone is always
    torn down afterward (no extracted data or built env persists). When
    ``record`` is true the run is appended to the scoreboard under tier
    ``"install"`` (synthetic-only tier, so always recorded).
    """
    repo_root = repo_root.resolve()
    clone_root = Path(tempfile.mkdtemp(prefix="premura-install-tier-"))
    result = InstallTierResult(passed=True, failed_step=None)
    try:
        _clone_head(repo_root, clone_root)
        ctx = InstallStepContext(
            clone_root=clone_root,
            warehouse_path=clone_root / "data" / "install_tier_warehouse.duckdb",
        )
        ctx.warehouse_path.parent.mkdir(parents=True, exist_ok=True)

        for step in steps:
            outcome = _run_step(step, ctx)
            result.steps.append(outcome)
            if not outcome.passed:
                result.passed = False
                result.failed_step = step.name
                break
    finally:
        shutil.rmtree(clone_root, ignore_errors=True)

    if record:
        _record_install_run(result, scoreboard_path=scoreboard_path)
    return result


def _record_install_run(result: InstallTierResult, *, scoreboard_path: Path) -> None:
    """Append one scoreboard line under tier ``"install"``.

    The tier is deterministic and single-attempt, so ``attempts_used`` is 1 and
    ``first_attempt_pass`` equals ``final_pass``. There is no driver model either,
    so ``driver_model`` reuses the same deterministic constant as the operator.
    """
    entry = ScoreboardEntry(
        ts=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        operator_model=INSTALL_OPERATOR_MODEL,
        driver_model=INSTALL_OPERATOR_MODEL,
        attempts_used=1,
        first_attempt_pass=result.passed,
        final_pass=result.passed,
        tier=INSTALL_TIER,
    )
    append_scoreboard(entry, path=scoreboard_path)


__all__ = [
    "INSTALL_OPERATOR_MODEL",
    "INSTALL_TIER",
    "INSTALL_TIER_STEPS",
    "InstallStep",
    "InstallStepContext",
    "InstallTierResult",
    "StepOutcome",
    "run_install_tier",
]
