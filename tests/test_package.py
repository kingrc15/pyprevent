from __future__ import annotations

from pathlib import Path

import pytest

from prevent import PREVENT_OUTPUT_COLUMNS, compute_prevent
from prevent._zip_sdi import _ZCTA_SDI_CSV


def test_sdi_crosswalk_file_bundled():
    assert _ZCTA_SDI_CSV.is_file(), f"Missing bundled SDI data: {_ZCTA_SDI_CSV}"


def test_compute_prevent_appends_thirty_columns(prevent_row):
    out = compute_prevent(prevent_row(BPTREAT=0, STATIN=0))
    for col in PREVENT_OUTPUT_COLUMNS:
        assert col in out.columns
    assert len(PREVENT_OUTPUT_COLUMNS) == 30


def test_repo_layout_paths_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "prevent" / "__init__.py").is_file()
    assert (root / "prevent" / "data" / "rgc_sdi_zcta2015_2019.csv").is_file()
