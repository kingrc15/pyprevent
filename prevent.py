from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = [
    "PAT_ID", "AGE", "SEX", "TCHOL", "HDL", "SBP", "BMI", "EGFR",
    "T2DM", "RECENT_SMOKING", "SMOKING_CURR", "UACR", "HBA1C",
    "ADI", "SVI", "ZIP"
]


def _mmol_conversion(cholesterol_mgdl: float) -> float:
    return 0.02586 * cholesterol_mgdl


def _sdicat(sdi: float) -> float:
    if pd.isna(sdi):
        return np.nan
    if 0 < sdi < 4:
        return 0.0
    elif 4 <= sdi < 7:
        return 1.0
    elif 7 <= sdi <= 10:
        return 2.0
    return np.nan


def _sigmoid_pct(x: float) -> float:
    return 100.0 / (1.0 + math.exp(-x))

def adjust(uacr: float):
    if pd.isna(uacr):
        return None
    if uacr >= 0.1:
        return uacr
    elif 0 <= uacr < 0.1:
        return 0.1
    return None


def _to_float(x) -> float:
    try:
        if pd.isna(x):
            return np.nan
        return float(x)
    except Exception:
        return np.nan


def _to_binary01(x) -> float:
    try:
        if pd.isna(x):
            return np.nan
        x = int(x)
        return float(x) if x in (0, 1) else np.nan
    except Exception:
        return np.nan


def _normalize_sex(x) -> float:
    """
    PREVENT source expects:
      0 = male
      1 = female
    """
    if pd.isna(x):
        return np.nan
    s = str(x).strip().lower()
    if s in {"m", "male", "0"}:
        return 0.0
    if s in {"f", "female", "1"}:
        return 1.0
    try:
        xv = float(x)
        if xv in (0.0, 1.0):
            return xv
    except Exception:
        pass
    return np.nan


def _clip_inputs(row: pd.Series) -> dict:
    out = {
        "PAT_ID": row.get("PAT_ID"),
        "AGE": _to_float(row.get("AGE")),
        "SEX": _normalize_sex(row.get("SEX")),
        "TCHOL": _to_float(row.get("TCHOL")),
        "HDL": _to_float(row.get("HDL")),
        "SBP": _to_float(row.get("SBP")),
        "BMI": _to_float(row.get("BMI")),
        "EGFR": _to_float(row.get("EGFR")),
        "T2DM": _to_binary01(row.get("T2DM")),
        "RECENT_SMOKING": _to_binary01(row.get("RECENT_SMOKING")),
        "SMOKING_CURR": _to_binary01(row.get("SMOKING_CURR")),
        "UACR": _to_float(row.get("UACR")),
        "HBA1C": _to_float(row.get("HBA1C")),
        "ADI": _to_float(row.get("ADI")),
        "SVI": _to_float(row.get("SVI")),
        "ZIP": None if pd.isna(row.get("ZIP")) else str(row.get("ZIP"))[:5],
    }

    # Match the earlier R wiring: cap to valid ranges before passing into the model.
    # This is from your PREVENT scoring pipeline, not from the AHAprevent core function itself.
    out["AGE"] = np.clip(out["AGE"], 30, 79) if not pd.isna(out["AGE"]) else np.nan
    out["SBP"] = np.clip(out["SBP"], 90, 200) if not pd.isna(out["SBP"]) else np.nan
    out["TCHOL"] = np.clip(out["TCHOL"], 130, 320) if not pd.isna(out["TCHOL"]) else np.nan
    out["HDL"] = np.clip(out["HDL"], 20, 100) if not pd.isna(out["HDL"]) else np.nan
    out["BMI"] = np.clip(out["BMI"], 18.5, 39.9) if not pd.isna(out["BMI"]) else np.nan
    out["EGFR"] = np.clip(out["EGFR"], 15, 140) if not pd.isna(out["EGFR"]) else np.nan
    out["HBA1C"] = np.clip(out["HBA1C"], 3, 15) if not pd.isna(out["HBA1C"]) else np.nan
    out["UACR"] = np.clip(out["UACR"], 0, 25000) if not pd.isna(out["UACR"]) else np.nan

    return out


