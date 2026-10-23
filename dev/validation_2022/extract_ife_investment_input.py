"""Read accepted input investment fields without constructing a simulation."""
import hashlib
import json
from pathlib import Path
import warnings
import pandas as pd
from macro_data import DataWrapper
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'dev/pkl_files/io2022_household_agreed_bankcap.pkl'
OUT=HERE/'outputs/IFE'


def main():
    warnings.filterwarnings('ignore')
    data=DataWrapper.init_from_pickle(SOURCE)
    rates=[];weights=[]
    for n,c in data.synthetic_countries.items():
        p=c.population;hd=p.household_data;r=hd['Investment Rate'].to_numpy()
        rates.append(dict(region=str(n),rate_min=r.min(),rate_max=r.max(),
            income=hd['Income'].sum(),initial_basic_investment=hd['Investment'].sum()))
        weights.extend(dict(region=str(n),industry=i,weight=float(v),initial_basic=hd['Investment'].sum()*float(v))
                       for i,v in enumerate(p.investment_weights))
    OUT.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rates).to_csv(OUT/'input_investment_rates.csv',index=False)
    pd.DataFrame(weights).to_csv(OUT/'input_investment_weights.csv',index=False)
    meta=dict(source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        fields=['population.household_data.Investment Rate','population.household_data.Income',
                'population.household_data.Investment','population.investment_weights'],
        interpretation='Read-only initial model fields. Rates are fractions of quarterly income; investment is basic-price quarterly CAD. Model clips/normalizes negative industry weights before use.')
    (OUT/'input_investment_provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('Read-only investment input snapshot complete')


if __name__=='__main__':main()
