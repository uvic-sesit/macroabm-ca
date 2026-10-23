"""Predeclared A gate; no tuning based on simulation outcomes."""
import numpy as np

BENCHMARK_SAVING = (1502.340 - 1511.382) / 1502.340


def asset_gate(quarter, constrained_share, saving_rate):
    quarter = np.asarray(quarter, int)
    share, saving = np.asarray(constrained_share, float), np.asarray(saving_rate, float)
    if not (quarter.shape == share.shape == saving.shape) or set(quarter) != set(range(1,13)) or len(quarter)!=12:
        raise ValueError('Gate requires one observation per quarter Q1-Q12')
    if not np.all(np.isfinite(share)) or not np.all(np.isfinite(saving)):
        raise ValueError('Non-finite gate data')
    mask = quarter >= 4
    slope = float(np.polyfit(quarter[mask], share[mask], 1)[0])
    q12 = float(saving[quarter==12][0])
    trend_pass = slope <= 0
    saving_pass = abs(q12-BENCHMARK_SAVING) <= .05
    return dict(constrained_slope_per_quarter=slope,
                constrained_Q4=float(share[quarter==4][0]), constrained_Q12=float(share[quarter==12][0]),
                Q12_saving_rate=q12, benchmark_saving_rate=BENCHMARK_SAVING,
                saving_gap_pp=100*(q12-BENCHMARK_SAVING),
                trend_pass=trend_pass, saving_pass=saving_pass, gate_pass=trend_pass and saving_pass)
