"""Bounded baseline-profile field allowlist for agent-mediated capture.

This module turns the planning allowlist into an enforceable runtime surface.
It answers three questions for the store boundary:

* which baseline profile keys are supported,
* what typed value slot each key expects, and
* which look-alike keys must be rejected outright (for example ``age``).

The allowlist is deliberately small and closed. It is NOT an open-ended profile
key registry: ``record_profile_context`` validates against this surface and
fails on anything it does not recognize, so the bounded character of profile
capture lives here rather than being re-litigated in higher layers.

Why ``age`` is rejected rather than supported: the profile/intake contract
(``docs/building/architecture/contracts/profile_and_intake_examples.yaml``) classifies
``age`` as a *derived* attribute computed from ``birth_date`` and the evaluation
date. Storing it independently would let the two drift apart, so an attempt to
assert ``age`` is a programming error, not a new profile fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProfileValueKind(StrEnum):
    """The typed value slot a supported profile attribute lands in.

    The store maps each kind onto exactly one of the
    ``hp.profile_context_assertion`` typed slots:

    * ``DATE`` -> ``value_date``
    * ``TEXT`` and ``ENUM`` -> ``value_text``
    * ``QUANTITY`` -> ``value_num`` (with ``unit``)
    """

    DATE = "date"
    TEXT = "text"
    ENUM = "enum"
    QUANTITY = "quantity"


@dataclass(frozen=True, slots=True)
class ProfileField:
    """One supported baseline-profile attribute.

    ``attribute_key`` is the stable contract key persisted in
    ``hp.profile_context_assertion.attribute_key``. ``value_kind`` decides which
    typed value slot is populated. ``unit`` is the expected canonical unit for a
    ``QUANTITY`` field and ``None`` otherwise. ``allowed_values`` constrains an
    ``ENUM`` field to a closed set.
    """

    attribute_key: str
    value_kind: ProfileValueKind
    description: str
    unit: str | None = None
    allowed_values: tuple[str, ...] | None = None


# The closed baseline profile surface for this mission. Keep this bounded to
# stable baseline facts; do not grow it into a generic attribute bucket.
_FIELDS: tuple[ProfileField, ...] = (
    ProfileField(
        attribute_key="birth_date",
        value_kind=ProfileValueKind.DATE,
        description="Operator's date of birth; a permanent declared attribute.",
    ),
    ProfileField(
        attribute_key="sex",
        value_kind=ProfileValueKind.ENUM,
        description="Operator's biological sex; a stable declared attribute.",
        allowed_values=("female", "male", "intersex"),
    ),
    ProfileField(
        attribute_key="standing_height_cm",
        value_kind=ProfileValueKind.QUANTITY,
        unit="cm",
        description="Operator's declared standing height, slowly changing over a lifetime.",
    ),
)

SUPPORTED_PROFILE_FIELDS: dict[str, ProfileField] = {f.attribute_key: f for f in _FIELDS}

# Keys that are explicitly rejected because they are derived or otherwise not a
# stored baseline fact. ``age`` is the canonical example: it is derived from
# ``birth_date`` and the evaluation date and must never be asserted directly.
REJECTED_PROFILE_KEYS: frozenset[str] = frozenset({"age"})


class UnsupportedProfileFieldError(ValueError):
    """Raised when a profile attribute_key is not in the bounded allowlist."""


def is_supported(attribute_key: str) -> bool:
    """Return True only for keys in the bounded allowlist."""
    return attribute_key in SUPPORTED_PROFILE_FIELDS


def get_profile_field(attribute_key: str) -> ProfileField:
    """Return the :class:`ProfileField` for a supported key.

    Raises :class:`UnsupportedProfileFieldError` for any key outside the
    allowlist. Explicitly rejected keys (such as ``age``) get a message that
    names why they are not storable.
    """
    field = SUPPORTED_PROFILE_FIELDS.get(attribute_key)
    if field is not None:
        return field
    if attribute_key in REJECTED_PROFILE_KEYS:
        raise UnsupportedProfileFieldError(
            f"profile attribute {attribute_key!r} is derived, not a stored baseline fact; "
            f"derive it instead (e.g. age from birth_date and the evaluation date)"
        )
    raise UnsupportedProfileFieldError(
        f"profile attribute {attribute_key!r} is not in the bounded allowlist; "
        f"supported keys: {sorted(SUPPORTED_PROFILE_FIELDS)}"
    )


def supported_keys() -> tuple[str, ...]:
    """Return the supported attribute keys in declaration order."""
    return tuple(SUPPORTED_PROFILE_FIELDS)


__all__ = [
    "REJECTED_PROFILE_KEYS",
    "SUPPORTED_PROFILE_FIELDS",
    "ProfileField",
    "ProfileValueKind",
    "UnsupportedProfileFieldError",
    "get_profile_field",
    "is_supported",
    "supported_keys",
]
