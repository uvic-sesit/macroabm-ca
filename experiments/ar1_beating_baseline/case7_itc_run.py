"""Multi-seed ITC runs for the case-7 baseline (alpha=0.30 + four substantive E16 changes).

Isolated clone only. Reads shared read-only reference data (oecd_econ/world_bank) via a
runtime DATA_REPO redirect; writes only inside the clone. Checkpoints per (closure, seed, arm):
each arm's quarterly CSV is saved immediately and skipped on re-run.

Closures:
  case7    : alpha=0.30 + change1(labour annual blocks) + change2(update before markets)
             + change3(labour unclamp) + change4(intermediate unclamp)
  e16      : identical to case7 but alpha=1.00 (exact E16), secondary diagnostic
ITC design unchanged: tau=0.30, eta_I=0.50, window 2026Q1-2030Q4, C27/C28, richer closure,
constant policy rate, same collector/timing as the frozen publication baseline.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
os.environ.setdefault("NUMBA_CACHE_DIR", str(Path(os.environ.get("TEMP", "/tmp")) / "macroabm_forecast_numba_cache"))
for p in [str(REPO), str(HERE), str(REPO / "experiments" / "itc_endogenous_closure"), str(REPO / "dev" / "validation")]:
    sys.path.insert(0, p)

import closure_feedback_exp as closure
closure.DATA_REPO = REPO.parent / "macroabm-ca"          # shared read-only reference data
import run_uc_closure_comparison as uc
import run_historical_experiment as historical
import followup_e16 as fu                                 # reuse recorder / no_b / collect helpers

Q_ITC = 55
SEEDS = (0, 1, 2, 3, 4)
OUT = HERE / "outputs" / "case7_itc"
JOBS = [("case7", SEEDS), ("e16", (0,))]                  # primary + secondary diagnostic


def _apply_common_changes(model, provs) -> None:
    """The four substantive E16 changes (timing + planning), no smoothing change."""
    model.configuration.labour_force_update_before_markets = True          # change 2
    paths = historical.labour_index_2022(Q_ITC, "observed_annual_blocks")  # change 1
    for c in provs:
        country = model.countries[c]
        country.individuals.functions["demography"].labour_force_index = paths[str(c)]
        country.firms.functions["desired_labour"].consider_capital_inputs = 0.0                      # change 3
        country.firms.functions["target_production"].intermediate_inputs_target_considers_capital_inputs = 0.0  # change 4


def apply_case7(model, provs) -> None:
    _apply_common_changes(model, provs)
    for c in provs:
        model.countries[c].firms.functions["demand_estimator"].demand_smoothing = 0.30   # keep validated alpha


def apply_e16(model, provs) -> None:
    _apply_common_changes(model, provs)
    for c in provs:
        model.countries[c].firms.functions["demand_estimator"].demand_smoothing = 1.00   # exact E16 smoothing


APPLY = {"case7": apply_case7, "e16": apply_e16}


def build(closure_name: str, seed: int, treatment: bool):
    model, provs = closure.build_closure_model(
        q=Q_ITC, seed=seed, price_dp=0.05, itc_rate=0.0,
        eligible_indices=closure.ELIGIBLE_INDICES,
        household_investment="exogenous", government_consumption="exogenous",
    )
    APPLY[closure_name](model, provs)
    uc.set_uc_params(model, provs, treatment=treatment)
    return model, provs


def run_arm(closure_name: str, seed: int, arm: str, cache=None):
    treatment = arm != "control"
    model, provs = build(closure_name, seed, treatment=treatment)
    recorded = fu.install_recorder(model, provs) if arm == "control" else None
    if arm == "no_b":
        fu.install_no_b(model, provs, cache)
    base_prices = {c: np.asarray(model.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}
    rows = []
    for t in range(Q_ITC + 1):
        rows.append({"case": arm, "t": t, "year_float": 2022.0 + t / 4.0,
                     "policy_active": treatment and uc.ACT0 <= t <= uc.ACT1,
                     **uc.collect(model, provs, base_prices)})
        if t < Q_ITC:
            if treatment:
                uc.set_policy_active(model, provs, treatment=True, active=uc.ACT0 <= t <= uc.ACT1)
            model.iterate(t)
    return pd.DataFrame(rows), recorded


def main() -> None:
    t_start = time.time()
    for closure_name, seeds in JOBS:
        for seed in seeds:
            d = OUT / closure_name / f"seed{seed:03d}"
            d.mkdir(parents=True, exist_ok=True)
            paths = {a: d / f"{a}_quarterly.csv" for a in ("control", "full", "no_b")}
            if all(p.exists() for p in paths.values()):
                print(f"SKIP {closure_name} seed={seed} (complete)", flush=True)
                continue
            # control first (records own-demand memory), then full, then no_b(control cache)
            tc = time.time()
            control_df, cache = run_arm(closure_name, seed, "control")
            control_df.to_csv(paths["control"], index=False)
            print(f"DONE {closure_name} s{seed} control ({(time.time()-tc)/60:.1f}m)", flush=True)
            tf = time.time()
            full_df, _ = run_arm(closure_name, seed, "full")
            full_df.to_csv(paths["full"], index=False)
            print(f"DONE {closure_name} s{seed} full ({(time.time()-tf)/60:.1f}m)", flush=True)
            tn = time.time()
            nob_df, _ = run_arm(closure_name, seed, "no_b", cache=cache)
            nob_df.to_csv(paths["no_b"], index=False)
            print(f"DONE {closure_name} s{seed} no_b ({(time.time()-tn)/60:.1f}m)", flush=True)
    print(f"ALL RUNS COMPLETE ({(time.time()-t_start)/60:.1f}m)", flush=True)
    print("case7 itc runs: complete", flush=True)


if __name__ == "__main__":
    main()
