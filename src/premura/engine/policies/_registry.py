"""Lightweight Stage 2 policy registry (WP03).

A registry is a deterministic, fail-loud lookup from metric family to its
:class:`MetricFamilyPolicy` declaration. It is intentionally small: it does not
evaluate evidence (the WP02 evaluator owns all branching) and it does not read
the warehouse or the network.

Two mistakes a future agent is most likely to make are caught at registration
time, with messages specific enough to fix the declaration from the exception:

* a duplicate ``policy_id`` (two declarations claiming the same identity), and
* duplicate metric-family ownership (two policies both claiming one family).

Both raise rather than silently overwriting an earlier declaration — accidental
duplicate registration must never quietly win. Lookup by family is **exact**
(no fuzzy matching) so the evaluator never has to infer a family from a name.
"""

from __future__ import annotations

from collections.abc import Iterable

from premura.engine.policies._defaults import builtin_policies
from premura.engine.policies._model import MetricFamilyPolicy


class DuplicatePolicyError(ValueError):
    """Raised when a registration would collide with an existing policy.

    Covers both a duplicate ``policy_id`` and duplicate metric-family
    ownership. A ``ValueError`` subclass so callers expecting the model's
    construction-time ``ValueError`` style still catch it.
    """


class PolicyRegistry:
    """A fail-loud, deterministic family -> policy registry.

    Registration order is preserved so :meth:`policies` and :meth:`families`
    return a stable, reproducible order regardless of dict iteration details.
    """

    def __init__(self) -> None:
        self._by_family: dict[str, MetricFamilyPolicy] = {}
        self._policy_ids: set[str] = set()
        self._order: list[str] = []

    def register(self, policy: MetricFamilyPolicy) -> None:
        """Register one policy, failing loudly on any collision.

        Raises
        ------
        DuplicatePolicyError
            If ``policy.policy_id`` is already registered, or if another policy
            already owns ``policy.metric_family``. The model does not declare
            family aliases, so one family maps to exactly one policy.
        """
        if policy.policy_id in self._policy_ids:
            raise DuplicatePolicyError(
                f"duplicate policy_id {policy.policy_id!r}: a policy with this "
                "id is already registered; policy ids must be unique"
            )
        if policy.metric_family in self._by_family:
            existing = self._by_family[policy.metric_family]
            raise DuplicatePolicyError(
                f"duplicate metric-family ownership for "
                f"{policy.metric_family!r}: already owned by policy "
                f"{existing.policy_id!r}. One family maps to exactly one "
                "policy (the model declares no family aliases); registering a "
                "second would silently overwrite the first"
            )
        self._policy_ids.add(policy.policy_id)
        self._by_family[policy.metric_family] = policy
        self._order.append(policy.metric_family)

    def register_all(self, policies: Iterable[MetricFamilyPolicy]) -> None:
        """Register many policies in order, failing loudly on the first clash."""
        for policy in policies:
            self.register(policy)

    def get(self, metric_family: str) -> MetricFamilyPolicy | None:
        """Return the policy owning ``metric_family`` by exact match, else None.

        Lookup is exact: there is no fuzzy/prefix matching, so an unknown family
        cleanly returns ``None`` (and the evaluator turns that into an
        unsupported-policy refusal) rather than silently using a near match.
        """
        return self._by_family.get(metric_family)

    def policies(self) -> tuple[MetricFamilyPolicy, ...]:
        """Return all registered policies in deterministic registration order."""
        return tuple(self._by_family[family] for family in self._order)

    def families(self) -> tuple[str, ...]:
        """Return all owned metric families in deterministic registration order."""
        return tuple(self._order)

    def __len__(self) -> int:
        return len(self._order)

    def __contains__(self, metric_family: object) -> bool:
        return metric_family in self._by_family


def build_builtin_registry() -> PolicyRegistry:
    """Build a registry pre-loaded with all built-in family defaults.

    Convenience entrypoint for the evaluator and for callers who want Premura's
    shipped admissibility defaults. Construction fails loudly if the built-ins
    ever introduce a duplicate, so a packaging mistake cannot ship silently.
    """
    registry = PolicyRegistry()
    registry.register_all(builtin_policies())
    return registry


__all__ = [
    "DuplicatePolicyError",
    "PolicyRegistry",
    "build_builtin_registry",
]
