"""New input only: financial-statement industry weights and NBSA external credit."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from macro_data import DataWrapper
from macro_data.processing.synthetic_credit_market.loan_data import LongtermLoans, ShorttermLoans
from macro_data.processing.synthetic_firms.canadian_external_debt import allocate_external_firm_debt
from macro_data.processing.synthetic_banks.canadian_book_capital import allocate_canadian_book_capital

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'dev/validation_2022'
SOURCE = ROOT/'dev/pkl_files/io2022_household_agreed_bankcap.pkl'
TARGET = ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt.pkl'
OUT = BASE/'outputs/FE'

# Source industries, in their published table order excluding the aggregate.
# Combined NAICS groups are split by model output, then regions by output.
# P/Q's combined private financial-statements row is deliberately excluded:
# no cited private producer share exists in the IO model's P/Q producers.
GROUPS = [[0,1,2], [4,7], [3,5,6], [27,28], [29], [8], [8], [10,11], [12], [13],
          [14], [15], [16], [17,18,19,21,22], [20], [23], [23], [24,25], [9,26],
          [30], [30], [30], [30], [30], [30], [30], [30], [31,32,33,34,35],
          [31,32,33,34,35], [31,32,33,34,35], [37,39], [38], [41], [41], [42],
          [43], [], [36,47], [48]]


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if TARGET.exists(): raise FileExistsError(TARGET)
    OUT.mkdir(parents=True, exist_ok=True)
    before = sha(SOURCE)
    data = DataWrapper.init_from_pickle(SOURCE)
    q = pd.read_csv(BASE/'benchmarks/FE/33100225_2022Q4.csv')
    industries = q.iloc[:,3].drop_duplicates().tolist()[1:]
    assert len(industries) == len(GROUPS)
    # Loan liability weights exclude debt securities and affiliate borrowing.
    # Mortgage liabilities are not separately exposed in this table: the same
    # observed non-mortgage loan distribution proxies both external instruments.
    q = q[q.iloc[:,4] == 'Non-mortgage loans and overdrafts'].set_index(q.columns[3])
    output = np.zeros(50)
    for n,c in data.synthetic_countries.items():
        if str(n).startswith('CAN_'):
            d=c.firms.firm_data
            np.add.at(output,d.Industry.to_numpy(),(d.Production*d.Price).to_numpy())
    weights=np.zeros(50); rows=[]
    for label, model in zip(industries,GROUPS):
        r=q.loc[label]; amount=float(r.VALUE)*1e6
        if not np.isfinite(amount) or amount<0: raise ValueError(f'Unusable observed loan weight: {label}')
        denom=output[model].sum()
        for g in model:
            share=output[g]/denom if denom else 0
            weights[g]+=amount*share
            rows.append(dict(source_industry=label,vector=r.VECTOR,source_value=amount,
                model_industry=g,output_split=share,weight=amount*share))
    pd.DataFrame(rows).to_csv(OUT/'industry_allocation.csv',index=False)
    firms=pd.DataFrame(allocate_external_firm_debt(data.synthetic_countries,weights))
    firms.to_csv(OUT/'initial_firm_debt.csv',index=False)
    # Rebuild loan principal, interest and installments with the source's
    # unchanged 60-quarter effective initial firm maturity.
    for n,c in data.synthetic_countries.items():
        if not str(n).startswith('CAN_'): continue
        cm=c.credit_market
        cm.longterm_loans=LongtermLoans.from_agent_data(c.banks.bank_data,c.firms.firm_data,60)
        cm.shortterm_loans=ShorttermLoans.from_agent_data(c.banks.bank_data,c.firms.firm_data,60)
        c.banks.set_loans_to_firms(c.firms.firm_data.Debt.to_numpy())
        c.firms.set_additional_initial_conditions(c.industry_data,c.banks,cm.longterm_loans,cm.shortterm_loans,c.tax_data)
    banks=pd.DataFrame(allocate_canadian_book_capital(data.synthetic_countries))
    banks.to_csv(OUT/'initial_banks.csv',index=False)
    if (banks.resolution_ratio<=.05).any(): raise RuntimeError('Initial resolution threshold breached; stop')
    data.save(TARGET)
    assert sha(SOURCE)==before
    source_meta=json.loads((BASE/'outputs/ABCD/firm_debt_provenance.json').read_text())
    meta=dict(source_pickle_sha256=before,new_pickle_sha256=sha(TARGET),nbsa=source_meta,
        industry=json.loads((BASE/'benchmarks/FE/industry_provenance.json').read_text()),
        external_credit=1281615e6,intercompany_equity_credit=1164071e6,bonds_outside_bank_book=625741e6,
        unexplained_NBSA_total_loans_residual=2954e6,
        holder_assumption='All external loans bank-held; borrower totals do not identify creditor sectors.',
        industry_proxy='33-10-0225 non-mortgage loans and overdrafts, 2022 Q4; same industry weights for mortgages.',
        industry_crosswalk='Published combined groups split by model output; no capital-share fallback. K/O/P/Q/T excluded.',
        consolidation='Equity credit 1164.071B plus separately reported scope adjustment; total equity rise equals old minus new bank debt.',
        bank_equity='456.221B reallocated by final joint firm and household loans; reserves are balance-sheet plug.')
    (OUT/'build_provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(firms[['debt_before','debt_after','consolidation_equity_credit','scope_equity_adjustment']].sum())
    print('Initial reserves',banks.reserves.sum(),'minimum resolution ratio',banks.resolution_ratio.min())


if __name__=='__main__': main()
