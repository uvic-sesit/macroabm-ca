"""Predeclared user gates in percentage-point/fraction units, no tuning."""
import numpy as np


def assess(zero_shares,slope_pp,q12_saving_pct,q1_C,C_target,quintile_relative_deviation,q12_C,q12_GDP,ref_C,ref_GDP,error):
    finite=all(np.isfinite(np.asarray(x)).all() for x in [zero_shares,slope_pp,q12_saving_pct,q1_C,C_target,
        quintile_relative_deviation,q12_C,q12_GDP,ref_C,ref_GDP,error])
    g=dict(accounting=bool(finite and error<=1e-8),G1=bool(finite and np.max(zero_shares)<.02),
        G2=bool(finite and slope_pp<=.25 and abs(q12_saving_pct+.6)<=5 and q1_C>=.95*C_target),
        G3=bool(finite and np.max(np.abs(quintile_relative_deviation))<=.15),
        G4=bool(finite and abs(q12_C/ref_C-1)<=.05 and abs(q12_GDP/ref_GDP-1)<=.05))
    g['pass_all']=all(g.values());return g
