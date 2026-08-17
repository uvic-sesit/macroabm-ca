# Household Canadianization — source manifest (Phase 1: balance sheet + income)

## STATUS 2026-08 — files present, Phase-1 REAL run validated
- ✅ SFS 2023 PUMF (`pumf/sfs_2023/sfs2023_efam_pumf.csv`, 16,241 economic families) + label files.
- ✅ CIS 2022 PUMF (`pumf/cis_2022/CIS2022_PUMF.csv`) + data-dictionary PDF.
- ✅ SHS 2019 / 2021 / **2023** ZIPs (`pumf/shs_2019/`) — **SHS 2023 selected** (fixed-width TXT, Phase-2).
- ✅ 8 control tables downloaded → `controls_2022.json` populated with official 2022 values.
- ✅ `SFS_COLUMN_MAP` / `CIS_COLUMN_MAP` filled from the SFS/CIS codebooks (in the prep script).
- ⏭ SHS consumption + saving = deferred Phase-2 (substantial: fixed-width parse + donor match).
All PUMFs / generated household CSVs / control-table CSVs live under the git-ignored `dev/` tree and are
NOT committed. Reproduce via `download_controls.py` + `extract_controls.py` + the manual PUMF downloads.

---


**Data-availability note.** None of the microdata/control files below are bundled in the repo or
downloadable in the build environment — StatCan PUMFs require manual portal download + open-licence
acceptance, and the DHEA/NBSA tables are interactive. Obtain them manually and place at the paths
noted; then fill `SFS_COLUMN_MAP` / `CIS_COLUMN_MAP` / `CONTROLS_2022` in
`prepare_household_canadianization.py` from the codebooks/tables before running `--real`.

## Donor / income microdata (PUMF)

| role | dataset | StatCan ID | vintage chosen | reference period | URL |
|---|---|---|---|---|---|
| wealth/assets + debt donor | Survey of Financial Security PUMF | **13M0006X** | **2023** | collected Apr 21–Aug 31 2023 (mode: self-complete EQ) | https://www150.statcan.gc.ca/n1/pub/13m0006x/13m0006x2021001-eng.htm ; open-license 2023: https://ouvert.canada.ca/data/dataset/11aecdcb-8bec-4dbe-9da2-3b0cc4e740c9 |
| income / person allocation | Canadian Income Survey PUMF | **72M0003X** | **2022** (ref year) | ref-year 2022, released 2024 | https://www150.statcan.gc.ca/n1/pub/72m0003x/72m0003x2024001-eng.htm |
| consumption (Phase 2 only) | Survey of Household Spending PUMF | **62M0004X** | **2019** (latest) | 2019 | https://www150.statcan.gc.ca/n1/en/catalogue/62M0004X |

SFS geographic coverage: **10 provinces only — no YT/NT/NU** (both 2019 and 2023). Territories use a
documented national/nearest-province donor fallback in the prototype.

## 2022 aggregate controls (benchmark targets; distributional + aggregate)

| control | StatCan table | use |
|---|---|---|
| Distributions of Household Economic Accounts — **wealth**, quarterly, by characteristic | **36-10-0660** | 2022 net-worth / asset / debt distribution by quintile/type (reconciled to NBSA) |
| DHEA — income, consumption, saving, annual | **36-10-0587** | 2022 income/consumption/saving by quintile |
| National Balance Sheet Accounts — households | **36-10-0580** | 2022 aggregate asset/debt/net-worth class totals |
| Household credit / mortgage vs consumer | **38-10-0238** | 2022 mortgage vs consumer debt totals |
| Backcast intermediates (2023→2022) — NHPI / CPI | **18-10-0205** / **18-10-0004** | housing / general price movement (intermediate only) |
| Household & family counts (weight calibration) | **17-10-0009**, **11-10-0012** | calibrate donor weights to 2022 households by province |

## Recipient skeleton (already local)

- HFCS-2021 raw waves: `dev/raw_data/hfcs/2021/{d,h,p}*.csv` — recipient household/member skeleton + IDs.
- Old Canadianized outputs (SFS-2016/CIS-2017), **schema reference / stand-in donor only**:
  `dev/raw_data/hfcs/New_Household*.csv`, `New_Individuals*.csv`. The generator script is **not** in
  the repo — only the output schema is reused; 2016/2017 assumptions are **not** inherited.
