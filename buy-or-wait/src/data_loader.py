import os
import pandas as pd
from decimal import Decimal
from typing import List, Dict
from src.schemas import (
    FinancialProfile,
    RequestRecord,
    RequestPaymentOption,
    FinancialEvent,
    MessageRecord,
    ImageRecord,
    ExchangeRate,
)

EXPECTED_SCHEMAS: Dict[str, List[str]] = {
    "financial_profiles.csv": [
        "user_id", "home_currency", "minimum_balance_to_keep", "payment_methods_user_will_consider"
    ],
    "requests.csv": [
        "request_id", "user_id", "request_date", "request_type", "requested_amount",
        "desired_completion_date", "allows_partial_payment", "request_text"
    ],
    "request_payment_options.csv": [
        "request_id", "payment_option_id", "method", "number_of_payments", "installment_fee", "plan_details"
    ],
    "financial_events.csv": [
        "event_id", "user_id", "event_date", "amount", "currency", "event_type", "status", "flexible"
    ],
    "messages.csv": [
        "message_id", "user_id", "request_id", "related_event_id", "timestamp", "sender", "message_text"
    ],
    "images.csv": [
        "image_id", "user_id", "request_id", "related_event_id", "timestamp", "file_path", "description"
    ],
    "exchange_rates.csv": [
        "rate_date", "from_currency", "to_currency", "exchange_rate"
    ],
}


def load_raw_df(filepath: str, filename: str) -> pd.DataFrame:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    df = pd.read_csv(filepath)
    df.columns = [str(c).strip() for c in df.columns]

    expected_cols = EXPECTED_SCHEMAS.get(filename)
    if expected_cols:
        missing = [col for col in expected_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Schema mismatch in {filename}. Missing columns: {missing}")

    return df


def load_financial_profiles(filepath: str) -> List[FinancialProfile]:
    df = load_raw_df(filepath, "financial_profiles.csv")
    records = []
    for _, row in df.iterrows():
        records.append(
            FinancialProfile(
                user_id=str(row["user_id"]).strip(),
                home_currency=str(row["home_currency"]).strip(),
                minimum_balance_to_keep=float(row["minimum_balance_to_keep"]),
                payment_methods_user_will_consider=str(row["payment_methods_user_will_consider"]).strip(),
            )
        )
    return records


def load_requests(filepath: str) -> List[RequestRecord]:
    df = load_raw_df(filepath, "requests.csv")
    records = []
    for _, row in df.iterrows():
        val_bool = row["allows_partial_payment"]
        if isinstance(val_bool, str):
            allows_partial = val_bool.strip().lower() == "true"
        else:
            allows_partial = bool(val_bool)

        records.append(
            RequestRecord(
                request_id=str(row["request_id"]).strip(),
                user_id=str(row["user_id"]).strip(),
                request_date=str(row["request_date"]).strip(),
                request_type=str(row["request_type"]).strip(),
                requested_amount=float(row["requested_amount"]),
                desired_completion_date=str(row["desired_completion_date"]).strip(),
                allows_partial_payment=allows_partial,
                request_text=str(row["request_text"]).strip(),
            )
        )
    return records


def load_request_payment_options(filepath: str) -> List[RequestPaymentOption]:
    df = load_raw_df(filepath, "request_payment_options.csv")
    records = []
    for _, row in df.iterrows():
        records.append(
            RequestPaymentOption(
                request_id=str(row["request_id"]).strip(),
                payment_option_id=str(row["payment_option_id"]).strip(),
                method=str(row["method"]).strip(),
                number_of_payments=int(row["number_of_payments"]),
                installment_fee=float(row["installment_fee"]),
                plan_details=str(row["plan_details"]).strip(),
            )
        )
    return records


def load_financial_events(filepath: str) -> List[FinancialEvent]:
    df = load_raw_df(filepath, "financial_events.csv")
    records = []
    for _, row in df.iterrows():
        amt_val = row["amount"]
        if pd.isna(amt_val) or str(amt_val).strip() == "":
            amt = None
        else:
            amt = float(amt_val)

        curr_val = row["currency"]
        curr = None if pd.isna(curr_val) else str(curr_val).strip()

        flex_val = row["flexible"]
        if pd.isna(flex_val):
            flex = None
        elif isinstance(flex_val, str):
            flex = flex_val.strip().lower() == "true"
        else:
            flex = bool(flex_val)

        records.append(
            FinancialEvent(
                event_id=str(row["event_id"]).strip(),
                user_id=str(row["user_id"]).strip(),
                event_date=str(row["event_date"]).strip(),
                amount=amt,
                currency=curr,
                event_type=str(row["event_type"]).strip(),
                status=str(row["status"]).strip(),
                flexible=flex,
            )
        )
    return records


def load_messages(filepath: str) -> List[MessageRecord]:
    df = load_raw_df(filepath, "messages.csv")
    records = []
    for _, row in df.iterrows():
        req_id = row["request_id"]
        rel_evt_id = row["related_event_id"]

        records.append(
            MessageRecord(
                message_id=str(row["message_id"]).strip(),
                user_id=str(row["user_id"]).strip(),
                request_id=None if pd.isna(req_id) else str(req_id).strip(),
                related_event_id=None if pd.isna(rel_evt_id) else str(rel_evt_id).strip(),
                timestamp=str(row["timestamp"]).strip(),
                sender=str(row["sender"]).strip(),
                message_text=str(row["message_text"]).strip(),
            )
        )
    return records


def load_images(filepath: str) -> List[ImageRecord]:
    df = load_raw_df(filepath, "images.csv")
    records = []
    for _, row in df.iterrows():
        req_id = row["request_id"]
        rel_evt_id = row["related_event_id"]
        desc = row["description"]

        records.append(
            ImageRecord(
                image_id=str(row["image_id"]).strip(),
                user_id=str(row["user_id"]).strip(),
                request_id=None if pd.isna(req_id) else str(req_id).strip(),
                related_event_id=None if pd.isna(rel_evt_id) else str(rel_evt_id).strip(),
                timestamp=str(row["timestamp"]).strip(),
                file_path=str(row["file_path"]).strip(),
                description=None if pd.isna(desc) else str(desc).strip(),
            )
        )
    return records


def load_exchange_rates(filepath: str) -> List[ExchangeRate]:
    df = load_raw_df(filepath, "exchange_rates.csv")
    records = []
    for _, row in df.iterrows():
        rate_val = row["exchange_rate"]
        records.append(
            ExchangeRate(
                rate_date=str(row["rate_date"]).strip(),
                from_currency=str(row["from_currency"]).strip(),
                to_currency=str(row["to_currency"]).strip(),
                exchange_rate=Decimal(str(rate_val)),
            )
        )
    return records