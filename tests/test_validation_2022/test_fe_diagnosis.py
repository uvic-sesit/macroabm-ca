import importlib.util
import sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parents[2]/'dev/validation_2022'
sys.path.insert(0,str(HERE))
from fe_instrumentation import constraint_classes


def test_income_restoration_distinguished_from_persistent_asset_drawdown():
    r=constraint_classes(np.array([True,True,False]),np.array([100,100,100]),np.array([80,80,110]),
        np.array([70,70,100]),np.array([100,75,100]),np.array([5,5,5]),np.array([20,20,20]))
    assert r.tolist()==['income_restoration_sufficient','persistent_spending_gap_assets_down','unconstrained']
