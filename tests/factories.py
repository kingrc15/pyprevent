from __future__ import annotations

import numpy as np
import pandas as pd


def make_prevent_row(**overrides) -> pd.DataFrame:
    """One-row DataFrame with defaults for all required PREVENT columns."""
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
        "ZIP": "75201",
    }
    base.update(overrides)
    return pd.DataFrame([base])
