"""Freeze named-commit IO sources and the gate specification before runs."""
import json,subprocess,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];IO=ROOT.parent/'macroabm-io2022';BENCH=HERE/'benchmarks/ZA';OUT=HERE/'outputs/ZA'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    BENCH.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
    git=['git','-c','safe.directory='+IO.as_posix(),'-C',str(IO)];records=[]
    for commit,names in [('d847fb2',['compatibility/compat_icio_2022_can_provinces.csv','canonical/VA_tax_output_basic.csv']),('eb40128',['OOH_SPLIT_2026-10-25.md','canonical/ooh_by_province_basic.csv','canonical/ooh_inputs_by_province_commodity_basic.csv'])]:
        full=subprocess.check_output(git+['rev-parse',commit]).decode().strip()
        for name in names:
            raw=subprocess.check_output(git+['show',commit+':'+name]);path=BENCH/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            records.append(dict(commit=full,file=name,sha256=sha(path),retrieved_utc='2026-10-25'))
    (BENCH/'provenance.json').write_text(json.dumps(dict(sources=records,OOH_table='2022 StatCan provincial detailed SUT, BS5311A0, PEC04200; canonical OECD-L split',OOH_vectors='PRM100000/200000 product taxes/subsidies, PRM300000/400000 production taxes/subsidies, PRM700000 gross mixed income; no native v-number for this mapped custom split',SUT_source='d847fb2; table36-10-0478 detailed underlying provincial workbooks'),indent=2)+'\n')
    for path in [BENCH,OUT]:(path/'.gitattributes').write_text('* -text -whitespace\n')
    spec=OUT/'gate_specification_before_runs.json'
    if not spec.exists():spec.write_text(json.dumps(dict(date_utc='2026-10-25',authorized_by='Round ZA user prompt, declared before v4 rebuild or gate measurements',margin=dict(universe='canonical source output >0, excluding every source-zero floor cell',max_gap_pp=1.,cost_above_price='only where observed NOS <0'),floor=dict(universe='all canonical source-zero cells, including inherited29',floor_CAD_annual=1000000.,max_national_output_share=.0001,finite_state=True,contracts_held=True),old_universal_gate='Report unchanged for transparency; not the new adoption gate.',GDP='all13 regions three approaches with unchanged tolerance',accounting_relative_tolerance=1e-8),indent=2)+'\n')
    print('ZA sources and pre-run gate specification frozen')
if __name__=='__main__':main()
