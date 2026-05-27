# Changelog

All notable changes to `pyprevent` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Batch column coercion (`coerce_dataframe`) and indexed scoring loop (no `iterrows`).
- R parity tolerance tightened to `atol=1e-12` against AHAprevent-generated fixtures.
- `generate_r_reference.R` skips reinstall when `PREVENT_SKIP_R_INSTALL=1`.

### Added

- Fixture cases `age_20_all_na` and `age_75_30yr_masked` in `r_cases.csv`.
- Shared `tests/factories.make_prevent_row` for test data construction.

## [0.2.0] - 2026-05-27

### Added

- `compute_prevent()` — all five PREVENT models × 10- and 30-year horizons (30 output columns).
- Optional per-row `BPTREAT` and `STATIN` columns; `prevent.OPTIONAL_COLUMNS`.
- ZIP → SDI decile lookup via bundled RGC ZCTA crosswalk (`prevent/data/rgc_sdi_zcta2015_2019.csv`).
- `scripts/fill_r_reference.py` and expanded `tests/fixtures/r_reference.csv` (full 30-column regression fixture).
- `scripts/audit_coefficients.py` (sentinel check vs R source; skips when R absent).
- GitHub Actions workflow `r-reference.yml` to regenerate fixtures from `AHAprevent` via `workflow_dispatch`.

### Changed

- **Breaking:** removed unused `ADI` and `SVI` from `REQUIRED_COLUMNS`.
- **Breaking:** monolithic `prevent.py` replaced by the `prevent/` package.
- `compute_prevent10()` scores only Base + Full models (no longer runs UACR/HbA1c/SDI-only equations).
- `sdi_series` aligns to `df.index` when possible; batch ZIP→SDI lookup before the row loop.
- Out-of-range inputs produce `NaN` (R parity) instead of silent clipping.

### Fixed

- Female `prevent_full` 30-year CVD/ASCVD were incorrectly nested under `can_hf` (missing BMI no longer suppresses them).

### Added

- Conda R environment under `scripts/r-env/` for running `generate_r_reference.R`.

### Known limitations

- Equation evaluation remains per-row Python (inputs are batch-coerced; log-odds are not column-vectorized).
- Regenerate `r_reference.csv` with `bash scripts/r-env/run_generate_reference.sh` when AHAprevent is available.

## [0.1.0] - 2026-05-12

Initial public release.

### Added

- **`prevent.py`** — single-module implementation of the AHA PREVENT 10-year
  cardiovascular risk equations, translated from the AHA `AHAprevent` R
  source.
  - `compute_prevent10(df, ...)` — vectorized scorer that consumes a
    `pandas.DataFrame` with the `REQUIRED_COLUMNS` schema and returns the
    same frame with six new columns:
    `PREVENT10_{CVD,ASCVD,HF}_{BASIC,FULL}_PCT`.
  - Sex-specific Basic and Full coefficient sets for total CVD, ASCVD, and
    heart failure.
  - Published missing-input offsets for UACR, HbA1c, and SDI in the Full
    equation, matching the upstream R behavior.
  - Helpers: `_mmol_conversion`, `_sdicat`, `_sigmoid_pct`, `_to_float`,
    `_to_binary01`, `_normalize_sex`, `_clip_inputs`,
    `_validate_common_inputs`, `_prevent_10yr_base`, `_prevent_10yr_full`,
    `adjust` (UACR floor for `log()` term).
- **`tests/test_prevent.py`** — 54 pytest cases covering:
  - Numerical parity (within 0.1 percentage points) against the published
    PREVENT reference values:
    - Khan et al. Table S25 worked example (female, age 50, base model).
    - `preventr` worked examples for the male base model (age 66) and the
      female Full model with HbA1c + UACR + missing SDI.
  - API contract: `REQUIRED_COLUMNS` validation, output column presence,
    input-DataFrame immutability, output value range, missing-input
    handling, `bp_treat_default` / `statin_default = None` behavior,
    smoking-column preference toggle, ZIP truncation, multi-row scoring.
  - Helper-level behavior of `_normalize_sex`, `_to_binary01`, `_sdicat`,
    and `_sigmoid_pct`.
- **`README.md`** — comprehensive documentation: input schema, model
  internals, Basic vs. Full comparison, output columns, public API,
  validation rules, differences from the official AHA calculator,
  citations (Khan 2024, Khan 2023, Ndumele 2023, AHA PREVENT calculator,
  upstream `AHAprevent` R package).
- **`pyproject.toml`** — PEP 621 build metadata, `py-modules = ["prevent"]`,
  `numpy>=1.21` and `pandas>=1.3` runtime deps, `pytest>=7` dev extra,
  `[tool.pytest.ini_options]` configuration.
- **`requirements.txt`** — runtime dependency pins.
- **`LICENSE`** — MIT license with appended medical-advice disclaimer.
- **`.gitignore`** — Python build / venv / test artifacts.
- **`.github/workflows/test.yml`** — GitHub Actions CI running the test
  suite on push, pull request, and manual dispatch across Python 3.9 –
  3.13 on Linux, plus a smoke run on macOS and Windows.

### Removed

- Dead helper `_adjust_uacr` (superseded by `adjust`, which is the version
  actually invoked inside `_prevent_10yr_full`).

### Known limitations

- Scoring loops rows in Python (`iterrows`); not column-vectorized across patients.
- R golden fixtures cover only a small vignette subset (`tests/fixtures/r_reference.csv`).
- Regenerating full R reference output requires `Rscript` and a local `AHAprevent` install.

[Unreleased]: https://github.com/kingrc15/pyprevent/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/kingrc15/pyprevent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/kingrc15/pyprevent/releases/tag/v0.1.0
