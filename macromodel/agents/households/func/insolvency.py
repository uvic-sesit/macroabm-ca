"""Household insolvency management implementation.

This module implements household insolvency handling through:
- Default detection and processing
- Debt restructuring mechanisms
- Asset liquidation procedures
- Bank interaction management

The implementation handles:
- Insolvency identification
- Credit market impacts
- Non-performing loan tracking
- Default rate calculations
"""

from abc import ABC, abstractmethod
from typing import Tuple

import numpy as np

from macromodel.agents.banks.banks import Banks
from macromodel.agents.households.households import Households
from macromodel.markets.credit_market.credit_market import CreditMarket


class HouseholdInsolvencyHandler(ABC):
    """Abstract base class for household insolvency management.

    Defines interface for handling household defaults through:
    - Insolvency detection
    - Default processing
    - Credit market updates
    - Bank interactions
    """

    @abstractmethod
    def handle_insolvency(
        self,
        households: Households,
        banks: Banks,
        credit_market: CreditMarket,
    ) -> Tuple[float, float, float]:
        """Process household insolvency cases.

        Args:
            households (Households): Household sector agent
            banks (Banks): Banking sector agent
            credit_market (CreditMarket): Credit market interface

        Returns:
            Tuple[float, float, float]: Default rate, NPL ratios for consumption
                loans and mortgages
        """
        pass


class DefaultHouseholdInsolvencyHandler(HouseholdInsolvencyHandler):
    """Default implementation of household insolvency management.

    Implements insolvency handling through:
    - Net wealth and deposit checks
    - Loan removal processing
    - NPL ratio calculations
    """

    def handle_insolvency(
        self,
        households: Households,
        banks: Banks,
        credit_market: CreditMarket,
    ) -> Tuple[float, float, float]:
        """Process household defaults using default behavior.

        Handles insolvency through:
        - Identifying insolvent households
        - Processing loan removals
        - Calculating default metrics

        Args:
            households (Households): Household sector agent
            banks (Banks): Banking sector agent
            credit_market (CreditMarket): Credit market interface

        Returns:
            Tuple[float, float, float]: Default rate, NPL ratios for consumption
                loans and mortgages
        """
        insolvent_households = np.where(
            np.logical_and(
                households.ts.current("net_wealth") < 0,
                households.ts.current("wealth_deposits") < 0,
            )
        )[0]
        bad_hh_cons_loans, bad_mortgages = credit_market.remove_loans_to_households(insolvent_households)

        # Calculate NPL ratios
        total_cons_loans = credit_market.ts.current("total_outstanding_loans_granted_households_consumption")[0]
        if total_cons_loans == 0.0:
            npl_hh_cons_loans = 0.0
        else:
            npl_hh_cons_loans = bad_hh_cons_loans / total_cons_loans
        if credit_market.ts.current("total_outstanding_loans_granted_mortgages")[0] == 0.0:
            npl_mortgages = 0.0
        else:
            npl_mortgages = bad_mortgages / credit_market.ts.current("total_outstanding_loans_granted_mortgages")[0]

        return (
            len(insolvent_households) / households.ts.current("n_households"),
            npl_hh_cons_loans,
            npl_mortgages,
        )


