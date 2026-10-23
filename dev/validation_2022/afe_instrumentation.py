"""Read-only household saving/constraining diagnosis; aggregates only committed."""
import numpy as np
import pandas as pd
from closure_diagnostics import cur


def household_cash_flows(h, vat):
    income=cur(h,'income')-cur(h,'interest_paid')
    consumption=(1+vat)*cur(h,'consumption')+cur(h,'rent')
    expected=float(cur(h,'total_consumption').sum()+cur(h,'rent').sum())
    if not np.isclose(consumption.sum(),expected,rtol=1e-12,atol=1e-3):
        raise AssertionError('Household consumption does not reconcile to regional total')
    return income,consumption


class AssetDiagnosis:
    def __init__(self, sim, diag):
        self.rows=[]
        for name,c in sim.countries.items():
            h=c.households
            initial=diag.initial[str(name)]
            # Fixed t0 bins, per represented household CAD; no benchmark fitting.
            nonpension=np.maximum(0.,initial['wealth_other_financial_assets']-h.states['protected_pension_assets'])/c.scale
            bins=np.select([nonpension<=1e-8,nonpension<=10000,nonpension<=100000],
                           ['zero','0-10k','10-100k'],default='100k+')
            def capture(*args, c=c, h=h, initial=initial, bins=bins, **kwargs):
                income,consumption=household_cash_flows(h,c.central_government.states['Value-added Tax'])
                saving=income-consumption
                frame=pd.DataFrame(dict(decile=initial['decile'],asset_bin=bins,
                    households=np.full(len(income),c.scale), constrained=h.states['overdraft_constrained']*c.scale,
                    cash_DI=income,consumption=consumption,cash_saving=saving,
                    positive_saving=np.maximum(0.,saving),dissaving=-np.minimum(0.,saving),
                    consumption_cut=h.states['overdraft_consumption_cut'],
                    liquidation=h.states['ofa_liquidation_without_issuer'],
                    opening_assets=h.states['budget_available_nonpension_assets'],
                    remaining_assets=np.maximum(0.,cur(h,'wealth_other_financial_assets')-h.states['protected_pension_assets']),
                    deposits=cur(h,'wealth_deposits'),senior_shortfall=h.states['payment_distress_before_goods']))
                group=frame.groupby(['decile','asset_bin']).sum().reset_index()
                group['quarter']=diag.t;group['region']=str(c.country_name)
                self.rows.extend(group.to_dict('records'))
            diag.wrap(h,'handle_insolvency',before=capture)

    def save(self,out):
        pd.DataFrame(self.rows).to_csv(out/'household_groups.csv',index=False)
