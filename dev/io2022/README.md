# MacroABM-CA — 2022 Provincial IO Integration

> **Status: work in progress** (branch `feature/io-2022-integration`). The 2022 base year builds and
> runs on the simple/default baseline; it is **stable over 13 quarters — all 13 regions, no collapse,
> 0 NaN/inf**. **Canonical baseline (2026-08-19, provincial 2022 labour init adopted): real GVA
> 687.3B→684.4B (−0.4%, seed 0); unemployment mean 6.1→7.0%; national t0 unemployment 5.34% ≈ StatCan
> 5.3%; 5-seed mean real-GVA change −0.97% (sd 0.50), all negative; 5-seed mean Δu +1.78pp, all rising.**
> t0 unemployment/participation now match StatCan 14-10-0327 by province (participation on the age≥16
> base); territories use a documented national fallback and PEI carries a small-population granularity
> caveat. The earlier small-region collapse is resolved (INTEGRATION_LOG #35). See
> [Status & roadmap](#status--roadmap).

Integration of Statistics Canada's 2022 provincial data into the MacroABM-CA DataWrapper: the new
data, build/run instructions, model changes, and remaining work. Behavioural equations are unchanged;
the work is data mapping and calibration.

- Detailed change log (provenance): [`INTEGRATION_LOG.md`](INTEGRATION_LOG.md) (entries #0–#34)
- IO table pipeline (separate repo): `github.com/esizadi/macroabm-io2022` (private) — produces the
  2022 provincial IO table and the validated province×sector inputs used here.

---

## 1. Scope

The 2022 base year replaces the legacy 2014 provincial table (10 provinces × 43 sectors) with a
**13-region × OECD-50-sector** table (10 provinces + territories YT/NT/NU) and wires in validated 2022
StatCan capital, employment, and compensation data.

---

## 2. New data

All 2022 inputs are produced by the `macroabm-io2022` pipeline from StatCan sources and placed under the
model's `raw_data_path` (`dev/raw_data/`). They are not committed to this repo (policy: no raw/large
data) — see [Inputs](#3-inputs).

| file (under `dev/raw_data/`) | contents | source |
|---|---|---|
| `icio/icio_2022_can_provinces.csv` | 2022 provincial IO table, 13 regions × OECD-50 (~7.9 MB) | `macroabm-io2022` compatibility output `icio_2022_can_provinces_oecd50.csv` |
| `can_2022/capital_stock_end2021_oecd50_by_province_CADmillions.csv` | opening net capital stock (end-2021) | StatCan 36-10-0096 |
| `can_2022/capital_compensation_oecd50_by_province_CADmillions.csv` | capital compensation (GOS + mixed income + net production tax) | 2022 IO VA breakdown |
| `can_2022/employment_shares_oecd50_by_province.csv` | province×sector employment shares | StatCan 36-10-0489 |
| `can_2022/compensation_of_employees_oecd50_by_province_CADmillions.csv` | wages (PRM500000) + employer social contributions (PRM600000) | 2022 IO VA breakdown |
| `can_2022/labour_2022_by_province.csv` | province t0 unemployment + participation rates (fractions) | StatCan 14-10-0327 (2022 annual, 15+, Total-Gender); rates ÷100. Territories YT/NT/NU = national fallback (table omits them) |

The 2022-specific bundle is ~7.6 MB.

---

## 3. Inputs

`dev/raw_data/` must contain two things:

1. **Base MacroABM-CA inputs** — the standard model `raw_data_path` (`hfcs/`, `wiod_sea/`, `oecd_econ/`,
   `exchange_rates/`, `eurostat/`, `world_bank/`, …). Large and private; not part of the 2022 work and
   not in the repo. The 2022 model will not run on the 2022 files alone.
2. **2022 delta (~7.6 MB)** — the five files in §2, placed as:

```text
raw_data_path/
  icio/icio_2022_can_provinces.csv
  can_2022/
    capital_stock_end2021_oecd50_by_province_CADmillions.csv
    capital_compensation_oecd50_by_province_CADmillions.csv
    employment_shares_oecd50_by_province.csv
    compensation_of_employees_oecd50_by_province_CADmillions.csv
    labour_2022_by_province.csv
```

`labour_2022_by_province.csv` is derived from StatCan **14-10-0327** (Labour force characteristics,
2022 annual, age 15+, Total-Gender): columns `region, unemployment_rate, participation_rate, source`
with rates as fractions (StatCan percent ÷ 100). It sets each province/territory's **t0** activity split
(loaded via `_load_can_2022_provincial_labour`, resolved from the normal `can_2022` data root, wired
through `synthetic_country` → `SyntheticHFCSPopulation.from_readers`); it is **not** a forward path.
Territories (YT/NT/NU) use a national fallback (14-10-0327 omits them); PEI has a small-population
granularity caveat.

The delta is a StatCan-derived output of the private `macroabm-io2022` pipeline; its
`compatibility/icio_2022_can_provinces_oecd50.csv` (→ `icio/icio_2022_can_provinces.csv`) and
`integration_2022_inputs/` files are the canonical source. The compensation file is prebuilt into the
bundle; `prepare_compensation_input.py` only regenerates it from that pipeline.

---

## 4. Build & run

From the repo root, with `dev/raw_data/` populated per §3:

```bash
# Build the 2022 DataWrapper (13 regions × OECD-50) -> dev/pkl_files/io2022_13prov_2022.pkl
uv run python dev/io2022/build_2022_datawrapper.py --force

# Simple/default baseline, 13 quarters (the accepted integration baseline)
uv run python dev/io2022/run_simple_baseline_2022.py --quarters 13
```

- `run_simple_baseline_2022.py` runs the shipped-defaults (no growth overlays) baseline and reports real
  GVA start→end, unemployment, per-province GVA, NaN/inf, and any collapse. This is the validated run.
- The candidate **growth** baseline (`run_candidate_2022.py`, no `--legacy`) is parked (a separate
  demand/intermediate collapse, INTEGRATION_LOG #30) and is not a measure of the 2022 wiring.
- `build_2022_datawrapper.py` reads `dev/raw_data/` and writes `dev/pkl_files/io2022_13prov_2022.pkl`;
  the run script reads that pickle (override with `IO2022_PKL=<path>`). Build takes ~2–3 min.

Validated simple/default 13q result (INTEGRATION_LOG #35): GDP identity balances for all 13 regions at
t0; 0 NaN/inf; real GVA **687.3B → 676.9B (−1.5%)**; unemployment **7.7% → 9.1%**; **all 13 regions
stable, no collapse**.

---

## 5. Model changes

Data/calibration only — no behavioural equations changed. Detail in `INTEGRATION_LOG.md`.

| area | change | log |
|---|---|---|
| Capital treatment | Capital-technology composition sourced from **pre-fold** fixed capital formation (inventories excluded), negatives clipped to zero — fixes a t0→t1 collapse from negative capital entries. Accounting net investment ≠ capital-technology composition. | #29 |
| Employment structure | Province×sector headcount wired to **StatCan 36-10-0489** shares (was HFCS France-proxy split by output). | #31 |
| Firm wage bill | Set to **observed compensation of employees** (PRM500000 wages + PRM600000 employer contributions); `tau_sif` = observed per-province employer ratio. Was the `VA − capital-comp` residual (over-stated). | #32 |
| Currency handling | `from_usd_to_lcu_io` stops the spurious ~1.30 USD→CAD conversion on the **CAD-native** 2022 IO/SEA inputs (Compustat USD data still converts). Model VA/output/compensation now match canonical 2022 CAD. | #33 |
| Trade allocation | Goods-market `origin/destination_trade_proportions`: (a) `simulation.py` reindexes to `all_country_names` order before `.values` — fixes a country-ordering permutation that routed sourcing to non-producers; (b) `_positive_sourcing_flow` builds sourcing shares from **positive-purchase** flows (clip negative inventory/disposal cells), keeping shares ∈ [0,1]. Accounting IO flows untouched. Resolves the small-region collapse. | #35 |
| Labour initialization | Per-province t0 unemployment/participation from **StatCan 14-10-0327** (2022 annual, 15+) replace the single national IMF/WB base rate. Gated CAN-2022 override passed through `synthetic_country`→`SyntheticHFCSPopulation.from_readers` (loaded via `_load_can_2022_provincial_labour`); **t0 initialisation only — no forward path, labour stays endogenous.** Territories use a national fallback (table omits YT/NT/NU); PEI has a small-population granularity caveat. | #36 |

---

## 6. Status & roadmap

**Validated (simple/default baseline):**
- 2022 DataWrapper builds and initializes; GDP identity balances for all 13 regions.
- Capital treatment, employment shares, observed compensation of employees, CAD-native currency.
- **Trade allocation (#35): all 13 regions stable over 13q (no collapse, 0 NaN/inf); the small-region
  collapse is resolved.**

**Deferred — quality improvements, no longer blockers:**
1. **Zero-sector handling** — genuinely-empty (province, sector) cells still use the ε floor
   (`_floor_empty_provincial_sectors`, #28); replace with principled model-side handling. Harmless
   placeholder now that trade allocation is fixed.
2. **Small-region synthetic-population scaling** — territories still use `scale=10` (#21); a principled
   per-region rule is a resolution/quality improvement, not a stability fix (the collapse it was blamed
   for was actually the trade-allocation bug, now fixed).

**Deferred (until otherwise scheduled):**
- Candidate growth baseline (parked, #30).
- Post-2022 external-series / vintage inputs.

---

## 6a. Next Phase: 2022 Economic Baseline Validation

**Accepted state (do not reopen — see DO-NOT-REOPEN below):**
- 2022 IO/DataWrapper integration mechanically stable; GDP identity balances all 13 regions.
- Validated: capital treatment, trade allocation, employment shares (36-10-0489), observed CoE,
  CAD-native currency, **household Canadianization** (Canadian household MVP integrated, `d74f732`).
- Simple/default 13q after household integration: GVA **687.3 → 676.0B (−1.6%)**, unemployment
  **7.6% → 9.8%**, all 13 regions stable, **0 NaN/inf**.
- Remaining household limitations (pooled-European individual/member skeleton; national distribution
  replicated across provinces; ~11%-weight transfer-imputation income floor) are **deferred, not blockers**.

**Next work, in order:**
1. **Active external-input audit.** Trace ONLY the external inputs actually on the current 2022
   simple/default build+run execution path. Classify each as: Canadian + 2022-consistent / Canadian but
   stale or nearest-year fallback / foreign proxy / behavioural-calibration parameter (not observed data) /
   initialization-only vs runtime/time-varying. The earlier audit flagged possible remaining
   Eurostat/ECB/France proxies (esp. financial / interest-rate and initialization inputs) — these must be
   **rechecked against the actual active path before any replacement**.
2. **Economic baseline decomposition.** Explain the remaining 13q drift as economics, not a crash.
   Decompose the path into at least: household consumption, government demand, investment, exports,
   inventories/intermediate-input dynamics, imports, production/capacity/productivity, labour
   demand/employment. Classify the −1.6% GVA / +2.2pp unemployment path as **DATA ISSUE** vs
   **CALIBRATION / NON-STEADY-STATE ISSUE** vs **EXPECTED MODEL BEHAVIOUR**.
3. **Targeted data/calibration updates.** Replace or recalibrate ONLY inputs that steps 1–2 show
   materially move the baseline. Do NOT broadly modernize every external series just because newer data
   exist.
4. **Post-2022 / real-growth phase.** Only after the static 2022 baseline is economically understood:
   determine which variables genuinely need forward time paths; update Canadian series
   (labour force/population/inflation/rates/productivity/demand/exports) where justified; then return to the
   parked candidate real-growth baseline. Distinguish **STATIC 2022 INITIALIZATION** from **POST-2022
   EXOGENOUS PATHS** from **ENDOGENOUS MODEL DYNAMICS**.

**DO-NOT-REOPEN (validated integration components):** capital treatment (#29), trade allocation (#35),
employment shares 36-10-0489 (#31), observed CoE (#32), CAD-native currency (#33), and the household
Canadianization block (SFS 2023 joint transplant, survey-weighted deciles + age matching, CHS 2022 tenure
65.41%, CIS 2022 income reconciliation, SHS 2023 consumption propensity, 15.455M weight rescale, Option B
labour-income reconciliation).

---

## 7. Layout

```text
dev/io2022/
  README.md                      this document
  INTEGRATION_LOG.md             detailed change log (#0–#35)
  NEW_THREAD_HANDOFF.md          working handoff / forensic notes
  build_2022_datawrapper.py      builds the 2022 DataWrapper pickle
  run_simple_baseline_2022.py    runs the validated simple/default 13q baseline
  run_candidate_2022.py          candidate growth baseline (parked, #30)
  prepare_compensation_input.py  regenerate the CoE input from the io2022 pipeline
  inspect_and_smoke_2022.py      quick init/smoke inspection
```

Code changes are in `macro_data/` (readers, synthetic population/firms); see the log for exact files.

---

## Maintenance

For each further 2022 change: add a numbered entry to `INTEGRATION_LOG.md`
(change | reason | validation | remaining), then update the affected row/section here (Model changes /
Status & roadmap) and the status banner. Keep this document a summary with pointers; keep detail in the log.
