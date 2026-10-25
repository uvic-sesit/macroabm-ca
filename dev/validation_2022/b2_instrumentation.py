"""Read-only B2 initial wealth-gap and realized consumption-distribution audit."""
import numpy as np
import pandas as pd
from closure_diagnostics import cur


def fixed_groups(income,weights,n):
    order=np.argsort(income,kind='stable');r=np.empty(len(income))
    r[order]=np.cumsum(weights[order])/weights.sum()
    return np.clip(np.ceil(n*r),1,n).astype(int)


def income_per_household(income,scale):
    if not np.isfinite(scale) or scale<=0:raise ValueError('Positive household expansion factor required')
    return np.asarray(income,float)/scale


def gross_wages_from_net(net_wages,income_tax,employee_contributions):
    """Invert the model payroll identity, with SSC deducted before PIT."""
    denominator=(1-income_tax)*(1-employee_contributions)
    if not np.isfinite(denominator) or denominator<=0:raise ValueError('Positive payroll net-wage factor required')
    return np.asarray(net_wages,float)/denominator


def weighted_median(values,weights):
    order=np.argsort(values,kind='stable');v=np.asarray(values)[order];w=np.asarray(weights)[order]
    return v[np.searchsorted(np.cumsum(w),w.sum()/2)]


def consumption_units(ages,households,n):
    """StatCan OECD-modified scale; retain actual linked membership, no refit."""
    adults=np.bincount(households,weights=(ages>=14).astype(float),minlength=n)
    children=np.bincount(households,weights=(ages<14).astype(float),minlength=n)
    return np.maximum(1.,1.+.5*np.maximum(0.,adults-1)+.3*children)


