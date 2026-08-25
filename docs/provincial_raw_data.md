# Provincial Raw Data — Macro Series (branch `provincial_raw_data`)

This document describes the **province-level macro data upgrade** added on the
`provincial_raw_data` branch: what it replaces, where each series comes from, how it was
processed, the assumptions made, and how it flows through the model.

It covers **item #1** of the provincial-data upgrade priority list (CPI, unemployment,
house prices, vacancy) and **item #6** (investment / GFCF institutional split). Items #2–#5
were assessed and found to be non-issues in the current single-firm configuration (see
`provincial_data_comparison.md`).

It also covers a later **effective tax-rate** upgrade — province-specific corporate income,
personal income, and consumption (sales/VAT) tax rates (Section 3c) — added after items #1/#6,
and a **labour-compensation calibration** (Section 3d, part of item #7) that corrects the
initial wage bill: the WIOD SEA source is effectively empty for Canada and was being proxied
from France, giving an initial labour share of 84.4% against Canada's observed 49.8% and
leaving firms loss-making from the first simulated year.

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

### 2.1 Data (in the `raw_data` bundle, not the model repo)

The processed provincial panels live in the shared `raw_data` bundle under a `canadian_inputs/`
folder (flat, one CSV per input), **not** in the model repo — keeping the repo fully downstream
of `raw_data`:

```
<raw_data>/canadian_inputs/provincial_macro_series.csv
```

Columns: `region, date, cpi_inflation, unemployment_rate, hpi_nominal_growth, vacancy_rate`.
The reproducible build scripts (`build_provincial_*.py`) live alongside the CSVs in
`<raw_data>/canadian_inputs/`, since they are upstream of the data they produce.

### 2.2 Code (minimal, backward-compatible)

| File | Change |
|------|--------|
| `macro_data/readers/economic_data/provincial_macro_reader.py` | **New.** `ProvincialMacroReader` loads the panel and blends provincial values over a national series where available. |
| `macro_data/readers/default_readers.py` | Constructs `ProvincialMacroReader.from_default(raw_data_path=...)` from `<raw_data>/canadian_inputs/` and attaches it to `DataReaders.provincial_macro`. |
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

## 3b. Investment / GFCF institutional split (item #6)

### What it replaces

The model splits each province's total gross fixed capital formation (from the provincial IO
table) into **Firm**, **Household**, and **Government** capital formation, using fractions
from `get_investment_fractions_of_country` (`icio_sea_matching.get_investment_fractions` →
`split_gfcf_column`). Canada is absent from the Eurostat `investment_percentage_of_gdp`
series, so the model falls back to **France** — every province received the same French split
(Firm 0.567 / Household 0.263 / Government 0.170).

### Source and processing

- **Source:** Table **36-10-0222-01**, *Gross domestic product, expenditure-based,
  provincial and territorial, annual*, **current prices**, all years **2000–2024**
  ([link](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022201)).
