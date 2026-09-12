from dataclasses import dataclass
from typing import Optional
from decimal import Decimal


@dataclass(frozen=True)
class FinancialProfile:
    user_id: str
    home_currency: str
    minimum_balance_to_keep: float
    payment_methods_user_will_consider: str


@dataclass(frozen=True)
class RequestRecord:
    request_id: str
    user_id: str
    request_date: str
    request_type: str
    requested_amount: float
    desired_completion_date: str
    allows_partial_payment: bool
    request_text: str


@dataclass(frozen=True)
class RequestPaymentOption:
    request_id: str
    payment_option_id: str
    method: str
    number_of_payments: int
    installment_fee: float
    plan_details: str


@dataclass(frozen=True)
class FinancialEvent:
    event_id: str
    user_id: str
    event_date: str
    amount: Optional[float]
    currency: Optional[str]
    event_type: str
    status: str
    flexible: Optional[bool]


@dataclass(frozen=True)
class MessageRecord:
    message_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]
    timestamp: str
    sender: str
    message_text: str


@dataclass(frozen=True)
class ImageRecord:
    image_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]
    timestamp: str
    file_path: str
    description: Optional[str]


@dataclass(frozen=True)
class ExchangeRate:
    rate_date: str
    from_currency: str
    to_currency: str
    exchange_rate: Decimal  # Preserved as Decimal from ingestion onward