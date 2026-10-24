"""Approved discretionary dividends: retained profit and forward cash reserve."""
import numpy as np


def prudent_requests(requests, deposits, retained_profit, reserve):
    """Preserve mixed/transfers exactly; do not redeploy released dividends."""
    approved=np.asarray(requests,float).copy()
    cash=np.maximum(0.,np.asarray(deposits)-approved[:2].sum(axis=0)-np.asarray(reserve))
    approved[2]=np.minimum(approved[2],np.minimum(np.maximum(0.,retained_profit),cash))
    return approved


def scheduled_reserve(country):
    """Current contracts are next-period schedule; latest nominal wage forecast.

    No maturity extension, new reserve multiplier, or ignored overdraft cost.
    The reserve is measured at declaration, before current market outcomes.
    """
    cm=country.credit_market;f=country.firms;b=country.banks
    service=sum((cm.states[k][1]+np.minimum(cm.states[k][0],cm.states[k][2])).sum(axis=0)
                for k in ('st_loans','lt_loans'))
    overdraft=np.maximum(0.,-f.ts.current('deposits'))
    od_interest=overdraft*b.ts.current('overdraft_rate_on_firm_deposits')[f.states['Corresponding Bank ID']]
    return np.maximum(0.,service)+od_interest+np.maximum(0.,f.ts.current('total_wage'))
