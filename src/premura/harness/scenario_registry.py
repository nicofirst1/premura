"""The acceptance-scenario registry — the bounded list a new source is added TO.

``all_scenarios()`` is the single place that enumerates the registered acceptance
:class:`~premura.harness.scenario.Scenario` objects. Adding a new source is
appending its factory here (and writing its strategy/fixture), **not** editing the
shared grader: the grader iterates whatever this registry returns and stays
drawer-agnostic (guide-don't-enumerate).

Today it lists the observation scenario and the intake scenario — the
≥ 2-scenarios surface the structural test asserts over. The
module is intentionally import-light (each factory is import-light) so the live
harness path can iterate scenarios without pulling in Ollama or the network.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from premura.harness.garbage_strategy import garbage_scenario
from premura.harness.intake_strategy import intake_scenario
from premura.harness.scenario import observation_scenario

if TYPE_CHECKING:
    from premura.harness.scenario import Scenario


def all_scenarios() -> list[Scenario]:
    """Return every registered acceptance scenario (observation + intake + garbage).

    The registry surface: a list a new source is appended to, not
    an ``if/elif`` over source names baked into the grader. Order is stable
    (observation, intake, then garbage_refusal) so callers that index or report over
    it are deterministic.
    """
    return [observation_scenario(), intake_scenario(), garbage_scenario()]


__all__ = ["all_scenarios"]
