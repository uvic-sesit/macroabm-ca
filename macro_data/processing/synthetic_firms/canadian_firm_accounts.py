"""Data-only reconciliation of producer output and signed production taxes.

Use the provincial supply-use column identity (basic intermediate use plus
input-product valuation plus observed VA), not the unbalanced sales-row total.
No intermediate flow, employee, capital stock, loan or deposit is invented.
The remaining ex-ante sales-row statistical discrepancy is reported separately.
"""
import numpy as np


def column_output(observed):
    return (observed['output_basic'].to_numpy()+observed['net_product_tax_intermediate'].to_numpy())*1e6/4


def reconcile_country(country,observed):
    c=country;f=c.firms;v=c.industry_data['industry_vectors'];d=f.firm_data
    old=v['Output in LCU'].to_numpy().copy();new=column_output(observed)
    new=np.where(np.abs(new)<1e-3,0.,new)
    if np.any((old<=0)&(np.abs(new)>1e-3)):raise ValueError('Observed positive output lacks initialized producer')
    ratio=np.divide(new,old,out=np.ones_like(new),where=old>0)
    if np.any(ratio<0):raise ValueError('Negative observed producer output')
    # A source-zero cell remains an inactive balance-sheet holder, not an
    # exited agent. Keep stocks/contracts and unused technology coefficients;
    # zero observed output/labour productivity cannot create fictitious goods.
    technology_ratio=np.where(ratio>0,ratio,1.)
    industries=d.Industry.to_numpy(int)
    # Preserve physical input/capital stocks and initial use. Productivity is
    # re-expressed per observed unit of output, not behaviourally recalibrated.
    for key,attribute in [('intermediate_inputs_productivity_matrix','intermediate_inputs_productivity_matrix'),
                          ('capital_inputs_productivity_matrix','capital_inputs_productivity_matrix')]:
        matrix=c.industry_data[key].copy()*technology_ratio[None,:]
        c.industry_data[key]=matrix;setattr(f,attribute,matrix.to_numpy().copy())
    key='capital_inputs_depreciation_matrix'
    matrix=c.industry_data[key].copy()/technology_ratio[None,:]
    c.industry_data[key]=matrix;f.capital_inputs_depreciation_matrix=matrix.to_numpy().copy()
    f.labour_productivity_by_industry=f.labour_productivity_by_industry*ratio
    d['Production']=d.Production.to_numpy()*ratio[industries]
    d['Demand']=d.Demand.to_numpy()*ratio[industries]
    for k in ('Output in LCU','Output in USD'):v[k]=new
    product=observed['net_product_tax_intermediate'].to_numpy()*1e6/4
    other=(observed['tax_production'].to_numpy()+observed['subsidy_production'].to_numpy())*1e6/4
    combined=product+other
    v['Other Production Taxes Net of Subsidies in LCU']=other
    v['Product Taxes on Intermediate Inputs in LCU']=product
    # Correct the VA residual's production-tax concept; retain the product
    # valuation separately. Firm settlement still pays both signed components.
    v['Taxes Less Subsidies in LCU']=other
    v['Taxes Less Subsidies in USD']=other
    value_added=(observed['wages_salaries'].to_numpy()+observed['employers_social_contributions'].to_numpy()+
        observed['gross_operating_surplus'].to_numpy()+observed['gross_mixed_income'].to_numpy()+
        observed['tax_production'].to_numpy()+observed['subsidy_production'].to_numpy())*1e6/4
    v['Value Added in LCU']=value_added;v['Value Added in USD']=value_added
    v['Taxes Less Subsidies Rates']=np.divide(combined,new,out=np.zeros_like(new),where=new!=0)
    return dict(old_output=old,new_output=new,product_tax=product,other_tax=other,
                sales_row_statistical_discrepancy=old-new)


def cfc_coefficients(previous,quarterly_CFC,quarterly_output):
    """Observed CFC level; keep the existing nonnegative capital-good mix."""
    previous=np.asarray(previous,float);target=np.asarray(quarterly_CFC,float);output=np.asarray(quarterly_output,float)
    if not np.isfinite(target).all() or np.any(target<0):raise ValueError('CFC targets must be nonnegative finite observations')
    if np.any((output<=0)&(target>1e-3)):raise ValueError('Positive CFC for zero-output industry needs an explicit holding treatment')
    weights=np.maximum(0.,previous);totals=weights.sum(axis=0)
    if np.any((totals==0)&(target>1e-3)):raise ValueError('Missing capital composition for observed CFC')
    weights=np.divide(weights,totals[None,:],out=np.zeros_like(weights),where=totals[None,:]!=0)
    rate=np.divide(target,output,out=np.zeros_like(target),where=output>0)
    return weights*rate[None,:]


def finite_initial_unit_costs(output,total_cost):
    """Match the runtime zero-output convention; a unit margin is undefined there."""
    return np.divide(total_cost,output,out=np.zeros_like(np.asarray(output,float)),where=np.asarray(output)!=0)
