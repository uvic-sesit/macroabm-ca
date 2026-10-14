"""Stage-2 household reconciliation table: StatCan 2022 benchmarks vs model t0 (branch + canonical pickles).
Inputs: outputs/hh_t0_*_{tag}.csv (from hh_t0_pickle_extract.py / hh_t0_model_extract.py) and the DBnomics/StatCan
benchmark files in benchmarks/raw. Output: outputs/hh_reconciliation_2022.csv. Units: $M CAD (flows annual).
"count-adjusted" = model x (15,455,000 CHS households / model household count) to separate per-household level
errors from the household-count error.
"""
import json
import pandas as pd
O = "dev/validation_2022/outputs/"; R = "dev/validation_2022/benchmarks/raw/"

def dbn(file, code, period):
    for x in json.load(open(R + file))["series"]["docs"]:
        if x["series_code"] == code:
            if period == "2022sum":
                return sum(v for p, v in zip(x["period"], x["value"]) if p.startswith("2022"))
            return dict(zip(x["period"], x["value"]))[period]
    raise KeyError(code)

B = {  # benchmark, source id, concept note
 "CoE": (dbn("dbn_36100224.json", "1.1", "2022"), "36-10-0224 v1.1"),
 "NetMixedIncome": (dbn("dbn_36100224.json", "1.2", "2022"), "36-10-0224 v1.2"),
 "RentalIncomeHH": (dbn("dbn_36100224.json", "1.5", "2022"), "36-10-0224 v1.5 (incl. owner-occupied, net)"),
 "PropIncRec": (dbn("dbn_36100224.json", "1.7", "2022"), "36-10-0224 v1.7"),
 "PropIncPaid": (dbn("dbn_36100224.json", "1.8", "2022"), "36-10-0224 v1.8"),
 "TransfersFromGov": (dbn("dbn_36100224.json", "1.14", "2022"), "36-10-0224 v1.14"),
 "EI": (dbn("dbn_36100224.json", "1.15", "2022"), "36-10-0224 v1.15"),
 "TransfersFromCorp": (dbn("dbn_36100224.json", "1.13", "2022"), "36-10-0224 v1.13"),
 "PIT": (dbn("dbn_36100224.json", "1.23", "2022"), "36-10-0224 v1.23"),
 "SocContrib": (dbn("dbn_36100224.json", "1.25", "2022"), "36-10-0224 v1.25"),
 "DI": (dbn("dbn_36100224.json", "1.27", "2022"), "36-10-0224 v1.27"),
 "HFCE": (dbn("dbn_36100224.json", "1.29", "2022"), "36-10-0224 v1.29"),
 "NetSaving": (dbn("dbn_36100224.json", "1.30", "2022"), "36-10-0224 v1.30"),
 "D8": (dbn("dbn_36100224.json", "1.32", "2022"), "36-10-0224 v1.32"),
 "PaidRent": (dbn("dbn_36100124.json", "1.1.1.17", "2022sum"), "36-10-0124 v1.1.1.17 (sum of 2022 SAQR)"),
 "ImputedRent": (dbn("dbn_36100124.json", "1.1.1.18", "2022sum"), "36-10-0124 v1.1.1.18 (sum of 2022 SAQR)"),
 "Deposits": (dbn("dbn_36100580_q.json", "1.4.1.16", "2022-Q4"), "36-10-0580 v1.4.1.16 Households"),
 "FinAssets": (dbn("dbn_36100580_q.json", "1.4.1.14", "2022-Q4"), "36-10-0580 v1.4.1.14 Households"),
 "DwellLand": (dbn("dbn_36100580_q.json", "1.4.1.4", "2022-Q4") + dbn("dbn_36100580_q.json", "1.4.1.114", "2022-Q4"), "36-10-0580 v1.4.1.4 + v1.4.1.114"),
 "Durables": (dbn("dbn_36100580_q.json", "1.4.1.8", "2022-Q4"), "36-10-0580 v1.4.1.8"),
 "Mortgages": (dbn("dbn_36100580_q.json", "1.4.1.70", "2022-Q4"), "36-10-0580 v1.4.1.70 (liability)"),
 "ConsCredit": (dbn("dbn_36100580_q.json", "1.4.1.68", "2022-Q4"), "36-10-0580 v1.4.1.68"),
 "NonMortLoans": (dbn("dbn_36100580_q.json", "1.4.1.69", "2022-Q4"), "36-10-0580 v1.4.1.69"),
 "Liabilities": (dbn("dbn_36100580_q.json", "1.4.1.50", "2022-Q4"), "36-10-0580 v1.4.1.50"),
 "NetWorth": (dbn("dbn_36100580_q.json", "1.4.1.84", "2022-Q4"), "36-10-0580 v1.4.1.84"),
 "Households": (15_455_000, "46-10-0083 CHS 2022, Canada (provinces only), number of households"),
}
rows = []
for tag in ["branch", "canonical", "phaseA"]:
    p = pd.read_csv(O + f"hh_t0_pickle_national_{tag}.csv", index_col=0).iloc[:, 0]
    m = pd.read_csv(O + f"hh_t0_model_national_{tag}.csv", index_col=0).iloc[:, 0]
    k = B["Households"][0] / p["n_hh"]
    M = {  # model concept for each benchmark line (annual $M; stocks $M)
     "CoE": (m.firm_total_wage, "firm wage bill cpi*Theta*sum(w) (incl. employer SSC)"),
     "NetMixedIncome": (0.0, "not modelled (unincorporated income stays in firm GOS)"),
     "RentalIncomeHH": (m.hh_income_rental, "landlord rent net of PIT; owner-occupier imputed income absent"),
     "PropIncRec": (m.hh_income_fa + 4 * 0, "FA income c_FA*OFA (no payer); deposit interest separately below"),
     "PropIncPaid": (None, "interest on mortgages+consumer loans (computed below)"),
     "TransfersFromGov": (m.hh_income_social + m.ind_ub, "TR (equal per hh) + UB to individuals (UB not in realised income)"),
     "EI": (m.ind_ub, "UB to unemployed individuals"),
     "TransfersFromCorp": (0.0, "not modelled"),
     "PIT": (m.gov_pit_formula, "booked tau_inc*(1-tau_ee)*sum w_emp + tau_inc*(rent paid + FAI)"),
     "SocContrib": (m.gov_ee_si_formula + m.gov_er_si_formula, "SSC_ee + SSC_er on net wage base"),
     "DI": (m.hh_income, "household 'Income' (hybrid: net wages + gross TR/FAI + net rent)"),
     "HFCE": (m.hh_total_consumption_purch, "(1+tau_vat)*C (basic C incl. sector-L rent output)"),
     "NetSaving": (m.hh_income - m.hh_total_consumption_purch, "Income - (1+vat)C (behavioural saving, ex-investment)"),
     "D8": (0.0, "not modelled"),
     "PaidRent": (m.hh_rent_actual, "rent transfers renter->landlord (housing market)"),
     "ImputedRent": (m.hh_rent_imputed, "imputed rent attached to owner-occupied dwellings"),
     "Deposits": (m.hh_deposits, "wealth_deposits"),
     "FinAssets": (m.hh_deposits + m.hh_other_fa, "deposits + OFA (equity, funds, pensions in OFA)"),
     "DwellLand": (m.hh_main_res + m.hh_other_prop, "main residence + other properties (market value)"),
     "Durables": (m.hh_other_real, "other real assets = vehicles + valuables + self-employment businesses"),
     "Mortgages": (m.hh_mortgage, "mortgage_debt"),
     "ConsCredit": (0.0, "credit lines + credit cards zeroed at build (hfcs_synthetic_population.py:442-446)"),
     "NonMortLoans": (m.hh_cons_loans, "other non-mortgage loans -> consumption loans"),
     "Liabilities": (m.hh_debt, "mortgages + consumption loans"),
     "NetWorth": (m.hh_net_wealth, "net_wealth"),
     "Households": (p.n_hh, "agents x scale"),
    }
    mr = pd.read_csv(O + f"hh_t0_model_by_region_{tag}.csv", index_col=0)
    paid = 4 * ((mr.hh_mortgage * mr.mort_rate_q).sum() + (mr.hh_cons_loans * mr.cons_rate_q).sum())
    M["PropIncPaid"] = (paid, M["PropIncPaid"][1])
    for key, (bv, src) in B.items():
        mv, concept = M[key]
        adj = mv * k if key not in ("Households",) else mv
        rows.append(dict(pickle=tag, line=key, benchmark=bv, source=src, model=mv, model_count_adj=adj,
                         resid=mv - bv, resid_pct=100 * (mv / bv - 1) if bv else None,
                         resid_count_adj_pct=100 * (adj / bv - 1) if bv else None, model_concept=concept))
df = pd.DataFrame(rows)
df.to_csv(O + "hh_reconciliation_2022.csv", index=False)
pd.set_option("display.width", 250, "display.max_colwidth", 60)
print(df[df.pickle == "branch"][["line", "benchmark", "model", "resid_pct", "resid_count_adj_pct"]].round(1).to_string(index=False))
print("count factor k =", B["Households"][0] / pd.read_csv(O + "hh_t0_pickle_national_branch.csv", index_col=0).iloc[:, 0]["n_hh"])
print("SNA check: DI-HFCE =", B["DI"][0] - B["HFCE"][0], " +D8 =", B["DI"][0] - B["HFCE"][0] + B["D8"][0], " vs net saving", B["NetSaving"][0], " rate S/DI =", B["NetSaving"][0] / B["DI"][0])
