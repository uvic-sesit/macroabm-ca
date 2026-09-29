# Raw data reference

Every input the 2022 provincial build of MacroABM-CA reads, where it sits under the
raw-data root, where it comes from, and how it is used. The root is the shared
*SESIT - MacroABM data/raw_data* folder (or a local copy); nothing under it is committed.
The [data build](data_build.md) page gives the build recipe.

```text
raw_data/
├── icio/                      2022 provincial IO table (+ global ICIO scaffold files)
├── can_2022/                  2022 Statistics Canada industry inputs, PUMFs, controls
├── canadian_inputs/           provincial time series, tax rates, investment splits
├── 3610000101_customizedLayoutData - <year> - processed.csv   labour-share extract
├── hfcs/                      HFCS survey waves (household and individual skeleton)
├── wiod_sea/                  WIOD socio-economic accounts (scaffold only for 2022)
├── oecd_econ/                 OECD economic series and the ISIC mappings
├── exchange_rates/, eurostat/, world_bank/, imf/, ...   framework economic readers
├── emission_factors/          emission intensities by carrier and industry
└── policy/                    carbon-pricing schedules and OBPS parameters
```

## 1. `icio/`

### `icio_2022_can_provinces.csv`

The 2022 inter-industry and inter-provincial transaction table for Canada, produced by
the `macroabm-io2022` pipeline from Statistics Canada's 2022 supply-use tables. Rows and
columns are labelled `(region, industry)` with regions `CAN_AB` ... `CAN_SK`, the three
territories and `ROW`, and industries in the OECD 50-sector scheme (`A01` ... `T`; coal
is `B05`, oil and gas together are `B06`). Final-demand columns carry household,
government and fixed capital formation, with changes in inventories and valuables folded
into fixed capital formation at load time. Values are CAD millions, read as CAD-native
(no exchange-rate conversion is applied to the IO or socio-economic level data on the
2022 path).

For the production build the territories are folded into `ROW`
(`dev/io2022/fold_territories_2022.py`) and the folded table is placed under this same
filename in the `dev/raw_data_10prov/icio/` overlay.

Loaded on the `use_provincial_can_reader` path of `DataReaders.from_raw_data`
(`macro_data/readers/default_readers.py`). It replaces the OECD ICIO table as the
calibration matrix for every province: production, intermediate structure, capital
composition (taken from the pre-fold fixed capital formation block), trade proportions
and household consumption weights are all initialised from it.

### `<year>_SML.csv`, `<year>_SML_P.csv`

The global OECD ICIO files. On the provincial path they are used only as a scaffold for
Canada's imputed rent and total output; if the 2022 files are absent, the nearest
earlier year is used with a warning. All economics come from the provincial table.

## 2. `can_2022/`

| File | Contents | Source | Use |
|---|---|---|---|
| `capital_stock_end2021_oecd50_by_province_CADmillions.csv` | opening net capital stock by province and industry | Statistics Canada 36-10-0096 | replaces the WIOD capital-stock scaffold |
| `capital_compensation_oecd50_by_province_CADmillions.csv` | gross operating surplus, mixed income and net production taxes | 2022 IO value-added breakdown | investment allocation and depreciation |
| `employment_shares_oecd50_by_province.csv` | employment shares by province and industry | Statistics Canada 36-10-0489 | province-by-industry headcount of the synthetic population |
| `compensation_of_employees_oecd50_by_province_CADmillions.csv` | wages and salaries plus employers' social contributions | 2022 IO value-added breakdown (`prepare_compensation_input.py`) | the firm wage bill and the per-province employer contribution ratio (`tau_sif`) |
| `pumf/sfs_2023/`, `pumf/cis_2022/`, `pumf/shs_2023/` | Survey of Financial Security 2023, Canadian Income Survey 2022 and Survey of Household Spending 2023 public-use microdata | Statistics Canada 13M0006X, 72M0003X, 62M0004X (manual download) | the household economic block, through the preparation scripts |
| `controls/` | 2022 distributional and aggregate controls (36-10-0660, 36-10-0587, 36-10-0580, 38-10-0238, 46-10-0083, price indices, household counts) | Statistics Canada tables, fetched by `download_controls.py` | calibration targets for the household preparation; reduced to the committed `controls_2022.json` |

The `can_2022` industry files are loaded by `_inject_can_2022_socioeconomic` in
`default_readers.py`; any province missing from a file keeps the WIOD scaffold, with a
warning.

## 3. `canadian_inputs/` and the labour-share extract

