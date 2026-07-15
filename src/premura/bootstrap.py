"""Bootstrap core service for a freshly cloned Premura checkout.

This module is the *setup-only* service layer that powers the future
``premura bootstrap`` CLI command. :func:`run_bootstrap` inspects the local
checkout, attempts the small set of *safe local* setup actions, installs or
verifies the bundled project skills, and returns a :class:`BootstrapRun` report
that a caller can format, test, and reason about without re-deriving any status.

Design rules this module enforces (see the mission spec, contract, and
data-model):

* **Setup-only.** Bootstrap never ingests health data, never queries the
  warehouse, never dispatches analytical MCP tools, never uploads, and never
  runs the monthly pipeline. The forbidden surface is named in
  :data:`FORBIDDEN_OPERATIONS` and this module does not import any of it.
* **Local-first, no silent system mutation.** A prerequisite that cannot be
  installed safely inside the checkout becomes a ``blocked`` check with
  ``local_action_allowed=False`` and an exact next action. Bootstrap does not
  shell out to mutate the system in that case.
* **Optional capability gaps are warnings, not blockers.** A missing upload
  capability (rclone/Drive) is reported as a warning and never makes the
  summary ``blocked``.
* **Failures are report data.** An ordinary local command failure produces a
  ``failed`` action and a ``blocked`` summary — never an uncaught traceback.
* **Reload guidance is always produced**, because a running agent session may
  not see newly materialized skills until it reloads.

The command runner and skill installer are injected so tests never invoke real
install commands or materialize real skill files.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from premura import skills

__all__ = [
    "FORBIDDEN_OPERATIONS",
    "SummaryStatus",
    "CheckStatus",
    "ActionResult",
    "CommandOutcome",
    "BootstrapCheck",
    "BootstrapAction",
    "SkillSetupState",
    "BootstrapSummary",
    "BootstrapRun",
    "run_bootstrap",
]


# ---------------------------------------------------------------------------
# Setup-only safety boundary
# ---------------------------------------------------------------------------

#: Operation surfaces this service must never invoke. Named here so callers and
#: tests can assert the boundary is honest. Keeping it as data (not an
#: enumerated import list) means bootstrap cannot accidentally pull a health
#: operation into its import graph.
FORBIDDEN_OPERATIONS: tuple[str, ...] = (
    "ingest",
    "run-monthly",
    "upload",
    "warehouse-query",
    "mcp-analytical-dispatch",
)


# ---------------------------------------------------------------------------
# Closed status vocabularies
# ---------------------------------------------------------------------------


class SummaryStatus(StrEnum):
    """Overall result of a bootstrap run."""

    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class CheckStatus(StrEnum):
    """Result of a single readiness check."""

    PASS = "pass"
    FIXED = "fixed"
    BLOCKED = "blocked"
    WARNING = "warning"
    SKIPPED = "skipped"


class ActionResult(StrEnum):
    """Outcome of a single local action bootstrap attempted."""

    CHANGED = "changed"
    NO_CHANGE = "no_change"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"


# ---------------------------------------------------------------------------
# Injectable boundaries
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandOutcome:
    """Result of running one local setup command through the runner boundary.

    The runner reports a process-style ``returncode`` plus an explicit
    ``changed`` flag so the service can distinguish "did work" from "already
    current" without parsing command output.
    """

    returncode: int
    changed: bool = False
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


#: A command runner takes a stable action *name* and the argv it would run, and
#: returns a :class:`CommandOutcome`. Tests inject a fake; the default runner
#: actually executes the command locally.
CommandRunner = Callable[[str, list[str]], CommandOutcome]

#: A skill installer materializes bundled skills under ``target_root`` and
#: returns the list of files actually written/changed (empty == no change).
SkillInstaller = Callable[[Path], list[Path]]

#: A tool probe answers "is this CLI tool available on PATH?".
ToolProbe = Callable[[str], bool]

#: A surface probe answers "does this ``module:attribute`` import target resolve?"
#: It returns ``(ok, detail)`` so a caller can classify a core-surface check
#: without re-deriving why an import failed.
SurfaceProbe = Callable[[str], tuple[bool, str]]

#: Bound on a single local setup command. A fresh-clone bootstrap must fail with
#: an actionable blocker rather than hang the agent indefinitely if dependency
#: resolution stalls. Sized generously above the NFR-001 10-minute success
#: target so a healthy clean sync never trips it.
_LOCAL_COMMAND_TIMEOUT_SECONDS = 900


def _make_default_command_runner(project_root: Path) -> CommandRunner:
    """Build the real subprocess runner anchored to the checkout root.

    Commands run with ``cwd=project_root`` so local setup targets the intended
    checkout regardless of the process working directory, and with a bounded
    timeout so a stalled dependency resolution becomes an actionable blocker
    instead of an indefinite hang. Used only when no runner is injected.
    """

    def _run(name: str, argv: list[str]) -> CommandOutcome:
        import subprocess

        try:
            proc = subprocess.run(  # noqa: S603 - argv is built by this module
                argv,
                capture_output=True,
                text=True,
                check=False,
                cwd=project_root,
                timeout=_LOCAL_COMMAND_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return CommandOutcome(
                returncode=124,
                changed=False,
                detail=(
                    f"{name} timed out after {_LOCAL_COMMAND_TIMEOUT_SECONDS}s; "
                    "re-run it manually to see where it stalls."
                ),
            )
        except (OSError, ValueError) as exc:  # pragma: no cover - defensive
            return CommandOutcome(returncode=127, changed=False, detail=str(exc))
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return CommandOutcome(
            returncode=proc.returncode,
            # The default runner cannot know "changed vs current"; treat a clean
            # run as a change so callers see the action happened.
            changed=proc.returncode == 0,
            detail=detail[-1] if detail else "",
        )

    return _run


def _default_tool_probe(tool: str) -> bool:
    return shutil.which(tool) is not None


def _default_surface_probe(target: str) -> tuple[bool, str]:
    """Verify a ``"module:attribute"`` surface resolves by import only.

    This confirms a core project surface *can start* (its entry point imports
    cleanly) without actually starting it — bootstrap is setup-only and never
    runs a CLI verb, MCP server, or pipeline.
    """
    import importlib

    module_name, _, attr = target.partition(":")
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - any import failure is a real blocker
        return False, f"import of {module_name} failed: {exc}"
    if attr and not hasattr(module, attr):
        return False, f"{module_name} has no attribute {attr!r}"
    return True, f"{target} importable"


# ---------------------------------------------------------------------------
# Report records
# ---------------------------------------------------------------------------


@dataclass
class BootstrapCheck:
    """One readiness check and its classification."""

    name: str
    category: str
    status: CheckStatus
    observed: str = ""
    next_action: str = ""
    local_action_allowed: bool = True


@dataclass
class BootstrapAction:
    """One local action bootstrap attempted (or deliberately did not)."""

    name: str
    scope: str
    result: ActionResult
    detail: str = ""


@dataclass
class SkillSetupState:
    """Skill installation/visibility state derived from the installer result."""

    installed_count: int
    unchanged: bool
    install_path: Path
    reload_required: bool
    message: str


@dataclass
class BootstrapSummary:
    """The final handoff object a caller renders verbatim."""

    status: SummaryStatus
    ready_for_operation: bool
    reload_guidance: str
    next_step: str
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class BootstrapRun:
    """One invocation of the bootstrap service."""

    started_at: datetime
    checkout_root: Path
    mode: str
    checks: list[BootstrapCheck]
    actions: list[BootstrapAction]
    skill_setup: SkillSetupState
    summary: BootstrapSummary


# ---------------------------------------------------------------------------
# Setup-area registry
# ---------------------------------------------------------------------------

#: Setup categories from the data-model. Kept as a registry so new areas are
#: added by extending this map plus a probe, not by special-casing prose.
CATEGORY_PROJECT_ENVIRONMENT = "project environment"
CATEGORY_COMMAND_AVAILABILITY = "command availability"
CATEGORY_SKILL_SETUP = "skill setup"
CATEGORY_OPTIONAL_CAPABILITY = "optional capability"
CATEGORY_EXTERNAL_PREREQUISITE = "external prerequisite"

#: The local dependency manager. Premura's documented setup path is `uv`
#: (see CONTRIBUTING/pyproject); it manages the project environment locally
#: rather than mutating the system, so we may invoke it. If it is absent we
#: report it as a blocker rather than installing it system-wide.
_DEP_MANAGER = "uv"
_DEP_ACTION = "install_local_dependencies"

#: Optional capabilities: absence is a warning, never a blocker.
_OPTIONAL_TOOLS: tuple[tuple[str, str], ...] = (
    ("rclone", "Encrypted-export upload to remote storage is unavailable until rclone is set up."),
)

#: Core project surfaces a ready checkout must be able to start, declared as a
#: registry of ``(label, "module:attribute")`` import targets that mirrors
#: pyproject's ``[project.scripts]``. Verification imports each target (never
#: runs it), so adding a surface is a one-line registry edit, not new prose. A
#: surface that fails to import is a real blocker: the environment cannot start
#: it before normal operation.
_CORE_SURFACES: tuple[tuple[str, str], ...] = (
    ("premura CLI", "premura.cli:app"),
    ("Premura MCP server", "premura.mcp.entrypoint:main"),
    ("Premura operator MCP server", "premura.mcp.entrypoint:main_operator"),
)


def _build_skill_setup_state(written: list[Path], install_path: Path) -> SkillSetupState:
    """Convert an installer's written-paths list into a SkillSetupState.

    Reload guidance is always populated. We cannot guarantee a running agent
    session sees newly materialized files, so any change recommends a reload.
    """
    installed_count = len(written)
    unchanged = installed_count == 0
    if unchanged:
        message = (
            f"Skills already current under {install_path}. "
            "Reload not required for skill visibility."
        )
        reload_required = False
    else:
        message = (
            f"Installed or updated {installed_count} skill file(s) under {install_path}. "
            "Reload required: start a fresh agent session to see the new skills."
        )
        reload_required = True
    return SkillSetupState(
        installed_count=installed_count,
        unchanged=unchanged,
        install_path=install_path,
        reload_required=reload_required,
        message=message,
    )


def _classify_dependency_manager(
    tool_probe: ToolProbe,
) -> BootstrapCheck:
    """Check for the local dependency manager.

    Present -> we may run a local install action (caller drives the runner).
    Absent  -> a blocked external prerequisite; we do NOT install it system-wide.
    """
    if tool_probe(_DEP_MANAGER):
        return BootstrapCheck(
            name=f"{_DEP_MANAGER} available",
            category=CATEGORY_COMMAND_AVAILABILITY,
            status=CheckStatus.PASS,
            observed=f"{_DEP_MANAGER} found on PATH",
            local_action_allowed=True,
        )
    return BootstrapCheck(
        name=f"{_DEP_MANAGER} available",
        category=CATEGORY_EXTERNAL_PREREQUISITE,
        status=CheckStatus.BLOCKED,
        observed=f"{_DEP_MANAGER} not found on PATH",
        next_action=(
            f"Install {_DEP_MANAGER} (the project dependency manager) following its "
            "official install guide, then re-run bootstrap. Bootstrap will not "
            "install it system-wide for you."
        ),
        local_action_allowed=False,
    )


def _classify_optional_capabilities(tool_probe: ToolProbe) -> list[BootstrapCheck]:
    checks: list[BootstrapCheck] = []
    for tool, guidance in _OPTIONAL_TOOLS:
        if tool_probe(tool):
            checks.append(
                BootstrapCheck(
                    name=f"{tool} available",
                    category=CATEGORY_OPTIONAL_CAPABILITY,
                    status=CheckStatus.PASS,
                    observed=f"{tool} found on PATH",
                    local_action_allowed=False,
                )
            )
        else:
            checks.append(
                BootstrapCheck(
                    name=f"{tool} available",
                    category=CATEGORY_OPTIONAL_CAPABILITY,
                    status=CheckStatus.WARNING,
                    observed=f"{tool} not found on PATH",
                    next_action=guidance,
                    local_action_allowed=False,
                )
            )
    return checks


def _classify_core_surfaces(
    surface_probe: SurfaceProbe,
    *,
    dependencies_ready: bool,
) -> list[BootstrapCheck]:
    """Verify that each declared core project surface can start (imports cleanly).

    When local dependencies are not yet installed the surfaces cannot import, so
    they are reported ``skipped`` with the dependency next-action rather than as
    false blockers — the dependency blocker already drives the summary.
    """
    checks: list[BootstrapCheck] = []
    for label, target in _CORE_SURFACES:
        name = f"{label} importable"
        if not dependencies_ready:
            checks.append(
                BootstrapCheck(
                    name=name,
                    category=CATEGORY_COMMAND_AVAILABILITY,
                    status=CheckStatus.SKIPPED,
                    observed="not verified: local dependencies are not installed yet",
                    next_action=(
                        "Install local dependencies, then re-run bootstrap to verify "
                        "core project surfaces."
                    ),
                    local_action_allowed=True,
                )
            )
            continue
        ok, detail = surface_probe(target)
        if ok:
            checks.append(
                BootstrapCheck(
                    name=name,
                    category=CATEGORY_COMMAND_AVAILABILITY,
                    status=CheckStatus.PASS,
                    observed=detail,
                    local_action_allowed=True,
                )
            )
        else:
            checks.append(
                BootstrapCheck(
                    name=name,
                    category=CATEGORY_COMMAND_AVAILABILITY,
                    status=CheckStatus.BLOCKED,
                    observed=detail,
                    next_action=(
                        f"Core surface {label} ({target}) could not be imported. Re-run "
                        "dependency setup and resolve the import error, then re-run bootstrap."
                    ),
                    local_action_allowed=True,
                )
            )
    return checks


def run_bootstrap(
    project_root: Path,
    *,
    command_runner: CommandRunner | None = None,
    skill_installer: SkillInstaller = skills.install_skills,
    tool_probe: ToolProbe | None = None,
    surface_probe: SurfaceProbe | None = None,
) -> BootstrapRun:
    """Inspect and prepare a local Premura checkout, returning a report.

    Parameters
    ----------
    project_root:
        The checkout to bootstrap. Used as the skill install root and as the
        working context for local actions. No private ``data/`` contents are
        required or read.
    command_runner:
        Boundary for local setup commands. Defaults to a real subprocess
        runner; tests inject a fake so no real install runs.
    skill_installer:
        Defaults to :func:`premura.skills.install_skills`. Returns the list of
        skill files actually written (empty == already current).
    tool_probe:
        Boundary for "is this CLI tool on PATH?". Defaults to ``shutil.which``.
    surface_probe:
        Boundary for "does this core-surface import target resolve?". Defaults to
        a real import probe; tests inject a fake so no real module is imported.

    Returns
    -------
    BootstrapRun
        A fully classified, data-shaped setup report. The caller formats it; it
        does not need to recompute status or infer reload guidance.
    """
    project_root = Path(project_root)
    runner = (
        command_runner if command_runner is not None else _make_default_command_runner(project_root)
    )
    probe = tool_probe if tool_probe is not None else _default_tool_probe
    surf_probe = surface_probe if surface_probe is not None else _default_surface_probe

    started_at = datetime.now(UTC)
    checks: list[BootstrapCheck] = []
    actions: list[BootstrapAction] = []

    # 1) Command availability: the local dependency manager.
    dep_check = _classify_dependency_manager(probe)
    checks.append(dep_check)

    # 2) Local project dependency action — only if it is safe to run locally.
    dependencies_ready = False
    if dep_check.local_action_allowed:
        outcome = runner(
            _DEP_ACTION,
            [_DEP_MANAGER, "sync", "--extra", "dev"],
        )
        dependencies_ready = outcome.ok
        if not outcome.ok:
            actions.append(
                BootstrapAction(
                    name=_DEP_ACTION,
                    scope="local checkout/environment",
                    result=ActionResult.FAILED,
                    detail=(
                        outcome.detail
                        or f"{_DEP_MANAGER} sync exited with code {outcome.returncode}"
                    ),
                )
            )
            checks.append(
                BootstrapCheck(
                    name="local dependencies installed",
                    category=CATEGORY_PROJECT_ENVIRONMENT,
                    status=CheckStatus.BLOCKED,
                    observed=outcome.detail or "dependency sync failed",
                    next_action=(
                        f"Re-run `{_DEP_MANAGER} sync --extra dev` and read the resolver "
                        "output; resolve the reported error, then re-run bootstrap."
                    ),
                    local_action_allowed=True,
                )
            )
        else:
            result = ActionResult.CHANGED if outcome.changed else ActionResult.NO_CHANGE
            actions.append(
                BootstrapAction(
                    name=_DEP_ACTION,
                    scope="local checkout/environment",
                    result=result,
                    detail=outcome.detail
                    or ("synced project dependencies" if outcome.changed else "already current"),
                )
            )
            checks.append(
                BootstrapCheck(
                    name="local dependencies installed",
                    category=CATEGORY_PROJECT_ENVIRONMENT,
                    status=CheckStatus.FIXED if outcome.changed else CheckStatus.PASS,
                    observed=(
                        "dependencies synced" if outcome.changed else "dependencies already current"
                    ),
                    local_action_allowed=True,
                )
            )
    else:
        # Dependency manager missing -> deliberately do not attempt the action.
        actions.append(
            BootstrapAction(
                name=_DEP_ACTION,
                scope="external/system",
                result=ActionResult.NOT_ATTEMPTED,
                detail=f"{_DEP_MANAGER} unavailable; not installing system-wide",
            )
        )

    # 2b) Core project surfaces: confirm each declared entry point can start by
    #     importing it (setup-only — bootstrap never runs the surface). Skipped
    #     with guidance when dependencies are not yet installed.
    checks.extend(_classify_core_surfaces(surf_probe, dependencies_ready=dependencies_ready))

    # 3) Skill setup via the repo-supported installer.
    skills_install_path = project_root / ".claude" / "skills"
    written = skill_installer(project_root)
    skill_setup = _build_skill_setup_state(written, skills_install_path)
    actions.append(
        BootstrapAction(
            name="install_or_verify_skills",
            scope="local checkout/environment",
            result=ActionResult.CHANGED if not skill_setup.unchanged else ActionResult.NO_CHANGE,
            detail=skill_setup.message,
        )
    )
    checks.append(
        BootstrapCheck(
            name="project skills installed",
            category=CATEGORY_SKILL_SETUP,
            status=CheckStatus.FIXED if not skill_setup.unchanged else CheckStatus.PASS,
            observed=(
                f"{skill_setup.installed_count} skill file(s) written"
                if not skill_setup.unchanged
                else "skills already current"
            ),
            local_action_allowed=True,
        )
    )

    # 4) Optional capabilities — warnings only.
    checks.extend(_classify_optional_capabilities(probe))

    summary = _summarize(checks, actions, skill_setup)
    return BootstrapRun(
        started_at=started_at,
        checkout_root=project_root,
        mode="install+verify",
        checks=checks,
        actions=actions,
        skill_setup=skill_setup,
        summary=summary,
    )


def _summarize(
    checks: list[BootstrapCheck],
    actions: list[BootstrapAction],
    skill_setup: SkillSetupState,
) -> BootstrapSummary:
    """Compute the final summary from checks, actions, and skill state.

    * ``blocked`` if any required blocker remains (a ``blocked`` check or a
      ``failed`` action). Optional warnings never cause this.
    * ``partial`` if there are optional warnings or session-visibility caveats
      but no required blocker.
    * ``ready`` otherwise.
    """
    blockers: list[str] = []
    for check in checks:
        if check.status is CheckStatus.BLOCKED:
            blockers.append(f"{check.name}: {check.next_action or check.observed}")
    for action in actions:
        if action.result is ActionResult.FAILED:
            blockers.append(f"{action.name}: {action.detail}")

    warnings: list[str] = [
        f"{check.name}: {check.next_action or check.observed}"
        for check in checks
        if check.status is CheckStatus.WARNING
    ]
    # A skill change is a session-visibility caveat, not a blocker.
    if skill_setup.reload_required:
        warnings.append(skill_setup.message)

    if blockers:
        status = SummaryStatus.BLOCKED
        ready = False
        next_step = (
            "Resolve the listed blocker(s), then re-run bootstrap. "
            "Do not start normal Premura operation yet."
        )
    elif warnings:
        status = SummaryStatus.PARTIAL
        ready = True
        next_step = (
            "Local install is ready for normal Premura operation. Review the warning(s); "
            "if skills changed, reload your agent session first. See README/CONTRIBUTING "
            "for the next safe operation step."
        )
    else:
        status = SummaryStatus.READY
        ready = True
        next_step = (
            "Local checkout is ready. Proceed to normal Premura operation per "
            "README/CONTRIBUTING (no health-data ingest is performed by bootstrap)."
        )

    return BootstrapSummary(
        status=status,
        ready_for_operation=ready,
        reload_guidance=(
            "reload required" if skill_setup.reload_required else "reload not required"
        ),
        next_step=next_step,
        blockers=blockers,
        warnings=warnings,
    )
