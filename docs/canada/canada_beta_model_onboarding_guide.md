# MacroABM-CA: getting started

This guide gets you from nothing to running the Canadian provincial model, defining your
own scenarios and reading the results. The hands-on part is the notebook
`MacroABM-CA_quickstart.ipynb` at the repository root; this page explains what it does
and what to know around it.

MacroABM-CA is a research model under active development. Treat its results as model
evidence to be checked, not as forecasts.

## 1. What the model is

MacroABM-CA is an agent-based macroeconomic model of Canada's ten provinces. Each
province is an economy of its own, linked to the others and to a rest-of-the-world block
through trade:

- **Firms:** one per industry and province, 50 industries (the OECD input-output
  classification: `A01` agriculture, `B06` oil and gas, `D` electricity, `F` construction,
  `L` real estate, ...). Firms set prices, hire, buy intermediate inputs and capital, and
  produce with fixed input recipes taken from the 2022 input-output tables.
- **Households:** a sample of a few thousand households per province, built from Statistics
  Canada surveys (income, wealth, housing tenure, consumption patterns). They work, earn,
  pay taxes, consume, and buy or rent housing.
- **Banks, governments and a central bank:** one bank and one government buyer per
  province; a central government collecting taxes and paying transfers; a central bank
  setting the policy rate.
- **Markets:** goods (including trade between provinces and with the rest of the world),
  labour, credit and housing.

The model starts from the economy of 2022Q1 and steps forward one quarter at a time. Nothing
is solved for an equilibrium: each quarter, agents decide from what they see, markets match
buyers and sellers, and the outcome is next quarter's starting point. Aggregates (GDP,
unemployment, prices) are the sum of what the agents did.

Some paths are set from outside rather than by the agents:

- the labour force of each province (observed to 2024, then a fixed annual growth rate);
- the growth of household and government demand (tied to the labour force);
- the rest of the world's demand and prices.

Energy use, electricity supply, carbon pricing and clean-technology investment come from
the CIMS-COPPER linkage (section 7), not from the model on its own.

## 2. What is where

| Folder | Contents |
|---|---|
| `macro_data/` | Turns raw data into the model's starting point (the pickle, section 3.3). Only needed to rebuild that file. |
| `macromodel/` | The simulation: `agents/` (firms, households, banks, governments), `markets/`, `configurations/` (settings and their defaults). |
| `scenarios/` | Run scripts. `macro_only.py` runs the model on its own (the notebook uses it); `run_cims_linkage.py` builds the simulation, for the notebook and for the linkage. |
| `MacroABM-CA_quickstart.ipynb` | The hands-on notebook. |
| `dev/` | Local working files, mostly ignored by git: the pickle goes in `dev/pkl_files/`. `dev/io2022/` holds the scripts that build the pickle. |
| `tests/` | Automated tests (`uv run pytest tests/`). |

## 3. Setup

### 3.1 What you need

