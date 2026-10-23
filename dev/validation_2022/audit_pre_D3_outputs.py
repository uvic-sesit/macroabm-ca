"""Read-only consistency checks for completed diagnostic artifacts."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
OUT=HERE/'outputs/pre_D3_checks'
ROOT=HERE.parents[1]


def audit():
    bridge=pd.read_csv(OUT/'income_bridge.csv')
    benchmarks={table:pd.read_csv(HERE/'benchmarks/household_corrections'/filename)
                for table,filename in [('36-10-0112','36100112_2022.csv'),('36-10-0482','36100482_2022.csv')]}
    for row in bridge[bridge.quarter.eq(1)].itertuples():
        b=benchmarks[row.table].groupby('VECTOR').VALUE.mean()
        expression=row.vector.replace(' minus ',' - ').replace(' plus ',' + ')
        tokens=expression.split();value=0.;sign=1
        for token in tokens:
            if token=='+':sign=1
            elif token=='-':sign=-1
            else:value+=sign*b[token]/1000
        assert abs(value-row.benchmark_B_per_year)<1e-6,(row.line,value,row.benchmark_B_per_year)
    manifests=list(OUT.glob('final_*/manifest.json'))
    assert len(manifests)==10,f'Expected ten completed final runs, found {len(manifests)}'
    pickle_path=Path(json.loads(manifests[0].read_text())['pickle'])
    assert hashlib.sha256(pickle_path.read_bytes()).hexdigest()=='3b48c0dba90c2d3c837f92bc0477e4b242ba0afa78275b095e26cc52b4fcb313'
    accounting_failures=[]
    checks=['loan_identity_resid','hh_cash_identity_resid','wage_counterparty_resid',
            'rent_counterparty_resid','house_sales_resid','ub_counterparty_resid',
            'reserves_unexplained','household_distribution_counterparty_resid',
            'imputed_housing_pair_resid','bank_hh_deposit_snapshot_gap',
            'bank_firm_deposit_snapshot_gap','bank_equity_unexplained','goods_market_gap']
    for path in manifests:
        m=json.loads(path.read_text())
        if m['max_accounting_error']>=1e-8:
            accounting_failures.append({'run':path.parent.name,'max_accounting_error':m['max_accounting_error']})
        assert m['pickle_sha256']=='3b48c0dba90c2d3c837f92bc0477e4b242ba0afa78275b095e26cc52b4fcb313'
        for source,digest in m['source_sha256'].items():
            assert hashlib.sha256((ROOT/source).read_bytes()).hexdigest()==digest,source
        loans=pd.read_csv(path.parent/'micro/originations.csv')
        assert np.isfinite(loans.select_dtypes(include='number').to_numpy()).all()
        accounting=pd.read_csv(path.parent/'accounting.csv')
        assert np.isfinite(accounting[checks].to_numpy()).all(),path
        assert (loans.loss>=-1e-6).all()
        assert (loans.loss<=loans.value+1e-4).all()
        outcomes=pd.read_csv(path.parent/'outcomes.csv')
        assert np.isfinite(outcomes.select_dtypes(include='number').to_numpy()).all(),path
        assert loans.loss.sum()<=outcomes.writeoffs.sum()+1
        l=pd.read_csv(path.parent/'L.csv').groupby('quarter').sum(numeric_only=True)
        buyer_sum=l[['HH_L_domestic','firms_L_domestic','government_L_domestic','ROW_L_sales']].sum(axis=1)
        assert np.allclose(l.sales,buyer_sum,rtol=1e-12,atol=.01)
    effects=pd.read_csv(OUT/'L_price_quantity_effects.csv')
    assert np.allclose(effects.delta_sales_B,effects.price_effect_B+effects.quantity_effect_B,atol=1e-8)
    assert np.allclose(effects.delta_sales_B,effects.regional_price_effect_B+effects.regional_quantity_effect_B,atol=1e-8)
    replayed=[]
    for arm in ['iii','iv','d1']:
        path=OUT/f'b1_{arm}_q12_s0'
        if not (path/'manifest.json').exists():continue
        old=pd.read_csv(HERE/f'outputs/household_corrections/{arm}_q12_s0_households_national.csv').set_index('t')
        new=pd.read_csv(path/'outcomes.csv').groupby('quarter').sum(numeric_only=True)
        new.index-=1
        for a,b in [('household_writeoffs','writeoffs'),('bank_loan_losses','bank_losses'),('gdp_output','gdp')]:
            assert np.allclose(old[a],new[b],rtol=0,atol=.01),(arm,a)
        l=pd.read_csv(path/'L.csv').groupby('quarter').sum(numeric_only=True);l.index-=1
        assert np.allclose(old.L_sales,l.sales,rtol=0,atol=.01),arm
        assert np.allclose(old.L_employment,l.employment,rtol=0,atol=.01),arm
        replayed.append(arm)
    result={'completed_final_runs':len(manifests),'benchmark_vector_formulas':'pass',
            'source_and_input_hashes':'pass','new_principal_loss_bounds':'pass',
            'finite_accounting_origination_and_outcome_fields':'pass',
            'L_buyer_reconciliation':'pass','L_price_quantity_identity':'pass',
            'original_12_quarter_replays_within_one_cent':replayed,
            'accounting_failures':accounting_failures}
    xml=OUT/'full_tests.xml'
    if xml.exists():
        doc=ET.parse(xml);failures=[];errors=[]
        for case in doc.findall('.//testcase'):
            for kind,bucket in [('failure',failures),('error',errors)]:
                for element in case.findall(kind):
                    bucket.append({'case':case.attrib,'message':element.attrib.get('message',''),
                                   'known_NaN':'Nan in transactor_total_real_supply' in (element.attrib.get('message','')+(element.text or ''))})
        result['full_suite']={'cases':len(doc.findall('.//testcase')),'failures':failures,'errors':errors,
                              'xml_sha256':hashlib.sha256(xml.read_bytes()).hexdigest(),
                              'log_sha256':hashlib.sha256((OUT/'full_tests.log').read_bytes()).hexdigest()}
    serial=OUT/'sampler_serial.xml'
    if serial.exists():
        doc=ET.parse(serial)
        properties=doc.findall('.//property')
        assert any(p.get('name')=='sampler_n_cores' and p.get('value')=='1' for p in properties)
        failed=doc.findall('.//failure');errors_serial=doc.findall('.//error')
        result['serial_sampler_rerun']={'worker_count':1,'cases':len(doc.findall('.//testcase')),
           'failures':len(failed),'errors':len(errors_serial),
           'known_NaN':all('Nan in transactor_total_real_supply' in (x.get('message','')+(x.text or '')) for x in failed),
           'xml_sha256':hashlib.sha256(serial.read_bytes()).hexdigest()}
    (OUT/'audit.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='full_suite'},indent=2))
    if 'full_suite' in result:
        print('Full-suite failures:',len(failures),'extra failures:',sum(not x['known_NaN'] for x in failures),'errors:',len(errors))


if __name__=='__main__':audit()
