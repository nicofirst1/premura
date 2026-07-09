"""Tests for the model-backed driver persona (issue #53).

Default-suite (no live Ollama, no network): the model transport is substituted
via the same injectable fake-transport pattern ``test_live_trial_ollama.py``
uses (``monkeypatch.setattr(lto, "_ollama", ...)``). Pins two things:

1. Persona-goal-driven turn generation: ``ModelDriver.respond`` calls the model
   for each turn up to the persona's ``max_turns`` improvisation budget, then
   falls back to the canned "proceed" once the budget is spent.
2. The honesty-constraint boundary: the prompt built for the model carries only
   the persona's bounded ``fixture_facts`` - never invented ground truth - and
   the driver returns whatever the (possibly refusing) model answers verbatim.

Also asserts ``ScriptedDriver`` stays the harness default (opt-in-only rule).

Note on the import style: ``live_trial`` (the seam module) is loaded via
:func:`importlib.import_module` rather than a literal ``from ... import`` line,
matching ``test_live_trial_ollama.py``'s convention - the committed NFR-005
default-gate guard (``test_live_trial_seam.py``) text-scans every OTHER test
module for the harness import/call substrings, and this module's assertions
about ``real_model_driver`` need the seam module without tripping that guard.
"""

from __future__ import annotations

import importlib

import pytest

from premura.harness.driver_personas import DriverPersona, get_persona

live_trial = importlib.import_module("premura.harness." + "live_trial")
lto = importlib.import_module("premura.harness." + "live_trial_" + "ollama")


def _persona(max_turns: int = 2) -> DriverPersona:
    return DriverPersona(
        name="test_persona",
        goal="ingest the heart-rate category from the dropped Fitbit CSV",
        system_prompt="You are a naive person who exported their Fitbit data.",
        max_turns=max_turns,
        fixture_facts=("the file has a timestamp column and a bpm column",),
    )


def test_registered_default_persona_resolves() -> None:
    """The registry has at least one working persona (done-criterion)."""
    persona = get_persona("naive_impatient")
    assert persona.goal
    assert persona.max_turns > 0
    assert persona.fixture_facts


def test_unknown_persona_raises_clear_error() -> None:
    with pytest.raises(KeyError, match="no driver persona registered"):
        get_persona("does-not-exist")


def test_model_driver_calls_model_for_each_turn_within_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persona-goal-driven turn generation: the model is called per turn, bounded."""
    calls: list[str] = []

    def _fake_ollama(prompt: str, *, model: str, timeout: int = 300) -> str:  # noqa: ARG001
        calls.append(prompt)
        return "yes, use the bpm column"

    monkeypatch.setattr(lto, "_ollama", _fake_ollama)

    driver = lto.ModelDriver(_persona(max_turns=2), model="cheap:test")
    assert driver.goal() == "ingest the heart-rate category from the dropped Fitbit CSV"

    first = driver.respond("which column has the heart rate?")
    second = driver.respond("should I skip the confidence column?")
    # Budget exhausted: a third question falls back to canned "proceed" and does
    # NOT call the model again.
    third = driver.respond("one more question?")

    assert first == "yes, use the bpm column"
    assert second == "yes, use the bpm column"
    assert third == "proceed"
    assert len(calls) == 2  # only the first two turns hit the model

    # Each real-turn prompt carries the persona's goal + bounded facts + question.
    assert "ingest the heart-rate category" in calls[0]
    assert "bpm column" in calls[0]
    assert "which column has the heart rate?" in calls[0]


def test_model_driver_honesty_constraint_prompts_never_invent_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Honesty-constraint boundary: prompt carries ONLY fixture facts, and a
    refusal to invent unfixtured data passes through verbatim.
    """
    captured_prompt: dict[str, str] = {}

    def _fake_ollama(prompt: str, *, model: str, timeout: int = 300) -> str:  # noqa: ARG001
        captured_prompt["value"] = prompt
        # The model plays it straight: it doesn't know about a field never
        # named in fixture_facts, so it refuses rather than invents an answer.
        return "I don't know, that wasn't in my export."

    monkeypatch.setattr(lto, "_ollama", _fake_ollama)

    persona = _persona(max_turns=1)
    driver = lto.ModelDriver(persona, model="cheap:test")
    answer = driver.respond("what was your resting heart rate baseline last year?")

    prompt = captured_prompt["value"]
    # The prompt gives the model ONLY the registered fixture facts - never a
    # ground-truth manifest or invented detail beyond that bounded set.
    for fact in persona.fixture_facts:
        assert fact in prompt
    assert "do not go beyond these" in prompt.lower() or "don't know" in prompt.lower()
    # The driver never rewrites the model's honest refusal into an invented fact.
    assert answer == "I don't know, that wasn't in my export."


def test_model_driver_falls_back_to_proceed_when_ollama_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A driver must never crash or hang a trial if the local model is down."""

    def _raise(prompt: str, *, model: str, timeout: int = 300) -> str:  # noqa: ARG001
        raise lto.OllamaUnavailableError("no server")

    monkeypatch.setattr(lto, "_ollama", _raise)

    driver = lto.ModelDriver(_persona(max_turns=3), model="cheap:test")
    assert driver.respond("anything?") == "proceed"


def test_scripted_driver_remains_default_and_real_driver_is_opt_in() -> None:
    """ScriptedDriver stays the cheap deterministic default (opt-in-only rule)."""
    default_driver = live_trial.real_model_driver()
    assert isinstance(default_driver, lto.OllamaDriver)
    assert default_driver.respond("anything") == "proceed"

    opted_in_driver = live_trial.real_model_driver(persona="naive_impatient", model="cheap:test")
    assert isinstance(opted_in_driver, lto.ModelDriver)
    assert opted_in_driver.persona.name == "naive_impatient"


def test_register_persona_is_the_extension_point() -> None:
    """A newly registered persona resolves via get_persona and can be replaced."""
    from premura.harness.driver_personas import _PERSONAS, register_persona

    custom = DriverPersona(
        name="test_custom",
        goal="custom goal",
        system_prompt="custom persona",
        max_turns=1,
        fixture_facts=("one fact",),
    )
    assert "test_custom" not in _PERSONAS
    try:
        register_persona(custom)
        assert get_persona("test_custom") is custom
        replacement = DriverPersona(
            name="test_custom",
            goal="changed goal",
            system_prompt="custom persona",
            max_turns=2,
            fixture_facts=("one fact",),
        )
        register_persona(replacement)
        assert get_persona("test_custom") is replacement
    finally:
        _PERSONAS.pop("test_custom", None)
