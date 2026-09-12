from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date
from typing import List, Optional


@dataclass(frozen=True)
class PaymentScheduleItem:
    payment_date: date
    amount: Decimal


@dataclass(frozen=True)
class CandidatePlan:
    method: str  # full_payment, partial_payment, installments, wait, not_recommended
    payment_option_id: Optional[str]  # ID from request_payment_options.csv or None
    schedule: List[PaymentScheduleItem]
    total_amount_paid: Decimal
    amount_safe_to_pay: Decimal
    earliest_date_for_full_payment: Optional[date]
    spending_changes_needed: List[str] = field(default_factory=list)

    @property
    def formatted_spending_changes(self) -> str:
        if not self.spending_changes_needed:
            return "none"
        return "|".join(self.spending_changes_needed[:3])

    @property
    def formatted_payment_plan(self) -> str:
        if self.method == "not_recommended" or not self.schedule:
            return "none"
        parts = [f"{item.payment_date.strftime('%Y-%m-%d')}:{item.amount:.2f}" for item in self.schedule]
        return "|".join(parts)