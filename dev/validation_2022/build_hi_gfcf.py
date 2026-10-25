"""Independent observed GFCF build; never change a stock or close GDP with a plug."""
import json
from pathlib import Path
import numpy as np,pandas as pd
from hi_income_audit import SOURCE,OUT,sha
from macro_data import DataWrapper
from macro_data.processing.synthetic_firms.observed_gfcf_init import observed_acquisitions
TARGET=SOURCE.with_name('io2022_household_f_cfc_gfcf_hi_2026_10_25.pkl');HERE=Path(__file__).resolve().parent

def main():
    if TARGET.exists():raise FileExistsError(TARGET)
    observed=pd.read_csv(HERE/'outputs/IH/observed_investment_concordance.csv');d=DataWrapper.init_from_pickle(SOURCE);rows=[]
    for name,c in d.synthetic_countries.items():
        name=str(name)
        if not name.startswith('CAN_'):continue
        f=c.firms;old=f.initial_capital_purchases.copy();frame=f.firm_data;industry=frame.Industry.to_numpy(int);codes=list(d.industries)
        v=observed[observed.region==name].groupby('industry_code').allocated_observed_investment.sum();targets=np.zeros(len(frame))
        for code,value in v.items():
            ids=industry==codes.index(code);output=(frame.Production*frame.Price).to_numpy()[ids];den=output.sum()
            if value>0 and den<=0:raise ValueError((name,code,'no operating output'))
            targets[ids]=value*output/den if den else 0.
        financial=frame[['Debt','Deposits','Equity']].copy();stock=f.capital_inputs_stock.copy();hh=c.population.household_data.copy(deep=True);banks=c.banks.bank_data.copy(deep=True)
        unsupported=(targets>1e-8)&((np.maximum(0,old).sum(axis=1)+np.maximum(0,stock).sum(axis=1))<=0)
        effective=np.where(unsupported,0.,targets)
        f.unallocated_observed_gfcf=np.where(unsupported,targets,0.)
        f.initial_capital_purchases=observed_acquisitions(old,stock,effective,np.ones(old.shape[1]))
        pd.testing.assert_frame_equal(financial,frame[['Debt','Deposits','Equity']]);np.testing.assert_array_equal(stock,f.capital_inputs_stock);pd.testing.assert_frame_equal(hh,c.population.household_data);pd.testing.assert_frame_equal(banks,c.banks.bank_data)
        assert np.allclose(f.initial_capital_purchases.sum(axis=1),effective,rtol=1e-12,atol=.001)
        for i in range(len(frame)):rows.append(dict(region=name,industry=codes[industry[i]],firm=i,old_investment=old[i].sum(),observed_allocation=targets[i],new_investment=f.initial_capital_purchases[i].sum(),CFC=f.used_capital_inputs[i].sum(),unallocated=float(f.unallocated_observed_gfcf[i])))
    d.save(TARGET);r=pd.DataFrame(rows);r.to_csv(OUT/'gfcf_build.csv',index=False)
    total=4*r.new_investment.sum();gate=dict(group_max_relative_error=float(((r.new_investment-r.observed_allocation).abs()/r.observed_allocation.clip(lower=1)).max()),national_annual=total,Canada_v90968052=411341e6,national_relative_gap=total/411341e6-1,stock_checks_exact=True,source_sha256=sha(SOURCE),new_pickle_sha256=sha(TARGET),new_pickle=str(TARGET),method='Existing observed CFC concordance, source industry/province investment, within-industry output shares and inherited capital-good composition. No stock/cash/trade/inventory change or national rescale.')
    gate['unallocated_annual']=float(4*r.unallocated.sum())
    gate['unsupported_rows']=r[r.unallocated>0][['region','industry','unallocated']].to_dict('records')
    gate['level_passed']=gate['group_max_relative_error']<=.02 and abs(gate['national_relative_gap'])<=.005
    (OUT/'gfcf_build_provenance.json').write_text(json.dumps(gate,indent=2)+'\n');print(json.dumps(gate),flush=True)
if __name__=='__main__':main()
