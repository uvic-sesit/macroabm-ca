"""Read-only per-household cash ledger, captured before insolvency bookkeeping."""
import numpy as np
import pandas as pd
from closure_diagnostics import cur


def cash_ledger(h,vat,cf):
    rows=dict(income=cur(h,'income'),consumption_VAT=(1+vat)*cur(h,'consumption'),
        investment_CF=(1+cf)*cur(h,'investment').sum(axis=1),principal=cur(h,'debt_installments'),
        interest=cur(h,'interest_paid'),rent=cur(h,'rent'),
        new_loans=cur(h,'received_consumption_loans')+cur(h,'received_mortgages'),
        asset_liquidation=np.asarray(h.states['ofa_liquidation_without_issuer']),
        deposit_change=cur(h,'wealth_deposits')-np.asarray(h.ts.prev('wealth_deposits')),
        OFA_change=cur(h,'wealth_other_financial_assets')-np.asarray(h.ts.prev('wealth_other_financial_assets')),
        house_purchases=cur(h,'price_paid_for_property'),house_sale_proceeds=cur(h,'property_sale_proceeds'))
    rows['new_OFA_saving']=rows['OFA_change']+rows['asset_liquidation']
    rows['cash_residual']=(rows['deposit_change']-(rows['income']-rows['consumption_VAT']-rows['investment_CF']
        -rows['principal']-rows['interest']-rows['rent']+rows['new_loans']+rows['asset_liquidation']
        -rows['new_OFA_saving']-rows['house_purchases']+rows['house_sale_proceeds']))
    if not np.allclose(rows['cash_residual'],0.,rtol=0.,atol=1e-4):
        raise AssertionError('Individual household cash ledger does not close')
    return pd.DataFrame(rows)


class CashLedger:
    def __init__(self,sim,diag,out):
        self.rows=[];self.out=out
        (out/'micro').mkdir(parents=True,exist_ok=True)
        self.rules=[]
        for name,c in sim.countries.items():
            h=c.households;z=diag.initial[str(name)]
            assets=np.maximum(0.,z['wealth_other_financial_assets']-h.states['protected_pension_assets'])/c.scale
            bands=np.select([assets<=1e-8,assets<=10000,assets<=100000],['zero','0-10k','10-100k'],default='100k+')
            self.rules.append(dict(region=str(name),rate_min=h.states['investment_rate'].min(),
                rate_max=h.states['investment_rate'].max(),initial_income=cur(h,'income').sum(),
                initial_investment=cur(h,'total_investment').sum(),assume_zero_growth=c.assume_zero_growth,
                function=type(h.functions['investment']).__name__,
                depreciation=h.functions['wealth'].other_real_assets_depreciation_rate))
            def capture(*args,c=c,h=h,z=z,bands=bands,**kwargs):
                frame=cash_ledger(h,c.central_government.states['Value-added Tax'],c.central_government.states['Capital Formation Tax'])
                frame['household']=np.arange(len(frame));frame['decile']=z['decile'];frame['asset_band']=bands
                frame['households']=c.scale;frame['quarter']=diag.t;frame['region']=str(c.country_name)
                frame.to_csv(out/'micro'/f'ledger_{c.country_name}_q{diag.t}.csv',index=False)
                frame=frame.drop(columns='household')
                cols=[k for k in frame.select_dtypes('number') if k not in ['quarter','decile']]
                group=frame.groupby(['decile','asset_band'])[cols].sum().reset_index()
                group['quarter']=diag.t;group['region']=str(c.country_name)
                self.rows.extend(group.to_dict('records'))
            diag.wrap(h,'handle_insolvency',before=capture)

    def save(self,out):
        pd.DataFrame(self.rows).to_csv(out/'cash_ledger_groups.csv',index=False)
        pd.DataFrame(self.rules).to_csv(out/'investment_rule.csv',index=False)
