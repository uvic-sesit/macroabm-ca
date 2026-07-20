# Provincial Macro Data — Scenario Comparison

Comparison of two otherwise-identical provincial runs that differ **only** in the four
macro series upgraded on the `provincial_raw_data` branch (CPI, unemployment, house-price
growth, vacancy). See `provincial_raw_data.md` for the data and code changes.

## Run configuration (identical across both scenarios)

- Base config: `scenarios/run_canada_provincial.py` (Sample provincial notebook settings) —
  TFP growth (`SimpleTFPGrowth`), technical-coefficient growth, single firm/bank/government
  per province, `time_unit = 3`, `seed = 0`.
- **Energy-bundle substitution enabled**: the CIMS energy carriers
  `[B05a, B05b, B05c, C19, D]` (coal, natural gas, crude oil, refined petroleum, electricity)
  are grouped into one `BundledLeontief` substitution bundle (indices `[1, 2, 3, 10, 24]`).
- Horizon: 16 quarterly steps (4 years).

| Scenario | Data pickle | Macro series |
|----------|-------------|--------------|
| **OLD** | `scenarios/MacroABM Reference/data_provincial_model.pkl` | National Canada, replicated identically to every province |
| **NEW** | `data_provincial_model_NEW.pkl` (rebuilt with the override) | Province-specific StatsCan series |

Both pickles are structurally identical apart from the four series (GDP and compensation
levels match to ~1e-16).

## Headline result — cross-province dispersion

Mean coefficient of variation across the ten provinces, averaged over the run:

| Variable | OLD | NEW | NEW / OLD |
|----------|-----|-----|-----------|
| **Unemployment rate** | 0.113 | 0.325 | **2.89×** |
| CPI | 0.059 | 0.043 | 0.73× |
| Real GDP (levels) | 1.12 | 1.15 | 1.03× |
| Nominal GDP (levels) | 1.09 | 1.19 | 1.09× |
| Consumption (levels) | 1.10 | 1.18 | 1.07× |

> The GDP / consumption CVs are dominated by province **size** (Ontario vs PEI), so they are
> not the cleanest dispersion signal. The rate variables (unemployment, CPI) are
> size-independent and meaningful. Unemployment dispersion **nearly triples**, and — more
> importantly — it is now *correctly structured* rather than noise-driven (below).

## Unemployment — structure, not just spread

![Provincial unemployment](provincial_comparison_plots/unemployment.png)

- **OLD (left):** every province starts at the same ~6.9% national rate and then fans out
  **randomly** as model noise accumulates. By the end, Manitoba and Alberta reach 14–18%,
  which has no basis in their actual (tight) labour markets. The ordering is an artefact.
- **NEW (right):** provinces start at their **true 2014 rates** and hold a realistic,
  persistent ranking throughout: Atlantic provinces (NL, PE, NS, NB) stay high, the West
  (SK, AB, MB, BC) stays low. This is the provincial labour-market heterogeneity the model
  is supposed to represent.

Unemployment level, first (t0) and last (tN) step:

| Prov | OLD t0 | OLD tN | NEW t0 | NEW tN |
|------|-------:|-------:|-------:|-------:|
| AB | 0.069 | 0.142 | **0.048** | 0.062 |
| BC | 0.069 | 0.115 | 0.065 | 0.080 |
| MB | 0.069 | 0.178 | 0.055 | 0.057 |
| NB | 0.072 | 0.101 | 0.101 | 0.126 |
| NL | 0.070 | 0.116 | **0.122** | 0.159 |
| NS | 0.069 | 0.110 | 0.092 | 0.118 |
| ON | 0.069 | 0.110 | 0.076 | 0.080 |
| PE | 0.075 | 0.094 | **0.132** | 0.132 |
| QC | 0.069 | 0.158 | 0.081 | 0.097 |
| SK | 0.070 | 0.103 | **0.044** | 0.074 |

Note how OLD `t0` is essentially flat (~0.069–0.075, the national value), while NEW `t0`
spans 4.4% (SK) to 13.2% (PE) — the real 2014 provincial spread.

## Real GDP — different growth ordering

![Provincial real GDP](provincial_comparison_plots/real_gdp.png)

Real GDP index (t0 = 100), final value:

| Prov | OLD | NEW |  | Prov | OLD | NEW |
|------|----:|----:|--|------|----:|----:|
| AB | 99.3 | 93.9 | | NS | 96.6 | 84.2 |
| BC | 97.8 | 92.4 | | ON | 94.6 | 101.5 |
| MB | 92.1 | 95.5 | | PE | 101.2 | 107.7 |
| NB | 100.8 | 83.9 | | QC | 85.8 | 93.7 |
| NL | 99.8 | 97.9 | | SK | 94.4 | 88.4 |

The provincial growth ranking reorders materially. Under OLD, Quebec alone collapses (an
artefact of identical starting conditions plus noise); under NEW, Ontario and PEI lead while
several Atlantic provinces and Saskatchewan contract more — trajectories now shaped by each
province's own inflation, labour-market slack and house-price path.

![Provincial nominal GDP](provincial_comparison_plots/nominal_gdp.png)
![Provincial CPI](provincial_comparison_plots/cpi.png)

## Interpretation

1. The upgrade delivers what it was meant to: **province-specific macro dynamics** rather
   than a single national path stamped onto ten provinces.
2. The largest, cleanest effect is on the **labour market** — unemployment now reflects real
   provincial conditions from the first step and stays economically ordered, instead of
   diverging only through simulation noise.
