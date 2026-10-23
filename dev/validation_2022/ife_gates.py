"""Revised IFE gates; benchmark initial investment independently of outcomes."""
import math


def investment_gate(realised, target=242393e6/4):
    realised,target=float(realised),float(target)
    if not math.isfinite(realised) or not math.isfinite(target) or target<=0:
        raise ValueError('Gate needs finite investment and a positive target')
    return dict(Q1_investment=realised,quarterly_benchmark=target,
        gap_pct=100*(realised/target-1),gate1_pass=bool(.9*target<=realised<=1.1*target))
