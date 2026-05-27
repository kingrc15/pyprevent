# R test environment (`pyprevent-r`)

Regenerates `tests/fixtures/r_reference.csv` from the upstream **AHAprevent** R
package (not the Python `fill_r_reference.py` shortcut).

## Prerequisites

- [Conda](https://docs.conda.io/) or [Mamba](https://mamba.readthedocs.io/)
- Local clone of PREVENT with R sources, default path:

  ```
  ../PREVENT/R/AHAprevent   # sibling of this repo
  ```

  Override with `PREVENT_R_PKG` if your layout differs.

## One-time setup

From the **pyprevent** repository root:

```bash
bash scripts/r-env/setup.sh
```

This creates conda env `pyprevent-r` (override with `PYPREVENT_R_ENV`) and runs
`R CMD INSTALL` on AHAprevent.

## Generate golden CSV

```bash
bash scripts/r-env/run_generate_reference.sh
git diff tests/fixtures/r_reference.csv
python -m pytest tests/test_r_parity.py -q
```

## Docker (optional)

From repo root, with `../PREVENT` checked out:

```bash
docker build -f scripts/r-env/Dockerfile -t pyprevent-r .
docker run --rm \
  -v "$(pwd):/pyprevent" \
  -v "$(pwd)/../PREVENT:/PREVENT" \
  -w /pyprevent \
  pyprevent-r \
  bash -lc 'R CMD INSTALL /PREVENT/R/AHAprevent && Rscript scripts/generate_r_reference.R'
```

## Troubleshooting

| Problem | Fix |
| -------- | ----- |
| `AHAprevent source not found` | Set `export PREVENT_R_PKG=/path/to/AHAprevent` |
| `conda env not found` | Run `bash scripts/r-env/setup.sh` |
| R install fails | Ensure `R CMD INSTALL` works on a plain R session first |
