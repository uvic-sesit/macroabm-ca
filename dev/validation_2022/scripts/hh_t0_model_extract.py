"""Stage-2: household-related t0 state of the INSTANTIATED model (Simulation.from_datawrapper, shipped-default
config identical to save_baseline_2022.build_config). NO iterate() call -> no simulation step is executed.
Writes annualised ($M) national + per-region t0 values for household income/outlay/balance-sheet lines.
"""
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration, SimulationConfiguration
from macromodel.simulation import Simulation
from macromodel.agents.individuals.individual_properties import ActivityStatus

import sys
PKL = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dev/pkl_files/io2022_13prov_2022_canadianized.pkl")
TAG = sys.argv[2] if len(sys.argv) > 2 else "canonical"
OUT = Path("dev/validation_2022/outputs"); OUT.mkdir(parents=True, exist_ok=True)
d = DataWrapper.init_from_pickle(PKL)
provs = [c for c in d.all_country_names if str(c).startswith("CAN_")]
cfg = SimulationConfiguration(seed=0, t_max=1, country_configurations={
    c: CountryConfiguration.n_industry_default(n_industries=d.n_industries) for c in provs})
m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)
A, S = 4.0 / 1e6, 1.0 / 1e6
def cur(ts, k):
    return np.asarray(ts.current(k), float)
