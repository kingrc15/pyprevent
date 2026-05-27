#!/usr/bin/env bash
# Create/update the pyprevent-r conda environment and install local AHAprevent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$SCRIPT_DIR/environment.yml"
ENV_NAME="${PYPREVENT_R_ENV:-pyprevent-r}"

PREVENT_R_PKG="${PREVENT_R_PKG:-$REPO_ROOT/../PREVENT/R/AHAprevent}"

if [[ ! -d "$PREVENT_R_PKG" ]]; then
  echo "ERROR: AHAprevent source not found at: $PREVENT_R_PKG" >&2
  echo "Clone PREVENT beside pyprevent or set PREVENT_R_PKG." >&2
  exit 1
fi

if ! command -v conda >/dev/null 2>&1 && ! command -v mamba >/dev/null 2>&1; then
  echo "ERROR: conda or mamba is required (e.g. Miniconda / Mambaforge)." >&2
  exit 1
fi

CONDA="$(command -v mamba || command -v conda)"
echo "Using: $CONDA"

if "$CONDA" env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "Updating existing environment: $ENV_NAME"
  "$CONDA" env update -n "$ENV_NAME" -f "$ENV_FILE" --prune -y
else
  echo "Creating environment: $ENV_NAME"
  "$CONDA" env create -f "$ENV_FILE" -y
fi

echo "Installing AHAprevent from $PREVENT_R_PKG"
"$CONDA" run -n "$ENV_NAME" R CMD INSTALL "$PREVENT_R_PKG"

echo ""
echo "Ready. Run:"
echo "  bash scripts/r-env/run_generate_reference.sh"
