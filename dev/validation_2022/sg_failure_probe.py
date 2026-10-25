"""Trace the first nonfinite budget input without changing any economic values."""
import sys,json
import numpy as np
import macromodel.country.household_closure as cl
from closure_diagnostics import cur
from prepare_sg import OUT
import sg_diagnostics

def main():
    original=cl.cap_household_goods_budget;rows=[]
    def inspect(c,net_receipts=None):
        try:return original(c,net_receipts)
        except ValueError:
            def capture(group,key,values,industry=None):
                a=np.asarray(values,float);bad=~np.isfinite(a)
                item=dict(region=str(c.country_name),group=group,field=key,size=int(a.size),nonfinite=int(bad.sum()),finite_sum=float(a[np.isfinite(a)].sum()))
                if industry is not None and a.ndim==1:item['nonfinite_industries']=np.asarray(industry)[bad].astype(int).tolist()
                rows.append(item)
            capture('budget','net_receipts',net_receipts if net_receipts is not None else cl.known_household_receipts(c))
            for key,value in c.households.states.get('budget_receipt_components',{}).items():capture('settled_receipt',key,value)
            capture('individual','employee_income',cur(c.individuals,'employee_income'),c.individuals.states['Corresponding Firm ID'])
            for key in ['income_employee','income_unemployment_benefits','income_social_transfers','income_rental','income_financial_assets','wealth_deposits','received_consumption_loans','received_mortgages','property_sale_proceeds','debt_installments','rent','interest_paid','price_paid_for_property']:
                if key in c.households.ts.dicts:capture('household',key,cur(c.households,key))
            for key in ['price','unit_costs','production','target_production','expected_profits','profits','total_wage','deposits','target_labour_inputs','labour_inputs','labour_productivity','labour_productivity_factor']:
                if key in c.firms.ts.dicts:capture('firm',key,cur(c.firms,key),c.firms.states['Industry'])
            for key in ['planned_mixed','planned_dividends','planned_transfers','actual_firm_payments','firm_requests']:
                if hasattr(c.household_closure,key):capture('D2',key,getattr(c.household_closure,key))
            capture('economy','good_prices',cur(c.economy,'good_prices'))
            (OUT/'first_nonfinite_budget_probe_complete.json').write_text(json.dumps(rows,indent=2)+'\n')
            raise
    cl.cap_household_goods_budget=inspect
    sg_diagnostics.main()
if __name__=='__main__':main()
