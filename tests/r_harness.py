from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from prevent import PREVENT_OUTPUT_COLUMNS, compute_prevent

ROOT = Path(__file__).resolve().parents[1]
SCORE_SCRIPT = ROOT / "scripts" / "score_cases.R"
DEFAULT_R_PKG = ROOT.parent / "PREVENT" / "R" / "AHAprevent"
R_PARITY_ATOL = 1e-9


def rscript_path() -> str | None:
    """Return an Rscript executable, preferring the pyprevent-r conda env."""
    override = os.environ.get("PREVENT_RSCRIPT")
    if override and Path(override).is_file():
        return override

    found = shutil.which("Rscript")
    if found:
        return found

    conda = shutil.which("mamba") or shutil.which("conda")
    if not conda:
        return None

    env_name = os.environ.get("PYPREVENT_R_ENV", "pyprevent-r")
    try:
        proc = subprocess.run(
            [conda, "run", "-n", env_name, "Rscript", "--version"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return f"{conda} run -n {env_name} Rscript"


def r_available() -> bool:
    return rscript_path() is not None


_AHAPREVENT_AVAILABLE: bool | None = None


def _ahaprevent_pkg_path() -> Path:
    return Path(os.environ.get("PREVENT_R_PKG", DEFAULT_R_PKG))


def ahaprevent_available() -> bool:
    """
    True when R can load the AHAprevent package (optionally after installing from PREVENT_R_PKG).

    CI runners often have Rscript without AHAprevent; property tests must skip in that case.
    """
    global _AHAPREVENT_AVAILABLE
    if _AHAPREVENT_AVAILABLE is not None:
        return _AHAPREVENT_AVAILABLE

    if rscript_path() is None:
        _AHAPREVENT_AVAILABLE = False
        return False

    def _probe() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            _rscript_cmd()
            + [
                "-e",
                "suppressPackageStartupMessages(library(AHAprevent)); quit(status=0)",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    if _probe().returncode == 0:
        _AHAPREVENT_AVAILABLE = True
        return True

    if os.environ.get("PREVENT_SKIP_R_INSTALL") == "1":
        _AHAPREVENT_AVAILABLE = False
        return False

    pkg = _ahaprevent_pkg_path()
    if not (pkg / "DESCRIPTION").is_file():
        _AHAPREVENT_AVAILABLE = False
        return False

    r_cmd = shutil.which("R")
    if r_cmd is None:
        _AHAPREVENT_AVAILABLE = False
        return False

    install = subprocess.run(
        [r_cmd, "CMD", "INSTALL", str(pkg)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if install.returncode != 0:
        _AHAPREVENT_AVAILABLE = False
        return False

    _AHAPREVENT_AVAILABLE = _probe().returncode == 0
    return _AHAPREVENT_AVAILABLE


def _rscript_cmd() -> list[str]:
    path = rscript_path()
    if path is None:
        raise RuntimeError("Rscript not available")
    if " run -n " in path or path.startswith(("conda ", "mamba ")):
        return path.split()
    return [path]


def cases_to_prevent_df(cases: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "PAT_ID": cases["case_id"],
            "AGE": cases["age"],
            "SEX": cases["sex"],
            "TCHOL": cases["tc"],
            "HDL": cases["hdl"],
            "SBP": cases["sbp"],
            "BMI": cases["bmi"],
            "EGFR": cases["egfr"],
            "T2DM": cases["dm"],
            "RECENT_SMOKING": cases["smoking"],
            "SMOKING_CURR": cases["smoking"],
            "UACR": cases["uacr"],
            "HBA1C": cases["hba1c"],
            "BPTREAT": cases["bptreat"],
            "STATIN": cases["statin"],
            "ZIP": "00000",
        }
    )


def score_with_python(cases: pd.DataFrame) -> pd.DataFrame:
    df = cases_to_prevent_df(cases)
    out = compute_prevent(
        df,
        sdi_series=cases["sdi"],
        smoking_preference="SMOKING_CURR",
    )
    ref = pd.DataFrame({"case_id": cases["case_id"].to_numpy()})
    for col in PREVENT_OUTPUT_COLUMNS:
        ref[col] = out[col].to_numpy()
    return ref


def score_with_r(cases: pd.DataFrame) -> pd.DataFrame:
    if not SCORE_SCRIPT.is_file():
        raise FileNotFoundError(f"Missing R scorer: {SCORE_SCRIPT}")

    env = os.environ.copy()
    env.setdefault("PREVENT_R_PKG", str(DEFAULT_R_PKG))
    env.setdefault("PREVENT_SKIP_R_INSTALL", "1")

    with tempfile.TemporaryDirectory(prefix="pyprevent-r-") as tmp:
        in_path = Path(tmp) / "cases.csv"
        out_path = Path(tmp) / "scores.csv"
        cases.to_csv(in_path, index=False, na_rep="")

        cmd = _rscript_cmd() + [str(SCORE_SCRIPT), str(in_path), str(out_path)]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "R scoring failed\n"
                f"cmd: {' '.join(cmd)}\n"
                f"stdout:\n{proc.stdout}\n"
                f"stderr:\n{proc.stderr}"
            )
        return pd.read_csv(out_path, na_values=["", "NA"])


def assert_python_matches_r(
    cases: pd.DataFrame,
    *,
    atol: float = R_PARITY_ATOL,
) -> None:
    py = score_with_python(cases)
    r_ref = score_with_r(cases)
    merged = py.merge(r_ref, on="case_id", suffixes=("_py", "_r"), validate="one_to_one")

    for col in PREVENT_OUTPUT_COLUMNS:
        py_col = f"{col}_py"
        r_col = f"{col}_r"
        if py_col not in merged.columns or r_col not in merged.columns:
            raise AssertionError(f"Missing comparison columns for {col}")

        expected = merged[r_col]
        got = merged[py_col]
        mask = ~expected.isna()
        if not mask.any():
            assert got.isna().all(), f"{col}: expected all NaN when R is all NaN"
            continue

        exp = expected.loc[mask].astype(float).to_numpy()
        g = got.loc[mask].astype(float).to_numpy()
        if not np.allclose(g, exp, rtol=0.0, atol=atol, equal_nan=True):
            worst = int(np.argmax(np.abs(g - exp)))
            raise AssertionError(
                f"{col} mismatch (max abs err "
                f"{np.max(np.abs(g - exp)):.3g}): "
                f"case={merged.loc[mask, 'case_id'].iloc[worst]!r} "
                f"py={g[worst]:.12g} r={exp[worst]:.12g}"
            )


def random_valid_cases(n: int, seed: int) -> pd.DataFrame:
    """Draw n in-range rows matching AHAprevent input domains."""
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    for i in range(n):
        has_uacr = bool(rng.integers(0, 2))
        has_hba1c = bool(rng.integers(0, 2))
        has_sdi = bool(rng.integers(0, 2))
        rows.append(
            {
                "case_id": f"rand_{seed}_{i:04d}",
                "sex": int(rng.integers(0, 2)),
                "age": int(rng.integers(30, 80)),
                "tc": int(rng.integers(130, 321)),
                "hdl": int(rng.integers(20, 101)),
                "sbp": int(rng.integers(90, 201)),
                "dm": int(rng.integers(0, 2)),
                "smoking": int(rng.integers(0, 2)),
                "bmi": float(rng.uniform(18.5, 39.99)),
                "egfr": float(rng.uniform(5, 120)),
                "bptreat": int(rng.integers(0, 2)),
                "statin": int(rng.integers(0, 2)),
                "uacr": float(rng.uniform(0.1, 500)) if has_uacr else np.nan,
                "hba1c": float(rng.uniform(4.0, 14.0)) if has_hba1c else np.nan,
                "sdi": float(int(rng.integers(1, 11))) if has_sdi else np.nan,
            }
        )
    return pd.DataFrame(rows)


def boundary_cases() -> pd.DataFrame:
    """Stratified edge inputs: age horizons, splines, optional-missing paths."""
    specs: list[dict] = []
    idx = 0

    def add(**kwargs) -> None:
        nonlocal idx
        row = {
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
            "uacr": np.nan,
            "hba1c": np.nan,
            "sdi": np.nan,
        }
        row.update(kwargs)
        row["case_id"] = f"boundary_{idx:03d}"
        specs.append(row)
        idx += 1

    for age in (30, 59, 60, 79):
        add(age=age, case_note="age_horizon")
    for sbp in (90, 110, 130, 200):
        add(sbp=sbp, case_note="sbp_spline")
    for egfr in (30.0, 60.0, 90.0, 120.0):
        add(egfr=egfr, case_note="egfr_spline")
    for bmi in (18.5, 25.0, 30.0, 39.9):
        add(bmi=bmi, case_note="bmi_spline")
    for tc, hdl in ((130, 20), (320, 100)):
        add(tc=tc, hdl=hdl, case_note="lipid_bounds")
    add(sex=0, uacr=0.05, case_note="uacr_floor")
    add(uacr=150.0, hba1c=8.5, sdi=10.0, case_note="all_optional_present")
    add(uacr=np.nan, hba1c=np.nan, sdi=np.nan, case_note="all_optional_missing")
    add(sex=0, age=75, tc=240, hdl=90, sbp=130, dm=0, smoking=0, bmi=30, egfr=105, bptreat=1, statin=1, uacr=10.0)
    add(sex=1, age=39, tc=190, hdl=50, sbp=110, dm=1, smoking=0, bmi=np.nan, egfr=120, hba1c=8.0)
    add(sex=0, age=58, tc=267, hdl=np.nan, sbp=150, bmi=35, egfr=45, bptreat=1, statin=np.nan, sdi=8.0)
    add(sex=1, age=50, tc=200, hdl=45, sbp=160, dm=1, smoking=0, bmi=35, egfr=90, bptreat=1, statin=0)

    df = pd.DataFrame(specs)
    return df.drop(columns=["case_note"], errors="ignore")
