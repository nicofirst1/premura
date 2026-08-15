"""Tests for the shared unit module (`premura.units`).

Covers: (a) every spelling in the old `lab_pdf._UNIT_ALIASES` normalizes as
before (the dict itself is deleted in a later WP, so expectations are
inlined as literals here); (b) conversion cases reproduced from
`test_lab_pdf.py` and `test_bmt.py` still hold; (c) an unregistered
(from, to[, metric]) pair refuses (`None`); (d) `duck.connect`'s read-only
default and `duck.initialize`'s explicit write-mode.
"""

from __future__ import annotations

import duckdb
import pytest

from premura.store import duck
from premura.units import convert, normalize_unit

# Byte-identical copy of the old lab_pdf._UNIT_ALIASES (lowercased-key form;
# case-sensitive G/l and T/l are covered separately below).
_OLD_UNIT_ALIASES = {
    "%": "pct",
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
}


@pytest.mark.parametrize("raw, expected", sorted(_OLD_UNIT_ALIASES.items()))
def test_normalize_unit_matches_old_lab_pdf_aliases(raw: str, expected: str) -> None:
    assert normalize_unit(raw) == expected


def test_normalize_unit_case_sensitive_german_cbc_units() -> None:
    # Upper-case G/l and T/l are Giga/Tera-per-litre counts; lower-case g/l
    # is grams per litre. Must not collapse under case-insensitive lookup.
    assert normalize_unit("G/l") == "10^9_per_l"
    assert normalize_unit("T/l") == "10^12_per_l"
    assert normalize_unit("g/l") == "g_per_l"


def test_normalize_unit_unknown_passes_through_stripped() -> None:
    assert normalize_unit("  weird_unit  ") == "weird_unit"


def test_normalize_unit_italian_ui_ml_alias() -> None:
    assert normalize_unit("UI/ml") == "IU_per_ml"


# --- conversion cases reproduced from test_lab_pdf.py:137 (unit normalization test) ---


@pytest.mark.parametrize(
    "value, from_unit, to_unit, metric_id, expected",
    [
        # MCH pg/eritr. -> pg: alias-only, no numeric conversion.
        (30.1, "pg", "pg", "lab:mch", 30.1),
        # Sideremia (iron) mg/l -> ug/dl.
        (1.02, "mg_per_l", "ug_per_dl", "lab:iron", 102.0),
        # Calcium mmol/l -> mg/dl.
        (2.50, "mmol_per_l", "mg_per_dl", "lab:calcium", pytest.approx(10.02, abs=1e-2)),
        # TSH microU/ml -> mIU/l.
        (2.4, "microU_per_ml", "mIU_per_l", "lab:tsh", 2.4),
        # Leukozyten (WBC) G/l -> 10^9_per_l: same canonical spelling, identity.
        (6.2, "10^9_per_l", "10^9_per_l", "lab:wbc", 6.2),
        # Albumin g/l -> g/dl.
        (44.0, "g_per_l", "g_per_dl", "lab:albumin", 4.4),
    ],
)
def test_convert_reproduces_lab_pdf_unit_normalization_cases(
    value: float, from_unit: str, to_unit: str, metric_id: str, expected: float
) -> None:
    assert convert(value, from_unit=from_unit, to_unit=to_unit, metric_id=metric_id) == expected


def test_convert_hba1c_affine_ifcc_to_pct() -> None:
    # mmol/mol -> pct, y = 0.09148x + 2.152.
    result = convert(50.0, from_unit="mmol_per_mol", to_unit="pct", metric_id="lab:hba1c")
    assert result == pytest.approx(0.09148 * 50.0 + 2.152)


def test_convert_sodium_meq_equivalent_to_mmol() -> None:
    result = convert(140.0, from_unit="mEq_per_l", to_unit="mmol_per_l", metric_id="lab:sodium")
    assert result == 140.0


def test_convert_vitamin_b12_pmol_to_pg() -> None:
    result = convert(
        300.0, from_unit="pmol_per_l", to_unit="pg_per_ml", metric_id="lab:vitamin_b12"
    )
    assert result == pytest.approx(300.0 * 1.355)


# --- conversion cases reproduced from test_bmt.py:31 (lb config) and :79 (inches) ---


def test_convert_bmt_lb_to_kg() -> None:
    result = convert(82.5, from_unit="lb", to_unit="kg", metric_id="weight")
    assert result == pytest.approx(82.5 * 0.45359237, abs=1e-6)


def test_convert_bmt_inches_to_cm() -> None:
    result = convert(32.0, from_unit="in", to_unit="cm", metric_id="waist_circumference")
    assert result == pytest.approx(81.28, abs=1e-6)


def test_convert_bmt_mm_to_cm_uses_division_not_reciprocal_multiply() -> None:
    # Pins the original bmt.py `value / 10` behavior exactly (not `value * 0.1`,
    # which differs at the float ULP: 3.3/10 == 0.32999999999999996).
    assert convert(3.3, from_unit="mm", to_unit="cm", metric_id="waist_circumference") == 3.3 / 10


# --- refusal ---


def test_convert_unknown_pair_returns_none() -> None:
    assert convert(1.0, from_unit="mg_per_l", to_unit="pct", metric_id="lab:nonexistent") is None


def test_convert_known_pair_wrong_metric_returns_none() -> None:
    # mmol_per_l -> mg_per_dl is only defined for calcium/magnesium/phosphorus.
    assert convert(1.0, from_unit="mmol_per_l", to_unit="mg_per_dl", metric_id="lab:sodium") is None


# --- duck.connect / duck.initialize read-only default ---


def test_connect_defaults_to_read_only(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    # A brand-new file must exist before a read-only connection can open it.
    duck.connect(db_path, read_only=False).close()

    conn = duck.connect(db_path)
    try:
        with pytest.raises(duckdb.Error):
            conn.execute("CREATE TABLE t (x INTEGER)")
    finally:
        conn.close()


def test_initialize_still_writes(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    conn = duck.initialize(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM hp.dim_metric").fetchone()
        assert row is not None and row[0] > 0
    finally:
        conn.close()
