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
tp_buyer[o] = tp[o] * (S_buyer[o] / S_default[o]) renormalised over origins, so the
buyer starts at its IO split and keeps the market's price response. Demand the
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
                 row_name: str = "ROW"):
        self.names = list(participant_names)
        self.row = self.names.index(row_name)
        self.tables = tables  # destination -> {"firm_intermediate", "gfcf", "households", "government"}
        # (destination, buyer kind, industry or None, good index) -> import share target
        self.import_share_targets: dict[tuple[str, str, Optional[int], int], float] = {}

    @classmethod
    def from_npz(cls, path: str | Path, participant_names: list[str]) -> "BuyerSourcing":
        data = np.load(path, allow_pickle=False)
        origins = [str(o) for o in data["origins"]]
        order = [origins.index(n) if n in origins else None for n in participant_names]
        tables = {}
        for dest in participant_names:
            if f"{dest}/households" not in data:
                continue
            t = {}
            for key in ("firm_intermediate", "gfcf", "households", "government"):
                src = data[f"{dest}/{key}"]
                arr = np.full((len(participant_names),) + src.shape[1:], np.nan)
                for i, j in enumerate(order):
                    if j is not None:
                        arr[i] = src[j]
                t[key] = arr
            tables[dest] = t
        return cls(participant_names, tables)

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
                default_origin_tp: np.ndarray) -> None:
        """Store each buyer's origin multipliers for this clearing (origin_tp: price-adjusted)."""
        for c2, dest in enumerate(self.names):
            t = self.tables.get(dest)
            if t is None:
                continue
            tp, de = origin_tp[:, c2, :], default_origin_tp[:, c2, :]
            for transactor in goods_market_participants[dest]:
                kind = type(transactor).__name__
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
                    shares = self._apply_targets(shares, dest, "firms", industries)
                elif kind == "Households":
                    shares = self._apply_targets(t["households"], dest, "households", None)
                elif kind == "GovernmentEntities":
                    shares = self._apply_targets(t["government"], dest, "government", None)
                else:
                    transactor._buyer_origin_multiplier = None
                    continue
                transactor._buyer_origin_multiplier = self._multipliers(shares, tp, de)


def origin_multiplier(transactor, origin: Optional[int]):
    """Multiplier array for this buyer and origin (rows x goods, or goods), or 1.0."""
    if origin is None:
        return 1.0
    mult = getattr(transactor, "_buyer_origin_multiplier", None)
    if mult is None:
        return 1.0
    return mult[origin]
