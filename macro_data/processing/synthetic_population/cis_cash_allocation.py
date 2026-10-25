"""CIS donor allocation weights; no income residual or per-decile payment."""
import numpy as np

def normalized_weights(values):
    x=np.maximum(0.,np.asarray(values,float));return x/x.sum() if x.sum()>0 else np.zeros_like(x)

def conserve_payroll(employee_households,firm_ids,employed,old_wages,old_effort,household_weights):
    """Reallocate each existing employer's net bill; preserve labour-input totals."""
    hh=np.asarray(employee_households,int);firms=np.asarray(firm_ids,float);employed=np.asarray(employed,bool)
    wages=np.zeros_like(np.asarray(old_wages,float));effort=np.asarray(old_effort,float).copy();fallback=[]
    count=np.bincount(hh[employed],minlength=len(household_weights))
    raw=np.divide(np.asarray(household_weights,float)[hh],count[hh],out=np.zeros(len(hh)),where=count[hh]>0)
    for fid in np.unique(firms[employed]):
        mask=employed&(firms==fid);weights=normalized_weights(raw[mask])
        if not weights.any():weights=normalized_weights(np.asarray(old_wages)[mask]);fallback.append(int(fid))
        if not weights.any():weights=np.full(mask.sum(),1/mask.sum());fallback.append(int(fid))
        wages[mask]=weights*np.asarray(old_wages)[mask].sum();effort[mask]=weights*np.asarray(old_effort)[mask].sum()
    return wages,effort,fallback
