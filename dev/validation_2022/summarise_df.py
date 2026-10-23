"""Aggregate completed serial runs; retain quarterly, seed and bank detail."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE/'outputs/DF'


def main():
    quarterly, summaries, events, industries, lending, banks = [], [], [], [], [], []
    for manifest in sorted(OUT.glob('*/manifest.json')):
        meta = json.loads(manifest.read_text())
        if 'arm' not in meta or meta.get('label') == 'bankcap':
            continue
        p = manifest.parent
        arm, seed, quarters = meta['arm'], meta['seed'], meta['quarters']
        x = pd.read_csv(p/'outcomes.csv')
        if 'household_writeoffs' not in x:
            continue
        sums = ['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses',
                'recapitalisation','gdp','consumption','cash_DI','represented_households',
                'constrained_households','consumption_cut','payment_distress','firm_insolvencies','new_loans',
                'rent_offset','rent_unoffset','senior_shortfall','saving_redirect','income_receipt_error']
        q = x.groupby('quarter')[sums].sum()
        q['cash_saving_rate'] = 1 - q.consumption/q.cash_DI
        q['cash_saving'] = q.cash_DI-q.consumption
        q['constrained_share'] = q.constrained_households/q.represented_households
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
                   Q1_consumption_shortfall=meta['Q1_consumption_shortfall'], household_gate_passed=meta['household_gate_passed'],
                   Q1_rent_offset=q.loc[1,'rent_offset'], Q12_rent_offset=end.rent_offset,
                   **{k:totals[k] for k in ['household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','consumption_cut']},
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
    print(result[['arm','seed','quarters','household_writeoffs','bank_losses','recapitalisation','Q12_GDP','Q12_cash_saving']].to_string(index=False))


if __name__ == '__main__':
    main()
