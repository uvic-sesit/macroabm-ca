import numpy as np
from macro_data.processing.synthetic_population.cis_cash_allocation import conserve_payroll

def test_cis_matching_preserves_each_employer_cash_bill_and_capacity():
    w,L,f=conserve_payroll(np.array([0,1,1,2]),np.array([0.,0.,1.,np.nan]),np.array([1,1,1,0],bool),np.array([10.,30.,50.,0.]),np.array([1.,1.,1.,0.]),np.array([3.,1.,0.]))
    assert np.isclose(w[:2].sum(),40.) and w[2]==50 and w[3]==0
    assert np.isclose(L[:2].sum(),2.) and L[2]==1 and L[3]==0
    assert np.isclose(w[0]/w[1],6.)

def test_unsupported_cis_payroll_retains_existing_shares_without_new_cash():
    w,L,f=conserve_payroll(np.array([0,1]),np.array([0.,0.]),np.array([1,1],bool),np.array([10.,30.]),np.ones(2),np.zeros(2))
    np.testing.assert_allclose(w,[10.,30.]);assert f==[0]

def test_initial_cis_transfers_keep_exact_public_budget_and_zero_recipients():
    from macromodel.agents.households.func.social_transfers import InitialAllocationSocialTransfersSetter
    s=InitialAllocationSocialTransfersSetter([0.,1.,3.])
    for budget in [40.,80.]:
        np.testing.assert_allclose(s.get_social_transfers(3,budget,None,None,None),[0,budget/4,3*budget/4])

def test_cis_transfer_allocation_survives_reset(monkeypatch):
    from types import SimpleNamespace
    import macromodel.agents.households.households as module
    monkeypatch.setattr(module,'update_functions',lambda **kwargs:kwargs['functions'].update(social_transfers=None))
    h=SimpleNamespace(gen_reset=lambda:None,functions={},states={'cis_government_allocation':np.array([0.,1.,3.])})
    module.Households.reset(h,SimpleNamespace(functions=None))
    np.testing.assert_allclose(h.functions['social_transfers'].get_social_transfers(3,40.,None,None,None),[0.,10.,30.])
