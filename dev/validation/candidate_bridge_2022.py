"""Bridge check: run the EXACT prior real-growth candidate profile on the current 2022
Canadianized baseline. Diagnostic only. Reuses build_config + labour_index_2022. 5 seeds, 13q.

Candidate package (as specified):
  demand_estimator: sectoral/firm_growth_adjustment_speed=1.0, demand_smoothing=0.3
  demand_for_goods: unmet_demand_weight=0.25
  excess_demand:    consider_capital_inputs=0.0        (relax demand-recording cap)
  target_capital_inputs: rolling_reference=True, target_capital_inputs_fraction=0.1, credit_gap_fraction=0.0
  demography = ExogenousLabourForcePath (observed 2022-2025 LFS index)
  exogenous government consumption; exogenous household consumption + investment
  HOUSEHOLD_DEMAND_GROWTH = 0.02 (compounding overlay on the household paths)

    uv run python dev/validation/candidate_bridge_2022.py run --seed 0
    uv run python dev/validation/candidate_bridge_2022.py report
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "dev" / "io2022"))
sys.path.insert(0, str(REPO / "dev" / "validation"))
from macro_data import DataWrapper
from macromodel.simulation import Simulation
from save_baseline_2022 import build_config
from growth_mechanism_retest_2022 import labour_index_2022

PKL = REPO / "dev" / "pkl_files" / "io2022_13prov_2022_canadianized.pkl"
OUT = REPO / "dev" / "validation" / "candidate_bridge_2022"
Q = 13
HH_GROWTH = 0.02
COLS = ["rGVA", "C", "I", "X", "M", "u", "emp"]


def run_seed(seed: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    d = DataWrapper.init_from_pickle(PKL)
    provs, cfg = build_config(d, seed, Q)
    lf = labour_index_2022(Q)
    for c in provs:
        cc = cfg.country_configurations[c]
        cc.firms.functions.demand_estimator.parameters.update(
            {"firm_growth_adjustment_speed": 1.0, "sectoral_growth_adjustment_speed": 1.0, "demand_smoothing": 0.3})
        cc.firms.functions.demand_for_goods.parameters.update({"unmet_demand_weight": 0.25})
        cc.firms.functions.excess_demand.parameters.update({"consider_capital_inputs": 0.0})
        cc.firms.functions.target_capital_inputs.parameters.update(
            {"rolling_reference": True, "target_capital_inputs_fraction": 0.1, "credit_gap_fraction": 0.0})
        if str(c) in lf:
            cc.individuals.functions.demography.name = "ExogenousLabourForcePath"
            cc.individuals.functions.demography.parameters = {"labour_force_index": lf[str(c)]}
        cc.government_entities.functions.consumption.name = "ExogenousGovernmentConsumptionSetter"
        cc.households.functions.consumption.name = "ExogenousHouseholdConsumption"
        cc.households.functions.investment.name = "ExogenousHouseholdInvestment"

    m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)

    # post-build: extend the exogenous national-accounts path to the horizon (flat), then apply the
    # +2%/yr compounding overlay to the household consumption/investment paths.
    for c in provs:
        exog = m.countries[c].exogenous
        frame = exog.national_accounts_during.copy()
        if len(frame) < Q + 1:
            last = frame.index[-1]
            ext = pd.DataFrame([frame.iloc[-1].copy() for _ in range(Q + 1 - len(frame))],
                               index=[last + pd.DateOffset(months=3 * (k + 1)) for k in range(Q + 1 - len(frame))])
            frame = pd.concat([frame, ext], axis=0)
        n = len(frame)
        fac = (1.0 + HH_GROWTH) ** (np.arange(n) / 4.0)
        for col in ["Real Household Consumption (Value)", "Household Consumption (Value)",
                    "Real Household Investment (Value)", "Household Investment (Value)"]:
            if col in frame.columns:
                frame[col] = frame[col].values * fac
        exog.national_accounts_during = frame

    p0 = {c: np.array(m.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}

    def rgva_region(c):
        f = m.countries[c].firms
        q = np.array(f.ts.current("production"), float); ui = np.array(f.ts.current("used_intermediate_inputs"), float)
        return (float((q * p0[c]).sum()) - (float((ui * p0[c][None, :]).sum()) if ui.ndim == 2 else 0.0)) / 1e9

    def snap():
        C = I = X = M = 0.0; ul = []; emp = 0
        for c in provs:
            e = m.countries[c].economy
            C += float(np.asarray(e.ts.current("total_household_fce"), float).reshape(-1)[0])
            I += float(np.asarray(e.ts.current("total_gross_fixed_capital_formation"), float).reshape(-1)[0])
            X += float(np.asarray(e.ts.current("total_exports"), float).reshape(-1)[0])
            M += float(np.asarray(e.ts.current("total_imports"), float).reshape(-1)[0])
            ul.append(float(np.asarray(e.ts.current("unemployment_rate"), float).reshape(-1)[0]))
            nm = np.asarray([x.name for x in m.countries[c].individuals.states["Activity Status"]])
            emp += int((nm == "EMPLOYED").sum())
        rg = sum(rgva_region(c) for c in provs)
        return [rg, C / 1e9, I / 1e9, X / 1e9, M / 1e9, float(np.mean(ul)) * 100, float(emp)]

    reg0 = {str(c): rgva_region(c) for c in provs}
    rows = [snap()]; nf = 0
    for t in range(Q):
        m.iterate(t)
        rows.append(snap())
        for c in provs:
            nf += int(np.sum(~np.isfinite(np.asarray(m.countries[c].firms.ts.current("production"), float))))
    regN = {str(c): rgva_region(c) for c in provs}
    np.savez_compressed(OUT / f"cand_s{seed}.npz", data=np.array(rows), nonfinite=nf,
                        reg0=np.array([reg0[str(c)] for c in provs]), regN=np.array([regN[str(c)] for c in provs]),
                        regions=np.array([str(c) for c in provs]))
    print(f"cand s{seed}: rGVA {rows[0][0]:.1f}->{rows[-1][0]:.1f} ({(rows[-1][0]/rows[0][0]-1)*100:+.1f}%)  u {rows[0][5]:.1f}->{rows[-1][5]:.1f}%  nf={nf}")


def report():
    import glob
    hist = REPO / "dev" / "validation" / "hist_2022"
    idx = {c: i for i, c in enumerate(COLS)}

    def load(pattern, base):
        out = []
        for f in sorted(glob.glob(str(base / pattern))):
            z = np.load(f, allow_pickle=True); out.append(z)
        return out

    ctrl = load("h_control_s*.npz", hist)
    cand = load("cand_s*.npz", OUT)
    if not cand:
        print("no candidate runs"); return

    def pct(zs, k):
        return float(np.mean([(z["data"][-1, idx[k]] / z["data"][0, idx[k]] - 1) * 100 for z in zs]))

    def disp(zs, per_region=False):
        # provincial real-GVA growth dispersion (sd across regions), mean over seeds
        sds = []
        for z in zs:
            if "reg0" in z.files:
                g = (z["regN"] / z["reg0"] - 1) * 100
                sds.append(float(np.std(g[:10])))  # 10 provinces
        return float(np.mean(sds)) if sds else float("nan")

    # control provincial dispersion from seed_robustness npz (per-region real GVA)
    ctrl_disp = float("nan")
    sr = REPO / "dev" / "validation" / "baseline_2022"
    srs = sorted(glob.glob(str(sr / "seed_*_robustness.npz")))
    if srs:
        sds = []
        for f in srs:
            z = np.load(f, allow_pickle=True); rg = z["real_gva"]
            g = (rg[:, -1] / rg[:, 0] - 1) * 100
            sds.append(float(np.std(g[:10])))
        ctrl_disp = float(np.mean(sds))

    print(f"{'metric':16}{'control':>10}{'candidate':>12}")
    print(f"{'real GVA %':16}{pct(ctrl,'rGVA'):>+10.1f}{pct(cand,'rGVA'):>+12.1f}")
    print(f"{'employment %':16}{pct(ctrl,'emp'):>+10.1f}{pct(cand,'emp'):>+12.1f}")
    u_c = float(np.mean([z['data'][-1, idx['u']] for z in ctrl])); u_k = float(np.mean([z['data'][-1, idx['u']] for z in cand]))
    print(f"{'unemploy tN %':16}{u_c:>10.1f}{u_k:>12.1f}")
    print(f"{'investment %':16}{pct(ctrl,'I'):>+10.1f}{pct(cand,'I'):>+12.1f}")
    print(f"{'imports %':16}{pct(ctrl,'M'):>+10.1f}{pct(cand,'M'):>+12.1f}")
    print(f"{'consumption %':16}{pct(ctrl,'C'):>+10.1f}{pct(cand,'C'):>+12.1f}")
    print(f"{'prov GVA disp sd':16}{ctrl_disp:>10.2f}{disp(cand):>12.2f}")
    print(f"\n(consumption/investment/imports are NOMINAL model flows; real GVA is double-deflated. CPI omitted.)")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["run", "report"]); ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(); run_seed(a.seed) if a.mode == "run" else report()


if __name__ == "__main__":
    main()
