"""Read-only cost/price decomposition: no extra RNG draws or market calls."""
import numpy as np
import pandas as pd
from closure_diagnostics import cur


def price_components(previous, actual, expected_factor, demand_factor, cost_factor):
    deterministic = previous * expected_factor * demand_factor * cost_factor
    noise = np.divide(actual, deterministic, out=np.ones_like(actual), where=deterministic != 0) - 1
    # At the price floor the residual is censored, not an identified noise draw.
    return deterministic, noise, actual <= .010000000001


class FirmCostDiagnosis:
    def __init__(self, sim, diag, data):
        self.rows = []; self.prices = {}; self.io = {}; self.parameters = [];self.payouts=[]
        for name, c in sim.countries.items():
            n = str(name); f = c.firms; setter = f.functions['prices']
            v = data.synthetic_countries[name].industry_data['industry_vectors']
            self.io[n] = (v['Value Added in LCU']-v['Labour Compensation in LCU']-v['Taxes Less Subsidies in LCU']).to_numpy()
            self.parameters.append(dict(region=n, setter=type(setter).__name__,
                gf=setter.price_setting_speed_gf, dp=setter.price_setting_speed_dp,
                cp=setter.price_setting_speed_cp, sigma=setter.price_setting_noise_std))
            def before(*args,c=c,f=f,n=n,setter=setter,**kwargs):
                if setter.price_setting_speed_dp != 0 or setter.price_setting_speed_cp != 0:
                    raise AssertionError('Diagnostic requires explicit decomposition for nonzero dp/cp')
                return cur(f,'price').copy()
            def after(previous,result,*args,c=c,f=f,n=n,setter=setter,**kwargs):
                # compute_price returns the new prices; its caller appends them afterwards.
                estimated = args[0] if args else kwargs['current_estimated_ppi_inflation']
                expected = 1+setter.price_setting_speed_gf*estimated
                deterministic,noise,floor=price_components(previous,np.asarray(result),expected,1.,1.)
                self.prices[n]=(previous,deterministic,noise,floor,np.full(len(previous),expected))
            diag.wrap(f,'compute_price',before=before,after=after)
            self.capture(c,0)
        def post(sim,t,year,month):
            for c in sim.countries.values(): self.capture(c,t+1)
        sim.posthooks.append(post)

    def capture(self,c,t):
        f=c.firms; n=str(c.country_name); output=cur(f,'production'); price=cur(f,'price'); count=len(output)
        capacity=f.functions['production'].compute_limiting_capital_inputs_stock(
            capital_inputs_productivity_matrix=f.get_effective_capital_coefficients(),
            capital_inputs_stock=cur(f,'capital_inputs_stock'),
            capital_inputs_utilisation_rate=f.capital_inputs_utilisation_rate,
            goods_criticality_matrix=f.goods_criticality_matrix,substitution_bundle_matrix=f.substitution_bundles)
        previous,deterministic,noise,floor,expected=self.prices.get(n,(price,price,np.zeros(count),np.zeros(count,dtype=bool),np.ones(count)))
        industries=f.states['Industry']; code=list(c.industries) if hasattr(c,'industries') else None
        # IO residuals are regional industry totals, split by initial output across firms.
        if t==0:
            totals=np.bincount(industries,weights=output,minlength=len(self.io[n]))
            self.io[n]=self.io[n][industries]*np.divide(output,totals[industries],out=np.zeros(count),where=totals[industries]!=0)
        costnames=dict(intermediates='used_intermediate_inputs_costs',wages='total_wage',taxes='taxes_paid_on_production',depreciation='used_capital_inputs_costs')
        costs={k:cur(f,v) for k,v in costnames.items()}
        for i in range(count):
            row=dict(region=n,quarter=t,firm=i,industry=int(industries[i]),output=output[i],price=price[i],
                unit_cost_stored=cur(f,'unit_costs')[i],GOS=cur(f,'gross_operating_surplus_mixed_income')[i],
                IO_GOS=self.io[n][i],profit=cur(f,'profits')[i],deposits=cur(f,'deposits')[i],
                inventory=cur(f,'inventory')[i],demand=cur(f,'demand')[i],capacity=capacity[i],
                price_previous=previous[i],price_without_noise=deterministic[i],noise=noise[i],price_floor=bool(floor[i]),expected_factor=expected[i])
            for k,v in costs.items(): row[k]=v[i]
            row['unit_cost_reconstructed']=sum(v[i] for v in costs.values())/output[i] if output[i] else np.nan
            self.rows.append(row)
            if t and c.configuration.household_closure.prudent_firm_payout_enabled:
                closure=c.household_closure
                self.payouts.append(dict(region=n,quarter=t,firm=i,industry=int(industries[i]),
                    retained_before=f.states['payout_retained_before'][i],retained_after=f.states['payout_retained_profit'][i],
                    cash_at_declaration=f.states['payout_cash_at_declaration'][i],reserve=f.states['payout_reserve'][i],
                    cash_before_settlement=f.states['payout_cash_before_settlement'][i],cash_after_settlement=f.states['payout_cash_after_settlement'][i],
                    dividend_requested=closure.requested_firm_payments[2,i],dividend_paid=closure.actual_firm_payments[2,i],
                    mixed_paid=closure.actual_firm_payments[0,i],transfers_paid=closure.actual_firm_payments[1,i],
                    current_profit=cur(f,'profits')[i]))

    def save(self,out):
        pd.DataFrame(self.rows).to_csv(out/'firm_costs.csv',index=False)
        pd.DataFrame(self.parameters).to_csv(out/'price_parameters.csv',index=False)
        if self.payouts:pd.DataFrame(self.payouts).to_csv(out/'payout_log.csv',index=False)
