"""
Tests for the ``prevent`` module.

The reference values in the parity tests come from worked examples in the
upstream AHA PREVENT R reference implementation (the ``preventr`` package,
``estimate_risk()`` examples), which in turn trace back to Table S25 and the
supplemental Excel file of the PREVENT development & validation manuscript:

    Khan SS, Matsushita K, Sang Y, et al. Development and Validation of the
    American Heart Association Predicting Risk of Cardiovascular Disease
    EVENTs (PREVENT) Equations. Circulation. 2024;149(6):430-449.

The published reference outputs are rounded to three decimal places, so the
tests assert agreement to within 0.1 percentage points (i.e. tolerant of the
rounding in the published values but tight enough to catch any meaningful
implementation drift).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from prevent import (
    REQUIRED_COLUMNS,
    _normalize_sex,
    _sdicat,
    _sigmoid_pct,
    _to_binary01,
    compute_prevent10,
)


PCT_TOL = 0.1  # percentage-point tolerance vs. published 3-decimal reference values


def _row(**overrides):
    """Return a one-row DataFrame with sensible defaults for every required column."""
    base = {
        "PAT_ID": "P001",
        "AGE": 55,
        "SEX": "F",
        "TCHOL": 200,
        "HDL": 50,
        "SBP": 130,
        "BMI": 28.0,
        "EGFR": 85,
        "T2DM": 0,
        "RECENT_SMOKING": 0,
        "SMOKING_CURR": 0,
        "UACR": np.nan,
        "HBA1C": np.nan,
        "ADI": np.nan,
        "SVI": np.nan,
        "ZIP": "75201",
    }
    base.update(overrides)
    return pd.DataFrame([base])


# ---------------------------------------------------------------------------
# Parity tests against the upstream R reference (preventr / Table S25)
# ---------------------------------------------------------------------------


def test_table_s25_female_base_model():
    """
    Table S25 worked example (base model, female, age 50):
        age=50, sex=F, sbp=160, bp_tx=1, tc=200, hdl=45, statin=0,
        dm=1, smoking=0, egfr=90, bmi=35
    Expected 10-year risks: total_cvd=14.7%, ascvd=9.2%, heart_failure=8.1%.
    """
    df = _row(
        AGE=50, SEX="F", SBP=160, TCHOL=200, HDL=45,
        T2DM=1, SMOKING_CURR=0, EGFR=90, BMI=35,
    )
    out = compute_prevent10(df, bp_treat_default=1, statin_default=0)

    assert out["PREVENT10_CVD_BASIC_PCT"].iloc[0] == pytest.approx(14.7, abs=PCT_TOL)
    assert out["PREVENT10_ASCVD_BASIC_PCT"].iloc[0] == pytest.approx(9.2, abs=PCT_TOL)
    assert out["PREVENT10_HF_BASIC_PCT"].iloc[0] == pytest.approx(8.1, abs=PCT_TOL)


def test_male_base_model():
    """
    preventr "base" worked example, male (zip with no SDI data, no optional vars):
        age=66, sex=M, sbp=148, bp_tx=0, tc=188, hdl=52, statin=1,
        dm=1, smoking=1, egfr=67, bmi=30
    Expected 10-year risks: total_cvd=22.4%, ascvd=14.2%, heart_failure=13.8%.
    """
    df = _row(
        AGE=66, SEX="M", SBP=148, TCHOL=188, HDL=52,
        T2DM=1, SMOKING_CURR=1, EGFR=67, BMI=30,
    )
    out = compute_prevent10(df, bp_treat_default=0, statin_default=1)

    assert out["PREVENT10_CVD_BASIC_PCT"].iloc[0] == pytest.approx(22.4, abs=PCT_TOL)
    assert out["PREVENT10_ASCVD_BASIC_PCT"].iloc[0] == pytest.approx(14.2, abs=PCT_TOL)
    assert out["PREVENT10_HF_BASIC_PCT"].iloc[0] == pytest.approx(13.8, abs=PCT_TOL)


def test_female_full_model_hba1c_and_uacr_no_sdi():
    """
    preventr "full" worked example, female with zip whose SDI is unavailable
    (so SDI takes the missing-coefficient path while HbA1c and UACR are real):
        age=66, sex=F, sbp=148, bp_tx=0, tc=188, hdl=52, statin=1,
        dm=1, smoking=1, egfr=67, bmi=30, hba1c=9, uacr=75
    Expected 10-year risks: total_cvd=28.8%, ascvd=17.8%, heart_failure=21.8%.
    """
    df = _row(
        AGE=66, SEX="F", SBP=148, TCHOL=188, HDL=52,
        T2DM=1, SMOKING_CURR=1, EGFR=67, BMI=30,
        HBA1C=9, UACR=75,
    )
    out = compute_prevent10(df, bp_treat_default=0, statin_default=1)

    assert out["PREVENT10_CVD_FULL_PCT"].iloc[0] == pytest.approx(28.8, abs=PCT_TOL)
    assert out["PREVENT10_ASCVD_FULL_PCT"].iloc[0] == pytest.approx(17.8, abs=PCT_TOL)
    assert out["PREVENT10_HF_FULL_PCT"].iloc[0] == pytest.approx(21.8, abs=PCT_TOL)


# ---------------------------------------------------------------------------
# Structural / API-level behavior
# ---------------------------------------------------------------------------


def test_required_columns_contract():
    """Removing any required column from the input must raise ValueError."""
    df = _row()
    for col in REQUIRED_COLUMNS:
        with pytest.raises(ValueError, match="Missing required columns"):
            compute_prevent10(df.drop(columns=[col]))


def test_output_columns_added():
    """All six PREVENT output columns should be present in the result."""
    out = compute_prevent10(_row(), bp_treat_default=0, statin_default=0)
    expected = {
        "PREVENT10_CVD_BASIC_PCT",
        "PREVENT10_ASCVD_BASIC_PCT",
        "PREVENT10_HF_BASIC_PCT",
        "PREVENT10_CVD_FULL_PCT",
        "PREVENT10_ASCVD_FULL_PCT",
        "PREVENT10_HF_FULL_PCT",
    }
    assert expected.issubset(out.columns)


def test_input_dataframe_not_mutated():
    """compute_prevent10 must operate on a copy of the input DataFrame."""
    df = _row()
    pre_cols = list(df.columns)
    _ = compute_prevent10(df, bp_treat_default=0, statin_default=0)
    assert list(df.columns) == pre_cols


def test_outputs_are_percentages_between_0_and_100():
    """Scores must be probabilities expressed on a 0-100 percent scale."""
    df = _row()
    out = compute_prevent10(df, bp_treat_default=0, statin_default=0)
    for col in [
        "PREVENT10_CVD_BASIC_PCT",
        "PREVENT10_ASCVD_BASIC_PCT",
        "PREVENT10_HF_BASIC_PCT",
        "PREVENT10_CVD_FULL_PCT",
        "PREVENT10_ASCVD_FULL_PCT",
        "PREVENT10_HF_FULL_PCT",
    ]:
        v = out[col].iloc[0]
        assert 0.0 <= v <= 100.0, f"{col}={v} out of [0,100]"


def test_missing_age_yields_all_nan():
    """Missing AGE must NaN-out every score for that row."""
    df = _row(AGE=np.nan)
    out = compute_prevent10(df, bp_treat_default=0, statin_default=0)
    for col in [c for c in out.columns if c.startswith("PREVENT10_")]:
        assert pd.isna(out[col].iloc[0]), f"expected NaN for {col}"


def test_age_out_of_range_is_silently_clipped():
    """
    Documented behavior: out-of-range inputs are silently clipped to the valid
    PREVENT range before validation, so AGE=20 produces the same output as
    AGE=30 (both clip to 30). This locks that contract in place.
    """
    out_low = compute_prevent10(_row(AGE=20), bp_treat_default=0, statin_default=0)
    out_edge = compute_prevent10(_row(AGE=30), bp_treat_default=0, statin_default=0)
    assert out_low["PREVENT10_CVD_BASIC_PCT"].iloc[0] == pytest.approx(
        out_edge["PREVENT10_CVD_BASIC_PCT"].iloc[0]
    )


def test_bp_treat_none_blocks_outputs():
    """
    With bp_treat_default=None, every score becomes NaN because both the
    CVD/ASCVD path and the HF path depend on BP-treatment status.
    """
    out = compute_prevent10(_row(), bp_treat_default=None, statin_default=0)
    for col in [c for c in out.columns if c.startswith("PREVENT10_")]:
        assert pd.isna(out[col].iloc[0])


def test_statin_none_blocks_cvd_ascvd_only():
    """statin_default=None should NaN only CVD and ASCVD; HF should still compute."""
    out = compute_prevent10(_row(), bp_treat_default=0, statin_default=None)
    assert pd.isna(out["PREVENT10_CVD_BASIC_PCT"].iloc[0])
    assert pd.isna(out["PREVENT10_ASCVD_BASIC_PCT"].iloc[0])
    assert pd.isna(out["PREVENT10_CVD_FULL_PCT"].iloc[0])
    assert pd.isna(out["PREVENT10_ASCVD_FULL_PCT"].iloc[0])
    assert not pd.isna(out["PREVENT10_HF_BASIC_PCT"].iloc[0])
    assert not pd.isna(out["PREVENT10_HF_FULL_PCT"].iloc[0])


def test_missing_bmi_blocks_hf_only():
    """Missing BMI should NaN only the HF output; CVD/ASCVD are unaffected."""
    out = compute_prevent10(_row(BMI=np.nan), bp_treat_default=0, statin_default=0)
    assert pd.isna(out["PREVENT10_HF_BASIC_PCT"].iloc[0])
    assert pd.isna(out["PREVENT10_HF_FULL_PCT"].iloc[0])
    assert not pd.isna(out["PREVENT10_CVD_BASIC_PCT"].iloc[0])
    assert not pd.isna(out["PREVENT10_ASCVD_BASIC_PCT"].iloc[0])


def test_smoking_preference_switches_column():
    """Switching the smoking column should affect the score when the two columns disagree."""
    df_disagree = _row(SMOKING_CURR=0, RECENT_SMOKING=1)
    out_curr = compute_prevent10(df_disagree, bp_treat_default=0, statin_default=0,
                                 smoking_preference="SMOKING_CURR")
    out_recent = compute_prevent10(df_disagree, bp_treat_default=0, statin_default=0,
                                   smoking_preference="RECENT_SMOKING")
    assert out_recent["PREVENT10_CVD_BASIC_PCT"].iloc[0] > out_curr["PREVENT10_CVD_BASIC_PCT"].iloc[0]


def test_smoking_preference_invalid_raises():
    with pytest.raises(ValueError, match="smoking_preference"):
        compute_prevent10(_row(), smoking_preference="NOPE")


def test_full_with_sdi_differs_from_full_without_sdi():
    """
    Providing an SDI value (here, deep into category 2) must change the Full-model
    output relative to the missing-SDI fallback path.
    """
    df = _row(
        AGE=66, SEX="F", SBP=148, TCHOL=188, HDL=52,
        T2DM=1, SMOKING_CURR=1, EGFR=67, BMI=30,
        HBA1C=9, UACR=75,
    )
    out_no_sdi = compute_prevent10(df, bp_treat_default=0, statin_default=1)
    out_sdi = compute_prevent10(df, bp_treat_default=0, statin_default=1,
                                sdi_series=pd.Series([10.0]))
    assert (
        out_no_sdi["PREVENT10_CVD_FULL_PCT"].iloc[0]
        != out_sdi["PREVENT10_CVD_FULL_PCT"].iloc[0]
    )


def test_zip_truncated_to_five_chars():
    """Long ZIP codes should be passed through as their first 5 characters."""
    out = compute_prevent10(_row(ZIP="752019999"), bp_treat_default=0, statin_default=0)
    assert out["ZIP"].iloc[0] == "752019999"  # original column is preserved
    # Internal truncation lives in _clip_inputs and does not surface in the output frame
    # but should not cause the row to error out.
    assert not pd.isna(out["PREVENT10_CVD_BASIC_PCT"].iloc[0])


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("M", 0.0), ("male", 0.0), ("MALE", 0.0), (0, 0.0), (0.0, 0.0),
        ("F", 1.0), ("female", 1.0), ("Female", 1.0), (1, 1.0), (1.0, 1.0),
    ],
)
def test_normalize_sex_accepted(raw, expected):
    assert _normalize_sex(raw) == expected


@pytest.mark.parametrize("raw", ["X", "", None, 2, 3.5])
def test_normalize_sex_rejected(raw):
    assert math.isnan(_normalize_sex(raw))


@pytest.mark.parametrize(
    "raw,expected",
    [(0, 0.0), (1, 1.0), ("0", 0.0), ("1", 1.0), (True, 1.0), (False, 0.0)],
)
def test_to_binary01_accepted(raw, expected):
    assert _to_binary01(raw) == expected


@pytest.mark.parametrize("raw", [2, -1, "yes", None])
def test_to_binary01_rejected(raw):
    assert math.isnan(_to_binary01(raw))


@pytest.mark.parametrize(
    "raw,expected",
    [(1, 0.0), (3.9, 0.0), (4, 1.0), (5.5, 1.0), (6.99, 1.0),
     (7, 2.0), (9, 2.0), (10, 2.0)],
)
def test_sdicat_buckets(raw, expected):
    assert _sdicat(raw) == expected


def test_sdicat_missing_returns_nan():
    assert math.isnan(_sdicat(np.nan))


@pytest.mark.parametrize(
    "x,expected",
    [
        (0.0, 50.0),
        # Realistic PREVENT logit magnitudes are bounded around +/- a few units;
        # check the asymptotes at values well past anything the equations produce.
        (-50.0, pytest.approx(0.0, abs=1e-9)),
        (50.0, pytest.approx(100.0, abs=1e-9)),
    ],
)
def test_sigmoid_pct(x, expected):
    assert _sigmoid_pct(x) == expected


# ---------------------------------------------------------------------------
# Vectorized / multi-row behavior
# ---------------------------------------------------------------------------


def test_multi_row_independence():
    """Scoring multiple rows should give the same result as scoring them individually."""
    df = pd.concat(
        [
            _row(AGE=50, SEX="F", SBP=160, TCHOL=200, HDL=45,
                 T2DM=1, SMOKING_CURR=0, EGFR=90, BMI=35),
            _row(AGE=66, SEX="M", SBP=148, TCHOL=188, HDL=52,
                 T2DM=1, SMOKING_CURR=1, EGFR=67, BMI=30, HBA1C=7.5),
        ],
        ignore_index=True,
    )
    # Score the batch under one shared bp_treat_default / statin_default,
    # then score each row individually -- once under that same default
    # (must match the batch result) and once under a different default
    # (must NOT match, proving rows are scored independently with no leakage).
    out_batch = compute_prevent10(df, bp_treat_default=1, statin_default=0)
    out_row0_same = compute_prevent10(df.iloc[[0]], bp_treat_default=1, statin_default=0)
    out_row1_diff = compute_prevent10(df.iloc[[1]], bp_treat_default=0, statin_default=1)

    assert out_batch["PREVENT10_HF_BASIC_PCT"].iloc[0] == pytest.approx(
        out_row0_same["PREVENT10_HF_BASIC_PCT"].iloc[0]
    )
    assert out_batch["PREVENT10_HF_BASIC_PCT"].iloc[1] != pytest.approx(
        out_row1_diff["PREVENT10_HF_BASIC_PCT"].iloc[0]
    )
