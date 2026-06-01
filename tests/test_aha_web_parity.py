from __future__ import annotations

import pytest

from tests.aha_web import (
    AhaWebCase,
    aha_web_available,
    assert_case_matches_web,
    benchmark_cases,
)
from tests.r_harness import random_valid_cases as random_cases_for_r

pytestmark = [
    pytest.mark.aha_web,
    pytest.mark.skipif(
        not aha_web_available(),
        reason="AHA PreventCalculate API unreachable (network or endpoint change)",
    ),
]


def test_benchmark_cases_match_aha_web():
    """Published vignettes vs live PreventCalculate API (official web calculator)."""
    for case in benchmark_cases():
        assert_case_matches_web(case)


@pytest.mark.parametrize("seed", [7, 19])
def test_random_valid_cases_match_aha_web(seed: int):
    """Spot-check random in-range rows against the live web API (50 per seed)."""
    import pandas as pd

    rng_cases = random_cases_for_r(n=50, seed=seed)
    for row in rng_cases.itertuples(index=False):
        has_uacr = pd.notna(row.uacr)
        has_hba1c = pd.notna(row.hba1c)
        # Web picks a single model; only test unambiguous base-model draws.
        if has_uacr or has_hba1c:
            continue
        case = AhaWebCase(
            case_id=row.case_id,
            sex=int(row.sex),
            age=float(row.age),
            tc=float(row.tc),
            hdl=float(row.hdl),
            sbp=float(row.sbp),
            bmi=float(row.bmi),
            egfr=float(row.egfr),
            dm=int(row.dm),
            smoking=int(row.smoking),
            bptreat=int(row.bptreat),
            statin=int(row.statin),
        )
        assert_case_matches_web(case)
