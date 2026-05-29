"""Public-surface tests for the Stage 2 evidence-admissibility policy seam.

These tests lock the *contributor* surface of the policy machinery through
public ``premura.engine`` imports only — the same discipline as
``tests/test_engine_input_resolution_surface.py``. A future policy author must
be able to author a declaration, evaluate candidates, and reach the shipped
defaults without ever importing a private ``premura.engine.policies._*`` module.

Two structural guarantees are asserted alongside the import surface:

* Importing ``premura.engine`` performs **no** network call and requires **no**
  PubMed tooling. PubMed MCP is an agent-side authoring/review aid, never a
  Stage 2 runtime dependency.
* Importing the policy exports does **not** eagerly load the built-in signal or
  resolver registries — the lazy-load posture documented in the engine module
  must survive the policy surface being added to ``__all__``.
"""

from __future__ import annotations

import sys

import pytest

# ---------------------------------------------------------------------------
# 1. Policy enums / dataclasses import from the public engine surface
# ---------------------------------------------------------------------------


def test_policy_surface_imports_from_premura_engine() -> None:
    """The stable policy vocabulary + dataclasses are reachable publicly.

    A policy author imports these names to *author* a declaration; locking them
    here means a refactor that demotes one to a private module is caught.
    """
    from premura.engine import (
        CAVEAT_REQUIRED_SHAPES,
        Admissibility,
        EvaluationResult,
        EvidenceCandidate,
        EvidenceOutcome,
        EvidenceStatus,
        FreshnessMode,
        FreshnessRule,
        MetricFamilyPolicy,
        MissingDataBehavior,
        PolicyExample,
        PolicyShape,
        QuestionRule,
        QuestionType,
        RefusalMode,
        RejectionReason,
        SufficiencyRule,
        TemporalMeaning,
    )

    # Closed vocabularies are real enums with members, not bare placeholders.
    assert len(list(QuestionType)) > 0
    assert len(list(RejectionReason)) > 0
    assert len(list(EvidenceStatus)) > 0

    # The authoring dataclasses are frozen declarations (no executable logic).
    assert MetricFamilyPolicy.__dataclass_params__.frozen is True
    assert QuestionRule.__dataclass_params__.frozen is True
    assert FreshnessRule.__dataclass_params__.frozen is True
    assert SufficiencyRule.__dataclass_params__.frozen is True
    assert PolicyExample.__dataclass_params__.frozen is True

    # The remaining names exist as the contributor surface promises.
    assert Admissibility is not None
    assert FreshnessMode is not None
    assert MissingDataBehavior is not None
    assert RefusalMode is not None
    assert PolicyShape is not None
    assert TemporalMeaning is not None
    assert EvidenceCandidate is not None
    assert EvidenceOutcome is not None
    assert EvaluationResult is not None
    assert CAVEAT_REQUIRED_SHAPES is not None


def test_policy_surface_names_are_listed_in_engine_all() -> None:
    """Every policy export is in ``__all__`` so ``import *`` and tooling see it."""
    import premura.engine as engine

    expected = {
        "QuestionType",
        "EvidenceStatus",
        "RejectionReason",
        "FreshnessMode",
        "Admissibility",
        "TemporalMeaning",
        "PolicyShape",
        "MissingDataBehavior",
        "RefusalMode",
        "CAVEAT_REQUIRED_SHAPES",
        "FreshnessRule",
        "SufficiencyRule",
        "QuestionRule",
        "PolicyExample",
        "MetricFamilyPolicy",
        "EvidenceCandidate",
        "EvidenceOutcome",
        "EvaluationResult",
        "evaluate_evidence",
        "BUILTIN_POLICIES",
        "builtin_policies",
        "PolicyRegistry",
        "DuplicatePolicyError",
        "build_builtin_registry",
    }
    assert expected <= set(engine.__all__)


# ---------------------------------------------------------------------------
# 2. Evaluator helper imports from the public engine surface
# ---------------------------------------------------------------------------


def test_evaluator_helper_imports_from_premura_engine() -> None:
    """``evaluate_evidence`` is the single public evaluation entrypoint.

    Contributors must reach the evaluator through ``premura.engine``, not
    ``premura.engine.policies._evaluator``.
    """
    from premura.engine import evaluate_evidence

    assert callable(evaluate_evidence)


def test_public_surface_supports_author_and_evaluate_round_trip() -> None:
    """The public exports are sufficient to author a policy and evaluate it.

    This is the edge case the WP calls out: a future agent should not need any
    private import to (a) build a candidate, (b) reuse a shipped family policy,
    and (c) run the evaluator. We assert the call succeeds and returns the
    public result envelope — behavioral depth lives in the evaluator tests.
    """
    from datetime import UTC, datetime

    from premura.engine import (
        BUILTIN_POLICIES,
        EvaluationResult,
        EvidenceCandidate,
        evaluate_evidence,
    )

    reference_time = datetime(2026, 1, 1, tzinfo=UTC)
    policy = BUILTIN_POLICIES[0]
    question_type = next(iter(policy.question_rules))
    candidate = EvidenceCandidate(
        metric_id=f"{policy.metric_family}-probe",
        metric_family=policy.metric_family,
        value_kind="scalar",
        observed_at=reference_time,
    )

    result = evaluate_evidence(
        question_type,
        [candidate],
        policy,
        reference_time=reference_time,
    )

    assert isinstance(result, EvaluationResult)


