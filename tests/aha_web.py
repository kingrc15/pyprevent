from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from prevent import compute_prevent

# Official PHD Sitecore endpoint used by <ckm-risk-calculator> on the PREVENT page.
DEFAULT_AHA_PREVENT_API = (
    "https://professional.heart.org/aha-service/PHDSearch/PreventCalculate"
)
AHA_WEB_ATOL = 0.05  # web UI displays one decimal; API matches to 0.1 pp

_MODEL_TO_SUFFIX = {
    "Base Model": "BASE",
    "Full Model": "FULL",
    "Model that included UACR": "UACR",
    "Model that included HbA1C": "HBA1C",
    "Model that included SDI based on zip code": "SDI",
}

_OUTCOME_TO_KEY = {
    "CVD": "CVD",
    "ASCVD": "ASCVD",
    "Heart Failure": "HF",
}


@dataclass(frozen=True)
class AhaWebCase:
    case_id: str
    sex: int  # R convention: 0 male, 1 female
    age: float
    tc: float
    hdl: float
    sbp: float
    bmi: float
    egfr: float
    dm: int
    smoking: int
    bptreat: int
    statin: int
    uacr: float | None = None
    hba1c: float | None = None
    zip_code: str | None = None


def aha_api_url() -> str:
    return os.environ.get("PREVENT_AHA_WEB_API", DEFAULT_AHA_PREVENT_API)


def web_gender_type(sex: int) -> int:
    """Map R sex (0=male, 1=female) to AHA API genderType (1=female, 2=male)."""
    return 1 if int(sex) == 1 else 2


def case_to_web_payload(case: AhaWebCase) -> dict[str, Any]:
    return {
        "genderType": web_gender_type(case.sex),
        "age": float(case.age),
        "totalCholesterol": float(case.tc),
        "hdlCholesterol": float(case.hdl),
        "sbp": float(case.sbp),
        "bmi": float(case.bmi),
        "egfr": float(case.egfr),
        "isAntihyperTensiveMedicUsed": bool(case.bptreat),
        "isLipidLoweringMedicUsed": bool(case.statin),
        "isDiabetes": bool(case.dm),
        "isSmoker": bool(case.smoking),
        "uacr": None if case.uacr is None or pd.isna(case.uacr) else float(case.uacr),
        "hbA1C": None if case.hba1c is None or pd.isna(case.hba1c) else float(case.hba1c),
        "zipCode": None if case.zip_code is None or (isinstance(case.zip_code, float) and pd.isna(case.zip_code)) else str(case.zip_code),
    }


def aha_web_available() -> bool:
    try:
        score_case_web(
            AhaWebCase(
                case_id="probe",
                sex=1,
                age=50,
                tc=200,
                hdl=50,
                sbp=130,
                bmi=28,
                egfr=85,
                dm=0,
                smoking=0,
                bptreat=0,
                statin=0,
            )
        )
        return True
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError):
        return False


def score_case_web(case: AhaWebCase, *, timeout: float = 30.0) -> dict[str, Any]:
    payload = case_to_web_payload(case)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        aha_api_url(),
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "pyprevent-parity-test/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if not body.get("success"):
        raise ValueError(f"AHA API error for {case.case_id}: {body}")
    return body


