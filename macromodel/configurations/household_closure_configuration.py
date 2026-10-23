"""Independent validation switches; all behavioural changes are opt-in."""
from pydantic import BaseModel, Field


class HouseholdClosureConfiguration(BaseModel):
    distress_enabled: bool = False
    deposit_only_saving: bool = False
    distress_periods: int = Field(default=3, ge=1)
    collateral_haircut: float = Field(default=.20, ge=0, lt=1)
    rent_offset_enabled: bool = False
    credit_enabled: bool = False
    periods_per_year: int = Field(default=4, ge=1)
    consumer_total_debt_to_annual_income: float = Field(default=4.5, ge=0)
    mortgage_total_debt_to_annual_income: float = Field(default=4.5, ge=0)
    # Uninsured-only origination proxy: no mortgage insurer or premiums exist.
    # Existing insured/high-LTV stock survives. 4.5 is a scenario assumption;
    # OSFI's 2025 portfolio measure is not a 2022 individual underwriting cap.
    mortgage_ltv: float = Field(default=.80, ge=0, lt=1)
    debt_service_to_disposable_income: float = Field(default=.40, ge=0, le=1)
    # Effective straight-line amortization terms match the initial stock's
    # debt / quarterly principal flow, not legal contract maturities.
    new_consumer_loan_maturity: int = Field(default=49, ge=1)
    new_mortgage_maturity: int = Field(default=145, ge=1)

    income_enabled: bool = False
    nonrental_mixed_income: float = Field(default=97_274e6, ge=0)
    corporate_transfers: float = Field(default=121_500e6, ge=0)
    # StatCan 36-10-0482, 2022, Dividends (v80013659), CAD.
    dividends_by_region: dict[str, float] = {'CAN_NL': 363000000.0, 'CAN_PE': 194000000.0, 'CAN_NS': 1748000000.0, 'CAN_NB': 1033000000.0, 'CAN_QC': 14371000000.0, 'CAN_ON': 35090000000.0, 'CAN_MB': 1825000000.0, 'CAN_SK': 3246000000.0, 'CAN_AB': 16072000000.0, 'CAN_BC': 17949000000.0, 'CAN_YT': 98000000.0, 'CAN_NT': 52000000.0, 'CAN_NU': 11000000.0}
