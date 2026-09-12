import pytest
from decimal import Decimal
from datetime import date
from src.candidate_plan import CandidatePlan, PaymentScheduleItem
from src.token_tracker import TokenUsageTracker
from src.explanation_generator import ExplanationGenerator


@pytest.fixture
def sample_plan():
    return CandidatePlan(
        method="full_payment",
        payment_option_id=None,
        schedule=[PaymentScheduleItem(payment_date=date(2026, 7, 1), amount=Decimal("100.00"))],
        total_amount_paid=Decimal("100.00"),
        amount_safe_to_pay=Decimal("100.00"),
        earliest_date_for_full_payment=date(2026, 7, 1),
        spending_changes_needed=[],
    )


def test_fallback_explanation_affordable_now(sample_plan):
    generator = ExplanationGenerator()
    explanation = generator.generate_explanation(
        request_id="req_1",
        affordability_status="affordable_now",
        winning_plan=sample_plan,
        requested_amount=Decimal("100.00"),
        home_currency="USD",
    )

    assert "affordable immediately" in explanation
    assert "USD 100.00" in explanation


def test_fallback_explanation_not_affordable(sample_plan):
    generator = ExplanationGenerator()
    not_rec_plan = CandidatePlan(
        method="not_recommended",
        payment_option_id=None,
        schedule=[],
        total_amount_paid=Decimal("0.0"),
        amount_safe_to_pay=Decimal("0.0"),
        earliest_date_for_full_payment=None,
        spending_changes_needed=[],
    )

    explanation = generator.generate_explanation(
        request_id="req_2",
        affordability_status="not_affordable",
        winning_plan=not_rec_plan,
        requested_amount=Decimal("500.00"),
        home_currency="USD",
    )

    assert "not recommended" in explanation
    assert "minimum balance floor" in explanation


class MockLLMClient:
    def generate(self, system: str, prompt: str) -> str:
        return "The request is fully affordable today based on cash flow projections."


def test_llm_explanation_generation_and_token_tracking(sample_plan):
    tracker = TokenUsageTracker()
    mock_llm = MockLLMClient()
    generator = ExplanationGenerator(tracker=tracker, llm_client=mock_llm)

    explanation = generator.generate_explanation(
        request_id="req_3",
        affordability_status="affordable_now",
        winning_plan=sample_plan,
        requested_amount=Decimal("100.00"),
        home_currency="USD",
    )

    assert explanation == "The request is fully affordable today based on cash flow projections."
    summary = tracker.get_summary()
    assert summary["total_calls"] == 1
    assert summary["total_tokens"] == 190