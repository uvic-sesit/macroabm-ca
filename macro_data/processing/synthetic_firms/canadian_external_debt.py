"""Opt-in NFPC external-loan boundary, StatCan 36-10-0580, 2022 Q4.

Borrower instruments do not identify holders: all external loans are treated
as bank-held. Intercompany consolidation and the remaining scope correction
are reported separately; neither is a simulated cash flow.
"""
import numpy as np

EXTERNAL_LOANS = (925_316 + 356_299) * 1e6
INTERCOMPANY = 1_164_071e6
BONDS = 625_741e6
EXCLUDED_INDUSTRIES = (40, 44, 45, 46, 49)  # finance, O/P/Q, households as employers


def allocate_external_firm_debt(countries, industry_weights):
    """Industry financial-statement weights; output shares within industries.

    Preserve real/cash assets. Equity changes exactly opposite bank debt.
    The explicitly recorded consolidation credit is INTERCOMPANY; a separate
    scope reconciliation offsets the difference between the old model stock
    and the unscaled national NBSA boundary. Bonds remain outside the model.
    """
    selected = [(n, c) for n, c in countries.items() if str(n).startswith('CAN_')]
    weights = np.asarray(industry_weights, dtype=float).copy()
    if weights.shape != (50,) or not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError('Expected 50 nonnegative, finite industry weights')
    weights[list(EXCLUDED_INDUSTRIES)] = 0
    output = np.zeros(50)
    for _, c in selected:
        d = c.firms.firm_data
        np.add.at(output, d['Industry'].to_numpy(), d['Production'].to_numpy() * d['Price'].to_numpy())
    weights[output <= 0] = 0
    if weights.sum() <= 0:
        raise ValueError('No eligible industry allocation')
    targets = EXTERNAL_LOANS * weights / weights.sum()
    old_total = sum(c.firms.firm_data['Debt'].sum() for _, c in selected)
    if old_total <= 0:
        raise ValueError('Consolidation requires a positive source debt stock')
    rows = []
    for name, c in selected:
        f = c.firms; d = f.firm_data
        for i, r in d.iterrows():
            industry = int(r['Industry'])
            new = targets[industry] * r['Production'] * r['Price'] / output[industry] if output[industry] else 0.
            credit = INTERCOMPANY * r['Debt'] / old_total
            scope = r['Debt'] - new - credit
            rows.append(dict(region=str(name), firm=int(i), industry=industry,
                debt_before=r['Debt'], debt_after=new, equity_before=r['Equity'],
                consolidation_equity_credit=credit, scope_equity_adjustment=scope,
                equity_after=r['Equity'] + credit + scope,
                capital=float(f.capital_inputs_stock[i].sum() * r['Price']),
                output=float(r['Production'] * r['Price'])))
            d.loc[i, 'Debt'] = new
            d.loc[i, 'Equity'] = r['Equity'] + credit + scope
        f.total_firm_debt = float(d['Debt'].sum())
    return rows
