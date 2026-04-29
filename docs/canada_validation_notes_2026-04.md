# Canada Validation Notes

This repo is currently under active development for the Canada provincial workflow.

The current active Canada input table is:

- `dev/raw_data/icio/icio_2014_can_provinces.csv`

This file is the new Link-1997-based provincial IO table produced in the companion `io-disaggregation` workflow.

A tracked validation copy of the exact table currently used on this machine is also included here:

- `docs/canada_validation_inputs/icio_2014_can_provinces_link97_43_b_proxy.csv`

Suggested setup:

1. copy
   - `docs/canada_validation_inputs/icio_2014_can_provinces_link97_43_b_proxy.csv`
2. to
   - `dev/raw_data/icio/icio_2014_can_provinces.csv`
3. then run the SESIT provincial workflow from `sesit_tools`

Important:

- the model currently reads the legacy runtime filename `icio_2014_can_provinces.csv`
- so the validated Link-1997 table must be copied into `dev/raw_data/icio/` under that exact name

A few local guardrails and robustness fixes are currently present so the model can read and execute against this new table while some upstream IO-table issues are still being refined.

## Current temporary or provisional fixes

- `macro_data/readers/io_tables/icio_reader.py`
  - safe zero-denominator handling in trade-share construction to prevent `0/0 -> NaN`

- `macro_data/readers/icio_sea_matching.py`
  - provisional guard against allocating positive investment mass into sectors with effectively zero provincial value added

- `macromodel/markets/goods_market/func/lib_water_bucket.py`
  - safe zero-denominator normalization in trade-proportion arrays
  - extra NaN diagnostics during goods-market clearing

- `macromodel/markets/goods_market/func/lib_pro_rata.py`
  - extra NaN diagnostics in seller-capacity construction

## Path and workflow cleanup

The SESIT helper scripts now use repo-relative `dev/` paths instead of machine-specific hard-coded paths:

- `sesit_tools/macroabm_provincial_data.py`
- `sesit_tools/macroabm_provincial_model_wTFP_simplifying.py`
- `sesit_tools/h5_results_dashboard.py`

The intended local working structure is:

- `dev/raw_data`
- `dev/pkl_files`
- `dev/output`

`dev/` remains a local working area and is intentionally ignored by Git.

## Interpretation

These changes are intended to make the Canada workflow reproducible and shareable for validation purposes.

Some of the current guardrails are best understood as model-readiness fixes rather than final methodological choices. In particular, the `icio_sea_matching.py` safeguard is likely better addressed upstream by refining very small provincial IO cells that retain positive fixed capital formation despite effectively zero value added.

These temporary fixes should be revisited and simplified as the upstream provincial IO-table issues are resolved.
