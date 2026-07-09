"""Driver persona registry (issue #53): the contract a model-backed driver plays.

#10's design needs a driver agent that plays a realistic naive human so the
harness can find where the operator derails - something a canned "proceed"
driver structurally cannot exercise. Per DOCTRINE.md "design a level above", a
persona is a small REGISTRY entry, not driver code: a new persona is added by
registering a :class:`DriverPersona` here, never by editing
:class:`~premura.harness.live_trial_ollama.ModelDriver`.

Every persona carries three contract fields:

* ``goal`` - the operator-facing goal statement (what the driver wants done).
* ``max_turns`` - the improvisation budget: the hard cap on how many operator
  questions the persona will answer before the driver falls back to "proceed"
  (a bounded, never-open-ended conversation).
* ``fixture_facts`` - the ONLY facts the persona may draw on when answering a
  question (e.g. the source file's own column names). This is the honesty
  constraint's raw material: the persona must never invent data the fixture
  does not contain, so its prompt is built ONLY from this bounded fact set,
  never from general world knowledge about the domain.

Personas never see the grader's manifest (mirrors C-005 for the operator side):
``fixture_facts`` is a plain description of what the DROPPED DATA contains, not
the ground-truth mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DriverPersona:
    """One registrable driver persona: goal + improvisation budget + honesty rail.

    ``system_prompt`` is the persona's voice/behavior brief (e.g. "naive,
    impatient, asks short clarifying questions"). ``fixture_facts`` is the
    bounded list of true statements about the dropped data the persona is
    allowed to answer from; anything outside it, the persona must say it does
    not know rather than invent (the honesty constraint).
    """

    name: str
    goal: str
    system_prompt: str
    max_turns: int
    fixture_facts: tuple[str, ...] = field(default_factory=tuple)


# The registry: a new persona is ADDED here, not by forking driver code.
_PERSONAS: dict[str, DriverPersona] = {
    "naive_impatient": DriverPersona(
        name="naive_impatient",
        goal="ingest the heart-rate category from the dropped Fitbit CSV",
        system_prompt=(
            "You are a naive, mildly impatient person who exported their own Fitbit "
            "data and wants their heart-rate readings usable. You are NOT a "
            "programmer. Answer the operator's question in one short sentence, in "
            "plain non-technical language. If the operator asks about a fact you do "
            "not know, say you don't know or don't have that information - NEVER "
            "invent a column name, value, or detail you were not told."
        ),
        max_turns=4,
        fixture_facts=(
            "the file is a CSV export of my Fitbit heart-rate data",
            "it has a timestamp column and a bpm (heart rate) column",
            "I only care about the heart-rate numbers, not confidence or altitude",
        ),
    ),
}


def get_persona(name: str) -> DriverPersona:
    """Resolve a registered persona by name; raise a clear error otherwise."""
    try:
        return _PERSONAS[name]
    except KeyError as exc:
        raise KeyError(
            f"no driver persona registered as {name!r}; register one in "
            f"driver_personas._PERSONAS (known: {sorted(_PERSONAS)})"
        ) from exc


def register_persona(persona: DriverPersona) -> None:
    """Register (or replace) a persona - the extension point for a new persona."""
    _PERSONAS[persona.name] = persona


DEFAULT_PERSONA = "naive_impatient"

__all__ = [
    "DEFAULT_PERSONA",
    "DriverPersona",
    "get_persona",
    "register_persona",
]
