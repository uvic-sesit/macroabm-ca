"""Productivity Mega Deduction (PMD) -- opt-in hooks, off unless the PMD_* switches are set.

Budget 2026 full expensing: eligible depreciable capital is deducted from taxable
income in the year it becomes available for use. Two independent channels, both
OFF unless switched on by environment variables (the linkage starts the model as a
subprocess, so env vars are the least invasive switch -- same pattern as
CEC_NONBINDING_CAPITAL):

1. Tax base (PMD_TAX=1). Taxable profit = profit - e * eligible capital purchases
   + depreciation on the PMD-expensed stock. The model's profit already deducts
   economic depreciation on ALL capital, so expensed capital is tracked in its own
   stock S and its depreciation added back -- otherwise it would be deducted twice.
   Losses get nothing (no carryforward): a non-refundable deduction. PMD_TAX_SCALE
   multiplies the eligible base, for calibrating to Finance's federal cost.

2. Desired capital (PMD_EPS > 0). The fall in each buyer industry's user cost of
   capital (pmd_buyer.csv, from Finance METRs) times the elasticity raises the
   firm's desired eligible capital per unit of output. With the rolling reference
   rule a plain multiplier on K_ref would compound every quarter, so the target is
   anchored: K_ref = max(K_ref, (1 + g) * (K/Q at activation, rescaled by any later
   change in capital productivity) * Q_desired).

Tables (PMD_TABLES_DIR): pmd_goods.csv (good, asset_class, weight) and
pmd_buyer.csv (industry, me_incremental, f_eligible, dln_user_cost, invest_hook).
Eligibility of good g bought by industry i:
    asset_class ME   -> weight_g * me_incremental_i
    asset_class F    -> weight_g * f_eligible_i   (engineering share of construction)
    asset_class NONE -> 0
PMD_START_STEP: first model step the policy is active (counted from 0 per country).
PMD_LOG: CSV path; one row per province per step is appended.
"""

from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Quarterly depreciation of the PMD-expensed stocks (≈17%/yr M&E, ≈5%/yr structures).
_DEP_ME = 0.045
_DEP_F = 0.0125
FEDERAL_RATE = 0.15


@dataclass
class PMDConfig:
    tax: bool
    tax_scale: float
    eps: float
    start_step: int
    goods: pd.DataFrame
    buyer: pd.DataFrame
    log_path: Optional[Path]


_CONFIG: Optional[PMDConfig] = None
_LOADED = False


def config() -> Optional[PMDConfig]:
    """Read the env switches once per process. None when the experiment is off."""
    global _CONFIG, _LOADED
    if _LOADED:
        return _CONFIG
    _LOADED = True
    tax = os.environ.get("PMD_TAX", "0") == "1"
    eps = float(os.environ.get("PMD_EPS", "0") or 0.0)
    if not tax and eps <= 0.0:
        return None
    tables = Path(os.environ["PMD_TABLES_DIR"])
    goods = pd.read_csv(tables / "pmd_goods.csv", comment="#").set_index("good")
    buyer = pd.read_csv(tables / "pmd_buyer.csv", comment="#").set_index("industry")
    log = os.environ.get("PMD_LOG")
    _CONFIG = PMDConfig(
        tax=tax,
        tax_scale=float(os.environ.get("PMD_TAX_SCALE", "1") or 1.0),
        eps=eps,
        start_step=int(os.environ.get("PMD_START_STEP", "19")),
        goods=goods,
        buyer=buyer,
        log_path=Path(log) if log else None,
    )
    logger.warning("PMD experiment ON: tax=%s scale=%s eps=%s start_step=%s",
                   tax, _CONFIG.tax_scale, eps, _CONFIG.start_step)
    return _CONFIG


