# pyprevent

A pure-Python, pandas-friendly implementation of the **American Heart
Association (AHA) PREVENT™ (Predicting Risk of CVD EVENTs)** 10-year risk
equations.

`prevent.py` ports the published AHA PREVENT coefficient set into a vectorized
workflow that consumes a `pandas.DataFrame` of patient features and returns
the same DataFrame with six new columns containing 10-year predicted risk (in
percent) for:

- **Total CVD** (atherosclerotic CVD + heart failure)
- **ASCVD** (atherosclerotic CVD: MI, stroke)
- **Heart Failure (HF)**

each estimated under both:

- the **Basic** model (traditional risk factors only), and
- the **Full** model (Basic + urine albumin-to-creatinine ratio, HbA1c, and
  Social Deprivation Index).

The model coefficients, input ranges, transformations, and missing-data
fallback paths in this file are translated from the official
[`AHAprevent` R source](https://github.com/AHA-Tools/AHAprevent) and the
[AHA PREVENT online calculator](https://professional.heart.org/en/guidelines-and-statements/prevent-calculator).

> **Clinical disclaimer.** This software is provided for research, education,
> and internal analytics only. It is **not** a medical device, is **not**
> FDA-cleared, and must not be used as the sole basis for clinical decision
> making. For point-of-care use, refer patients to the official AHA PREVENT
> calculator.

---

## Table of contents

1. [Background](#background)
2. [Installation](#installation)
3. [Quick start](#quick-start)
4. [Input schema](#input-schema)
5. [How the score is computed](#how-the-score-is-computed)
6. [Basic vs. Full model](#basic-vs-full-model)
7. [Output columns](#output-columns)
8. [Public API](#public-api)
9. [Internal helpers](#internal-helpers)
10. [Validation rules and missing-data behavior](#validation-rules-and-missing-data-behavior)
11. [Differences from the official calculator](#differences-from-the-official-calculator)
12. [Project layout](#project-layout)
13. [License](#license)
14. [Citations](#citations)

---

## Background

The AHA PREVENT equations were published in 2023 as a Scientific Statement and
externally validated in 2024. They were developed to replace the 2013
Pooled Cohort Equations (PCE) and offer several improvements:

- **Race-free** — race/ethnicity is not used as an input.
- **Sex-specific** equations for adults aged **30–79**.
- Predict **10-year and 30-year** absolute risk for total CVD, ASCVD subtypes,
  and heart failure (this implementation covers the **10-year** horizon).
- Adjust for the **competing risk of non-CVD death**.
- Incorporate **cardiovascular–kidney–metabolic (CKM)** health by including
  estimated glomerular filtration rate (eGFR) in the base model, with
  optional extensions for urine albumin-to-creatinine ratio (UACR), HbA1c,
  and a Social Deprivation Index (SDI).

Derivation used 25 datasets (N = 3,281,919) with external validation in
21 additional datasets (N = 3,330,085); total study population was
6,612,004 US adults with 211,515 incident CVD events. External C-statistics
were 0.794 (women) and 0.757 (men).<sup>[1,2]</sup>

---

## Installation

`pyprevent` is a single Python module with two runtime dependencies:

```bash
pip install numpy pandas
```

Then either:

```bash
# Option A: clone and import locally
git clone https://github.com/kingrc15/pyprevent.git
cd pyprevent
python -c "from prevent import compute_prevent10; print('ok')"
```

or copy `prevent.py` into your project.

Supported Python versions: **3.9+** (uses `from __future__ import annotations`).

---

## Quick start

```python
import pandas as pd
from prevent import compute_prevent10

df = pd.DataFrame([
    {
        "PAT_ID": "P001",
        "AGE": 55, "SEX": "F",
        "TCHOL": 200, "HDL": 50,
        "SBP": 130, "BMI": 28.4,
        "EGFR": 85,
        "T2DM": 0,
        "SMOKING_CURR": 0, "RECENT_SMOKING": 0,
        "UACR": 12.0, "HBA1C": 5.6,
        "ADI": None, "SVI": None, "ZIP": "75201",
    }
])

scored = compute_prevent10(
    df,
    bp_treat_default=0,   # no antihypertensive treatment
    statin_default=0,     # not on a statin
    smoking_preference="SMOKING_CURR",
    sdi_series=None,      # SDI unknown -> uses missing-SDI fallback coefficients
)

scored[[
    "PAT_ID",
    "PREVENT10_CVD_BASIC_PCT",
    "PREVENT10_ASCVD_BASIC_PCT",
    "PREVENT10_HF_BASIC_PCT",
    "PREVENT10_CVD_FULL_PCT",
    "PREVENT10_ASCVD_FULL_PCT",
    "PREVENT10_HF_FULL_PCT",
]]
```

---

## Input schema

`compute_prevent10` requires a `pandas.DataFrame` containing **exactly** the
columns listed in `REQUIRED_COLUMNS`:

| Column            | Type      | Units                | Accepted values / coercion                                                              | Used by equations? |
| ----------------- | --------- | -------------------- | --------------------------------------------------------------------------------------- | ------------------ |
| `PAT_ID`          | any       | —                    | passthrough identifier                                                                  | no                 |
| `AGE`             | numeric   | years                | clipped to **[30, 79]**                                                                 | yes                |
| `SEX`             | str/int   | —                    | `"M"`, `"male"`, `0` → male; `"F"`, `"female"`, `1` → female                            | yes                |
| `TCHOL`           | numeric   | mg/dL                | clipped to **[130, 320]**                                                               | yes (CVD/ASCVD)    |
| `HDL`             | numeric   | mg/dL                | clipped to **[20, 100]**                                                                | yes (CVD/ASCVD)    |
| `SBP`             | numeric   | mmHg                 | clipped to **[90, 200]**                                                                | yes                |
| `BMI`             | numeric   | kg/m²                | clipped to **[18.5, 39.9]**                                                             | yes (HF)           |
| `EGFR`            | numeric   | mL/min/1.73 m²       | clipped to **[15, 140]**                                                                | yes                |
| `T2DM`            | 0/1       | —                    | type-2 diabetes status                                                                  | yes                |
| `RECENT_SMOKING`  | 0/1       | —                    | recent (e.g., within X months) tobacco use                                              | optional (smoking) |
| `SMOKING_CURR`    | 0/1       | —                    | current smoker                                                                          | optional (smoking) |
| `UACR`            | numeric   | mg/g                 | clipped to **[0, 25000]**; values < 0.1 floored to 0.1 inside `log()`                   | Full model         |
| `HBA1C`           | numeric   | %                    | clipped to **[3, 15]**                                                                  | Full model         |
| `ADI`             | numeric   | percentile           | Area Deprivation Index — **stored for reference, not used in equations**                | no                 |
| `SVI`             | numeric   | 0–1                  | Social Vulnerability Index — **stored for reference, not used in equations**            | no                 |
| `ZIP`             | str/int   | —                    | truncated to first 5 characters — **stored for reference, not used in equations**       | no                 |

Two additional model inputs are supplied **outside** the DataFrame:

| Argument            | Type / values     | Meaning                                                              |
| ------------------- | ----------------- | -------------------------------------------------------------------- |
| `bp_treat_default`  | `0`, `1`, or `None` | Whether the patient is on antihypertensive treatment.              |
| `statin_default`    | `0`, `1`, or `None` | Whether the patient is on a statin.                                |
| `sdi_series`        | `pandas.Series` or `None` | Optional **Social Deprivation Index** decile (1–10) per row. |

When `bp_treat_default` or `statin_default` is `None`, the affected risk
columns (anything requiring statin or BP-treatment status) are set to `NaN`.

### Sex encoding

The PREVENT R source uses **0 = male, 1 = female**. `_normalize_sex` accepts
`"M"/"male"/0` for male and `"F"/"female"/1` for female. Anything else
becomes `NaN` and that row's outputs become `NaN`.

> Note: This is the **opposite** convention from many older risk calculators
> (e.g., the 2013 Pooled Cohort Equations). Double-check your data feed.

### Smoking column

PREVENT requires a single binary smoking indicator. Choose between
`"SMOKING_CURR"` (default) or `"RECENT_SMOKING"` via `smoking_preference`.

### SDI handling

The Social Deprivation Index is **not** read from `ADI`, `SVI`, or `ZIP`.
Pass it explicitly through `sdi_series` aligned to the rows of `df`. Internally
the raw 1–10 score is bucketed by `_sdicat` into a 3-level category:

| Raw SDI       | Category |
| ------------- | -------- |
| `0 < sdi < 4` | 0 (low)  |
| `4 ≤ sdi < 7` | 1 (mid)  |
| `7 ≤ sdi ≤10` | 2 (high) |

If `sdi_series` is `None` (or the value is `NaN`), the Full model substitutes
the published missing-SDI offsets — i.e., the exact "no-SDI" path used by the
AHA `AHAprevent` R source.

---

## How the score is computed

For every row:

1. **`_clip_inputs`** normalizes types, coerces sex/binary fields, and clips
   each numeric input to the valid PREVENT input range.
2. **`_validate_common_inputs`** ensures `AGE`, `SEX`, `SBP`, `T2DM`,
   smoking, and `EGFR` are all present and in-range. If not, that row's
   scores become `NaN`.
3. The selected smoking flag, `bptreat`, `statin`, and `sdi` are bound.
4. **`_prevent_10yr_base`** computes the log-odds for the **Basic** equations:
   CVD, ASCVD, and HF (HF requires BMI and BP-treatment status; CVD/ASCVD
   require TC, HDL, statin, and BP-treatment status).
5. **`_prevent_10yr_full`** computes the log-odds for the **Full** equations,
   adding terms for SDI, `log(UACR)`, and HbA1c (HbA1c is interacted with
   diabetes status: separate slope when `T2DM == 1` vs `T2DM == 0`).
6. Each log-odds value is converted to a percentage via the logistic link:

   \[ p\,(\%) = \frac{100}{1 + e^{-x}} \]

All numeric coefficients (including SDI fallback offsets and missing-UACR/
HbA1c offsets) are taken verbatim from the AHA `AHAprevent` R source.

### Cholesterol unit conversion

US labs typically report cholesterol in mg/dL; the PREVENT equations are
fitted in mmol/L. Both `_mmol_conversion(x) = 0.02586 * x` and term-by-term
subtraction (e.g., `_mmol_conversion(TC) - _mmol_conversion(HDL)`) are used
exactly as in the upstream source.

### Piecewise SBP and eGFR

PREVENT uses piecewise-linear terms in SBP and eGFR:

- `min(SBP, 110)` and `max(SBP, 110)` split SBP into "below 110" and
  "above 110" branches (centered at 110 and 130 respectively).
- `min(EGFR, 60)` and `max(EGFR, 60)` split eGFR similarly (centered at 60
  and 90 respectively).
- For BMI in the HF equation, `min(BMI, 30)` and `max(BMI, 30)` split BMI
  (centered at 25 and 30 respectively).

These piecewise splits and centering constants are part of the published
equation form.

---

## Basic vs. Full model

| Predictor                   | Basic | Full |
| --------------------------- | :---: | :--: |
| Age                         |   ✓   |  ✓   |
| Sex (separate equations)    |   ✓   |  ✓   |
| Total cholesterol           |   ✓   |  ✓   |
| HDL cholesterol             |   ✓   |  ✓   |
| Systolic BP (piecewise)     |   ✓   |  ✓   |
| BMI (HF model only)         |   ✓   |  ✓   |
| eGFR (piecewise)            |   ✓   |  ✓   |
| Diabetes (T2DM)             |   ✓   |  ✓   |
| Smoking                     |   ✓   |  ✓   |
| On antihypertensive therapy |   ✓   |  ✓   |
| On statin (CVD/ASCVD only)  |   ✓   |  ✓   |
| **UACR (log, adjusted)**    |       |  ✓   |
| **HbA1c × diabetes**        |       |  ✓   |
| **Social Deprivation Index**|       |  ✓   |

The Full model adds three optional predictors. The published equations
include an explicit "missing" coefficient for each of UACR, HbA1c, and SDI;
`_prevent_10yr_full` uses these fallback offsets whenever the corresponding
input is `NaN`, matching the AHA R source exactly.

---

## Output columns

`compute_prevent10` appends the following columns to a copy of the input
DataFrame (all values are 10-year predicted probabilities expressed as a
percent, 0–100):

| Column                       | Meaning                                       |
| ---------------------------- | --------------------------------------------- |
| `PREVENT10_CVD_BASIC_PCT`    | Total CVD, Basic model                        |
| `PREVENT10_ASCVD_BASIC_PCT`  | Atherosclerotic CVD, Basic model              |
| `PREVENT10_HF_BASIC_PCT`     | Heart failure, Basic model                    |
| `PREVENT10_CVD_FULL_PCT`     | Total CVD, Full model (with UACR/HbA1c/SDI)   |
| `PREVENT10_ASCVD_FULL_PCT`   | Atherosclerotic CVD, Full model               |
| `PREVENT10_HF_FULL_PCT`      | Heart failure, Full model                     |

Any row whose required inputs fail validation receives `NaN` for the
affected outputs.

---

## Public API

### `compute_prevent10(df, bp_treat_default=0, statin_default=0, smoking_preference="SMOKING_CURR", sdi_series=None) -> pandas.DataFrame`

Score an entire DataFrame.

- **`df`** — must contain every column in `REQUIRED_COLUMNS`. A `ValueError`
  is raised if any are missing.
- **`bp_treat_default`** — `0`, `1`, or `None`. Default antihypertensive
  treatment status applied to every row. Set to `None` to force any
  BP-treatment-dependent output to `NaN`.
- **`statin_default`** — `0`, `1`, or `None`. Default statin status applied to
  every row. Set to `None` to force CVD/ASCVD outputs to `NaN`.
- **`smoking_preference`** — `"SMOKING_CURR"` (default) or `"RECENT_SMOKING"`.
  Selects which column drives the smoking term.
- **`sdi_series`** — optional `pandas.Series` of raw SDI deciles (1–10),
  aligned by integer position to the rows of `df`. When `None` or `NaN`,
  the Full model uses the published missing-SDI offsets.

Returns a **copy** of `df` with the six `PREVENT10_*` columns appended.

### `REQUIRED_COLUMNS`

The canonical list of column names required by `compute_prevent10`:

```python
[
    "PAT_ID", "AGE", "SEX", "TCHOL", "HDL", "SBP", "BMI", "EGFR",
    "T2DM", "RECENT_SMOKING", "SMOKING_CURR", "UACR", "HBA1C",
    "ADI", "SVI", "ZIP",
]
```

---

## Internal helpers

These functions are not part of the supported API but are documented for
auditability of the port from the AHA R source.

| Function                                   | Purpose                                                                                                                                  |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `_mmol_conversion(x)`                      | Converts cholesterol from mg/dL to mmol/L (`0.02586 * x`).                                                                               |
| `_adjust_uacr(uacr)` / `adjust(uacr)`      | Floors `UACR` at 0.1 mg/g (to avoid `log(0)`); returns `NaN`/`None` for missing inputs. `adjust` is the version invoked inside the Full equations, mirroring the R source. |
| `_sdicat(sdi)`                             | Buckets raw SDI 1–10 into the 0/1/2 category used by PREVENT.                                                                            |
| `_sigmoid_pct(x)`                          | Logistic link, scaled to percent: `100 / (1 + exp(-x))`.                                                                                  |
| `_to_float(x)`                             | Safe float coercion that returns `NaN` for unparseable/`NA` values.                                                                       |
| `_to_binary01(x)`                          | Coerces a value to `0.0` or `1.0`; everything else becomes `NaN`.                                                                         |
| `_normalize_sex(x)`                        | Accepts `"M"/"male"/0` → 0.0 (male) and `"F"/"female"/1` → 1.0 (female).                                                                  |
| `_clip_inputs(row)`                        | Type-coerces and clips each row's inputs to PREVENT's valid ranges.                                                                       |
| `_validate_common_inputs(...)`             | Sanity check on the always-required inputs (age, sex, SBP, T2DM, smoking, eGFR).                                                          |
| `_prevent_10yr_base(...)`                  | Sex-specific Basic equations for CVD, ASCVD, and HF (10-year horizon).                                                                    |
| `_prevent_10yr_full(...)`                  | Sex-specific Full equations adding UACR/HbA1c/SDI (10-year horizon).                                                                      |

---

## Validation rules and missing-data behavior

The implementation follows the AHA source's split between hard validation
and graceful degradation:

- **Hard validation (`_validate_common_inputs`).** If `AGE`, `SEX`, `SBP`,
  `T2DM`, smoking flag, or `EGFR` is missing or out of range, **all three**
  outputs (CVD, ASCVD, HF) become `NaN` for that row in both the Basic and
  Full models.
- **CVD/ASCVD gating.** If `TCHOL`, `HDL`, `statin`, or `bptreat` is missing
  or out of range, the CVD and ASCVD outputs become `NaN`; the HF output is
  unaffected.
- **HF gating.** If `BMI` or `bptreat` is missing or out of range
  (`BMI < 18.5` or `BMI ≥ 40`), the HF output becomes `NaN`; CVD and ASCVD
  are unaffected.
- **Full-model extras.** Missing `UACR`, `HbA1c`, or `SDI` does **not**
  produce `NaN`; instead, the published missing-input offsets are added,
  matching the R source.

---

## Differences from the official calculator

This module differs from the public AHA PREVENT online calculator in a few
deliberate ways. Keep these in mind when comparing outputs:

1. **10-year only.** Only the 10-year horizon is implemented here. The
   30-year PREVENT equations are not yet ported.
2. **Input clipping.** Out-of-range inputs are silently clipped to the
   valid PREVENT range (e.g., `SBP = 250` becomes `200`). The web
   calculator typically rejects out-of-range values.
3. **BP-treatment and statin status** are not part of the row schema. They
   are supplied per-call via `bp_treat_default` / `statin_default`. For
   patient-level fidelity, score each cohort sub-group (treated vs.
   untreated) separately, or extend the call site to pass row-level values.
4. **SDI** must be passed explicitly via `sdi_series`. The `ADI`, `SVI`, and
   `ZIP` columns in the input schema are carried through but are **not**
   used by the equations.

---

## Project layout

```
pyprevent/
├── prevent.py     # The PREVENT 10-year implementation (single module)
└── README.md
```

---

## License

This repository does not yet ship a `LICENSE` file. Add one before public
release. The original AHA PREVENT equations are publicly available; the
official `AHAprevent` R source is distributed under its own license — check
the upstream repository before redistributing derivative code.

---

## Citations

1. **Khan SS, Matsushita K, Sang Y, et al.** Development and Validation of
   the American Heart Association Predicting Risk of Cardiovascular Disease
   EVENTs (PREVENT) Equations. *Circulation*. 2024;149(6):430–449.
   doi:[10.1161/CIRCULATIONAHA.123.067626](https://doi.org/10.1161/CIRCULATIONAHA.123.067626).
   PMID:&nbsp;[37947085](https://pubmed.ncbi.nlm.nih.gov/37947085/).
   PMCID:&nbsp;[PMC10910659](https://pmc.ncbi.nlm.nih.gov/articles/PMC10910659/).

2. **Khan SS, Coresh J, Pencina MJ, et al.; on behalf of the American Heart
   Association.** Novel Prediction Equations for Absolute Risk Assessment of
   Total Cardiovascular Disease Incorporating Cardiovascular-Kidney-Metabolic
   Health: A Scientific Statement From the American Heart Association.
   *Circulation*. 2023;148(24):1982–2004.
   doi:[10.1161/CIR.0000000000001191](https://doi.org/10.1161/CIR.0000000000001191).
   PMID:&nbsp;[37947094](https://pubmed.ncbi.nlm.nih.gov/37947094/).

3. **Ndumele CE, Rangaswami J, Chow SL, et al.; on behalf of the American
   Heart Association.** Cardiovascular-Kidney-Metabolic Health: A
   Presidential Advisory From the American Heart Association. *Circulation*.
   2023;148(20):1606–1635.
   doi:[10.1161/CIR.0000000000001184](https://doi.org/10.1161/CIR.0000000000001184).

4. **American Heart Association.** PREVENT™ Online Risk Calculator.
   Professional Heart Daily.
   <https://professional.heart.org/en/guidelines-and-statements/prevent-calculator>
   (accessed May 2026).

5. **American Heart Association.** `AHAprevent` R package (reference
   implementation of the PREVENT equations).
   <https://github.com/AHA-Tools/AHAprevent>.

When using `pyprevent` in publications, please cite references **[1]** and
**[2]** above (the development/validation paper and the scientific
statement) — they are the canonical sources of the equations implemented
here.