3. Growth and consumption trajectories shift as a consequence, so downstream provincial
   results (and any CIMS-linkage feedback that depends on provincial output) change in a
   defensible, data-grounded way.

## Caveats

- Short horizon (16 quarters) with a single seed — this is a **directional** demonstration
  of the data effect, not a calibrated policy run. Confirm with longer horizons and multiple
  seeds before drawing quantitative conclusions.
- Only item #1 of the upgrade list is applied; firm-size, firm-financial, sectoral-growth and
  household-income inputs are still national/proxy, so some remaining cross-province similarity
  is expected.
- CPI dispersion is slightly *lower* under NEW: real provincial CPI inflation is more
  homogeneous than the model's endogenous CPI was — plausible, since Canadian provincial
  inflation is fairly synchronized.

---

# Items #2–5: impact assessment

Before collecting any data, each item was traced through the **active** provincial build
path (single firm per industry, `"Default"` firm constructor, `create_all_exogenous_data`
disabled). Unlike #1, most of #2–#5 turn out to be either not consumed, inert under the
current configuration, or already sourced from Canadian data. Evidence and verdicts:

## #2 Sectoral output growth (Eurostat `perc_growth_sector`, France) — NO IMPACT (dead path)

- `get_perc_sectoral_growth` is called only inside `DataReaders.get_exogenous_data`
  (`default_readers.py:574`).
- The active pipeline builds exogenous data via `ExogenousCountryData.from_data_readers`;
  the alternative `create_all_exogenous_data` is commented out (`data_wrapper.py:248`).
- The one live consumer of `get_exogenous_data` is the central government
  (`default_synthetic_central_government.py:128`), which uses only `log_inflation` and
  `unemployment_rate` (via `get_benefits_inflation_data`) — never `sectoral_growth`.
- **Verdict:** provincializing sectoral growth changes nothing until the model is re-wired
  to consume it. Not integrated.

## #3 Firm size distribution (ONS UK zeta) — INERT in current config

- Firm-size zetas distribute employees across firms in `firm_tools`, driven by
  `Number of Firms` per industry.
- Under `single_firm_per_industry=True` (the run's setting), `Number of Firms = 1` for
  every industry (`industry_extraction.py:143`), so there is nothing to distribute.
- **Verdict:** zero impact while single-firm. A genuine data-quality issue (UK firm sizes
  used for Canada) only in **multi-firm** runs. Canadian Business Counts (33-10-1014,
  available by province) is the correct replacement and can be wired for that case.

## #4 Firm deposits & debt — ALREADY Canadian (national)

- The `"Default"` firm constructor sets total firm deposits and debt from
  `eurostat.get_total_nonfin_firm_deposits/debt(country_name)` with `country_name = CAN`
  (`default_synthetic_firms.py:202-205`).
- Eurostat's `nasa_10_f_bs.csv` is the **OECD-extended** financial-accounts file and
  **contains Canada** (`geo = CA`, alongside US, JP, MX, KR, …). For 2014 it returns
  Canadian non-financial-corporate loans ≈ 1.35 trillion CAD and deposits ≈ 0.66 trillion
  CAD (national-currency units).
- **Verdict:** firm balance-sheet aggregates are already Canadian national data, delivered
  through the Eurostat reader — not a French proxy. Provincial firm balance sheets are not
  publicly available, so no provincial upgrade is possible; a newer StatsCan QSFS
  (33-10-0225) vintage would be only a marginal refresh.

## #5 Household income & saving — mostly already Canadian; one French residue

- **Saving rates:** fitted by regression on the Canadian provincial HFCS micro-data
  (`New_Household_provincial.csv`) in `hfcs_synthetic_population.set_household_saving_rates`
  — already Canadian and provincial.
- **Disposable income / balance sheets:** from the same Canadian HFCS micro-data.
- The remaining foreign proxy is the **consumption-weights-by-income-quantile** matrix
  (`get_household_consumption_by_income_quantile`), which logs *"Overwriting Consumption
  Weights by Income with French Data"* (`oecd_economic_data.py:1034`). It controls how each
  income group splits spending across sectors.
- **Verdict:** the only live foreign proxy in #5 is the consumption-weights matrix
  (replaceable with the Canadian Survey of Household Spending, national by income quintile;
  a provincial × quintile × sector version is thin). Modest impact on demand composition.

## Summary

| Item | Live in current config? | Source today | Upgrade available | Impact if applied |
|------|------------------------|--------------|-------------------|-------------------|
| #2 Sectoral growth | **No** (dead path) | Eurostat FR (unused) | — | None until re-wired |
| #3 Firm size | **No** (single-firm) | ONS UK | Business Counts (prov.) | None single-firm; matters multi-firm |
| #4 Firm deposits/debt | Yes | Eurostat **CA** (already Canadian) | StatsCan QSFS (marginal) | Negligible (already CA) |
| #5 Consumption weights by income | Yes | **French** | SHS national (prov. thin) | Modest (demand mix) |

This is a materially different picture from the source-provenance audit, which ranked these
items assuming they were live foreign proxies. Tracing the *active single-firm pipeline*
shows #2 is unused, #3 is inert, #4 is already Canadian, and only #5's consumption-weights
matrix is a live foreign proxy with (modest) impact. The single highest-value **live**
foreign proxy touching the provincial run is actually item **#6 (investment / GFCF split &
imputed rent, Eurostat France)** from the priority table, which was outside this batch.
