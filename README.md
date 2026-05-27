# PyPrevent

[![tests](https://github.com/kingrc15/pyprevent/actions/workflows/test.yml/badge.svg)](https://github.com/kingrc15/pyprevent/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)

A pure-Python, pandas-friendly implementation of the **American Heart
Association (AHA) PREVENT™ (Predicting Risk of CVD EVENTs)** equations.

The `prevent` package scores patient cohorts from a `pandas.DataFrame` and
returns predicted **10-year and 30-year** absolute risk (percent) for:

- **Total CVD**, **ASCVD**, and **heart failure (HF)**

under five published model variants (**Base**, **UACR**, **HbA1c**, **SDI**,
**Full**). The convenience wrapper `compute_prevent10` returns the legacy six
Basic + Full 10-year columns only.

Scoring is row-oriented (one patient per row); optional per-row `BPTREAT` and
`STATIN` columns override call-level defaults when present.

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
  and heart failure (both horizons are implemented in `compute_prevent`).
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

```bash
git clone https://github.com/kingrc15/pyprevent.git
cd pyprevent
pip install .          # or: pip install -e .[dev]   for development
```

For development (running the test suite):

```bash
pip install -e ".[dev]"
pytest
```

Or, if you just want the dependencies without installing the package:

```bash
pip install -r requirements.txt
```

Supported Python versions: **3.9+** (the module uses
`from __future__ import annotations`). Runtime dependencies are `numpy` and
`pandas`; the test suite additionally requires `pytest`.

---

## Quick start

```python
import pandas as pd
from prevent import compute_prevent, compute_prevent10

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
        "ZIP": "75201",
    }
])

scored = compute_prevent10(
    df,
    bp_treat_default=0,   # no antihypertensive treatment
    statin_default=0,     # not on a statin
    smoking_preference="SMOKING_CURR",
    sdi_series=None,      # omit to use ZIP → bundled RGC ZCTA crosswalk
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

`compute_prevent` and `compute_prevent10` require a `pandas.DataFrame` with at
least the columns in `REQUIRED_COLUMNS` (extra columns are ignored):

| Column            | Type      | Units                | Accepted values / coercion                                                              | Used by equations? |
| ----------------- | --------- | -------------------- | --------------------------------------------------------------------------------------- | ------------------ |
| `PAT_ID`          | any       | —                    | passthrough identifier                                                                  | no                 |
| `AGE`             | numeric   | years                | must be in **[30, 79]**                                                                 | yes                |
| `SEX`             | str/int   | —                    | `"M"`, `"male"`, `0` → male; `"F"`, `"female"`, `1` → female                            | yes                |
| `TCHOL`           | numeric   | mg/dL                | must be in **[130, 320]**                                                               | yes (CVD/ASCVD)    |
| `HDL`             | numeric   | mg/dL                | must be in **[20, 100]**                                                                | yes (CVD/ASCVD)    |
| `SBP`             | numeric   | mmHg                 | must be in **[90, 200]**                                                                | yes                |
| `BMI`             | numeric   | kg/m²                | must be in **[18.5, 39.9]**                                                             | yes (HF)           |
| `EGFR`            | numeric   | mL/min/1.73 m²       | must be **> 0**                                                                         | yes                |
| `T2DM`            | 0/1       | —                    | type-2 diabetes status                                                                  | yes                |
| `RECENT_SMOKING`  | 0/1       | —                    | recent (e.g., within X months) tobacco use                                              | optional (smoking) |
| `SMOKING_CURR`    | 0/1       | —                    | current smoker                                                                          | optional (smoking) |
| `UACR`            | numeric   | mg/g                 | must be **≥ 0**; values < 0.1 floored to 0.1 inside `log()`                              | UACR/Full models   |
| `HBA1C`           | numeric   | %                    | must be **> 0**                                                                          | HbA1c/Full models  |
| `ZIP`             | str/int   | 5-digit ZCTA         | SDI lookup when `sdi_series` is omitted (first five digits, zero-padded)               | SDI/Full models    |
| `BPTREAT`         | 0/1       | —                    | optional; per-row antihypertensive treatment (overrides `bp_treat_default`)             | yes                |
| `STATIN`          | 0/1       | —                    | optional; per-row statin use (overrides `statin_default`)                               | yes (CVD/ASCVD)    |

Call-level arguments (used when `BPTREAT` / `STATIN` columns are absent):

| Argument            | Type / values     | Meaning                                                              |
| ------------------- | ----------------- | -------------------------------------------------------------------- |
| `bp_treat_default`  | `0`, `1`, or `None` | Default antihypertensive treatment for all rows.                     |
| `statin_default`    | `0`, `1`, or `None` | Default statin status for all rows.                                |
| `sdi_series`        | `pandas.Series` or `None` | Optional SDI decile (1–10) per row; overrides ZIP lookup when set. |

When treatment values are `None` or `NaN`, outputs that require them are `NaN`.

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

SDI enters the **SDI** and **Full** models only. Resolution order:

1. **`sdi_series`** — optional per-row PREVENT decile (integer 1–10), aligned to
   `df.index` (or same length in row order).
2. **`ZIP`** — when `sdi_series` is omitted, the first five digits of `ZIP` are
   matched to the bundled [Robert Graham Center](https://www.graham-center.org/rgc/maps-data-tools/sdi/social-deprivation-index.html)
   ZCTA file (`prevent/data/rgc_sdi_zcta2015_2019.csv`). The file’s `SDI_score`
   (percentile 1–100) is converted to a decile using the AHA crosswalk
   (1–10 → 1, 11–20 → 2, …, 91–100 → 10).
3. **Missing** — unknown or absent ZIP → published missing-SDI coefficients (same
   as `sdi = NA` in `AHAprevent`).

Internally, deciles 1–10 are bucketed by
`_sdicat` into tertiles 0/1/2 for the equations:

| Decile        | Category |
| ------------- | -------- |
| `0 < sdi < 4` | 0 (low)  |
| `4 ≤ sdi < 7` | 1 (mid)  |
| `7 ≤ sdi ≤10` | 2 (high) |

---

## How the score is computed

For every row:

1. **Input coercion** (`coerce_dataframe`) normalizes types column-wise, then each
   row is scored through the sex-specific equations (batch SDI lookup from `ZIP`).
2. **`_validate_common_inputs`** ensures `AGE`, `SEX`, `SBP`, `T2DM`,
   smoking, and `EGFR` are all present and in-range. If not, that row's
   scores become `NaN`.
3. Smoking, `bptreat`, `statin` (from `BPTREAT`/`STATIN` columns or call
   defaults), and `sdi` (from `sdi_series`, `ZIP` lookup, or missing) are bound.
4. Each `prevent_*` module evaluates the sex-specific **10-year and 30-year**
   log-odds for CVD, ASCVD, and HF (Base, UACR, HbA1c, SDI, Full).
5. Age rules mask 30-year outputs for ages 60–79 and all outputs outside 30–79.
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
`prevent_full` uses these fallback offsets whenever the corresponding input is
`NaN`, matching the AHA R source exactly.

---

## Output columns

### `compute_prevent` (30 columns)

`PREVENT{10|30}_{CVD|ASCVD|HF}_{BASE|UACR|HBA1C|SDI|FULL}_PCT` — see
`prevent.PREVENT_OUTPUT_COLUMNS` for the full list.

### `compute_prevent10` (6 columns)

Appends these 10-year columns (percent, 0–100) to a copy of the input DataFrame:

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

### `compute_prevent(df, ...) -> pandas.DataFrame`

Score all models and horizons. Same arguments as `compute_prevent10`; returns
input columns plus 30 `PREVENT*` risk columns.

### `compute_prevent10(df, bp_treat_default=0, statin_default=0, smoking_preference="SMOKING_CURR", sdi_series=None) -> pandas.DataFrame`

Score the legacy six 10-year Basic + Full columns.

- **`df`** — must contain every column in `REQUIRED_COLUMNS`. A `ValueError`
  is raised if any are missing.
- **`bp_treat_default`** — `0`, `1`, or `None`. Default antihypertensive
  treatment status applied to every row. Set to `None` to force any
  BP-treatment-dependent output to `NaN`.
- **`statin_default`** — `0`, `1`, or `None`. Default statin status applied to
  every row. Set to `None` to force CVD/ASCVD outputs to `NaN`.
- **`smoking_preference`** — `"SMOKING_CURR"` (default) or `"RECENT_SMOKING"`.
  Selects which column drives the smoking term.
- **`sdi_series`** — optional `pandas.Series` of SDI deciles (1–10), aligned
  by position to `df`. When omitted, SDI is looked up from `ZIP`; when a row
  is `NaN` in `sdi_series` or ZIP is unknown, missing-SDI coefficients apply.

Returns a **copy** of `df` with the six `PREVENT10_*` columns appended.

### `REQUIRED_COLUMNS`

The canonical list of column names required by `compute_prevent10`:

```python
[
    "PAT_ID", "AGE", "SEX", "TCHOL", "HDL", "SBP", "BMI", "EGFR",
    "T2DM", "RECENT_SMOKING", "SMOKING_CURR", "UACR", "HBA1C", "ZIP",
]
```

Optional per-row treatment columns: `BPTREAT`, `STATIN` (see `prevent.OPTIONAL_COLUMNS`).

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
| `coerce_inputs(row)`                       | Type-coerces each row's inputs (no range clipping).                                                                                      |
| `_validate_common_inputs(...)`             | Sanity check on the always-required inputs (age, sex, SBP, T2DM, smoking, eGFR).                                                          |
| `prevent_*` functions                      | Sex-specific PREVENT equations for Basic, UACR, HbA1c, SDI, and Full models (10-year and 30-year horizons).                              |

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

1. **R-parity behavior.** This implementation follows the upstream `AHAprevent`
   R package: out-of-range inputs are rejected (produce `NaN`) rather than
   silently clipped.
2. **Treatment flags.** Use optional `BPTREAT` / `STATIN` columns for per-row
   values, or `bp_treat_default` / `statin_default` when those columns are absent.
3. **SDI** is resolved from `sdi_series` when provided, otherwise from `ZIP`
   via the bundled RGC ZCTA crosswalk.

---

## Testing

The repository ships with a `pytest` suite under `tests/`. It includes:

- **Numerical-parity checks** against worked examples from the upstream AHA
  PREVENT reference (Table S25 of Khan et al. 2024 plus the published
  supplemental Excel file, mirrored in the [`preventr`](https://github.com/martingmayer/preventr)
  R package's `estimate_risk()` documentation). The tests assert agreement to
  within **0.1 percentage points** of the published three-decimal reference
  values for the female base model (age 50) and the male base model (age 66),
  and against the Full model for a worked example with HbA1c and UACR.
- **Structural / contract tests** covering `REQUIRED_COLUMNS` validation,
  output column presence, immutability of the input DataFrame, the
  out-of-range rejection behavior, the `bp_treat_default=None` /
  `statin_default=None` NaN behavior, the smoking-column preference toggle,
  ZIP truncation, multi-row scoring, and the helper functions
  (`_normalize_sex`, `_to_binary01`, `_sdicat`, `_sigmoid_pct`).

Run them with:

```bash
pip install -e ".[dev]"
pytest
python scripts/audit_coefficients.py  # skips if R source not found locally
```

Set `PREVENT_R_SOURCE` to point at `AHA_prevent_equations.R` when the audit
cannot find `../PREVENT/R/AHAprevent/R/` relative to the repo.

To refresh fixtures from **AHAprevent** (recommended), use the conda R env:

```bash
bash scripts/r-env/setup.sh                      # once: creates env pyprevent-r
bash scripts/r-env/run_generate_reference.sh   # writes tests/fixtures/r_reference.csv
```

See [`scripts/r-env/README.md`](scripts/r-env/README.md) for `PREVENT_R_PKG`, Docker, and troubleshooting.

Fallback without R (locks current Python output):

```bash
python scripts/fill_r_reference.py
```

The `r-reference` GitHub Actions workflow can regenerate the CSV via
`workflow_dispatch` when a sibling `PREVENT` checkout is available.

> Note: the Full equation here is the AHA-source full-only form with
> published missing-input offsets — it is **not** equivalent to the
> intermediate "+HbA1c-only" / "+UACR-only" / "+SDI-only" models that the
> `preventr` R package fits as distinct equations. Numerical parity is
> verified against the **Base** model and the **Full** model with optional
> inputs; intermediate variants are out of scope.

---

## Project layout

```
pyprevent/
├── prevent/                         # Package implementation
│   ├── __init__.py                  # compute_prevent, compute_prevent10
│   ├── _base.py … _full.py          # Model equations (10yr + 30yr)
│   ├── _zip_sdi.py                  # ZIP → SDI decile lookup
│   └── data/
│       ├── rgc_sdi_zcta2015_2019.csv
│       └── DATA_SOURCES.md
├── tests/
│   ├── test_prevent.py              # Parity + contract tests
│   ├── test_prevent30.py            # Age / horizon masks
│   ├── test_r_parity.py             # Fixture-based R comparison
│   └── test_package.py              # Bundled data + output schema
├── scripts/
│   ├── audit_coefficients.py
│   ├── fill_r_reference.py          # Python regression fixture (CI default)
│   └── generate_r_reference.R       # Upstream AHAprevent golden (needs R)
├── .github/workflows/test.yml
├── pyproject.toml
└── README.md
```

## Continuous integration

`.github/workflows/test.yml` runs the `pytest` suite on every push and pull
request to `main` / `master`, plus manual `workflow_dispatch`. The matrix
covers:

- **Linux**: Python 3.9, 3.10, 3.11, 3.12, 3.13.
- **macOS** and **Windows**: smoke run on Python 3.12.

## Release history

See [`CHANGELOG.md`](CHANGELOG.md) for the full release history. The current
version is **0.2.0**.

---

## License

This project is released under the **MIT License**. See [`LICENSE`](LICENSE)
for full text, including the medical-advice disclaimer appended to the
license.

The original AHA PREVENT equations are publicly available; the official
`AHAprevent` R source is distributed under its own license — check the
upstream repository before redistributing derivative code.

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