class PersistentDistressHouseholdInsolvencyHandler(HouseholdInsolvencyHandler):
    """Restructure unsecured shortfalls after sustained payment distress.

    The model currently pays instalments automatically, allowing deposits to go
    negative. An increase in that overdraft, capped at scheduled debt service,
    is therefore a payment-shortfall PROXY, not an observed arrears account.
    No foreclosure or cash recovery is invented: collateral-backed principal
    survives as a restructured claim; only the unrecoverable excess is removed.
    """

    def __init__(self, distress_periods=3, collateral_haircut=0.2):
        if distress_periods < 1 or not 0 <= collateral_haircut < 1:
            raise ValueError("Invalid distress duration or collateral haircut")
        self.distress_periods = int(distress_periods)
        self.collateral_haircut = float(collateral_haircut)

    def handle_insolvency(self, households, banks, credit_market):
        h, cm = households, credit_market
        deposits = h.ts.current("wealth_deposits")
        previous = h.ts.prev("wealth_deposits")
        service = np.maximum(0, h.ts.current("debt_installments") + h.ts.current("interest_paid_on_loans"))
        shortfall = np.minimum(service, np.maximum(0, -deposits) - np.minimum(np.maximum(0, -deposits),
                                                                                    np.maximum(0, -previous)))
        prior = h.states.get("payment_distress_periods", np.zeros(len(deposits), dtype=int))
        consecutive = np.where(shortfall > 1e-8, prior + 1, 0)
        h.states["payment_distress_periods"] = consecutive
        h.states["debt_service_shortfall_proxy"] = shortfall
        eligible = consecutive >= self.distress_periods
        cons_before = cm.states["cons_loans"][0].sum(axis=0)
        mort_before = cm.states["mort_loans"][0].sum(axis=0)
        housing = np.maximum(0, h.ts.current("wealth_main_residence") + h.ts.current("wealth_other_properties"))
        secured_capacity = (1 - self.collateral_haircut) * housing
        # Outstanding overdrafts remain bank claims and rank against liquid assets.
        other_capacity = np.maximum(0, h.ts.current("wealth_other_real_assets")
                                    + h.ts.current("wealth_other_financial_assets") + deposits)
        secured_mort = np.minimum(mort_before, secured_capacity)
        unsecured_mort = mort_before - secured_mort
        unsecured_claims = cons_before + unsecured_mort
        unsecured_pool = other_capacity + np.maximum(0, secured_capacity - secured_mort)
        recovery_fraction = np.minimum(1, np.divide(unsecured_pool, unsecured_claims,
                                                   out=np.ones_like(unsecured_pool), where=unsecured_claims > 0))
        keep_mort = secured_mort + unsecured_mort * recovery_fraction
        keep_cons = cons_before * recovery_fraction
        cons_loss = np.where(eligible, cons_before - keep_cons, 0)
        mort_loss = np.where(eligible, mort_before - keep_mort, 0)
        by_bank = np.zeros(cm.states["cons_loans"].shape[1])
        for key, before, loss in (("cons_loans", cons_before, cons_loss), ("mort_loans", mort_before, mort_loss)):
            fraction = np.divide(loss, before, out=np.zeros_like(loss), where=before > 0)
            by_bank += (cm.states[key][0] * fraction).sum(axis=1)
            # Scale principal AND scheduled interest/principal consistently.
            cm.states[key] *= (1 - fraction)[None, None, :]
        cm._record_writeoff(cons_loss.sum() + mort_loss.sum(), by_bank=by_bank)
        restructured = cons_loss + mort_loss > 1e-8
        h.states["payment_distress_periods"][restructured] = 0
        h.states["restructured_principal"] = cons_loss + mort_loss
        # Write-downs change household liabilities in the same quarter.
        for key, value in (("consumption_loan_debt", cons_before - cons_loss),
                           ("mortgage_debt", mort_before - mort_loss)):
            h.ts.dicts[key][-1] = value
        h.ts.dicts["debt"][-1] = cons_before + mort_before - cons_loss - mort_loss
        h.ts.dicts["net_wealth"][-1] = h.ts.current("wealth") - h.ts.current("debt")
        for key, value in (("total_consumption_loan_debt", cons_before - cons_loss),
                           ("total_mortgage_debt", mort_before - mort_loss)):
            h.ts.dicts[key][-1] = np.array([value.sum()])
        return (restructured.mean(), cons_loss.sum() / cons_before.sum() if cons_before.sum() else 0.0,
                mort_loss.sum() / mort_before.sum() if mort_before.sum() else 0.0)