def _validate_common_inputs(age, sex, sbp, dm, smoking, egfr) -> bool:
    if pd.isna(age) or age < 30 or age > 79:
        return False
    if pd.isna(sex) or sex not in (0.0, 1.0):
        return False
    if pd.isna(sbp) or sbp < 90 or sbp > 200:
        return False
    if pd.isna(dm) or dm not in (0.0, 1.0):
        return False
    if pd.isna(smoking) or smoking not in (0.0, 1.0):
        return False
    if pd.isna(egfr) or egfr <= 0:
        return False
    return True


def _prevent_10yr_base(
    sex: float,
    age: float,
    tc: float,
    hdl: float,
    sbp: float,
    dm: float,
    smoking: float,
    bmi: float,
    egfr: float,
    bptreat: float,
    statin: float,
) -> dict:
    """
    10-year PREVENT base equation translated from the uploaded AHAprevent R source.
    """
    if not _validate_common_inputs(age, sex, sbp, dm, smoking, egfr):
        return {"CVD": np.nan, "ASCVD": np.nan, "HF": np.nan}

    # ASCVD/CVD require tc/hdl/statin. HF requires bmi.
    can_cvd_ascvd = not (
        pd.isna(tc) or tc < 130 or tc > 320 or
        pd.isna(hdl) or hdl < 20 or hdl > 100 or
        pd.isna(statin) or statin not in (0.0, 1.0) or
        pd.isna(bptreat) or bptreat not in (0.0, 1.0)
    )
    can_hf = not (
        pd.isna(bmi) or bmi < 18.5 or bmi >= 40 or
        pd.isna(bptreat) or bptreat not in (0.0, 1.0)
    )

    if sex == 1.0:  # female in the uploaded source
        if can_cvd_ascvd:
            logor_10yr_CVD = (
                -3.307728 +
                0.7939329*(age - 55)/10 +
                0.0305239*(_mmol_conversion(tc - hdl) - 3.5) -
                0.1606857*(_mmol_conversion(hdl) - 1.3)/(0.3) -
                0.2394003*(min(sbp, 110) - 110)/20 +
                0.360078*(max(sbp, 110) - 130)/20 +
                0.8667604*(dm) +
                0.5360739*(smoking) +
                0.6045917*(min(egfr, 60) - 60)/(-15) +
                0.0433769*(max(egfr, 60) - 90)/(-15) +
                0.3151672*(bptreat) -
                0.1477655*(statin) -
                0.0663612*(bptreat)*(max(sbp, 110) - 130)/20 +
                0.1197879*(statin)*(_mmol_conversion(tc - hdl) - 3.5) -
                0.0819715*(age - 55)/10*(_mmol_conversion(tc - hdl) - 3.5) +
                0.0306769*(age - 55)/10*(_mmol_conversion(hdl) - 1.3)/(0.3) -
                0.0946348*(age - 55)/10*(max(sbp, 110) - 130)/20 -
                0.27057*(age - 55)/10*(dm) -
                0.078715*(age - 55)/10*(smoking) -
                0.1637806*(age - 55)/10*(min(egfr, 60) - 60)/(-15)
            )

            logor_10yr_ASCVD = (
                -3.819975 +
                0.719883*(age - 55)/10 +
                0.1176967*((_mmol_conversion(tc) - _mmol_conversion(hdl)) - 3.5) -
                0.151185*(_mmol_conversion(hdl) - 1.3)/0.3 - 0.0835358*(min(sbp, 110) - 110)/20 +
                0.3592852*(max(sbp, 110) - 130)/20 +
                0.8348585*(dm) + 0.4831078*(smoking) +
                0.4864619*(min(egfr, 60) - 60)/(-15) +
                0.0397779*(max(egfr, 60)  - 90)/(-15) +
                0.2265309*(bptreat) -
                0.0592374*(statin) -
                0.0395762*(bptreat)*(max(sbp, 110) - 130)/20  +
                0.0844423*(statin)*((_mmol_conversion(tc) - _mmol_conversion(hdl)) - 3.5) -
                0.0567839*(age - 55)/10*((_mmol_conversion(tc) - _mmol_conversion(hdl)) - 3.5) +
                0.0325692*(age - 55)/10*(_mmol_conversion(hdl) - 1.3)/0.3 -
                0.1035985*(age - 55)/10*(max(sbp, 110) - 130)/20 -
                0.2417542*(age - 55)/10*(dm) -
                0.0791142*(age - 55)/10*(smoking) -
                0.1671492*(age - 55)/10*(min(egfr, 60) - 60)/(-15)
            )
        else:
            logor_10yr_CVD = np.nan
            logor_10yr_ASCVD = np.nan

        if can_hf:
            logor_10yr_HF = (
                -4.310409 +
                0.8998235*(age - 55)/10 -
                0.4559771*(min(sbp, 110) - 110)/20 +
                0.3576505*(max(sbp, 110) - 130)/20 +
                1.038346*(dm) +
                0.583916*(smoking) -
                0.0072294*(min(bmi, 30) - 25)/5 +
                0.2997706*(max(bmi, 30) - 30)/5 +
                0.7451638*(min(egfr, 60) - 60)/(-15) +
                0.0557087*(max(egfr, 60)  - 90)/(-15) +
                0.3534442*(bptreat) -
                0.0981511*(bptreat)*(max(sbp, 110) - 130)/20  -
                0.0946663*(age - 55)/10*(max(sbp, 110) - 130)/20 -
                0.3581041*(age - 55)/10*(dm) -
                0.1159453*(age - 55)/10*(smoking) -
                0.003878*(age - 55)/10*(max(bmi, 30) - 30)/5 -
                0.1884289*(age - 55)/10*(min(egfr, 60) - 60)/(-15)
            )
        else:
            logor_10yr_HF = np.nan

    else:  # male in the uploaded source
        if can_cvd_ascvd:
            logor_10yr_CVD = (
                -3.031168 +
                0.7688528*(age - 55)/10 +
                0.0736174*(_mmol_conversion(tc - hdl) - 3.5) -
                0.0954431*(_mmol_conversion(hdl) - 1.3)/(0.3) -
                0.4347345*(min(sbp, 110) - 110)/20 +
                0.3362658*(max(sbp, 110) - 130)/20 +
                0.7692857*(dm) +
                0.4386871*(smoking) +
                0.5378979*(min(egfr, 60) - 60)/(-15) +
                0.0164827*(max(egfr, 60) - 90)/(-15) +
                0.288879*(bptreat) -
                0.1337349*(statin) -
                0.0475924*(bptreat)*(max(sbp, 110) - 130)/20 +
                0.150273*(statin)*(_mmol_conversion(tc - hdl) - 3.5) -
                0.0517874*(age - 55)/10*(_mmol_conversion(tc - hdl) - 3.5) +
                0.0191169*(age - 55)/10*(_mmol_conversion(hdl) - 1.3)/(0.3) -
                0.1049477*(age - 55)/10*(max(sbp, 110) - 130)/20 -
                0.2251948*(age - 55)/10*(dm) -
                0.0895067*(age - 55)/10*(smoking) -
                0.1543702*(age - 55)/10*(min(egfr, 60) - 60)/(-15)
            )

            logor_10yr_ASCVD = (
                -3.500655 +
                0.7099847*(age - 55)/10 +
                0.1658663*((_mmol_conversion(tc) - _mmol_conversion(hdl)) - 3.5) -
                0.1144285*(_mmol_conversion(hdl) - 1.3)/0.3 - 0.2837212*(min(sbp, 110) - 110)/20 +
                0.3239977*(max(sbp, 110) - 130)/20 +
                0.7189597*(dm) +
                0.3956973*(smoking) +
                0.3690075*(min(egfr, 60) - 60)/(-15) +
                0.0203619*(max(egfr, 60)  - 90)/(-15) +
                0.2036522*(bptreat) -
                0.0865581*(statin) -
                0.0322916*(bptreat)*(max(sbp, 110) - 130)/20 +
                0.114563*(statin)*((_mmol_conversion(tc) - _mmol_conversion(hdl)) - 3.5) -
                0.0300005*(age - 55)/10*((_mmol_conversion(tc) - _mmol_conversion(hdl)) - 3.5) +
                0.0232747*(age - 55)/10*(_mmol_conversion(hdl) - 1.3)/0.3 -
                0.0927024*(age - 55)/10*(max(sbp, 110) - 130)/20 -
                0.2018525*(age - 55)/10*(dm) -
                0.0970527*(age - 55)/10*(smoking) -
                0.1217081*(age - 55)/10*(min(egfr, 60) - 60)/(-15)
            )
        else:
            logor_10yr_CVD = np.nan
            logor_10yr_ASCVD = np.nan

        if can_hf:
            logor_10yr_HF = (
                -3.946391 +
                0.8972642*(age - 55)/10 -
                0.6811466*(min(sbp, 110) - 110)/20 +
                0.3634461*(max(sbp, 110) - 130)/20 +
                0.923776*(dm) +
                0.5023736*(smoking) -
                0.0485841*(min(bmi, 30) - 25)/5 +
                0.3726929*(max(bmi, 30) - 30)/5 +
                0.6926917*(min(egfr, 60) - 60)/(-15) +
                0.0251827*(max(egfr, 60)  - 90)/(-15) +
                0.2980922*(bptreat) -
                0.0497731*(bptreat)*(max(sbp, 110) - 130)/20 -
                0.1289201*(age - 55)/10*(max(sbp, 110) - 130)/20 -
                0.3040924*(age - 55)/10*(dm) -
                0.1401688*(age - 55)/10*(smoking) +
                0.0068126*(age - 55)/10*(max(bmi, 30) - 30)/5 -
                0.1797778*(age - 55)/10*(min(egfr, 60) - 60)/(-15)
            )
        else:
            logor_10yr_HF = np.nan

    return {
        "PREVENT10_CVD_BASIC_PCT": _sigmoid_pct(logor_10yr_CVD) if not pd.isna(logor_10yr_CVD) else np.nan,
        "PREVENT10_ASCVD_BASIC_PCT": _sigmoid_pct(logor_10yr_ASCVD) if not pd.isna(logor_10yr_ASCVD) else np.nan,
        "PREVENT10_HF_BASIC_PCT": _sigmoid_pct(logor_10yr_HF) if not pd.isna(logor_10yr_HF) else np.nan,
    }


