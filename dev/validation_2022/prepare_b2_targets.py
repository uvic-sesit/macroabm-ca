"""Freeze DHEA primary and SHS secondary distribution benchmarks before runs."""
import hashlib
import json
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent;OUT=HERE/'benchmarks/B2';RAW=OUT/'raw'


def main():
    x=pd.read_csv(RAW/'36100587.csv',low_memory=False)
    names=['Lowest income quintile','Second income quintile','Third income quintile','Fourth income quintile','Highest income quintile']
    y=x[(x.REF_DATE==2022)&(x.GEO=='Canada')&x.Characteristics.isin(names)&
        (x['Income, consumption and savings']=='Household final consumption expenditure (HFCE)')].copy()
    y.to_csv(OUT/'dhea_hfce_2022.csv',index=False)
    dhea=y[y.Statistics=='Value'].set_index('Characteristics').loc[names]
    dshares=(dhea.VALUE/dhea.VALUE.sum()).tolist()
    x=pd.read_csv(RAW/'11100223_2023.csv')
    names2=['Lowest quintile','Second quintile','Third quintile','Fourth quintile','Highest quintile']
    shs=x[(x.GEO=='Canada')&(x.Statistic=='Average expenditure per household')&
        (x['Household expenditures, summary-level categories']=='Total current consumption')&
        x['Before-tax household income quintile'].isin(names2)].copy()
    shs.to_csv(OUT/'shs_consumption_2023.csv',index=False)
    shs=shs.set_index('Before-tax household income quintile').loc[names2]
    sources=dict(primary=json.loads((RAW/'36100587_download.json').read_text()),
        secondary=json.loads((RAW/'11100223_2023_provenance.json').read_text()))
    meta=dict(reference_dates=dict(DHEA=2022,SHS=2023),sources=sources,
        primary_table='36-10-0587-01',primary_vectors=dhea.VECTOR.tolist(),primary_shares=dshares,
        secondary_table='11-10-0223-01',secondary_vectors=shs.VECTOR.tolist(),secondary_shares=(shs.VALUE/shs.VALUE.sum()).tolist(),
        secondary_annual_means=shs.VALUE.tolist(),
        definitions=dict(DHEA='Household disposable income equivalised using OECD-modified units (1/.5/.3), household-weighted quintiles; HFCE excluding social transfers in kind.',
                         SHS='Household total before-tax income, not equivalised; current consumption.'),
        gate_protocol=dict(G1='Positive cash-income households; realized zero goods at t0 and each quarter strictly <2%.',
            G2='Accounting <=1e-8; Q4-Q12 constrained-share OLS <=.25 pp/q; Q12 saving [-5.6,4.4]%; Q1 consumption >=95% target.',
            G3='DHEA shares primary, relative deviation <=15% in every quintile at t0 and every quarter; SHS secondary only. No distributional rescale.',
            G4='Q12 C and GDP within5% of same-seed accepted FE arm F, e386f4e lineage.'),
        kappa='User-approved unestimated assumptions: .01/q base, .005/.02/q sensitivities; asymmetric above .005 and below .02. Smoothing .25.',
        mapping_limits='Model cash DI omits SNA noncash income components; source household-member skeleton retained. OECD equivalence is applied without reweighting. SHS gross-income rank reconstructed from modeled net components/tax rates. Noncash owner housing consumption is not separately tagged inside L; subtracting the rent_imputed memo would not be an exact bridge. Expected owner-imputed-rent bias raises upper-quintile SHS-comparison shares.',
        extracts={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['dhea_hfce_2022.csv','shs_consumption_2023.csv']})
    (OUT/'distribution_provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('DHEA shares',dshares,'SHS shares',meta['secondary_shares'])


if __name__=='__main__':main()
