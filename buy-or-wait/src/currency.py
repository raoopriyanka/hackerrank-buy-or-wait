from decimal import Decimal
from datetime import datetime, date
from typing import Dict, Tuple, List
from src.schemas import ExchangeRate


class MissingExchangeRateError(Exception):
    """Raised when an exchange rate for a specific date and currency pair is not found."""
    pass


class DuplicateExchangeRateError(Exception):
    """Raised when duplicate rate records exist for the same (date, from_currency, to_currency)."""
    pass


class InvalidDateError(Exception):
    """Raised when a date string cannot be parsed."""
    pass


def parse_iso_date(date_str: str) -> date:
    """Parses ISO format date strings (YYYY-MM-DD)."""
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError) as e:
        raise InvalidDateError(f"Invalid ISO date string: '{date_str}'") from e


class CurrencyConverter:
    """Strict lookup-table currency converter with unrounded Decimal precision."""

    def __init__(self, rates: List[ExchangeRate]):
        self._rate_table: Dict[Tuple[str, str, str], Decimal] = {}
        for r in rates:
            key = (r.rate_date.strip(), r.from_currency.strip().upper(), r.to_currency.strip().upper())
            if key in self._rate_table:
                raise DuplicateExchangeRateError(
                    f"Duplicate exchange rate found for key {key}"
                )
            self._rate_table[key] = r.exchange_rate if isinstance(r.exchange_rate, Decimal) else Decimal(str(r.exchange_rate))

    def convert(self, amount: float | Decimal, from_curr: str, to_curr: str, rate_date: str) -> Decimal:
        """
        Converts monetary amount between currencies on a specific date without premature rounding.
        """
        from_c = from_curr.strip().upper()
        to_c = to_curr.strip().upper()
        date_s = rate_date.strip()

        parse_iso_date(date_s)

        amt_decimal = amount if isinstance(amount, Decimal) else Decimal(str(amount))

        if from_c == to_c:
            return amt_decimal

        key = (date_s, from_c, to_c)
        if key not in self._rate_table:
            raise MissingExchangeRateError(
                f"No exchange rate found for {from_c} -> {to_c} on date {date_s}"
            )

        rate = self._rate_table[key]
        return amt_decimal * rate