# Powering Canada Strong assessment: scenario configurations

Configurations of the Baseline (`EPM1120_B7`) and Powering Canada Strong (`EPM1120_PCS6`)
runs of 2026-11-20. They are linkage configurations: they drive the model through the
CIMS-COPPER linkage (M3-linkages), not through this repository alone.

| Item | Version |
|---|---|
| Model code used by the runs | `6f6e327` (core code unchanged on this branch) |
| Linkage code used by the runs | M3-linkages `4ef1629` |
| Energy-system inputs | CIMS-COPPER delivery `EPM_11_20`: `EPM_Baseline_7`, `EPM_PCS_6` |
| Seed | 4 |

To run, place each folder in the linkage's `scenarios/` with its arm's `cims/`, `copper/` and
`iterations/` folders, replace `<M3-linkages>` in the Powering Canada Strong configuration
with the absolute path of the linkage checkout, and run the Baseline before the policy arm.
The only edits from the files as run are the header comments, one inline comment, and that
path. The energy-system inputs and the model's data file are not included here.