def _web_ten_year_map(body: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for item in body.get("tenYearRiskEstimations", []):
        key = _OUTCOME_TO_KEY.get(item["Type"])
        if key:
            out[key] = float(item["RiskPercentage"])
    return out


def _web_thirty_year_map(body: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for item in body.get("thirtyYearRiskEstimations", []):
        key = _OUTCOME_TO_KEY.get(item["Type"])
        if key:
            out[key] = float(item["RiskPercentage"])
    return out


def _model_suffix(model_name: str) -> str:
    suffix = _MODEL_TO_SUFFIX.get(model_name)
    if suffix is None:
        raise KeyError(f"Unknown AHA web modelName: {model_name!r}")
    return suffix


def score_case_python(case: AhaWebCase, *, model_suffix: str) -> tuple[dict[str, float], dict[str, float]]:
    # Unknown ZIP → missing-SDI coefficients (matches web when zipCode is null).
    zip_val = case.zip_code if case.zip_code is not None else "99999"
    df = pd.DataFrame(
        [
            {
                "PAT_ID": case.case_id,
                "AGE": case.age,
                "SEX": case.sex,
                "TCHOL": case.tc,
                "HDL": case.hdl,
                "SBP": case.sbp,
                "BMI": case.bmi,
                "EGFR": case.egfr,
                "T2DM": case.dm,
                "RECENT_SMOKING": case.smoking,
                "SMOKING_CURR": case.smoking,
                "UACR": case.uacr if case.uacr is not None else np.nan,
                "HBA1C": case.hba1c if case.hba1c is not None else np.nan,
                "ZIP": zip_val,
                "BPTREAT": case.bptreat,
                "STATIN": case.statin,
            }
        ]
    )
    out = compute_prevent(df, smoking_preference="SMOKING_CURR")
    ten = {
        outcome: float(out[f"PREVENT10_{outcome}_{model_suffix}_PCT"].iloc[0])
        for outcome in ("CVD", "ASCVD", "HF")
    }
    thirty = {
        outcome: float(out[f"PREVENT30_{outcome}_{model_suffix}_PCT"].iloc[0])
        for outcome in ("CVD", "ASCVD", "HF")
    }
    return ten, thirty


def assert_case_matches_web(case: AhaWebCase, *, atol: float = AHA_WEB_ATOL) -> None:
    web_body = score_case_web(case)
    web_model = _model_suffix(web_body["modelName"])
    py_ten, py_thirty = score_case_python(case, model_suffix=web_model)

    web_ten = _web_ten_year_map(web_body)
    for outcome in ("CVD", "ASCVD", "HF"):
        w = web_ten.get(outcome)
        p = py_ten[outcome]
        if w is None:
            if not np.isnan(p):
                raise AssertionError(f"{case.case_id} 10yr {outcome}: web missing, python={p}")
            continue
        if not np.isclose(p, w, rtol=0.0, atol=atol, equal_nan=True):
            raise AssertionError(
                f"{case.case_id} 10yr {outcome}: python={p:.4f} web={w:.4f} "
                f"(Δ={abs(p - w):.4f})"
            )

    web_thirty = _web_thirty_year_map(web_body)
    for outcome in ("CVD", "ASCVD", "HF"):
        w = web_thirty.get(outcome)
        p = py_thirty[outcome]
        if w is None:
            if not np.isnan(p):
                raise AssertionError(f"{case.case_id} 30yr {outcome}: web missing, python={p}")
            continue
        if not np.isclose(p, w, rtol=0.0, atol=atol, equal_nan=True):
            raise AssertionError(
                f"{case.case_id} 30yr {outcome}: python={p:.4f} web={w:.4f} "
                f"(Δ={abs(p - w):.4f})"
            )


def benchmark_cases() -> list[AhaWebCase]:
    """Published / vignette inputs that match the official web calculator."""
    return [
        AhaWebCase(
            case_id="table_s25_female_base",
            sex=1,
            age=50,
            tc=200,
            hdl=45,
            sbp=160,
            bmi=35,
            egfr=90,
            dm=1,
            smoking=0,
            bptreat=1,
            statin=0,
        ),
        AhaWebCase(
            case_id="preventr_male_base",
            sex=0,
            age=66,
            tc=188,
            hdl=52,
            sbp=148,
            bmi=30,
            egfr=67,
            dm=1,
            smoking=1,
            bptreat=0,
            statin=1,
        ),
        AhaWebCase(
            case_id="ahaprevent_female_45",
            sex=1,
            age=45,
            tc=200,
            hdl=60,
            sbp=120,
            bmi=25,
            egfr=95,
            dm=1,
            smoking=0,
            bptreat=0,
            statin=0,
        ),
        AhaWebCase(
            case_id="preventr_full_female_66",
            sex=1,
            age=66,
            tc=188,
            hdl=52,
            sbp=148,
            bmi=30,
            egfr=67,
            dm=1,
            smoking=1,
            bptreat=0,
            statin=1,
            uacr=75,
            hba1c=9,
        ),
        AhaWebCase(
            case_id="vignette_uacr_male_75",
            sex=0,
            age=75,
            tc=240,
            hdl=90,
            sbp=130,
            bmi=30,
            egfr=105,
            dm=0,
            smoking=0,
            bptreat=1,
            statin=1,
            uacr=10,
        ),
        AhaWebCase(
            case_id="vignette_hba1c_female_39",
            sex=1,
            age=39,
            tc=190,
            hdl=50,
            sbp=110,
            bmi=25,
            egfr=120,
            dm=1,
            smoking=0,
            bptreat=0,
            statin=0,
            hba1c=8,
        ),
        AhaWebCase(
            case_id="zip_75201_sdi_base_inputs",
            sex=1,
            age=55,
            tc=200,
            hdl=50,
            sbp=130,
            bmi=28,
            egfr=85,
            dm=0,
            smoking=0,
            bptreat=0,
            statin=0,
            zip_code="75201",
        ),
    ]
