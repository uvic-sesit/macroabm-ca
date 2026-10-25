"""Freeze verified primary-source credit benchmarks, scope and assumptions."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;OUT=HERE/'benchmarks/QE'

def main():
    output=OUT/'credit_benchmarks.json'
    if output.exists():raise FileExistsError('Frozen benchmark file already exists')
    tu=dict(source='TransUnion Industry Insights Q3 2024',table='Mortgage Loan Summary, printed page 12',vector='not applicable',
        reference='Q3 2024',url='https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q3_24_ciir_report.pdf',
        account_60plus_pct=.25,consumer_60plus_pct=.26,balance_60plus_pct=.23,
        checked_UTC=datetime.now(timezone.utc).isoformat(),
        access='Verified through web PDF reader. Direct download returned HTTP 403; hash below covers this cached factual extract, not the inaccessible PDF bytes.')
    (OUT/'raw/TransUnion_extract.json').write_text(json.dumps(tu,indent=2)+'\n')
    cba=json.loads((OUT/'raw/CBA.json').read_text())
    cba.update(table='Canada monthly table, PDF page 3',vector='not applicable',reference='December 2022',
        mortgage_90plus_pct=.15,mortgages=5106262,arrears_count=7740,
        definition='Three or more months overdue; account count, reporting CBA member banks.')
    rbc=json.loads((HERE/'benchmarks/FE/rbc_credit_quality_2022_2023.json').read_text())
    meta=dict(frozen_UTC=datetime.now(timezone.utc).isoformat(),CBA=cba,TransUnion=tu,RBC=rbc,
        file_hashes={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/'raw/CBA.pdf',OUT/'raw/TransUnion_extract.json',HERE/'benchmarks/ABCD/rbc_2023.pdf',HERE/'benchmarks/FE/rbc_credit_quality_2022_2023.json']},
        scope_correction='RBC .10% (2022) and .14% (2023) are consolidated ALL-loan net write-off ratios, not household-only ratios. Retain the requested range as an explicitly imperfect order-of-magnitude gate, not a validated household calibration target.',
        parameters=dict(N=dict(value=3,unit='consecutive distressed quarters',source='labelled assumption retained from accepted F; no Canada-wide legal foreclosure time is asserted',uncertainty='roughly 7-9 months from first missed instalment under quarterly buckets; provincial procedures vary'),
            haircut=dict(value=.20,source='labelled stress-sale discount assumption, not a measured transaction-cost rate',uncertainty='10-30% illustrative uncertainty; not fitted'),
            unsecured_recovery=dict(rule='Existing non-pension financial assets are included in servicing resources first; residual formal unsecured principal written off after N quarters',source='model accounting choice; no fitted recovery fraction'),
            no_buyer=dict(rule='Mortgage stays as encumbering bank claim in foreclosure queue, collateral legally retained pending sale; no cash recovery or mortgage write-off before executed sale',source='explicit holding treatment; not bank REO ownership'),
            arrears=dict(rule='Interest first then principal, pro rata by lender/type. Non-accrual unpaid-interest memo; principal arrears remain in loan book. Monthly buckets inferred from equal monthly due dates and cash available first.',source='quarterly timing assumption, not observed monthly income or loan-level data')))
    output.write_text(json.dumps(meta,indent=2)+'\n')

if __name__=='__main__':main()
