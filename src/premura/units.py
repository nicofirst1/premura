"""Shared unit spelling normalization and value conversion.

Single home for both: `normalize_unit` maps a raw unit spelling (as observed
in a source document) to its canonical spelling; `convert` maps a value from
one canonical spelling to another, per-metric where the relationship is not
metric-agnostic.

This is a byte-identical port of logic formerly duplicated in
`parsers/lab_pdf.py` (`_normalize_unit`, `_convert_value_to_canonical`,
`_UNIT_ALIASES`) and `parsers/bmt.py` (`_convert_to_canonical`).

To add a new conversion: add an entry to `_SIMPLE_FACTORS` if the factor is
metric-agnostic (e.g. length, mass), to `_METRIC_SCOPED` if the factor/divisor
only holds for specific metrics (e.g. molar mass conversions), or to
`_AFFINE` for a non-multiplicative (a*x + b) relationship. An unregistered
(from_unit, to_unit[, metric_id]) combination returns `None` — never guess,
never pass through.
"""

from __future__ import annotations

import re
import unicodedata

# Raw spelling -> canonical spelling. Union of lab_pdf._UNIT_ALIASES and the
# unit spellings bmt.py accepted. Case-sensitive German CBC entries (G/l,
# T/l) are checked before lowercasing since lower-case g/l means something
# different (grams per litre, for proteins).
_CASE_SENSITIVE_ALIASES = {
    "G/l": "10^9_per_l",
    "T/l": "10^12_per_l",
}

_ALIASES = {
    "%": "pct",
    "pct": "pct",
    "eu/dl": "EU_per_dl",
    "f": "fl",
    "fl": "fl",
    "pg": "pg",
    "pg/eritr": "pg",
    "pg/eritr.": "pg",
    "pg/ml": "pg_per_ml",
    "g/dl": "g_per_dl",
    "gr/dl": "g_per_dl",
    "g/g": "ug_per_g",
    "g/100g": "g_per_100g",
    "g/l": "g_per_l",
    "iu/ml": "IU_per_ml",
    "ui/ml": "IU_per_ml",
    "k/ul": "10^9_per_l",
    "k/microl": "10^9_per_l",
    "k/microl.": "10^9_per_l",
    "m/ul": "10^12_per_l",
    "meq/l": "mEq_per_l",
    "mila/mmc": "10^9_per_l",
    "mg/dl": "mg_per_dl",
    "mg/l": "mg_per_l",
    "mg/1": "mg_per_l",
    "miu/l": "mIU_per_l",
    "miu/ml": "mIU_per_ml",
    "microiu/ml": "mIU_per_ml",
    "microu/ml": "microU_per_ml",
    "ml/min/1.73m2": "ml_per_min_per_173m2",
    "mm/h": "mm_per_h",
    "mmol/l": "mmol_per_l",
    "mmol/mol": "mmol_per_mol",
    "mu/l": "mU_per_l",
    "mu/ml": "mU_per_ml",
    "u/l": "U_per_l",
    "u/": "U_per_l",
    "ng/dl": "ng_per_dl",
    "ng/ml": "ng_per_ml",
    "pmol/l": "pmol_per_l",
    "sec": "s",
    "sek": "s",
    "t/l": "10^12_per_l",
    "ug/g": "ug_per_g",
    "ug/dl": "ug_per_dl",
    "ug/l": "ug_per_l",
    "ug/ml": "ug_per_ml",
    "umol/l": "umol_per_l",
    "molli": "umol_per_l",
    "/nl": "10^9_per_l",
    "/pl": "10^12_per_l",
    "10^9/l": "10^9_per_l",
    "10^12/l": "10^12_per_l",
    "10e9/l": "10^9_per_l",
    "10e12/l": "10^12_per_l",
    # bmt.py spellings (lowercased raw -> canonical); numeric factors for
    # these pairs live in _SIMPLE_FACTORS below.
    "kg": "kg",
    "lb": "lb",
    "lbs": "lb",
    "g": "g",
    "m": "m",
    "cm": "cm",
    "mm": "mm",
    "in": "in",
    "inch": "in",
    "inches": "in",
}