- **Institutional mapping** (to match the model's Firm/Household/Government definition, where
  Eurostat's "Household" = households + NPISH):
  - **Government** = *General governments gross fixed capital formation*
  - **Household** = *Residential structures* + *NPISH gross fixed capital formation*
  - **Firm** = *Business GFCF* − *Residential structures* (= non-residential structures +
    machinery & equipment + intellectual property products)
- **Processing:** for every year 2000–2024, each component is taken at current prices per
  province; fractions = component / (Firm + Household + Government), normalised to sum to 1.
- **Output:** `<raw_data>/canadian_inputs/provincial_investment_fractions.csv`
  (`region, year, firm, household, government`), one row per province × year (250 rows).
  `ProvincialInvestmentReader.get_fractions(region, year)` selects the row matching the run's
  base year (clamping to the nearest available year if out of range), so the split tracks the
  actual investment cycle (e.g. Alberta's firm share falls from 0.755 in 2014 to ~0.63 by
  2020–2024 as the oil-investment boom faded).

### Resulting fractions (2014 — illustrative base year)

| Province | Firm | Household | Government |  | Province | Firm | Household | Government |
|----------|-----:|----------:|-----------:|--|----------|-----:|----------:|-----------:|
| AB | 0.755 | 0.166 | 0.080 | | NS | 0.433 | 0.317 | 0.250 |
| SK | 0.741 | 0.171 | 0.087 | | ON | 0.443 | 0.373 | 0.184 |
| NL | 0.746 | 0.144 | 0.110 | | QC | 0.449 | 0.336 | 0.215 |
| MB | 0.542 | 0.274 | 0.184 | | PE | 0.434 | 0.336 | 0.229 |
| BC | 0.492 | 0.368 | 0.139 | | NB | 0.441 | 0.294 | 0.265 |

Resource provinces (AB, SK, NL) are ~75% firm investment (oil, gas, mining capex) versus the
0.567 French proxy; housing-heavy provinces (ON, BC) carry more household investment; Atlantic
provinces carry proportionally more government investment.

### Code

`ProvincialInvestmentReader` (`macro_data/readers/economic_data/provincial_investment_reader.py`)
loads the file; `get_investment_fractions` in `icio_sea_matching.py` uses the provincial
fraction where available and otherwise keeps the existing Eurostat/France path. No-op when the
file is absent or the region is not Canadian.

## 3c. Effective corporate, personal income & consumption (sales/VAT) tax rates

### What it replaces

All three tax rates were national-only for every province, because the tax readers collapse a
`Region` to its parent country before lookup:

- **Corporate (`profit_tax`):** `OECDEconData.read_tau_firm` returned Canada's single **statutory
  combined** corporate income tax rate (`COMB_CIT_RATE`, ~26.5%) for all ten provinces.
- **Personal (`income_tax`):** `OECDEconData.read_tau_income` returned a **hard-coded `0.09`** for
  Canada (the real OECD data path is commented out), for all ten provinces.
- **Consumption (`value_added_tax`):** `WorldBankReader.get_tau_vat` returned one **national** VAT
  figure for all ten provinces — so Alberta (no provincial sales tax) and Quebec (GST + ~10% QST)
  were treated identically.

### Why *effective* rates (not statutory), and why the sales tax uses the VAT field

The model applies a tax rate **flat** — `rate × base`, with no brackets, deductions,
small-business rate, capital-cost allowance or federal abatement — everywhere it uses one:
`CentralGovernment.compute_taxes` (government revenue), `Firms.compute_corporate_taxes_paid`
and `Banks.compute_equity` (corporate tax paid), the income-tax term on wages + rent +
financial income, and the VAT term on final household consumption. The rates are set **once**
from `TaxData` and are never re-estimated during the simulation. Consequently the scalar the
model needs is the **effective** rate: feeding a statutory marginal rate would overstate tax
paid and government revenue (real effective corporate burden is well below the ~26.5% statutory
rate because of the small-business rate and deductions; effective consumption-tax burden is well
below the statutory GST+PST because groceries, rent, health and financial services are exempt).
All three provincial series are therefore built as effective rates — tax actually paid divided by
the relevant base — from the StatsCan Provincial and Territorial Economic Accounts (PTEA).

**Sales tax → `value_added_tax`.** The model does **not** implement a staged VAT: `value_added_tax`
is applied as a flat `1/(1+τ)` wedge on *final household consumption* only (in every consumption
variant), with revenue `= τ × Σ consumption`; there is no input-tax credit and no tax on
intermediate / firm-to-firm sales. That is mechanically a **retail sales tax**. So a provincial
sales tax needs **no model code change** — it is an effective consumption-tax rate written into
`value_added_tax`. The economic distinctions between a true VAT and a PST (cascading on business
inputs, good-level exemptions, export/import border adjustment) are all outside the model's
resolution and are *not* represented (see Section 4).

### Source and processing

All series are annual PTEA tables downloaded from the StatsCan bulk-CSV endpoint.

| Rate | Model field | Definition | Source table(s) & member |
|------|-------------|-----------|--------------------------|
| **Corporate** | `profit_tax` | corporate income tax paid ÷ corporate net operating surplus | **numerator:** 36-10-0450, `Estimates = "From corporations and government business enterprises, liabilities"` at `Levels of government = "General governments"` (federal + provincial/territorial + local, consolidated, allocated by province) ([link](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610045001)). **denominator:** 36-10-0221, `Estimates = "Net operating surplus: corporations"` ([link](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022101)). |
| **Personal** | `income_tax` | household personal income tax ÷ primary household income | 36-10-0224, `Estimates = "Personal income tax"` ÷ `Estimates = "Primary household income"` ([link](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022401)). |
| **Consumption** | `value_added_tax` | (federal GST + provincial general sales taxes) ÷ household final consumption | **numerator:** 36-10-0450, `Estimates = "Goods and services tax (GST)"` at `Levels of government = "Federal general government"` **plus** `Estimates = "General sales taxes"` at `"Provincial and territorial general governments"` (the PST/HST/QST component; zero where a province has none). **denominator:** 36-10-0224, `Estimates = "Less: household final consumption expenditure"`. |

- **Pooled multi-year window.** Each rate for year *Y* is `Σ numerator / Σ denominator` over a
  **centered 5-year window** (*Y*−2 … *Y*+2, clamped at the panel edges), **not** a single-year
  ratio. This is essential for the corporate rate: corporate net operating surplus collapses in
  downturns (e.g. Alberta in the 2015–16 oil bust), so a single-year tax/surplus ratio spikes to
  implausible values (>70 %) purely because the denominator is momentarily tiny. Pooling recovers
  the structural effective rate and roughly halves the year-to-year volatility. The same window
  is applied to the (already stable) personal and sales rates for methodological consistency.
- **Consolidated levels of government.** The corporate numerator uses the `General governments`
  level so that both federal and provincial corporate income tax raised in a province are
  counted; using only the provincial-government level would omit the (larger) federal share. The
  sales numerator instead sums the **federal** GST and the **provincial** general-sales-tax lines,
  because those are the two consumer-facing components and they sit at different government levels.
- **Coverage:** **2007–2024** (36-10-0450 begins in 2007). The provincial model consumes the
  base-year (2014) value; `ProvincialTaxReader` clamps to the nearest available year for
  out-of-range start years.
- **Output:** `<raw_data>/canadian_inputs/provincial_tax_rates.csv`
  (`region, year, corporate_tax_rate, personal_income_tax_rate, sales_tax_rate`, decimals), one
  row per province × year (180 rows).

### Resulting effective rates (2014 — the model's base year)

| Province | Corporate | Personal | Sales |  | Province | Corporate | Personal | Sales |
|----------|----------:|---------:|------:|--|----------|----------:|---------:|------:|
| AB | 0.297 | 0.178 | 0.035 | | NS | 0.466 | 0.174 | 0.091 |
| BC | 0.289 | 0.160 | 0.073 | | ON | 0.278 | 0.177 | 0.088 |
| MB | 0.185 | 0.172 | 0.087 | | PE | 0.197 | 0.169 | 0.090 |
| NB | 0.197 | 0.160 | 0.087 | | QC | 0.281 | 0.190 | 0.095 |
| NL | 0.101 | 0.181 | 0.091 | | SK | 0.138 | 0.163 | 0.072 |

Personal effective rates are tightly clustered (16–19 %). Corporate effective rates span a wide,
economically-coherent range: resource provinces with low provincial CIT and large, volatile
surplus bases sit low (**NL 0.10, SK 0.14**), while **Nova Scotia (0.47)** is the high outlier —
it levied the highest provincial general CIT (16 % in 2014) on a small, volatile corporate base
with a large government-business-enterprise presence, so its *effective* rate sits above the
statutory combined rate. This NS value is a genuine (documented) data characteristic, not an
error; see the volatility caveat in Section 4. Sales effective rates correctly place **Alberta
lowest (0.035 — GST only, no PST)** and the HST/QST provinces highest (**QC 0.095, NS 0.091**);
all sit below the statutory combined GST+PST because a large share of consumption is exempt.

### Code

`ProvincialTaxReader` (`macro_data/readers/economic_data/provincial_tax_reader.py`) loads the
file; `TaxData.from_readers` (`macro_data/processing/country_data/tax_data.py`) uses the
provincial effective rate where available and otherwise keeps the existing OECD/World-Bank
statutory/proxy path (`profit_tax` → corporate, `income_tax` → personal, `value_added_tax` →
sales). No-op (falls back to national) when the file is absent, the region is not a Canadian
province, or a rate is missing. The reader is loaded once via a cached module-level singleton
(the same lazy-loading style as the item-#6 investment override).

## 3d. Labour compensation — calibrating the initial wage bill (item #7)

### What it replaces

Firms' initial wage bills come from `industry_vectors["Labour Compensation in LCU"]`, built in
`macro_data/readers/util/industry_extraction.py` from the **WIOD Socio-Economic Accounts**
(`raw_data/wiod_sea/wiod_sea.csv`). For Canada that source is effectively **empty**: of 56
industry rows for 2014, exactly **one** is non-zero — *A03, "Fishing and aquaculture"* — and
SEA's Canadian `VA` series is zero in **every** year. The Canadian `COMP` series is also
implausible over time (2,171 → 748 → 602 → 700 across 2000–2014, when Canadian compensation
actually grew steadily).

| country | `COMP` rows (2014) | non-null | **> 0** |
|---------|-------------------:|---------:|--------:|
| **CAN** | 56 | 6 | **1** |
| FRA | 56 | 5 | **4** |
| USA | 56 | 1 | **0** |
| DEU | 56 | 2 | **1** |

The vector is therefore filled through `proxy_country_dict={"CAN": "FRA"}`
(`scenarios/run_canada_provincial.py`) from French data that is itself only 4-of-56 populated,
and then applied against Canadian provincial IO value added.

### Why it matters

**Value added is already accurate** — the model's total ($1.7332T annualised) matches StatCan
2014 value added ($1.7303T) to **0.17%**. The mismatch lands entirely on the labour side:

| | labour share of value added |
|---|---:|
| Model, before this change | **84.4%** |
| Canada, observed (StatCan) | **49.8%** |

Firms are consequently **loss-making in the first simulated year**, before any scenario
mechanism acts. The share then drifts upward, crosses **100% around 2023** — wages exceeding
the value firms create — and the economy has no margin to absorb any shock.

### Source and processing

`<raw_data>/3610000101_customizedLayoutData - <year> - processed.csv` — the **same StatCan
supply-use extract the provincial IO table was built from**, so numerator and denominator come
from one source and the resulting share is consistent by construction. Value-added components
(column `Total use`, $ thousands, Canada 2014):

| component | value |
|---|---:|
| **Wages and salaries** | **861,052,898** |
| Gross mixed income | 227,170,359 |
| Gross operating surplus | 557,797,503 |
| Taxes on production | 89,918,751 |
| Subsidies on production | −5,597,127 |
| **= Value added** | **1,730,342,384** |

giving a labour share of **861,052,898 / 1,730,342,384 = 49.76%**. The existing labour
compensation vector is rescaled by a single scalar onto that share, per province.

### Code

`ProvincialLabourReader` (`macro_data/readers/economic_data/provincial_labour_reader.py`)
reads the share; `DataReaders.from_raw_data` attaches it as `provincial_labour`;
`get_industry_data` applies `rescale()` to `Labour Compensation in LCU` (and recomputes the
USD column) right after the industry vectors are built. No-op — falling back to the existing
SEA/proxy path — when the file is absent, unreadable, or yields a share outside a plausible
band, so national and non-Canadian runs are unaffected.

### Assumptions and limitations

1. **Level only, not composition.** A single scalar is applied per province, so the *relative*
   industry distribution still comes from the SEA/French proxy. Mapping StatCan's ~533
   detailed industries onto the model's 43 codes needs a concordance that is not present in
   the bundle (`icio/mappings.json` is the model's own `A → [A01, A03]` aggregation, and
   `…to icio_can_2014_disagg.csv` is a flow matrix, not a lookup). Building that concordance
   is the natural follow-up and would replace this rescale with a true per-industry vector.
2. **Cross-province labour-share variation is equalised.** Before the change it ranged from
   70.4% (AB) to 91.9% (PE), but that spread is an artefact of French data apportioned by IO
   value added, not observed Canadian variation — so no genuine information is lost. Real
   provincial variation (Alberta's lower labour share, for instance) would require StatCan
   provincial compensation, e.g. 36-10-0221 / 36-10-0480.
3. **Wages and salaries, not full compensation of employees.** Employers' social contributions
   are excluded, so this is a mild *under*-statement of true compensation; the model separately
   grosses wages by `tau_sif` when firms pay them. Including **gross mixed income** as labour
   would instead give 62.9% — self-employment income genuinely mixes labour and capital
   returns, and wages-only is the conservative, convention-matching choice.
4. **A 2014 base-year share, held fixed.** The share is read for the IO table's base year and
   applied at initialisation only; it does not vary over the simulation.
5. **Plausibility guard.** A share outside 35–70% is refused with a warning rather than
   applied, so a wrong file, column or unit change cannot silently recalibrate the model.

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
8. **GFCF split — residential ≈ household (item #6).** The expenditure accounts classify
   residential structures under *business* GFCF and do not separate owner-occupied (household)
   from rental (corporate) dwellings. Following the standard SNA approximation, all residential
   structures investment is attributed to the **Household** sector (matching how the model uses
   *Household Fixed Capital Formation*). This slightly overstates household investment where
   rental construction is large. Fractions use current-price (nominal) values; the model
   consumes the base-year split, held fixed across the run.
9. **Effective, not statutory, tax rates (tax section).** All three tax rates (corporate,
   personal, consumption) are computed as tax-paid ÷ base ratios, because the model applies the
   rate flat with no bracket, deduction or exemption machinery (see Section 3c). They therefore
   capture the *actual* average burden, not the legislated marginal rate. A consequence is that
   switching national Canada from the OECD statutory corporate rate (~26.5 %) — and from the
   national World-Bank VAT figure — to the effective rates is itself a revenue *level* change,
   independent of the cross-province variation; the comparison report separates the two.
10. **Corporate rate volatility (tax section).** Corporate net operating surplus is volatile, so
    even after the 5-year pooling the corporate effective rate carries more noise than the
    personal rate, and small provinces (PE, NS, NL) are the noisiest. The pooled series is the
    intended input; the raw single-year ratios (recoverable by setting `WINDOW_HALF = 0` in the
    build script) should not be used, as downturn years produce >70 % artefacts.
11. **Model base ≠ accounts base (tax section).** The effective rate is measured against the
    national-accounts income base, but the model applies it to its own *endogenous* profit /
    income base, which need not equal the accounts aggregate. The rate is therefore the correct
    *concept* for the model but will not reproduce observed dollar tax revenue exactly.
12. **Corporate base includes government business enterprises (tax section).** Both the corporate
    tax numerator ("… and government business enterprises") and the net-operating-surplus
    denominator include GBEs (e.g. provincial power / liquor corporations), so numerator and
    denominator are consistent. Personal income tax is levied by all levels of government and the
    denominator (primary household income = compensation + net mixed income + net property income)
    matches the model's income-tax base (wages + rent + financial income), excluding transfers.
13. **Sales tax is a consumption tax, VAT-vs-PST distinction not modelled (tax section).** The
    provincial sales rate is written into `value_added_tax`, which the model applies as a uniform
    flat wedge on final household consumption. The model therefore captures the *revenue* and
    *consumer-incidence* effects of a provincial sales tax, but **not** the economic features that
    distinguish a retail PST from a VAT: PST cascading on business inputs, good-level exemptions
    (the effective rate already folds the *average* exemption effect into the number, but the tax
    is uniform across goods in-model), and VAT export/import border adjustment. Capturing those
    would require new model mechanics (taxing intermediate inputs), which the current single-firm,
    no-input-credit configuration does not warrant. The effective consumption rate is the
    model-consistent input. AB's rate (~0.035) reflects GST only, as Alberta levies no sales tax.

## Start-year flexibility

The provincial data is now multi-year so the model inputs support a range of start years:
- **#1 macro series:** quarterly **1998–2024** (vacancy 2015+).
- **#6 investment fractions:** annual **2000–2024**.

Both readers select by the run's base year, so changing the start year automatically picks the
right vintage. **However**, the provincial start year is still pinned to **2014** by the
provincial IO table itself: `DataReaders.from_raw_data` raises *"Only 2014 is supported for
this reader"* in the `use_provincial_can_reader` branch, because the provincial IO/trade matrix
(`icio_2014_can_provinces.csv`) is a 2014 table. To actually start the provincial model in
another year you would additionally need a provincial IO table for that year (or a rebasing
step). The multi-year #1/#6 data removes the *data-side* obstacle and already feeds the
calibration history; the remaining constraint is the IO base year.

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

The build scripts live in the `raw_data` bundle at `<raw_data>/canadian_inputs/` (upstream of
the model repo) and write their CSVs into that same folder (flat):

```bash
# Run from <raw_data>/canadian_inputs/
# 1a. Download the four StatsCan tables (bulk CSV) and process to the #1 macro panel.
python build_provincial_macro_series.py

# 1b. Rebuild the #6 investment-fraction panel.
python build_provincial_investment_fractions.py

# 1c. Rebuild the effective tax-rate panel (Section 3c).
python build_provincial_tax_rates.py

# 1d. Labour compensation (Section 3d) needs NO build step: the reader consumes the StatCan
#     supply-use extract already at the raw_data root
#     (3610000101_customizedLayoutData - <year> - processed.csv), the same file the
#     provincial IO table was built from.

# 2. Rebuild the provincial pickle (all overrides activate automatically when the files exist).
python scenarios/run_canada_provincial.py --input-path <raw_data> --skip-simulation \
    --pkl-path <out>/data_provincial_model_NEW.pkl --force-rebuild-pickle
```

The readers resolve these files from `<raw_data>/canadian_inputs/` via
`DataReaders.from_raw_data` (each is a no-op if its file is absent, so national/proxy runs and
non-Canadian `raw_data` bundles are unaffected). The processing scripts and exact filter
definitions are recorded in Sections 3, 3b and 3c; the StatsCan table PIDs are `18100004` (CPI),
`14100287` (LFS), `18100205` (NHPI), `14100325` (JVWS) for #1, `36100222` for #6, and
`36100450` / `36100221` / `36100224` for the tax rates.
