# Manual PUMF download — SFS 2023, CIS 2022, SHS 2023

These files are **not** programmatically downloadable: StatCan PUMFs require going through the catalogue
page and accepting the open-data licence; there is no WDS/API endpoint for microdata. Download them
manually and unzip into the drop-in folders below. **Do not substitute synthetic/stand-in data.**

## Raw-data root
Scripts resolve ONE root (`_paths.raw_data_root`): `$MACROABM_RAW_DATA` → `<repo>/raw_data/` (if it exists)
→ `<repo>/dev/raw_data/` (legacy default). Place the files under `<root>/can_2022/pumf/…`. `<root>` below =
the resolved root (currently `dev/raw_data` locally; set `MACROABM_RAW_DATA` to override).

## Drop-in folder structure

```text
<root>/can_2022/pumf/
  sfs_2023/     <- SFS 2023 data CSV + codebook   (13M0006X)
  cis_2022/     <- CIS 2022 data CSV + codebook   (72M0003X, 2022 reference year)
  shs_2023/     <- SHS 2023 fixed-width TXT + SAS layout + codebook   (62M0004X)
  shs_archive/  <- SHS 2019 / 2021 zips           (archive only)
```

## SFS 2023 — Survey of Financial Security PUMF (13M0006X)

1. Open the catalogue page: https://www150.statcan.gc.ca/n1/pub/13m0006x/13m0006x2021001-eng.htm
   (or the 2023 open-license dataset: https://ouvert.canada.ca/data/dataset/11aecdcb-8bec-4dbe-9da2-3b0cc4e740c9)
2. Select the **2023** reference period; download the CSV/zip PUMF package (contains the data file +
   user guide + **codebook / layout card**).
3. Unzip into `<root>/can_2022/pumf/sfs_2023/`. Expect a family-level data CSV (economic family)
   and a codebook. Note the exact data filename.

## CIS 2022 — Canadian Income Survey PUMF (72M0003X)

1. Catalogue page: https://www150.statcan.gc.ca/n1/pub/72m0003x/72m0003x2024001-eng.htm
2. Download the **2022 reference year** PUMF (SAS/SPSS/STATA/CSV) + codebook; unzip into
   `<root>/can_2022/pumf/cis_2022/`. This is person + household level income by source.

## SHS 2023 — Survey of Household Spending PUMF (62M0004X)

1. Catalogue page: https://www150.statcan.gc.ca/n1/en/catalogue/62M0004X
2. Download the **2023** PUMF + codebook; unzip into `<root>/can_2022/pumf/shs_2023/`. The pipeline reads
   the fixed-width `PUMF_SHS_2023.txt` + the SAS input layout `pumf_SHS_2023_i.SAS`. Archive 2019/2021 zips
   under `<root>/can_2022/pumf/shs_archive/`.

## Controls (programmatic — no manual download)
`uv run python dev/io2022/household_prototype/download_controls.py` fetches the 11 public StatCan tables
(incl. CHS 46-10-0083) into `<root>/can_2022/controls/`; `extract_controls.py` writes `controls_2022.json`
(committed). The pipeline reads `controls_2022.json` at runtime, not the raw CSVs.

## After downloading — run the pipeline
The column maps are already filled (`SFS_COLUMN_MAP` / SHS layout parser / CIS shares baked into the adapter).
```bash
uv run python dev/io2022/household_prototype/prepare_household_canadianization.py --real   # balance sheet + income
uv run python dev/io2022/household_prototype/prepare_household_consumption.py --real        # consumption + saving
uv run python dev/io2022/build_2022_datawrapper.py --canadianized --force --check-households # integrate + build
```
