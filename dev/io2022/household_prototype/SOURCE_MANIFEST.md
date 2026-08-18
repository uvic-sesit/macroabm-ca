# Household Canadianization — source manifest (balance sheet + income + consumption; integrated MVP)

## Raw-data root (configurable) & canonical layout
All prep/build scripts resolve ONE raw-data root via `dev/io2022/household_prototype/_paths.py`
(`raw_data_root`), in this order:
1. `$MACROABM_RAW_DATA` (explicit override);
2. `<repo>/raw_data/` — the canonical root-level layout (pushed-repo / clone convention), if it exists;
3. `<repo>/dev/raw_data/` — the legacy local layout (backward-compatible default; current local setup).

The production model (`macro_data`) is already root-agnostic — `DataWrapper.from_config` takes an injected
`raw_data_path` and reads `raw_data_path/{hfcs, can_2022, icio}`. Expected tree under the resolved root
(files are git-ignored and NOT committed — see below):
```
raw_data/
├── can_2022/
│   ├── pumf/
│   │   ├── sfs_2023/   sfs2023_efam_pumf.csv (+ label/codebook files)
│   │   ├── cis_2022/   CIS2022_PUMF.csv (+ data dictionary, layout SAS)
│   │   ├── shs_2023/   PUMF_SHS_2023.txt, pumf_SHS_2023_i.SAS (+ codebook)
│   │   └── shs_archive/ SHS_EDM_2019.zip, SHS_EDM_2021.zip
│   ├── controls/       11 StatCan control CSVs incl. 46100083 (CHS tenure)  ← regenerate via scripts
│   └── compensation_of_employees_/ employment_shares_/ capital_*_oecd50_by_province*.csv  (2022 integration)
├── hfcs/               SHARED member skeleton (2010/2014/2017/2021, all countries) — NOT Canadian-specific
└── icio/               SHARED IO tables incl. icio_2022_can_provinces.csv — NOT duplicated
```

## STATUS 2026-08 — integrated MVP; household economic block validated + wired into the 2022 DataWrapper
- ✅ SFS 2023 PUMF (`can_2022/pumf/sfs_2023/sfs2023_efam_pumf.csv`, 16,241 economic families) + label files.
- ✅ CIS 2022 PUMF (`can_2022/pumf/cis_2022/CIS2022_PUMF.csv`) + data-dictionary/layout. (Income-source
  shares are baked into `canadianized_household_adapter.py`; CIS is read only to regenerate them.)
- ✅ SHS 2023 PUMF (`can_2022/pumf/shs_2023/`, fixed-width TXT + SAS layout); 2019/2021 archived under
  `can_2022/pumf/shs_archive/`. **SHS 2023 selected** (behavioural consumption propensity).
- ✅ 11 control tables downloaded → `controls_2022.json` populated (incl. **CHS 46-10-0083** tenure).
- ✅ Household block integrated (adapter + Option B income reconciliation); 13q baseline stable.
All PUMFs / generated household CSVs / control-table CSVs are git-ignored and NOT committed. Regenerate the
controls with `download_controls.py` + `extract_controls.py`; place the licensed PUMFs manually (below), then
run `prepare_household_canadianization.py --real` and `prepare_household_consumption.py --real`.

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
| consumption (behavioural propensity) | Survey of Household Spending PUMF | **62M0004X** | **2023** | 2023 (TC001 total current consumption) | https://www150.statcan.gc.ca/n1/en/catalogue/62M0004X |

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
| **Household characteristics by tenure (Canadian Housing Survey)** | **46-10-0083** | 2022 homeownership control **65.41%** (owner 10,109,100 / total 15,455,000 households, provinces only) — tenure + household-count calibration |
| Household final consumption / disposable income / net saving (DHEA) | **36-10-0587** | 2022 HFCE 1,511,381 $M (macro consumption control) + disposable income + net saving |

## Recipient skeleton (SHARED — NOT under can_2022, not duplicated)

- HFCS-2021 raw waves: `<root>/hfcs/2021/{d,h,p}*.csv` — recipient household/member skeleton + IDs, and the
  all-country individual pool loaded for the integration (`no_country_filter`). Shared across all countries.
- Old Canadianized outputs (SFS-2016/CIS-2017), **schema reference / stand-in donor only**:
  `<root>/hfcs/New_Household*.csv`, `New_Individuals*.csv`. `New_*_provincial.csv` carry **no province
  field** and were **not** production inputs. The generator script is **not** in the repo — only the output
  schema is reused; 2016/2017 assumptions are **not** inherited.
- Provincial IO: `<root>/icio/icio_2022_can_provinces.csv` — SHARED IO table (reader path `raw_data/icio/`).
