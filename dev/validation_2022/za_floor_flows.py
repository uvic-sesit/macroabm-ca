"""Translate the inherited dummy-VA/FCF floor into its existing sector split."""
import numpy as np

def add_floor_final_demand(country,old_table,new_table,industries):
    c=country;name=str(c.country_name);v=c.industry_data['industry_vectors'];f=c.firms
    def column(table,label):
        return table[(name,label)].groupby(level=1).sum().reindex(industries).fillna(0).to_numpy()/4
    old_fold=column(old_table,'Fixed Capital Formation')+column(old_table,'Changes in Inventories')
    extra=column(new_table,'Fixed Capital Formation')-column(old_table,'Fixed Capital Formation')
    # External-table changes affect only exports. Domestic FCF differences here
    # are precisely the new empty-sector floor; inventories are not changed.
    firm=v['Firm Capital Inputs in LCU'].to_numpy();hh=v['Household Capital Inputs in LCU'].to_numpy()
    support=np.flatnonzero(np.abs(old_fold)>1.)
    r=int(support[np.argmax(np.abs(old_fold[support]))]);fractions=np.array([firm[r]/old_fold[r],hh[r]/old_fold[r]])
    assert np.allclose(firm[support],old_fold[support]*fractions[0],rtol=1e-10,atol=.01)
    assert np.allclose(hh[support],old_fold[support]*fractions[1],rtol=1e-10,atol=.01)
    gov_fraction=1-fractions.sum();assert gov_fraction>=0 and np.all(extra>=-.001)
    extra=np.maximum(0,extra);firm_extra=fractions[0]*extra;hh_extra=fractions[1]*extra;gov_extra=gov_fraction*extra
    weights=f.initial_capital_purchases.sum(axis=1);assert weights.sum()>0
    f.initial_capital_purchases=f.initial_capital_purchases+np.outer(weights/weights.sum(),firm_extra)
    for suffix in ['LCU','USD']:
        v['Firm Capital Inputs in '+suffix]+=firm_extra
        v['Household Capital Inputs in '+suffix]+=hh_extra
        v['Government Consumption in '+suffix]+=gov_extra
    v['Household Investment Weights']=v['Household Capital Inputs in LCU']/v['Household Capital Inputs in LCU'].sum()
    v['Government Consumption Weights']=v['Government Consumption in LCU']/v['Government Consumption in LCU'].sum()
    p=c.population;rate=p.household_data['Investment Rate'].to_numpy();income=p.household_data['Income'].to_numpy();cf=c.tax_data.capital_formation_tax
    old_actual=(rate*income).sum()/(1+cf)
    basket=v['Household Capital Inputs in LCU'];target=(old_actual+hh_extra.sum())*basket/basket.sum()
    p.normalise_household_investment(tau_cf=cf,iot_hh_investment=target)
    ge=c.government_entities.gov_entity_data
    for field in ['Consumption in LCU','Consumption in USD']:
        ge[field]*=(ge[field].sum()+gov_extra.sum())/ge[field].sum()
    g=c.central_government.central_gov_data;tax=cf*hh_extra.sum()
    for field in ['Capital Formation Taxes','Taxes on Products','Revenue']:g[field]+=tax
    return dict(region=name,extra_floor_quarterly=float(extra.sum()),firm_fraction=float(fractions[0]),household_fraction=float(fractions[1]),government_fraction=float(gov_fraction),firm_capital_formation=float(firm_extra.sum()),household_capital_formation=float(hh_extra.sum()),government_consumption=float(gov_extra.sum()),household_CF_tax=float(tax),allocation='Same existing provincial FCF sector fractions; existing capital-investor row shares; same household investment normalizer and government budget shares. No new parameter, buyer, household or stock.')
