"""Independent validation switches; all behavioural changes are opt-in."""
from pydantic import BaseModel, Field


class HouseholdClosureConfiguration(BaseModel):
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
