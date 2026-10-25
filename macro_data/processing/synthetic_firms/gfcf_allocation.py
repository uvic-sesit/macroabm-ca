"""Budget-preserving allocation of an observed IO fixed-capital product basket."""
import numpy as np


def allocate_product_budget(product_totals, investor_weights):
    product=np.asarray(product_totals,float);weights=np.asarray(investor_weights,float)
    if np.any(product < 0) or np.any(weights < 0) or not np.isfinite(product).all() or not np.isfinite(weights).all():
        raise ValueError('Finite nonnegative fixed-capital budgets and shares required')
    if product.sum()>0 and weights.sum()<=0:
        raise ValueError('Positive observed budget without an investing industry')
    return np.outer(weights/weights.sum(),product) if weights.sum() else np.zeros((len(weights),len(product)))
