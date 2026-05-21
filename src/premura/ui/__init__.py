"""Stage 4 - User interface: the human-facing interview surface for Premura.

This package is the importable home for the fourth stage of the four-stage
architecture (parsers → engine → MCP → UI). Stage 4 is the user's entry
point: it walks the user through an interview keyed on the six health
directions — sleep, energy, mood, movement, recovery, longevity — and asks,
for each direction, which signals to surface and which missing inputs to
prompt the user to gather (a fasting lab, a wearable export, a sleep
tracker, etc.). The UI never assembles signals itself; it asks the MCP
layer, which in turn asks the engine.

The hard layering rule for this stage is, verbatim, that the UI
"never reads hp.fact_measurement or calls engine directly".
All data flows are UI → MCP → engine → warehouse, in that order. Future
implementation missions wire this stub up to a real interview flow (CLI
prompt, web form, or otherwise); Phase 1 ships only the stage's importable
name and a stub entry point.

The name ``ui`` is intentional and authoritative. An earlier draft of the
spec called this stage ``learn``; that name is dead. Any future code or
docs referring to ``learn`` for this stage should be migrated to ``ui``.
"""

from __future__ import annotations

__all__ = ["start_interview"]


def start_interview() -> None:
    """Launch the six-direction health interview.

    Phase 1 stub. The eventual implementation prompts the user across the six
    health directions, calls into the Stage 3 MCP surface for each chosen
    direction, and renders results plus a ``missing_inputs_report`` for any
    signals whose inputs are not yet available. Raises
    :class:`NotImplementedError` until that mission lands.
    """
    raise NotImplementedError(
        "start_interview is a Phase 1 stub; the Stage 4 interview flow "
        "ships in a later implementation mission."
    )