def eligibility(cfg: PMDConfig, industries: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """(industry x good) eligible shares, split into the M&E and structures parts."""
    n = len(industries)
    me = np.zeros((n, n))
    f = np.zeros((n, n))
    for gi, g in enumerate(industries):
        if g not in cfg.goods.index:
            continue
        cls = str(cfg.goods.at[g, "asset_class"]).strip()
        w = float(cfg.goods.at[g, "weight"])
        for bi, b in enumerate(industries):
            if b not in cfg.buyer.index:
                continue
            if cls == "ME":
                me[bi, gi] = w * float(cfg.buyer.at[b, "me_incremental"])
            elif cls == "F":
                f[bi, gi] = w * float(cfg.buyer.at[b, "f_eligible"])
    return me, f


def capital_uplift(cfg: PMDConfig, industries: list[str]) -> np.ndarray:
    """(industry x good) proportional rise in desired capital: eps * dlnUC on eligible goods."""
    me, f = eligibility(cfg, industries)
    elig = (me + f) > 0.0
    g = np.zeros(len(industries))
    for bi, b in enumerate(industries):
        if b in cfg.buyer.index and int(cfg.buyer.at[b, "invest_hook"]) == 1:
            g[bi] = cfg.eps * float(cfg.buyer.at[b, "dln_user_cost"])
    return np.where(elig, g[:, None], 0.0)


class PMDCountryState:
    """Per-country (province) state: step counter, expensed stocks, logging."""

    def __init__(self, cfg: PMDConfig, industries: list[str], country_name: str):
        self.cfg = cfg
        self.industries = list(industries)
        self.name = country_name
        self.step = -1
        self.me, self.f = eligibility(cfg, self.industries)
        self.uplift = capital_uplift(cfg, self.industries) if cfg.eps > 0 else None
        self.stock_me = None
        self.stock_f = None
        self.capital_hook_on = False

    def taxable_profits(self, firms, good_prices: np.ndarray, profits: np.ndarray,
                        tau: float) -> np.ndarray:
        """Called once per step where corporate tax is computed. Returns the tax base."""
        self.step += 1
        active = self.step >= self.cfg.start_step
        ind = np.asarray(firms.states["Industry"], dtype=int)
        profits = np.asarray(profits, dtype=float)
        nf = profits.shape[0]
        if self.stock_me is None:
            self.stock_me = np.zeros(nf)
            self.stock_f = np.zeros(nf)

        # Switch the capital hook on from the start step (takes effect next step's order).
        if active and self.uplift is not None:
            setter = firms.functions["target_capital_inputs"]
            prod = np.asarray(firms.get_effective_capital_coefficients(), dtype=float)
            if not self.capital_hook_on:
                setter._pmd_uplift = self.uplift[ind]          # firms x goods
                setter._pmd_anchor = None
                self._prod0 = prod.copy()
                self.capital_hook_on = True
            # Capital needed per unit of output is 1 / productivity. When the linkage moves
            # productivity later (transition_capital at CIMS milestones), the anchored K/Q
            # follows it, so PMD adds its uplift on top instead of freezing the 2026 ratio.
            # Goods a sector does not use as capital carry INFINITE productivity in the model
            # (inf / inf = NaN), so the ratio is taken only where both values are finite.
            if prod.shape == self._prod0.shape:
                ok = np.isfinite(prod) & np.isfinite(self._prod0) & (prod > 0.0)
                setter._pmd_prod_ratio = np.divide(self._prod0, prod, out=np.ones_like(prod),
                                                   where=ok)

        bought = np.asarray(firms.ts.current("real_amount_bought_as_capital_goods"), dtype=float)
        value = np.nan_to_num(bought * np.asarray(good_prices, dtype=float)[None, :])
        elig_me = (value * self.me[ind]).sum(axis=1) * self.cfg.tax_scale if active else np.zeros(nf)
        elig_f = (value * self.f[ind]).sum(axis=1) * self.cfg.tax_scale if active else np.zeros(nf)
        addback = _DEP_ME * self.stock_me + _DEP_F * self.stock_f
        self.stock_me = self.stock_me * (1.0 - _DEP_ME) + elig_me
        self.stock_f = self.stock_f * (1.0 - _DEP_F) + elig_f

        if self.cfg.tax:
            taxable = profits - elig_me - elig_f + addback
        else:
            taxable = profits
        self._log(profits, taxable, tau, elig_me, elig_f, addback, value)
        return taxable

    def _log(self, profits, taxable, tau, elig_me, elig_f, addback, value):
        path = self.cfg.log_path
        if path is None:
            return
        base_loss = float(np.maximum(profits, 0).sum() - np.maximum(taxable, 0).sum())
        row = {
            "province": self.name, "step": self.step,
            "capital_purchases": float(value.sum()),
            "eligible_me": float(elig_me.sum()), "eligible_f": float(elig_f.sum()),
            "addback": float(addback.sum()),
            "tax_base_reduction": base_loss,
            "revenue_forgone_model_rate": float(tau) * base_loss,
            "revenue_forgone_federal": FEDERAL_RATE * base_loss,
            "stock_me": float(self.stock_me.sum()), "stock_f": float(self.stock_f.sum()),
            "profits_pos": float(np.maximum(profits, 0).sum()),
        }
        new = not path.exists()
        with open(path, "a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(row))
            if new:
                w.writeheader()
            w.writerow(row)


def apply_capital_target(setter, reference_capital_stock: np.ndarray,
                         prev_capital_inputs_stock: np.ndarray, prev_production: np.ndarray,
                         desired_production: Optional[np.ndarray]) -> np.ndarray:
    """Raise eligible reference capital to (1+g) x the activation K/Q ratio x desired output."""
    uplift = getattr(setter, "_pmd_uplift", None)
    if uplift is None or uplift.shape != reference_capital_stock.shape:
        return reference_capital_stock
    if getattr(setter, "_pmd_anchor", None) is None:
        q = np.asarray(prev_production, dtype=float)
        setter._pmd_anchor = np.divide(
            prev_capital_inputs_stock, q[:, None],
            out=np.zeros_like(prev_capital_inputs_stock, dtype=float),
            where=q[:, None] > 0.0,
        )
    q_des = np.asarray(desired_production if desired_production is not None else prev_production,
                       dtype=float)
    ratio = getattr(setter, "_pmd_prod_ratio", None)
    anchor = setter._pmd_anchor
    if ratio is not None and ratio.shape == anchor.shape:
        anchor = anchor * ratio
    target = (1.0 + uplift) * anchor * q_des[:, None]
    # Never let a non-finite PMD target reach the market: fall back to the model's own value.
    use = (uplift > 0.0) & np.isfinite(target)
    return np.where(use, np.maximum(reference_capital_stock, target), reference_capital_stock)
