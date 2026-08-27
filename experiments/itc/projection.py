"""Shared projection/baseline utilities for the ITC working-paper scenarios.

Only genuinely shared, policy-neutral projection quantities live here: the
common 2026+ projection growth path and horizon. Policy-specific parameters
(ITC rate, active policy window, eligible goods/sectors) belong in the
individual scenario files, since they differ across scenarios.

The projection extends the frozen CAN-2022 candidate baseline (tag
pre-itc-validation-2026-08-22) over 2022-2035: quarters 0..PROJ_START-1 are
the 2022-2025 historical/near-term block (factor 1.0), and from PROJ_START
(2026Q1) the exogenous demand and labour paths grow at the annual rates below.
"""

import numpy as np

# Horizon and projection start (shared across all scenarios).
Q_LR = 55           # number of iterations: 2022Q1 (t=0) .. 2035Q4 (t=55)
PROJ_START = 16     # first projected quarter (2026Q1); t < PROJ_START is the 2022-2025 block

# Common projection growth rates (annual), applied from PROJ_START:
#   GC household consumption, GG government, GI household investment,
#   GL labour force, GX rest-of-world export demand.
GC = GG = GI = 0.02
GL = 0.01
GX = 0.02


def _qf(n, g):
    """Per-quarter multiplier on a level path: 1.0 through 2025, then compounding
    at annual rate `g` from PROJ_START. `n` is the path length in quarters.

    f[t] = 1.0                                      for t < PROJ_START
    f[t] = (1+g) ** ((t - (PROJ_START-1)) / 4.0)    for t >= PROJ_START
    """
    f = np.ones(n)
    for t in range(PROJ_START, n):
        f[t] = (1.0 + g) ** ((t - (PROJ_START - 1)) / 4.0)
    return f
