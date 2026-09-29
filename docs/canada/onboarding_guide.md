# MacroABM-CA onboarding guide

This guide is for someone joining the Canadian model team: where things are in the
repository, how raw data becomes a model, what the model is made of, and how the team
works with the upstream INET repository. For the configuration used in the *Powering
Canada's Growth* analysis start from the [Canada overview](index.md); for the data build
see [Data build](data_build.md); for the inputs see the
[raw data reference](raw_data_reference.md).

## 1. What MacroABM-CA is

MacroABM-CA is the Canadian, provincial adaptation of the shared MacroABM framework
developed at INET Oxford and Macrocosm. The framework is an agent-based macroeconomic
model in which firms by industry, households and individuals, banks, a central bank and
governments interact through goods, labour, credit and housing markets, with an explicit
rest of the world. The Canadian adaptation replaces the national OECD input-output base
with a provincial one, adds Canadian data readers (households, labour, capital,
provincial series, taxes, investment splits), Canadian policy instruments (the consumer
carbon price and the output-based pricing system) and the hooks through which the energy
models of the M3 linkages drive the economy.

The ten provinces are modelled explicitly; the territories are aggregated into the rest
of the world at the input-output level. Each province is a `SyntheticCountry` at build
time and a runtime `Country` inside the simulation, and the provinces trade with each
other and with the rest of the world through the shared goods market.

## 2. Main repository areas

### `macro_data/`

Turns raw datasets into the model-ready `DataWrapper` object: raw-data readers, IO table
loading and transformation, socio-economic matching, synthetic firms, households, banks
and government entities, trade proportions and exogenous data, and the pickled data
object the simulation starts from. Entry point:
[`macro_data/data_wrapper.py`](../../macro_data/data_wrapper.py). Further documentation:
the [macro data overview](../macro_data/index.md) and the
[reader API](../macro_data/api/readers/index.md).

Canada-specific readers: `macro_data/readers/economic_data/provincial_*_reader.py`,
`macro_data/readers/population_data/canadianized_household_adapter.py`,
`macro_data/readers/policy_data/obps_can_reader.py`, the `can_2022` injection in
`macro_data/readers/default_readers.py`, and the OECD-50 handling in
`macro_data/readers/emissions/emissions_reader.py`.

### `macromodel/`

The dynamic simulation engine: countries and provincial economies, the agents, the
markets, the time stepping and the HDF5 writers. Entry point:
[`macromodel/simulation.py`](../../macromodel/simulation.py). Further documentation: the
[macromodel overview](../macromodel/index.md) and the [API pages](../macromodel/api/index.md).

Canada-specific code: the growth baseline preset
(`macromodel/configurations/growth_baseline_preset.py`), the exogenous labour-force path
(`macromodel/agents/individuals/func/demography.py`), the linkage hooks on firms,
households, the rest of the world and the goods-market clearing, the national inflation
expectation and rest-of-world absorption in `simulation.py`, and the OBPS in
`macromodel/policy/output_based_price_system_can.py`.

### `scenarios/`

Run scripts. `run_cims_linkage.py` holds the helpers that the M3-linkages driver imports
(simulation construction, the linkage prehook, checkpoints, the shallow export, GDP
growth); `run_canada_provincial.py` holds the province list, the simulation configuration
builder and the pickle loader. Keep new run scripts here (section 6).

### `dev/`

Git-ignored working area: `dev/pkl_files/` holds the pickles, `dev/raw_data_10prov/` the
ten-province input overlay, and `dev/io2022/` the scripts that build the 2022 pickle
(committed) together with their household-preparation tooling.

### `scripts/`

`build_labour_force_index.py` builds the bundled observed labour-force index
(`scripts/data/labour_force_index_2014_2024.json`) that the growth baseline preset
reads.

### External raw data

Raw data is never committed. Users provide a raw-data root and pass it as
`raw_data_path` to `DataWrapper.from_config(...)`; the [raw data reference](raw_data_reference.md)
describes it. Generated artifacts (pickles, HDF5 outputs, CSV summaries) are local run
products and stay outside version control.

## 3. Where raw data enters the model

Raw data enters through `DataWrapper.from_config(...)`; the run script only sees the
processed pickle.

**Step 1, `DataWrapper.from_config`** ([`macro_data/data_wrapper.py`](../../macro_data/data_wrapper.py)).
The provincial path is taken when the configuration contains Canada as an aggregated
country with provinces:

```python
if configuration.aggregation_structure:
    regions_dict = configuration.aggregation_structure
    if Country("CAN") in configuration.countries and configuration.is_aggregated(Country("CAN")):
        use_provincial_can_reader = True
```

`DataReaders.from_raw_data(...)` is then called with `use_provincial_can_reader=True`,
the region dictionary, and, for the production build, the path of the Canadian household
file (`canadianized_can_households_csv`).