# ---------------------------------------------------------------------------
# 3. Built-in defaults + registry import from the public engine surface
# ---------------------------------------------------------------------------


def test_builtin_policy_lookup_available_from_public_surface() -> None:
    """The shipped family defaults and registry are publicly reachable.

    WP03 exposes the built-in list and a registry/lookup; a policy author reuses
    an existing family rather than reinventing one, so these must be public.
    """
    from premura.engine import (
        BUILTIN_POLICIES,
        MetricFamilyPolicy,
        PolicyRegistry,
        build_builtin_registry,
        builtin_policies,
    )

    assert len(BUILTIN_POLICIES) > 0
    assert all(isinstance(p, MetricFamilyPolicy) for p in BUILTIN_POLICIES)
    # The callable form returns the same shipped declarations.
    assert tuple(builtin_policies()) == tuple(BUILTIN_POLICIES)

    registry = build_builtin_registry()
    assert isinstance(registry, PolicyRegistry)
    # Every shipped family is looked up through the registry without spelunking.
    for policy in BUILTIN_POLICIES:
        assert policy.metric_family in registry


# ---------------------------------------------------------------------------
# 4. No PubMed / network runtime dependency
# ---------------------------------------------------------------------------


def test_engine_import_does_not_require_pubmed_runtime() -> None:
    """Importing ``premura.engine`` must not pull in PubMed or network modules.

    PubMed MCP supports policy authoring/review *outside* runtime; Stage 2 must
    never call PubMed at runtime. The durable proof is that no PubMed/MCP/HTTP
    module is resident after a *fresh* interpreter imports the engine and
    touches the policy surface.

    Run in a clean subprocess: in the full test run, sibling MCP tests have
    already loaded ``mcp``/``httpx`` into this interpreter's ``sys.modules``, so
    scanning the live process would report their imports, not the engine's.
    """
    import subprocess

    code = (
        "import sys;"
        "import premura.engine;"
        "from premura.engine import evaluate_evidence, BUILTIN_POLICIES;"
        "forbidden = ('pubmed', 'mcp', 'entrez', 'httpx', 'aiohttp');"
        "leaked = sorted(n for n in sys.modules"
        " if any(t in n.lower() for t in forbidden));"
        "assert leaked == [], 'engine import leaked: ' + repr(leaked);"
        "print('ok')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"


def test_evaluator_does_not_call_network_at_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """A boundary sentinel: evaluating evidence must not open a socket.

    Patched only at the socket boundary (not at any engine internal) so the
    test does not overfit to import structure. If the evaluator ever reached
    for the network, ``socket.socket`` would fire and fail the run.
    """
    import socket
    from datetime import UTC, datetime

    from premura.engine import BUILTIN_POLICIES, EvidenceCandidate, evaluate_evidence

    def _forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("Stage 2 evidence evaluation must not open a socket")

    monkeypatch.setattr(socket, "socket", _forbidden)

    reference_time = datetime(2026, 1, 1, tzinfo=UTC)
    policy = BUILTIN_POLICIES[0]
    question_type = next(iter(policy.question_rules))
    candidate = EvidenceCandidate(
        metric_id=f"{policy.metric_family}-probe",
        metric_family=policy.metric_family,
        value_kind="scalar",
        observed_at=reference_time,
    )

    # Must complete without touching the patched socket boundary.
    evaluate_evidence(
        question_type,
        [candidate],
        policy,
        reference_time=reference_time,
    )


# ---------------------------------------------------------------------------
# 5. Policy surface does not disturb lazy signal/resolver loading
# ---------------------------------------------------------------------------


def test_policy_exports_do_not_eagerly_load_signal_registry() -> None:
    """Importing the policy surface must leave the signal registry empty.

    The engine's open-boundary promise is that ``REGISTRY`` stays empty until a
    query/compute helper needs the built-in signals. Adding the policy exports
    to ``__all__`` must not smuggle in an eager built-in-signal import.

    Run in a clean subprocess so a sibling test that already triggered the lazy
    loader cannot mask a regression here.
    """
    import subprocess

    code = (
        "import premura.engine as e;"
        # touch the policy surface explicitly
        "from premura.engine import evaluate_evidence, BUILTIN_POLICIES, MetricFamilyPolicy;"
        # the built-in signal AND resolver registries must still be empty
        "assert len(e.REGISTRY) == 0, e.REGISTRY;"
        "assert len(e.RESOLVERS) == 0, e.RESOLVERS;"
        "assert e._BUILTINS_LOADED is False;"
        "assert e._RESOLVERS_LOADED is False;"
        "print('ok')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"
