"""Stage-2 household t0 extraction from the canadianized 2022 pickle (no simulation).
Writes per-region and national annualised ($M CAD) aggregates of the household block as built.
Usage: .venv/Scripts/python.exe dev/validation_2022/scripts/hh_t0_pickle_extract.py
"""
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from macro_data import DataWrapper

import sys
PKL = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dev/pkl_files/io2022_13prov_2022_canadianized.pkl")
TAG = sys.argv[2] if len(sys.argv) > 2 else "canonical"
OUT = Path("dev/validation_2022/outputs"); OUT.mkdir(parents=True, exist_ok=True)
d = DataWrapper.init_from_pickle(PKL)
A = 4.0 / 1e6  # quarterly CAD -> annual $M
S = 1.0 / 1e6  # stock CAD -> $M
rows, meta = [], {}
for r, c in d.synthetic_countries.items():
    p, hd, idd = c.population, c.population.household_data, c.population.individual_data
    sc = c.scale
    sr = hd["Saving Rate"].astype(float); inc = hd["Income"].astype(float)
    hm = c.housing_market.housing_market_data
    oo = hm["Is Owner-Occupied"].astype(bool)
    occ = hm["Corresponding Inhabitant Household ID"].notna() & (hm["Corresponding Inhabitant Household ID"] != -1)
    ten = hd["Tenure Status of the Main Residence"]
    cg = c.central_government.central_gov_data.iloc[0]
    iv = c.industry_data["industry_vectors"]
    act = idd["Activity Status"]
    row = dict(
        region=r, scale=sc, n_hh_agents=len(hd), n_hh=len(hd) * sc, n_ind_agents=len(idd),
        owner_share=float(ten.isin([1, 2, 4]).mean()), renter_share=float((ten == 3).mean()),
        social_housing_share=float((hd["Corresponding Inhabited House ID"].fillna(-1) == -1).mean()),
        tenure_codes=json.dumps({int(k): int(v) for k, v in ten.value_counts().items()}),
        # flows (annual $M)
        Income=inc.sum() * A, Validated_Income=hd["Validated Income"].astype(float).sum() * sc * A,
        Employee_Income_hh=hd["Employee Income"].astype(float).sum() * A,
        Social_Transfers=hd["Regular Social Transfers"].astype(float).sum() * A,
        Rental_Income=hd["Rental Income from Real Estate"].astype(float).sum() * A,
        FA_Income=hd["Income from Financial Assets"].astype(float).sum() * A,
        Consumption_basic=hd["Consumption"].astype(float).sum() * A,
        Investment_basic=hd["Investment"].astype(float).sum() * A,
        Rent_Paid=hd["Rent Paid"].astype(float).sum() * A,
        Rent_Imputed=hd["Rent Imputed"].astype(float).sum() * A if "Rent Imputed" in hd else np.nan,
        Debt_Installments=hd["Debt Installments"].astype(float).sum() * A,
        SR_mean=float(sr.mean()), SR_incw=float((sr * inc).sum() / inc.sum()),
        SR_neg_share=float((sr < 0).mean()), SR_zero_share=float((sr == 0).mean()),
        Ind_EmployeeIncome_employed=idd.loc[act == 1, "Employee Income"].astype(float).sum() * A,
        Ind_Income_all=idd["Income"].astype(float).sum() * A,
        Ind_UB=idd["Income from Unemployment Benefits"].astype(float).sum() * A,
        n_employed_agents=int((act == 1).sum()), n_unemployed_agents=int((act == 2).sum()),
        n_nea_agents=int((act == 3).sum()), n_firm_inv=int((act == 4).sum()), n_bank_inv=int((act == 5).sum()),
        Firm_TotalWages=c.firms.firm_data["Total Wages"].astype(float).sum() * A,
        Firm_TotalWagesPaid=c.firms.firm_data["Total Wages Paid"].astype(float).sum() * A,
        IO_LabourComp=iv["Labour Compensation in LCU"].sum() * A,
        IO_HH_Consumption=iv["Household Consumption in LCU"].sum() * A,
        IO_HH_Capital=iv["Household Capital Inputs in LCU"].sum() * A,
        CG_UB_total=float(cg["Total Unemployment Benefits"]) * A,
        CG_Other_Benefits=float(cg["Other Social Benefits"]) * A,
        housing_rent_rented=float(hm.loc[~oo & occ, "Rent"].sum()) * A,
        housing_rent_oo=float(hm.loc[oo & occ, "Rent"].sum()) * A,
        housing_rent_vacant=float(hm.loc[~occ, "Rent"].sum()) * A,
        n_houses=len(hm), n_vacant=int((~occ).sum()),
        # stocks ($M)
        Deposits=hd["Wealth in Deposits"].astype(float).sum() * S,
        Other_FA=hd["Wealth in Other Financial Assets"].astype(float).sum() * S,
        Main_Residence=hd["Value of the Main Residence"].astype(float).sum() * S,
        Other_Properties=hd["Value of other Properties"].astype(float).sum() * S,
        Other_Real=hd["Wealth Other Real Assets"].astype(float).sum() * S,
        Real_Assets=hd["Wealth in Real Assets"].astype(float).sum() * S,
        Housing_Value_market=float(hm["Value"].sum()) * S,
        HMR_Mortgages=hd["Outstanding Balance of HMR Mortgages"].astype(float).sum() * S,
        Other_Mortgages=hd["Outstanding Balance of Mortgages on other Properties"].astype(float).sum() * S,
        Credit_Line=hd["Outstanding Balance of Credit Line"].astype(float).sum() * S,
        Credit_Card=hd["Outstanding Balance of Credit Card Debt"].astype(float).sum() * S,
        Other_Loans=hd["Outstanding Balance of other Non-Mortgage Loans"].astype(float).sum() * S,
        Debt=hd["Debt"].astype(float).sum() * S, Net_Wealth=hd["Net Wealth"].astype(float).sum() * S,
    )
    rows.append(row)
    meta[r] = dict(tax=str(c.tax_data), coef_fa=float(p.coefficient_fa_income),
                   dividend_payout=float(c.dividend_payout_ratio), cg=cg.to_dict())
df = pd.DataFrame(rows).set_index("region")
tot = df.drop(columns=["tenure_codes"]).select_dtypes("number").sum()
for k in ["SR_mean", "SR_incw", "owner_share", "renter_share", "social_housing_share", "SR_neg_share", "SR_zero_share", "scale"]:
    tot[k] = np.nan
tot["owner_share_hhw"] = float((df.owner_share * df.n_hh).sum() / df.n_hh.sum())
tot["SR_incw"] = float((df.SR_incw * df.Income).sum() / df.Income.sum())
df.to_csv(OUT / "hh_t0_pickle_by_region.csv")
tot.to_csv(OUT / "hh_t0_pickle_national.csv")
json.dump(meta, open(OUT / "hh_t0_pickle_meta.json", "w"), indent=1, default=str)
pd.set_option("display.width", 250, "display.max_rows", 200)
print(tot.round(3).to_string())
print(df[["n_hh", "Income", "Consumption_basic", "SR_incw", "owner_share", "Deposits", "Debt"]].round(3))
