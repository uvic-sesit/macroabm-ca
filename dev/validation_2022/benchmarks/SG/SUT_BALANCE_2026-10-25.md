# SUT balance — re-exports and output valuation (2026-10-25)

Branch `feature/sut-balance` (from `main` @ 479dcb4). Not pushed. Responds to the read-only handoff
`macroabm-ca-validation/dev/validation_2022/IO_HANDOFF_2026-10-25.md` (74.883B/yr expenditure excess).
Before changing anything, `python run.py --all` on `main` reproduced the committed canonical and compatibility files byte for byte.

## Diagnosis

The handoff's expenditure excess has two separate causes:

| Item | B/yr | Cause | Where |
|---|---:|---|---|
| Sales row exceeds cost column | 48.432 | Imported re-exports booked as sales of Canadian producers | `s4_consolidate_national`, `s6_row`, `s7_assemble` scaled the Canada→ROW blocks to exports **plus** re-exports (INTRX000) |
| Input-product valuation | 26.546 | `output_basic` omitted net product taxes on intermediates | `s8_validate` canonical export (`Z + VA`); the S3 commodity balance already used `Z + VA + product taxes` |

**Re-exports.** These are imported goods that leave Canada untransformed: 49.094B across the 13 P/T.
- Their imports never enter `InternatImportUse`, which is why import use (902.465B) is below the INTIM total (950.897B). That is the previously "undecomposed ~5% gap".
- Because they were booked as provincial producer sales, row sales exceeded column costs by exactly the unused imports.
- **The match is exact.** For every goods commodity, re-exports equal INTIM less import use.
- **The exception is margin services.** G, H49 and H52 carry 0.651B of re-export value that is **Canadian trade and transport margins** on the re-exported goods. That is genuine domestic output, and no import matches it.

**Downstream effect.** The legacy `ICIOReader` sets industry output to the row sum and then computes value added as output − intermediates − taxes (`macro_data/readers/io_tables/icio_reader.py:1174–1190`). The 48.3B therefore became fictitious value added in the model: reader VA was 2,722.492B against an observed VA6 of 2,674.183B. This is part of the "GOS +12.5%" finding in the validation firm audit.

## Changes (`src/ioqc/stages.py`)

1. **`_reexport_split(b)`** splits each province × commodity re-export:
   - the **imported** part is `min(re-exports, max(INTIM − import use, 0))`;
   - the **domestic** part is the remainder (margins).
2. **S4, S6, S7.** The Canada→ROW export blocks (national total and provincial shares) are scaled to `exports + domestic re-export part`. The imported part is excluded from producer rows, mirroring its absence from import use; OECD ICIO also excludes re-exports from both sides. The S3 commodity supply = use control is unchanged, and it still includes all re-exports against INTIM.
3. **Canonical `output_basic`** is now `Z + VA6 + net product taxes on intermediates` (basic-price industry output). The compatibility file's `('TOTAL','Output')` row is now the same column total; the reader drops that row.
4. **New satellite file.** `canonical/reexports_by_province_commodity_basic.csv` holds total, imported (excluded) and domestic (kept) re-exports.
5. **Import diagnostic decomposed.** INTIM = import use + imported re-exports + residual. The residual is 0.000 in every region.
6. **New hard controls in S8** (the build fails if any is violated):
   - every region × industry row total (Z + FD, all destinations) equals its column total (Z + VA6 + net product taxes on intermediates), to a relative tolerance of 1e-6;
   - production, income and expenditure GDP agree in every region, to 1e-3 M.

## Results

| Check | `main` | `feature/sut-balance` |
|---|---:|---:|
| Canonical row total, 13 P/T + CE (B) | 5,104.367 | 5,057.573 |
| Canonical column total (B) | 5,055.935 | 5,057.573 |
| Net row − column gap (B) | 48.432 | 1.3e-8 |
| Largest cell gap (M) | 5,815 (output_basic) / 4,461 | 4.4e-6 |
| GDP expenditure − income, worst region (M) | 289.6 (ON) | 5.2e-6 |
| Canada → ROW exports (B) | 965.801 | 917.369 |
| ROW → Canada imports in use (B) | 902.465 | 902.465 (unchanged) |
| Compat file: reader-implied VA vs VA6 (B) | 2,722.492 vs 2,674.183 | 2,674.060 vs 2,674.183 |

Canadian 13 P/T GDP, by all three approaches:
- at basic prices: 2,674.2B, unchanged;
- at market prices: about 2,862B for the 13 P/T, plus CE.

What changed and what didn't:
- **Unchanged:** the VA components, product taxes, the interprovincial O-D and all domestic and import-use blocks.
- **Changed:** only the Canada→ROW columns (Z −20.024B, FD −28.408B) and `output_basic`.
- **Reader:** the real `ICIOReader` still constructs on the compatibility file, and the load test matches all 50 industries.

## Remaining, explicitly not absorbed

- **Compatibility view, 0.122B of CE residual.** CE is dropped from the behavioural 13 P/T + ROW view (pre-existing, documented). The row − column gap there is −0.122B; the largest cell is 0.049B.
- **ROW block not closed by design.** ROW comes from OECD ICIO, while StatCan governs Canada→ROW. ROW sales exceed ROW Z + VA by about 375B, out of about 254,500B of ROW output (0.15%). That gap is pre-existing (about 355B on `main`); this change adds 20.0B to it. It sits outside the Canadian accounts.
- **100.504B of other production taxes less subsidies** is correctly inside VA6 here. The model does not charge it to firms (validation item F-A1). That is a model-side fix, not a pipeline one.
- **Six boundary-industry fallbacks** stay PROVISIONAL, as before.

## Output hashes (SHA-256)

| File | SHA-256 |
|---|---|
| `compatibility/compat_icio_2022_can_provinces.csv` | `41590fdb19d9eb79758169b51afc0751e6d5c19ce88183bb8fbe330889e689aa` (was `30cd1674…d165896`) |
| `compatibility/icio_2022_can_provinces_oecd50.csv` | `f71b827d7aa96611d63ea9c204d8b324e01d3b637b6c10b0b364256b2b06f309` |
| `canonical/VA_tax_output_basic.csv` | `6af2042259aebc5d25d7cb718d84fbd58a91bc345d3d92c0a4a29278267aa4c2` |
| `canonical/Z_intermediate_basic.csv` | `0a7f48f14b0510ec67c347ee11c5db6260c9a1fd5b1e32ac609267e1e3fc02fe` |
| `canonical/FD_by_source_and_category_basic.csv` | `d4fda8a8d0f525eed3fd70d704cf1f6b124306d01cfc4fdc564bdee002cbd89b` |
| `canonical/reexports_by_province_commodity_basic.csv` | `ff5b99bb3afa748ee25608353fb395f10dacf88f1efb04886d449c018a461c73` |

All checks are in `validation/final_checks.json`:
- `checks.industry_row_col`
- `checks.gdp_three_approaches_by_region`
- `international_import_diagnostic.use_vs_control`
