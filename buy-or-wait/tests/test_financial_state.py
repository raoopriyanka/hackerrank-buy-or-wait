import pytest
from decimal import Decimal
from datetime import date
from src.schemas import FinancialProfile, FinancialEvent
from src.currency import CurrencyConverter
from src.financial_state import FinancialStateReconstructor, ResolutionStatus
from src.untrusted_extractor import ExtractedEventFact


@pytest.fixture
def sample_profile():
    return FinancialProfile(
        user_id="user_1",
        home_currency="USD",
        current_available_balance=5000.0,
        minimum_balance_to_keep=500.0,
        payment_methods_user_will_consider="full_payment,installments",
    )


@pytest.fixture
def empty_converter():
    return CurrencyConverter(rates=[])


def test_status_filtering_inclusions_exclusions(sample_profile, empty_converter):
    reconstructor = FinancialStateReconstructor(empty_converter)
    events = [
        FinancialEvent("e1", "user_1", "2026-07-01", 100.0, "USD", "recurring_expense", "confirmed", False),
        FinancialEvent("e2", "user_1", "2026-07-02", 50.0, "USD", "recurring_expense", "settled", False),
        FinancialEvent("e3", "user_1", "2026-07-03", 200.0, "USD", "recurring_expense", "pending", False),
        FinancialEvent("e4", "user_1", "2026-07-04", 300.0, "USD", "recurring_expense", "cancelled", False),
    ]

    state = reconstructor.reconstruct_user_state(
        profile=sample_profile,
        events=events,
        extracted_facts=[],
    )

    event_ids = [e.event_id for e in state.recurring_expenses]
    assert "e1" in event_ids
    assert "e2" in event_ids
    assert "e3" in event_ids
    assert "e4" not in event_ids


def test_blank_amount_resolved_via_extracted_fact(sample_profile, empty_converter):
    reconstructor = FinancialStateReconstructor(empty_converter)
    events = [
        FinancialEvent("e1", "user_1", "2026-07-01", None, "USD", "recurring_expense", "confirmed", False),
    ]
    facts = [
        ExtractedEventFact(
            event_id="e1",
            source_id="msg_1",
            amount=Decimal("150.00"),
            currency="USD",
            status_update=None,
            confidence=0.95,
            provenance_type="message",
            provenance_source_id="msg_1",
            raw_source_text="Expense amount USD 150",
        ),
    ]

    state = reconstructor.reconstruct_user_state(
        profile=sample_profile,
        events=events,
        extracted_facts=facts,
    )

    assert len(state.recurring_expenses) == 1
    assert state.recurring_expenses[0].amount == Decimal("150.00")
    assert state.recurring_expenses[0].resolution_status == ResolutionStatus.RESOLVED


def test_blank_amount_without_fact_is_unresolved(sample_profile, empty_converter):
    reconstructor = FinancialStateReconstructor(empty_converter)
    events = [
        FinancialEvent("e1", "user_1", "2026-07-01", None, "USD", "recurring_expense", "confirmed", False),
    ]

    state = reconstructor.reconstruct_user_state(
        profile=sample_profile,
        events=events,
        extracted_facts=[],
    )

    assert len(state.recurring_expenses) == 0
    assert len(state.unresolved_events) == 1
    assert state.unresolved_events[0].event_id == "e1"


def test_currency_conversion_at_event_date(sample_profile):
    from src.schemas import ExchangeRate
    rates = [
        ExchangeRate("2026-07-01", "EUR", "USD", Decimal("1.10")),
    ]
    converter = CurrencyConverter(rates=rates)
    reconstructor = FinancialStateReconstructor(converter)

    events = [
        FinancialEvent("e1", "user_1", "2026-07-01", 100.0, "EUR", "recurring_expense", "confirmed", False),
    ]

    state = reconstructor.reconstruct_user_state(
        profile=sample_profile,
        events=events,
        extracted_facts=[],
    )

    assert len(state.recurring_expenses) == 1
    assert state.recurring_expenses[0].amount == Decimal("110.00")
    assert state.recurring_expenses[0].home_currency == "USD"


def test_deduplication_exact_rows(sample_profile, empty_converter):
    reconstructor = FinancialStateReconstructor(empty_converter)
    events = [
        FinancialEvent("e1", "user_1", "2026-07-01", 100.0, "USD", "recurring_expense", "confirmed", False),
        FinancialEvent("e1", "user_1", "2026-07-01", 100.0, "USD", "recurring_expense", "confirmed", False),
    ]

    state = reconstructor.reconstruct_user_state(
        profile=sample_profile,
        events=events,
        extracted_facts=[],
    )

    assert len(state.recurring_expenses) == 1


def test_conflict_resolution_settled_over_estimate(sample_profile, empty_converter):
    reconstructor = FinancialStateReconstructor(empty_converter)
    events = [
        FinancialEvent("e1", "user_1", "2026-07-01", 100.0, "USD", "recurring_expense", "estimated", False),
        FinancialEvent("e1", "user_1", "2026-07-01", 120.0, "USD", "recurring_expense", "settled", False),
    ]

    state = reconstructor.reconstruct_user_state(
        profile=sample_profile,
        events=events,
        extracted_facts=[],
    )

    assert len(state.recurring_expenses) == 1
    assert state.recurring_expenses[0].amount == Decimal("120.00")


def test_deterministic_repeatability(sample_profile, empty_converter):
    reconstructor = FinancialStateReconstructor(empty_converter)
    events = [
        FinancialEvent("e1", "user_1", "2026-07-01", 100.0, "USD", "recurring_expense", "confirmed", False),
        FinancialEvent("e2", "user_1", "2026-07-05", 200.0, "USD", "recurring_income", "confirmed", False),
    ]

    state1 = reconstructor.reconstruct_user_state(sample_profile, events, [])
    state2 = reconstructor.reconstruct_user_state(sample_profile, events, [])

    assert state1 == state2