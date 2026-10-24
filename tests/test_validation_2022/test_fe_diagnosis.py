import importlib.util
import sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parents[2]/'dev/validation_2022'
sys.path.insert(0,str(HERE))
from fe_instrumentation import constraint_classes,household_workers


def test_income_restoration_distinguished_from_persistent_asset_drawdown():
    r=constraint_classes(np.array([True,True,False]),np.array([100,100,100]),np.array([80,80,110]),
        np.array([70,70,100]),np.array([100,75,100]),np.array([5,5,5]),np.array([20,20,20]))
    assert r.tolist()==['income_restoration_sufficient','persistent_spending_gap_assets_down','unconstrained']


def test_household_employment_uses_jobs_not_positive_wage_income():
    assert household_workers([0,0,1,1],[2,-1,-1,7],3).tolist()==[1,1,0]
