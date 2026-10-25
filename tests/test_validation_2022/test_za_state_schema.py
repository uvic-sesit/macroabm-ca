import importlib.util
from pathlib import Path
import pandas as pd


def test_only_unset_initial_target_forecast_is_excluded():
    path=Path(__file__).parents[2]/'dev/validation_2022/za_state_schema.py'
    spec=importlib.util.spec_from_file_location('za_schema',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rows=pd.DataFrame(dict(quarter=[0,1,2,0],field=['target_production']*3+['production']))
    assert module.defined_floor_states(rows).tolist()==[False,True,True,True]
