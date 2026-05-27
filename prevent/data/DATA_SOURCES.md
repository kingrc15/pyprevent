# Bundled data files

## `rgc_sdi_zcta2015_2019.csv`

Robert Graham Center Social Deprivation Index (SDI) by ZIP Code Tabulation Area (ZCTA),
2015–2019 release.

- Source: [RGC SDI maps & data tools](https://www.graham-center.org/rgc/maps-data-tools/sdi/social-deprivation-index.html)
- Used column: `ZCTA5_FIPS` (5-digit ZCTA), `SDI_score` (percentile 1–100)
- Conversion to PREVENT decile (1–10) follows the AHA `AHAprevent` crosswalk documented in
  the upstream PREVENT package help (percentile bins 1–10 → decile 1, 11–20 → decile 2, …).

This file is redistributed for convenience in clinical-analytics pipelines. Verify
licensing and attribution requirements for your organization before production use.
