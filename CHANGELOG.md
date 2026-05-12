# Changelog

All notable changes to `pyprevent` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

- Only the **10-year** PREVENT horizon is implemented; the 30-year
  equations are not yet ported.
- The `ADI`, `SVI`, and `ZIP` columns are part of the input schema but are
  passed through unused — the Social Deprivation Index must be supplied
  separately via the `sdi_series` argument.
- The Full equation is the AHA-source "full-only" form (with published
  missing-input offsets); it is not equivalent to the intermediate
  "+HbA1c-only", "+UACR-only", or "+SDI-only" models fit by the `preventr`
  R package as distinct equations.
- Out-of-range numeric inputs are silently clipped to the valid PREVENT
  range rather than rejected.

[Unreleased]: https://github.com/kingrc15/pyprevent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kingrc15/pyprevent/releases/tag/v0.1.0
