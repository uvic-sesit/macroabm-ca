# 2022 MacroABM Integration — Implementation Log

Branch: `feature/io-2022-integration` (from verified `real-growth-baseline`; baseline untouched).
Goal: wire validated 2022 inputs into the DataWrapper build without altering behavioural
equations; build a 2022 DataWrapper; verify 50 OECD sectors × 13 provinces; run smallest sim;
short candidate run; compare vs 2014 `real-growth-baseline`.

Validated inputs: `macroabm-io2022/integration_2022_inputs/`
- OECD-50 2022 provincial IO compat table → copied to `dev/raw_data/icio/icio_2022_can_provinces.csv`
- `capital_stock_end2021_oecd50_by_province_CADmillions.csv` (opening K, end-2021)
- `capital_compensation_oecd50_by_province_CADmillions.csv` (replaces WIOD CAP)
- `employment_shares_oecd50_by_province.csv` (distribution only, from 36-10-0489)
- HFCS-2021 for remaining household dimensions (fallback for the rest)

Issue classes: `data mapping | DataWrapper integration | sector compatibility | accounting | behavioural`

## Structural facts established (orientation, no code changed)
- 2014 provincial IO: 10 provinces, 43 legacy industries, FD = {HH cons, Govt cons, FCF}.
- 2022 provincial IO: **13 regions** (adds YT/NT/NU), **50 OECD industries**,
  FD = {HH cons, Govt cons, FCF, Changes in Inventories, Direct Purchases Abroad}.
- Reader seam for IO: `default_readers.py` `use_provincial_can_reader` block (hardcoded 2014).
- Reader seam for capital stock / capital comp / labour comp: WIOD `WIODSEAReader`
  (`get_values_in_usd` / `set_values_in_usd`); values stored in **USD absolute** (CAD→USD via
  exchange rate, ×1e6). SEA drops employment (VA/COMP/CAP/K only).
- Identity from validation report: `capital_comp = VA − wages − employer contributions`
  ⇒ `Labour Compensation (COMP) = VA_io − capital_comp` (wages + employer contributions).
  This makes capital-stock, capital-comp, labour-comp all sourceable from validated+IO data,
  avoiding the WIOD OECD-50 sector bridge (built for the 43 legacy codes; a compatibility risk).

## Changes

