"""Driver persona registry (#53 / #70): the contract a model-backed driver plays.

Extracted out of ``live_trial_ollama.py`` (#70) so the persona registry - a
guide-don't-enumerate rubric, not driver code - lives in its own AI-navigable
module (DOCTRINE.md "design a level above"). A new persona is added by
registering a :class:`DriverPersona` in :data:`DRIVER_PERSONAS` here, never by
editing :class:`~premura.harness.live_trial_ollama.PersonaDriver`.

Every field is the SAME role for every persona:

* ``name`` - the registry key + the ``model_id`` suffix recorded on the
  session (so persona tiers compare later, FR-031).
* ``goal`` - the human's intent the persona pursues (what it wants ingested).
* ``improv_budget`` - the max number of improvised answers before the persona
  stops and defers to the operator. A code-enforced turn cap, so an operator
  that keeps asking cannot make the driver improvise unboundedly.
* ``persona_brief`` - the character the model plays (a naive human who does not
  speak the operator's jargon). Free prose; never contains fixture ground truth.
* ``known_facts`` - the ONLY data the persona is allowed to state. The honesty
  constraint: the persona answers from these facts and REFUSES to invent
  anything the fixture does not contain. This is what keeps a driven trial
  grounded in the real dropped data instead of hallucinated inputs.

This module owns the persona data + prompt-building only. The model transport
(:class:`~premura.harness.live_trial_ollama.PersonaDriver`) stays in
``live_trial_ollama.py`` since it reuses that module's Ollama transport.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DriverPersona:
    """One naive-human persona the model plays (guide-don't-enumerate contract).

    See module docstring for the role of each field.
    """

    name: str
    goal: str
    improv_budget: int
    persona_brief: str
    known_facts: tuple[str, ...]


# The persona registry: name -> :class:`DriverPersona`. Adding a driver persona
# is registering an entry here (the guide-don't-enumerate surface, DOCTRINE), NOT
# editing PersonaDriver. At least one working persona ships (#53 done-criteria).
DRIVER_PERSONAS: dict[str, DriverPersona] = {
    "naive_fitbit_owner": DriverPersona(
        name="naive_fitbit_owner",
        goal="ingest the heart-rate category from the dropped Fitbit CSV",
        improv_budget=6,
        persona_brief=(
            "You are an ordinary person who exported your own Fitbit data and want "
            "it loaded. You are NOT a programmer: you do not know what a parser, a "
            "schema, a column mapping, or a metric_id is. Answer the operator's "
            "questions plainly and briefly, like a real non-technical human would. "
            "If the operator uses jargon, say you do not understand it and ask them "
            "to handle it. Do not volunteer technical solutions."
        ),
        known_facts=(
            "The export is a CSV of heart-rate readings from a Fitbit wearable.",
            "Each row has a timestamp and a beats-per-minute value.",
            "You only care about the heart-rate data; you did not export anything else.",
        ),
    ),
}

DEFAULT_PERSONA = "naive_fitbit_owner"

# The fixed reply the persona gives once its improvisation budget is spent: it
# stops improvising and hands control back to the operator. Code-enforced, so the
# turn cap is a real ceiling, not a prompt suggestion.
BUDGET_EXHAUSTED_REPLY = "That's all I can tell you - please go ahead with what you have."


def persona_prompt(persona: DriverPersona, question: str) -> str:
    """Build the per-question prompt: persona brief + honesty rule + known facts.

    The honesty constraint is stated explicitly AND bounded by ``known_facts``:
    the persona is told to answer only from those facts and to refuse (say it does
    not know) anything the facts do not cover. The prompt never contains fixture
    ground truth beyond the persona's own ``known_facts`` (C-005 posture: no answer
    key leaks into the driver).
    """
    facts = "\n".join(f"- {fact}" for fact in persona.known_facts)
    return (
        f"{persona.persona_brief}\n\n"
        f"Your goal: {persona.goal}\n\n"
        f"The ONLY things you actually know about your data:\n{facts}\n\n"
        "HONESTY RULE: answer ONLY from the facts above. If the operator asks about "
        "anything not covered by those facts, you MUST say you do not know / do not "
        "have that - NEVER make up a value, a column, a date, or any detail that is "
        "not listed above.\n\n"
        f"The operator asks you:\n{question}\n\n"
        "Reply in one or two short sentences, in plain non-technical language."
    )


__all__ = [
    "BUDGET_EXHAUSTED_REPLY",
    "DEFAULT_PERSONA",
    "DRIVER_PERSONAS",
    "DriverPersona",
    "persona_prompt",
]
