"""Reproduce fixed-weight H7 aggregate checks, without exporting microdata."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--households", type=Path, required=True)
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    d = pd.read_csv(args.households)
    raw = args.raw / "can_2022"
    sfs_path = raw / "pumf/sfs_2023/sfs2023_efam_pumf.csv"
    s = pd.read_csv(sfs_path, usecols=["PWEIGHT", "PWAPRVAL", "PWASTRST", "PWDPRMOR", "PWDSTOMR"])
    controls = raw / "controls/36100660.csv"
    c = pd.read_csv(controls, low_memory=False)
    labels = ["Lowest", "Second", "Third", "Fourth", "Highest"]
    c = c[c.REF_DATE.eq("2022-10") & c.GEO.eq("Canada") & c.Statistics.eq("Distribution of value") & c.Wealth.eq("Net worth (wealth)")]
    benchmark = [float(c.loc[c.Characteristics.eq(f"{q} income quintile"), "VALUE"].iloc[0]) for q in labels]
    def metrics(frame, weight, properties, mortgages):
        w = frame[weight].to_numpy(float)
        result = {}
        for name, p, m in zip(("main", "other"), properties, mortgages):
            v, loan = frame[p].to_numpy(float), frame[m].to_numpy(float)
            result[name] = dict(mortgages_CAD=float(w @ loan),
                                underwater_mortgagor_pct=float(100*w[(loan>v)&(loan>0)].sum()/w[loan>0].sum()))
        total = sum(x["mortgages_CAD"] for x in result.values())
        for x in result.values():
            x["mortgage_share_pct"] = 100*x["mortgages_CAD"]/total
        return result
    model = metrics(d, "Weight", ["Value of the Main Residence", "Value of other Properties"], ["Outstanding Balance of HMR Mortgages", "Outstanding Balance of Mortgages on other Properties"])
    survey = metrics(s, "PWEIGHT", ["PWAPRVAL", "PWASTRST"], ["PWDPRMOR", "PWDSTOMR"])
    # Split a record crossing a quintile boundary, rather than moving a whole weight.
    order = np.argsort(d.Income.to_numpy(), kind="stable")
    w, nw = d.Weight.to_numpy()[order], d["Net Worth"].to_numpy()[order]
    right = np.cumsum(w); left = right-w; total=w.sum()
    shares = [float(100*np.dot(np.maximum(0,np.minimum(right,(q+1)*total/5)-np.maximum(left,q*total/5)),nw)/np.dot(w,nw)) for q in range(5)]
    files = [args.households, controls, sfs_path]
    result = dict(model=model, sfs_2023=survey, net_worth_income_quintiles_pct=shares,
                  table_36100660_2022Q4_pct=benchmark,
                  provenance={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                  sources=["https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610066001", "https://www150.statcan.gc.ca/n1/en/catalogue/13M0006X"],
                  limitations="2023 SFS economic families versus 2022 NBSA households; model quintiles use mapped gross income, DHEA uses equivalized disposable income. Comparisons are diagnostics, not calibration constraints.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
