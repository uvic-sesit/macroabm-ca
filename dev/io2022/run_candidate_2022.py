"""Short 2022 candidate-baseline run (same real-growth settings as the 2014 baseline) and a
legacy (shipped-defaults) control, for the io-2022 integration coherence check.

Real-growth settings = candidate growth baseline (rolling capital + unmet-demand memory +
demand smoothing + demand-growth-response + ExogenousLabourForcePath) + the common 2% household
demand overlay, mirroring dev/validation and scripts/run_candidate_baseline.py.

Differences from the 2014 runner:
  * base year 2022, 13 regions incl. territories;
  * the bundled observed provincial labour index (StatCan LFS, annual 2014-2024) is rebased to
    2022=1.0 for the 10 provinces; the 3 territories (absent from the index) fall back to the
    shipped NoAging fixed-labour default.

Usage:
    uv run python dev/io2022/run_candidate_2022.py [--quarters 13] [--seed 0] [--legacy]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration, SimulationConfiguration
from macromodel.configurations.growth_baseline_preset import (
    apply_candidate_growth_baseline,
    observed_labour_force_index,
)
from macromodel.simulation import Simulation

REPO = Path(__file__).resolve().parents[2]
# Allow pointing at an alternate pickle (e.g. a staged capital-treatment rebuild) via IO2022_PKL.
PKL = Path(__import__("os").environ.get("IO2022_PKL", str(REPO / "dev" / "pkl_files" / "io2022_13prov_2022.pkl")))
HH_COLS = ["Real Household Consumption (Value)", "Household Consumption (Value)",
           "Real Household Investment (Value)", "Household Investment (Value)"]
HOUSEHOLD_DEMAND_GROWTH = 0.02
LABOUR_BASE_YEAR = 2014
SIM_BASE_YEAR = 2022
PROVINCES_WITH_LABOUR = {"CAN_AB", "CAN_BC", "CAN_MB", "CAN_NB", "CAN_NL",
                         "CAN_NS", "CAN_ON", "CAN_PE", "CAN_QC", "CAN_SK"}


def labour_index_2022(province: str, n_quarters: int) -> list[float] | None:
    """Observed provincial labour index rebased to 2022=1.0, or None (NoAging) for territories."""
    if province not in PROVINCES_WITH_LABOUR:
        return None
    offset = (SIM_BASE_YEAR - LABOUR_BASE_YEAR) * 4  # quarters from 2014-Q1 to 2022-Q1
    full = observed_labour_force_index(n_quarters=offset + n_quarters, province=province)
    sliced = np.asarray(full[offset:offset + n_quarters], dtype=float)
    return (sliced / sliced[0]).tolist()


def _extend_exogenous(model, required_length: int) -> None:
    for country in model.countries.values():
        frame = country.exogenous.national_accounts_during.copy()
        if len(frame) >= required_length:
            continue
        last_index = frame.index[-1]
        rows, index = [], []
        for step in range(required_length - len(frame)):
            rows.append(frame.iloc[-1].copy())
            index.append(last_index + pd.DateOffset(months=3 * (step + 1)))
        country.exogenous.national_accounts_during = pd.concat([frame, pd.DataFrame(rows, index=index)], axis=0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarters", type=int, default=13)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--legacy", action="store_true", help="run shipped defaults (control arm)")
    args = ap.parse_args()

    data = DataWrapper.init_from_pickle(PKL)
    provinces = [c for c in data.all_country_names if str(c).startswith("CAN_")]

    cfg = SimulationConfiguration(
        seed=args.seed,
        country_configurations={c: CountryConfiguration.n_industry_default(n_industries=data.n_industries)
                                for c in provinces},
        t_max=args.quarters,
    )
    if not args.legacy:
        for i, c in enumerate(provinces):
            apply_candidate_growth_baseline(
                cfg.country_configurations[c],
                labour_force_index=labour_index_2022(str(c), args.quarters + 1),
                demography_seed=1000 + i + 100 * args.seed,
            )

    m = Simulation.from_datawrapper(datawrapper=data, simulation_configuration=cfg)

    if not args.legacy:
        _extend_exogenous(m, required_length=args.quarters + 1)
        for country in m.countries.values():
            fr = country.exogenous.national_accounts_during
            fac = (1.0 + HOUSEHOLD_DEMAND_GROWTH) ** (np.arange(len(fr)) / 4.0)
            for col in HH_COLS:
                if col in fr.columns:
                    fr[col] = fr[col].values * fac

    p0 = {c: np.array(m.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provinces}
    ro = np.zeros(args.quarters)
    ri = np.zeros(args.quarters)
    u = np.zeros(args.quarters)
    for t in range(args.quarters):
        m.iterate(t)
        for c in provinces:
            f = m.countries[c].firms
            base = p0[c]
            qr = np.array(f.ts.current("production"), float)
            ui = np.array(f.ts.current("used_intermediate_inputs"), float)
            ro[t] += float((qr * base).sum())
            ri[t] += float((ui * base[None, :]).sum()) if ui.ndim == 2 else 0.0
        u[t] = float(np.mean([np.array(m.countries[c].economy.ts.current("unemployment_rate"),
                                       float).reshape(-1)[0] for c in provinces]))
        if __import__("os").environ.get("IO2022_TRACE"):
            _rva_t = (ro[t] - ri[t]) / 1e9
            _prod = sum(float(np.array(m.countries[c].firms.ts.current("production"), float).sum())
                        for c in provinces) / 1e9
            print(f"  [trace] t={t:2d} realGVA={_rva_t:8.1f}B grossProd={_prod:8.1f}B u={u[t]*100:5.1f}%",
                  flush=True)
            if __import__("os").environ.get("IO2022_TRACE_ON") and str(provinces and "CAN_ON"):
                fon = m.countries["CAN_ON"].firms

                def _s(field):
                    try:
                        return float(np.nansum(np.asarray(fon.ts.current(field), float)))
                    except Exception:
                        return float("nan")
                ind = m.countries["CAN_ON"].individuals
                try:
                    _emp = int(np.sum(np.asarray(ind.states["Activity Status"]) == 1))
                    _lab = float(np.nansum(np.asarray(ind.ts.current("labour_inputs"), float)))
                except Exception:
                    _emp, _lab = -1, float("nan")
                print(f"    [ON] target_prod={_s('target_production')/1e9:7.1f}B prod={_s('production')/1e9:7.1f}B "
                      f"limInt={_s('limiting_intermediate_inputs')/1e9:7.1f}B firm_labour={_s('labour_inputs')/1e9:7.2f}B "
                      f"demand={_s('demand')/1e9:7.1f}B wage={_s('total_wage')/1e9:7.2f}B "
                      f"profits={_s('profits')/1e9:8.2f}B | indiv_employed={_emp} indiv_labour={_lab/1e9:7.2f}B",
                      flush=True)
    rva = ro - ri
    yrs = (args.quarters - 1) / 4.0
    ann = ((rva[-1] / rva[0]) ** (1 / yrs) - 1) * 100 if rva[0] > 0 and rva[-1] > 0 else float("nan")

    mode = "LEGACY (shipped defaults)" if args.legacy else "CANDIDATE growth baseline"
    print(f"\n=== 2022 {mode} | {len(provinces)} regions | seed {args.seed} | {args.quarters}q ===")
    print(f"  double-deflated real GVA: {rva[0] / 1e9:.1f}B -> {rva[-1] / 1e9:.1f}B  "
          f"({(rva[-1] / rva[0] - 1) * 100:+.1f}% cumulative, {ann:+.2f}%/yr)")
    print(f"  unemployment: {u[0] * 100:.1f}% -> {u[-1] * 100:.1f}%")
    print(f"  non-finite rva: {int(np.sum(~np.isfinite(rva)))}")
    print("  (2014 real-growth-baseline reference: ~1.87%/yr real GVA; provisional, national aggregate only)")


if __name__ == "__main__":
    main()
