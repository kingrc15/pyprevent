#!/usr/bin/env Rscript
# Score arbitrary PREVENT input rows with AHAprevent (batch golden for parity tests).
suppressPackageStartupMessages({
  library(utils)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Usage: score_cases.R <input.csv> <output.csv>")
}

in_path <- args[[1]]
out_path <- args[[2]]

if (!file.exists(in_path)) {
  stop(paste("Missing input file:", in_path))
}

file_arg <- commandArgs(trailingOnly = FALSE)
script_arg <- sub("^--file=", "", file_arg[grep("^--file=", file_arg)])
root <- if (length(script_arg)) {
  normalizePath(file.path(dirname(script_arg), ".."))
} else {
  normalizePath(getwd())
}

default_pkg <- file.path(root, "..", "PREVENT", "R", "AHAprevent")
pkg_path <- Sys.getenv("PREVENT_R_PKG", unset = default_pkg)
skip_install <- identical(Sys.getenv("PREVENT_SKIP_R_INSTALL"), "1")

if (!skip_install) {
  status <- system(paste("R CMD INSTALL", shQuote(pkg_path)))
  if (status != 0) {
    stop("Failed to install AHAprevent from ", pkg_path)
  }
}

suppressPackageStartupMessages({
  library(AHAprevent)
})

cases <- read.csv(in_path, stringsAsFactors = FALSE, na.strings = c("", "NA"))
required <- c(
  "case_id", "sex", "age", "tc", "hdl", "sbp", "dm", "smoking",
  "bmi", "egfr", "bptreat", "statin", "uacr", "hba1c", "sdi"
)
missing <- setdiff(required, names(cases))
if (length(missing)) {
  stop(paste("Input missing columns:", paste(missing, collapse = ", ")))
}

to_num <- function(x) as.numeric(x)

safe_val <- function(x) {
  if (length(x) == 0 || is.null(x)) {
    return(NA_real_)
  }
  v <- x[[1]]
  if (length(v) == 0) {
    return(NA_real_)
  }
  as.numeric(v)
}

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

  ref[i, "PREVENT10_CVD_BASE_PCT"] <- safe_val(base$prevent_base_10yr_CVD)
  ref[i, "PREVENT10_ASCVD_BASE_PCT"] <- safe_val(base$prevent_base_10yr_ASCVD)
  ref[i, "PREVENT10_HF_BASE_PCT"] <- safe_val(base$prevent_base_10yr_HF)
  ref[i, "PREVENT30_CVD_BASE_PCT"] <- safe_val(base$prevent_base_30yr_CVD)
  ref[i, "PREVENT30_ASCVD_BASE_PCT"] <- safe_val(base$prevent_base_30yr_ASCVD)
  ref[i, "PREVENT30_HF_BASE_PCT"] <- safe_val(base$prevent_base_30yr_HF)

  ref[i, "PREVENT10_CVD_UACR_PCT"] <- safe_val(uacr_m$prevent_uacr_10yr_CVD)
  ref[i, "PREVENT10_ASCVD_UACR_PCT"] <- safe_val(uacr_m$prevent_uacr_10yr_ASCVD)
  ref[i, "PREVENT10_HF_UACR_PCT"] <- safe_val(uacr_m$prevent_uacr_10yr_HF)
  ref[i, "PREVENT30_CVD_UACR_PCT"] <- safe_val(uacr_m$prevent_uacr_30yr_CVD)
  ref[i, "PREVENT30_ASCVD_UACR_PCT"] <- safe_val(uacr_m$prevent_uacr_30yr_ASCVD)
  ref[i, "PREVENT30_HF_UACR_PCT"] <- safe_val(uacr_m$prevent_uacr_30yr_HF)

  ref[i, "PREVENT10_CVD_HBA1C_PCT"] <- safe_val(hba1c_m$prevent_hba1c_10yr_CVD)
  ref[i, "PREVENT10_ASCVD_HBA1C_PCT"] <- safe_val(hba1c_m$prevent_hba1c_10yr_ASCVD)
  ref[i, "PREVENT10_HF_HBA1C_PCT"] <- safe_val(hba1c_m$prevent_hba1c_10yr_HF)
  ref[i, "PREVENT30_CVD_HBA1C_PCT"] <- safe_val(hba1c_m$prevent_hba1c_30yr_CVD)
  ref[i, "PREVENT30_ASCVD_HBA1C_PCT"] <- safe_val(hba1c_m$prevent_hba1c_30yr_ASCVD)
  ref[i, "PREVENT30_HF_HBA1C_PCT"] <- safe_val(hba1c_m$prevent_hba1c_30yr_HF)

  ref[i, "PREVENT10_CVD_SDI_PCT"] <- safe_val(sdi_m$prevent_sdi_10yr_CVD)
  ref[i, "PREVENT10_ASCVD_SDI_PCT"] <- safe_val(sdi_m$prevent_sdi_10yr_ASCVD)
  ref[i, "PREVENT10_HF_SDI_PCT"] <- safe_val(sdi_m$prevent_sdi_10yr_HF)
  ref[i, "PREVENT30_CVD_SDI_PCT"] <- safe_val(sdi_m$prevent_sdi_30yr_CVD)
  ref[i, "PREVENT30_ASCVD_SDI_PCT"] <- safe_val(sdi_m$prevent_sdi_30yr_ASCVD)
  ref[i, "PREVENT30_HF_SDI_PCT"] <- safe_val(sdi_m$prevent_sdi_30yr_HF)

  ref[i, "PREVENT10_CVD_FULL_PCT"] <- safe_val(full$prevent_full_10yr_CVD)
  ref[i, "PREVENT10_ASCVD_FULL_PCT"] <- safe_val(full$prevent_full_10yr_ASCVD)
  ref[i, "PREVENT10_HF_FULL_PCT"] <- safe_val(full$prevent_full_10yr_HF)
  ref[i, "PREVENT30_CVD_FULL_PCT"] <- safe_val(full$prevent_full_30yr_CVD)
  ref[i, "PREVENT30_ASCVD_FULL_PCT"] <- safe_val(full$prevent_full_30yr_ASCVD)
  ref[i, "PREVENT30_HF_FULL_PCT"] <- safe_val(full$prevent_full_30yr_HF)
}

write.csv(ref, out_path, row.names = FALSE, na = "")
