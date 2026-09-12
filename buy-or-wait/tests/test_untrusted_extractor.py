import pytest
from decimal import Decimal
from src.untrusted_extractor import UntrustedDataExtractor, ExtractedEventFact
from src.token_tracker import TokenUsageTracker


def test_extract_currency_from_text():
    extractor = UntrustedDataExtractor()
    info = extractor.extract_request_currency("req_1", "I want to purchase a laptop for USD 1200")
    assert info.currency == "USD"


def test_extract_currency_fallback_to_usd():
    extractor = UntrustedDataExtractor()
    info = extractor.extract_request_currency("req_2", "I need to pay 500 for rent")
    assert info.currency == "USD"


def test_extract_event_fact_from_text():
    extractor = UntrustedDataExtractor()
    text = "Confirmed expense update: amount is USD 250.00"
    fact = extractor.extract_event_fact_from_text("evt_100", "msg_10", text, "message")

    assert fact.event_id == "evt_100"
    assert fact.source_id == "msg_10"
    assert fact.amount == Decimal("250.00")
    assert fact.currency == "USD"


def test_extractor_logs_token_usage():
    tracker = TokenUsageTracker()
    extractor = UntrustedDataExtractor(tracker=tracker)
    extractor.extract_event_fact_from_text("evt_1", "msg_1", "Amount USD 100", "message")

    summary = tracker.get_summary()
    assert summary["total_calls"] == 1
    assert summary["total_tokens"] == 120