def _prevent_10yr_full(
    sex: float,
    age: float,
    tc: float,
    hdl: float,
    sbp: float,
    dm: float,
    smoking: float,
    bmi: float,
    egfr: float,
    bptreat: float,
    statin: float,
    uacr: float,
    hba1c: float,
    sdi: float = np.nan,
) -> dict:
    """
    10-year PREVENT full equation translated from the uploaded AHAprevent R source.
    Uses the missing-coefficient path when sdi/uacr/hba1c are NA, matching the R code.
    """
    if not _validate_common_inputs(age, sex, sbp, dm, smoking, egfr):
        return {"CVD": np.nan, "ASCVD": np.nan, "HF": np.nan}

    can_cvd_ascvd = not (
        pd.isna(tc) or tc < 130 or tc > 320 or
        pd.isna(hdl) or hdl < 20 or hdl > 100 or
        pd.isna(statin) or statin not in (0.0, 1.0) or
        pd.isna(bptreat) or bptreat not in (0.0, 1.0)
    )
    can_hf = not (
        pd.isna(bmi) or bmi < 18.5 or bmi >= 40 or
        pd.isna(bptreat) or bptreat not in (0.0, 1.0)
    )

    def sdi_term(f0, f1):
        if not pd.isna(sdi):
            s = _sdicat(sdi)
            return f0 * (2 - s) * s + f1 * (s - 1) * (0.5 * s)
        return np.nan

    if sex == 1.0:  # female in source
        if can_cvd_ascvd:
            sdi_cvd = sdi_term(0.1361989, 0.2261596)
            sdi_ascvd = sdi_term(0.1413965, 0.228136)

            logor_10yr_CVD = (
                -3.860385 +
                + 0.7716794 * ((age - 55) / 10)
                + 0.0062109 * (_mmol_conversion(tc - hdl) - 3.5)
                - 0.1547756 * (_mmol_conversion(hdl) - 1.3) / 0.3
                - 0.1933123 * (min(sbp, 110) - 110) / 20
                + 0.3071217 * (max(sbp, 110) - 130) / 20
                + 0.496753 * dm
                + 0.466605 * smoking
                + 0.4780697 * (min(egfr, 60) - 60) / (-15)
                + 0.0529077 * (max(egfr, 60) - 90) / (-15)
                + 0.3034892 * bptreat
                - 0.1556524 * statin
                - 0.0667026 * bptreat * (max(sbp, 110) - 130) / 20
                + 0.1061825 * statin * (_mmol_conversion(tc - hdl) - 3.5)
                - 0.0742271 * ((age - 55) / 10) * (_mmol_conversion(tc - hdl) - 3.5)
                + 0.0288245 * ((age - 55) / 10) * (_mmol_conversion(hdl) - 1.3) / 0.3
                - 0.0875188 * ((age - 55) / 10) * (max(sbp, 110) - 130) / 20
                - 0.2267102 * ((age - 55) / 10) * dm
                - 0.0676125 * ((age - 55) / 10) * smoking
                - 0.1493231 * ((age - 55) / 10) * (min(egfr, 60) - 60) / (-15)
                + (
                    0.1361989 * (2 - _sdicat(sdi)) * _sdicat(sdi)
                    + 0.2261596 * (_sdicat(sdi) - 1) * (0.5 * _sdicat(sdi))
                    if not pd.isna(sdi)
                    else 0.1804508
                )
                + (
                    0.1645922 * math.log(adjust(uacr))
                    if not pd.isna(uacr)
                    else 0.0198413
                )
                + (
                    0.1298513 * (hba1c - 5.3) * dm
                    + 0.1412555 * (hba1c - 5.3) * (1 - dm)
                    if not pd.isna(hba1c)
                    else -0.0031658
                )
            )

            logor_10yr_ASCVD = (
                -4.291503
                + 0.7023067 * ((age - 55) / 10)
                + 0.0898765 * ((_mmol_conversion(tc) - _mmol_conversion(hdl)) - 3.5)
                - 0.1407316 * (_mmol_conversion(hdl) - 1.3) / 0.3
                - 0.0256648 * (min(sbp, 110) - 110) / 20
                + 0.314511 * (max(sbp, 110) - 130) / 20
                + 0.4799217 * dm
                + 0.4062049 * smoking
                + 0.3847744 * (min(egfr, 60) - 60) / (-15)
                + 0.0495174 * (max(egfr, 60) - 90) / (-15)
                + 0.2133861 * bptreat
                - 0.0678552 * statin
                - 0.0451416 * bptreat * (max(sbp, 110) - 130) / 20
                + 0.0788187 * statin * ((_mmol_conversion(tc) - _mmol_conversion(hdl)) - 3.5)
                - 0.0535985 * ((age - 55) / 10) * ((_mmol_conversion(tc) - _mmol_conversion(hdl)) - 3.5)
                + 0.0291762 * ((age - 55) / 10) * (_mmol_conversion(hdl) - 1.3) / 0.3
                - 0.0961839 * ((age - 55) / 10) * (max(sbp, 110) - 130) / 20
                - 0.2001466 * ((age - 55) / 10) * dm
                - 0.0586472 * ((age - 55) / 10) * smoking
                - 0.1537791 * ((age - 55) / 10) * (min(egfr, 60) - 60) / (-15)
                + (
                    0.1413965 * ((2 - _sdicat(sdi)) * _sdicat(sdi))
                    + 0.228136 * ((_sdicat(sdi) - 1) * (0.5 * _sdicat(sdi)))
                    if not pd.isna(sdi)
                    else 0.1588908
                )
                + (
                    0.1371824 * math.log(adjust(uacr))
                    if not pd.isna(uacr)
                    else 0.0061613
                )
                + (
                    0.123192 * (hba1c - 5.3) * dm
                    + 0.1410572 * (hba1c - 5.3) * (1 - dm)
                    if not pd.isna(hba1c)
                    else 0.005866
                )
            )
        else:
            logor_10yr_CVD = np.nan
            logor_10yr_ASCVD = np.nan

        if can_hf:
            sdi_hf = sdi_term(0.1213034, 0.2314147)

            logor_10yr_HF = (
                -4.896524
                + 0.884209 * ((age - 55) / 10)
                - 0.421474 * (min(sbp, 110) - 110) / 20
                + 0.3002919 * (max(sbp, 110) - 130) / 20
                + 0.6170359 * dm
                + 0.5380269 * smoking
                - 0.0191335 * (min(bmi, 30) - 25) / 5
                + 0.2764302 * (max(bmi, 30) - 30) / 5
                + 0.5975847 * (min(egfr, 60) - 60) / (-15)
                + 0.0654197 * (max(egfr, 60) - 90) / (-15)
                + 0.3313614 * bptreat
                - 0.1002304 * bptreat * (max(sbp, 110) - 130) / 20
                - 0.0845363 * ((age - 55) / 10) * (max(sbp, 110) - 130) / 20
                - 0.2989062 * ((age - 55) / 10) * dm
                - 0.1111354 * ((age - 55) / 10) * smoking
                + 0.0008104 * ((age - 55) / 10) * (max(bmi, 30) - 30) / 5
                - 0.1666635 * ((age - 55) / 10) * (min(egfr, 60) - 60) / (-15)
                + (
                    0.1213034 * ((2 - _sdicat(sdi)) * _sdicat(sdi))
                    + 0.2314147 * ((_sdicat(sdi) - 1) * (0.5 * _sdicat(sdi)))
                    if not pd.isna(sdi)
                    else 0.1819138
                )
                + (
                    0.1948135 * math.log(adjust(uacr))
                    if not pd.isna(uacr)
                    else 0.0395368
                )
                + (
                    0.176668 * (hba1c - 5.3) * dm
                    + 0.1614911 * (hba1c - 5.3) * (1 - dm)
                    if not pd.isna(hba1c)
                    else -0.0010583
                )
            )
        else:
            logor_10yr_HF = np.nan

    else:  # male in source
        if can_cvd_ascvd:
            sdi_cvd = sdi_term(0.0802431, 0.275073)
            sdi_ascvd = sdi_term(0.0651121, 0.2676683)

            logor_10yr_CVD = (
                -3.631387
                + 0.7847578 * ((age - 55) / 10)
                + 0.0534485 * (_mmol_conversion(tc - hdl) - 3.5)
                - 0.0911282 * (_mmol_conversion(hdl) - 1.3) / 0.3
                - 0.4921973 * (min(sbp, 110) - 110) / 20
                + 0.2972415 * (max(sbp, 110) - 130) / 20
                + 0.4527054 * dm
                + 0.3726641 * smoking
                + 0.3886854 * (min(egfr, 60) - 60) / (-15)
                + 0.0081661 * (max(egfr, 60) - 90) / (-15)
                + 0.2508052 * bptreat
                - 0.1538484 * statin
                - 0.0474695 * bptreat * (max(sbp, 110) - 130) / 20
                + 0.1415382 * statin * (_mmol_conversion(tc - hdl) - 3.5)
                - 0.0436455 * ((age - 55) / 10) * (_mmol_conversion(tc - hdl) - 3.5)
                + 0.0199549 * ((age - 55) / 10) * (_mmol_conversion(hdl) - 1.3) / 0.3
                - 0.1022686 * ((age - 55) / 10) * (max(sbp, 110) - 130) / 20
                - 0.1762507 * ((age - 55) / 10) * dm
                - 0.0715873 * ((age - 55) / 10) * smoking
                - 0.1428668 * ((age - 55) / 10) * (min(egfr, 60) - 60) / (-15)
                + (
                    0.0802431 * (2 - _sdicat(sdi)) * _sdicat(sdi)
                    + 0.275073 * (_sdicat(sdi) - 1) * (0.5 * _sdicat(sdi))
                    if not pd.isna(sdi)
                    else 0.144759
                )
                + (
                    0.1772853 * math.log(adjust(uacr))
                    if not pd.isna(uacr)
                    else 0.1095674
                )
                + (
                    0.1165698 * (hba1c - 5.3) * dm
                    + 0.1048297 * (hba1c - 5.3) * (1 - dm)
                    if not pd.isna(hba1c)
                    else -0.0230072
                )
            )

            logor_10yr_ASCVD = (
                -3.969788
                + 0.7128741 * ((age - 55) / 10)
                + 0.1465201 * ((_mmol_conversion(tc) - _mmol_conversion(hdl)) - 3.5)
                - 0.1125794 * (_mmol_conversion(hdl) - 1.3) / 0.3
                - 0.3387216 * (min(sbp, 110) - 110) / 20
                + 0.2980252 * (max(sbp, 110) - 130) / 20
                + 0.399583 * dm
                + 0.3379111 * smoking
                + 0.2582604 * (min(egfr, 60) - 60) / (-15)
                + 0.0147769 * (max(egfr, 60) - 90) / (-15)
                + 0.1686621 * bptreat
                - 0.1073619 * statin
                - 0.0381038 * bptreat * (max(sbp, 110) - 130) / 20
                + 0.1034169 * statin * ((_mmol_conversion(tc) - _mmol_conversion(hdl)) - 3.5)
                - 0.0228755 * ((age - 55) / 10) * ((_mmol_conversion(tc) - _mmol_conversion(hdl)) - 3.5)
                + 0.0267453 * ((age - 55) / 10) * (_mmol_conversion(hdl) - 1.3) / 0.3
                - 0.0897449 * ((age - 55) / 10) * (max(sbp, 110) - 130) / 20
                - 0.1497464 * ((age - 55) / 10) * dm
                - 0.077206 * ((age - 55) / 10) * smoking
                - 0.1198368 * ((age - 55) / 10) * (min(egfr, 60) - 60) / (-15)
                + (
                    0.0651121 * ((2 - _sdicat(sdi)) * _sdicat(sdi))
                    + 0.2676683 * ((_sdicat(sdi) - 1) * (0.5 * _sdicat(sdi)))
                    if not pd.isna(sdi)
                    else 0.1388492
                )
                + (
                    0.1375837 * math.log(adjust(uacr))
                    if not pd.isna(uacr)
                    else 0.0652944
                )
                + (
                    0.101282 * (hba1c - 5.3) * dm
                    + 0.1092726 * (hba1c - 5.3) * (1 - dm)
                    if not pd.isna(hba1c)
                    else -0.0112852
                )
            )
        else:
            logor_10yr_CVD = np.nan
            logor_10yr_ASCVD = np.nan

        if can_hf:
            sdi_hf = sdi_term(0.1106372, 0.3371204)

            logor_10yr_HF = (
                -4.663513 +
                0.9095703*((age - 55)/10) -
                0.6765184*(min(sbp, 110) - 110)/20 +
                0.3111651*(max(sbp, 110) - 130)/20 +
                0.5535052*(dm) +
                0.4326811*(smoking) -
                0.0854286*(min(bmi, 30) - 25)/5 +
                0.3551736*(max(bmi, 30) - 30)/5 +
                0.5102245*(min(egfr, 60) - 60)/(-15) +
                0.015472*(max(egfr, 60) - 90)/(-15) +
                0.2570964*(bptreat) -
                0.0591177*(bptreat)*(max(sbp, 110) - 130)/20 -
                0.1219056*(age - 55)/10*(max(sbp, 110) - 130)/20 -
                0.2437577*(age - 55)/10*(dm) -
                0.105363*(age - 55)/10*(smoking) +
                0.0037907*(age - 55)/10*(max(bmi, 30) - 30)/5 -
                0.1660207*(age - 55)/10*(min(egfr, 60) - 60)/(-15) +
                (
                    0.1106372 * ((2 - _sdicat(sdi)) * _sdicat(sdi))
                    + 0.3371204 * ((_sdicat(sdi) - 1) * (0.5 * _sdicat(sdi)))
                    if not pd.isna(sdi)
                    else 0.1694628
                )
                + (
                    0.2164607 * math.log(adjust(uacr))
                    if not pd.isna(uacr)
                    else 0.1702805
                )
                + (
                    0.148297 * (hba1c - 5.3) * dm
                    + 0.1234088 * (hba1c - 5.3) * (1 - dm)
                    if not pd.isna(hba1c)
                    else -0.0234637
                )
            )
        else:
            logor_10yr_HF = np.nan

    return {
        "PREVENT10_CVD_FULL_PCT": _sigmoid_pct(logor_10yr_CVD) if not pd.isna(logor_10yr_CVD) else np.nan,
        "PREVENT10_ASCVD_FULL_PCT": _sigmoid_pct(logor_10yr_ASCVD) if not pd.isna(logor_10yr_ASCVD) else np.nan,
        "PREVENT10_HF_FULL_PCT": _sigmoid_pct(logor_10yr_HF) if not pd.isna(logor_10yr_HF) else np.nan,
    }


