import sys
from pathlib import Path
sys.path.insert(0,str(Path('dev/validation_2022').resolve()))
from ih_diagnostics import entrant_trigger

def test_amortisation_ratio_does_not_classify_a_contract_as_rate_reset():
    assert entrant_trigger(False,False,True)=='persistent_dissaver'
    assert entrant_trigger(False,False,False)=='other'
    assert entrant_trigger(False,True,True)=='income_loss'
    assert entrant_trigger(True,True,True)=='unable_from_t0'
