"""Read-only GDP valuation bridge, retaining an explicit statistical residual."""
import numpy as np


def gdp_bridge(cost_side_output,basic_intermediates,input_product_tax,compensation,gos_mixed,other_production_tax,final_product_tax,housing,expenditure):
    production=np.asarray(cost_side_output)-np.asarray(basic_intermediates)-np.asarray(input_product_tax)
    income=np.asarray(compensation)+np.asarray(gos_mixed)+np.asarray(other_production_tax)
    production_market=production+final_product_tax+housing
    income_market=income+final_product_tax+housing
    return dict(production_basic=production,income_basic=income,
        production_market=production_market,income_market=income_market,
        production_income_residual=production-income,
        expenditure_residual=np.asarray(expenditure)-production_market)
