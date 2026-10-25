"""Protected inputs, final source bookkeeping, failed gates and exact test IDs."""
import json,subprocess,pickle
from pathlib import Path
import numpy as np,pandas as pd
from macro_data import DataWrapper
from prepare_sg import HERE,ROOT,BENCH,OUT,sha
from qe_baseline import PICKLE
from build_sg import target,raw_table,sales

def main():
    old=json.loads((HERE/'outputs/HI/audit.json').read_text());protected={n:sha(ROOT/'dev/pkl_files'/n) for n in old['protected_sha256']};assert protected==old['protected_sha256']
    prov=json.loads((BENCH/'source_provenance.json').read_text())
    for p in prov['files']:assert sha(BENCH/p['file'])==p['sha256']
    tests=json.loads((OUT/'verification/full_test_execution.json').read_text());previous=json.loads((HERE/'outputs/HI/verification/full_test_execution.json').read_text());ids=lambda t:{(x['test']['classname'],x['test']['name']) for x in t['failures']}
    assert ids(tests)==ids(previous) and len(tests['failures'])==30 and all(x['known_nan'] for x in tests['failures']);assert tests['tests']==524 and tests['passed']==494
    assert any(p['name']=='sampler_n_cores' and p['value']=='1' for p in tests['sampler_properties'])
    a=DataWrapper.init_from_pickle(PICKLE);rawold=raw_table('before/');rawnew=raw_table();codes=list(a.industries);gates=json.loads((OUT/'step1_gates.json').read_text());records=[]
    for arm in ['FS','FS_T']:
        meta=json.loads((OUT/f'{arm}_build_provenance.json').read_text());assert sha(target(arm))==meta['new_pickle_sha256']==gates[arm]['pickle_sha256'];b=DataWrapper.init_from_pickle(target(arm))
        assert gates[arm]['regional_initialization'] and gates[arm]['independent_income'] and not gates[arm]['passed']
        for name,c in b.synthetic_countries.items():
            source=a.synthetic_countries[name];pd.testing.assert_frame_equal(c.population.household_data,source.population.household_data);pd.testing.assert_frame_equal(c.population.individual_data,source.population.individual_data)
            pd.testing.assert_frame_equal(c.banks.bank_data,source.banks.bank_data)
            assert pickle.dumps(c.credit_market,protocol=5)==pickle.dumps(source.credit_market,protocol=5)
            pd.testing.assert_frame_equal(c.housing_market.housing_market_data,source.housing_market.housing_market_data,check_exact=True)
            assert str(c.housing_market.country_name)==str(source.housing_market.country_name)
            for field in ['Debt','Deposits','Equity','Total Wages Paid','Number of Employees']:
                np.testing.assert_array_equal(c.firms.firm_data[field],source.firms.firm_data[field])
            for attr in ['capital_inputs_stock','intermediate_inputs_stock','used_capital_inputs','used_intermediate_inputs','initial_capital_purchases']:
                np.testing.assert_array_equal(getattr(c.firms,attr),getattr(source.firms,attr))
            np.testing.assert_array_equal(c.industry_data['industry_vectors']['Value Added in LCU'],source.industry_data['industry_vectors']['Value Added in LCU'])
        delta=(rawnew.loc[rawnew.index.get_level_values(0)!='ROW','ROW'].sum(axis=1)-rawold.loc[rawold.index.get_level_values(0)!='ROW','ROW'].sum(axis=1));delta=delta.groupby(level=1).sum().reindex(codes).to_numpy()/4
        np.testing.assert_allclose(b.synthetic_rest_of_the_world.row_data['Imports in USD'].to_numpy()-a.synthetic_rest_of_the_world.row_data['Imports in USD'].to_numpy(),delta,atol=.001,rtol=1e-12)
        records.append(dict(arm=arm,pickle_sha256=sha(target(arm)),non_IO_stocks_members_jobs_wages_and_CFC_exact=True,explicit_VA6_exact=True,ROW_counterpart_exact=True))
    short=json.loads((OUT/'short_accounting_execution.json').read_text());assert len(short)==2 and all(not r['passed'] and r['max_accounting_error'] is None and r['exit_code']==1 for r in short)
    for arm in ['FS','FS_T']:assert 'Household cash budget requires finite settled cash and senior payments' in (OUT/f'{arm}_accounting.log').read_text()
    concept=pd.read_csv(OUT/'CIS_concepts.csv');assert np.allclose(concept.groupby(['arm','concept']).model_share.sum(),1.) and np.allclose(concept.groupby(['arm','concept']).CIS_share.sum(),1.)
    house=pd.read_csv(OUT/'housing_national.csv');assert np.isfinite(house.select_dtypes('number')).all().all();assert np.allclose(house.imputed_memo,235938e6);assert (house.C_memo_proxy_dissaver_share<house.C_dissaver_share).all()
    rent=json.loads((BENCH/'rent_vector_provenance.json').read_text());assert sha(ROOT/rent['source'])==rent['source_sha256'];assert sha(BENCH/'imputed_rent_accepted_2022.csv')==rent['extract_sha256']
    probe=json.loads((OUT/'first_nonfinite_budget_probe_complete.json').read_text());assert any(r['group']=='settled_receipt' and r['field']=='wages' and r['nonfinite']==1 for r in probe)
    assert any(r['field']=='labour_productivity_factor' and r['nonfinite_industries']==[14] for r in probe)
    deps=json.loads((OUT/'step_dependencies.json').read_text());assert not deps['step2']['started'] and not deps['twelve_quarter_runs_started']
    excluded=[]
    for version in ['', '_v2']:
        for arm in ['fs','fs_t']:
            p=ROOT/f'dev/pkl_files/io2022_{arm}_sg{version}_2026_10_25.pkl';assert p.exists();excluded.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p),reason='Excluded initial source-bookkeeping build: explicit VA6 incorrectly followed residual VA; v1 also lacked the ROW import counterpart. No iterations.'))
    audit=dict(passed=True,git_HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),protected_sha256=protected,source_git_blob_hashes_verified=True,final_candidates=records,excluded_builds=excluded,tests=dict(total=524,passed=494,failures=30,beyond_known=0,sampler_workers=1),short_accounting_passed=False,failed_run_reason='Both arms abort before Q1 completes, nonfinite household settled cash/senior guard; no battery pass or12Q claim.',dependent_steps_skipped=True,benchmarks=dict(CIS_PUMF=json.loads((OUT/'household_provenance.json').read_text()),housing_constants_source=dict(path='macro_data/configuration/can_2022_constants.py',sha256=sha(ROOT/'macro_data/configuration/can_2022_constants.py')),CIS_HI_aftertax_benchmark_sha256=sha(HERE/'benchmarks/HI/cis_household_deciles_2022.csv'),inherited_HI_provenance=sha(HERE/'outputs/HI/benchmark_index.json')))
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');print('SG audit passed',audit['tests'])
    index=dict(date_utc='2026-10-25',IO=dict(table='2022 provincial detailed SUT underlying36-10-0478; canonical OECD50 source transformation',vectors='PRM100000/200000 net product taxes/subsidies; PRM300000/400000 other production taxes/subsidies; PRM500000/600000 wages/employer contributions; PRM700000 mixed income; PRM800000 GOS. Mapped aggregates have no single native v-number.',git_sources=prov),CIS=json.loads((OUT/'household_provenance.json').read_text()),rent=rent,inherited_HI_index_path='dev/validation_2022/outputs/HI/benchmark_index.json',inherited_HI_index_sha256=sha(HERE/'outputs/HI/benchmark_index.json'),definitions_sources=[dict(url='https://www150.statcan.gc.ca/n1/pub/13-606-g/2016001/article/14620-eng.htm',checked_utc='2026-10-25',concept='Canadian rental component of mixed income includes owner imputed services; conceptual source, not an extra numeric target.'),dict(url='https://www150.statcan.gc.ca/n1/daily-quotidien/240426/dq240426a-eng.htm',checked_utc='2026-10-25',concept='2022 CIS cash income/after-tax definitions; numeric custom targets come from the hashed PUMF, not this release.')])
    (OUT/'benchmark_index.json').write_text(json.dumps(index,indent=2)+'\n')
if __name__=='__main__':main()
