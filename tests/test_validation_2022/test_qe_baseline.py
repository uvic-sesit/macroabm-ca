from dev.validation_2022.qe_baseline import configuration,PICKLE_SHA256


def test_reviewed_f_cfc_baseline_keeps_unaccepted_rules_off():
    c=configuration()
    assert c.firm_payment_default_enabled and c.financial_asset_drawdown
    assert c.investment_benchmark_enabled and c.consumption_before_investment
    assert not c.buffer_stock_enabled and not c.distress_enabled
    assert not c.prudent_firm_payout_enabled and not getattr(c,'quintile_propensity_enabled',False)
    assert PICKLE_SHA256=='a16386b64e0eeca5986dc1d4a3d94a4a7c0b33b178f76e1a8933e926948677ae'
