"""Observed non-residential CFC, new input only, no firm-behaviour change."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from macro_data import DataWrapper
from macro_data.processing.synthetic_firms.canadian_firm_accounts import cfc_coefficients,finite_initial_unit_costs
SOURCE=ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt.pkl'
TARGET=ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt_cfc_v2.pkl'
RAW=HERE/'benchmarks/B2/raw';OUT=HERE/'outputs/B2/firm_data'
GEO=dict(CAN_NL='Newfoundland and Labrador',CAN_PE='Prince Edward Island',CAN_NS='Nova Scotia',CAN_NB='New Brunswick',
    CAN_QC='Quebec',CAN_ON='Ontario',CAN_MB='Manitoba',CAN_SK='Saskatchewan',CAN_AB='Alberta',CAN_BC='British Columbia',
    CAN_YT='Yukon',CAN_NT='Northwest Territories',CAN_NU='Nunavut')
GROUPS=[(['Crop production','Animal production','Support activities for agriculture and forestry'],['A01']),
    (['Forestry and logging'],['A02']),(['Fishing, hunting and trapping'],['A03']),
    (['Conventional oil and gas extraction','Non-conventional oil extraction'],['B06']),
    (['Mining and quarrying (except oil and gas)'],['B05','B07','B08']),
    (['Support activities for mining and oil and gas extraction'],['B09']),(['Utilities'],['D','E']),
    (['Construction'],['F']),(['Food manufacturing','Beverage and tobacco products manufacturing'],['C10T12']),
    (['Textile and textile product mills','Clothing and leather and allied product manufacturing'],['C13T15']),
    (['Wood product manufacturing'],['C16']),(['Paper manufacturing','Printing and related support activities'],['C17_18']),
    (['Petroleum and coal products manufacturing'],['C19']),(['Chemical manufacturing'],['C20','C21']),
    (['Plastics and rubber products manufacturing'],['C22']),(['Non-metallic mineral product manufacturing'],['C23']),
    (['Primary metal manufacturing'],['C24A','C24B']),(['Fabricated metal product manufacturing'],['C25']),
    (['Computer and electronic product manufacturing'],['C26']),(['Electrical equipment, appliance and component manufacturing'],['C27']),
    (['Machinery manufacturing'],['C28']),(['Transportation equipment manufacturing'],['C29','C301','C302T309']),
    (['Furniture and related product manufacturing','Miscellaneous manufacturing'],['C31T33']),
    (['Wholesale trade','Retail trade'],['G']),(['Transportation and warehousing'],['H49','H50','H51','H52','H53']),
    (['Information and cultural industries'],['J58T60','J61','J62_63']),
    (['Finance and insurance','Holding companies'],['K']),(['Real estate and rental and leasing'],['L','N']),
    (['Professional, scientific and technical services'],['M','J62_63']),
    (['Administrative and support, waste management and remediation services'],['N','E']),
    (['Educational services','Government educational services'],['P']),
    (['Health care and social assistance','Hospitals','Nursing and residential care facilities'],['Q']),
    (['Arts, entertainment and recreation'],['R']),(['Accommodation and food services'],['I']),
    (['Other services (except public administration)'],['S']),
    (['Non-profit institutions serving households'],['P','Q','R','S'])]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def output_split(amount,outputs):
    outputs=np.maximum(0.,np.asarray(outputs,float))
    return amount*outputs/outputs.sum() if outputs.sum()>0 else np.zeros_like(outputs)


def main():
    if TARGET.exists():raise FileExistsError('Do not overwrite a new build')
    data=DataWrapper.init_from_pickle(SOURCE);before=sha(SOURCE)
    raw=pd.read_csv(RAW/'36100096_2022.csv')
    selected=raw[(raw.Prices=='Current prices')&(raw['Flows and stocks']=='Geometric depreciation')&(raw.Assets=='Total non-residential')].copy()
    selected.to_csv(OUT/'observed_nonres_CFC_2022.csv',index=False)
    sources=selected.set_index(['GEO','Industry']);codes=list(data.industries)
    observed=pd.read_csv(OUT/'observed_VA_2022.csv',index_col=0)
    outputs={str(n):c.industry_data['industry_vectors']['Output in LCU'].to_numpy() for n,c in data.synthetic_countries.items() if str(n) in GEO}
    national_output=sum(outputs.values());allocation=[];rows=[];boundaries=[]
    for name,c in data.synthetic_countries.items():
        n=str(name)
        if n not in GEO:continue
        f=c.firms;d=f.firm_data;out=outputs[n];target=np.zeros(len(codes));groups=list(GROUPS)
        # Government O is the government total excluding observed P/Q facilities.
        groups += [(['Government sector','-Government educational services','-Hospitals','-Nursing and residential care facilities'],['O'])]
        for labels,model in groups:
            indices=[codes.index(g) for g in model];amount=0.;vectors=[];fallback=[]
            for label in labels:
                sign=-1 if label.startswith('-') else 1;label=label.lstrip('-')
                source=sources.loc[(GEO[n],label)];value=float(source.VALUE)
                if not np.isfinite(value):
                    source=sources.loc[('Canada',label)];denom=national_output[indices].sum()
                    value=float(source.VALUE)*out[indices].sum()/denom if denom else 0.
                    fallback.append(label+' national CFC x regional output share')
                if not np.isfinite(value):raise ValueError(f'No observed CFC aggregate for {n} {label}')
                amount+=sign*value*1e6/4;vectors.append(str(source.VECTOR))
            if amount<-.01:raise ValueError('Overlapping public subaggregate exceeds observed government CFC')
            amount=max(0.,amount);parts=output_split(amount,out[indices]);target[indices]+=parts
            if amount>0 and not parts.any():boundaries.append(dict(region=n,source=' + '.join(labels),quarterly_CFC=amount,reason='source CFC without modeled operating output; holding treatment deferred'))
            for j,part in zip(indices,parts):allocation.append(dict(region=n,source_industry=' + '.join(labels),vectors=';'.join(vectors),industry=codes[j],
                observed_quarterly_group_CFC=amount,allocated_CFC=part,output_share=out[j]/out[indices].sum() if out[indices].sum() else 0.,fallback=';'.join(fallback)))
        old=f.capital_inputs_depreciation_matrix.copy();old_CFC=f.used_capital_inputs.sum(axis=1).copy()
        # The accepted input used one proxy for both CFC and new acquisitions.
        # Replace depreciation only; retain the accepted t0 acquisition flow.
        f.initial_capital_purchases=f.used_capital_inputs.copy()
        composition=np.maximum(0.,old)
        for j in range(len(codes)):
            if composition[:,j].sum()==0 and target[j]>1e-3:
                stock=f.capital_inputs_stock[d.Industry.to_numpy(int)==j].sum(axis=0)
                if stock.sum()>0:
                    composition[:,j]=stock
                    boundaries.append(dict(region=n,source=codes[j],quarterly_CFC=0.,reason='capital-good mix fallback: observed initial capital-stock composition'))
                else:
                    boundaries.append(dict(region=n,source=codes[j],quarterly_CFC=target[j],reason='observed CFC has no modeled capital-stock/composition; not charged to nonexistent assets'))
                    target[j]=0.
        matrix=cfc_coefficients(composition,target,out)
        c.industry_data['capital_inputs_depreciation_matrix'].iloc[:,:]=matrix
        f.capital_inputs_depreciation_matrix=matrix.copy()
        industries=d.Industry.to_numpy(int)
        f.used_capital_inputs=d.Production.to_numpy()[:,None]*matrix[:,industries].T
        financial=d[['Debt','Deposits','Equity']].to_numpy().copy();stocks=f.capital_inputs_stock.copy()
        f.set_additional_initial_conditions(c.industry_data,c.banks,c.credit_market.longterm_loans,c.credit_market.shortterm_loans,c.tax_data)
        costs=d['Total Wages Paid'].to_numpy()+f.used_intermediate_inputs.sum(axis=1)+f.used_capital_inputs.sum(axis=1)+d['Taxes paid on Production'].to_numpy()
        d['Unit Costs']=finite_initial_unit_costs(d.Production.to_numpy(),costs)
        # Do not re-run the legacy government's wholesale initializer: it
        # overwrites accepted household VAT/tax corrections unrelated to CFC.
        # Corporate taxes are the only fiscal receipt changed by this build.
        old_corporate=c.central_government.central_gov_data['Corporate Taxes'].iloc[0]
        new_corporate=d['Corporate Taxes Paid'].sum()+c.banks.bank_data['Corporate Taxes Paid'].sum()
        c.central_government.central_gov_data['Corporate Taxes']=new_corporate
        c.central_government.central_gov_data['Revenue']+=new_corporate-old_corporate
        np.testing.assert_array_equal(d[['Debt','Deposits','Equity']],financial);np.testing.assert_array_equal(f.capital_inputs_stock,stocks)
        if not np.isfinite(d[['Unit Costs','Profits']].to_numpy()).all():raise ValueError('Nonfinite initial accounts')
        for i,r in d.iterrows():
            j=int(r.Industry);obs=c.industry_data['industry_vectors'].iloc[j]
            gos=r.Production*r.Price-r['Total Wages Paid']-f.used_intermediate_inputs[i].sum()-r['Taxes paid on Production']
            source_row=observed.loc[n+'|'+codes[j]]
            source_gos=(source_row.gross_operating_surplus+source_row.gross_mixed_income)*1e6/4
            rows.append(dict(region=n,firm=i,industry=codes[j],output=r.Production*r.Price,price=r.Price,
                intermediate=f.used_intermediate_inputs[i].sum(),compensation=r['Total Wages Paid'],taxes=r['Taxes paid on Production'],
                old_CFC=old_CFC[i],new_CFC=f.used_capital_inputs[i].sum(),interest=r['Interest paid'],unit_cost=r['Unit Costs'],
                GOS=gos,IO_GOS=source_gos,profit=r.Profits,source_zero_activity=bool(r.Production<=1e-3),
                above_price_positive_IO_GOS=bool(r.Production>1e-3 and r['Unit Costs']>r.Price+1e-8 and source_gos>=0),
                margin_gap_pp=100*(gos-source_gos)/(r.Production*r.Price) if r.Production>1e-3 else 0.))
    frame=pd.DataFrame(rows);frame.to_csv(OUT/'cfc_cost_bridge.csv',index=False)
    pd.DataFrame(allocation).to_csv(OUT/'cfc_allocation.csv',index=False)
    pd.DataFrame(boundaries,columns=['region','source','quarterly_CFC','reason']).to_csv(OUT/'cfc_boundaries.csv',index=False)
    data.save(TARGET);assert sha(SOURCE)==before
    meta=dict(source=str(SOURCE),source_sha256=before,new_pickle=str(TARGET),new_pickle_sha256=sha(TARGET),
        table='36-10-0096-01',reference='2022 current prices, Total non-residential, Geometric depreciation',
        provenance=json.loads((RAW/'36100096_2022_provenance.json').read_text()),
        allocation='Published provincial industry observations; nearest NAICS aggregates split by fixed accepted initial output. Missing provincial detail uses national observation x regional output share. Every vector and fallback retained. CFC-only build: combined IO/tax experiment failed GDP initialisation and is not promoted.',
        capital_scope='Firm capital stocks in the accepted build are non-residential. Residential CFC from 36-10-0099 is a separate scope check, not charged to firms that do not own household dwellings. No housing-producer block or fictitious capital added.',
        max_margin_gap_pp=float(frame.margin_gap_pp.abs().max()),above_price_exceptions=int(frame.above_price_positive_IO_GOS.sum()),
        CFC_before_annual=float(4*frame.old_CFC.sum()),CFC_after_annual=float(4*frame.new_CFC.sum()),
        gate_operating_margin=bool(frame.margin_gap_pp.abs().max()<=1),gate_unit_cost=bool(not frame.above_price_positive_IO_GOS.any()))
    (OUT/'cfc_build_provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('Built',TARGET.name,'margin gap pp',meta['max_margin_gap_pp'],'above-price exceptions',meta['above_price_exceptions'])


if __name__=='__main__':main()
