# Provincial Raw Data — Macro Series (branch `provincial_raw_data`)

This document describes the **province-level macro data upgrade** added on the
`provincial_raw_data` branch: what it replaces, where each series comes from, how it was
processed, the assumptions made, and how it flows through the model.

It covers **item #1** of the provincial-data upgrade priority list (CPI, unemployment,
house prices, vacancy). Items #2–#5 (sectoral growth, firm size distribution, firm
financials, household income/saving) are not yet included.

---

## 1. Why this upgrade exists

The provincial model builds ten Canadian provinces, but the underlying data readers
(`world_bank`, `oecd`, `imf`, `eurostat`, …) all begin every lookup by collapsing a
`Region` to its parent country:

```python
if isinstance(country, Region):
    country = country.parent_country   # CAN_AB, CAN_BC, ... -> CAN
```

As a result, every province was handed the **same national** CPI, unemployment,
house-price and vacancy path. In the pre-upgrade `data_provincial_model.pkl`, all ten
provinces carried an identical 2014 unemployment rate of 6.91%, identical CPI, a
degenerate (all-NaN) national house-price series, and **no** vacancy data at all
(the OECD vacancy series is empty for Canada).

This upgrade injects genuinely provincial series for those four variables so that, e.g.,
Alberta (4.8% unemployment in 2014) and Newfoundland & Labrador (12.1%) start and evolve
from different labour-market conditions.

---

## 2. What was changed

### 2.1 Data (this branch, not committed to `raw_data`)

A single processed panel is written to a **temporary** folder so it never overwrites the
canonical `raw_data`:

```
dependencies/macroabm-ca/new_raw_data/statcan_provincial/provincial_macro_series.csv
```

Columns: `region, date, cpi_inflation, unemployment_rate, hpi_nominal_growth, vacancy_rate`.

### 2.2 Code (minimal, backward-compatible)

| File | Change |
|------|--------|
| `macro_data/readers/economic_data/provincial_macro_reader.py` | **New.** `ProvincialMacroReader` loads the panel and blends provincial values over a national series where available. |
| `macro_data/readers/default_readers.py` | Constructs `ProvincialMacroReader.from_default()` and attaches it to `DataReaders.provincial_macro`. |
| `macro_data/readers/exogenous_data.py` | Three override hooks: CPI (in `from_data_readers`), house-price growth (in `from_data_readers`), unemployment + vacancy (in `prepare_labour_stats`). |

The override is **opt-in by data presence**: if `provincial_macro_series.csv` is absent,
or a region has no row, the reader returns the original national/proxy series. National
(non-provincial) runs and every non-Canadian country are therefore unaffected. Values are
**blended, not clobbered** — provincial data is substituted only where it exists, and the
national series is retained elsewhere (pre-1998 history; vacancy before 2015).

---

## 3. Data sources and processing

All series were downloaded from Statistics Canada's public bulk-CSV endpoint
(`https://www150.statcan.gc.ca/n1/tbl/csv/{pid}-eng.zip`) and filtered to the ten
provinces. Province name → model code mapping:

| StatsCan GEO | Model code |  | StatsCan GEO | Model code |
|---|---|---|---|---|
| Alberta | `CAN_AB` | | Nova Scotia | `CAN_NS` |
| British Columbia | `CAN_BC` | | Ontario | `CAN_ON` |
| Manitoba | `CAN_MB` | | Prince Edward Island | `CAN_PE` |
| New Brunswick | `CAN_NB` | | Quebec | `CAN_QC` |
| Newfoundland and Labrador | `CAN_NL` | | Saskatchewan | `CAN_SK` |

Common processing: monthly source data is aggregated to calendar quarters by **mean**,
then mapped to quarter-start timestamps (months 1/4/7/10) to match the model's calibration
index. Output span: 1998-Q1 to 2024-Q4 (the model reindexes to what it needs).

### 3.1 CPI inflation — `cpi_inflation`

- **Source:** Table **18-10-0004-01**, *Consumer Price Index, monthly, not seasonally adjusted*
  ([link](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401)).
- **Filter:** `Products and product groups = "All-items"`, `GEO ∈ provinces`.
- **Processing:** quarterly-average index level per province, then quarter-over-quarter
  percentage change (decimal).
- **Replaces:** the CPI-inflation column that the model otherwise takes from the IMF IFS
  file (`imf/IFS.csv`) at the national level.

### 3.2 Unemployment rate — `unemployment_rate`

- **Source:** Table **14-10-0287-03**, *Labour force characteristics by province, monthly, seasonally adjusted*
  ([link](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028703)).
- **Filter:** `Labour force characteristics = "Unemployment rate"`, `Gender = "Total - Gender"`,
  `Age group = "15 years and over"`, `Statistics = "Estimate"`, `Data type = "Seasonally adjusted"`,
  `UOM = "Percent"`.