def compute_prevent10(
    df: pd.DataFrame,
    bp_treat_default: Optional[int] = 0,
    statin_default: Optional[int] = 0,
    smoking_preference: str = "SMOKING_CURR",
    sdi_series: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    Compute 10-year PREVENT basic + full scores.

    Parameters
    ----------
    df : pandas.DataFrame
        Must contain:
        ['PAT_ID', 'AGE', 'SEX', 'TCHOL', 'HDL', 'SBP', 'BMI', 'EGFR',
         'T2DM', 'RECENT_SMOKING', 'SMOKING_CURR', 'UACR', 'HBA1C',
         'ADI', 'SVI', 'ZIP']

    bp_treat_default : 0/1/None
        PREVENT needs BP treatment status, but your reduced schema does not include it.
        If None, CVD/ASCVD/HF outputs will become NaN when BP treatment is required.

    statin_default : 0/1/None
        PREVENT needs statin status for CVD/ASCVD, but your reduced schema does not include it.
        If None, CVD/ASCVD outputs will become NaN.

    smoking_preference : {"SMOKING_CURR", "RECENT_SMOKING"}
        Which smoking column to use.

    sdi_series : pandas.Series or None
        Optional true SDI decile (1-10). If omitted, the full model uses the
        missing-SDI coefficient path from the original R implementation.

    Returns
    -------
    pandas.DataFrame
        Original dataframe plus:
        PREVENT10_CVD_BASIC_PCT
        PREVENT10_ASCVD_BASIC_PCT
        PREVENT10_HF_BASIC_PCT
        PREVENT10_CVD_FULL_PCT
        PREVENT10_ASCVD_FULL_PCT
        PREVENT10_HF_FULL_PCT
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    out = df.copy()

    if smoking_preference not in {"SMOKING_CURR", "RECENT_SMOKING"}:
        raise ValueError("smoking_preference must be 'SMOKING_CURR' or 'RECENT_SMOKING'")

    rows = []
    for pos, (_, row) in enumerate(out.iterrows()):
        r = _clip_inputs(row)

        smoking = r[smoking_preference]
        bptreat = _to_binary01(bp_treat_default) if bp_treat_default is not None else np.nan
        statin = _to_binary01(statin_default) if statin_default is not None else np.nan
        sdi = _to_float(sdi_series.iloc[pos]) if sdi_series is not None else np.nan

        base = _prevent_10yr_base(
            sex=r["SEX"],
            age=r["AGE"],
            tc=r["TCHOL"],
            hdl=r["HDL"],
            sbp=r["SBP"],
            dm=r["T2DM"],
            smoking=smoking,
            bmi=r["BMI"],
            egfr=r["EGFR"],
            bptreat=bptreat,
            statin=statin,
        )

        full = _prevent_10yr_full(
            sex=r["SEX"],
            age=r["AGE"],
            tc=r["TCHOL"],
            hdl=r["HDL"],
            sbp=r["SBP"],
            dm=r["T2DM"],
            smoking=smoking,
            bmi=r["BMI"],
            egfr=r["EGFR"],
            bptreat=bptreat,
            statin=statin,
            uacr=r["UACR"],
            hba1c=r["HBA1C"],
            sdi=sdi,
        )

        rows.append({**base, **full})

    scores = pd.DataFrame(rows, index=out.index)
    for col in scores.columns:
        out[col] = scores[col]

    return out
