import pytest
from decimal import Decimal
from datetime import date

from src.schemas import RequestRecord, FinancialProfile
from src.financial_state import FinancialState, ReconstructedEvent, ResolutionStatus, Provenance
from src.candidate_plan import CandidatePlan, PaymentScheduleItem
from src.forecaster import FinancialForecaster
from src.ranker import PlanRanker


@pytest.fixture
def sample_request():
    return RequestRecord(
        request_id="req_200",
        user_id="user_1",
        request_date="2026-07-01",
        request_type="purchase",
        requested_amount=500.0,
        desired_completion_date="2026-07-20",
        allows_partial_payment=True,
        request_text="Purchase item USD 500",
    )


@pytest.fixture
def sample_state():
    prov = Provenance(origin="csv", source_id="s1")
    return FinancialState(
        user_id="user_1",
        home_currency="USD",
        minimum_balance_to_keep=Decimal("500.00"),
        recurring_income=[],
        recurring_expenses=[],
        one_time_events=[],
    )


def test_select_best_plan_affordable_now(sample_request, sample_state):
    ranker = PlanRanker()
    req_date = date(2026, 7, 1)

    plan_full = CandidatePlan(
        method="full_payment",
        payment_option_id=None,
        schedule=[PaymentScheduleItem(payment_date=req_date, amount=Decimal("500.00"))],
        total_amount_paid=Decimal("500.00"),
        amount_safe_to_pay=Decimal("500.00"),
        earliest_date_for_full_payment=req_date,
        spending_changes_needed=[],
    )

    best_plan, status = ranker.select_best_plan(
        request=sample_request,
        initial_balance=Decimal("2000.00"),
        financial_state=sample_state,
        candidates=[plan_full],
    )

    assert best_plan.method == "full_payment"
    assert status == "affordable_now"


def test_ranking_prefers_no_spending_changes(sample_request, sample_state):
    ranker = PlanRanker()
    req_date = date(2026, 7, 1)

    plan_with_change = CandidatePlan(
        method="full_payment",
        payment_option_id=None,
        schedule=[PaymentScheduleItem(payment_date=req_date, amount=Decimal("500.00"))],
        total_amount_paid=Decimal("500.00"),
        amount_safe_to_pay=Decimal("500.00"),
        earliest_date_for_full_payment=req_date,
        spending_changes_needed=["stop:evt_1"],
    )

    plan_no_change = CandidatePlan(
        method="full_payment",
        payment_option_id=None,
        schedule=[PaymentScheduleItem(payment_date=req_date, amount=Decimal("500.00"))],
        total_amount_paid=Decimal("500.00"),
        amount_safe_to_pay=Decimal("500.00"),
        earliest_date_for_full_payment=req_date,
        spending_changes_needed=[],
    )

    best_plan, status = ranker.select_best_plan(
        request=sample_request,
        initial_balance=Decimal("2000.00"),
        financial_state=sample_state,
        candidates=[plan_with_change, plan_no_change],
    )

    assert best_plan.spending_changes_needed == []
    assert status == "affordable_now"


def test_fallback_when_no_candidate_safe(sample_request, sample_state):
    ranker = PlanRanker()
    req_date = date(2026, 7, 1)

    plan_unaffordable = CandidatePlan(
        method="full_payment",
        payment_option_id=None,
        schedule=[PaymentScheduleItem(payment_date=req_date, amount=Decimal("500.00"))],
        total_amount_paid=Decimal("500.00"),
        amount_safe_to_pay=Decimal("500.00"),
        earliest_date_for_full_payment=req_date,
        spending_changes_needed=[],
    )

    # Initial balance below minimum balance floor
    best_plan, status = ranker.select_best_plan(
        request=sample_request,
        initial_balance=Decimal("100.00"),
        financial_state=sample_state,
        candidates=[plan_unaffordable],
    )

    assert best_plan.method == "not_recommended"
    assert status == "not_affordable"