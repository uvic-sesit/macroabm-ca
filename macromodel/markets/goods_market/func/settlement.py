"""Settlement of goods-market payments at the sellers' prices (validation-2022, D6).

The clearing algorithms allocate real quantities and charge buyers the industry's average (supply-weighted) price,
while each seller books its own price times the quantity it sold (Agent.record). With heterogeneous seller prices
the two nominal totals differ, so money is created or destroyed in every period. Settlement keeps the real
allocation unchanged and rescales, for every origin country o, destination country d and industry g, the buyers'
payments so that they equal the sellers' receipts:

    sum_{buyers b in d} spent_b(o, g)  :=  sum_{sellers s in o, industry g} p_s * q_s(to d)

i.e. buyers pay the realised quantity-weighted price of the sellers they were supplied by. All amounts in USD
(transactor states); local-currency conversion happens in Agent.record.
"""

from __future__ import annotations

import numpy as np


def _sellers(participants, country):
    for tr in participants[country]:
        s = tr.transactor_seller_states
        if "Prices" in s and "Industries" in s and "Real Amount sold" in s:
            yield s


def _buyers(participants, country):
    for tr in participants[country]:
        b = tr.transactor_buyer_states
        if "Nominal Amount spent" in b:
            yield b


def bilateral_flows(participants: dict, n_industries: int) -> dict:
    """Seller receipts, buyer payments and real quantities for every (origin, destination) pair, by industry."""
    countries = list(participants.keys())
    flows = {}
    for o in countries:
        for d in countries:
            rev = np.zeros(n_industries)
            q_sold = np.zeros(n_industries)
            for s in _sellers(participants, o):
                q = s.get("Real Amount sold to " + d)
                if q is None:
                    continue
                ind = np.asarray(s["Industries"], dtype=int)
                rev += np.bincount(ind, weights=np.asarray(s["Prices"], float) * q, minlength=n_industries)
                q_sold += np.bincount(ind, weights=q, minlength=n_industries)
            pay = np.zeros(n_industries)
            q_bought = np.zeros(n_industries)
            for b in _buyers(participants, d):
                x = b.get("Nominal Amount spent on Goods from " + o)
                if x is None:
                    continue
                pay += np.asarray(x, float).reshape(-1, n_industries).sum(axis=0)
                q_bought += np.asarray(b["Real Amount bought from " + o], float).reshape(-1, n_industries).sum(axis=0)
            if rev.any() or pay.any():
                flows[(o, d)] = {"receipts": rev, "payments": pay, "real_sold": q_sold, "real_bought": q_bought}
    return flows


def settle_at_seller_prices(participants: dict, n_industries: int) -> dict:
    """Rescale buyer payments to the sellers' receipts; returns a diagnostic summary (USD).

    Pairs where buyers paid but no seller booked a sale, or vice versa, cannot be settled by rescaling; they are
    left unchanged and reported (`unsettled_payments`, `unsettled_receipts`).
    """
    flows = bilateral_flows(participants, n_industries)
    negative_spending = 0.0
    for d in participants.keys():
        for b in _buyers(participants, d):
            x = np.asarray(b["Nominal Amount spent"], float)
            negative_spending += float(x[x < 0].sum())
    gap_before = 0.0
    unsettled_pay = 0.0
    unsettled_rec = 0.0
    real_gap = 0.0
    for (o, d), f in flows.items():
        rev, pay = f["receipts"], f["payments"]
        gap_before += float((pay - rev).sum())
        real_gap += float(np.abs(f["real_bought"] - f["real_sold"]).sum())
        ok = (pay > 0) & (rev > 0)
        unsettled_pay += float(pay[(pay > 0) & ~ok].sum())
        unsettled_rec += float(rev[(rev > 0) & ~ok].sum())
        factor = np.where(ok, rev / np.where(ok, pay, 1.0), 1.0)
        if np.all(factor == 1.0):
            continue
        for b in _buyers(participants, d):
            key = "Nominal Amount spent on Goods from " + o
            if key in b:
                b[key] = b[key] * factor[None, :] if b[key].ndim == 2 else b[key] * factor
    # total spending = sum over origins
    for d in participants.keys():
        for b in _buyers(participants, d):
            parts = [b["Nominal Amount spent on Goods from " + o] for o in participants.keys()
                     if ("Nominal Amount spent on Goods from " + o) in b]
            if parts:
                b["Nominal Amount spent"] = np.sum(parts, axis=0)
    return {
        "payments_minus_receipts_before": gap_before,
        "unsettled_payments": unsettled_pay,
        "unsettled_receipts": unsettled_rec,
        "abs_real_quantity_gap": real_gap,
        # negative purchases are clipped to zero by Agent.record on the buyer side only; must be 0
        "negative_buyer_spending": negative_spending,
    }