- **Processing:** quarterly-average rate, converted to decimal (÷100).
- **Replaces:** the World Bank national unemployment series
  (`world_bank/API_SL.UEM.TOTL.ZS…csv`), which the model uses for Canada and which ends in 2021.

### 3.3 Nominal house-price growth — `hpi_nominal_growth`

- **Source:** Table **18-10-0205-01**, *New Housing Price Index, monthly*
  ([link](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810020501)).
- **Filter:** `New housing price indexes = "Total (house and land)"`, `GEO ∈ provinces`.
- **Processing:** quarterly-average index (base 201612=100), then quarter-over-quarter
  percentage change (decimal). The model consumes the **growth** of the nominal index and
  re-normalizes to the base year internally.
- **Replaces:** the OECD nominal house-price series, which for Canada produced an all-NaN
  `HPI (Value)` in the pre-upgrade pickle.

### 3.4 Job vacancy rate — `vacancy_rate`

- **Source:** Table **14-10-0325-01**, *Job vacancies, payroll employees, job vacancy rate,
  and average offered hourly wage by province and territory, quarterly*
  ([link](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410032501)).
- **Filter:** `Statistics = "Job vacancy rate"`, `UOM = "Percentage"`, `GEO ∈ provinces`.
- **Processing:** quarterly rate, converted to decimal (÷100).
- **Coverage:** JVWS begins **2015-Q1**; there is no vacancy history before that. Earlier
  quarters remain NaN (the OECD national vacancy series was already empty for Canada, so
  this strictly adds data).
- **Replaces / fills:** the previously-empty OECD vacancy series for Canada.

---

## 4. Assumptions and limitations

1. **PPI is left national.** Canada has no provincial Industrial Product Price Index; the
   model's PPI already falls back to CPI/zero at the national level. To keep the comparison
   clean (isolating the four target series), provincial PPI was **not** introduced — PPI
   behaves exactly as before.
2. **Quarterly aggregation by simple mean** of monthly index levels; inflation/HPI growth
   is then computed on the quarterly-average series (not an end-of-quarter or geometric
   aggregation). This matches the quarterly convention the readers already use.
3. **CPI base/linking.** The all-items CPI is used as published (StatsCan handles basket
   re-linking); only quarter-over-quarter growth is consumed, so the index base is irrelevant.
4. **New Housing Price Index as the house-price proxy.** NHPI covers newly-built
   *residential* structures (house + land) and is the province-level series with the longest
   clean history. It is not a resale/whole-stock price index; it is used here as the nominal
   house-price *growth* signal per province.
5. **Vacancy pre-2015 is absent**, so any behaviour keyed to vacancy before 2015 keeps the
   national (empty) fallback. For a 2014-base run this affects only the first year.
6. **Unemployment is seasonally adjusted**; CPI and NHPI are not seasonally adjusted
   (StatsCan does not publish SA provincial CPI/NHPI). Because the model consumes quarterly
   averages and growth rates, residual seasonality is largely averaged out.
7. **Blend at the series level.** Where provincial data exists it fully replaces the national
   value for that quarter/region; there is no smoothing between the provincial and national
   segments at the 1998 / 2015 boundaries.

---

## 5. Validation

Rebuilding the pickle with the override active and diffing against the pre-upgrade
`data_provincial_model.pkl` confirms the change is correctly scoped:

- **Unemployment (2014-Q1):** old = 0.0691 for every province (cross-province std = 0);
  new = province-specific (AB 0.048, SK 0.043, NL 0.121; std = 0.026).
- **CPI index (2020-Q1):** old identical 1.1043; new varies (BC 1.123 highest, QC 1.085 lowest).
- **House prices:** old `HPI (Value)` was NaN; new carries real provincial values (ON 1.18, SK 0.93).
- **Vacancy:** old empty; new province-specific from 2015 (BC 4.2%, NL 1.5%).
- **Structural invariance:** `GDP (Value)` and `Compensation of Employees (Value)` are
  unchanged to ~1e-16, confirming the provincial IO structure and all non-targeted series
  are untouched.

---

## 6. Regenerating the data

```bash
# 1. Download the four StatsCan tables (bulk CSV) and process to the tidy panel.
python new_raw_data/build_provincial_macro_series.py

# 2. Rebuild the provincial pickle (override activates automatically when the file exists).
python scenarios/run_canada_provincial.py --input-path <raw_data> --skip-simulation \
    --pkl-path <out>/data_provincial_model_NEW.pkl --force-rebuild-pickle
```

The processing script and exact filter definitions are recorded in Section 3; the
StatsCan table PIDs are `18100004` (CPI), `14100287` (LFS), `18100205` (NHPI),
`14100325` (JVWS).