| File | Reader | Contents | Use |
|---|---|---|---|
| `provincial_macro_series.csv` | `ProvincialMacroReader` | quarterly CPI inflation, unemployment rate, house-price growth and vacancy rate by province | replaces the national series the international readers would return for every province; also the 2022 unemployment targets of the LFS calibration |
| `provincial_tax_rates.csv` | `ProvincialTaxReader` | effective corporate, personal income and sales tax rates by province and year (Provincial and Territorial Economic Accounts) | province-specific tax rates (the model applies flat effective rates) |
| `provincial_investment_fractions.csv` | `ProvincialInvestmentReader` | split of gross fixed capital formation across firms, households and government by province | replaces the Eurostat split, which has no Canadian row |
| `3610000101_customizedLayoutData - <year> - processed.csv` (at the root) | `ProvincialLabourReader` | Statistics Canada supply-use value-added components | the observed aggregate labour share the wage bill is calibrated onto (a share outside 35 to 70 % is refused) |

Each reader is a no-op when its file is absent, so national or non-Canadian builds are
unaffected.

## 4. `hfcs/`

The Household Finance and Consumption Survey waves (`2010/`, `2014/`, `2017/`, `2021/`)
provide the household and individual skeleton of the synthetic population. On the 2022
provincial build the household economic block is replaced by the Canadian file produced
from the PUMFs (`canadianized_can_households_csv`, see [data build](data_build.md)); the
individual-level demographics attached to each household keep the HFCS 2021 skeleton.

## 5. `wiod_sea/`, `oecd_econ/`, `exchange_rates/`, `eurostat/`, `world_bank/`

The framework's socio-economic and macroeconomic readers. On the 2022 provincial path
the WIOD socio-economic accounts (which end in 2014) are only a scaffold that the
`can_2022` files and the provincial IO table overwrite; `oecd_econ/mappings.json` maps
ISIC sections to industry codes; the exchange-rate, Eurostat and World Bank readers
supply the international series the model needs for the rest of the world and for any
province-level series that has no Canadian override.

## 6. `emission_factors/`

Emission intensities per unit purchased, by carrier and buying industry:

* `emitting_fraction_CO2.csv`: rows are the fossil carriers (coal, gas, oil, refined
  products), columns the industries; used for firms' input and capital emissions each
  quarter.
* `emitting_fraction_CH4.csv`: one row (`CH4`) over the industries.
* `emitting_fraction_consumption.csv`, `emitting_fraction_investment.csv`: the fraction
  of households' consumption and investment of each good that generates direct
  emissions.

The files are written on the legacy coal / gas / oil carrier split. On the OECD-50
scheme the reader (`macro_data/readers/emissions/emissions_reader.py`) blends the gas
and oil factors into one value-weighted factor for the merged oil-and-gas industry
`B06`, and emissions tracking is switched on whenever the scheme's carriers are present
(`macro_data/data_wrapper.py`).

`EN-GHG_EconSectByGas-CA_Emissions_2014_2023_v4.csv` (Environment and Climate Change
Canada's inventory by economic sector) is kept for validation and is not loaded by the
simulation; `emitting_fraction_CO2 - original.csv` and `emitting_fraction_v2.csv` are
earlier calibrations that are not selected.

## 7. `policy/`

| File | Reader | Contents | Use |
|---|---|---|---|
| `consumer_carbon_price_rates.csv` | `ConsumerCarbonCANReader` | annual consumer fuel-charge rates by jurisdiction, 2014 to 2050 (the federal charge ends in 2025) | the consumer carbon price when `use_consumer_carbon_reg` is on (off in the Powering Canada's Growth runs: CER's end-use prices already carry it) |
| `output_based_price_system_rates.csv` | `OBPSCANReader` | annual industrial carbon price by jurisdiction, rising to $170/t | the price `P` in the OBPS cost `(emissions - limit) x P` |
| `output_based_price_system_policy_values_disagg.csv` | `OBPSCANReader` | per-industry baseline intensity, tightening rate and reduction factor | the OBPS allowance per industry; written in the legacy industry codes, so OECD-50 codes fall back to their closest legacy row (`B06` uses the oil row, oil dominating the merged industry's output value) |
| `output_based_price_system_policy_values_elec.csv` | `OBPSCANReader` | year-by-year electricity benchmark | the electricity-sector allowance |
| `output_based_price_system_policy_values.csv`, `energy_bundle_price.csv`, `*.xlsx` | not read on the production path | aggregate OBPS values, a quarterly exogenous energy-price index, and the source spreadsheets | kept for provenance |

In the Powering Canada's Growth runs the OBPS parameters are further overlaid at run
time by the M3-linkages policy tables (provincial stringency, the Quebec WCI price,
tightening extended to 2050 under Net-zero).

## 8. `cims_prices/firm_prices.csv`

An exogenous industry-price series read by `SectorExoPricesReader` when present. The
production runs pin energy prices to CER's own paths through the linkage instead, so
this file is not used by them.
