"""Predeclared F and household checks; no outcome-driven calibration."""
import numpy as np


def constrained_slope(shares):
    y=np.asarray(shares,dtype=float)
    if y.shape!=(12,) or not np.isfinite(y).all():
        raise ValueError('Twelve finite quarterly shares required')
    x=np.arange(4,13,dtype=float);x-=x.mean()
    return float(np.dot(x,y[3:]-y[3:].mean())/np.dot(x,x))


def firm_gate(error,loss,baseline_loss):
    # "Material" is reported as at least 25% lower, predeclared before 12Q
    # outcomes. This assessment threshold does not enter simulation behaviour.
    return bool(error<=1e-8 and baseline_loss>0 and loss<=.75*baseline_loss)


def planned_investment_gate(initial_planned,target=242393e6/4):
    return bool(np.isfinite(initial_planned) and .9*target<=initial_planned<=1.1*target)
