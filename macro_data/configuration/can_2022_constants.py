"""Observed Canadian 2022 constants used by the CAN-2022 (13-region) build. Each value cites its source."""

# Household final consumption expenditure 2022, StatCan 36-10-0124 (sum of the four 2022 seasonally adjusted
# quarterly-rate values, current prices), $ CAD.
CAN_2022_HFCE_PAID_RENT = 81_506e6  # v1.1.1.17 "Paid rental fees for housing"
CAN_2022_HFCE_IMPUTED_RENT = 235_938e6  # v1.1.1.18 "Imputed rental fees for housing"

# Initial household loan terms, in model periods (quarters), CAN-2022 validated build (validation-2022, H6).
# Installments are principal / maturity at t0 (loan_data.py), so the maturity is set such that obligated principal
# repayments match StatCan 11-10-0065-01 (debt service indicators of households, 2022 mean of the four
# seasonally adjusted annual-rate quarters, $M): non-mortgage principal 60,172 -> 15,043/quarter; mortgage principal
# 58,695 -> 14,674/quarter. Stocks: 36-10-0580 households 2022Q4, consumer credit + non-mortgage loans
# 597,597 + 132,335 = 729,932; mortgages 2,126,996.
# The default (12 and 120 periods) implies 4.1x and 1.2x the observed principal flows.
CAN_2022_CONSUMER_LOAN_MATURITY_Q = round(729_932 / (60_172 / 4))  # = 49
CAN_2022_MORTGAGE_MATURITY_Q = round(2_126_996 / (58_695 / 4))  # = 145
