"""Read-only F industry leverage and household constraint counterfactuals."""
import numpy as np
import pandas as pd
from closure_diagnostics import cur


def constraint_classes(constrained, planned, resources, income, reference_income, assets, reference_assets):
    """Restore Q1 receipts holding today's plan/assets/senior payments fixed.

    This is an accounting counterfactual, not a causal estimate of employment
    feedback. Other income-loss and spending-gap indicators are also saved.
    """
    loss=np.maximum(0.,reference_income-income)
    restored=resources+loss
    income_sufficient=constrained & (loss>1e-5) & (restored>=planned-1e-5)
    persistent=constrained & ~income_sufficient & (planned>income+1e-5) & (assets<reference_assets-1e-5)
    return np.select([~constrained,income_sufficient,persistent],
        ['unconstrained','income_restoration_sufficient','persistent_spending_gap_assets_down'],default='other_or_combined')


def household_workers(household_ids, firm_ids, size):
    return np.bincount(np.asarray(household_ids,dtype=int),
        weights=(np.asarray(firm_ids)>=0).astype(float),minlength=size)


class FirmHouseholdDiagnosis:
    def __init__(self,sim,diag):
        self.rows=[];self.budgets={};self.leverage=[];self.initial=[];self.reference={}
        import macromodel.country.household_closure as closure
        original=closure.cap_household_goods_budget
        def budget(c,net_receipts=None):
            h=c.households;g=c.central_government.states
            C=(1+g['Value-added Tax'])*cur(h,'target_consumption').sum(axis=1)
            I=(1+g['Capital Formation Tax'])*cur(h,'target_investment').sum(axis=1)
            cash=cur(h,'wealth_deposits')+cur(h,'received_consumption_loans')+cur(h,'received_mortgages')+cur(h,'property_sale_proceeds')
            senior=cur(h,'debt_installments')+cur(h,'rent')+cur(h,'interest_paid')+cur(h,'price_paid_for_property')
            result=original(c,net_receipts)
            income=h.states['budget_net_receipts'].copy()
            assets=h.states['budget_available_nonpension_assets'].copy()
            self.budgets[str(c.country_name)]=dict(planned_consumption=C,planned_investment=I,
                planned=C+I,resources=cash+income-senior+assets,income=income,assets=assets,
                senior=senior,opening_deposits=cur(h,'wealth_deposits').copy())
            return result
        closure.cap_household_goods_budget=budget
        for name,c in sim.countries.items():
            n=str(name);h=c.households;f=c.firms;z=diag.initial[n]
            assets=np.maximum(0.,z['wealth_other_financial_assets']-h.states['protected_pension_assets'])/c.scale
            bands=np.select([assets<=1e-8,assets<=10000,assets<=100000],['zero','0-10k','10-100k'],default='100k+')
            for i in range(len(cur(f,'debt'))):
                self.initial.append(dict(region=n,firm=i,industry=int(f.states['Industry'][i]),
                    debt=cur(f,'debt')[i],capital=cur(f,'capital_inputs_stock')[i]@cur(c.economy,'good_prices'),
                    GOS=cur(f,'gross_operating_surplus_mixed_income',np.zeros(len(cur(f,'debt'))))[i]))
            def capture(*args,c=c,h=h,n=n,z=z,bands=bands,**kwargs):
                b=self.budgets[n]
                wages=cur(h,'income_employee').copy()
                d2=cur(h,'income_mixed')+cur(h,'income_dividends')+cur(h,'income_corporate_transfers')
                workers=household_workers(c.individuals.states['Corresponding Household ID'],
                    c.individuals.states['Corresponding Firm ID'],len(wages))
                if diag.t==1:
                    self.reference[n]=dict(income=b['income'].copy(),assets=b['assets'].copy(),wages=wages.copy(),
                        d2=d2.copy(),workers=workers.copy())
                ref=self.reference[n]; constrained=h.states['overdraft_constrained']
                klass=constraint_classes(constrained,b['planned'],b['resources'],b['income'],ref['income'],b['assets'],ref['assets'])
                frame=pd.DataFrame(dict(decile=z['decile'],asset_band=bands,diagnosis=klass,
                    households=np.full(len(klass),c.scale),constrained=constrained*c.scale,
                    income_down=(b['income']<ref['income']-1e-5)*c.scale,
                    wages_down=(wages<ref['wages']-1e-5)*c.scale,
                    firm_receipts_down=(d2<ref['d2']-1e-5)*c.scale,
                    employment_down=(workers<ref['workers'])*c.scale,
                    represented_employment=workers*c.scale,
                    employment_change=(workers-ref['workers'])*c.scale,
                    assets_down=(b['assets']<ref['assets']-1e-5)*c.scale,
                    plan_above_income=(b['planned']>b['income']+1e-5)*c.scale,
                    income=b['income'],reference_income=ref['income'],income_change=b['income']-ref['income'],
                    wage_change=wages-ref['wages'],firm_receipts_change=d2-ref['d2'],
                    other_income_change=b['income']-ref['income']-(wages-ref['wages'])-(d2-ref['d2']),
                    opening_assets=b['assets'],reference_assets=ref['assets'],
                    planned_consumption=b['planned_consumption'],planned_investment=b['planned_investment'],
                    consumption_cut=h.states['overdraft_consumption_cut'],investment_cut=h.states['overdraft_investment_cut']))
                group=frame.groupby(['decile','asset_band','diagnosis']).sum().reset_index()
                group['region']=n;group['quarter']=diag.t
                self.rows.extend(group.to_dict('records'))
            diag.wrap(h,'handle_insolvency',before=capture)
        def post(sim,t,year,month):
            for n,c in sim.countries.items():
                f=c.firms;capital=cur(f,'capital_inputs_stock')@cur(c.economy,'good_prices')
                gos=cur(f,'gross_operating_surplus_mixed_income')
                for i in range(len(cur(f,'debt'))):
                    self.leverage.append(dict(region=str(n),quarter=t+1,firm=i,industry=int(f.states['Industry'][i]),
                        debt=cur(f,'debt')[i],capital=capital[i],GOS=gos[i],deposits=cur(f,'deposits')[i]))
        sim.posthooks.append(post)

    def save(self,out):
        pd.DataFrame(self.rows).to_csv(out/'constraint_diagnosis.csv',index=False)
        pd.DataFrame(self.initial).to_csv(out/'initial_firm_leverage.csv',index=False)
        pd.DataFrame(self.leverage).to_csv(out/'firm_leverage.csv',index=False)
