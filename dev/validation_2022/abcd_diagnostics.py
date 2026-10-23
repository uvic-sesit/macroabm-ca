"""Serial A–D measurement, using the existing read-only diagnostics."""
import argparse
import hashlib
import json
import subprocess
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from closure_diagnostics import ROOT, Diagnostics, AccountingBattery, IDENTITY_COLUMNS, cur
from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration, SimulationConfiguration
from macromodel.simulation import Simulation


def run(args):
    warnings.filterwarnings('ignore')
    data = DataWrapper.init_from_pickle(args.pickle)
    names = [n for n in data.all_country_names if str(n).startswith('CAN_')]
    configs = {n: CountryConfiguration.n_industry_default(n_industries=data.n_industries) for n in names}
    for c in configs.values():
        cfg = c.household_closure
        cfg.credit_enabled = cfg.income_enabled = True
        cfg.recalibrate_saving_with_d2 = args.arm in ['iv-AC', 'iv-ACD', 'v-ACD']
        cfg.overdraft_limit_enabled = args.arm in ['iv-ACD', 'v-ACD']
        cfg.distress_enabled = args.arm == 'v-ACD'
        cfg.rent_offset_enabled = args.arm == 'final_d1'
    sim = Simulation.from_datawrapper(data, SimulationConfiguration(country_configurations=configs,
                                                                   t_max=args.quarters, seed=args.seed))
    out = args.output / f'{args.arm}_q{args.quarters}_s{args.seed}'
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'manifest.json').exists():
        raise FileExistsError('Refusing to overwrite completed measurement')
    diag = Diagnostics(sim, data, out)
    battery = AccountingBattery()
    sim.posthooks.extend([battery, diag.post])
    calibration = [dict(region=str(n), **c.households.states.get('saving_calibration',
        dict(old_propensity=c.households.states['average_saving_rate'],
             new_propensity=c.households.states['average_saving_rate']))) for n, c in sim.countries.items()]
    pd.DataFrame(calibration).to_csv(out / 'saving_calibration.csv', index=False)
    rows, events = [], []
    for t in range(args.quarters):
        diag.t = t + 1
        sim.iterate(t)
        for n, c in sim.countries.items():
            h, b, cm = c.households, c.banks, c.credit_market
            f = [r for r in diag.firm if r['quarter'] == t+1 and r['region'] == str(n) and r['failed']]
            firm_debt = sum(r['loan_debt'] for r in f)
            firm_od = sum(r['overdraft_cancelled'] for r in f)
            losses = np.asarray(b.states.get('loan_losses_current', 0.)).sum()
            hh_loss = cm.states.get('household_writeoffs_current', 0.)
            # Principal cancellation and overdraft losses are distinct bank paths.
            residual = losses - hh_loss - firm_debt - firm_od
            if abs(residual) > max(1., abs(losses)) * 1e-8:
                raise AssertionError(f'Unattributed bank loss {n} Q{t+1}: {residual}')
            count = len(cur(h, 'income'))
            constrained = np.asarray(h.states.get('overdraft_constrained', np.zeros(count)))
            cash_di = cur(h, 'income').sum() - cur(h, 'interest_paid').sum()
            consumption = cur(h, 'total_consumption').sum() + cur(h, 'rent').sum()
            rows.append(dict(region=str(n), quarter=t+1, household_writeoffs=hh_loss,
                firm_loan_losses=firm_debt, overdraft_losses=firm_od, bank_losses=losses,
                recapitalisation=np.asarray(b.states.get('recapitalisation_current', 0.)).sum(),
                min_capital_ratio=np.min(cur(b, 'equity') / cur(b, 'total_outstanding_loans')),
                min_resolution_ratio=np.min(cur(b, 'equity') / (cur(b, 'total_outstanding_loans') + cur(b, 'deposits'))),
                gdp=cur(c.economy, 'gdp_output').sum(), consumption=consumption, cash_DI=cash_di,
                cash_saving_rate=1-consumption/cash_di, represented_households=count*c.scale,
                constrained_households=constrained.sum()*c.scale,
                consumption_cut=np.asarray(h.states.get('overdraft_consumption_cut', 0.)).sum(),
                payment_distress=np.asarray(h.states.get('payment_distress', 0.)).sum(),
                firm_insolvencies=len(f),
                new_loans=cur(h, 'received_consumption_loans').sum()+cur(h, 'received_mortgages').sum()))
            for e in b.states.get('resolution_events', []):
                if e['quarter'] == t+1:
                    events.append(dict(region=str(n), **e))
        print(f'{args.arm} seed{args.seed} Q{t+1}/{args.quarters}', flush=True)
    diag.save()
    frame = battery.frame()
    frame.to_csv(out / 'accounting.csv', index=False)
    pd.DataFrame(rows).to_csv(out / 'outcomes.csv', index=False)
    pd.DataFrame(events, columns=['region', 'bank', 'quarter', 'resolution_count', 'equity_before',
        'losses_absorbed_by_equity', 'uncovered_loss', 'recapitalisation', 'equity_after']).to_csv(out / 'resolutions.csv', index=False)
    checks = IDENTITY_COLUMNS + ['bank_hh_deposit_snapshot_gap', 'bank_firm_deposit_snapshot_gap',
                                'bank_equity_unexplained', 'goods_market_gap']
    if not np.isfinite(frame[checks].to_numpy()).all():
        raise AssertionError('Non-finite accounting identity')
    err = frame[checks].abs().div(frame[['hh_income', 'firm_sales']].abs().max(axis=1).clip(lower=1), axis=0).max().max()
    lending = pd.DataFrame(diag.loans)
    lending['to_overdrawn'] = lending.value * (lending.deposit < 0)
    lending.groupby(['region', 'quarter'])[['value', 'loss', 'to_overdrawn']].sum().to_csv(out/'new_lending.csv')
    sources = list((ROOT/'macromodel').rglob('*.py')) + [Path(__file__), Path(__file__).with_name('closure_diagnostics.py'),
                                                                  Path(__file__).parent/'battery/accounting.py']
    meta = dict(arm=args.arm, seed=args.seed, quarters=args.quarters,
        head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        pickle=str(args.pickle), pickle_sha256=hashlib.sha256(args.pickle.read_bytes()).hexdigest(),
        max_accounting_error=err,
        source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (out/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    print('accounting error', err, flush=True)
    if not np.isfinite(err) or err > 1e-8:
        raise AssertionError('Accounting battery failed')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', required=True, choices=['iv-A','iv-AC','iv-ACD','v-ACD','final_d1'])
    ap.add_argument('--quarters', type=int, default=12)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--pickle', type=Path, default=ROOT/'dev/pkl_files/io2022_household_agreed_bankcap.pkl')
    ap.add_argument('--output', type=Path, default=Path(__file__).parent/'outputs/ABCD')
    run(ap.parse_args())