| # | change | reason | validation | effect | remaining issue |
|---|--------|--------|------------|--------|-----------------|
| 0 | (pre-existing, uncommitted) widened industry-code regex in `use_provincial_can_reader` | accept OECD-50 codes (A01, C17_18, C302T309, J62_63, R/S/T) | regex matches all 50 codes | reader can enumerate 2022 industries | — |
| 1 | `default_readers.py`: year→file map in `use_provincial_can_reader` (2014→legacy, 2022→`icio_2022_can_provinces.csv`); replaced 2014-only `raise` | **DataWrapper integration** — let the provincial reader load the 2022 table | probe: 50 industries + 13 regions enumerate; import OK | 2022 provincial IO can be selected | extra FD cols (Changes in Inventories, Direct Purchases Abroad) pass through unused (verified no getter references them) |
| 2 | `default_readers.py`: new `inject_can_provincial_socioeconomic_2022()` called after SEA reconciliation for the 2022 build; overrides Capital Stock (end-2021), Capital Compensation (2022 IO), Labour Comp = VA−capcomp | **data mapping** — replace WIOD `K`/`CAP` national-split-by-VA with validated province×OECD-50 StatCan series; avoids WIOD OECD-50 sector bridge | probe: capcomp/VA 0.43–0.61, labour>0, K/Y 0.83–2.57 all 13 regions; units CAD×1e6 match IO output ($1,960B ON) | model gets real 2022 provincial capital/labour | Labour comp lumps employer contributions into COMP (SNA-correct); capstock floored at 1 CAD-mn to keep output/K finite |
| 3 | `default_readers.py`: provincial build falls back to newest available `{y}_SML.csv` (2020) when `{year}_SML.csv` missing, with warning | **sector compatibility** — model's global ICIO only exists in pre-2021 classification; real 2022 SML is OECD-50 and incompatible with `aggregate_io`/`ICIO_ALL`. Global table only scaffolds CAN imputed-rent/total-output; provincial table overrides economics | build now passes ICIO layer (warning fired) | 2022 build no longer aborts on missing global SML | imputed rent for CAN is 2020-based (reallocated to provinces by 2022 output shares) — flag as approximation |
| 4 | `default_readers.py`: HFCS wave folder resolved to nearest available vintage ≤ year when exact `{year}` folder missing (2022→2021) | **data mapping** — HFCS waves are discrete (2010/14/17/21); report specifies HFCS-2021 for household dims | build passes ICIO layer, reached HFCS; wave 2021 present (p1/h1/d1, case-insensitive FS) | household structure uses HFCS-2021 as intended | — |
| 5 | `hfcs_reader.py`: upper-case column names + mapping keys on read; drop duplicate columns; `low_memory=False` | **data mapping** — 2021 HFCS wave ships lower-case codes (`sa0100`, `pe0400`); reader/`var_mapping` assume upper-case → `KeyError: 'SA0100'` | probe: all mapped vars present after upper-casing (PE0400, DHHTYPE, DA*/DL*, SA0100 with country codes); no-op for older waves | HFCS-2021 wave reads for all P/H/D files | — |
| 6 | `wiod_sea_data.py` + `default_readers.py`: new `data_year` param decouples the WIOD column read from the reported `year`; provincial build reads latest WIOD year (≤2014) but reports `simulation_year` | **sector compatibility / data mapping** — WIOD SEA coverage ends 2014 → `KeyError: '2022'`. For 2022, WIOD is pure scaffold (VA rescaled to IO; K/CAP/COMP overwritten by injection), so scaffold year is irrelevant while exchange-rate year must stay 2022 | build passes WIOD read (warning fired) | 2022 build passes WIOD SEA construction | WIOD→OECD-50 bridge output is discarded (overwritten) |
| 7 | `sector_contracts.py`: add WIOD-old→OECD-50 bridge rules (C17→C17_18, C24→C24A/B, C30→C301/C302T309, J62→J62_63, R_S→R/S) + `SEA_DROP_SECTORS={U}` (no OECD-50 counterpart) | **sector compatibility** — bridge raised `Cannot align WIOD SEA sectors ... C17, C24, C30, J62, R_S, U`. Rules gated by target-set membership so old-classification builds are unaffected | build passes bridge | WIOD SEA aligns to OECD-50 without raising | values discarded for 2022; rules are also correct for any future OECD-50 build |
| 8 | `icio_sea_matching.py`: 3 division guards `np.isnan`→`np.isfinite` (cap_factors=CAP/gfcf L68; ratios=CAP/VA L77; va_factor L209) | **accounting** — cvxpy `Problem data contains NaN`. **Diagnosed** (diag_reconcile.py): every province (incl. ON/AB) has 2–3 capital-good sectors with capital-comp>0 but zero firm-FCF supply → `CAP/gfcf=+inf`; guard caught 0/0 nan only. `cc>VA`=0 and `VA~0&cc>0`=0 everywhere (identity holds, γ finite) | build passes SEA reconciliation | zero-FCF-supply sectors get 0 investment weight; no finite result changed | not territory-specific — inherent to the finer OECD-50 split; 2014 WIOD-floored data never hit exact zeros |
| 9 | `world_bank_reader.py`: `_nearest_year_str()` helper + applied to get_tau_vat / get_tau_exp / get_lcu_exports / get_gini_coef / get_historic_gdp | **data mapping** — WB annual series (VAT, export tax, GDP) end before 2022 → `KeyError: '2022'` in exogenous data build | build passes exogenous WB lookups | year-indexed WB scalars resolve to latest available year | WB tax/GDP scalars are pre-2022 vintage (latest available) — flag as approximation for 2022 base |
| 10 | `default_readers.py`: fold 2022 FD columns "Changes in Inventories"→"Fixed Capital Formation", "Direct Purchases Abroad"→"Household Consumption", then drop originals | **accounting** — `assert gdp_output==gdp_expenditure` failed. **Diagnosed** (diag_gdp_identity.py, real ICIOReader methods): the two omitted FD columns are the exact residual; VA−(C+G+I+X−M) = +2.6%..+4.8% before, **0.000 after** for every region. Tax multipliers provably cancel; leaving them in place would also double-count via `get_trade` | in-build diag: core identity closes to 0 once vat finite | GDP output=expenditure identity holds exactly; 2022 table now structurally matches the 3-symbol model layout | inventories fold into total FCF then split firm/hh/gov by France proxy fractions — identity unaffected (cancels) |
| 11 | `world_bank_reader.py`: `_nearest_year_str`→`_nearest_year_value` (nearest year with a **finite** value, skipping trailing NaNs); all 5 getters updated | **data mapping** — after fix #9 the GDP identity still failed with `resid=NaN` because `get_tau_vat(CAN,2022)`'s nearest year column exists but CAN's cell is NaN (trailing NaNs in WB VAT series) | in-build diag: **GDP identity now resid=0.000% for all 13 regions**; vat=0.0274 finite | WB scalars resolve to nearest populated year | CAN VAT is a pre-2022 populated vintage — flag as approximation |
| 12 | `oecd_economic_data.py`: `_closest_time()` helper + `unemployment_benefits_gdp_pct` uses it (filter country first, then nearest available year) | **data mapping** — central-government build: `unemployment_benefits_gdp_pct(CAN,2022)` did `.iloc[0]` on empty → `IndexError: single positional indexer is out-of-bounds`; OECD benefits series ends before 2022 | build passes central government | benefits % GDP resolves to nearest available year | OECD benefits are pre-2022 vintage — flag as approximation |
| 13 | `oecd_economic_data.py`: `read_business_demography` resolves year via `_closest_time` for the (country) subset before the TIME filter | **data mapping** — govt-entities build: 2022 filter empty → `isic_table[country]` `KeyError: Country.CANADA` (empty unstack drops the country column); OECD business demography ends before 2022 | build passes govt entities | firm counts by industry resolve to nearest available year | business-demography counts are pre-2022 vintage — flag as approximation |
| 14 | `eurostat_reader.py`: `number_of_households` nearest-populated-year fallback (wide format) | **data mapping** — synthetic-population build: `df.loc[country,'2022']` `KeyError: '2022'`; Eurostat household counts end before 2022 | build passes household counts | household count resolves to nearest available year | pre-2022 vintage — flag as approximation |
| 15 | `hfcs_synthetic_population.py`: base-quarter unemployment/participation rate fall back to last finite observation | **data mapping** — `labour_stats.loc['2022-Q1']` `KeyError`; WB/IMF/OECD labour series end before 2022 | build passes population labour rates | base labour rates resolve to last available quarter | pre-2022 labour-rate vintage — flag; also affects YT/NT/NU person normalization (verify at init) |
| 16 | `oecd_economic_data.py`: read_tau_sif / read_tau_siw / read_tau_firm pass a **country-only**-filtered df to `find_closest_year` (was passing the already-empty country+year filter) | **data mapping** (latent bug) — synthetic-firms build: `find_closest_year` did `min([])` → `ValueError: min() iterable argument is empty` for 2022 | build passes firms | social-insurance / corporate tax rates resolve to nearest available year | pre-existing bug, only reachable when the exact year is absent (2022); pre-2022 tax vintage |
| 17 | `eurostat_reader.py`: `get_total_bank_equity` nearest-populated-year lookup + guard `proxy==country` (no self-recursion) | **data mapping** (latent bug) — synthetic-banks build: `RecursionError` (repeated 974×); FRA's proxy is FRA and FRA had no 2022 data → infinite recursion | build passes banks | bank equity resolves to latest valid year and terminates | pre-existing bug, only reachable when neither country nor proxy has the year (2022) |
| 18 | `eurostat_reader.py`: new `_nearest_balance_sheet_value()` helper; `get_total_fin_firm_debt` (was unguarded) + `get_total_nonfin_firm_debt` use it | **data mapping** — TaxData/`firm_risk_premium`: `get_total_fin_firm_debt` `df['2022']` `KeyError: '2022'`; eurostat balance sheets end before 2022 | build passes TaxData | firm debt (fin+nonfin) resolves to nearest populated year; risk premium stays finite | pre-2022 vintage |
| 19 | `icio_reader.py`: `get_taxes_less_subsidies_rates` zero-safe divide (0 rate where output==0) | **accounting** — firm-bank matching `lsa` got `matrix contains invalid numeric entries` (NaN). **Diagnosed** (diag_zero_output.py): zero-output (province,sector) cells pervasive under OECD-50 (coal B05/B06/B07 in NL/PE/NS/NB/MB; NU up to 12) → taxes/0 = NaN | matching diag showed real NaN source was firm Deposits (all 50), not tax rate | zero-output sectors → 0 tax rate | pervasive under finer split, not just territories; 2014 43-sector had none |
| 20 | `eurostat_reader.py`: `get_total_nonfin_firm_deposits`, `get_total_household_deposits`, `get_total_household_fixed_assets` use `_nearest_balance_sheet_value` + self-recursion guards | **data mapping** — **Diagnosed** (matching diag): firm Deposits NaN for all 50 firms → `get_total_nonfin_firm_deposits(FRA,2022)` returned NaN (FRA has no 2022 col) → NaN firm deposits → NaN bank accounts → `lsa` invalid entries | matching diag now 0 NaN, all regions pass matching | firm/household deposits + fixed assets resolve to nearest populated year | pre-2022 vintage; proxy FRA/GBR |
| 21 | `build_2022_datawrapper.py`: per-region config copies; territories (YT/NT/NU) use `scale=10` (vs 1000) | **DataWrapper integration** (person normalization) — synthetic population raised "Not enough individuals to fill each industry with at least one worker" for a territory: tiny population × scale=1000 < 50 sectors. The task-flagged YT/NT/NU normalization issue | **BUILD COMPLETE (2.8 min)** | territories generate enough synthetic individuals to staff all 50 sectors | territory agent scale differs from provinces (documented); revisit if candidate run needs uniform scale |

