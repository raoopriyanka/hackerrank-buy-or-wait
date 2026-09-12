import pytest
from decimal import Decimal
from datetime import date, timedelta

from src.financial_state import FinancialState, ReconstructedEvent, ResolutionStatus, Provenance
from src.forecaster import FinancialForecaster, ForecastResult


@pytest.fixture
def sample_state():
    prov = Provenance(origin="csv", source_id="s1")
    return FinancialState(
        user_id="user_1",
        home_currency="USD",
        minimum_balance_to_keep=Decimal("500.00"),
        recurring_income=[
            ReconstructedEvent(
                event_id="inc1",
                user_id="user_1",
                event_date=date(2026, 7, 1),
                amount=Decimal("2000.00"),
                home_currency="USD",
                event_type="recurring_income",
                status="confirmed",
                flexible=False,
                resolution_status=ResolutionStatus.RESOLVED,
                provenance=prov,
            )
        ],
        recurring_expenses=[
            ReconstructedEvent(
                event_id="exp1",
                user_id="user_1",
                event_date=date(2026, 7, 15),
                amount=Decimal("1000.00"),
                home_currency="USD",
                event_type="recurring_expense",
                status="confirmed",
                flexible=True,
                resolution_status=ResolutionStatus.RESOLVED,
                provenance=prov,
            )
        ],
        one_time_events=[],
    )


def test_forecast_90_days_safe_scenario(sample_state):
    forecaster = FinancialForecaster(forecast_days=90)
    req_date = date(2026, 7, 1)
    initial_bal = Decimal("1000.00")

    result = forecaster.forecast_90_days(
        initial_balance=initial_bal,
        financial_state=sample_state,
        request_date=req_date,
    )

    assert len(result.daily_records) == 91
    assert result.is_entire_forecast_safe is True
    assert result.min_balance_reached >= Decimal("500.00")


def test_forecast_detects_minimum_balance_violation():
    prov = Provenance(origin="csv", source_id="s1")
    # State with NO income and an upcoming expense on July 15th
    state_no_income = FinancialState(
        user_id="user_1",
        home_currency="USD",
        minimum_balance_to_keep=Decimal("500.00"),
        recurring_income=[],
        recurring_expenses=[
            ReconstructedEvent(
                event_id="exp1",
                user_id="user_1",
                event_date=date(2026, 7, 15),
                amount=Decimal("300.00"),
                home_currency="USD",
                event_type="recurring_expense",
                status="confirmed",
                flexible=True,
                resolution_status=ResolutionStatus.RESOLVED,
                provenance=prov,
            )
        ],
        one_time_events=[],
    )

    forecaster = FinancialForecaster(forecast_days=90)
    req_date = date(2026, 7, 1)
    # Balance starts at 600. On 15th, 600 - 300 = 300 (< 500 min balance)
    initial_bal = Decimal("600.00")

    result = forecaster.forecast_90_days(
        initial_balance=initial_bal,
        financial_state=state_no_income,
        request_date=req_date,
    )

    assert result.is_entire_forecast_safe is False
    assert len(result.violating_dates) > 0
    assert date(2026, 7, 15) in result.violating_dates


def test_forecast_with_additional_candidate_payment(sample_state):
    forecaster = FinancialForecaster(forecast_days=90)
    req_date = date(2026, 7, 1)
    initial_bal = Decimal("3000.00")

    candidate_payments = {
        date(2026, 7, 5): Decimal("1500.00")
    }

    result = forecaster.forecast_90_days(
        initial_balance=initial_bal,
        financial_state=sample_state,
        request_date=req_date,
        additional_candidate_payments=candidate_payments,
    )

    day5_rec = [r for r in result.daily_records if r.sim_date == date(2026, 7, 5)][0]
    assert day5_rec.expense_total == Decimal("1500.00")