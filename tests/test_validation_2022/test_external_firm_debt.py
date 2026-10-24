from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from macro_data.processing.synthetic_firms.canadian_external_debt import (
    allocate_external_firm_debt, EXTERNAL_LOANS, INTERCOMPANY)


def country(output):
    d=pd.DataFrame({'Industry':[0,1,44,45,46,40,49], 'Production':output,
                    'Price':np.ones(7),'Debt':np.full(7,2e11),'Equity':np.full(7,3e11)})
    return SimpleNamespace(firms=SimpleNamespace(firm_data=d,capital_inputs_stock=np.ones((7,2))))


def test_external_boundary_consolidation_and_output_allocation():
    countries={'CAN_A':country([1,3,1,1,1,1,1]),'CAN_B':country([3,1,1,1,1,1,1])}
    weights=np.ones(50);weights[0]=2;weights[1]=1
    r=pd.DataFrame(allocate_external_firm_debt(countries,weights))
    assert r.debt_after.sum()==pytest.approx(EXTERNAL_LOANS)
    assert r.consolidation_equity_credit.sum()==pytest.approx(INTERCOMPANY)
    assert np.allclose(r.equity_after-r.equity_before,r.debt_before-r.debt_after)
    assert (r.loc[r.industry.isin([40,44,45,46,49]),'debt_after']==0).all()
    a=r[(r.region=='CAN_A')&(r.industry==0)].debt_after.iloc[0]
    b=r[(r.region=='CAN_B')&(r.industry==0)].debt_after.iloc[0]
    assert b==pytest.approx(3*a)
    assert r[r.industry==0].debt_after.sum()==pytest.approx(2*r[r.industry==1].debt_after.sum())


def test_bad_industry_weight_rejected():
    with pytest.raises(ValueError): allocate_external_firm_debt({'CAN_A':country([1]*7)},np.full(50,np.nan))
