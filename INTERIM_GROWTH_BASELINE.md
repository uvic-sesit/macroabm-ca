# Interim real-growth baseline — reviewable branch

**Branch:** `real-growth-baseline`
**Status:** interim / provisional. **No decision has been made** about merging to
MacroABM-CA `main` or upstreaming any general change to INET. This branch exists so
colleagues can review the model changes before those decisions.

## What changed

This branch adds **opt-in** firm and labour-supply mechanisms plus several numerical
bug fixes. The initiating demand and labour paths remain exogenous; the changes let them
be transmitted internally (through expectations → investment → capacity → employment →
output) rather than being truncated at current supply.

**Bug / numerical fixes (default behaviour changes only where a defect was hit):**
- `macromodel/util/clamps.py` (new) + `target_production.py`, `desired_labour.py`,
  `excess_demand.py`: an inf-safe input clamp. The naive form `target + w*(limit-target)`
  evaluated `0*inf -> NaN` for a firm with no binding constraint at weight 0; a downstream
  `fillna` then silently rewrote it to 0, disabling the firm. Identical to the old form
  for all finite limits at every weight.
- `government_entities/func/consumption.py`: absorbing-zero trapdoor + exogenous-setter
  weight-ratchet fixes.
- `util/get_histogram.py`: no longer crashes the run on degenerate/non-finite
  distributions (was a diagnostic call aborting the whole simulation).
- `individuals/individuals.py`: wires the previously-dead workforce-entry hooks (a no-op
  under the `NoAging` default).

**Optional (opt-in) mechanisms — shipped defaults reproduce legacy behaviour exactly:**
- `demand_estimator.demand_smoothing` (alpha, default **1.0** = no smoothing).
- `demand_for_goods.unmet_demand_weight` (rho, default **1.0**).
- `target_capital_inputs.rolling_reference` (default **False**) and
  `forward_looking_reference_fraction` (phi, default **0.0**).
- `individuals` demography `ExogenousLabourForcePath` (default demography **NoAging**).

## Legacy compatibility

All new parameters default to the shipped values, and the default demography stays
`NoAging`. A configuration that does not opt in reproduces prior results; only the
documented bug fixes change behaviour, and only on the specific defective paths.

## Candidate (provisional) baseline preset

`macromodel/configurations/growth_baseline_preset.py` carries the machine-readable
parameter set (`CANDIDATE_GROWTH_BASELINE`) and `apply_candidate_growth_baseline(...)`.
The labour-supply path is an **on/off switch like the other mechanisms**: the observed
provincial labour-force index is **bundled** (`scripts/data/labour_force_index_2014_2024.json`,
~4 KB), so `use_observed_labour_path=True` loads it automatically — no data assembly.

```python
from macromodel.configurations import CountryConfiguration
from macromodel.configurations.growth_baseline_preset import apply_candidate_growth_baseline

cfg = CountryConfiguration.n_industry_default(n_industries=43)
# candidate baseline with the bundled observed labour path for Ontario, 53q:
apply_candidate_growth_baseline(cfg, use_observed_labour_path=True, province="CAN_ON", n_quarters=54)
# ...or pass your own index explicitly: apply_candidate_growth_baseline(cfg, labour_force_index=[...])
# ...or omit it entirely -> stays on the legacy NoAging default (fixed labour force).
```

### Turnkey runner

`scripts/run_candidate_baseline.py` runs the whole thing and prints the headline
national result:

```
uv run python scripts/run_candidate_baseline.py [path/to/datawrapper.pkl] --quarters 53 --seed 0
uv run python scripts/run_candidate_baseline.py ... --legacy      # shipped defaults, for A/B
```

### Data dependencies

- **Labour-force index — BUNDLED** (`scripts/data/...json`). Rebuild from raw LFS with
  `uv run python scripts/build_labour_force_index.py [path/to/14100327.csv]`
  (defaults to `../raw_data/14100327.csv`, then `dev/statcan/14100327.csv`).
- **DataWrapper pickle — NOT bundled** (large; rebuildable from `raw_data` via the tracked
  `macro_data` pipeline / the `build_macrodata` CI workflow). The runner defaults to
  `dev/pkl_files/disagg_sectorprovs_2026_07_10_default.pkl`; pass a path if yours differs.
- **Raw StatCan LFS (`14100327.csv`)** is placed in the shared `../raw_data/` for the SESIT
  team (not committed — `raw_data` is gitignored); it is only needed to *rebuild* the index.

## Running the tests

```
uv run python -m pytest tests/ -q                       # full suite
uv run python -m pytest tests/test_macromodel/unit/test_util/test_clamps.py \
  tests/test_macromodel/unit/test_util/test_get_histogram_robustness.py \
  tests/test_macromodel/unit/test_agents/test_firms/func/test_growth_mechanisms.py \
  tests/test_macromodel/unit/test_agents/test_individuals/func/test_exogenous_labour_force_path.py -q
```

The new tests cover: inf-safe clamps, demand smoothing (alpha), unmet-demand weighting
(rho), the rolling capital reference and its safeguards, the exogenous labour-force path
and workforce-entry hooks, the histogram robustness fix, and the candidate-baseline preset
+ bundled labour-index loader.

## Checkpoint 2026-07-27 — household, fiscal, and productivity status

Verified from code/config/git history (not memory). Branch `real-growth-baseline`, HEAD
`06ef683`, tag `checkpoint/pre-productivity-2026-07-22` at `48dea36`.

