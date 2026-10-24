"""Identify loss-producing sectors, cash deficits and payouts without causal fitting."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
OUT=HERE/'outputs/FE'


def main():
    quarters=pd.read_csv(OUT/'quarterly.csv').query('quarters==12')
    initial=pd.read_csv(OUT/'initial_industry_bridge.csv')
    codes=json.loads((HERE/'outputs/pre_D3_checks/industry_mapping.json').read_text())
    allrows=[];summaries=[]
    for seed in range(3):
        f=pd.read_csv(OUT/f'serial/iv-ACDpAIF_q12_s{seed}/firms.csv')
        f['loss']=np.where(f.failed,f.loan_debt+f.overdraft_cancelled,0.)
        f['paid']=f.paid_mixed+f.paid_transfers+f.paid_dividends
        expected=quarters[quarters.seed==seed].set_index('quarter')
        actual=f.groupby('quarter').loss.sum()
        assert np.allclose(actual,expected.firm_loan_losses+expected.overdraft_losses,rtol=1e-12,atol=1e-3)
        total=f.loss.sum()
        summaries.append(dict(seed=seed,firm_losses=total,default_events=int(f.failed.sum()),
            losses_while_negative_profit=f.loc[f.profits<0,'loss'].sum(),
            losses_while_positive_equity=f.loc[f.equity>=0,'loss'].sum(),
            payouts=f.paid.sum(),payouts_while_negative_profit=f.loc[f.profits<0,'paid'].sum(),
            payouts_while_end_cash_short=f.loc[f.cash_before_payout<0,'paid'].sum(),
            payout_at_loss_events=f.loc[f.loss>0,'paid'].sum()))
        f['seed']=seed;allrows.append(f)
    f=pd.concat(allrows,ignore_index=True)
    g=f.groupby(['seed','industry']).agg(losses=('loss','sum'),defaults=('failed','sum'),
        overdraft_losses=('overdraft_cancelled','sum'),
        payouts=('paid','sum'))
    # loan_debt is pre-default exposure on non-default rows; sum only losses.
    formal=f[f.failed].groupby(['seed','industry']).loan_debt.sum()
    g['formal_losses']=formal.reindex(g.index,fill_value=0.)
    g=g.reset_index().merge(initial[['industry','debt_after','capital','GOS']],on='industry',validate='many_to_one')
    g['industry_code']=g.industry.astype(str).map(codes)
    g['initial_debt_capital']=g.debt_after/g.capital
    g.to_csv(OUT/'firm_loss_industry_diagnosis.csv',index=False)
    events=f[f.loss>0].copy().sort_values(['seed','loss'],ascending=[True,False])
    events.groupby('seed',sort=False).head(15).to_csv(OUT/'largest_firm_loss_events.csv',index=False)
    pd.DataFrame(summaries).to_csv(OUT/'firm_loss_mechanisms.csv',index=False)
    print(pd.DataFrame(summaries).to_string(index=False))


if __name__=='__main__':main()
