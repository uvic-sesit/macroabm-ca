# The 2022 provincial data build

The scripts in this folder build the ten-province 2022 `DataWrapper` pickle that the
Powering Canada's Growth runs use. The full recipe, inputs and rationale are documented in
[`docs/canada/data_build.md`](../../docs/canada/data_build.md); the inputs themselves are
described in [`docs/canada/raw_data_reference.md`](../../docs/canada/raw_data_reference.md).

| Script | Role |
|---|---|
| `fold_territories_2022.py` | aggregates the territories of the 13-region 2022 IO table into the rest of the world |
| `build_2022_datawrapper_10prov.py` | builds the ten-province pickle from the `dev/raw_data_10prov/` overlay (`--canadianized-households`, `--lfs-unemployment`) |
| `lfs_unemployment_2022.py` | post-build calibration of each province's initial unemployment rate to the 2022 Labour Force Survey |
| `prepare_compensation_input.py` | regenerates the 2022 compensation-of-employees input from the `macroabm-io2022` pipeline |
| `household_prototype/prepare_household_canadianization.py` | household balance sheets and income from the SFS 2023 and CIS 2022 microdata |
| `household_prototype/prepare_household_consumption.py` | household consumption and saving from the SHS 2023 microdata |
| `household_prototype/download_controls.py`, `extract_controls.py` | fetch and reduce the 2022 Statistics Canada control tables to `controls_2022.json` |
| `household_prototype/PUMF_DOWNLOAD_INSTRUCTIONS.md`, `SOURCE_MANIFEST.md` | where to obtain the microdata and what each source is used for |

Build, from the repository root, with `MACROABM_RAW_DATA` pointing at the raw-data root for the preparation scripts and the `dev/raw_data_10prov/` overlay in place for the builder (see the data-build page):

```bash
uv run python dev/io2022/fold_territories_2022.py --input <root>/icio/icio_2022_can_provinces.csv
uv run python dev/io2022/household_prototype/prepare_household_canadianization.py --real
uv run python dev/io2022/household_prototype/prepare_household_consumption.py --real
uv run python dev/io2022/build_2022_datawrapper_10prov.py --force --canadianized-households --lfs-unemployment
```

The 2022 IO table and the `can_2022/` industry inputs are produced by the private
`macroabm-io2022` pipeline from Statistics Canada sources and placed under the raw-data
root; they are not committed here.
