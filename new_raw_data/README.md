# `new_raw_data/` — staging area for provincial data upgrades

**Temporary/evaluation folder.** This holds newly-collected provincial input data that is
being validated before it is promoted into the canonical `raw_data` bundle (the SharePoint
`SESIT - MacroABM data/raw_data`). Keeping it separate guarantees we never overwrite an
existing `raw_data` file while iterating.

The `macro_data` package reads from here automatically via
`ProvincialMacroReader` (see `macro_data/readers/economic_data/provincial_macro_reader.py`),
which resolves this folder relative to the repository root. If the folder or its data file
is absent, the model silently falls back to the existing national/proxy behaviour.

## Contents

| Path | What |
|------|------|
| `statcan_provincial/provincial_macro_series.csv` | Tidy provincial panel: CPI inflation, unemployment rate, nominal house-price growth, vacancy rate, by province and quarter. |
| `build_provincial_macro_series.py` | Reproducible downloader + processor that regenerates the panel from Statistics Canada bulk CSVs. |

Regenerate the panel with:

```bash
python new_raw_data/build_provincial_macro_series.py
```

Full provenance, filters, and assumptions: `docs/canada/provincial_raw_data.md`.

## Promotion checklist (when ready)

1. Move `statcan_provincial/provincial_macro_series.csv` into the canonical `raw_data`
   (e.g. `raw_data/statcan_provincial/`) and update `ProvincialMacroReader.default_path()`
   to resolve it under `raw_data_path` instead of the repo root.
2. Keep `build_provincial_macro_series.py` in-repo for reproducibility.
