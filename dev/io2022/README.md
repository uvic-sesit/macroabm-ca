# MacroABM-CA — 2022 Provincial IO Integration Guide

> **Status: WORK IN PROGRESS** (branch `feature/io-2022-integration`).
> The 2022 base year builds and runs on the **simple/default baseline**. It is **mechanically
> stable nationally** (no NaN/inf, GDP identity holds), but **five small regions collapse over a
> 13-quarter run** — see [Status & roadmap](#status--roadmap). Do not treat 2022 results as final.

This is the living guide for wiring Statistics Canada's 2022 provincial data into the MacroABM-CA
DataWrapper. It explains the new data, how to run the 2022 model, what changed, and what's left.
Keep it updated as work continues (see [Keeping this doc current](#keeping-this-doc-current)).

- **Detailed change log (provenance):** [`INTEGRATION_LOG.md`](INTEGRATION_LOG.md) (entries #0–#34)
- **IO table pipeline (separate repo):** `github.com/esizadi/macroabm-io2022` (private) — produces the
  2022 provincial IO table + the validated province×sector inputs used here.

---

## 1. What this is

The 2022 base year replaces the legacy 2014 provincial table (10 provinces × 43 sectors) with a
**13-region × OECD-50-sector** table (10 provinces + the 3 territories YT/NT/NU) and wires in
validated 2022 StatCan capital, employment, and compensation data. Behavioural equations are
unchanged; the work is data mapping + calibration into the existing model.

---

## 2. New data added

All 2022 inputs are **derived by the `macroabm-io2022` pipeline** from StatCan sources and placed
under the model's `raw_data_path` (`dev/raw_data/`). They are **not committed to this repo** (repo
policy: no raw/large data) — see [Data access](#3-data-access-how-colleagues-get-the-data).

| file (under `dev/raw_data/`) | what | source |
|---|---|---|
| `icio/icio_2022_can_provinces.csv` | 2022 provincial IO table, 13 regions × OECD-50 (~7.9 MB) | `macroabm-io2022` compatibility output `icio_2022_can_provinces_oecd50.csv` |
| `can_2022/capital_stock_end2021_oecd50_by_province_CADmillions.csv` | opening net capital stock (end-2021) | StatCan 36-10-0096 |
| `can_2022/capital_compensation_oecd50_by_province_CADmillions.csv` | capital compensation (GOS + mixed income + net production tax) | 2022 IO VA breakdown |
| `can_2022/employment_shares_oecd50_by_province.csv` | province×sector employment shares | StatCan 36-10-0489 |
| `can_2022/compensation_of_employees_oecd50_by_province_CADmillions.csv` | wages (PRM500000) + employer social contributions (PRM600000) | 2022 IO VA breakdown |

The whole 2022-specific bundle is **~7.6 MB**.

---

## 3. Data access (how colleagues get the data)

Running the 2022 model needs **two things** in `dev/raw_data/`:

1. **The base MacroABM-CA `raw_data_path`** — the standard model inputs (`hfcs/`, `wiod_sea/`,
   `oecd_econ/`, `exchange_rates/`, `eurostat/`, `world_bank/`, …). This is large and private; get it
   from the team's data store (it is not in the repo and is not part of the 2022 work).
2. **The 2022 delta (~7.6 MB)** — the five files in the table above.

**Recommendation: send colleagues the ~7.6 MB 2022 delta as a copy** to drop into their existing
`raw_data_path`, at exactly these locations:

```text
raw_data_path/
  icio/icio_2022_can_provinces.csv
  can_2022/
    capital_stock_end2021_oecd50_by_province_CADmillions.csv
    capital_compensation_oecd50_by_province_CADmillions.csv
    employment_shares_oecd50_by_province.csv
    compensation_of_employees_oecd50_by_province_CADmillions.csv
```

**Do not commit these to this repo** — repo policy is no raw/private data, and they are StatCan-derived
outputs of the private `macroabm-io2022` pipeline. A colleague with access to that pipeline repo can
instead take `compatibility/icio_2022_can_provinces_oecd50.csv` (→ rename to
`icio/icio_2022_can_provinces.csv`) and the `integration_2022_inputs/` files.

> The compensation file is pre-built into the bundle, so colleagues do **not** need to run
> `prepare_compensation_input.py` (that script only regenerates it from the private pipeline).

---

## 4. How to run the 2022 model

From the repo root, with `dev/raw_data/` populated as above:

```bash
# 1. Build the 2022 DataWrapper (13 regions × OECD-50) -> dev/pkl_files/io2022_13prov_2022.pkl
uv run python dev/io2022/build_2022_datawrapper.py --force

# 2. Run the SIMPLE/DEFAULT baseline for 13 quarters (this is the accepted integration baseline)
uv run python dev/io2022/run_candidate_2022.py --quarters 13 --legacy
```

Notes:
- `--legacy` = the **simple/default** (shipped-defaults) baseline. **Use this.**
- Omitting `--legacy` runs the **candidate growth baseline**, which is **parked** — it hits a separate
  demand/intermediate collapse unrelated to this integration (INTEGRATION_LOG #30). Don't use it to
  judge the 2022 wiring.
- `build_2022_datawrapper.py` reads `dev/raw_data/` and writes `dev/pkl_files/io2022_13prov_2022.pkl`;
  the run script reads that pickle (override with `IO2022_PKL=<path>`).
- Build takes ~2–3 min; the pickle is ~20–30 GB-free-friendly but a few hundred MB on disk.

**Expected result (simple/default 13q, INTEGRATION_LOG #34):** GDP output==expenditure identity balances
for all 13 regions at t0; **0 NaN/inf**; national real GVA ≈ **−6%** over 13q; and **5 small regions
(NL, PE, NB, YT, NT) collapse** — the known WIP issue below. Large provinces are stable.

---

## 5. What changed in the model

Data/calibration only — **no behavioural equations changed**. Each is detailed in `INTEGRATION_LOG.md`.

| area | change | log |
|---|---|---|
| **Capital treatment** | Capital-technology composition sourced from **pre-fold** fixed capital formation (inventories excluded), negatives clipped to zero — fixes a t0→t1 collapse caused by negative capital entries. Accounting net investment ≠ capital-technology composition. | #29 |
| **Employment structure** | Province×sector headcount wired to **StatCan 36-10-0489** shares (was HFCS France-proxy split by output). | #31 |
| **Firm wage bill** | Set to **observed compensation of employees** (PRM500000 wages + PRM600000 employer contributions); `tau_sif` = observed per-province employer ratio. Was the `VA − capital-comp` residual (over-stated). | #32 |
| **Currency handling** | `from_usd_to_lcu_io` stops the spurious ~1.30 USD→CAD conversion on the **CAD-native** 2022 IO/SEA inputs (Compustat USD data still converts). Model VA/output/compensation now match canonical 2022 CAD. | #33 |

---

## 6. Status & roadmap

**Validated (simple/default baseline):**
- ✅ 2022 DataWrapper builds & initializes; GDP identity balances for all 13 regions.
- ✅ Capital treatment, employment shares, observed compensation of employees, CAD-native currency.

**Work in progress / next:**
1. **Zero-sector handling** — genuinely-empty (province, sector) cells use an ε floor
   (`_floor_empty_provincial_sectors`); replace with principled model-side handling.
2. **Small-region synthetic-population scaling** — small provinces/territories have too few synthetic
   agents to express 50-sector shares (e.g. PEI ≈ 61 employed across 50 sectors), and the ≥1-worker
   floor injects phantom employment. **This is why NL/PE/NB/YT/NT collapse over 13q.** Needs
   per-region scaling (supersedes the `scale=10` territory hack).
3. **Rerun** the simple/default 13q baseline and confirm the collapse is resolved.

**Deferred (until regional mechanics are stable):**
- HFCS-2021 Canadianization (household block still uses the raw European wave).
- Candidate growth baseline (parked, #30).
- Post-2022 external-series / vintage inputs.

---

## 7. Where things live

```text
dev/io2022/
  README.md                      ← this guide
  INTEGRATION_LOG.md             ← detailed change log (#0–#34), provenance for every change
  NEW_THREAD_HANDOFF.md          ← working handoff / forensic notes
  build_2022_datawrapper.py      ← builds the 2022 DataWrapper pickle
  run_candidate_2022.py          ← runs 13q (use --legacy for simple/default)
  prepare_compensation_input.py  ← (maintainers) regenerate the CoE input from the io2022 pipeline
  inspect_and_smoke_2022.py      ← quick init/smoke inspection
```

Code changes are in `macro_data/` (readers, synthetic population/firms) — see the log for exact files.

---

## Keeping this doc current

When you make a further 2022 change:
1. Add a numbered entry to `INTEGRATION_LOG.md` (change | reason | validation | remaining).
2. Update the relevant row/section here (What changed / Status & roadmap) and the status banner.
3. Keep this guide a **summary with pointers** — put the detail in the log so the two stay in sync.
