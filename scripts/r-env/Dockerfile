# Optional container image for R golden fixture generation.
# Build from repo root:
#   docker build -f scripts/r-env/Dockerfile -t pyprevent-r .
# Run (mount PREVENT checkout):
#   docker run --rm -v "$PWD:/pyprevent" -v "$PWD/../PREVENT:/PREVENT" pyprevent-r

FROM condaforge/miniforge3:24.11.3-0

WORKDIR /pyprevent

COPY scripts/r-env/environment.yml /tmp/environment.yml
RUN mamba env create -f /tmp/environment.yml && mamba clean -afy

ENV PATH=/opt/conda/envs/pyprevent-r/bin:$PATH
ENV PREVENT_R_PKG=/PREVENT/R/AHAprevent

COPY scripts/generate_r_reference.R scripts/generate_r_reference.R
COPY tests/fixtures/r_cases.csv tests/fixtures/r_cases.csv

# AHAprevent is mounted at runtime from the host PREVENT repo.
RUN test -d "$PREVENT_R_PKG" || echo "Mount ../PREVENT at /PREVENT when running the container."

CMD ["Rscript", "scripts/generate_r_reference.R"]
