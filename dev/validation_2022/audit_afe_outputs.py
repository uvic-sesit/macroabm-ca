"""Read-only gate, funding, source and regression evidence for steps 1–3."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
from macro_data import DataWrapper

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE/'outputs/AFE'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def failed(xml):
    return {(c.get('classname'),c.get('name')) for c in ET.parse(xml).iter('testcase')
            if c.find('failure') is not None or c.find('error') is not None}


def main(measurements_only=False):
    data = DataWrapper.init_from_pickle(ROOT/'dev/pkl_files/io2022_household_agreed_bankcap.pkl')
    opening = {(str(n),int(i)):float(row.Deposits) for n,c in data.synthetic_countries.items()
               for i,row in c.firms.firm_data.iterrows()}
    component_audit=[]
    for name,c in data.synthetic_countries.items():
        hd=c.population.household_data
        components=['Mutual Funds','Bonds','Value of Private Businesses','Shares','Managed Accounts',
                    'Money owed to Households','Other Assets','Voluntary Pension']
        expected=hd[components].sum(axis=1).to_numpy()*c.scale
        ofa=hd['Wealth in Other Financial Assets'].to_numpy()
        assert np.allclose(ofa,expected,rtol=1e-12,atol=1e-3)
        pensions=hd['Voluntary Pension'].to_numpy()*c.scale
        assert (pensions <= ofa+1e-3).all()
        component_audit.append(dict(region=str(name),OFA=float(ofa.sum()),protected_pension=float(pensions.sum()),
                                    available_nonpension=float(np.maximum(0.,ofa-pensions).sum()),scale=c.scale))
    pd.DataFrame(component_audit).to_csv(OUT/'initial_financial_assets.csv',index=False)
    rows, funding = [], []
    for path in sorted(OUT.glob('*/manifest.json')):
        m = json.loads(path.read_text())
        assert m['max_accounting_error'] < 1e-8
        assert sha(Path(m['pickle'])) == m['pickle_sha256']
        for source, checksum in m['source_sha256'].items():
            assert sha(ROOT/source) == checksum, (path,source)
        b = pd.read_csv(path.parent/'banks.csv')
        assert (b[b.stage=='end'].equity >= 0).all()
        outcomes = pd.read_csv(path.parent/'outcomes.csv')
        groups = pd.read_csv(path.parent/'household_groups.csv').groupby(['region','quarter']).sum(numeric_only=True)
        for r in outcomes.itertuples(index=False):
            z = groups.loc[(r.region,r.quarter)]
            assert np.isclose(z.cash_DI,r.cash_DI,rtol=1e-12,atol=1e-3)
            assert np.isclose(z.consumption,r.consumption,rtol=1e-12,atol=1e-3)
            assert np.isclose(z.liquidation,r.asset_liquidation,rtol=1e-12,atol=1e-3)
            assert np.isclose(z.constrained,r.constrained_households)
        accounting = pd.read_csv(path.parent/'accounting.csv')
        for quarter,z in outcomes.groupby('quarter'):
            assert np.isclose(z.asset_liquidation.sum(),accounting[accounting.t==quarter-1].ofa_liquidation_without_issuer.sum(),rtol=1e-12,atol=1e-3)
        assert (outcomes.asset_liquidation >= -1e-6).all()
        assert (outcomes.asset_liquidation <= outcomes.available_nonpension_assets + 1e-3).all()
        assert np.isfinite(outcomes.income_receipt_error).all()
        cash = dict(opening)
        for r in pd.read_csv(path.parent/'firms.csv').itertuples(index=False):
            key = (r.region,int(r.firm))
            paid = r.paid_mixed+r.paid_dividends+r.paid_transfers
            available = max(0.,cash[key])
            assert paid <= available + max(1e-3,available*1e-12), (path,key,r.quarter,paid,available)
            funding.append(dict(arm=m['arm'],seed=m['seed'],quarters=m['quarters'],quarter=r.quarter,
                                region=r.region,firm=r.firm,opening_cash=cash[key],declared_paid=paid))
            cash[key] = 0. if r.failed else r.cash_after_payout
        rows.append(dict(run=path.parent.name,legacy_Q1_consumption_gate=m['household_gate_passed'],
                         Q1_shortfall=m['Q1_consumption_shortfall'],error=m['max_accounting_error']))
    assert len(rows) == 6
    for seed in range(3):
        for arm in ['iv-ACDpA']:
            short = pd.read_csv(OUT/f'{arm}_q2_s{seed}/outcomes.csv')
            long = pd.read_csv(OUT/f'{arm}_q12_s{seed}/outcomes.csv').query('quarter<=2')
            assert np.allclose(short.select_dtypes('number'),long.select_dtypes('number'),rtol=1e-12,atol=1e-3)
    pd.DataFrame(funding).to_csv(OUT/'funding_declarations.csv',index=False)
    if measurements_only:
        print('6 runs: source/input hashes, accounting, funded declarations and 2Q/12Q replay checked')
        return
    tests = json.loads((OUT/'full_test_execution.json').read_text())
    assert len(tests['failures']) == 30 and all(f['known_nan'] for f in tests['failures'])
    assert tests['sampler_properties'] == [{'name':'sampler_n_cores','value':'1'}]
    assert failed(OUT/'full_tests.xml') == failed(HERE/'outputs/DF/full_tests.xml')
    protected = {'io2022_phaseA.pkl':'4bf77da7707cab00d507c4505c16740224863298ba9b858e5aaf6d60a9c2dc4c',
        'io2022_household_agreed.pkl':'3b48c0dba90c2d3c837f92bc0477e4b242ba0afa78275b095e26cc52b4fcb313',
        'io2022_household_agreed_bankcap.pkl':'d7b39868a569ea52d749aced375247ed6824c8ff2c9e9493100a43645b0de228'}
    for name,checksum in protected.items():
        assert sha(ROOT/'dev/pkl_files'/name) == checksum
    (OUT/'audit.json').write_text(json.dumps(dict(runs=rows,step_A_gates=json.loads((OUT/'step_A_gates.json').read_text()),
        declared_payments_funded_from_opening_cash=True,first_two_quarters_match_long_runs=True,
        known_failure_identities_unchanged=True,protected_pickles=protected,tests=tests['tests'],passed=tests['passed'],
        known_failures=30,extra_failures=0,native_head='f140ae2'),indent=2)+'\n')
    files = {str(p.relative_to(ROOT)):sha(p) for p in OUT.rglob('*')
             if p.is_file() and 'micro' not in p.parts and p.name!='artifact_manifest.json'}
    (OUT/'artifact_manifest.json').write_text(json.dumps(files,indent=2)+'\n')
    print('6 runs: input/source/funding/receipt/accounting checks pass; same 30 known failures; protected inputs unchanged')


if __name__ == '__main__':
    import sys
    main(measurements_only='--measurements-only' in sys.argv)
