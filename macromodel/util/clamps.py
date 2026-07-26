"""Shared, inf-safe input clamp used by the firm planning rules.

Several planning rules clamp a production target toward an input-implied limit with a
configurable weight. The naive expression

    np.minimum(target, target + weight * (limit - target))

has a silent failure mode: a firm with no binding constraint has `limit = inf`, so at
`weight = 0.0` the term evaluates `0.0 * inf` -> NaN, `np.minimum` propagates the NaN,
and the callers' `fillna(..., value=0)` (firms.py:701, 732) rewrites it to **0** -- the
firm then plans zero inputs and stops producing. The failure is invisible except for a
RuntimeWarning, and it fires exactly when a weight is set to 0.0, i.e. during the
natural "remove this clamp" experiment.

`clamp_towards` is identical to the naive expression wherever `limit` is finite (at
every weight), and treats an infinite limit as "no constraint" (target unchanged) at
every weight, which is the intended semantics.
"""

from __future__ import annotations

import numpy as np


def clamp_towards(
    target: np.ndarray,
    limit: np.ndarray,
    weight: float,
) -> np.ndarray:
    """Blend `target` toward `limit` by `weight`, never raising `target`.

        result = min(target, target + weight * (limit - target))
               = min(target, (1-weight)*target + weight*limit)

    Args:
        target: production target to clamp.
        limit: input-implied production limit. `inf` means "no constraint".
        weight: 0.0 = ignore the limit, 1.0 = clamp fully to it.

    Returns:
        The clamped target, free of the 0 * inf -> NaN hazard.
    """
    target = np.asarray(target, dtype=float)
    limit = np.asarray(limit, dtype=float)
    finite = np.isfinite(limit)
    # np.where(finite, limit - target, 0.0) keeps the inf out of the multiply entirely,
    # so weight * (...) can never evaluate 0.0 * inf.
    adjusted = np.where(finite, target + weight * np.where(finite, limit - target, 0.0), target)
    return np.minimum(target, adjusted)
