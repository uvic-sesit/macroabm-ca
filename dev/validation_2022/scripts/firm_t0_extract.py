"""Firm sector at t0 from a DataWrapper pickle (no simulation): per region and national, model units
(nominal CAD; firm flows are QUARTERLY in the pickle, industry vectors as stored). Writes
outputs/firm_t0_{by_region,national,by_industry}_{TAG}.csv.

    .venv/Scripts/python.exe dev/validation_2022/scripts/firm_t0_extract.py PICKLE TAG
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from macro_data import DataWrapper  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "dev" / "validation_2022" / "outputs"
pkl, tag = Path(sys.argv[1]), sys.argv[2]
d = DataWrapper.init_from_pickle(pkl)

rows, ind_rows = [], []
for name, sc in d.synthetic_countries.items():
    if not str(name).startswith("CAN_"):
        continue
    F = sc.firms
    fd = F.firm_data
    iv = sc.industry_data["industry_vectors"]
    A = sc.industry_data["intermediate_inputs_productivity_matrix"].values
    B = sc.industry_data["capital_inputs_productivity_matrix"].values
    Dm = sc.industry_data["capital_inputs_depreciation_matrix"].values
    ind = fd["Industry"].values
    p, q = fd["Price"].values, fd["Production"].values
    used_ii = np.asarray(F.used_intermediate_inputs)  # (firms, goods) real
    used_k = np.asarray(F.used_capital_inputs)
    ii_stock = np.asarray(F.intermediate_inputs_stock)
    k_stock = np.asarray(F.capital_inputs_stock)
    r = {"region": str(name), "n_firms": len(fd), "n_employees_agents": fd["Number of Employees"].sum(),
         "output_q": (p * q).sum(),
         "wages_net_q": fd["Total Wages"].sum(), "wages_paid_q": fd["Total Wages Paid"].sum(),
         "intermediate_used_q": used_ii.sum(), "capital_used_q": used_k.sum(),
         "taxes_production_q": fd["Taxes paid on Production"].sum(), "profits_q": fd["Profits"].sum(),
         "corporate_taxes_q": fd["Corporate Taxes Paid"].sum(), "interest_paid_q": fd["Interest paid"].sum(),
         "debt_installments_q": fd["Debt Installments"].sum(),
         "inventory": (p * fd["Inventory"].values).sum(), "intermediate_stock": ii_stock.sum(),
         "capital_stock": k_stock.sum(), "deposits": fd["Deposits"].sum(), "debt": fd["Debt"].sum(),
         "equity": fd["Equity"].sum(),
         "deposits_cv_across_firms": fd["Deposits"].std() / fd["Deposits"].mean() if fd["Deposits"].mean() else np.nan,
         "iv_output": iv["Output in LCU"].sum(), "iv_value_added": iv["Value Added in LCU"].sum(),
         "iv_intermediate_use": iv["Intermediate Inputs Use in LCU"].sum(),
         "iv_labour_comp": iv["Labour Compensation in LCU"].sum(), "iv_tls": iv["Taxes Less Subsidies in LCU"].sum(),
         "iv_firm_gfcf": iv["Firm Capital Inputs in LCU"].sum(), "iv_hh_gfcf": iv["Household Capital Inputs in LCU"].sum(),
         "iv_capital_stock": iv["Capital Stock"].sum(), "iv_exports": iv["Exports in LCU"].sum(),
         "iv_imports": iv["Imports in LCU"].sum(), "iv_hh_cons": iv["Household Consumption in LCU"].sum(),
         "iv_gov_cons": iv["Government Consumption in LCU"].sum()}
    # gross operating surplus implied by the firm accounts (model concept, before depreciation)
    r["gos_model_q"] = r["output_q"] - r["intermediate_used_q"] - r["wages_paid_q"] - r["taxes_production_q"]
    rows.append(r)
    for g in range(len(iv)):
        k = ind == g
        ind_rows.append({"region": str(name), "industry": iv.index[g], "output_q": (p * q)[k].sum(),
                         "iv_output": iv["Output in LCU"].values[g], "wages_paid_q": fd["Total Wages Paid"].values[k].sum(),
                         "iv_labour_comp": iv["Labour Compensation in LCU"].values[g],
                         "intermediate_used_q": used_ii[k].sum(), "capital_used_q": used_k[k].sum(),
                         "taxes_production_q": fd["Taxes paid on Production"].values[k].sum(),
                         "profits_q": fd["Profits"].values[k].sum(), "capital_stock": k_stock[k].sum(),
                         "debt": fd["Debt"].values[k].sum(), "deposits": fd["Deposits"].values[k].sum(),
                         "employees_agents": fd["Number of Employees"].values[k].sum(),
                         "unit_costs": fd["Unit Costs"].values[k].mean()})
df = pd.DataFrame(rows).set_index("region")
df.to_csv(OUT / f"firm_t0_by_region_{tag}.csv")
nat = df.drop(columns=["deposits_cv_across_firms"]).sum()
nat.to_csv(OUT / f"firm_t0_national_{tag}.csv", header=["value"])
pd.DataFrame(ind_rows).to_csv(OUT / f"firm_t0_by_industry_{tag}.csv", index=False)
pd.set_option("display.width", 200)
print((nat / 1e9).round(1).to_string())
print(df[["deposits_cv_across_firms"]].T.round(3).to_string())