- **Git**, and access to the GitHub repository `uvic-sesit/macroabm-ca`.
- **uv**, the Python package manager the project uses
  ([install instructions](https://docs.astral.sh/uv/getting-started/installation/);
  on Windows: `winget install astral-sh.uv`). uv installs the right Python (3.12) itself.
- **Access to the SESIT SharePoint** folder `Projects - Shared/SESIT - MacroABM data`.
- About 3 GB of free disk space (mostly Python packages) and 8 GB of memory (a run to
  2030 uses about 4 GB).

### 3.2 Get the code and install

```console
git clone https://github.com/uvic-sesit/macroabm-ca.git
cd macroabm-ca
git checkout epm
uv sync
```

`epm` is the branch the current project runs use. `uv sync` creates a `.venv` folder with
every package at its tested version; the first time takes a few minutes.

### 3.3 Get the starting data (the pickle)

The model starts from one file, the pickle: the 2022 input-output tables and the firms,
households, banks and governments of every province, already built. It is not in the
repository. Copy

```
io2022_10prov_2022_v2_pumf_built-2026-08-18.pkl   (20 MB)
```

from the SharePoint folder above into `dev/pkl_files/` in your clone (create the folder).
Everyone uses this same file, so results compare across machines. It can be rebuilt from
raw data (see `docs/cims_copper_macro_labour/setup.md` in M3-linkages), but you don't need
to, and a rebuild is not identical because households are sampled at random.

### 3.4 Check it works

```console
uv run python -c "from scenarios.macro_only import load_data; print(load_data('dev/pkl_files/io2022_10prov_2022_v2_pumf_built-2026-08-18.pkl').all_country_names)"
```

After about a minute this prints the ten provinces (`CAN_AB` ... `CAN_SK`) and `ROW`.

## 4. Run the model

Open the notebook:

```console
uv run --with jupyterlab python -m jupyterlab MacroABM-CA_quickstart.ipynb
```

`--with jupyterlab` adds Jupyter for this command only (`python -m` avoids launcher
programs that managed Windows machines sometimes block). In VS Code you can instead open the
notebook and choose `.venv` as the kernel. If uv stops with "failed to hardlink file"
(common when folders sit on OneDrive or a network drive), set `UV_LINK_MODE=copy` and
rerun (PowerShell: `$env:UV_LINK_MODE="copy"`; bash: `export UV_LINK_MODE=copy`). Run the cells from the top: the notebook runs
the baseline from 2022 to 2030 (about 3 minutes, after a minute of loading), shows the
results, then runs one scenario and compares it with the baseline.

The same in a script:

```python
from scenarios.macro_only import load_data, build, run, results, annual

data = load_data("dev/pkl_files/io2022_10prov_2022_v2_pumf_built-2026-08-18.pkl")
sim = build(data, end_year=2030)
run(sim)
df = results(sim)
print(annual(df, ["Real GDP", "Unemployment Rate"], national=True))
```

**What "the baseline" is.** `BASELINE` in `scenarios/macro_only.py` copies the macro
settings of the linkage's EPM baseline: labour force growth by province, productivity
growth, how prices and wages adjust. It leaves out the energy and policy layers that need
the linkage's inputs. So this is the macro model's own baseline, and its numbers are not
those of a linkage run.

A run to 2050 takes roughly 10 minutes. A run holds its whole history in memory, about
4 GB to 2030 and more for longer runs, until you delete it (`del sim`).

## 5. Read the results

`results(sim)` returns a table with one row per province and quarter, from 2022Q1. Main
columns:

| Column | Meaning |
|---|---|
| `GDP Output` | Nominal GDP (production side), CAD per quarter |
| `Real GDP` | `GDP Output` deflated by the province's CPI (2022Q1 = 1) |
| `Household Consumption`, `Government Consumption`, `Capital Bought`, `Exports`, `Imports` | Nominal spending, CAD per quarter |
| `Production`, `Gross Output` | Real and nominal output of all firms |
| `Unemployment Rate` | Share of the labour force (0.06 = 6%) |
| `CPI`, `PPI`, `CPI Inflation Rate` | Price indices and quarterly inflation |
| `Wages`, `Profits`, `Operating Surplus` | Incomes, CAD per quarter |

`annual(df, columns)` sums flows and averages rates per year, by province or for Canada
(`national=True`). `industry_output(sim)` gives real production by industry.
`save(sim, folder)` writes `simulation_shallow.h5`, the same summary file the linkage
writes. Read it back with `pd.read_hdf(path, key="CAN_BC")`; the keys are the provinces,
plus `CAN_BC_industries` and `CAN_BC_firms_<variable>` for industry detail.

**Read with care:**

- **The first quarter jumps.** In 2022Q1 the model adjusts away from its data starting
  point (prices rise about 5%). Compare scenarios with a baseline rather than with data,
  and look at paths from 2023 on.
- **One run is one draw.** Prices and some decisions have random parts. A scenario and its
  baseline with the same seed differ because of the scenario, but small differences can
  still flip with another seed: check two or three seeds before reporting one.
- **Construction is often rationed.** Government purchases of construction (`F`) are
  only about 55% filled on average, and in some quarters not at all, so anything bought
  from construction jumps around from quarter to quarter. Health, education and public
  administration are filled 90-100%.
- **Unemployment and the policy rate are crude.** In longer linkage runs, unemployment
  has sat at zero in some provinces for long stretches, and the policy rate barely moves.
  Rely on output, prices and incomes first.

## 6. Define and run scenarios

A scenario is the baseline with something changed, run with the same seed and horizon,
and compared with the baseline. `run_scenario` builds, runs and returns the results table
in one call, then lets go of the simulation, so memory stays low:

```python
from scenarios.macro_only import run_scenario, annual

base = run_scenario(data, end_year=2030)
scenario = run_scenario(data, end_year=2030, household_demand_growth=0.02)

columns = ["Real GDP", "Household Consumption"]
print((annual(scenario, columns, national=True) / annual(base, columns, national=True) - 1) * 100)
```

**Change a setting** by passing it by name, as above. Any key of `BASELINE` works, and so
does any other argument of `build_simulation` in `scenarios/run_cims_linkage.py`; each is
explained where that function uses it. Good ones to start with:

| Setting | Baseline | What it does |
|---|---|---|
| `household_demand_growth` | 0.01 | Annual growth of household demand on top of the labour force |
| `labour_force_growth` | per province | Annual labour force growth after 2024 |
| `tfp_base_growth_rate` | 0.001 | Productivity growth per quarter |
| `wage_cpi_indexation` | 0.5 | Share of past inflation passed into wages |
| `price_setting_noise_std` | 0.01 | Size of random price changes |
| `seed` | 4 | Random seed |

**Change the economy during the run** (a policy from a given year, a purchase programme)
with a *hook*: a function `hook(sim, year, month)` the model calls at the start of every
quarter, passed as `run_scenario(data, hooks=[hook])`. It can change any part of the
model; `sim.countries["CAN_BC"]` is British Columbia, with its `firms`, `households`,
`central_government`, `government_entities` and `banks`. `extra_government_purchases` in
`scenarios/macro_only.py` (about 20 lines) is an example to copy, and
`government_purchases(sim, "BC")` shows what the government actually bought, to check a
purchase took hold.

**Checklist for a scenario:**

1. Same `seed` and `end_year` as the baseline it is compared with.
2. Check the change took hold: the variable you changed moves as intended.
3. Check the sign of the main effects before reading magnitudes.
4. Repeat the pair with two or three other seeds before reporting a result.

## 7. Running with the linkage

Project runs couple this model with CIMS (energy demand and technology), COPPER
(electricity supply) and LabourABM (occupations). That workflow lives in the GitLab
repository `sesit/M3-linkages`, which clones this repository into
`dependencies/macroabm-ca` and runs it from a scenario's `config.toml`. Once you are
comfortable with the model on its own, start with its
`docs/cims_copper_macro_labour/setup.md` and `quickstart.md`. The settings in `BASELINE`
here are the `[Models.MacroABM.Config]` section of its `scenarios/baseline/config.toml`.

## 8. Further reading

- `dev/io2022/README.md`: how the 2022 pickle was built (2022 input-output tables,
  Canadian households, labour force calibration).
- `docs/canada/raw_data_reference.md` and `canada_provincial_io_development.md`: the
  earlier 2014 build (43 industries). Background only; the runs here use the 2022 pickle.
- `docs/macromodel/`: reference pages for the agents and markets.
- `README.md`: other install options (conda, pip) and development tools.
