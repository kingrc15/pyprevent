from __future__ import annotations

import pytest

from tests.r_harness import (
    assert_python_matches_r,
    boundary_cases,
    r_available,
    random_valid_cases,
)

pytestmark = pytest.mark.skipif(not r_available(), reason="Rscript / pyprevent-r env not available")


@pytest.mark.parametrize("seed", [42, 99, 2024])
def test_random_valid_cases_match_r(seed: int):
    """Property test: 200 in-range rows per seed vs AHAprevent (all 30 outputs)."""
    cases = random_valid_cases(n=200, seed=seed)
    assert_python_matches_r(cases)


def test_boundary_stratified_cases_match_r():
    """Spline knots, age horizons, and optional-input paths vs AHAprevent."""
    assert_python_matches_r(boundary_cases())


def test_invalid_optional_inputs_match_r():
    """Post-validation paths that R handles without error."""
    import pandas as pd

    cases = pd.DataFrame(
        [
            {
                "case_id": "invalid_hba1c_zero",
                "sex": 1,
                "age": 55,
                "tc": 200,
                "hdl": 50,
                "sbp": 130,
                "dm": 0,
                "smoking": 0,
                "bmi": 28.0,
                "egfr": 85.0,
                "bptreat": 0,
                "statin": 0,
                "uacr": 10.0,
                "hba1c": 0.0,
                "sdi": 5.0,
            },
            {
                "case_id": "invalid_sdi_eleven",
                "sex": 1,
                "age": 55,
                "tc": 200,
                "hdl": 50,
                "sbp": 130,
                "dm": 0,
                "smoking": 0,
                "bmi": 28.0,
                "egfr": 85.0,
                "bptreat": 0,
                "statin": 0,
                "uacr": 10.0,
                "hba1c": 8.0,
                "sdi": 11.0,
            },
        ]
    )
    assert_python_matches_r(cases)


def test_r_harness_smoke():
    """Ensure the batch R scorer returns all PREVENT output columns."""
    from prevent import PREVENT_OUTPUT_COLUMNS

    from tests.r_harness import score_with_r

    ref = score_with_r(boundary_cases().head(3))
    assert len(ref) == 3
    for col in PREVENT_OUTPUT_COLUMNS:
        assert col in ref.columns
