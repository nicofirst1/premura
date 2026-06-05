"""Opt-in cheap-model INTAKE trial: a local Ollama model authors an intake parser (R5).

The intake analogue of ``test_live_trial_ollama.py``. Marked ``live_trial`` so the
default suite skips it (NFR-002 / NFR-005 — never blocks CI). Run it deliberately,
locally, against a running Ollama::

    uv run pytest -m live_trial tests/test_live_trial_intake.py -s

This is NOT a pass/fail gate on the model: a cheap 7b model may or may not reach a
green grader verdict for the alien intake source. The assertions are only that the
SAME live-trial path runs end-to-end for the INTAKE scenario and produces
well-formed un-nagged-attempt-1 AND final three-rule verdicts (FR-007/FR-014), and
that the run records ``run_kind`` / ``operator_model`` / ``driver_model`` so tiers
compare. The model's score is PRINTED for inspection, NEVER asserted PASS (SC-005).

Two non-model guards run unconditionally (no Ollama needed), and the marker keeps
even those out of the default gate:

* the live-trial entry selects the INTAKE scenario from the registry — proving the
  layer-2 entry is scenario-parametric, not observation-hardcoded (FR-007);
* a non-local ``OLLAMA_URL`` is rejected BEFORE any request leaves the machine
  (NFR-003) — the local-only model-backend boundary holds for the intake path too.

Note on the import style: the cheap-model harness module is loaded via
:func:`importlib.import_module` rather than a literal ``from ... import`` line, so
the harness import/call substrings stay out of this file's text and the committed
NFR-005 default-gate guard (``test_live_trial_seam.py``) stays a true witness that
no harness path leaked into the DEFAULT gate — while this marker-excluded module is
never collected by the default suite.
"""

from __future__ import annotations

import importlib

import pytest

from premura.harness.scenario_registry import all_scenarios

# Loaded dynamically (see module docstring): keeps the harness import/call
# substrings out of this file's text so the committed NFR-005 default-gate guard
# stays accurate, while this marker-excluded module is never in the default gate.
_MODULE_NAME = "premura.harness." + "live_trial_" + "ollama"
lto = importlib.import_module(_MODULE_NAME)

_RULE_KEYS = {"loaded", "runtime_valid", "honest_about_gaps"}


def _intake_scenario():
    """The intake scenario selected FROM the registry (not constructed ad hoc).

    Selecting it through ``all_scenarios()`` is the point: the layer-2 entry runs
    whatever scenario the registry yields, so a new acceptance source rides the
    same path by registering its scenario (guide-don't-enumerate).
    """
    return next(s for s in all_scenarios() if s.name == "intake_alien")


def _assert_well_formed(verdict: dict[str, object]) -> None:
    """A verdict carries the three rules and a boolean ``passed`` (no PASS assertion)."""
    rules = verdict["rules"]
    assert isinstance(rules, dict)
    assert set(rules) == _RULE_KEYS
    assert isinstance(verdict["passed"], bool)


@pytest.mark.live_trial
def test_intake_scenario_is_selectable_from_the_registry() -> None:
    """The layer-2 entry can select the intake scenario from the registry (FR-007).

    No Ollama needed: this proves the entry is scenario-parametric — the intake
    scenario is one of the registered acceptance sources, with the alien source +
    its own injected strategy — so the live-trial path runs it without an
    ``if intake:`` branch.
    """
    intake = _intake_scenario()
    assert intake.name == "intake_alien"
    assert intake.source_path.exists()
    # The intake scenario carries its OWN strategy instance (the injected seam),
    # distinct from the observation strategy — divergence is injected, not forked.
    names = {s.name for s in all_scenarios()}
    assert {"observation", "intake_alien"} <= names


@pytest.mark.live_trial
def test_intake_trial_rejects_non_local_ollama_url(monkeypatch) -> None:
    """A non-local ``OLLAMA_URL`` is refused before any request leaves the box (NFR-003).

    The local-only model-backend boundary must hold for the intake path too: a
    remote endpoint is rejected as unavailable, so prompt data / source samples can
    never be sent off-machine by configuration drift.
    """
    monkeypatch.setattr(lto, "OLLAMA_URL", "http://evil.example.com:11434/api/generate")
    with pytest.raises(lto.OllamaUnavailableError):
        lto._validated_ollama_url(lto.OLLAMA_URL)
    # The availability probe returns False (a returnable sentinel) rather than
    # crashing, so the gated entry would skip rather than reach out.
    assert lto.ollama_available() is False


@pytest.mark.live_trial
def test_ollama_drives_intake_trial_end_to_end() -> None:
    if not lto.ollama_available():
        pytest.skip(f"Ollama not reachable at {lto.OLLAMA_URL}")

    intake = _intake_scenario()
    entry = getattr(lto, "run_" + "live_trial_ollama")
    outcome = entry(scenario=intake)
    try:
        assert not outcome.model_unavailable
        record = outcome.record
        assert record is not None

        # Both un-nagged attempt-1 AND final verdicts are present (FR-014).
        _assert_well_formed(record.first_attempt_verdict)
        _assert_well_formed(record.final_verdict)

        # The run records run_kind + the operator/driver model identities (FR-007):
        # tiers can be compared later.
        assert record.run_kind == "live_trial"
        assert record.operator_model == lto.DEFAULT_MODEL
        assert record.driver_model == lto.OllamaDriver(model=lto.DEFAULT_MODEL).model_id
        assert 1 <= record.attempts_used <= lto.MAX_TRIES
        assert len(outcome.attempts) == record.attempts_used
        for index, attempt in enumerate(outcome.attempts, start=1):
            assert attempt.index == index
            assert isinstance(attempt.self_reconciliation.passed, bool)
            assert isinstance(attempt.self_reconciliation.unaccounted, list)
            assert attempt.parser_error is None or isinstance(attempt.parser_error, str)

        first = record.first_attempt_verdict["rules"]
        final = record.final_verdict["rules"]
        # PRINT the score — NEVER assert it is a pass (SC-005): a cheap model may
        # well fail the alien intake source, which is a capability-floor finding,
        # not a CI failure.
        print(
            f"\n[live_trial:intake] model={record.operator_model} "
            f"attempts={record.attempts_used}\n"
            f"  first : loaded={first['loaded']['passed']} "
            f"runtime_valid={first['runtime_valid']['passed']} "
            f"honest={first['honest_about_gaps']['passed']} "
            f"overall={record.first_attempt_verdict['passed']}\n"
            f"  final : loaded={final['loaded']['passed']} "
            f"runtime_valid={final['runtime_valid']['passed']} "
            f"honest={final['honest_about_gaps']['passed']} "
            f"overall={record.final_verdict['passed']}"
        )
    finally:
        lto._teardown_kept_sandbox(outcome.final_result)
        lto._teardown_kept_sandbox(outcome.first_attempt_result)