class B2HouseholdDiagnosis:
    def __init__(self,sim,data,micro_out=None):
        self.rows=[];self.initial=[];self.units={};self.calibration=[]
        self.micro_out=micro_out;self.micro=[]
        for name,c in sim.countries.items():
            h=c.households;n=len(cur(h,'income'))
            self.units[str(name)]=consumption_units(np.asarray(c.individuals.states['Age'],float),
                np.asarray(c.individuals.states['Corresponding Household ID'],int),n)
            if 'buffer_stock_initial_gap' in h.states:
                f=pd.DataFrame(dict(decile=h.states['buffer_stock_decile'],age_band=h.states['buffer_stock_age_band'],
                    weight=np.full(n,c.scale),gap=h.states['buffer_stock_initial_gap']/c.scale,
                    Yperm=h.states['buffer_stock_initial_permanent_income']/c.scale,
                    L=h.states['buffer_stock_initial_L']/c.scale,
                    kappa_gap=h.states['buffer_stock_initial_wealth_response']/c.scale,
                    c0_initial=h.states['buffer_stock_initial_c0'],c0=h.states['buffer_stock_c0']))
                self.initial.append(f)
        if self.initial:
            f=pd.concat(self.initial,ignore_index=True);rows=[]
            for (d,a),z in f.groupby(['decile','age_band']):
                w=z.weight.to_numpy();rows.append(dict(decile=d,age_band=a,households=w.sum(),
                    mean_gap_CAD=np.average(z.gap,weights=w),median_gap_CAD=weighted_median(z.gap.to_numpy(),w),
                    negative_share=np.average(z.gap<0,weights=w),L=(z.L*z.weight).sum(),
                    permanent_income=(z.Yperm*z.weight).sum(),kappa_gap=(z.kappa_gap*z.weight).sum(),
                    mean_c0_initial=np.average(z.c0_initial,weights=w),mean_c0=np.average(z.c0,weights=w)))
            self.gaps=pd.DataFrame(rows)
        else:self.gaps=pd.DataFrame()
        self.capture_all(sim,0)
        def post(sim,t,year,month):
            self.capture_all(sim,t+1)
        sim.posthooks.append(post)

    def income(self,c,t):
        h=c.households;tax=c.central_government.states['Income Tax'];ee=c.central_government.states['Employee Social Insurance Tax']
        if t==0:
            d2=c.household_closure.planned_mixed+c.household_closure.planned_dividends+c.household_closure.planned_transfers
            income=cur(h,'income')-cur(h,'income_financial_assets')+d2
            loan_interest=sum(c.credit_market.states[k][1].sum(axis=0) for k in ('cons_loans','mort_loans'))
            ids=h.states['Corresponding Bank ID'];deposits=cur(h,'wealth_deposits')
            interest_received=np.maximum(0.,deposits)*cur(c.banks,'interest_rate_on_household_deposits')[ids]
            net_interest=loan_interest+np.maximum(0.,-deposits)*cur(c.banks,'overdraft_rate_on_household_deposits')[ids]-interest_received
        else:
            income=cur(h,'income');d2=cur(h,'income_mixed')+cur(h,'income_dividends')+cur(h,'income_corporate_transfers')
            net_interest=cur(h,'interest_paid');interest_received=np.maximum(0.,-cur(h,'interest_paid_on_deposits'))
        gross=gross_wages_from_net(cur(h,'income_employee'),tax,ee)+cur(h,'income_unemployment_benefits')+cur(h,'income_social_transfers')+(cur(h,'income_rental')+d2)/(1-tax)+interest_received
        return income,income-net_interest,gross

    def capture_all(self,sim,t):
        blocks=[];weights=[];DHEA=[];SHS=[]
        for c in sim.countries.values():
            income,di,gross=self.income(c,t);blocks.append((c,income));weights.append(np.full(len(income),c.scale))
            DHEA.append(income_per_household(di,c.scale)/self.units[str(c.country_name)])
            SHS.append(income_per_household(gross,c.scale))
        w=np.concatenate(weights)
        if self.micro_out is not None:
            C=np.concatenate([cur(c.households,'consumption')*(1+c.central_government.states['Value-added Tax'])+
                cur(c.households,'rent') for c,_ in blocks])
            self.micro.append(np.column_stack([np.full(len(w),t),w,np.concatenate(DHEA),np.concatenate(SHS),C]))
        for scheme,values in [('DHEA_equivalised_DI',DHEA),('SHS_gross_household_income',SHS)]:
            ranks=fixed_groups(np.concatenate(values),w,5);start=0
            for c,income in blocks:
                n=len(income);self.capture(c,t,income,ranks[start:start+n],scheme);start+=n

    def capture(self,c,t,income,quintiles,scheme):
        h=c.households;n=len(cur(h,'income'));vat=c.central_government.states['Value-added Tax']
        C=(1+vat)*cur(h,'consumption');rent=cur(h,'rent')
        if not np.isclose(C.sum(),cur(h,'total_consumption').sum(),rtol=1e-12,atol=1e-3):raise AssertionError('Goods C does not reconcile')
        positive=income>1e-8*c.scale;zero=C<=1e-8*c.scale
        frame=pd.DataFrame(dict(quintile=quintiles,households=np.full(n,c.scale),
            positive_income=positive*c.scale,zero_goods=zero*c.scale,positive_zero_goods=(positive&zero)*c.scale,
            consumption=C+rent,goods_consumption=C,rent=rent,income=income))
        group=frame.groupby('quintile').sum().reset_index();group['quarter']=t;group['region']=str(c.country_name)
        group['scheme']=scheme
        self.rows.extend(group.to_dict('records'))

    def save(self,out):
        pd.DataFrame(self.rows).to_csv(out/'consumption_quintiles.csv',index=False)
        if len(self.gaps):self.gaps.to_csv(out/'initial_wealth_gaps.csv',index=False)
        if self.micro_out is not None:
            self.micro_out.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(self.micro_out/'distribution_ranks.npz',
                columns=np.array(['quarter','households','equivalised_DI_per_HH','gross_income_per_HH','consumption_aggregate']),
                data=np.vstack(self.micro))