| 22 | `exogenous_data.py`: `prepare_labour_stats(base_year=…)` extends labour_stats flat forward when the base quarter is absent (gated, so 2014 unchanged) | **DataWrapper integration** — `Simulation.from_datawrapper` → `Exogenous.__init__` `np.where(unemployment_rate.index=='2022-Q1')[0][0]` `IndexError` (size 0): labour series ends 2021-Q1 while base=2022-Q1 (inflation/HPI reach it). Model slices `iloc[start:start+t_max]` so base quarter must exist | pending rebuild | labour series covers base quarter + horizon | flat-held past last real obs (2021); documented |

| 23 | `icio_reader.py`: `get_intermediate_inputs_matrix` maps non-finite → +inf (matches capital-matrix `fillna(inf)`) | **accounting** — `Simulation` → `economy_ts` `assert output==expenditure GDP: nan`. **Diagnosed** (econ diag): `sectoral_firm_used_ii` NaN for 1 sector in CAN_NL (zero-output coal B05); the intermediate productivity matrix = output/intermediate = 0/0 = NaN, and the model does `production / matrix` → NaN | pending rebuild+smoke | zero-output firms get 0 required intermediates; economy GDP identity finite | needs pickle rebuild |

| 24 | `eurostat_reader.py`: `taxrate_on_capital_formation` gains a `proxy_country=FRA` fallback when the direct (CAN) rate is non-finite | **data mapping** — `Simulation` economy check NaN. **Diagnosed** (econ2 diag): `cf_tax=nan` → cascades to central-gov taxes_on_products + gfcf + household investment. `TaxData` calls it with CAN directly (CAN absent from EU eurostat); the exogenous path already used the FRA proxy (0.2447) | pending rebuild+smoke | central-gov capital-formation tax finite (FRA proxy), matching exogenous path | needs pickle rebuild |
| 25 | `icio_reader.py`: `get_capital_inputs_depreciation` fully zero-safe (0 weights on zero column-sum; capcomp/output=0 where output==0) | **accounting** — firm `total_capital_inputs_bought_costs` NaN for zero-output B05 (idx 3) in CAN_NL. Firm cost = Production × depreciation_matrix (MULTIPLY); rate was inf (capcomp/0) → 0 × inf = NaN. (Intermediate uses DIVISION so inf was safe there; capital needed the opposite) | pending rebuild+smoke | zero-output firms get 0 capital cost | needs pickle rebuild |

| 26 | `default_readers.py`: **moved** the validated capital injection to BEFORE `reconcile_value_added`/`add_investment_matrix`/`match_iot_with_sea`; inject only capital stock + capital compensation, **not** labour comp | **accounting** (design correction) — model economy `output/expenditure GDP` mismatched (ratio 0.697, CAN_NL). **Diagnosed** (compared 2014 balanced vs 2022): `_match_country_iot_with_sea` overwrites SEA capcomp with investment-matrix sums (reconciled to GFCF) and sets labour=VA−capcomp. Injecting raw validated capcomp AFTER match made firm capital cost = capcomp (≈$7.8B) instead of the GFCF-consistent value ($2.3B) → gfcf 3.7× too high. Now validated capcomp feeds only the investment-allocation pattern; the model reconciles the level to GFCF | pending rebuild+smoke | validated capcomp is a drop-in for the WIOD scaffold; economy identity preserved (as 2014); labour derived by the model | capital compensation LEVEL is GFCF-reconciled (model convention), not the raw StatCan level — the validated series drives the sectoral allocation + capital stock |

