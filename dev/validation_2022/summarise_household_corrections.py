"""Aggregate the saved diagnostic panels; never run a simulation here."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs/household_corrections"


def main():
    summaries, losses, bridge, saving = [], [], [], []
    frames = {}
    for arm in ["i", "ii", "iii", "iv", "v", "d1", "deposit"]:
        f = pd.read_csv(OUT/f"{arm}_q12_s0_households_national.csv")
        frames[arm] = f
        last = f.iloc[-1]
        initial_debt = f.debt.iloc[0] + f.principal.iloc[0] + f.household_writeoffs.iloc[0] - f.new_credit.iloc[0]
        summaries.append(dict(arm=arm, household_writeoffs_bn=f.household_writeoffs.sum()/1e9,
                              bank_loan_losses_bn=f.bank_loan_losses.sum()/1e9,
                              q12_gdp_bn=last.gdp_output/1e9, q12_saving_pct=100*last.cash_saving_rate,
                              q12_debt_bn=last.debt/1e9, new_credit_bn=f.new_credit.sum()/1e9,
                              principal_bn=f.principal.sum()/1e9,
                              initial_debt_bn=initial_debt/1e9,
                              debt_bridge_error=last.debt-initial_debt-f.new_credit.sum()+f.principal.sum()+f.household_writeoffs.sum()))
        for _,r in f.iterrows():
            losses.append(dict(arm=arm, quarter=int(r.t)+1, household_writeoffs_bn=r.household_writeoffs/1e9,
                               bank_loan_losses_bn=r.bank_loan_losses/1e9))
        if arm in ["iv", "d1"]:
            for t in [0,11]:
                r=f.iloc[t]
                bridge.append(dict(arm=arm,quarter=t+1,L_sales_bn=r.L_sales/1e9,L_employment=r.L_employment,
                                   rent_offset_bn=r.L_offset/1e9,unoffset_rent_bn=r.L_unoffset/1e9))
    # Fixed order, old insolvency in all four: increments include dynamic feedback.
    for component,a,b in [("D2","iii","iv"),("D1","iv","d1"),("deposit-only saving","d1","deposit")]:
        for t in [0,11]:
            saving.append(dict(component=component,quarter=t+1,before_pct=100*frames[a].cash_saving_rate.iloc[t],
                               after_pct=100*frames[b].cash_saving_rate.iloc[t],
                               change_pp=100*(frames[b].cash_saving_rate.iloc[t]-frames[a].cash_saving_rate.iloc[t])))
    for name,rows in [("summary",summaries),("writeoffs_by_quarter",losses),("L_sector",bridge),("saving_decomposition",saving)]:
        pd.DataFrame(rows).to_csv(OUT/f"{name}.csv",index=False)
    benchmark = pd.read_csv(HERE/"benchmarks/household_corrections/36100112_2022.csv")
    b=benchmark[(benchmark.GEO=="Canada") & (benchmark["Seasonal adjustment"]=="Seasonally adjusted at annual rates")]
    annual=lambda label:float(b.loc[b.Estimates==label,"VALUE"].mean())
    di=annual("Household disposable income"); c=annual("Less: household final consumption expenditure")
    d8=annual("Plus: change in pension entitlements")
    result=dict(sna_2022=dict(disposable_income_millions=di,consumption_millions=c,pension_adjustment_millions=d8,
                            net_saving_rate_pct=100*(di-c+d8)/di, excluding_pension_adjustment_pct=100*(di-c)/di),
                summaries=summaries,saving_decomposition=saving)
    xml=OUT/"full_tests.xml"
    if xml.exists():
        tree=ET.parse(xml)
        failures=[dict(test=x.attrib,reason=(x.find("failure").attrib if x.find("failure") is not None else x.find("error").attrib))
                  for x in tree.iter("testcase") if x.find("failure") is not None or x.find("error") is not None]
        result["test_suites"]=[x.attrib for x in tree.iter("testsuite")]
        result["test_failures"]=failures
        result["known_nan_failures"] = sum("Nan in transactor_total_real_supply" in x["reason"].get("message", "") for x in failures)
        rerun = OUT/"temp_errors_rerun.xml"
        if rerun.exists():
            result["temp_directory_rerun_suites"] = [x.attrib for x in ET.parse(rerun).iter("testsuite")]
    result["result_sha256"]={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob("*.csv")}
    (OUT/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(pd.DataFrame(summaries).to_string(index=False))


if __name__ == "__main__":
    main()
