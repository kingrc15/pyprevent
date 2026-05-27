#!/usr/bin/env bash
# Regenerate tests/fixtures/r_reference.csv using AHAprevent in the pyprevent-r env.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_NAME="${PYPREVENT_R_ENV:-pyprevent-r}"

PREVENT_R_PKG="${PREVENT_R_PKG:-$REPO_ROOT/../PREVENT/R/AHAprevent}"
export PREVENT_R_PKG

if ! command -v conda >/dev/null 2>&1 && ! command -v mamba >/dev/null 2>&1; then
  echo "ERROR: conda or mamba is required. Run: bash scripts/r-env/setup.sh" >&2
  exit 1
fi

CONDA="$(command -v mamba || command -v conda)"
if ! "$CONDA" env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "ERROR: conda env '$ENV_NAME' not found. Run: bash scripts/r-env/setup.sh" >&2
  exit 1
fi

cd "$REPO_ROOT"
export PREVENT_SKIP_R_INSTALL=1
echo "Generating R reference (PREVENT_R_PKG=$PREVENT_R_PKG)"
"$CONDA" run -n "$ENV_NAME" Rscript scripts/generate_r_reference.R
echo "Done. Review: git diff tests/fixtures/r_reference.csv"
