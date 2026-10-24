"""Independent validation switches; all behavioural changes are opt-in."""
from pydantic import BaseModel, Field


class HouseholdClosureConfiguration(BaseModel):
    buffer_stock_enabled: bool = False
    buffer_stock_kappa: float = Field(default=.10,ge=0)
    buffer_stock_smoothing: float = Field(default=.25,gt=0,le=1)
    buffer_stock_reference: dict[str,list[float]] = {}
    prudent_firm_payout_enabled: bool = False
    firm_payment_default_enabled: bool = False
    firm_distress_periods: int = Field(default=3, ge=1)
    firm_collateral_haircut: float = Field(default=.20, ge=0, lt=1)
    distress_enabled: bool = False
    deposit_only_saving: bool = False
    overdraft_limit_enabled: bool = False
    financial_asset_drawdown: bool = False
    investment_benchmark_enabled: bool = False
    consumption_before_investment: bool = False
    # StatCan 36-10-0112 v62305994, 2022 mean SAAR, purchasers' prices.
    initial_annual_investment_benchmark: float = Field(default=242_393e6, gt=0)
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
    recalibrate_saving_with_d2: bool = True
    # StatCan 36-10-0112 v62305982, 2022 annual mean of quarterly SAAR.
    initial_annual_consumption_benchmark: float = Field(default=1_511_382e6, gt=0)
    nonrental_mixed_income: float = Field(default=97_274e6, ge=0)
    corporate_transfers: float = Field(default=121_500e6, ge=0)
    # StatCan 36-10-0482, 2022, Dividends (v80013659), CAD.
    dividends_by_region: dict[str, float] = {'CAN_NL': 363000000.0, 'CAN_PE': 194000000.0, 'CAN_NS': 1748000000.0, 'CAN_NB': 1033000000.0, 'CAN_QC': 14371000000.0, 'CAN_ON': 35090000000.0, 'CAN_MB': 1825000000.0, 'CAN_SK': 3246000000.0, 'CAN_AB': 16072000000.0, 'CAN_BC': 17949000000.0, 'CAN_YT': 98000000.0, 'CAN_NT': 52000000.0, 'CAN_NU': 11000000.0}

    @classmethod
    def cashflow_candidate(cls, distress=False):
        """Reviewed D-timing/D1 arms; all wider housing behavior stays off."""
        return cls(credit_enabled=True, income_enabled=True, recalibrate_saving_with_d2=True,
                   overdraft_limit_enabled=True, rent_offset_enabled=True, distress_enabled=distress)
