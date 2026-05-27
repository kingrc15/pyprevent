from __future__ import annotations

import pandas as pd

from prevent import compute_prevent


def test_age_over_59_masks_30yr_only(prevent_row):
    out = compute_prevent(prevent_row(AGE=75, BPTREAT=1, STATIN=1, ZIP="00000"))
    assert not pd.isna(out["PREVENT10_CVD_BASE_PCT"].iloc[0])
    assert pd.isna(out["PREVENT30_CVD_BASE_PCT"].iloc[0])
    assert pd.isna(out["PREVENT30_CVD_FULL_PCT"].iloc[0])


def test_age_out_of_range_masks_all_horizons(prevent_row):
    out = compute_prevent(prevent_row(AGE=20, BPTREAT=1, STATIN=1, ZIP="00000"))
    assert pd.isna(out["PREVENT10_CVD_BASE_PCT"].iloc[0])
    assert pd.isna(out["PREVENT30_CVD_BASE_PCT"].iloc[0])
