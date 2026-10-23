from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from macro_data.processing.synthetic_banks.canadian_book_capital import (
    CANADIAN_BANK_BOOK_EQUITY_2022, allocate_canadian_book_capital,
)
from macro_data.processing.synthetic_banks.default_synthetic_banks import DefaultSyntheticBanks
from macro_data.readers.economic_data.eurostat_reader import EuroStatReader


def test_nbsa_book_equity_does_not_read_asset_f5():
    reader = object.__new__(EuroStatReader)
    assert reader.get_total_bank_equity('CAN', 2022) == 456221e6


def test_joint_allocation_preserves_contracts_and_reserve_identity():
    countries = {}
    for name, loans in [('CAN_ON', 100.), ('CAN_QC', 300.)]:
        b = object.__new__(DefaultSyntheticBanks)
        b.bank_data = pd.DataFrame({'Loans to Firms': [loans / 2], 'Loans to Households': [loans / 2],
            'Consumption Loans to Households': [loans / 4], 'Mortgages to Households': [loans / 4],
            'Deposits from Firms': [80.], 'Deposits from Households': [50.],
            'Interest Rates on Household Deposits': [.01], 'Interest Rates on Firm Deposits': [.01],
            'Overdraft Rate on Firm Deposits': [.03], 'Overdraft Rate on Household Deposits': [.04],
            'Interest received from Loans': [4.]})
        countries[name] = NS(banks=b, tax_data=NS(profit_tax=.2))
    rows = allocate_canadian_book_capital(countries)
    assert sum(r['equity'] for r in rows) == pytest.approx(CANADIAN_BANK_BOOK_EQUITY_2022)
    assert [r['loan_share'] for r in rows] == [.25, .75]
    for name, loans in [('CAN_ON', 100.), ('CAN_QC', 300.)]:
        d = countries[name].banks.bank_data.iloc[0]
        assert d['Loans to Firms'] + d['Loans to Households'] == loans
        assert d['Deposits from Firms'] + d['Deposits from Households'] == 130.
        assert d['Deposits'] == pytest.approx(130. + d['Equity'] - loans)
        assert np.isfinite(d['Profits'])
        assert d['Corporate Taxes Paid'] == pytest.approx(.2 * max(0, d['Profits']))