rows = []
for r in provs:
    C = m.countries[r]; h, i, f, g, b, e = C.households, C.individuals, C.firms, C.central_government, C.banks, C.economy
    st = g.states
    act = np.asarray(i.states["Activity Status"])
    emp = act == ActivityStatus.EMPLOYED
    w_net_ind = cur(i.ts, "employee_income")
    tax_wedge = (1 + st["Employer Social Insurance Tax"]) / ((1 - st["Employee Social Insurance Tax"]) * (1 - st["Income Tax"]))
    ten = np.asarray(h.states["Tenure Status of the Main Residence"])
    row = dict(region=r,
        cpi0=float(cur(e.ts, "cpi")[0]),
        tau_inc=st["Income Tax"], tau_ee=st["Employee Social Insurance Tax"], tau_er=st["Employer Social Insurance Tax"],
        tau_vat=st["Value-added Tax"], tau_cf=st["Capital Formation Tax"], tau_firm=st["Profit Tax"],
        hh_income=cur(h.ts, "income").sum() * A,
        hh_income_employee=cur(h.ts, "income_employee").sum() * A,
        hh_income_social=cur(h.ts, "income_social_transfers").sum() * A,
        hh_income_rental=cur(h.ts, "income_rental").sum() * A,
        hh_income_fa=cur(h.ts, "income_financial_assets").sum() * A,
        hh_consumption_basic=cur(h.ts, "consumption").sum() * A,
        hh_total_consumption_purch=float(cur(h.ts, "total_consumption").sum()) * A,
        hh_investment_basic=cur(h.ts, "investment").sum() * A,
        hh_rent_actual=cur(h.ts, "rent").sum() * A,
        hh_rent_imputed=cur(h.ts, "rent_imputed").sum() * A,
        hh_rent_actual_renters_ten3=cur(h.ts, "rent")[ten == 3].sum() * A,
        hh_rent_social=float(h.states.get("Rent paid to Government", np.nan)) * A if "Rent paid to Government" in h.states else np.nan,
        hh_debt_installments=cur(h.ts, "debt_installments").sum() * A if "debt_installments" in h.ts.dicts else np.nan,
        hh_interest_paid=cur(h.ts, "interest_paid").sum() * A if "interest_paid" in h.ts.dicts else np.nan,
        ind_w_net_employed=w_net_ind[emp].sum() * A,
        ind_w_net_all=w_net_ind.sum() * A,
        ind_ub=cur(i.ts, "income_from_unemployment_benefits").sum() * A,
        n_unemp_agents=int((act == ActivityStatus.UNEMPLOYED).sum()),
        ub_per_ind=float(cur(g.ts, "unemployment_benefits_by_individual")[0]) * 4,
        cg_total_other_benefits=float(cur(g.ts, "total_other_benefits")[0]) * A,
        firm_total_wage=cur(f.ts, "total_wage").sum() * A,
        firm_net_wage_implied=cur(f.ts, "total_wage").sum() / tax_wedge * A,
        # stocks
        hh_deposits=cur(h.ts, "wealth_deposits").sum() * S,
        hh_other_fa=cur(h.ts, "wealth_other_financial_assets").sum() * S,
        hh_real=cur(h.ts, "wealth_real_assets").sum() * S,
        hh_main_res=cur(h.ts, "wealth_main_residence").sum() * S,
        hh_other_prop=cur(h.ts, "wealth_other_properties").sum() * S,
        hh_other_real=cur(h.ts, "wealth_other_real_assets").sum() * S,
        hh_debt=cur(h.ts, "debt").sum() * S,
        hh_mortgage=cur(h.ts, "mortgage_debt").sum() * S,
        hh_cons_loans=cur(h.ts, "consumption_loan_debt").sum() * S,
        hh_net_wealth=cur(h.ts, "net_wealth").sum() * S,
        bank_hh_deposits=cur(b.ts, "deposits_from_households").sum() * S if "deposits_from_households" in b.ts.dicts else np.nan,
        bank_mortgages=cur(b.ts, "mortgages_to_households").sum() * S if "mortgages_to_households" in b.ts.dicts else np.nan,
        bank_cons_loans=cur(b.ts, "consumption_loans_to_households").sum() * S if "consumption_loans_to_households" in b.ts.dicts else np.nan,
        cg_debt=float(cur(g.ts, "debt")[0]) * S,
        policy_rate_q=float(cur(C.central_bank.ts, "policy_rate")[0]),
        hh_dep_rate_q=float(np.mean(cur(b.ts, "interest_rate_on_household_deposits"))),
        mort_rate_q=float(np.mean(cur(b.ts, "interest_rates_on_mortgages"))),
        cons_rate_q=float(np.mean(cur(b.ts, "interest_rates_on_household_consumption_loans"))),
        n_hh=int(h.ts.current("n_households")) * C.scale,
        sr_avg_state=float(h.states["average_saving_rate"]),
        coef_fa=float(h.states["coefficient_fa_income"]),
        inv_rate_mean=float(np.mean(h.states["investment_rate"])),
    )
    # saving rates actually used by the behavioural rule at t0
    srs = h.get_saving_rates_by_household(); inc = cur(h.ts, "income")
    row["sr_rule_mean"] = float(np.mean(srs)); row["sr_rule_incw"] = float((srs * inc).sum() / inc.sum())
    # implied "household tax" the government records on household income at t0 (compute_taxes formulas)
    w_emp = w_net_ind[emp].sum()
    row["gov_pit_formula"] = (st["Income Tax"] * (1 - st["Employee Social Insurance Tax"]) * w_emp
        + st["Income Tax"] * cur(h.ts, "rent")[ten == 3].sum() + st["Income Tax"] * cur(h.ts, "income_financial_assets").sum()) * A
    row["gov_ee_si_formula"] = st["Employee Social Insurance Tax"] * w_emp * A
    row["gov_er_si_formula"] = st["Employer Social Insurance Tax"] * w_emp * A
    row["gov_vat_formula"] = st["Value-added Tax"] * cur(h.ts, "consumption").sum() * A
    rows.append(row)
df = pd.DataFrame(rows).set_index("region")
df.to_csv(OUT / f"hh_t0_model_by_region_{TAG}.csv")
nat = df.select_dtypes("number").sum()
for k in [c for c in df.columns if c.startswith(("tau_", "cpi0", "sr_", "coef", "inv_rate", "policy", "hh_dep_rate", "mort_rate", "cons_rate", "ub_per"))]:
    nat[k] = df[k].mean()
nat.to_csv(OUT / f"hh_t0_model_national_{TAG}.csv")
pd.set_option("display.max_rows", 200)
print(nat.round(4).to_string())
print(df[["n_hh", "hh_income", "ind_w_net_employed", "firm_net_wage_implied", "hh_deposits", "sr_rule_incw"]].round(2))
bp = m.countries[provs[0]].banks.parameters
print("BANK PARAMETERS (", provs[0], "):", bp)