**Step 2, `DataReaders.from_raw_data`** ([`macro_data/readers/default_readers.py`](../../macro_data/readers/default_readers.py))
loads the provincial IO table, the 2022 Statistics Canada industry inputs, the WIOD
scaffold, exchange rates, the provincial series, taxes and investment splits, the policy
and emissions data, and the household and population data. The provincial table is read
in the `use_provincial_can_reader` branch:

```python
provincial_table = {2014: "icio_2014_can_provinces.csv", 2022: "icio_2022_can_provinces.csv"}[year]
df = pd.read_csv(raw_data_path / "icio" / provincial_table, header=[0, 1], index_col=[0, 1])
```

The 2022 table is CAD-native: `from_usd_to_lcu_io` returns 1.0 for it, so no currency
conversion is applied to the IO or socio-economic level data. Monetary variables are
stored in both a "USD" and an "LCU" field for compatibility with the framework; on the
2022 path the two are equal and both are CAD.

## 4. How the model object is built

```text
Raw data
  -> DataReaders
  -> industry vectors and matrices
  -> SyntheticCountry objects (one per province)
  -> DataWrapper pickle
  -> Simulation.from_datawrapper(...)
  -> runtime Country objects
```

The pickle stores the initialised model state, not raw tables: firms, households, banks,
the central bank, governments, the markets, trade proportions, exogenous time series and
emission factors. The [data build](data_build.md) page lists the exact commands used for
the production pickle.

## 5. Key model components

**Firms.** One representative firm per industry and province
(`single_firm_per_industry = True`), carrying output, intermediate inputs, labour
compensation, capital input structures, inventories, deposits, debt and equity, taxes,
and the productivity and technical-coefficient functions. The linkage hooks (intensity
targets, quantity anchors, capacity floor and ceiling, production gate and floor, the
capital-intensity uplift for fuel switching) are methods of the firm agent. Code:
`macro_data/processing/synthetic_firms/`, `macromodel/agents/firms/`.

**Households and individuals.** Households carry income, consumption, deposits, debt,
housing balance-sheet variables, consumption weights and investment behaviour; the
household energy-share and quantity anchors of the linkage act here. Individuals carry
the labour-market status that the exogenous labour-force path moves. Code:
`macro_data/processing/synthetic_population/`, `macromodel/agents/households/`,
`macromodel/agents/individuals/`.

**Banks and credit.** One bank per province (`single_bank = True`) intermediating the
credit market. Code: `macro_data/processing/synthetic_banks/`, `macromodel/agents/banks/`,
`macromodel/markets/credit_market/`.

**Governments.** One government entity per province (`single_government_entity = True`)
that consumes goods, collects and pays taxes, and carries the carbon-pricing instruments
and the transfer and grant programs the linkage applies. Code:
`macro_data/processing/synthetic_government_entities/`,
`macromodel/agents/government_entities/`, `macromodel/policy/`.

**Markets.** Goods (including interprovincial and rest-of-world trade, the export pins
and the rest-of-world electricity split), labour, credit and housing. Code:
`macromodel/markets/`.

**Rest of the world.** A single external agent with frozen base-year industry shares of
its import demand; the export-demand indices of the linkage move it. Code:
`macromodel/rest_of_the_world/`.

## 6. Team workflow: scenarios and upstream sync

### Keep run scripts in `scenarios/`

All run scripts live in `scenarios/`, with descriptive names that make the geography,
policy or assumption and horizon obvious (`run_canada_provincial.py`,
`scenario_carbon_price_ramp_2025_2030.py`, not `run.py` or `new_scenario_v2.py`). When
adapting an existing scenario, copy and rename the closest script rather than editing a
shared baseline in place. Analysis-only post-processing can live in a separate project
repository.

### Pulling changes from the upstream INET repository

MacroABM-CA is built on top of the shared framework whose source of truth is
[inet-complexity/macro-main](https://github.com/inet-complexity/macro-main). When INET
releases new features or fixes, pull them while preserving the Canada-only additions.

Canada-only folders to preserve:

| Folder | Purpose |
|---|---|
| `docs/canada/` | Canada documentation (these pages) |
| `scenarios/` | run scripts and helpers |
| `dev/io2022/`, `scripts/` | the 2022 data build and the labour-force index builder |

Shared framework code (`macro_data/`, `macromodel/`, `macrocalib/`, `tests/`, project
files) carries Canadian changes too (readers, linkage hooks, policy instruments), so
merges there need care. The preferred sequence: identify the Canadian changes that touch
shared packages; upstream what is reusable first; then fetch and merge upstream; resolve
conflicts in shared code, keeping the Canada-only folders intact; rebuild or reuse a
provincial pickle and run the test suite before pushing.

```bash
git remote add upstream https://github.com/inet-complexity/macro-main.git   # once
git fetch upstream
git merge upstream/main          # or: git rebase upstream/main
uv sync                          # after reconciling pyproject.toml / uv.lock
uv run pytest tests -q
```

If you are unsure whether a conflict hunk is Canada-specific or shared framework code,
check whether the same file exists upstream and whether the Canadian change has already
been merged there.
