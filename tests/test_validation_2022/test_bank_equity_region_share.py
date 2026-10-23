import pandas as pd
import pytest
from macro_data.configuration.countries import Country
from macro_data.configuration.region import Region
from macro_data.readers.economic_data.eurostat_reader import EuroStatReader


@pytest.mark.parametrize('has_own_data',[True,False])
def test_regional_bank_proxy_amounts_sum_to_one_national_amount(has_own_data):
    r=object.__new__(EuroStatReader)
    r.c_map=pd.DataFrame({'Alpha-3 code':[Country('CAN'),Country('FRA')],'Alpha-2 code':['CA','FR']})
    rows=[['MIO_NAC,NCO,S122_S123,ASS,F5,FR',100.]]
    if has_own_data:rows.append(['MIO_NAC,NCO,S122_S123,ASS,F5,CA',200.])
    r.data={'financial_balance_sheets':pd.DataFrame(rows,columns=[r'unit,co_nco,sector,finpos,na_item,geo\time','2022'])}
    r.total_output={Country('CAN'):200.,Country('FRA'):100.}
    regions=[Region('CAN_ON',Country('CAN'),'Ontario',.6),Region('CAN_QC',Country('CAN'),'Quebec',.4)]
    national=r.get_total_bank_equity(Country('CAN'),2022)
    assert [r.get_total_bank_equity(x,2022) for x in regions]==pytest.approx([.6*national,.4*national])
    assert sum(r.get_total_bank_equity(x,2022) for x in regions)==pytest.approx(national)
