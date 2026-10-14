"""One-quarter diagnostic of first-quarter price and rate discontinuities for firms: domestic firm prices, the
economy good-price index used to value inputs, ROW prices, CPI/PPI and expectations, firm loan and deposit rates
vs the t0 data, and the interest paid at t0 (data) vs Q1 (model).

    .venv/Scripts/python.exe dev/validation_2022/battery/diag_firm_prices_rates.py PICKLE
"""
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
from macro_data import DataWrapper  # noqa: E402
from macromodel.configurations import CountryConfiguration, SimulationConfiguration  # noqa: E402
from macromodel.simulation import Simulation  # noqa: E402

d = DataWrapper.init_from_pickle(Path(sys.argv[1]))
provs = [c for c in d.all_country_names if str(c).startswith("CAN_")]
cfg = SimulationConfiguration(seed=0, t_max=1, country_configurations={
    c: CountryConfiguration.n_industry_default(n_industries=d.n_industries) for c in provs})
m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)
c = m.countries["CAN_ON"]
e, f, b, cb = c.economy, c.firms, c.banks, c.central_bank
g0 = lambda ts, k: np.asarray(ts.initial(k), float)  # noqa: E731
row = m.rest_of_the_world
print("ROW ts keys with price:", [k for k in row.ts.dicts if "price" in k][:10])
pre = {"good_prices": g0(e.ts, "good_prices") if "good_prices" in e.ts.dicts else None,
       "firm_price": np.asarray(f.ts.current("price"), float).copy(),
       "row_price": np.asarray(row.ts.current("price"), float).copy() if "price" in row.ts.dicts else None}
m.iterate(0)
cur = lambda ts, k: np.asarray(ts.current(k), float)  # noqa: E731
gp = cur(e.ts, "good_prices")
fp = cur(f.ts, "price")
print("firm price change: mean %.4f, min %.4f, max %.4f" % ((fp / pre["firm_price"]).mean() - 1, (fp / pre["firm_price"]).min() - 1, (fp / pre["firm_price"]).max() - 1))
if pre["good_prices"] is not None:
    print("good_prices t0: mean %.4f; Q1: mean %.4f; ratio min %.3f max %.3f" % (pre["good_prices"].mean(), gp.mean(), (gp / pre["good_prices"]).min(), (gp / pre["good_prices"]).max()))
if pre["row_price"] is not None:
    rp = cur(row.ts, "price")
    print("ROW price change: mean %.4f min %.4f max %.4f" % ((rp / pre["row_price"]).mean() - 1, (rp / pre["row_price"]).min() - 1, (rp / pre["row_price"]).max() - 1))
for k in ["cpi", "ppi", "estimated_ppi_inflation", "estimated_cpi_inflation", "cpi_inflation", "ppi_inflation"]:
    if k in e.ts.dicts:
        print(k, "t0", np.round(g0(e.ts, k), 4), "Q1", np.round(cur(e.ts, k), 4))
print("policy rate t0", g0(cb.ts, "policy_rate"), "Q1", cur(cb.ts, "policy_rate"))
for k in ["interest_rate_on_firm_deposits", "overdraft_rate_on_firm_deposits", "interest_rates_on_short_term_firm_loans",
          "interest_rates_on_long_term_firm_loans", "interest_rate_on_long_term_firm_loans", "average_interest_rate_on_long_term_firm_loans"]:
    if k in b.ts.dicts:
        print(k, "t0", np.round(g0(b.ts, k), 5), "Q1", np.round(cur(b.ts, k), 5))
lt = c.credit_market.states["lt_loans"]; st = c.credit_market.states["st_loans"]
print("credit market LT principal %.1fB, interest field %.2fB/q, implied rate/q %.4f" % (lt[0].sum() / 1e9, lt[1].sum() / 1e9, lt[1].sum() / max(lt[0].sum(), 1)))
print("firm interest paid on loans Q1 %.2fB, on deposits %.2fB; t0 data interest on loans %.2fB" % (
    cur(f.ts, "interest_paid_on_loans").sum() / 1e9, cur(f.ts, "interest_paid_on_deposits").sum() / 1e9,
    g0(f.ts, "interest_paid_on_loans").sum() / 1e9 if "interest_paid_on_loans" in f.ts.dicts else np.nan))
print("bank t0 data rates:", {k: v for k, v in c.banks.states.items() if "Rate" in str(k) or "rate" in str(k)} if hasattr(c.banks, "states") else "")