### Growth & supply (commit status)
The demand-memory, rolling-capital-reference, internal-growth-transmission and observed
labour-path mechanisms above are **committed as code and as an opt-in preset**
(`growth_baseline_preset.py`, runner `run_candidate_baseline.py`; last touched `e2e6e25`).
They are **not shipped config defaults** — verified legacy defaults still ship
(`demand_smoothing` 1.0, `unmet_demand_weight` 1.0, `excess_demand.consider_capital_inputs`
1.0, `firm/sectoral_growth_adjustment_speed` 0.0, `target_capital_inputs_fraction` 0.0,
`rolling_reference` False, gov consumption `AutoregressiveGovernmentConsumptionSetter`,
demography `NoAging`). The preset overrides these. Approx. real-GVA growth of the current
**structural** provisional baseline (disposable closure + candidate levers + `NoOpTFPGrowth`,
3 seeds, 53q): **~1.0%/yr** (vs the earlier `ExogenousHouseholdConsumption` candidate arm
~1.7–1.9%/yr). Main remaining limits: long-horizon full-employment ceiling, investment
benchmark and labour-level calibration unresolved, aggregation-dependent provincial allocation.

### Household demand — `DisposableIncomeHouseholdConsumption` (COMMITTED, `06ef683`)
- Implemented and committed with focused tests (`test_disposable_consumption.py`).
- Consumption responds to **after-tax disposable income**: `disposable = expected_income −
  income_tax·((1−SI)·employee_income + financial_income) − SI·employee_income`, floored at 0
  (mirrors `CentralGovernment.compute_taxes`). Higher personal tax/SI lowers consumption.
- **Transfers** are untaxed and retained in full → raise household resources and consumption.
- The existing **propensity distribution is preserved unchanged** (the rule only nets income
  and forwards `saving_rates`; falls back to gross if income components absent).
- Propensity `(1−s)≈0.611` is **provisional**, `1 − HFCS(goods+services/gross income)` —
  **NOT an SNA saving-rate calibration**. Housing/rent overlap and APC re-centring remain
  **deferred**.
- **Availability vs default:** available and tested, but the **repository default is still
  `DefaultHouseholdConsumption`** (the disposable rule is a selectable option, not the default).

### Government & public finance — passive fiscal closure (present stage)
- Government consumption stays on the **exogenous** path for the provisional baseline (preset
  selects `ExogenousGovernmentConsumptionSetter`; national-accounts path held flat past the tail).
- Taxes and social contributions are **endogenous** to activity (`compute_taxes`); revenue
  aggregates them (`compute_revenue`).
- `deficit = benefits + gov_spending + interest − revenue`; extra revenue **reduces the
  deficit / raises the surplus**. `debt_{t+1} = debt_t + deficit`; `interest = policy_rate·debt`.
- **No debt cap, borrowing limit, or fiscal-reaction rule is active** (verified absent).
- This is a coherent **passive fiscal closure** for this stage: taxes/benefits endogenous,
  government consumption exogenous, deficit accumulates into debt with no policy feedback.

### Productivity / TFP (correction UNCOMMITTED; NoOp remains default)
- **Original defect:** `Firms.compute_productivity_investment` returns net capital investment
  (`max(0, capital_bought − replacement)`), fed to TFP via `compute_tfp_growth` **regardless of
  the planner** — so ordinary capital investment drove TFP even under
  `NoProductivityInvestmentPlanner` (TFP ballooned to ~2.69× over 53q).
- **Narrow gating correction** (`firms.py`, uncommitted): `Firms._investment_drives_tfp()` is
  True only when a real planner is active; `compute_tfp_growth` uses **zero** productivity
  investment under the No-op planner. `NoOpTFPGrowth` stays **bit-for-bit** (full-sim NoOp arm
  reproduces exactly); investment-induced TFP is **preserved as an explicit opt-in** (select
  `Simple`/`Optimal` planner). Covered by `test_tfp_investment_gating.py`.
- Clean `SimpleTFPGrowth` at `0.0025`/q follows the intended geometric path
  (`(1.0025)^53 = 1.1415`, matched exactly).
- **Three-seed findings (clean Simple vs NoOp):** labour-per-output −0.96%/yr, unit-cost growth
  −0.42pp/yr and PPI −0.43pp/yr (price transmission via the labour-cost channel — traced through
  factor inputs and unit costs, not inferred from `prices.py`), profit/GVA +3.2pp, real GVA
  ≈ unchanged (−0.04pp), unemployment +1.1pp. Numerically stable (0 NaN, 0 neg-K). Intermediate-
  per-output is unchanged **by design** (intermediate efficiency is the separate
  `technical_coefficients_growth` lever).
- **Interpretation:** this configuration is **demand-constrained** — productivity expands
  *efficient supply*, but final demand does not rise enough to absorb materially higher
  production, so the gain surfaces as lower labour input, modest disinflation and better margins
  rather than extra output. Demand growth could later come from population growth translated into
  household demand, disposable-income growth, exports, government demand, investment expectations,
  transfers, or credit — **none implemented now**.
- **`NoOpTFPGrowth` remains the default.** Clean TFP is an **available diagnostic/scenario**, not
  the selected baseline growth fix.

## Provisional status

The baseline is **robust across five seeds** and suitable for **model development and
controlled comparative scenario testing**. It is **not yet fully validated for
quantitative inference**: long-horizon behaviour approaches a full-employment ceiling,
labour-market level calibration and an investment benchmark are unresolved, and
provincial allocation is aggregation-dependent (national plausibility does not by itself
validate the sub-national allocation). The full validation record and figures are kept
outside this branch (in the group's `dev/` workspace), deliberately excluded here.
