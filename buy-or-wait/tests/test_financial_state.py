import pytest
from decimal import Decimal
from datetime import date

from src.schemas import FinancialProfile, FinancialEvent, ExchangeRate
from src.currency import CurrencyConverter
from src.untrusted_extractor import ExtractedEventFact
from src.financial_state import (
    FinancialStateReconstructor,
    ResolutionStatus,
    ReconstructedEvent,
)


@pytest.fixture
def sample_profile():
    return FinancialProfile(
        user_id="user_1",
        home_currency="USD",
        minimum_balance_to_keep=500.0,
        payment_methods_user_will_consider="full_payment,installments",
    )


@pytest.fixture
def converter():
    rates = [
        ExchangeRate(rate_date="2026-07-05", from_currency="EUR", to_currency="USD", exchange_rate=Decimal("1.10")),
        ExchangeRate(rate_date="2026-07-05", from_currency="ZAR", to_currency="USD", exchange_rate=Decimal("0.05")),
    ]
    return CurrencyConverter(rates)


def test_status_filtering_inclusions_exclusions(sample_profile, converter):
    reconstructor = FinancialStateReconstructor(converter)
    events = [
        FinancialEvent("e1", "user_1", "2026-07-05", 1000.0, "USD", "recurring_income", "confirmed", False),
        FinancialEvent("e2", "user_1", "2026-07-05", 200.0, "USD", "one_time_expense", "cancelled", False),
        FinancialEvent("e3", "user_1", "2026-07-05", 50.0, "USD", "one_time_expense", "failed", False),
        FinancialEvent("e4", "user_1", "2026-07-05", 500.0, "USD", "pending_credit", "pending", False),
    ]

    state = reconstructor.reconstruct_user_state(sample_profile, events)
    assert len(state.recurring_income) == 1
    assert state.recurring_income[0].event_id == "e1"
    assert len(state.one_time_events) == 0  # Cancelled and failed events ignored


def test_blank_amount_resolved_via_extracted_fact(sample_profile, converter):
    reconstructor = FinancialStateReconstructor(converter)
    events = [
        FinancialEvent("e_blank", "user_1", "2026-07-05", None, "USD", "one_time_expense", "confirmed", False)
    ]
    facts = [
        ExtractedEventFact(
            event_id="e_blank",
            amount=Decimal("150.00"),
            currency="USD",
            status_update=None,
            provenance_source_id="msg_42",
            provenance_type="message",
            confidence=0.95,
            raw_source_text="Receipt amount USD 150.00",
        )
    ]

    state = reconstructor.reconstruct_user_state(sample_profile, events, extracted_facts=facts)
    assert len(state.one_time_events) == 1
    ev = state.one_time_events[0]
    assert ev.resolution_status == ResolutionStatus.RESOLVED
    assert ev.amount == Decimal("150.00")
    assert ev.provenance.origin == "message"
    assert ev.provenance.source_id == "msg_42"


def test_blank_amount_without_fact_is_unresolved(sample_profile, converter):
    reconstructor = FinancialStateReconstructor(converter)
    events = [
        FinancialEvent("e_blank2", "user_1", "2026-07-05", None, "USD", "one_time_expense", "confirmed", False)
    ]

    state = reconstructor.reconstruct_user_state(sample_profile, events)
    assert len(state.unresolved_events) == 1
    ev = state.unresolved_events[0]
    assert ev.resolution_status == ResolutionStatus.UNRESOLVED


def test_currency_conversion_at_event_date(sample_profile, converter):
    reconstructor = FinancialStateReconstructor(converter)
    events = [
        FinancialEvent("e_eur", "user_1", "2026-07-05", 100.0, "EUR", "recurring_expense", "confirmed", True)
    ]

    state = reconstructor.reconstruct_user_state(sample_profile, events)
    assert len(state.recurring_expenses) == 1
    ev = state.recurring_expenses[0]
    # 100 EUR * 1.10 = 110.00 USD
    assert ev.amount == Decimal("110.00")
    assert ev.provenance.is_converted is True
    assert ev.provenance.original_currency == "EUR"


def test_deduplication_exact_rows(sample_profile, converter):
    reconstructor = FinancialStateReconstructor(converter)
    dup_event = FinancialEvent("e1", "user_1", "2026-07-05", 100.0, "USD", "recurring_expense", "confirmed", True)
    events = [dup_event, dup_event]

    state = reconstructor.reconstruct_user_state(sample_profile, events)
    assert len(state.recurring_expenses) == 1


def test_conflict_resolution_settled_over_estimate(sample_profile, converter):
    reconstructor = FinancialStateReconstructor(converter)
    events = [
        FinancialEvent("e1", "user_1", "2026-07-05", 200.0, "USD", "one_time_expense", "estimated", False),
        FinancialEvent("e1", "user_1", "2026-07-05", 180.0, "USD", "one_time_expense", "settled", False),
    ]

    state = reconstructor.reconstruct_user_state(sample_profile, events)
    assert len(state.one_time_events) == 1
    assert state.one_time_events[0].amount == Decimal("180.0")
    assert state.one_time_events[0].status == "settled"


def test_deterministic_repeatability(sample_profile, converter):
    reconstructor = FinancialStateReconstructor(converter)
    events = [
        FinancialEvent("e1", "user_1", "2026-07-05", 100.0, "USD", "recurring_income", "confirmed", False),
        FinancialEvent("e2", "user_1", "2026-07-05", 50.0, "USD", "recurring_expense", "confirmed", True),
    ]

    state1 = reconstructor.reconstruct_user_state(sample_profile, events)
    state2 = reconstructor.reconstruct_user_state(sample_profile, events)

    assert state1 == state2