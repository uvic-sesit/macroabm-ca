"""Aggregate completed serial runs; retain quarterly, seed and bank detail."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE/'outputs/FE'
RUNS = OUT/'serial'


def main():
    quarterly, summaries, events, industries, lending, banks = [], [], [], [], [], []
    for manifest in sorted(RUNS.glob('*/manifest.json')):
        meta = json.loads(manifest.read_text())
        if 'arm' not in meta or meta.get('label') == 'bankcap':
            continue
        p = manifest.parent
        arm, seed, quarters = meta['arm'], meta['seed'], meta['quarters']
        x = pd.read_csv(p/'outcomes.csv')
        if 'household_writeoffs' not in x or arm!='iv-ACDpAIF':
            continue
        sums = ['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses',
                'recapitalisation','gdp','consumption','cash_DI','represented_households',
                'constrained_households','consumption_cut','payment_distress','firm_insolvencies','new_loans',
                'rent_offset','rent_unoffset','senior_shortfall','saving_redirect','income_receipt_error',
                'asset_liquidation','available_nonpension_assets','investment','investment_cut','consumption_constrained_households']
        q = x.groupby('quarter')[sums].sum()
        q['cash_saving_rate'] = 1 - q.consumption/q.cash_DI
        q['cash_saving'] = q.cash_DI-q.consumption
        battery = pd.read_csv(p/'accounting.csv').groupby('t').sum(numeric_only=True)
        battery.index = battery.index + 1
        q['ofa_without_issuer'] = battery.ofa_without_issuer
        q['net_OFA_accumulation'] = battery.hh_dOFA
        q['deposit_change'] = battery.hh_dDeposits
        q['principal_repayment'] = battery.hh_principal
        q['house_sales_net'] = battery.house_sales_resid
        q['investment_including_CF_tax_implied'] = (q.cash_saving - battery.hh_dDeposits
            - battery.hh_dOFA - battery.hh_principal + battery.hh_new_loans - battery.house_sales_resid)
        q['constrained_share'] = q.constrained_households/q.represented_households
        q['consumption_constrained_share'] = q.consumption_constrained_households/q.represented_households
        q['min_capital_ratio'] = x.groupby('quarter').min_capital_ratio.min()
        q['min_resolution_ratio'] = x.groupby('quarter').min_resolution_ratio.min()
        b = pd.read_csv(p/'banks.csv')
        q['min_capital_ratio_before_resolution'] = b[b.stage=='before_rescue'].groupby('quarter').capital_ratio.min()
        for frame in [q]:
            frame['arm'], frame['seed'], frame['quarters'] = arm, seed, quarters
        quarterly.append(q.reset_index())
        resolution = pd.read_csv(p/'resolutions.csv')
        resolution['arm'], resolution['seed'], resolution['quarters'] = arm, seed, quarters
        events.append(resolution)
        b['arm'], b['seed'], b['quarters'] = arm, seed, quarters
        banks.append(b)
        orig = pd.read_csv(p/'new_lending.csv')
        orig['arm'], orig['seed'], orig['quarters'] = arm, seed, quarters
        lending.append(orig)
        firm = pd.read_csv(p/'firms.csv')
        fail = firm[firm.failed].groupby(['quarter','industry']).agg(
            failures=('firm','size'), principal=('loan_debt','sum'), overdraft=('overdraft_cancelled','sum')).reset_index()
        fail['arm'], fail['seed'], fail['quarters'] = arm, seed, quarters
        codes = json.loads((HERE/'outputs/pre_D3_checks/industry_mapping.json').read_text())
        fail.insert(2, 'industry_code', fail.industry.astype(str).map(codes))
        industries.append(fail)
        totals = x[sums].sum()
        end = q.loc[quarters]
        calibration = pd.read_csv(p/'saving_calibration.csv')
        initial = pd.read_csv(p/'income_flows.csv').query('quarter==0').set_index('region')
        weights = initial.loc[calibration.region, 'income_booked'].to_numpy()
        old = np.average(calibration.old_propensity, weights=weights)
        new = np.average(calibration.new_propensity, weights=calibration.d2_income) if 'd2_income' in calibration else old
        row = dict(arm=arm, seed=seed, quarters=quarters,
                   Q1_C_target=meta['initial_quarterly_C_target'],
                   Q1_consumption_shortfall=meta['Q1_consumption_shortfall'], legacy_Q1_consumption_gate_passed=meta['household_gate_passed'],
                   Q1_rent_offset=q.loc[1,'rent_offset'], Q12_rent_offset=end.rent_offset,
                   **{k:totals[k] for k in ['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','consumption_cut']},
                   asset_liquidation=totals['asset_liquidation'],
                   Q4_constrained_share=q.loc[4,'constrained_share'] if quarters>=4 else float('nan'),
                   Q12_constrained_share=end.constrained_share,
                   resolution_events=len(resolution), Q12_GDP=end.gdp, Q12_consumption=end.consumption,
                   Q12_cash_saving=end.cash_saving_rate, Q1_consumption=q.loc[1,'consumption'], Q1_cash_DI=q.loc[1,'cash_DI'],
                   Q1_cash_saving=q.loc[1,'cash_saving_rate'], old_propensity=old, new_propensity=new,
                   min_capital_ratio=q.min_capital_ratio.min(), min_capital_before_resolution=q.min_capital_ratio_before_resolution.min(),
                   overdraft_share_new_lending=orig.to_overdrawn.sum()/orig.value.sum(),
                   loss_share_new_principal=orig.loss.sum()/orig.value.sum(), max_accounting_error=meta['max_accounting_error'])
        summaries.append(row)
    for name, frames in [('quarterly',quarterly),('resolution_log',events),('firm_insolvencies_by_industry',industries),
                         ('new_lending_vintages',lending),('banks_by_quarter',banks)]:
        pd.concat(frames, ignore_index=True).to_csv(OUT/f'{name}.csv', index=False)
    result = pd.DataFrame(summaries)
    result.to_csv(OUT/'summary.csv', index=False)
    groups=[]
    for seed in range(3):
        f=pd.read_csv(RUNS/f'iv-ACDpAIF_q12_s{seed}/household_groups.csv')
        f['seed']=seed
        groups.append(f)
    grouped=pd.concat(groups,ignore_index=True)
    values=[c for c in grouped.select_dtypes('number').columns if c not in ['seed','quarter','decile']]
    for keys,name in [(['seed','quarter','decile'],'saving_by_decile'),
                      (['seed','quarter','asset_bin'],'saving_by_assets'),
                      (['seed','quarter','decile','asset_bin'],'saving_by_decile_assets')]:
        g=grouped.groupby(keys)[values].sum()
        g['constrained_share']=g.constrained/g.households
        g['cash_saving_rate']=1-g.consumption/g.cash_DI
        g.to_csv(OUT/f'{name}.csv')
    ledgers=[]
    for path in RUNS.glob('*/cash_ledger_groups.csv'):
        meta=json.loads((path.parent/'manifest.json').read_text())
        f=pd.read_csv(path);f['seed']=meta['seed'];f['arm']=meta['arm'];f['quarters']=meta['quarters']
        ledgers.append(f)
    ledger=pd.concat(ledgers,ignore_index=True)
    values=[c for c in ledger.select_dtypes('number') if c not in ['seed','quarter','quarters','decile']]
    for group,label in [(['arm','seed','quarters','quarter'],'national'),
                        (['arm','seed','quarters','quarter','decile'],'decile'),
                        (['arm','seed','quarters','quarter','asset_band'],'assets'),
                        (['arm','seed','quarters','quarter','decile','asset_band'],'decile_assets')]:
        ledger.groupby(group)[values].sum().to_csv(OUT/f'cash_ledger_{label}.csv')
    print(result[['seed','quarters','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','Q12_GDP','Q12_cash_saving']].to_string(index=False))


if __name__ == '__main__':
    main()
