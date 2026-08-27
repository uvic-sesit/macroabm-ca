"""Minimum 2022 real-growth mechanism retest (paired arms vs the shipped-default control).

Reuses `save_baseline_2022.build_config` (the canonical 2022 shipped-default config) and toggles
ONE mechanism family per arm. No parameter tuning to history. Compact per-arm .npz only (no h5).

Arms:
  control                     shipped default (canonical 2022 baseline)
  labour                      ExogenousLabourForcePath = observed 2022-2025 LFS index (per province)
  rolling                     rolling_reference capital (target_capital_inputs_fraction=0.1)
  demand                      demand-growth-response (sectoral/firm growth adjustment speed = 1.0)
  labour_rolling              labour + rolling
  labour_rolling_demand       labour + rolling + demand

    uv run python dev/validation/growth_mechanism_retest_2022.py run --arm labour
    uv run python dev/validation/growth_mechanism_retest_2022.py report
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]  # macroabm-ca root
sys.path.insert(0, str(REPO / "dev" / "io2022"))
from macro_data import DataWrapper
from macromodel.simulation import Simulation
from save_baseline_2022 import build_config

PKL = REPO / "dev" / "pkl_files" / "io2022_13prov_2022_canadianized.pkl"
OUT = REPO / "dev" / "validation" / "growth_retest_2022"
LFS_JSON = REPO / "scripts" / "data" / "labour_force_index_2014_2024.json"
QUARTERS = 13
ARMS = ("control", "labour", "rolling", "demand", "labour_rolling", "labour_rolling_demand")


def labour_index_2022(quarters: int) -> dict[str, list[float]]:
    """Per-region quarterly labour-force index, base 1.0 at 2022Q1, from the observed LFS json
    (annual 2022-2024, linearly interpolated to quarters, flat after 2024). Territories (absent
    from the json) get the mean provincial index (national fallback)."""
    d = json.load(open(LFS_JSON))
    n = quarters + 1
    prov_q: dict[str, np.ndarray] = {}
    for p, series in d.items():
        a = {int(y): v for y, v in series.items()}
        base = a[2022]
        anchors_x = [0, 4, 8]                                   # 2022Q1, 2023Q1, 2024Q1
        anchors_y = [1.0, a[2023] / base, a[2024] / base]
        q = np.interp(np.arange(n), anchors_x, anchors_y)       # flat past x=8 by np.interp
        prov_q[p] = q
    natl = np.mean(np.vstack(list(prov_q.values())), axis=0)    # territory fallback
    for terr in ("CAN_YT", "CAN_NT", "CAN_NU"):
        prov_q[terr] = natl
    return {k: list(map(float, v)) for k, v in prov_q.items()}


def apply_arm(cfg, provs, arm: str) -> None:
    lf = labour_index_2022(QUARTERS) if "labour" in arm else None
    for c in provs:
        cc = cfg.country_configurations[c]
        if "labour" in arm and str(c) in lf:
            cc.individuals.functions.demography.name = "ExogenousLabourForcePath"
            cc.individuals.functions.demography.parameters = {"labour_force_index": lf[str(c)]}
        if "rolling" in arm:
            cc.firms.functions.target_capital_inputs.parameters.update(
                {"rolling_reference": True, "target_capital_inputs_fraction": 0.1}
            )
        if "demand" in arm:
            cc.firms.functions.demand_estimator.parameters.update(
                {"sectoral_growth_adjustment_speed": 1.0, "firm_growth_adjustment_speed": 1.0}
            )
        if "tfp" in arm:
            # Pure exogenous Hicks-neutral TFP drift (~1.6%/yr), no investment feedback.
            cc.firms.functions.productivity_growth.name = "SimpleTFPGrowth"
            cc.firms.functions.productivity_growth.parameters = {"investment_effectiveness": 0.0}
            cc.firms.parameters.tfp_base_growth_rate = 0.004
        if "clamp" in arm:
            # Arm C: capital-capacity target-clamp relaxation (Wiese-motivated, NOT their full
            # partial-resource-constraint spec). Firms plan capital-input targets for DESIRED
            # production instead of current capacity. Single boundary value, not GDP-tuned.
            cc.firms.functions.target_production.parameters.update(
                {"capital_inputs_target_considers_capital_inputs": 0.0}
            )


def _employed(country) -> int:
    nm = np.asarray([x.name for x in country.individuals.states["Activity Status"]])
    return int((nm == "EMPLOYED").sum())


def run_arm(arm: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    d = DataWrapper.init_from_pickle(PKL)
    provs, cfg = build_config(d, 0, QUARTERS)
    apply_arm(cfg, provs, arm)
    m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)
    p0 = {c: np.array(m.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}

    def snap() -> list[float]:
        rgva = rprod = K = I = M = 0.0
        u_list, cpi_list = [], []
        emp = 0
        for c in provs:
            f = m.countries[c].firms
            q = np.array(f.ts.current("production"), float)
            ui = np.array(f.ts.current("used_intermediate_inputs"), float)
            rprod += float((q * p0[c]).sum())
            rgva += float((q * p0[c]).sum()) - (float((ui * p0[c][None, :]).sum()) if ui.ndim == 2 else 0.0)
            K += float(np.asarray(f.ts.current("capital_inputs_stock_value"), float).sum())
            I += float(np.asarray(m.countries[c].economy.ts.current("total_gross_fixed_capital_formation"), float).reshape(-1)[0])
            M += float(np.asarray(m.countries[c].economy.ts.current("total_imports"), float).reshape(-1)[0])
            u_list.append(float(np.asarray(m.countries[c].economy.ts.current("unemployment_rate"), float).reshape(-1)[0]))
            cpi_list.append(float(np.asarray(m.countries[c].economy.ts.current("cpi"), float).reshape(-1)[0]))
            emp += _employed(m.countries[c])
        return [rgva / 1e9, rprod / 1e9, K / 1e9, I / 1e9, M / 1e9, float(np.mean(u_list)) * 100, float(np.mean(cpi_list)), float(emp)]

    rows = [snap()]
    nonfinite = 0
    for t in range(QUARTERS):
        m.iterate(t)
        rows.append(snap())
        for c in provs:
            nonfinite += int(np.sum(~np.isfinite(np.asarray(m.countries[c].firms.ts.current("production"), float))))
    arr = np.array(rows)  # (T+1, 8): rgva, rprod, K, I, M, u%, cpi, emp
    target = OUT / f"arm_{arm}.npz"
    np.savez_compressed(target, data=arr, cols=np.array(["rgva", "rprod", "K", "I", "M", "u_pct", "cpi", "emp"]), nonfinite=nonfinite)
    print(f"arm {arm}: saved {target.name}  nonfinite={nonfinite}  rGVA {arr[0,0]:.1f}->{arr[-1,0]:.1f}  u {arr[0,5]:.1f}->{arr[-1,5]:.1f}%")
    return target


def report() -> None:
    print(f"{'arm':22} {'rGVA%':>7} {'u_t0':>5} {'u_tN':>5} {'emp%':>6} {'K%':>7} {'I%':>7} {'M%':>7} {'cpi%':>6} {'nf':>4}")
    base = None
    for arm in ARMS:
        p = OUT / f"arm_{arm}.npz"
        if not p.exists():
            print(f"{arm:22} (not run)"); continue
        z = np.load(p, allow_pickle=True); a = z["data"]; nf = int(z["nonfinite"])
        def pc(i): return (a[-1, i] / a[0, i] - 1) * 100 if a[0, i] else float("nan")
        rgva, K, I, M, emp = pc(0), pc(2), pc(3), pc(4), pc(7)
        cpi = (a[-1, 6] / a[0, 6] - 1) * 100
        collapse = " COLLAPSE" if a[-1, 0] < 0.5 * a[0, 0] or nf > 0 else ""
        print(f"{arm:22} {rgva:>+7.1f} {a[0,5]:>5.1f} {a[-1,5]:>5.1f} {emp:>+6.1f} {K:>+7.1f} {I:>+7.1f} {M:>+7.1f} {cpi:>+6.1f} {nf:>4}{collapse}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "report"])
    ap.add_argument("--arm", choices=ARMS, default="control")
    args = ap.parse_args()
    if args.mode == "run":
        run_arm(args.arm)
    else:
        report()


if __name__ == "__main__":
    main()