# Metric-agnostic (from, to) -> multiplicative factor.
_SIMPLE_FACTORS: dict[tuple[str, str], float] = {
    ("mg_per_l", "mg_per_dl"): 0.1,
    ("mg_per_dl", "mg_per_l"): 10.0,
    ("g_per_l", "g_per_dl"): 0.1,
    ("ug_per_l", "ng_per_ml"): 1.0,
    ("mg_per_l", "ug_per_dl"): 100.0,
    ("mU_per_ml", "U_per_l"): 1.0,
    ("mU_per_l", "mIU_per_l"): 1.0,
    ("microU_per_ml", "mIU_per_l"): 1.0,
    ("mIU_per_ml", "mIU_per_l"): 1000.0,
    # bmt.py mass/length conversions.
    ("lb", "kg"): 0.45359237,
    ("cm", "m"): 0.01,
    ("in", "m"): 0.0254,
    ("in", "cm"): 2.54,
    ("m", "cm"): 100.0,
}

# Metric-agnostic (from, to) -> divisor. Kept separate from _SIMPLE_FACTORS
# (rather than pre-inverted to a factor) to reproduce the original bmt.py
# division exactly — dividing and multiplying by the reciprocal differ at
# the float ULP.
_SIMPLE_DIVISORS: dict[tuple[str, str], float] = {
    ("g", "kg"): 1000.0,
    ("mm", "cm"): 10.0,
}

# (from, to) -> {metric_id: factor-or-divisor}. `convert` below dispatches
# through equivalence, divisor, then factor shapes in that order, matching
# the original per-call-site logic.
_METRIC_SCOPED_EQUIVALENT: dict[tuple[str, str], set[str]] = {
    ("mEq_per_l", "mmol_per_l"): {"lab:sodium", "lab:potassium"},
}

_METRIC_SCOPED_DIVISOR: dict[tuple[str, str], dict[str, float]] = {
    ("mg_per_l", "mmol_per_l"): {
        "lab:sodium": 22.98976928,
        "lab:potassium": 39.0983,
    },
}

_METRIC_SCOPED_FACTOR: dict[tuple[str, str], dict[str, float]] = {
    ("mmol_per_l", "mg_per_dl"): {
        "lab:calcium": 4.008,
        "lab:magnesium": 2.431,
        "lab:phosphorus": 3.097,
    },
    ("pmol_per_l", "pg_per_ml"): {"lab:vitamin_b12": 1.355},
}

# (from, to) -> {metric_id: (a, b)} for affine y = a*x + b relationships.
_AFFINE: dict[tuple[str, str], dict[str, tuple[float, float]]] = {
    ("mmol_per_mol", "pct"): {"lab:hba1c": (0.09148, 2.152)},
}


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", normalized.lower()).strip()


def known_spellings() -> dict[str, str]:
    """Raw unit spellings (lowercased) this module has an alias for.

    Used by lab_pdf's value/unit splitter to find a trailing unit token
    embedded in a value cell (e.g. ``"14.1g/dl"`` with no separate unit
    column). Not for general use — call `normalize_unit` instead.
    """
    return dict(_ALIASES)


def normalize_unit(raw: str) -> str:
    """Map a raw unit spelling to its canonical spelling.

    Falls back to the stripped input unchanged when no alias applies.
    """
    stripped = raw.strip()
    if stripped in _CASE_SENSITIVE_ALIASES:
        return _CASE_SENSITIVE_ALIASES[stripped]
    normalized = _normalize_text(raw.replace("µ", "u").replace("μ", "u"))
    return _ALIASES.get(normalized, stripped)


def convert(value: float, *, from_unit: str, to_unit: str, metric_id: str) -> float | None:
    """Convert `value` from `from_unit` to `to_unit` for `metric_id`.

    Dispatch order: identity -> metric-agnostic factor/divisor -> metric-scoped
    (equivalence / divisor / factor) -> affine -> refuse (`None`).
    """
    if from_unit == to_unit:
        return value

    factor = _SIMPLE_FACTORS.get((from_unit, to_unit))
    if factor is not None:
        return value * factor

    simple_divisor = _SIMPLE_DIVISORS.get((from_unit, to_unit))
    if simple_divisor is not None:
        return value / simple_divisor

    if metric_id in _METRIC_SCOPED_EQUIVALENT.get((from_unit, to_unit), set()):
        return value

    divisor = _METRIC_SCOPED_DIVISOR.get((from_unit, to_unit), {}).get(metric_id)
    if divisor is not None:
        return value / divisor

    scoped_factor = _METRIC_SCOPED_FACTOR.get((from_unit, to_unit), {}).get(metric_id)
    if scoped_factor is not None:
        return value * scoped_factor

    affine = _AFFINE.get((from_unit, to_unit), {}).get(metric_id)
    if affine is not None:
        a, b = affine
        return a * value + b

    return None


__all__ = ["normalize_unit", "convert", "known_spellings"]
