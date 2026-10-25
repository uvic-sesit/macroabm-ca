"""Replace IO sales/output without resampling people or changing financial stocks."""
import numpy as np


def rescale_output_units(country, new_output):
    f=country.firms;d=f.firm_data;v=country.industry_data['industry_vectors']
    old=v['Output in LCU'].to_numpy().copy();new=np.asarray(new_output,float)
    new=np.where(np.abs(new)<1e-3,0.,new)
    if np.any(new<0) or np.any((old<=0)&(new>1e-3)):
        raise ValueError('IO output requires a producer with initialized support')
    ratio=np.divide(new,old,out=np.ones_like(new),where=old>0)
    technology_ratio=np.where(ratio>0,ratio,1.)
    ids=d.Industry.to_numpy(int)
    for k in ['intermediate_inputs_productivity_matrix','capital_inputs_productivity_matrix']:
        country.industry_data[k]=country.industry_data[k]*technology_ratio[None,:]
        setattr(f,k,country.industry_data[k].to_numpy().copy())
    k='capital_inputs_depreciation_matrix';country.industry_data[k]=country.industry_data[k]/technology_ratio[None,:]
    setattr(f,k,country.industry_data[k].to_numpy().copy())
    f.labour_productivity_by_industry=f.labour_productivity_by_industry*ratio
    d['Production']=d.Production.to_numpy()*ratio[ids];d['Demand']=d.Demand.to_numpy()*ratio[ids]
    if 'Labour Productivity' in d:d['Labour Productivity']=d['Labour Productivity'].to_numpy()*ratio[ids]
    for field in ['Output in LCU','Output in USD']:v[field]=new
    return old,ratio


def net_surplus_gate(output,price,unit_cost,cfc,observed_gos):
    output=np.asarray(output,float);active=output>1e-3
    expected=np.divide(np.asarray(observed_gos)-cfc,output,out=np.zeros_like(output),where=active)
    actual=(price-unit_cost)/price
    gap=np.where(active,100*(actual-expected),0.)
    above=active&(unit_cost>price+1e-8)&((np.asarray(observed_gos)-cfc)>=0)
    return gap,above
