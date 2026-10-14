"""Firm-sector step diagnostic (validation-2022, firm audit). Runs Q quarters of the shipped-default 2022
configuration and records, per region x industry x quarter:
  * stock-flow identities: inventory, intermediate-input stock, capital stock (count and value of clipping by the
    max(0, .) floors), profits vs gross operating surplus (sales + p*dINV - p*Q), firm cash identity;
  * first-quarter jumps vs t0 (production, price, employment, sales, inventories, profits, purchases);
  * binding production constraint (labour / intermediate / capital / demand).
Nominal CAD per quarter, real units as in the model.

    .venv/Scripts/python.exe dev/validation_2022/battery/diag_firm_step.py PICKLE TAG [Q]
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from macro_data import DataWrapper  # noqa: E402
from macromodel.configurations import CountryConfiguration, SimulationConfiguration  # noqa: E402
from macromodel.simulation import Simulation  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "dev" / "validation_2022" / "outputs"
pkl, tag = Path(sys.argv[1]), sys.argv[2]
Q = int(sys.argv[3]) if len(sys.argv) > 3 else 2
d = DataWrapper.init_from_pickle(pkl)
provs = [c for c in d.all_country_names if str(c).startswith("CAN_")]
cfg = SimulationConfiguration(seed=0, t_max=Q, country_configurations={
    c: CountryConfiguration.n_industry_default(n_industries=d.n_industries) for c in provs})
m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)

KEYS = ["production", "price", "real_amount_sold", "inventory", "labour_inputs", "desired_labour_inputs",
        "total_wage", "profits", "deposits", "debt", "real_excess_demand", "target_production",
        "nominal_amount_sold_in_lcu", "used_intermediate_inputs_costs", "used_capital_inputs_costs",
        "interest_paid", "taxes_paid_on_production", "gross_operating_surplus_mixed_income",
        "total_capital_inputs_bought_costs", "total_intermediate_inputs_bought_costs", "corporate_taxes_paid",
        "received_credit", "debt_installments", "number_of_employees", "expected_demand"]


def get(ts, k, how="current"):
    try:
        return np.asarray(getattr(ts, how)(k), dtype=float)
    except Exception:
        return None


rows = []


def snapshot(t, label):
    for name, c in m.countries.items():
        f = c.firms
        ind = np.asarray(f.states["Industry"])
        rec = {k: get(f.ts, k) for k in KEYS}
        prev = {k: get(f.ts, k, "prev") for k in ("inventory", "intermediate_inputs_stock", "capital_inputs_stock")} if t >= 0 else {}
        cur_stock = {k: get(f.ts, k) for k in ("intermediate_inputs_stock", "capital_inputs_stock")}
        extra = {}
        if t >= 0:
            used_ii = get(f.ts, "used_intermediate_inputs"); bought_ii = get(f.ts, "real_amount_bought_as_intermediate_inputs")
            used_k = get(f.ts, "used_capital_inputs")
            if used_ii is not None and bought_ii is not None and prev["intermediate_inputs_stock"] is not None:
                raw = prev["intermediate_inputs_stock"] - used_ii + bought_ii
                extra["ii_clipped_cells"] = (raw < -1e-6).sum(axis=1)
                extra["ii_clipped_qty"] = np.clip(-raw, 0, None).sum(axis=1)
                extra["ii_used_over_stock"] = np.divide(used_ii.sum(axis=1), prev["intermediate_inputs_stock"].sum(axis=1) + 1e-30)
            if used_k is not None and prev["capital_inputs_stock"] is not None:
                extra["k_used_over_stock"] = np.divide(used_k.sum(axis=1), prev["capital_inputs_stock"].sum(axis=1) + 1e-30)
            q, sold, inv_p = rec["production"], rec["real_amount_sold"], prev["inventory"]
            if inv_p is not None and sold is not None:
                raw_inv = inv_p + q - sold
                extra["inv_clipped_qty"] = np.clip(-raw_inv, 0, None)
            p = rec["price"]
            if all(rec[k] is not None for k in ("nominal_amount_sold_in_lcu", "inventory")) and inv_p is not None:
                extra["gos_minus_profit_bridge"] = (rec["gross_operating_surplus_mixed_income"]
                                                    - (rec["profits"] + rec["used_capital_inputs_costs"] + rec["interest_paid"]))
                extra["sales_plus_dinv_minus_pq"] = rec["nominal_amount_sold_in_lcu"] + p * (rec["inventory"] - inv_p) - p * q
        for i in range(len(ind)):
            r = {"t": t, "label": label, "region": str(name), "industry": int(ind[i])}
            for k, v in rec.items():
                if v is not None and v.ndim >= 1 and len(v) == len(ind):
                    r[k] = v[i] if v.ndim == 1 else v[i].sum()
            for k in ("intermediate_inputs_stock", "capital_inputs_stock"):
                v = cur_stock[k]
                if v is not None:
                    r[k] = v[i].sum()
            for k, v in extra.items():
                r[k] = v[i]
            rows.append(r)


snapshot(-1, "t0")
m.posthooks.append(lambda sim, t, y, mo: snapshot(t, f"q{t + 1}"))
for t in range(Q):
    m.iterate(t)
df = pd.DataFrame(rows)
df.to_csv(OUT / f"firm_step_{tag}.csv", index=False)
num = df.select_dtypes("number").columns.drop(["t", "industry"])
nat = df.groupby("label")[list(num)].sum(min_count=1)
pd.set_option("display.width", 250)
print((nat.T / 1e9).round(2).to_string())
