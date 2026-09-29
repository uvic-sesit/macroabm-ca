# Data build: the 2022 provincial population pickle

The model runs from a pickled `DataWrapper` that holds the initialised state of the ten
provincial economies. The pickle used for *Powering Canada's Growth* is
`dev/pkl_files/io2022_10prov_2022_v2_pumf_built-2026-08-18.pkl` (about 20 MB). It is not
committed (`dev/` is git-ignored); a copy sits on the SESIT shared drive next to the
raw-data root. This page records how it was built so that the build can be repeated on a
new data vintage. Rebuilds are not bit-identical to the pinned file, because the synthetic
population is sampled at random; to reproduce the published numbers, use the pinned pickle.

## 1. Inputs

Everything the build reads sits under one raw-data root (the shared *SESIT - MacroABM
data/raw_data* folder, or a local copy). The [raw data reference](raw_data_reference.md)
lists every file; the parts specific to the 2022 build are:

| Input | Location under the root | Origin |
|---|---|---|
| 2022 provincial input-output table, 13 regions x OECD-50 | `icio/icio_2022_can_provinces.csv` | the `macroabm-io2022` pipeline (Statistics Canada 2022 supply-use tables) |
| 2022 capital stock, capital compensation, employment shares and compensation of employees by province and industry | `can_2022/*.csv` | Statistics Canada 36-10-0096, the 2022 IO value-added breakdown, 36-10-0489 |
| Public-use microdata for households | `can_2022/pumf/{sfs_2023,cis_2022,shs_2023}/` | Statistics Canada PUMFs, downloaded manually ([instructions](../../dev/io2022/household_prototype/PUMF_DOWNLOAD_INSTRUCTIONS.md)) |
| 2022 household controls | `can_2022/controls/` and the committed `dev/io2022/household_prototype/controls_2022.json` | Statistics Canada tables, fetched by `download_controls.py` and reduced by `extract_controls.py` |
| Provincial series and rates | `canadian_inputs/*.csv` and the Statistics Canada labour-share extract | Statistics Canada |
| Shared inputs of the framework (HFCS 2021 skeleton, WIOD SEA scaffold, OECD, exchange rates, Eurostat, World Bank, emission factors, policy tables) | `hfcs/`, `wiod_sea/`, `oecd_econ/`, ... | as for the national model |

The build scripts resolve the root through `dev/io2022/household_prototype/_paths.py`:
the `MACROABM_RAW_DATA` environment variable, else `<repo>/raw_data/`, else
`<repo>/dev/raw_data/`. Set `MACROABM_RAW_DATA` to the shared-drive root.

## 2. Fold the territories

The production workflow is a ten-province structure end to end, so the three territories
are aggregated into the rest of the world at the input-output level:

```bash
uv run python dev/io2022/fold_territories_2022.py --input <root>/icio/icio_2022_can_provinces.csv
```

The script writes `icio_2022_can_provinces_10prov.csv` next to the input. The 10-province
builder reads its inputs from the local overlay `dev/raw_data_10prov/`, whose `icio/`
folder holds that folded table under the standard filename
`icio_2022_can_provinces.csv`; every other folder of the overlay is a link to the shared
root, so no derived file is written back to the shared drive.

Folding is a pure aggregation: every accounting identity is preserved, and
territory-province trade becomes external trade, which is how the CER linkage treats the
territories in every channel.

## 3. Prepare the Canadian households

Two scripts turn the public-use microdata into the household file the builder samples
from. Both need the PUMFs in place and the controls JSON:

```bash
uv run python dev/io2022/household_prototype/prepare_household_canadianization.py --real
uv run python dev/io2022/household_prototype/prepare_household_consumption.py --real
```

The first transplants SFS 2023 balance-sheet and income vectors onto the HFCS 2021
household skeleton (joint donor matching, backcast to 2022 and calibrated to the 2022
distributions of household economic accounts and national balance sheet controls, with
CIS 2022 income composition and the Canadian Housing Survey tenure control). The second
adds SHS 2023 consumption shares, calibrated to 2022 household final consumption. The
output that the builder reads is
`dev/io2022/household_prototype/prototype_household_consumption.csv`.

## 4. Build the pickle

```bash
uv run python dev/io2022/build_2022_datawrapper_10prov.py --force \
    --canadianized-households --lfs-unemployment \
    --pickle dev/pkl_files/io2022_10prov_2022_v2_pumf_built-<date>.pkl
```

* `--canadianized-households` makes every province sample the Canadian household file
  instead of the framework's proxy households.
* `--lfs-unemployment` runs `dev/io2022/lfs_unemployment_2022.py` after the build: it
  reclassifies a seeded random surplus of unemployed individuals as not economically
  active until each province's initial unemployment rate matches its 2022 Labour Force
  Survey annual mean (from `canadian_inputs/provincial_macro_series.csv`). Employment,
  firm matching, output and wealth are untouched, so the participation rate sits below
  the observed one by construction.

The build takes a few minutes. It also bakes in the observed 2022 compensation of
employees, employment shares and capital data from `can_2022/`, the provincial series
from `canadian_inputs/`, the labour-share calibration, the emissions factors on the
OECD-50 scheme and the OBPS policy data. The one production-time switch that is not in
the pickle is the growth baseline preset, which the run configuration applies.

## 5. Pin it

Record the pickle's path in the scenario configuration (`pkl_path` under
`[Models.MacroABM.Config]` in M3-linkages) and copy it to the shared drive. The
M3-linkages driver refuses a pickle whose base year differs from the simulation start
year, and it refuses to run without an explicit `pkl_path`, so a run can never silently
build a different population.

## 6. Regenerating the compensation input

`can_2022/compensation_of_employees_oecd50_by_province_CADmillions.csv` ships in the
raw-data bundle. `dev/io2022/prepare_compensation_input.py` regenerates it from the
canonical value-added breakdown of the (private) `macroabm-io2022` pipeline when that
pipeline changes.