| 27 | `icio_reader.py`: `get_intermediate_inputs_matrix` non-finite→inf (rebuild) — confirmed init clean, GDP identity balances all 13 regions | (part of #23, re-confirmed after reorder) | smoke: init OK, all regions ratio=1.0000 | — | — |
| 28 | `default_readers.py`: `_floor_empty_provincial_sectors` — tiny (1 CAD-mn) self-consistent output+VA+investment for exact-zero (province,sector) cells | **sector compatibility / DataWrapper integration** — smallest sim iterated then hit `firms.py:1238 assert avg_price>0` (NaN) for zero-output B05; the model's per-firm runtime dynamics degenerate on empty sectors (2014's coarser table had none). Data-level floor avoids editing behavioural code; identity preserved (both GDP sides +ε) | pending rebuild+smoke | empty sectors behave like tiny real sectors | ε negligible (~1e-5 of provincial GDP); documented |

## ✅ Milestone: 2022 DataWrapper built (steps 1–3 complete)

`dev/pkl_files/io2022_13prov_2022.pkl` — **50 OECD sectors × 13 regions** (10 provinces + YT/NT/NU).
`n_sellers_by_industry sum = 50` for every region (all sectors populated). GDP output=expenditure
identity holds to 0.000% for all 13 regions. 21 integration fixes applied; classes: mostly **data
mapping** (exogenous WB/OECD/eurostat year-vintage fallbacks — sources end before 2022), a few
**accounting** (FD folding, finite guards, zero-safe tax rate), **sector compatibility** (OECD-50
global-ICIO scaffold, WIOD bridge), and **DataWrapper integration** (territory scale). No behavioural
equation was changed. Two latent bugs fixed (find_closest_year on empty df; bank-equity infinite
recursion). Remaining known approximations: several exogenous scalars use nearest pre-2022 vintage;
CAN imputed rent 2020-based; territory agent scale=10; employment-share wiring (task) still deferred
to the HFCS fallback.

## ✅ Milestone: initialization coherent + smallest sim runs (steps 4–5 complete)

`dev/io2022/inspect_and_smoke_2022.py`: builds the `Simulation` from the pickle, verifies t0 agent
states, runs 4 quarters. Result after fixes #22–#28:
- **All 13 regions initialize**; economy GDP output==expenditure identity holds to ratio **1.0000**
  for every region (was NaN, then 0.697 before the injection reorder #26).
- t0 agent states finite: firm production / used-intermediate / labour inputs / prices / unemployment
  / gdp_output — **no NaN/inf, no negatives** across all 13 regions.
- Smallest simulation **runs cleanly through 4 quarters**, 0 non-finite production entries.
- `firm_capital_bought_costs` now equals the IO firm GFCF (e.g. NL 1.61B) — capital is investment-flow
  consistent, not the raw StatCan capital-compensation level.

Fixes #22–#28 were all reachable only after init: labour-stats extension to the base year (model
Exogenous), cf_tax FRA-proxy, zero-safe intermediate/depreciation matrices, the injection reorder
(the key accounting correction), and the empty-sector floor. Temporary env-gated diagnostics used to
localize each NaN were removed after diagnosis.

## ⚠️ Step 6–7: candidate run vs 2014 — mechanically coherent, economically INCOHERENT

`dev/io2022/run_candidate_2022.py` (13 regions, 13q, seed 0), classification: **behavioural**
(labour-market / employment), 2022-specific.

| run | real GVA | unemployment | verdict |
|-----|----------|--------------|---------|
| 2022 candidate | 890.2B → **0.0B** (−100%) | 7.9% → **89.5%** | collapse |
| 2022 legacy (defaults) | 893.6B → −0.3B (−100%) | 7.6% → **88.9%** | collapse |
| 2014 candidate (13q, control) | 465.2B → 474.5B (**+0.67%/yr**) | 7.4% → 8.0% | **stable** |

- The collapse is **instantaneous** (single step t0→t1) and **systemic** — it hits Ontario, which has
  zero floored sectors, so it is NOT the empty-sector floor or the territories.
- It occurs under **both** the candidate and shipped-default configs, so it is not the candidate
  growth switches or the exogenous setters.
- **Mechanism (traced, Ontario):** at t1 target production is still healthy (490B) and intermediate
  inputs are fine (490B), but **firm labour input collapses 489.8B → 0.46B** and the wage bill with it
  (274B → 0.28B); production is then labour-starved → mass unemployment → no recovery. The binding
  constraint flips to labour on the first step.
