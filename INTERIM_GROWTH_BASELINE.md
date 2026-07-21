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

## Provisional status

The baseline is **robust across five seeds** and suitable for **model development and
controlled comparative scenario testing**. It is **not yet fully validated for
quantitative inference**: long-horizon behaviour approaches a full-employment ceiling,
labour-market level calibration and an investment benchmark are unresolved, and
provincial allocation is aggregation-dependent (national plausibility does not by itself
validate the sub-national allocation). The full validation record and figures are kept
outside this branch (in the group's `dev/` workspace), deliberately excluded here.
