import pytest
from decimal import Decimal
from datetime import date

from src.schemas import RequestRecord, FinancialProfile, RequestPaymentOption
from src.financial_state import FinancialState, ReconstructedEvent, ResolutionStatus, Provenance
from src.candidate_plan import CandidatePlan
from src.plan_generator import CandidatePlanGenerator


@pytest.fixture
def sample_request():
    return RequestRecord(
        request_id="req_100",
        user_id="user_1",
        request_date="2026-07-01",
        request_type="purchase",
        requested_amount=1000.0,
        desired_completion_date="2026-07-15",
        allows_partial_payment=True,
        request_text="Buy item USD 1000",
    )


@pytest.fixture
def sample_profile():
    return FinancialProfile(
        user_id="user_1",
        home_currency="USD",
        minimum_balance_to_keep=500.0,
        payment_methods_user_will_consider="full_payment,partial_payment,installments,wait",
    )


@pytest.fixture
def sample_state():
    prov = Provenance(origin="csv", source_id="s1")
    return FinancialState(
        user_id="user_1",
        home_currency="USD",
        minimum_balance_to_keep=Decimal("500.00"),
        recurring_expenses=[
            ReconstructedEvent(
                event_id="flex_1",
                user_id="user_1",
                event_date=date(2026, 7, 5),
                amount=Decimal("100.00"),
                home_currency="USD",
                event_type="recurring_expense",
                status="confirmed",
                flexible=True,
                resolution_status=ResolutionStatus.RESOLVED,
                provenance=prov,
            )
        ],
    )


def test_generate_full_payment_and_wait_candidates(sample_request, sample_profile, sample_state):
    generator = CandidatePlanGenerator()
    plans = generator.generate_candidate_plans(
        request=sample_request,
        profile=sample_profile,
        financial_state=sample_state,
        options=[],
        home_requested_amount=Decimal("1000.00"),
    )

    methods = {p.method for p in plans}
    assert "full_payment" in methods
    assert "partial_payment" in methods
    assert "wait" in methods
    assert "not_recommended" in methods


def test_installment_candidate_from_options(sample_request, sample_profile, sample_state):
    generator = CandidatePlanGenerator()
    opt = RequestPaymentOption(
        request_id="req_100",
        payment_option_id="opt_1",
        method="installments",
        number_of_payments=3,
        installment_fee=30.0,
        plan_details="3 monthly payments",
    )

    plans = generator.generate_candidate_plans(
        request=sample_request,
        profile=sample_profile,
        financial_state=sample_state,
        options=[opt],
        home_requested_amount=Decimal("1000.00"),
    )

    inst_plans = [p for p in plans if p.method == "installments"]
    assert len(inst_plans) > 0
    assert inst_plans[0].payment_option_id == "opt_1"
    assert inst_plans[0].total_amount_paid == Decimal("1030.00")