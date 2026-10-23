from pathlib import Path
import sys
from types import SimpleNamespace as NS
import numpy as np
import pytest
from macromodel.timeseries import TimeSeries
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'dev/validation_2022'))
from ife_ledger import cash_ledger


def test_cash_ledger_separates_capital_and_consumption_and_all_counterparts():
    ts=TimeSeries(income=np.array([100.]),consumption=np.array([40.]),investment=np.array([[10.]]),
        debt_installments=np.array([15.]),interest_paid=np.array([3.]),rent=np.array([5.]),
        received_consumption_loans=np.array([2.]),received_mortgages=np.array([0.]),
        wealth_deposits=np.array([20.]),wealth_other_financial_assets=np.array([30.]),
        price_paid_for_property=np.array([8.]),property_sale_proceeds=np.array([1.]))
    ts.wealth_other_financial_assets.append(np.array([26.]))
    # income - C44 - I12 - principal15 - interest3 - rent5 + loan2 + L4 - house8 + sale1 =20
    ts.wealth_deposits.append(np.array([40.]))
    h=NS(ts=ts,states={'ofa_liquidation_without_issuer':np.array([4.])})
    r=cash_ledger(h,.1,.2).iloc[0]
    assert r.consumption_VAT==44.
    assert r.investment_CF==12.
    assert r.deposit_change==20.
    assert r.cash_residual==0.
    ts.dicts['wealth_deposits'][-1]+=1.
    with pytest.raises(AssertionError):cash_ledger(h,.1,.2)
