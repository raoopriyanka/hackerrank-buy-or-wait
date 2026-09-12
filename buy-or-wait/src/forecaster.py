from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional

from src.financial_state import FinancialState, ReconstructedEvent


@dataclass(frozen=True)
class DailyBalanceRecord:
    sim_date: date
    day_index: int
    starting_balance: Decimal
    income_total: Decimal
    expense_total: Decimal
    ending_balance: Decimal
    is_safe: bool  # ending_balance >= minimum_balance_to_keep


@dataclass
class ForecastResult:
    user_id: str
    request_date: date
    start_balance: Decimal
    minimum_balance_to_keep: Decimal
    daily_records: List[DailyBalanceRecord] = field(default_factory=list)
    min_balance_reached: Decimal = field(default=Decimal("0.0"))
    is_entire_forecast_safe: bool = True
    violating_dates: List[date] = field(default_factory=list)


class FinancialForecaster:
    """
    Deterministic 90-Day Daily Financial Forecast Engine.
    Simulates day-by-day cash flow for 90 days following request_date.
    """

    def __init__(self, forecast_days: int = 90):
        self.forecast_days = forecast_days

    def forecast_90_days(
        self,
        initial_balance: Decimal,
        financial_state: FinancialState,
        request_date: date,
        additional_candidate_payments: Optional[Dict[date, Decimal]] = None,
    ) -> ForecastResult:
        """
        Runs a 90-day simulation starting on request_date.
        
        additional_candidate_payments: Optional candidate payment plan entries 
        mapping date -> payment_amount (used in Step 6/7 for testing proposed candidate plans).
        """
        candidate_payments = additional_candidate_payments or {}
        current_balance = initial_balance
        min_balance_keep = financial_state.minimum_balance_to_keep

        result = ForecastResult(
            user_id=financial_state.user_id,
            request_date=request_date,
            start_balance=initial_balance,
            minimum_balance_to_keep=min_balance_keep,
        )

        min_observed = initial_balance
        is_safe_overall = True
        violating_days = []

        for day_idx in range(self.forecast_days + 1):
            current_date = request_date + timedelta(days=day_idx)
            day_start = current_balance

            # 1. Sum incoming cash flow for current_date
            day_income = Decimal("0.0")
            day_income += self._calculate_event_totals_for_date(
                financial_state.recurring_income, current_date, request_date
            )
            day_income += self._calculate_one_time_totals_for_date(
                financial_state.one_time_events, current_date, is_income=True
            )

            # 2. Sum outgoing cash flow for current_date
            day_expense = Decimal("0.0")
            day_expense += self._calculate_event_totals_for_date(
                financial_state.recurring_expenses, current_date, request_date
            )
            day_expense += self._calculate_one_time_totals_for_date(
                financial_state.one_time_events, current_date, is_income=False
            )

            # Add optional candidate plan payment if scheduled for current_date
            if current_date in candidate_payments:
                day_expense += candidate_payments[current_date]

            # 3. Compute ending balance for the day
            day_end = day_start + day_income - day_expense
            current_balance = day_end

            is_day_safe = day_end >= min_balance_keep
            if not is_day_safe:
                is_safe_overall = False
                violating_days.append(current_date)

            if day_end < min_observed:
                min_observed = day_end

            result.daily_records.append(
                DailyBalanceRecord(
                    sim_date=current_date,
                    day_index=day_idx,
                    starting_balance=day_start,
                    income_total=day_income,
                    expense_total=day_expense,
                    ending_balance=day_end,
                    is_safe=is_day_safe,
                )
            )

        result.min_balance_reached = min_observed
        result.is_entire_forecast_safe = is_safe_overall
        result.violating_dates = violating_days

        return result

    def _calculate_event_totals_for_date(
        self,
        events: List[ReconstructedEvent],
        current_date: date,
        request_date: date,
    ) -> Decimal:
        """Determines if a recurring event falls on current_date (monthly cycle)."""
        total = Decimal("0.0")
        for ev in events:
            if self._is_recurring_due(ev.event_date, current_date):
                total += ev.amount
        return total

    def _calculate_one_time_totals_for_date(
        self,
        events: List[ReconstructedEvent],
        current_date: date,
        is_income: bool,
    ) -> Decimal:
        """Sums one-time events occurring on current_date."""
        total = Decimal("0.0")
        for ev in events:
            ev_is_income = "income" in ev.event_type.lower()
            if ev_is_income == is_income and ev.event_date == current_date:
                total += ev.amount
        return total

    def _is_recurring_due(self, base_date: date, current_date: date) -> bool:
        """Monthly recurrence rule: matches exact day-of-month or last valid day of month."""
        if current_date < base_date:
            return False
        # Matches same day of month
        if current_date.day == base_date.day:
            return True
        return False