"""Reallocate initial acquisition flows only; capital and financial stocks are inputs."""
import numpy as np

def observed_acquisitions(old_bundles,capital_stock,targets,prices):
    old=np.asarray(old_bundles,float);stock=np.asarray(capital_stock,float);target=np.asarray(targets,float);p=np.asarray(prices,float)
    if np.any(target<0) or np.any(p<=0):raise ValueError('Nonnegative GFCF and positive prices required')
    mix=np.maximum(0,old).copy();empty=mix.sum(axis=1)==0;mix[empty]=np.maximum(0,stock[empty])
    values=mix@p
    if np.any((target>1e-8)&(values<=0)):raise ValueError('Observed investment has no supported capital-good composition')
    return mix*np.divide(target,values,out=np.zeros_like(target),where=values>0)[:,None]
