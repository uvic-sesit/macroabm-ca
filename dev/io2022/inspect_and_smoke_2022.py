"""Inspect 2022 DataWrapper initialization accounting + key agent states, then run the
smallest simulation (shipped defaults) to confirm it iterates cleanly.

Usage:
    uv run python dev/io2022/inspect_and_smoke_2022.py [--quarters 4]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration, SimulationConfiguration
from macromodel.simulation import Simulation

REPO = Path(__file__).resolve().parents[2]
PKL = REPO / "dev" / "pkl_files" / "io2022_13prov_2022.pkl"


def _cur(agent, field):
    """Best-effort read of a current time-series field; returns np.array or None."""
    try:
        return np.asarray(agent.ts.current(field), dtype=float).reshape(-1)
    except Exception:
        return None


def _fmt(arr):
    if arr is None:
        return "n/a"
    finite = np.isfinite(arr)
    return (f"sum={np.nansum(arr):.3e} min={np.nanmin(arr):+.2e} max={np.nanmax(arr):+.2e} "
            f"nan/inf={np.sum(~finite)} neg={np.sum(arr < 0)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarters", type=int, default=4)
    args = ap.parse_args()

    data = DataWrapper.init_from_pickle(PKL)
    provinces = [c for c in data.all_country_names if str(c).startswith("CAN_")]
    n_ind = data.n_industries

    cfg = SimulationConfiguration(
        seed=0,
        country_configurations={c: CountryConfiguration.n_industry_default(n_industries=n_ind) for c in provinces},
        t_max=args.quarters,
    )
    m = Simulation.from_datawrapper(datawrapper=data, simulation_configuration=cfg)

    print("=" * 100)
    print(f"2022 DataWrapper t0 initialization inspection ({len(provinces)} regions x {n_ind} sectors)")
    print("=" * 100)

    # Candidate fields to probe (best-effort; different builds expose different names).
    firm_fields = ["production", "capital_inputs", "used_intermediate_inputs", "productivity",
                   "prices", "wages", "labour_inputs", "desired_production", "capacity"]
    econ_fields = ["good_prices", "unemployment_rate", "employment", "gdp_output"]

    issues = []
    for c in provinces:
        firms = m.countries[c].firms
        econ = m.countries[c].economy
        print(f"\n--- {c} ---")
        for f in firm_fields:
            arr = _cur(firms, f)
            if arr is not None:
                print(f"  firm.{f:24s} {_fmt(arr)}")
                if np.sum(~np.isfinite(arr)) > 0:
                    issues.append(f"{c} firm.{f} has non-finite")
        for f in econ_fields:
            arr = _cur(econ, f)
            if arr is not None:
                print(f"  econ.{f:24s} {_fmt(arr)}")
                if np.sum(~np.isfinite(arr)) > 0:
                    issues.append(f"{c} econ.{f} has non-finite")

    # Household / population summary from the datawrapper
    print("\n" + "=" * 100)
    print("Household / population summary")
    for c in provinces:
        sc = data.synthetic_countries[c]
        print(f"  {c:8s} n_buyers={sc.n_buyers} n_sellers_sum={int(np.sum(sc.n_sellers_by_industry))}")

    # Smallest simulation
    print("\n" + "=" * 100)
    print(f"Running smallest simulation: {args.quarters} quarters ...")
    for t in range(args.quarters):
        m.iterate(t)
        # per-step finiteness check on production
        bad = 0
        for c in provinces:
            p = _cur(m.countries[c].firms, "production")
            if p is not None:
                bad += int(np.sum(~np.isfinite(p)))
        print(f"  t={t} done; non-finite production entries across regions: {bad}")
        if bad:
            issues.append(f"t={t} non-finite production")

    print("\n" + "=" * 100)
    if issues:
        print(f"ISSUES ({len(issues)}):")
        for i in issues[:40]:
            print("  -", i)
    else:
        print("No non-finite states detected in probed fields. Smallest simulation ran cleanly.")


if __name__ == "__main__":
    main()
