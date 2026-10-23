"""Read-only F proposal: instrument bridge and illustrative industry allocation."""
import hashlib
import json
from pathlib import Path

import pandas as pd
from macro_data import DataWrapper

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'dev/validation_2022/outputs/ABCD'
SOURCE = ROOT.parent/'macroabm-ca/dev/raw_data/can_2022/controls/36100580.csv'


def main():
    panels = []
    for chunk in pd.read_csv(SOURCE, chunksize=100000, low_memory=False):
        subset = chunk[(chunk.REF_DATE == '2022-10') & (chunk.Sectors == 'Non-financial private corporations')]
        panels.append(subset)
    benchmark = pd.concat(panels)
    benchmark.to_csv(OUT/'firm_nbsa_2022Q4.csv', index=False)
    market = benchmark[benchmark.Valuation == 'Market value'].set_index('COORDINATE')
    def instrument(category):
        row = market.loc[f'1.8.1.{category}']
        return float(row.VALUE)*1e6
    total = instrument(67)
    intercompany = instrument(71)
    data = DataWrapper.init_from_pickle(ROOT/'dev/pkl_files/io2022_household_agreed_bankcap.pkl')
    rows = []
    for name, c in data.synthetic_countries.items():
        for i, f in c.firms.firm_data.iterrows():
            rows.append(dict(region=str(name), firm=int(i), industry=int(f['Industry']), debt=float(f['Debt']),
                implied_intercompany=float(f['Debt'])*intercompany/total,
                external_instrument_proxy=float(f['Debt'])*(total-intercompany)/total))
    pd.DataFrame(rows).to_csv(OUT/'initial_firm_debt_by_firm.csv', index=False)
    industry = pd.DataFrame(rows).groupby('industry')[['debt','implied_intercompany','external_instrument_proxy']].sum().reset_index()
    codes = json.loads((ROOT/'dev/validation_2022/outputs/pre_D3_checks/industry_mapping.json').read_text())
    industry.insert(1, 'industry_code', industry.industry.astype(str).map(codes))
    industry.to_csv(OUT/'initial_firm_debt_by_industry.csv', index=False)
    meta = dict(table='36-10-0580', url='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610058001',
        source=str(SOURCE), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        date='inherited 2026-10-13 controls snapshot', reference='2022 Q4',
        instruments={str(k): instrument(k) for k in [60,67,68,69,70,71,72]},
        vectors={str(k): str(market.loc[f'1.8.1.{k}', 'VECTOR']) for k in [60,67,68,69,70,71,72]},
        interpretation='Pro rata intercompany allocation is an illustrative bridge, not observed industry or lender holdings; external loans are not identifiable as bank-only.')
    (OUT/'firm_debt_provenance.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(meta['instruments']))
    print('model total', sum(r['debt'] for r in rows), 'implied intercompany', sum(r['implied_intercompany'] for r in rows))


if __name__ == '__main__':
    main()
