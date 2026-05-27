from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prevent import PREVENT_OUTPUT_COLUMNS, compute_prevent

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CASES_PATH = FIXTURES / "r_cases.csv"
REF_PATH = FIXTURES / "r_reference.csv"


@pytest.mark.parametrize("path", [CASES_PATH, REF_PATH])
def test_r_parity_fixtures_exist(path: Path):
    assert path.is_file(), f"Missing fixture file: {path}"


def test_r_parity_against_fixture():
    cases = pd.read_csv(CASES_PATH, na_values=["", "NA"])
    ref = pd.read_csv(REF_PATH, na_values=["", "NA"])

    assert "case_id" in cases.columns
    assert "case_id" in ref.columns

    merged = cases.merge(ref, on="case_id", how="inner", validate="one_to_one")
    assert len(merged) == len(cases), "Every case must have a reference row"
    assert len(merged) == len(ref), "Reference must cover all cases"

    df = pd.DataFrame(
        {
            "PAT_ID": merged["case_id"],
            "AGE": merged["age"],
            "SEX": merged["sex"],
            "TCHOL": merged["tc"],
            "HDL": merged["hdl"],
            "SBP": merged["sbp"],
            "BMI": merged["bmi"],
            "EGFR": merged["egfr"],
            "T2DM": merged["dm"],
            "RECENT_SMOKING": merged["smoking"],
            "SMOKING_CURR": merged["smoking"],
            "UACR": merged["uacr"],
            "HBA1C": merged["hba1c"],
            "BPTREAT": merged["bptreat"],
            "STATIN": merged["statin"],
            "ZIP": "00000",
        }
    )

    out = compute_prevent(
        df,
        sdi_series=merged["sdi"],
        smoking_preference="SMOKING_CURR",
    )

    ref_cols = [c for c in PREVENT_OUTPUT_COLUMNS if c in ref.columns]
    assert ref_cols, "Reference must include PREVENT output columns"
    missing_cols = [c for c in ref_cols if c not in out.columns]
    assert not missing_cols, f"Reference columns missing from compute_prevent output: {missing_cols}"

    atol = 1e-12
    for col in ref_cols:
        expected = merged[col]
        mask = ~expected.isna()
        if not mask.any():
            continue
        got = out.loc[mask, col].astype(float).to_numpy()
        exp = expected.loc[mask].astype(float).to_numpy()
        assert np.allclose(got, exp, rtol=0.0, atol=atol, equal_nan=True), f"Mismatch in {col}"
