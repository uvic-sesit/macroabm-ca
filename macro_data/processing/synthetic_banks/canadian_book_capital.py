"""Canadian 2022 Q4 liability-side book capital, in CAD (not asset F5).

StatCan 36-10-0580, book value: chartered banks v62696428, 405572
million; quasi-banks v62696533, 50649 million. The inherited 2026-10-13
controls snapshot has SHA256
1c4f10ddd68a67e79b0565a63b731bcfaf97ebcbf294701b3c9a63ce20919b9a.
https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610058001
"""
import numpy as np
from macro_data.configuration.countries import Country

CANADIAN_BANK_BOOK_EQUITY_2022 = (405_572 + 50_649) * 1e6


def allocate_canadian_book_capital(countries):
    """Allocate the national book equity by final initial loans, not regional VA.

    Preserve every loan and customer deposit. Recompute the reserve plug and
    initial income/tax/liability fields by the existing synthetic-bank methods.
    Returns one row per bank for the initialization audit.
    """
    selected = [(name, c) for name, c in countries.items()
                if name == Country('CAN') or str(name).startswith('CAN_')]
    total_loans = sum((c.banks.bank_data['Loans to Firms'] +
                       c.banks.bank_data['Loans to Households']).sum()
                      for _, c in selected)
    if not selected or not np.isfinite(total_loans) or total_loans <= 0:
        raise ValueError('Canadian bank-capital allocation requires positive initial loans')
    rows = []
    for name, c in selected:
        b = c.banks
        d = b.bank_data
        loans = d['Loans to Firms'] + d['Loans to Households']
        d['Equity'] = CANADIAN_BANK_BOOK_EQUITY_2022 * loans / total_loans
        d['Deposits'] = d['Deposits from Firms'] + d['Deposits from Households'] + d['Equity'] - loans
        b.set_interest_received_from_deposits(float(d['Interest Rates on Household Deposits'].iloc[0]))
        b.set_profits()
        b.set_corporate_taxes_paid(c.tax_data.profit_tax)
        b.set_liability()
        b.set_market_share()
        for i, r in d.iterrows():
            l = float(loans.loc[i]); e = float(r['Equity']); reserve = float(r['Deposits'])
            rows.append(dict(region=str(name), bank=int(i), loans=l, equity=e, reserves=reserve,
                             loan_share=l / total_loans, equity_to_loans=e / l,
                             resolution_ratio=e / (l + reserve)))
    return rows
