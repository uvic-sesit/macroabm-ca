"""Reviewed QE baseline: accepted FE household rule and observed firm CFC."""
from pathlib import Path
from macromodel.configurations.household_closure_configuration import HouseholdClosureConfiguration

ROOT=Path(__file__).resolve().parents[2]
PICKLE=ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt_cfc_v2.pkl'
PICKLE_SHA256='a16386b64e0eeca5986dc1d4a3d94a4a7c0b33b178f76e1a8933e926948677ae'


def configuration():
    cfg=HouseholdClosureConfiguration.cashflow_candidate()
    cfg.financial_asset_drawdown=True
    cfg.investment_benchmark_enabled=True
    cfg.consumption_before_investment=True
    cfg.firm_payment_default_enabled=True
    return cfg
