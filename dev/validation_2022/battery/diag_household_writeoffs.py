"""One-quarter diagnostic of household defaults: who is insolvent at the F2 check, the composition of their
balance sheets now and at t0, and the flows that made their deposits negative. Nominal CAD, model units (x scale
for national totals is NOT applied; per-region sums are in model units).

    .venv/Scripts/python.exe dev/validation_2022/battery/diag_household_writeoffs.py PICKLE TAG
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from macro_data import DataWrapper  # noqa: E402
from macromodel.agents.households.func import insolvency as ins  # noqa: E402
from macromodel.configurations import CountryConfiguration, SimulationConfiguration  # noqa: E402
from macromodel.simulation import Simulation  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
pkl, tag = Path(sys.argv[1]), sys.argv[2]
d = DataWrapper.init_from_pickle(pkl)
provs = [c for c in d.all_country_names if str(c).startswith("CAN_")]
cfg = SimulationConfiguration(seed=0, t_max=1, country_configurations={
    c: CountryConfiguration.n_industry_default(n_industries=d.n_industries) for c in provs})
m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)

T0_KEYS = ["wealth_deposits", "wealth_other_financial_assets", "wealth_main_residence", "wealth_other_properties",
           "wealth_other_real_assets", "debt", "net_wealth", "income"]
t0 = {str(n): {k: np.asarray(c.households.ts.current(k), float).copy() for k in T0_KEYS}
      for n, c in m.countries.items()}
records, hh_rows = [], []
orig = ins.DefaultHouseholdInsolvencyHandler.handle_insolvency


def wrapped(self, households, banks, credit_market):
    h = households
    name = h.country_name if hasattr(h, "country_name") else "?"
    cur = lambda k: np.asarray(h.ts.current(k), float)  # noqa: E731
    nw, dep = cur("net_wealth"), cur("wealth_deposits")
    ins_ = (nw < 0) & (dep < 0)
    cm = credit_market.states
    cons = cm["cons_loans"][0].sum(axis=0)
    mort = cm["mort_loans"][0].sum(axis=0)
    rec = {"region": str(name), "n_households": len(nw), "n_insolvent": int(ins_.sum()),
           "nw_neg": int((nw < 0).sum()), "dep_neg": int((dep < 0).sum()),
           "cons_written": cons[ins_].sum(), "mort_written": mort[ins_].sum(),
           "cons_total": cons.sum(), "mort_total": mort.sum()}
    z = t0.get(str(name))
    if z is not None:
        rec["t0_nw_neg"] = int((z["net_wealth"] < 0).sum())
        rec["t0_insolvent_set_nw_neg"] = int((z["net_wealth"][ins_] < 0).sum())
    for k in ["wealth_deposits", "wealth_other_financial_assets", "wealth_main_residence", "wealth_other_properties",
              "wealth_other_real_assets", "debt", "net_wealth", "income", "rent", "interest_paid", "debt_installments",
              "price_paid_for_property", "property_sale_proceeds", "received_mortgages", "received_consumption_loans"]:
        try:
            rec["insolvent_" + k] = cur(k)[ins_].sum()
            if z is not None and k in z:
                rec["insolvent_t0_" + k] = z[k][ins_].sum()
        except (KeyError, IndexError):
            pass
    spent = np.asarray(h.ts.current("nominal_amount_spent_in_lcu"), float)
    rec["insolvent_spent"] = spent.sum(axis=1)[ins_].sum() if spent.ndim > 1 else spent[ins_].sum()
    records.append(rec)
    idx = np.where(ins_)[0][:2000]
    for i in idx:
        hh_rows.append({"region": str(name), "hh": int(i), "nw": nw[i], "dep": dep[i], "cons": cons[i], "mort": mort[i],
                        "main_res": cur("wealth_main_residence")[i], "other_prop": cur("wealth_other_properties")[i],
                        "tenure": h.states["Tenure Status of the Main Residence"][i],
                        "t0_nw": z["net_wealth"][i] if z else np.nan, "t0_dep": z["wealth_deposits"][i] if z else np.nan,
                        "t0_main_res": z["wealth_main_residence"][i] if z else np.nan,
                        "t0_other_prop": z["wealth_other_properties"][i] if z else np.nan,
                        "t0_debt": z["debt"][i] if z else np.nan})
    return orig(self, households, banks, credit_market)


ins.DefaultHouseholdInsolvencyHandler.handle_insolvency = wrapped
m.iterate(0)
out = REPO / "dev" / "validation_2022" / "outputs"
df = pd.DataFrame(records)
df.to_csv(out / f"hh_writeoffs_{tag}_by_region.csv", index=False)
pd.DataFrame(hh_rows).to_csv(out / f"hh_writeoffs_{tag}_households.csv", index=False)
pd.set_option("display.width", 250)
print(df.set_index("region").T.to_string())
