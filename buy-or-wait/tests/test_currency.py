import pytest
from decimal import Decimal
from src.schemas import ExchangeRate
from src.currency import (
    CurrencyConverter,
    MissingExchangeRateError,
    DuplicateExchangeRateError,
    InvalidDateError,
    parse_iso_date,
)


@pytest.fixture
def sample_rates():
    return [
        ExchangeRate(rate_date="2026-07-05", from_currency="ZAR", to_currency="USD", exchange_rate=Decimal("0.054")),
        ExchangeRate(rate_date="2026-07-05", from_currency="EUR", to_currency="USD", exchange_rate=Decimal("1.08")),
        ExchangeRate(rate_date="2025-08-03", from_currency="IDR", to_currency="USD", exchange_rate=Decimal("0.000065")),
    ]


def test_parse_iso_date_valid():
    parsed = parse_iso_date("2026-07-05")
    assert parsed.year == 2026
    assert parsed.month == 7
    assert parsed.day == 5


def test_parse_iso_date_invalid():
    with pytest.raises(InvalidDateError):
        parse_iso_date("05/07/2026")


def test_same_currency_conversion(sample_rates):
    converter = CurrencyConverter(sample_rates)
    result = converter.convert(100.50, "USD", "USD", "2026-07-05")
    assert result == Decimal("100.50")


def test_valid_cross_currency_conversion(sample_rates):
    converter = CurrencyConverter(sample_rates)
    result = converter.convert(1000.0, "ZAR", "USD", "2026-07-05")
    assert result == Decimal("54.000")


def test_exact_rate_date_lookup(sample_rates):
    converter = CurrencyConverter(sample_rates)
    res1 = converter.convert(100.0, "EUR", "USD", "2026-07-05")
    assert res1 == Decimal("108.00")

    with pytest.raises(MissingExchangeRateError):
        converter.convert(100.0, "EUR", "USD", "2026-07-06")


def test_invalid_currency_pair(sample_rates):
    converter = CurrencyConverter(sample_rates)
    with pytest.raises(MissingExchangeRateError):
        converter.convert(100.0, "GBP", "USD", "2026-07-05")


def test_duplicate_exchange_rate_raises_error():
    rates_with_dup = [
        ExchangeRate(rate_date="2026-07-05", from_currency="ZAR", to_currency="USD", exchange_rate=Decimal("0.054")),
        ExchangeRate(rate_date="2026-07-05", from_currency="ZAR", to_currency="USD", exchange_rate=Decimal("0.055")),
    ]
    with pytest.raises(DuplicateExchangeRateError, match="Duplicate exchange rate"):
        CurrencyConverter(rates_with_dup)


def test_unrounded_decimal_precision(sample_rates):
    converter = CurrencyConverter(sample_rates)
    result = converter.convert(15656000.0, "IDR", "USD", "2025-08-03")
    assert isinstance(result, Decimal)
    assert result == Decimal("1017.640000")