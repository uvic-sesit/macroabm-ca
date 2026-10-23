from types import SimpleNamespace as NS

import numpy as np
import pytest

from macromodel.agents.banks.banks import Banks
from macromodel.agents.banks.func.demography import DefaultBankDemography
from macromodel.agents.central_government.central_government import CentralGovernment
from macromodel.configurations.bank_configuration import BankParameters
from macromodel.markets.credit_market.credit_market import CreditMarket
from macromodel.timeseries import TimeSeries


@pytest.mark.parametrize('equity', [-20., 2.])
def test_resolution_preserves_borrower_contracts_and_funds_the_equity_hole(equity):
    cm = NS(states={k: np.arange(12., dtype=float).reshape(3, 1, 4)
                    for k in ['st_loans', 'lt_loans', 'cons_loans', 'mort_loans']})
    cm.remove_loans_by_bank = lambda i: CreditMarket.remove_loans_by_bank(cm, i)
    before = {k: v.copy() for k, v in cm.states.items()}
    b = NS(parameters=BankParameters(), states={'is_insolvent': np.array([False]),
           'loan_losses_current': np.array([30.])},
           functions={'demography': DefaultBankDemography(.05)},
           ts=TimeSeries(equity=np.array([10.]), total_outstanding_loans=np.array([100.]),
                         deposits_from_firms=np.array([50.]), deposits_from_households=np.array([30.]),
                         deposits=np.array([equity - 20.]), liability=np.zeros(1)))
    b.ts.equity.append(np.array([equity]))
    b.compute_deposits = lambda: Banks.compute_deposits(b)
    b.compute_liability = lambda: Banks.compute_liability(b)
    recap = Banks.handle_insolvency(b, cm)
    for k in before:
        np.testing.assert_array_equal(cm.states[k], before[k])
    assert b.ts.current('equity')[0] == pytest.approx(9.)
    assert b.ts.current('equity')[0] - equity == pytest.approx(recap)
    assert b.ts.current('deposits')[0] == pytest.approx(50 + 30 + 9 - 100)
    assert b.ts.current('equity')[0] / (100 + b.ts.current('deposits')[0]) > .05
    assert b.states['resolution_count'][0] == 1
    assert b.states['resolution_events'][0]['losses_absorbed_by_equity'] == 10.
    assert b.states['recapitalisation_current'].sum() == recap

    g = NS(ts=TimeSeries(bank_equity_injection=np.array([recap]),
                         debt=np.array([100.]), revenue=np.array([0.]),
                         unemployment_benefits_paid=np.array([0.])))
    deficit = CentralGovernment.compute_deficit(g, np.array([]), np.array([]), np.array([]),
                                                0., total_unemployment_benefits_paid=0.)
    assert deficit[0] == pytest.approx(recap)
