"""Serial unchanged regional GDP checks; never return a failed initialization."""
import json
import pandas as pd
import check_hi_gfcf as check
from build_sg import target
from prepare_sg import OUT
def main():
    gates={}
    for arm in ['FS','FS_T']:
        destination=OUT/arm;destination.mkdir(exist_ok=True)
        check.TARGET=target(arm);check.OUT=destination;check.main()
        f=pd.read_csv(OUT/f'{arm}_firm_bridge.csv');g=pd.read_csv(destination/'gfcf_GDP_initialization.csv')
        every=bool(g.passed.all());income=bool(((g.income-g.output).abs()<=1e-8+1e-5*g.output.abs()).all())
        gates[arm]=dict(regional_initialization=every,independent_income=income,margin=bool(f.margin_gap_pp.abs().max()<=1),margin_exceptions=int((f.margin_gap_pp.abs()>1).sum()),max_margin_gap_pp=float(f.margin_gap_pp.abs().max()),above_price=bool(not f.above_price_nonnegative_NOS.any()),above_price_exceptions=int(f.above_price_nonnegative_NOS.sum()),inherited_floor_exceptions=int(((f.margin_gap_pp.abs()>1)&f.inherited_floor).sum()),accounting='No dynamic accounting claim: pre-run adoption gates fail.',passed=every and income and bool(f.margin_gap_pp.abs().max()<=1) and not bool(f.above_price_nonnegative_NOS.any()))
    (OUT/'step1_gates.json').write_text(json.dumps(gates,indent=2)+'\n');print(json.dumps(gates,indent=2))
if __name__=='__main__':main()
