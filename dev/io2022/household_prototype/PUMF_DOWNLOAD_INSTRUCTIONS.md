# Manual PUMF download — SFS 2023, CIS 2022, SHS 2019

These three files are **not** programmatically downloadable: StatCan PUMFs require going through the
catalogue page and accepting the open-data licence; there is no WDS/API endpoint for microdata. Download
them manually and unzip into the drop-in folders below. **Do not substitute synthetic/stand-in data.**

## Drop-in folder structure (already created)

```text
dev/raw_data/can_2022/pumf/
  sfs_2023/   <- SFS 2023 data CSV + codebook   (13M0006X)
  cis_2022/   <- CIS 2022 data CSV + codebook   (72M0003X, 2022 reference year)
  shs_2019/   <- SHS 2019 data CSV + codebook   (62M0004X)  [archive only; Phase-2]
```

## SFS 2023 — Survey of Financial Security PUMF (13M0006X)

1. Open the catalogue page: https://www150.statcan.gc.ca/n1/pub/13m0006x/13m0006x2021001-eng.htm
   (or the 2023 open-license dataset: https://ouvert.canada.ca/data/dataset/11aecdcb-8bec-4dbe-9da2-3b0cc4e740c9)
2. Select the **2023** reference period; download the CSV/zip PUMF package (contains the data file +
   user guide + **codebook / layout card**).
3. Unzip into `dev/raw_data/can_2022/pumf/sfs_2023/`. Expect a family-level data CSV (economic family)
   and a codebook. Note the exact data filename.

## CIS 2022 — Canadian Income Survey PUMF (72M0003X)

1. Catalogue page: https://www150.statcan.gc.ca/n1/pub/72m0003x/72m0003x2024001-eng.htm
2. Download the **2022 reference year** PUMF (SAS/SPSS/STATA/CSV) + codebook; unzip into
   `dev/raw_data/can_2022/pumf/cis_2022/`. This is person + household level income by source.

## SHS 2019 — Survey of Household Spending PUMF (62M0004X)  [obtain/archive only]

1. Catalogue page: https://www150.statcan.gc.ca/n1/en/catalogue/62M0004X
2. Download the **2019** PUMF + codebook; unzip into `dev/raw_data/can_2022/pumf/shs_2019/`.
   **Not used in Phase 1** — archive for the later consumption step.

## After downloading

1. Open the SFS 2023 and CIS 2022 **codebooks** and fill `SFS_COLUMN_MAP` / `CIS_COLUMN_MAP` in
   `prepare_household_canadianization.py` (see the variable classification in VALIDATION_REPORT.md §
   "Source-variable classification" for what to look for and the special/missing-value codes).
2. Point the `--real` loader at the data filenames.
3. Run: `uv run python dev/io2022/household_prototype/prepare_household_canadianization.py --real`
   (controls_2022.json is already populated with official 2022 values).
