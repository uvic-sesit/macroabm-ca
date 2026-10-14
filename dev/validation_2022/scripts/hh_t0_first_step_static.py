"""Static (no-simulation) first-step consistency indicators from the t0 extracts.
C0  = t0 household consumption (basic prices) as initialised.
C1* = consumption the t=1 rule would target if expected income equalled firm-consistent income at cpi=1, pi_e=0:
      C1* = (1 - s_rule_r) / (1 + vat) * [firm-implied net wages + UB + social transfers + rental + FA income]
      (s_rule_r = regional unweighted-mean saving rate used by AverageSavingRatesSetter).
Labour jump = firm-implied net wage bill - t0 household labour income (wage reset by WorkEffortFirmWageSetter at t=1).
"""
import pandas as pd
O = "dev/validation_2022/outputs/"
out = []
for tag in ["canonical", "branch"]:
    m = pd.read_csv(O + f"hh_t0_model_by_region_{tag}.csv", index_col=0)
    p = pd.read_csv(O + f"hh_t0_pickle_by_region_{tag}.csv", index_col=0)
    y1 = m.firm_net_wage_implied + m.ind_ub + m.hh_income_social + m.hh_income_rental + m.hh_income_fa
    c1 = (1 - m.sr_rule_incw) / (1 + m.tau_vat) * y1
    df = pd.DataFrame({"tag": tag, "Y0": m.hh_income, "Y1star": y1, "labour0": m.hh_income_employee,
                       "labour_firm": m.firm_net_wage_implied, "labour_jump_pct": 100 * (m.firm_net_wage_implied / m.hh_income_employee - 1),
                       "SR_incw_t0": p.SR_incw, "SR_rule": m.sr_rule_incw, "C0": m.hh_consumption_basic, "C1star": c1,
                       "C_jump_pct": 100 * (c1 / m.hh_consumption_basic - 1)})
    tot = df.select_dtypes("number").sum()
    tot["labour_jump_pct"] = 100 * (tot.labour_firm / tot.labour0 - 1); tot["C_jump_pct"] = 100 * (tot.C1star / tot.C0 - 1)
    tot["SR_incw_t0"] = 1 - (df.C0 * (1 + m.tau_vat)).sum() / df.Y0.sum(); tot["SR_rule"] = (df.SR_rule * df.Y0).sum() / df.Y0.sum()
    df.loc["CANADA"] = tot; df.loc["CANADA", "tag"] = tag
    out.append(df)
res = pd.concat(out)
res.to_csv(O + "hh_t0_first_step_static.csv")
pd.set_option("display.width", 250)
print(res.round(3).to_string())
