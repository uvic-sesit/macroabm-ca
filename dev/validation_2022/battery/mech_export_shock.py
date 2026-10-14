"""Firm mechanism test (validation-2022): one-quarter +20% rest-of-world demand shock for one industry (default C29,
motor vehicles) in Q1, versus an identical baseline (same seed). Records every firm's response for Q quarters.

    .venv/Scripts/python.exe dev/validation_2022/battery/mech_export_shock.py PICKLE {baseline|shock} [Q] [INDUSTRY]
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from macro_data import DataWrapper  # noqa: E402
from macromodel.configurations import CountryConfiguration, SimulationConfiguration  # noqa: E402
from macromodel.rest_of_the_world.rest_of_the_world import RestOfTheWorld  # noqa: E402
from macromodel.simulation import Simulation  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "dev" / "validation_2022" / "outputs"
pkl, mode = Path(sys.argv[1]), sys.argv[2]
Q = int(sys.argv[3]) if len(sys.argv) > 3 else 3
IND = sys.argv[4] if len(sys.argv) > 4 else "C29"
SHOCK = 1.2
d = DataWrapper.init_from_pickle(pkl)
g = list(d.industries).index(IND)
provs = [c for c in d.all_country_names if str(c).startswith("CAN_")]
cfg = SimulationConfiguration(seed=0, t_max=Q, country_configurations={
    c: CountryConfiguration.n_industry_default(n_industries=d.n_industries) for c in provs})
m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)
state = {"t": 0}
orig = RestOfTheWorld.prepare_buying_goods


def shocked(self, *a, **k):
    out = orig(self, *a, **k)
    if mode == "shock" and state["t"] == 0:
        ig = self.transactor_buyer_states["Initial Goods"]
        ig[:, g] = ig[:, g] * SHOCK
    return out


RestOfTheWorld.prepare_buying_goods = shocked
KEYS = ["production", "target_production", "real_amount_sold", "real_excess_demand", "inventory", "price",
        "labour_inputs", "desired_labour_inputs", "total_wage", "profits", "deposits", "debt", "received_credit",
        "total_intermediate_inputs_bought_costs", "total_capital_inputs_bought_costs", "number_of_employees"]
rows = []


def hook(sim, t, y, mo):
    for name, c in sim.countries.items():
        f = c.firms
        for k in KEYS:
            try:
                v = np.asarray(f.ts.current(k), float)
            except Exception:
                continue
            for i, ind in enumerate(f.states["Industry"]):
                rows.append({"t": t, "region": str(name), "industry": int(ind), "key": k, "value": v[i] if v.ndim == 1 else v[i].sum()})
        rows.append({"t": t, "region": str(name), "industry": -1, "key": "cpi", "value": float(np.asarray(c.economy.ts.current("cpi"))[0])})
        rows.append({"t": t, "region": str(name), "industry": -1, "key": "unemployment_rate",
                     "value": float(np.asarray(c.economy.ts.current("unemployment_rate"))[0]) if "unemployment_rate" in c.economy.ts.dicts else np.nan})
    state["t"] = t + 1


m.posthooks.append(hook)
for t in range(Q):
    m.iterate(t)
pd.DataFrame(rows).to_csv(OUT / f"mech_export_shock_{IND}_{mode}.csv", index=False)
print("done", mode, IND, g)
