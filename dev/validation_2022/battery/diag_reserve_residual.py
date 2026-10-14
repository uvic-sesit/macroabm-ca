"""One-quarter diagnostic: government revenue lines and bank interest vs the payers' recorded debits, by region
(nominal CAD per quarter). Locates the residual `reserves_unexplained` term of the accounting battery.

    .venv/Scripts/python.exe dev/validation_2022/battery/diag_reserve_residual.py PICKLE
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

d = DataWrapper.init_from_pickle(Path(sys.argv[1]))
provs = [c for c in d.all_country_names if str(c).startswith("CAN_")]
cfg = SimulationConfiguration(seed=0, t_max=1, country_configurations={
    c: CountryConfiguration.n_industry_default(n_industries=d.n_industries) for c in provs})
m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)
m.iterate(0)
c0 = lambda ts, k: np.asarray(ts.current(k), float)  # noqa: E731
rows = []
for name, c in m.countries.items():
    h, f, b, g, cm = c.households, c.firms, c.banks, c.central_government, c.credit_market
    st = g.states
    inv = c0(h.ts, "investment")
    r = {"region": str(name)}
    r["cf_tax_gov_minus_hh"] = c0(g.ts, "taxes_cf")[0] - st["Capital Formation Tax"] * np.maximum(0, inv.sum(axis=1) if inv.ndim > 1 else inv).sum()
    r["vat_gov_minus_hh"] = c0(g.ts, "taxes_vat")[0] - c0(h.ts, "vat_paid").sum()
    r["prod_tax_gov_minus_firms"] = c0(g.ts, "taxes_production")[0] - c0(f.ts, "taxes_paid_on_production").sum()
    bank_tax = st["Profit Tax"] * np.maximum(0, c0(b.ts, "profits")).sum()
    r["corp_tax_gov_minus_firms_banks"] = c0(g.ts, "taxes_corporate_income")[0] - c0(f.ts, "corporate_taxes_paid").sum() - bank_tax
    r["loan_int_bank_minus_payers"] = (c0(b.ts, "interest_received_on_loans").sum()
                                       - c0(h.ts, "interest_paid_on_loans").sum() - c0(f.ts, "interest_paid_on_loans").sum())
    r["dep_int_bank_minus_payers_minus_cb"] = (c0(b.ts, "interest_received_on_deposits").sum()
                                               - c0(h.ts, "interest_paid_on_deposits").sum()
                                               - c0(f.ts, "interest_paid_on_deposits").sum())
    r["hh_interest_paid_minus_parts"] = (c0(h.ts, "interest_paid").sum() - c0(h.ts, "interest_paid_on_loans").sum()
                                         - c0(h.ts, "interest_paid_on_deposits").sum())
    r["exports_tax"] = c0(g.ts, "taxes_exports")[0]
    rows.append(r)
df = pd.DataFrame(rows).set_index("region")
print((df / 1e6).round(3).to_string())
