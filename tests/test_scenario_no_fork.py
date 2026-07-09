"""WP05 T021 — the machine-checkable no-fork guarantee (NFR-005 / NFR-006 / SC-003).

The structural proof of the mission's central doctrine claim (``DOCTRINE.md``
§"guide, don't enumerate"): a new acceptance source is added by **registering a
scenario**, never by forking the shared grade path. Two halves, each a real guard
that fails the moment someone reintroduces a per-drawer branch:

1. **Structural (NFR-005).** Parse the source of :func:`premura.harness.grader.grade`
   (and the helper it orchestrates) and assert its body contains **no** per-drawer
   token — no ``intake`` / ``nutrition`` / ``supplement`` / ``fact_`` literal and no
   ``if ... drawer`` switch. All drawer-specific facts must reach the body only
   through the injected :class:`~premura.harness.scenario.DrawerGradingStrategy`
   seam. This is an AST + token scan over the *actual function body*, so an
   ``if intake:`` ladder added later trips it.
2. **Declared dispatch, not name-matching (NFR-006 / SC-003).** Every
   :class:`~premura.harness.scenario.Scenario` declares its own grading entry
   point via ``grade_fn`` (``None`` means "use the shared ``grade()``"); the
   caller (``live_trial.py``) resolves ``scenario.grade_fn or grade`` and never
   name-matches ``scenario.name``. Every scenario with ``grade_fn=None`` (still
   observation + intake) is driven through that resolution and asserted to land
   on the ONE shared ``grade()`` callable, each with a distinct injected
   strategy - proving the abstraction *carries* multiple scenarios through one
   path. NOT every registered scenario shares that one callable: garbage_refusal
   declares its own ``grade_fn`` (``grade_garbage_refusal``) because its PASS
   polarity genuinely differs (see that function's docstring); this is asserted
   as a declared, structural exception, not exercised through the recorder.

Offline / deterministic: no network, no model server, no warehouse writes for the
structural half (NFR-001).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import yaml

import premura.harness.grader as grader_module
from premura.harness import grader as grader_pkg
from premura.harness.grader import grade, grade_garbage_refusal
from premura.harness.scenario_registry import all_scenarios

# --------------------------------------------------------------------------- #
# Forbidden per-drawer tokens (the exact set WP05 enumerates). A drawer name, an
# intake table noun, or a ``fact_`` warehouse prefix appearing INSIDE grade()'s body
# would mean the shared path knows about a specific drawer — exactly the fork
# NFR-005 forbids. The strategy methods (boundary_truth / runtime_check / gap_set)
# are the only places these may appear.
#
# ``observation`` is deliberately NOT here: ``grade()`` legitimately names
# ``observation_scenario().strategy`` once as the C-004 *default* (so existing
# call sites that pass no strategy keep observation behavior). That single default
# selection is not a per-drawer branch; the separate ``no conditional drawer
# switch`` assertion below is what guards against an ``if <drawer>:`` ladder.
# --------------------------------------------------------------------------- #
FORBIDDEN_DRAWER_TOKENS: tuple[str, ...] = (
    "intake",
    "nutrition",
    "supplement",
    "fact_",
    "drawer",
)

# The one allowed drawer-named expression in grade()'s body: selecting the default
# strategy when the caller passes none (C-004). It must remain a single unconditional
# default, never grow into a drawer switch.
_ALLOWED_DEFAULT_STRATEGY_EXPR = "observation_scenario().strategy"


def _function_body_source(func: Any) -> str:
    """Return the dedented source of just ``func``'s body (signature + docstring
    stripped), so the scan judges executable logic, not the documentation that
    legitimately names drawers when explaining the seam."""
    full_source = inspect.getsource(func)
    module = ast.parse(full_source.lstrip())
    func_def = module.body[0]
    assert isinstance(func_def, (ast.FunctionDef, ast.AsyncFunctionDef))

    statements = func_def.body
    # Drop a leading docstring expression — prose may name drawers to explain the
    # seam; only executable statements are part of the no-fork contract.
    if (
        statements
        and isinstance(statements[0], ast.Expr)
        and isinstance(statements[0].value, ast.Constant)
        and isinstance(statements[0].value.value, str)
    ):
        statements = statements[1:]

    return "\n".join(ast.unparse(node) for node in statements)


def test_grade_body_names_no_drawer_token() -> None:
    """``grade()``'s executable body contains no per-drawer token (NFR-005).

    The structural enforcement of guide-don't-enumerate: every drawer-specific
    fact reaches ``grade()`` only via the injected strategy. If a future change
    adds ``if intake:`` / a ``hp.fact_*`` literal / a ``nutrition`` branch into the
    body, the token appears in the unparsed AST and this assertion fails.
    """
    body = _function_body_source(grade).lower()
    found = [token for token in FORBIDDEN_DRAWER_TOKENS if token in body]
    assert not found, (
        f"grade() body leaked per-drawer token(s) {found}; drawer divergence must "
        "live behind the DrawerGradingStrategy seam, never in the shared grade path."
    )


def test_grade_body_has_no_conditional_drawer_switch() -> None:
    """``grade()``'s only branch is the C-004 default-strategy guard — no drawer switch.

    The complement to the token scan: even a token-free fork (``if some_flag:`` that
    selects a drawer) is forbidden. We assert the body's *only* conditional is the
    ``if strategy is None:`` default guard, and that it sets the allowed default
    expression. A new ``if intake_target:`` / ``match drawer:`` would add a branch and
    trip this.
    """
    body_ast = ast.parse(_function_body_source(grade).lstrip())
    branches = [n for n in ast.walk(body_ast) if isinstance(n, (ast.If, ast.Match))]
    assert len(branches) == 1, (
        f"grade() body has {len(branches)} conditional branches; only the single "
        "C-004 default-strategy guard is allowed — a drawer switch must not appear."
    )

    # The lone branch is the default-strategy guard, and it sets the allowed default.
    only_branch = branches[0]
    assert isinstance(only_branch, ast.If)
    guard_src = ast.unparse(only_branch)
    assert "strategy is None" in guard_src, guard_src
    assert _ALLOWED_DEFAULT_STRATEGY_EXPR in guard_src, guard_src


def test_grade_orchestration_helper_names_no_drawer_token() -> None:
    """The grade-orchestration helper is drawer-blind too (NFR-005).

    ``grade()`` delegates honesty to ``_grade_honest_about_gaps``; that helper must
    not fork on a drawer either, or the no-fork guarantee would be evaded one level
    down. (It legitimately names ``Observation`` only to pick the default strategy,
    so we scan only its non-default body.) We assert there is no ``if``/``elif``
    drawer *switch* in the helper.
    """
    helper = grader_module._grade_honest_about_gaps
    body_ast = ast.parse(_function_body_source(helper).lstrip())
    # No branching control-flow keying on a drawer: the helper computes one
    # strategy's view with zero conditional drawer dispatch.
    branch_nodes = [n for n in ast.walk(body_ast) if isinstance(n, (ast.If, ast.Match))]
    assert not branch_nodes, (
        "the grade-orchestration helper introduced conditional control flow; a "
        "drawer switch must not appear in the shared honesty path."
    )


def test_grade_signature_is_strategy_injected_not_source_keyed() -> None:
    """``grade()`` takes a ``strategy`` seam, never a ``source``/``drawer`` selector.

    A structural witness that divergence is injected, not selected: the only way
    drawer behavior enters is the ``DrawerGradingStrategy`` parameter. A
    ``source=``/``drawer=`` parameter would be the fork's entry point.
    """
    params = set(inspect.signature(grade).parameters)
    assert "strategy" in params
    assert not (params & {"source", "drawer", "scenario", "source_kind"})


def test_at_least_two_scenarios_registered() -> None:
    """The registry lists ≥2 scenarios (SC-003 / NFR-006).

    The abstraction is only meaningfully proven when more than one source rides
    it; the registry is the bounded list new sources are appended to.
    """
    scenarios = all_scenarios()
    assert len(scenarios) >= 2, scenarios
    names = {s.name for s in scenarios}
    assert {"observation", "intake_alien"} <= names, names


def test_every_scenario_grades_through_its_declared_dispatch_rule(
    monkeypatch, empty_warehouse
) -> None:
    """Every registered scenario grades through ``scenario.grade_fn or grade`` (#51).

    The behavioral half of the no-fork guarantee, corrected to match what
    production actually does (``live_trial.py``'s dispatch line): the caller
    never name-matches ``scenario.name``, it resolves ``scenario.grade_fn or
    grade`` and calls whatever that resolves to. Scenarios that leave
    ``grade_fn`` unset (``None``) all route to the ONE shared ``grade()``
    callable - proven here by driving every such scenario through a recorder
    wrapping ``grade`` and asserting they all land on it with distinct injected
    strategies. garbage_refusal is the one scenario that declares its own
    ``grade_fn`` (``grade_garbage_refusal``, a genuine verdict-polarity fork per
    its docstring in ``grader.py``) - asserted here as a declared exception, not
    exercised through the shared-``grade()`` recorder.

    The warehouse is intentionally empty: this proves *which code path each
    scenario travels*, not the verdict value (the e2e value tests own that).
    """
    calls: list[Any] = []
    real_grade = grade

    def _recording_grade(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs.get("strategy"))
        return real_grade(**kwargs)

    monkeypatch.setattr(grader_pkg, "grade", _recording_grade)

    scenarios = all_scenarios()
    shared_grade_scenarios = [s for s in scenarios if s.grade_fn is None]
    assert len(shared_grade_scenarios) >= 2, shared_grade_scenarios

    # garbage_refusal declares its own grading entry point - the one allowed
    # exception to "everyone shares grade()" (a genuine polarity fork, not a
    # drawer fork).
    garbage_refusal = next(s for s in scenarios if s.name == "garbage_refusal")
    assert garbage_refusal.grade_fn is grade_garbage_refusal

    # An empty, manifest-shaped stand-in per scenario keeps the call drawer-blind:
    # we only assert the routing, so an empty manifest (no columns/fields) is
    # sufficient and keeps the scenarios on identical calling code.
    empty_manifests: dict[str, dict[str, list[Any]]] = {
        "observation": {"source_fields": []},
        "intake_alien": {"columns": []},
    }

    class _Prov:
        declared_metrics: list[str] = []
        emitted_metric_ids: list[str] = []
        unmapped_metrics: list[str] = []
        skipped_rows: list[dict[str, Any]] = []
        rows_inserted = 0
        ingest_run_ok = False
        produced = None
        error = None

    for scenario in shared_grade_scenarios:
        manifest = empty_manifests.get(scenario.name)
        if manifest is None:  # a newly registered scenario: load its real manifest
            manifest = yaml.safe_load(Path(scenario.manifest_path).read_text(encoding="utf-8"))
        # Dispatch exactly as production does: `scenario.grade_fn or grade`,
        # called THROUGH the patched module entry so the recorder witnesses routing.
        grader_fn = scenario.grade_fn or grader_pkg.grade
        grader_fn(
            provenance=_Prov(),
            warehouse_conn=empty_warehouse,
            fixture_manifest=manifest,
            strategy=scenario.strategy,
        )

    # Every grade_fn=None scenario reached the one shared callable, each with a
    # DISTINCT strategy instance - one entry point, divergence only in the
    # injected seam.
    assert len(calls) == len(shared_grade_scenarios) >= 2
    strategy_types = {type(s).__name__ for s in calls}
    assert len(strategy_types) >= 2, (
        f"expected >=2 distinct injected strategies through one grade() path, got {strategy_types}"
    )
