#!/usr/bin/env Rscript
suppressPackageStartupMessages({
  library(utils)
})

args <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", args[grep("^--file=", args)])
root <- if (length(file_arg)) {
  normalizePath(file.path(dirname(file_arg), ".."))
} else {
  normalizePath(getwd())
}

cases_path <- file.path(root, "tests", "fixtures", "r_cases.csv")
out_path <- file.path(root, "tests", "fixtures", "r_reference.csv")

if (!file.exists(cases_path)) {
  stop(paste("Missing cases file:", cases_path))
}

message("Reading cases from ", cases_path)
cases <- read.csv(cases_path, stringsAsFactors = FALSE, na.strings = c("", "NA"))

default_pkg <- file.path(root, "..", "PREVENT", "R", "AHAprevent")
pkg_path <- Sys.getenv("PREVENT_R_PKG", unset = default_pkg)
skip_install <- identical(Sys.getenv("PREVENT_SKIP_R_INSTALL"), "1")

if (!skip_install) {
  message("Installing AHAprevent from ", pkg_path)
  status <- system(paste("R CMD INSTALL", shQuote(pkg_path)))
  if (status != 0) {
    stop("Failed to install AHAprevent from ", pkg_path)
  }
} else {
  message("Skipping install (PREVENT_SKIP_R_INSTALL=1); loading existing AHAprevent")
}

suppressPackageStartupMessages({
  library(AHAprevent)
})

to_num <- function(x) as.numeric(x)

ref <- data.frame(case_id = cases$case_id, stringsAsFactors = FALSE)

for (i in seq_len(nrow(cases))) {
  row <- cases[i, ]
  sex <- to_num(row$sex)
  age <- to_num(row$age)
  tc <- to_num(row$tc)
  hdl <- to_num(row$hdl)
  sbp <- to_num(row$sbp)
  dm <- to_num(row$dm)
  smoking <- to_num(row$smoking)
  bmi <- to_num(row$bmi)
  egfr <- to_num(row$egfr)
  bptreat <- to_num(row$bptreat)
  statin <- to_num(row$statin)
  uacr <- to_num(row$uacr)
  hba1c <- to_num(row$hba1c)
  sdi <- to_num(row$sdi)

  base <- prevent_base(sex, age, tc, hdl, sbp, dm, smoking, bmi, egfr, bptreat, statin)
  uacr_m <- prevent_uacr(sex, age, tc, hdl, sbp, dm, smoking, bmi, egfr, bptreat, statin, uacr)
  hba1c_m <- prevent_hba1c(sex, age, tc, hdl, sbp, dm, smoking, bmi, egfr, bptreat, statin, hba1c)
  sdi_m <- prevent_sdi(sex, age, tc, hdl, sbp, dm, smoking, bmi, egfr, bptreat, statin, sdi)
  full <- prevent_full(sex, age, tc, hdl, sbp, dm, smoking, bmi, egfr, bptreat, statin, uacr, hba1c, sdi)

  ref[i, "PREVENT10_CVD_BASE_PCT"] <- base$prevent_base_10yr_CVD
  ref[i, "PREVENT10_ASCVD_BASE_PCT"] <- base$prevent_base_10yr_ASCVD
  ref[i, "PREVENT10_HF_BASE_PCT"] <- base$prevent_base_10yr_HF
  ref[i, "PREVENT30_CVD_BASE_PCT"] <- base$prevent_base_30yr_CVD
  ref[i, "PREVENT30_ASCVD_BASE_PCT"] <- base$prevent_base_30yr_ASCVD
  ref[i, "PREVENT30_HF_BASE_PCT"] <- base$prevent_base_30yr_HF

  ref[i, "PREVENT10_CVD_UACR_PCT"] <- uacr_m$prevent_uacr_10yr_CVD
  ref[i, "PREVENT10_ASCVD_UACR_PCT"] <- uacr_m$prevent_uacr_10yr_ASCVD
  ref[i, "PREVENT10_HF_UACR_PCT"] <- uacr_m$prevent_uacr_10yr_HF
  ref[i, "PREVENT30_CVD_UACR_PCT"] <- uacr_m$prevent_uacr_30yr_CVD
  ref[i, "PREVENT30_ASCVD_UACR_PCT"] <- uacr_m$prevent_uacr_30yr_ASCVD
  ref[i, "PREVENT30_HF_UACR_PCT"] <- uacr_m$prevent_uacr_30yr_HF

  ref[i, "PREVENT10_CVD_HBA1C_PCT"] <- hba1c_m$prevent_hba1c_10yr_CVD
  ref[i, "PREVENT10_ASCVD_HBA1C_PCT"] <- hba1c_m$prevent_hba1c_10yr_ASCVD
  ref[i, "PREVENT10_HF_HBA1C_PCT"] <- hba1c_m$prevent_hba1c_10yr_HF
  ref[i, "PREVENT30_CVD_HBA1C_PCT"] <- hba1c_m$prevent_hba1c_30yr_CVD
  ref[i, "PREVENT30_ASCVD_HBA1C_PCT"] <- hba1c_m$prevent_hba1c_30yr_ASCVD
  ref[i, "PREVENT30_HF_HBA1C_PCT"] <- hba1c_m$prevent_hba1c_30yr_HF

  ref[i, "PREVENT10_CVD_SDI_PCT"] <- sdi_m$prevent_sdi_10yr_CVD
  ref[i, "PREVENT10_ASCVD_SDI_PCT"] <- sdi_m$prevent_sdi_10yr_ASCVD
  ref[i, "PREVENT10_HF_SDI_PCT"] <- sdi_m$prevent_sdi_10yr_HF
  ref[i, "PREVENT30_CVD_SDI_PCT"] <- sdi_m$prevent_sdi_30yr_CVD
  ref[i, "PREVENT30_ASCVD_SDI_PCT"] <- sdi_m$prevent_sdi_30yr_ASCVD
  ref[i, "PREVENT30_HF_SDI_PCT"] <- sdi_m$prevent_sdi_30yr_HF

  ref[i, "PREVENT10_CVD_FULL_PCT"] <- full$prevent_full_10yr_CVD
  ref[i, "PREVENT10_ASCVD_FULL_PCT"] <- full$prevent_full_10yr_ASCVD
  ref[i, "PREVENT10_HF_FULL_PCT"] <- full$prevent_full_10yr_HF
  ref[i, "PREVENT30_CVD_FULL_PCT"] <- full$prevent_full_30yr_CVD
  ref[i, "PREVENT30_ASCVD_FULL_PCT"] <- full$prevent_full_30yr_ASCVD
  ref[i, "PREVENT30_HF_FULL_PCT"] <- full$prevent_full_30yr_HF
}

message("Writing reference to ", out_path)
write.csv(ref, out_path, row.names = FALSE, na = "")
message("Done.")
