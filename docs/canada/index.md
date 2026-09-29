# MacroABM-CA as used for Powering Canada's Growth

MacroABM-CA is the Canadian, provincial adaptation of the INET Oxford / Macrocosm
MacroABM framework: ten provincial economies (the territories are folded into the
rest of the world), each with firms by industry, households and individuals, a bank,
a government entity and the shared goods, labour, credit and housing markets, trading
with each other and with the rest of the world. This branch (`powering_canadas_growth`)
is the version of the model used for the *Powering Canada's Growth* analysis of the
macroeconomic return on doubling Canada's electricity grid, in which the Canada Energy
Regulator's *Energy Futures 2026* scenarios are imposed on the model through the
CER-MacroABM linkage in the
[M3-linkages](https://gitlab.com/sesit/M3-linkages) repository.

The published methodology of that analysis, including every linkage channel, the
policy environment, the calibration and the standing limitations, is at
<https://sesit.gitlab.io/m3-linkages/projects/powering_canadas_growth/methodology/>.
This page records what is specific to the model on this branch and how it was run.

| Read this | for |
|---|---|
| [Onboarding guide](onboarding_guide.md) | the repository layout, where raw data enters, how the model object is built, the model components, and the team workflow for syncing with the upstream INET repository |
| [Data build](data_build.md) | how the pinned 2022 provincial population pickle was built, step by step |
| [Raw data reference](raw_data_reference.md) | every raw-data input the 2022 provincial build reads, its source and how it is used |

## The model as configured for the analysis

The runs are driven from M3-linkages: `scripts/run_cer_linkage.py` there imports the
helpers in [`scenarios/run_cims_linkage.py`](../../scenarios/run_cims_linkage.py) and
[`scenarios/run_canada_provincial.py`](../../scenarios/run_canada_provincial.py), builds
the simulation from the pinned pickle, installs the linkage hooks and runs it. The three
production scenario folders (`CER Current Measures 2022io CORE`, `CER Net-zero 2022io
CORE`, `CER Net-zero 2022io CORE status quo`) hold the complete configuration; the
settings that concern the model itself are:

| Setting | Value | Where |
|---|---|---|
| Base data | 2022 provincial input-output table, OECD 50-sector scheme (coal `B05`, merged oil and gas `B06`), ten provinces | `dev/pkl_files/io2022_10prov_2022_v2_pumf_built-2026-08-18.pkl`, see [Data build](data_build.md) |
| Households | Canadian balance sheets, income and consumption from the SFS 2023, CIS 2022 and SHS 2023 public-use microdata, calibrated to 2022 national accounts controls; individual-level demographics keep the HFCS skeleton | `macro_data/readers/population_data/canadianized_household_adapter.py` |
| Labour and capital data | Statistics Canada 2022 compensation of employees, employment shares, capital stock and capital compensation by province and industry; labour share calibrated to the observed Canadian share | `macro_data/readers/default_readers.py` (`can_2022` inputs), `ProvincialLabourReader` |
| Provincial series | Province-specific CPI, unemployment, house-price and vacancy paths, effective tax rates and investment splits | `canadian_inputs/` readers |
| Emissions and carbon pricing | Emissions on the OECD-50 scheme with a value-weighted factor for the merged oil-and-gas industry; Canada's output-based pricing system (`use_obps_reg`) | `macro_data/readers/emissions/`, `macromodel/policy/output_based_price_system_can.py` |
| Horizon | 2022 to 2050, quarterly, one seed (4) | `sim_start_year`, `steps_per_year`, `seed` |
| Growth baseline | The real-growth baseline preset: observed provincial labour-force index continued with Statistics Canada population projections (`labour_force_growth`), household demand following each province's labour force plus 0.75 %/yr per head, TFP constants 0.001 and 0.01 | `macromodel/configurations/growth_baseline_preset.py`, `use_candidate_baseline = true` |
| Capital adjustment | `CandidateCapitalRule.target_capital_inputs_fraction` 0.10 (preset) in Current Measures and the status-quo leg, 0.15 in the Net-zero scenario with the enabling package | preset and config |
| Price regime | `price_setting_noise_std = 0.01`, `national_inflation_expectation = true`, `price_setting_speed_gf = 0.5` | config |
| Memory | `trim_agent_history = 4`, shallow HDF5 export only | config |

The linkage flags applied at run time (intensity targets, quantity anchors, capacity
floor, ceiling and gate, production floors, export pins, the rest-of-world electricity
split, the policy environment, project overlays) are documented in the M3-linkages
methodology; their implementation on the model side lives in
`macromodel/agents/firms/firms.py`, `macromodel/agents/households/households.py`,
`macromodel/rest_of_the_world/rest_of_the_world.py`,
`macromodel/markets/goods_market/func/clearing.py` and `macromodel/simulation.py`.

## Reproducing a run

1. Install the model with `uv sync` (see the repository [README](../../README.md)).
2. Obtain the raw-data root and the pinned pickle from the SESIT shared drive
   (*SESIT - MacroABM data*), or rebuild the pickle following [Data build](data_build.md).
   Rebuilding is not bit-identical (the population sampler is random), so a replication
   of the published numbers must use the pinned pickle.
3. Check out `powering_canadas_growth` in both repositories and run the scenario from
   M3-linkages with `python linkage_cer_macroabm.py -sc "<scenario folder>"`, after
   editing `pkl_path` and `raw_data_path` in the scenario's `config.toml` to your own
   locations. The M3-linkages project page gives the full recipe.

The in-repo command line of `scenarios/run_cims_linkage.py` is a legacy entry point
that wires only part of the linkage; production runs go through the M3-linkages driver.

## Disclosures that concern the model

The analysis-level limitations are listed in the published methodology. Two are
properties of this model build rather than of the linkage and are repeated here:

* **Households are Canadian, individuals are not.** The household economic block
  (balance sheets, income, consumption and saving) is drawn from Canadian microdata, but
  the individual-level demographics attached to each household (age, sex, education,
  household composition) keep the pooled-European HFCS skeleton.
* **The labour share is calibrated, not observed.** The provincial input-output table
  gives value added; compensation of employees is taken from Statistics Canada's 2022
  breakdown and the aggregate labour share is calibrated onto the observed Canadian
  share (`ProvincialLabourReader`). The industry distribution of the wage bill follows
  the observed compensation data.
