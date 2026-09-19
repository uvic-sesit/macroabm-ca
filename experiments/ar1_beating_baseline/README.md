# Alpha 0.40 Historical and ITC Experiments

This directory contains the source needed to reproduce the reported
MacroABM-CA alpha=0.40 historical-validation and ITC experiment packages.
Generated outputs are intentionally excluded from version control.

## Reported specification

The final specification combines:

1. calendar-year labour-force levels;
2. labour-force membership updates before quarterly labour matching;
3. desired labour based on target production without inherited-capital
   pre-clamping;
4. desired intermediate inputs based on target production without
   inherited-capital pre-clamping; and
5. firm demand smoothing of 0.40.

Realized production remains constrained by target production and available
labour, intermediate inputs, and inherited capital.

## Main entry points

- `run_alpha040_30seed.py`: 30-seed historical-validation package.
- `alpha040_validation.py`: historical-validation tables and diagnostics.
- `pub_stage_a040.py`: definitive 10-seed control/full-ITC/no-B package.
- `pub_a040_report.py`: headline policy reporting from saved outputs.
- `robustness_a040.py`: Taylor-rule and investment-elasticity exercises.
- `report_robustness_a040.py`: robustness reporting.
- `pub_collector.py`: common quarterly, annual, window, regional, and cell
  collection conventions.

`case7_itc_run.py`, `followup_e16.py`, `run_batch.py`,
`run_historical_experiment.py`, and `evaluate_experiments.py` provide the
shared construction and controlled-path helpers used by those entry points.

## Dependencies and inputs

The runners use the frozen closure helpers in
`experiments/itc_endogenous_closure/` and the validated CAN-2022 construction
scripts and inputs under the local `dev/io2022`, `dev/validation`, `dev/statcan`,
and `dev/pkl_files` data workspace. Those large or development-only inputs are
not duplicated here. A reproducibility archive must preserve the validated
CAN-2022 pickle and official-data inputs separately.

## Output policy

All simulation results are written below `outputs/`, which is ignored. Python
caches, Numba caches, and logs are also ignored. Reports in this directory are
source programs; generated Markdown, CSV, NPZ, PDF, and image artifacts should
be archived outside Git with the paper replication package.
