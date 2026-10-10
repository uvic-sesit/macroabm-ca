"""Optional buyer-specific origin shares for the goods market (off unless attached).

The goods market splits each buyer's demand for a good between origins (own province,
other provinces, rest of world) with one share per destination country and good, so
every buyer in a province sources a good identically. This layer gives each buyer its
own split from the IO tables -- firms by industry (intermediate shares for their
intermediate demand, business-investment shares for their capital demand), households
(household consumption) and government (government consumption) -- and can impose
import-share targets on any buyer and good (onshoring policies, import caps).

It acts only in the trade-proportion stage of clearing: each quarter it turns the
buyer's IO shares into multipliers on the market's price-adjusted proportions,
tp_buyer[o] = tp[o] * (S_buyer[o] / S_ref[o]) renormalised over origins, keeping the
market's price response. mode="relative" (default): S_ref = the IO all-buyer average,
so each buyer deviates from the model's own province split by its IO pattern and
province totals stay at the model's calibration. mode="absolute": S_ref = the model's
default split, so each buyer starts exactly at its IO shares (totals follow the IO). Demand the
preferred origins cannot fill still clears in the unconstrained stage afterwards, as
for every buyer, so a target without domestic capacity shows up as unmet or imported.

Attach:  clearer.buyer_sourcing = BuyerSourcing.from_npz(path, participant_names)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np


class BuyerSourcing:
    def __init__(self, participant_names: list[str], tables: dict[str, dict[str, np.ndarray]],
                 row_name: str = "ROW", mode: str = "relative"):
        if mode not in ("relative", "absolute"):
            raise ValueError(f"Unknown buyer-sourcing mode: {mode!r}")
        self.mode = mode
        self.names = list(participant_names)
        self.row = self.names.index(row_name)
        self.tables = tables  # destination -> {"firm_intermediate", "gfcf", "households", "government"}
        # (destination, buyer kind, industry or None, good index) -> import share target
        self.import_share_targets: dict[tuple[str, str, Optional[int], int], float] = {}

    @classmethod
    def from_npz(cls, path: str | Path, participant_names: list[str], mode: str = "relative") -> "BuyerSourcing":
        data = np.load(path, allow_pickle=False)
        origins = [str(o) for o in data["origins"]]
        order = [origins.index(n) if n in origins else None for n in participant_names]
        tables = {}
        for dest in participant_names:
            if f"{dest}/households" not in data:
                continue
            t = {}
            for key in ("firm_intermediate", "gfcf", "households", "government", "average"):
                src = data[f"{dest}/{key}"]
                arr = np.full((len(participant_names),) + src.shape[1:], np.nan)
                for i, j in enumerate(order):
                    if j is not None:
                        arr[i] = src[j]
                t[key] = arr
            tables[dest] = t
        return cls(participant_names, tables, mode=mode)

    # ------------------------------------------------------------------ policy
    def set_import_share(self, destination: str, buyer: str, good: int, share: Optional[float],
                         industry: Optional[int] = None) -> None:
        """Target import share for (destination, buyer kind, [industry], good); None clears it.

        buyer: "firms" (with industry = the buying industry's index), "households" or
        "government". The rest-of-world share is set to ``share`` and the domestic origins
        are rescaled proportionally to fill the remainder.
        """
        key = (destination, buyer, industry, int(good))
        if share is None:
            self.import_share_targets.pop(key, None)
        else:
            self.import_share_targets[key] = float(min(max(share, 0.0), 1.0))

    # ------------------------------------------------------------------ market
    def _apply_targets(self, shares: np.ndarray, dest: str, buyer: str,
                       industries: Optional[np.ndarray]) -> np.ndarray:
        """shares: (origin, good) or (origin, row, good); returns a copy with targets applied."""
        if not self.import_share_targets:
            return shares
        out = shares.copy()
        dom = np.ones(len(self.names), dtype=bool)
        dom[self.row] = False
        for (d, b, ind, g), target in self.import_share_targets.items():
            if d != dest or b != buyer:
                continue
            if out.ndim == 2:
                cols = [(slice(None), g)]
            else:
                rows = np.arange(out.shape[1]) if ind is None else np.flatnonzero(industries == ind)
                cols = [(r, g) for r in rows]
            for c in cols:
                v = out[(slice(None),) + c] if out.ndim == 3 else out[:, g]
                d_sum = np.nansum(v[dom])
                if not np.isfinite(v).any() or d_sum <= 0.0:
                    continue
                new = v.copy()
                new[dom] = v[dom] / d_sum * (1.0 - target)
                new[self.row] = target
                if out.ndim == 3:
                    out[:, c[0], g] = new
                else:
                    out[:, g] = new
        return out

    @staticmethod
    def _multipliers(target: np.ndarray, tp: np.ndarray, default: np.ndarray) -> np.ndarray:
        """Per-origin multipliers m with sum_o tp[o] m[o] = 1 and tp*m proportional to tp*target/default.

        target: (origin, ..., good) buyer shares (NaN = no IO information -> province average).
        tp, default: (origin, good) market proportions for this destination.
        """
        extra = target.ndim - 2
        tp_b = tp.reshape(tp.shape[:1] + (1,) * extra + tp.shape[1:])
        de_b = default.reshape(tp_b.shape)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(de_b > 0.0, target / de_b, 0.0)
        no_info = ~np.isfinite(target).any(axis=0, keepdims=True)
        ratio = np.where(np.isfinite(ratio), ratio, 0.0)
        ratio = np.where(no_info, 1.0, ratio)
        weighted = tp_b * ratio
        total = weighted.sum(axis=0, keepdims=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            mult = np.where(total > 0.0, ratio / total, 1.0)
        return mult

    def prepare(self, goods_market_participants: dict, origin_tp: np.ndarray,
                default_origin_tp: np.ndarray, balance_iterations: int = 3) -> None:
        """Store each buyer's origin multipliers for this clearing (origin_tp: price-adjusted).

        1. Each buyer's IO split -> its effective origin shares E = tp * multiplier.
        2. Balance (relative mode): rescale origins so the demand-weighted average over
           all buyers equals the market's own split tp, then renormalise each buyer
           (a few proportional-fitting passes) -- buyers keep their relative differences,
           province totals stay at the model's calibration.
        3. Import-share targets are applied AFTER balancing, to the targeted buyers only,
           so an onshoring target lowers imports instead of being offset elsewhere.
        """
        for c2, dest in enumerate(self.names):
            t = self.tables.get(dest)
            if t is None:
                continue
            tp = origin_tp[:, c2, :]
            de = default_origin_tp[:, c2, :] if self.mode == "absolute" else t["average"]
            de = np.where(np.isfinite(de), de, 0.0)
            entries = []  # (transactor, kind, effective shares, demand by good per row, industries)
            for transactor in goods_market_participants[dest]:
                kind = type(transactor).__name__
                industries = None
                if kind == "Firms":
                    industries = np.asarray(transactor.states["Industry"])
                    ti = np.asarray(transactor.ts.current("target_intermediate_inputs"), dtype=float)
                    tc = np.asarray(transactor.ts.current("target_capital_inputs"), dtype=float)
                    with np.errstate(divide="ignore", invalid="ignore"):
                        w = np.where(ti + tc > 0.0, ti / (ti + tc), 1.0)       # (row, good)
                    inter = t["firm_intermediate"][:, industries, :]           # (origin, row, good)
                    gfcf = np.broadcast_to(t["gfcf"][:, None, :], inter.shape)
                    inter_f = np.where(np.isfinite(inter), inter, gfcf)
                    gfcf_f = np.where(np.isfinite(gfcf), gfcf, inter)
                    shares = w[None] * inter_f + (1.0 - w[None]) * gfcf_f
                elif kind == "Households":
                    shares = t["households"]
                elif kind == "GovernmentEntities":
                    shares = t["government"]
                else:
                    transactor._buyer_origin_multiplier = None
                    continue
                eff = self._multipliers(shares, tp, de) * (tp[:, None, :] if shares.ndim == 3 else tp)
                demand = np.asarray(transactor.transactor_buyer_states["Initial Goods"], dtype=float)
                demand = demand if shares.ndim == 3 else demand.sum(axis=0)
                entries.append([transactor, kind, eff, np.maximum(demand, 0.0), industries])

            if self.mode == "relative" and entries:
                for _ in range(balance_iterations):
                    num = np.zeros_like(tp)
                    den = np.zeros(tp.shape[1])
                    for _, _, eff, d, _ in entries:
                        if eff.ndim == 3:
                            num += (eff * d[None]).sum(axis=1)
                            den += d.sum(axis=0)
                        else:
                            num += eff * d[None]
                            den += d
                    with np.errstate(divide="ignore", invalid="ignore"):
                        avg = np.where(den > 0.0, num / den, tp)
                        kappa = np.where(avg > 0.0, tp / avg, 1.0)
                    for e in entries:
                        k = kappa[:, None, :] if e[2].ndim == 3 else kappa
                        new = e[2] * k
                        total = new.sum(axis=0, keepdims=True)
                        e[2] = np.where(total > 0.0, new / np.where(total > 0.0, total, 1.0), e[2])

            for transactor, kind, eff, _, industries in entries:
                buyer = {"Firms": "firms", "Households": "households", "GovernmentEntities": "government"}[kind]
                eff = self._apply_targets(eff, dest, buyer, industries)
                tp_b = tp[:, None, :] if eff.ndim == 3 else tp
                with np.errstate(divide="ignore", invalid="ignore"):
                    transactor._buyer_origin_multiplier = np.where(tp_b > 0.0, eff / tp_b, 0.0)


def origin_multiplier(transactor, origin: Optional[int]):
    """Multiplier array for this buyer and origin (rows x goods, or goods), or 1.0."""
    if origin is None:
        return 1.0
    mult = getattr(transactor, "_buyer_origin_multiplier", None)
    if mult is None:
        return 1.0
    return mult[origin]
