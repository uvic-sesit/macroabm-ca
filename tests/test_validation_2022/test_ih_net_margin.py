import sys
from pathlib import Path
sys.path.insert(0,str(Path('dev/validation_2022').resolve()))
from prepare_ih import net_gate
import pandas as pd

def test_net_surplus_gate_allows_above_price_only_for_negative_nos():
    f=pd.DataFrame(dict(output=[100.,100.],price=[1.,1.],unit_cost=[1.1,1.1],IO_GOS=[10.,20.],CFC=[20.,10.]))
    r=net_gate(f)
    assert not r.iloc[0].margin_fail and not r.iloc[0].above_price_exception
    assert r.iloc[1].margin_fail and r.iloc[1].above_price_exception
