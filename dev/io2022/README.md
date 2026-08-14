# MacroABM-CA — 2022 Provincial IO Integration

> **Status: work in progress** (branch `feature/io-2022-integration`). The 2022 base year builds and
> runs on the simple/default baseline; it is mechanically stable nationally (no NaN/inf, GDP identity
> holds) but five small regions collapse over a 13-quarter run — see [Status & roadmap](#status--roadmap).

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
```

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
uv run python dev/io2022/run_candidate_2022.py --quarters 13 --legacy
```

- `--legacy` selects the simple/default (shipped-defaults) baseline. Omitting it runs the candidate
  growth baseline, which is parked (a separate demand/intermediate collapse, INTEGRATION_LOG #30) and is
  not a measure of the 2022 wiring.
- `build_2022_datawrapper.py` reads `dev/raw_data/` and writes `dev/pkl_files/io2022_13prov_2022.pkl`;
  the run script reads that pickle (override with `IO2022_PKL=<path>`). Build takes ~2–3 min.

Expected simple/default 13q result (INTEGRATION_LOG #34): GDP output==expenditure identity balances for
all 13 regions at t0; 0 NaN/inf; national real GVA ≈ −6% over 13q; five small regions (NL, PE, NB, YT,
NT) collapse (known WIP, §Status). Large provinces are stable.

---

## 5. Model changes

Data/calibration only — no behavioural equations changed. Detail in `INTEGRATION_LOG.md`.

| area | change | log |
|---|---|---|
| Capital treatment | Capital-technology composition sourced from **pre-fold** fixed capital formation (inventories excluded), negatives clipped to zero — fixes a t0→t1 collapse from negative capital entries. Accounting net investment ≠ capital-technology composition. | #29 |
| Employment structure | Province×sector headcount wired to **StatCan 36-10-0489** shares (was HFCS France-proxy split by output). | #31 |
| Firm wage bill | Set to **observed compensation of employees** (PRM500000 wages + PRM600000 employer contributions); `tau_sif` = observed per-province employer ratio. Was the `VA − capital-comp` residual (over-stated). | #32 |
| Currency handling | `from_usd_to_lcu_io` stops the spurious ~1.30 USD→CAD conversion on the **CAD-native** 2022 IO/SEA inputs (Compustat USD data still converts). Model VA/output/compensation now match canonical 2022 CAD. | #33 |

---

## 6. Status & roadmap

**Validated (simple/default baseline):**
- 2022 DataWrapper builds and initializes; GDP identity balances for all 13 regions.
- Capital treatment, employment shares, observed compensation of employees, CAD-native currency.

**In progress:**
1. **Zero-sector handling** — genuinely-empty (province, sector) cells use an ε floor
   (`_floor_empty_provincial_sectors`); replace with principled model-side handling.
2. **Small-region synthetic-population scaling** — small provinces/territories have too few synthetic
   agents to express 50-sector shares (e.g. PEI ≈ 61 employed across 50 sectors), and the ≥1-worker
   floor injects phantom employment. This is why NL/PE/NB/YT/NT collapse over 13q. Needs per-region
   scaling (supersedes the `scale=10` territory hack).
3. **Rerun** the simple/default 13q baseline and confirm the collapse is resolved.

**Deferred (until regional mechanics are stable):**
- HFCS-2021 Canadianization (household block still uses the raw European wave).
- Candidate growth baseline (parked, #30).
- Post-2022 external-series / vintage inputs.

---

## 7. Layout

```text
dev/io2022/
  README.md                      this document
  INTEGRATION_LOG.md             detailed change log (#0–#34)
  NEW_THREAD_HANDOFF.md          working handoff / forensic notes
  build_2022_datawrapper.py      builds the 2022 DataWrapper pickle
  run_candidate_2022.py          runs 13q (use --legacy for simple/default)
  prepare_compensation_input.py  regenerate the CoE input from the io2022 pipeline
  inspect_and_smoke_2022.py      quick init/smoke inspection
```

Code changes are in `macro_data/` (readers, synthetic population/firms); see the log for exact files.

---

## Maintenance

For each further 2022 change: add a numbered entry to `INTEGRATION_LOG.md`
(change | reason | validation | remaining), then update the affected row/section here (Model changes /
Status & roadmap) and the status banner. Keep this document a summary with pointers; keep detail in the log.