- **Interpretation:** a 2022-specific inconsistency on the **labour-supply / employment / wage** side
  (task-flagged: "employment/person normalization", "wages and labour productivity"). The prime
  suspect is the still-deferred employment-share wiring (task #3): the synthetic population currently
  uses the HFCS (France-proxy) employment distribution/normalization rather than the validated 2022
  StatCan 36-10-0489 shares, so the initial employment / labour-input scale is likely inconsistent
  with the 2022 IO output/wage scale, and the first labour-market clearing wipes out employment.

### Verdict (superseded — see #29 below)
- **Mechanically coherent:** builds, initializes (GDP identity exact for all 13 regions), and runs a
  multi-quarter simulation with no NaN/inf. ✅
- **Economically coherent:** NO — the candidate (and default) run collapses on the first step. ❌
- ~~Prime suspect: employment-share wiring.~~ **This interpretation was WRONG** — the root cause was
  negative capital-composition entries, not employment. See #29.

## ✅ #29: t0→t1 collapse ROOT-CAUSED and FIXED — negative capital composition (2026-08-13)

Classification: **accounting / data mapping** (capital-technology construction), 2022-specific.
NOT behavioural, NOT employment. The Step 6–7 "employment" interpretation above is superseded.

### Root cause (demonstrated, not assumed)
The 2022 OECD-50 provincial capital matrices carried **1646 negative entries** across capital
stock / productivity / depreciation (2014 baseline: **0**). Origin: **negative net Fixed Capital
Formation** for ~2 (province, capital-good) cells each — partly the Changes-in-Inventories fold (#10)
flipping a positive FCF negative (destocking; e.g. ON A02: FCF +1.97, ΔInv −23.7 → −21.8), partly
**raw-negative net fixed FCF** (disinvestment; ON C24A −601, ON C24B −1698, "G" wholesale/retail across
provinces). Across all 13 regions: 118 folded-negative capital cells (89 fold-induced, 29 raw-negative).

**Causal chain (Ontario, traced):** negative net FCF → negative `norm_investment_matrix` → negative
capital coef/stock/dep. At t0, (neg coef)×(neg stock) = **positive**, so `limiting_capital` is
coincidentally correct and the GDP identity holds ("constructed"). After one step,
`firms.compute_capital_inputs_stock` applies `np.maximum(0, stock−used+bought)` → floors the negative
stock to 0; then `compute_limiting_capital_inputs_stock = min_g(coef×stock)` hits (neg coef)×0 = **0** →
with `consider_capital=1.0, consider_intermediate=0.0`, `desired_labour = min(target, 0) ≈ 0` → labour
market fires ~98% (ON employed 6979→117) → production labour-starved → real GVA→0, unemployment→~89%.
Config-independent and systemic because every province has negative-FCF cells.

### Fix — ACCOUNTING net investment ≠ CAPITAL-TECHNOLOGY composition
`icio_reader.py`: new `_prefold_capital_composition(country)` sources the capital-goods composition from
**pre-fold Fixed Capital Formation** (snapshot taken in `default_readers.py` BEFORE the #10 inventory
fold, stored as `ICIOReader._prefold_fcf_block`), clips negatives→0, normalizes over positives; if a
region has no positive cell it makes that capital channel **non-binding** (inf coefficient) and warns —
it does not invent a distribution. Used consistently in `get_capital_inputs_matrix` (productivity) and
`get_capital_inputs_depreciation`; `capital_inputs_stock` inherits non-negativity via `Production/cap_prod`.
- **Changes in Inventories NEVER enter capital technology** (rule 1).
- **Observed net FCF (incl. negatives) preserved in accounting/FD**; `investment_matrices` →
  capital-compensation reconciliation → GDP identity all **untouched** (rule 2).
- Clamp is on the **weight** (→ inf coef, non-binding), NOT the coefficient (→ 0 would bind at zero).
- `None` fallback when no pre-fold snapshot exists ⇒ **legacy 2014 behaviour unchanged**.
- No behavioural equation changed (rule 5).

### Validation — staged pickle `dev/pkl_files/io2022_13prov_2022_capfix.pkl`
Exact commands:
```
uv run python dev/io2022/build_2022_datawrapper.py --pickle dev/pkl_files/io2022_13prov_2022_capfix.pkl --force --build-only
IO2022_PKL=dev/pkl_files/io2022_13prov_2022_capfix.pkl uv run python dev/io2022/run_candidate_2022.py --quarters 13 --legacy
```
Results:
- Negative capital stock/productivity/depreciation entries: **0** (was 1646). ✅
- GDP output==expenditure identity: **1.00000 for all 13 regions** (unchanged). ✅
- **t0→t1 labour collapse ELIMINATED.** Legacy/default 13q: real GVA **893.6B → 822.8B**
  (−7.9% cumulative; was → 0). ON + all 10 provinces stable (ON ~6760 employed through the run). ✅
- Smallest sim (4q, default): **0 non-finite**, large provinces stable. ✅

**Scope statement: the capital-treatment implementation is VALIDATED. The overall 2022 integration is
NOT yet "production-ready"** — see #30 and the remaining-items list.

## ⚠️ #30: candidate-growth t2 collapse is a SEPARATE growth-baseline issue (NOT the capital fix)

For **integration acceptance use the simplest/default 2022 baseline** (no candidate growth overlays).
The candidate baseline (`run_candidate_2022.py` without `--legacy`) was built for the separate
real-growth problem and adds demand/inventory dynamics (rolling capital, unmet-demand memory, demand
smoothing/growth-response, ExogenousLabourForcePath, +2%/q household-demand overlay) that must NOT be
conflated with basic 2022 DataWrapper integration.

With the capital fix in place, the candidate 13q run still collapses, but at a **t2 cliff** (real GVA
883B → 52B), via **`limiting_intermediate` depletion** (ON limInt 489.8B → 2.7B) after the demand overlay
pushes demand (609B) past intermediate supply — the known **"intermediate lock" / demand-channel** area,
NOT capital (capital is non-binding there). Small-region residuals: PEI = same intermediate depletion;
YT/NT/NU = the `scale=10` #21 territory hack. **Classified as a separate growth-baseline / demand-channel
issue; explicitly NOT a failure of the capital fix. Deferred — do not diagnose or fix here.**

## ✅ #31: 2022 labour initialization — StatCan 36-10-0489 employment shares WIRED (2026-08-13)

Classification: **data mapping** (employed-person structure). Simple/default baseline only.

Previously the province×sector employment (headcount) came entirely from the HFCS (France-proxy)
aggregate distribution split by **output** shares (`reassign_industries`); the validated 36-10-0489
shares were prepared but unwired.

**Change.** `_load_can_2022_employment_shares` (in `default_readers.py`) loads the validated shares and
stashes them on the SEA reader inside `inject_can_provincial_socioeconomic_2022`;
`reallocate_employment_by_shares` (`synthetic_population/utils.py`) reassigns employed individuals'
`Employment Industry` to those shares, applied in `synthetic_country` build **after** the population is
built and **before** firms inherit `number_employees_by_industry` (both proxied and EU paths). Every
sector floored at ≥1 worker (mirrors `ensure_minimum_workers_in_industries`; StatCan has exact-zero
cells and the model builds one firm per sector). Only the sector label changes — activity status,
income, household links, the sector wage bill (SEA Labour Compensation), and value added are untouched.
No behavioural equation changed.

**Validation** (`dev/pkl_files/io2022_13prov_2022_labourfix.pkl`; build cmd as #29 with that path):
- Realized vs target shares: large provinces match closely (ON L1=0.008, corr≈1.000; QC/AB/BC/MB/SK
  L1≤0.10). Small provinces are min-1-floor-dominated (NL/NB/NS L1 0.15–0.22; **PEI L1=0.92**, only 61
  synthetic employed across 50 sectors — a `scale`/#21 artifact, not a wiring error). corr ≥0.90 all.
- GDP identity still **1.00000 all 13 regions** (0 off). ✅
- wage/worker & labour productivity finite and plausibly ordered; 1 non-positive wage/worker per province
  = a zero-labour-comp sector forced to 1 worker (the #28 zero-sector interaction).
- t0→t1 stable (ON ~6910 employed), 4q smoke 0 non-finite.
- **Simple/default 13q improved vs capital-only**: real GVA 894.5B→875.7B (−2.1%, was −7.9%);
  unemployment 7.7%→25.6% (was →35.8%). No collapse.

**Wages assessment (now resolved — see #32).** Earlier deferred; observed compensation was in fact
available in the io2022 canonical layer.

## ✅ #32: observed compensation of employees WIRED (PRM500000 + PRM600000) (2026-08-13)

Classification: **data mapping** (firm wage bill). Simple/default baseline only. Capital/GFCF untouched.

The firm wage bill was the residual `Labour Compensation = VA − GFCF-reconciled capcomp`, which
over-stated labour (GFCF ≪ true operating surplus). Model expectation is **Option B** (proven from the
equations): `add_wages` sets `Total Wages = labour_compensation/(1+tau_sif)` and
`Total Wages Paid = labour_compensation`; firm `labour_costs = Total Wages·(1+tau_sif) = labour_compensation`.
So the input **is total compensation of employees**, and `tau_sif` only splits it (wages vs employer part);
firm labour cost = CoE for any `tau_sif`.

**Change.** New input `dev/raw_data/can_2022/compensation_of_employees_oecd50_by_province_CADmillions.csv`
(built from `macroabm-io2022/canonical/VA_tax_output_basic.csv`: `wages_salaries`=PRM500000,
`employers_social_contributions`=PRM600000). `_load_can_2022_compensation_of_employees` stores per-region
CoE (=wages+employer, ×1e6) and the employer/wages ratio on the SEA reader.
`_match_country_iot_with_sea` sets `Labour Compensation = observed CoE` for 2022 provinces (same annual
CAD-abs units as `new_va = annual IO VA`), instead of the residual — **Capital Compensation stays
GFCF-based** (investment allocation + depreciation rate), VA unchanged. `read_tau_sif` (single source for
both the wage split and the firm/government tax side) returns the observed per-province employer ratio,
so the split matches PRM500000/PRM600000. Dependency basis: the GDP identity is output/expenditure-based
and uses neither compensation field; GOS auto-recomputes as `Output − CoE − intermediate − taxes`.

**Validation** (`dev/pkl_files/io2022_13prov_2022_wagefix.pkl`):
- Firm labour cost / observed CoE = **1.30 uniformly** all provinces (the pre-existing USD→CAD factor
  carried by every CAD magnitude — VA/output/capital); wages/PRM500000 = employer/PRM600000 = 1.30 too,
  so **share and split are exact**. `tau_sif` now per-province 0.13–0.18 (was 0.022) = observed ratio.
- Scale-adjusted wage/person: ON ≈ 91k, AB ≈ 56k CAD/yr (÷scale) — O(10⁴–10⁵), economically sane vs the
  per-agent ~2.7e7 (resolves the scale red flag). `number_employees_by_industry` = synthetic agents,
  agent ≈ `scale` persons; the wage bill is full-scale so per-agent wage = scale × per-person.
- GDP identity **1.00000 all 13 regions** (0 off).
- t0→t1 stable (ON ~6910), 4q smoke 0 non-finite, 13q simple/default no collapse
  (real GVA 894.5B→849.1B, −5.1%; unemployment 7.7%→31.9% — slightly higher drift than the wage-residual
  run because the correct, lower wage bill feeds less household income; still the separate small-region /
  demand-channel drift, not a collapse).

## ✅ #33: removed the spurious USD→CAD (~1.30) inflation for the 2022 CAN path (2026-08-13)

Classification: **units / currency**. No economic equation changed. Capital/GFCF untouched.

The 2022 provincial IO and the canonical VA/compensation inputs are **already in CAD**, but the generic
pipeline labels SEA/IO values "USD" and converts to LCU via `ExchangeRatesReader.from_usd`
(`from_usd_to_lcu`), which returned the market rate `from_usd(CAN, 2022) ≈ 1.30`. That factor was applied
to every CAD magnitude in `industry_extraction` (`"... in LCU" = value × exchange_rate`) and the
firm/bank/government/emissions builders, inflating VA/output/CoE by ~1.30 (this was the "uniform 1.30" in
#32). Because it was uniform it cancelled in ratios and the GDP identity, so it was invisible there — but
absolute CAD levels were 1.30× reality.

**Change (SCOPED — not a global override).** A first pass globally forced `from_usd(CAN,2022)=1.0`, but a
caller audit found **both** source families: CAD-native 2022 IO/SEA **and** genuinely USD-denominated
Compustat bank balance sheets (`default_synthetic_banks` `get_country_data(exchange_rate=…)`). A global
override wrongly zeroes the bank USD→CAD conversion. So the bypass lives on the **CAD-native IO/SEA
ingestion path only**: new `ExchangeRatesReader.from_usd_to_lcu_io` returns 1.0 for CAN+2022 (real rate
otherwise), used at `industry_extraction` (industry_vectors: output/VA/labour/capital/consumption/trade)
and the firm **price numeraire** (`default_synthetic_firms`, `Price = Price in USD × exchange_rate`, must
match the CAD vectors). `from_usd`/`from_usd_to_lcu` stay generic, so Compustat banks keep the real
USD→CAD rate. Scoped to CAN+2022 (2014 baseline and other countries untouched); no economic equation
changed.

**Caller audit** (every `from_usd(CAN,2022)` in the 2022 build):
| caller | source | native ccy | classification |
|---|---|---|---|
| `industry_extraction:40` industry_vectors | 2022 provincial IO + injected SEA | CAD | CAD-native → **1.0** |
| `default_synthetic_firms:157` price numeraire | IO price base | CAD | CAD-native → **1.0** |
| `default_synthetic_banks:291` Compustat | Compustat balance sheets | USD | genuinely USD → **keep ~1.30** |
| `default_readers:806/823` gov debt / WB exports | OECD / World Bank | (LCU per docstring) | external, out of scope → unchanged |
| `data_wrapper:303/330` emissions | emission factors | output-tied | conditional, unchanged |
| `industry_extraction:63/219/252`, ROW / historical | OECD ICIO (2010-19) | USD | keep real rate (io returns real for year≠2022) |

**Validation** (`dev/pkl_files/io2022_13prov_2022_cadscoped.pkl`; annual CAD bn):
- CoE **1386.3** / wages **1202.4** / employer **183.9** = canonical **exactly**.
- **Nominal VA reconciliation (like-for-like):** DataWrapper nominal VA = the IO `("TOTAL","Value Added")`
  row that `get_value_added` reads = **2674.18B** vs canonical **2674.953B** → gap **0.77B (0.03%)**
  (valuation/rounding between the compat OECD-50 IO and the canonical VA breakdown — same StatCan SU;
  not aggregation, not currency). The earlier "~2.6%" was an artefact of comparing firm-based
  double-deflated **real GVA** (2746B), a transformed quantity that differs from nominal VA by the
  synthetic-firm construction (integer firm counts, #28 floor, single-firm rounding).
- Compustat banks **preserved** (ON Equity 5.06e11, Deposits 2.53e11 — not zeroed).
- GDP identity **0/13 off**; 4q smoke stable, 0 non-finite (real GVA 686.5→654.7B/qtr).

## 🏁 #34: integration acceptance run + LOCAL CHECKPOINT (2026-08-13)

**Local checkpoint:** commit `e9346ff75e63de6944744635d50fd6df2eae9e54` on `feature/io-2022-integration`
(not pushed; `real-growth-baseline` untouched at `d11edc1`).

**13q simple/default acceptance** (`dev/pkl_files/io2022_13prov_2022_accept.pkl`; candidate-growth NOT run):
- t0 GDP identity: **13/13 balanced**
- NaN/inf over 13q (production/intermediate/labour): **0**
- national real GVA: **687.3B → 646.4B (−6.0%)**
- unemployment: 7.7% → 35.7%
- small-region catastrophic collapse (end → ~0): **NL, PE, NB, YT, NT** (large provinces hold)

**Status:**
- Capital treatment — **validated** (#29).
- Canadian StatCan 36-10-0489 employment shares — **wired** (#31).
- Observed compensation of employees / wages / employer contributions — **wired** (#32).
- CAD-native IO currency handling — **validated** (#33).
- Candidate-growth baseline — **PARKED** (#30).
- **Overall 2022 integration NOT yet complete**: mechanically stable nationally (0 NaN/inf, identity
  holds) but the **small-region mechanics fail** (NL/PE/NB/YT/NT collapse over 13q).

**Next task (explicit, in order):**
1. Zero-sector handling — replace the ε floor (#28) with principled model-side handling.
2. Principled small-region synthetic-population scaling — per-province `scale` so small
   provinces/territories carry enough agents to express 50-sector shares without the ≥1-worker floor
   injecting `scale` phantom persons per empty sector (supersedes the #21 scale=10 hack).
3. Rerun the simple/default 13q baseline and confirm the small-region collapse is resolved.

**Deferred until after regional mechanics are stable:** HFCS-2021 Canadianization; post-2022
external-series / vintage work.

## ✅ #35: trade-allocation proportions fixed — small-region collapse RESOLVED (2026-08-13)

Classification: **orientation/indexing + allocation-layer construction**. No accounting IO flow changed;
goods-market algorithm, min-fill, scaling, and zero-sector handling untouched.

The small-region collapse (NL/PE/NB/YT/NT) was traced past capital, employment, CoE, currency, and
accounting to the **goods-market `origin_trade_proportions`** — not a supply deficit (t0 accounting is
balanced; the commodity-output the model reads already covers domestic sourcing). Two construction bugs:

1. **Country-ordering bug (primary).** The proportion DataFrames are `sort_index()`-ed (alphabetical) but
   `simulation.py` fed `.values` to the goods market, which indexes countries in **participant order**
   (`NL,PE,NS,NB,QC,ON,…`). The two orders differ, so both origin and destination axes were permuted —
   buyers were told to source e.g. C24B from AB/YT (non-producers; AB asked 6.11B, produces 0.44B) with
   ON asked for negative. **Fix:** `simulation.py` explicitly reindexes origin/destination proportions to
   `all_country_names` order before `.values` (no reliance on sort/insertion order).

2. **Negative sourcing shares (secondary).** ACCOUNTING use flows can be negative (net-disinvestment /
   folded Changes-in-Inventories cells in C24A/C24B/B07/B08), so `get_trade`-based shares went <0 (domestic
   self-share) and >1 (import share) for those metals. SOURCING shares must be actual purchases ∈ [0,1].
   Compared two fixes: **A** clip the net flow to 0 — rejected, it zeroes the *producer's own* domestic
   sourcing (ON-C24B net −5498 → 0, forcing ON to import all its C24B). **B** build the basis from
   **positive-purchase components** (positive intermediate + positive final; exclude negative inventory /
   disposal FCF) — recovers ON-C24B = 3891 (correct). A and B differ materially; **B implemented.**
   `icio_reader.py`: new `_positive_sourcing_flow` (element-wise `clip(lower=0)` of `iot.loc[start,end]`)
   used in `get_origin/destination_trade_proportions`, normalized by the sum of positive flows. `get_trade`
   and all IO/accounting flows are untouched.

**Validation** (`dev/pkl_files/io2022_13prov_2022_tradefix.pkl`; run `dev/io2022/run_simple_baseline_2022.py`):
- Every origin share ∈ **[0,1]** (0 negative, 0 >1); sums to 1 per destination×good (699/700 — the one
  exception is **ROW·T**, a good with zero positive sourcing anywhere → all-zero vector, benign).
- C24A/C24B sourcing points to the actual producers (ON/QC); ordering intact.
- t0 per-good restocking for PE/NL/NB/YT/NT = **1.00** (was ~0).
- **13q simple/default: real GVA 687.3B → 676.9B (−1.5%); unemployment 7.7% → 9.1%; all 13 regions stable
  (no collapse); 0 NaN/inf.** 4q: 687.3B → 686.3B, u 7.7→8.0%, 0 NaN/inf.

**Status:** the small-region collapse is resolved on the simple/default baseline. **Scaling (#21) and
zero-sector cleanup (#28) are deferred — they are no longer blockers** (the ε floor + scale=10 remain as
harmless placeholders; principled replacements are quality improvements, not stability fixes).

## Household economic block — Canadianized MVP integration (2026-08) [DataWrapper integration]

The validated Canadian household block is now wired into the 2022 DataWrapper (MVP), gated behind a
`canadianized_can_households_csv` config flag for CAN-2022. Behavioural equations unchanged.

**Integration seam (explicit CAN-2022 branch; legacy/raw-HFCS path untouched):**
- `macro_data/readers/population_data/canadianized_household_adapter.py` (new) — schema adapter mapping the
  validated `prototype_household_consumption.csv` onto the model household schema. No validated economic
  magnitude changes; CIS 2022 income-share split for financial/pension/transfers; rental = documented
  `rental_gross_yield` residual (owners only) that the housing build rescales to observed Rent Paid.
- `default_readers.py` — CAN-2022 branch: load the Canadianized households_df directly + the FULL
  pooled-European individuals (`no_country_filter=True`, HFCS reader) so the member skeleton spans the same
  83,162-household ID space (exact household↔individual linkage); sets `reader.cad_native = True`.
- `hfcs_reader.py` — `no_country_filter` option on `read_csv`/`from_csv`.
- `hfcs_synthetic_population.py` — Canadianized households **bypass EUR→CAD** conversion (`cad_native`);
  pooled-European individuals still convert **once**. `reconcile_labour_income()` (Option B) resets the
  household labour term to `validated_income − Canadian non-labour`, rescaling members multiplicatively
  (within-household shares preserved), so pre-matching household Income matches the validated Canadian
  distribution. **Observed CoE firm wage bill and 36-10-0489 employment are untouched**; downstream
  `match_individuals_with_firms` (`normalise_employee_income=True`) still renormalizes individual employee
  incomes to the CoE-driven firm wage bill.

**What is Canadian vs still national/European (MVP):**
- Canadian: household income (distribution + level), wealth, debt, tenure (0.654), consumption propensity
  (APC≈0.82), household counts (per-province via population ratio), employment industry (36-10-0489),
  firm wage bill (observed CoE $1.39T annual).
- Still pooled-European: individual demographic/member skeleton (age/sex/education/composition) and the
  within-household member income split. Individuals are NOT Canadianized (deferred).
- National household distribution is replicated across all 13 provinces (no provincial household
  heterogeneity yet); provincial overlays (count, employment, IO/bank anchoring) still apply.

**Income-floor limitation (~11% weighted):** for households whose model-imputed **social transfers**
exceed their validated total income, the labour residual floors at 0 and household Income slightly exceeds
validated. Concentrated in the **bottom income quintile** (54% of Q1; <0.5% of Q2–Q5), spread across wealth
(nwQ1 22% → nwQ5 5%). Driver = the model's **endogenous social-transfer imputation** (regression on
income/debt rescaled to `total_social_transfers`, `set_household_social_transfers`), NOT the adapter's
mapping (the adapter's own transfers are a CIS share of income, always < income, and are overwritten by the
model) and NOT the wealth→financial-income rule (financial is minor among floored). Aggregate income
overshoot **+1.1%**. Documented MVP limitation; no household redesign.

**13q simple/default baseline (Canadianized) vs pre-household checkpoint:**
- real GVA **687.3B → 676.0B (−1.6%)** vs 687.3 → 676.9B (−1.5%) — essentially identical; t0 GVA matches.
- unemployment **7.6% → 9.8%** vs 7.7 → 9.1% (t0 matches; +0.7pp at horizon, household-demand driven).
- all 13 regions stable (no collapse); **0 NaN/inf**. 4q: 687.3 → 686.3B, u 7.6→8.0%, 0 NaN/inf.

**Status:** household economic block integrated and stable on the MVP baseline. Deferred: individual
Canadianization, provincial household distributions, the income-floor refinement.
