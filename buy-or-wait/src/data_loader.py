import os
import pandas as pd
from decimal import Decimal
from typing import List
from src.schemas import (
    FinancialProfile,
    RequestRecord,
    RequestPaymentOption,
    FinancialEvent,
    MessageRecord,
    ImageRecord,
    ExchangeRate,
)


def load_raw_df(filepath: str) -> pd.DataFrame:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    df = pd.read_csv(filepath)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def load_financial_profiles(filepath: str) -> List[FinancialProfile]:
    df = load_raw_df(filepath)
    records = []
    for _, row in df.iterrows():
        avail_bal = row.get("current_available_balance", row.get("available_balance", 5000.0))
        records.append(
            FinancialProfile(
                user_id=str(row["user_id"]).strip(),
                home_currency=str(row["home_currency"]).strip(),
                current_available_balance=float(avail_bal),
                minimum_balance_to_keep=float(row["minimum_balance_to_keep"]),
                payment_methods_user_will_consider=str(row["payment_methods_user_will_consider"]).strip(),
            )
        )
    return records


def load_requests(filepath: str) -> List[RequestRecord]:
    df = load_raw_df(filepath)
    records = []
    for _, row in df.iterrows():
        val_bool = row["allows_partial_payment"]
        allows_partial = val_bool.strip().lower() == "true" if isinstance(val_bool, str) else bool(val_bool)

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
    df = load_raw_df(filepath)
    records = []
    for _, row in df.iterrows():
        freq_val = row.get("payment_frequency_days")
        freq_days = 30 if pd.isna(freq_val) or str(freq_val).strip() == "" else int(float(freq_val))

        fee_val = row.get("financing_fee", row.get("installment_fee", 0.0))
        fee = 0.0 if pd.isna(fee_val) or str(fee_val).strip() == "" else float(fee_val)

        total_val = row.get("total_payable_amount")
        total_payable = float(row["payment_amount"]) if pd.isna(total_val) else float(total_val)

        first_date_val = row.get("first_payment_date")
        first_date = "" if pd.isna(first_date_val) else str(first_date_val).strip()

        records.append(
            RequestPaymentOption(
                payment_option_id=str(row["payment_option_id"]).strip(),
                request_id=str(row["request_id"]).strip(),
                payment_method=str(row.get("payment_method", row.get("method", "installments"))).strip(),
                payment_amount=float(row["payment_amount"]),
                number_of_payments=int(row["number_of_payments"]),
                first_payment_date=first_date,
                payment_frequency_days=freq_days,
                financing_fee=fee,
                total_payable_amount=total_payable,
            )
        )
    return records


def load_financial_events(filepath: str) -> List[FinancialEvent]:
    df = load_raw_df(filepath)
    records = []
    for _, row in df.iterrows():
        amt_val = row.get("amount")
        amt = None if pd.isna(amt_val) or str(amt_val).strip() == "" else float(amt_val)

        curr_val = row.get("currency")
        curr = None if pd.isna(curr_val) else str(curr_val).strip()

        flex_val = row.get("flexibility", row.get("flexible"))
        if pd.isna(flex_val):
            flex = None
        elif isinstance(flex_val, str):
            flex = flex_val.strip().lower() in ("flexible", "true", "yes")
        else:
            flex = bool(flex_val)

        records.append(
            FinancialEvent(
                event_id=str(row["event_id"]).strip(),
                user_id=str(row["user_id"]).strip(),
                event_date=str(row.get("event_date", row.get("settlement_date", ""))).strip(),
                amount=amt,
                currency=curr,
                event_type=str(row["event_type"]).strip(),
                status=str(row["status"]).strip(),
                flexible=flex,
            )
        )
    return records


def load_messages(filepath: str) -> List[MessageRecord]:
    df = load_raw_df(filepath)
    records = []
    for _, row in df.iterrows():
        req_id = row.get("request_id")
        rel_evt_id = row.get("related_event_id")
        ts_val = row.get("sent_at", row.get("timestamp", ""))
        sender_val = row.get("source_type", row.get("sender", "user"))
        msg_text = row.get("message_text", row.get("text", ""))

        records.append(
            MessageRecord(
                message_id=str(row["message_id"]).strip(),
                user_id=str(row["user_id"]).strip(),
                request_id=None if pd.isna(req_id) else str(req_id).strip(),
                related_event_id=None if pd.isna(rel_evt_id) else str(rel_evt_id).strip(),
                timestamp="" if pd.isna(ts_val) else str(ts_val).strip(),
                sender="user" if pd.isna(sender_val) else str(sender_val).strip(),
                message_text="" if pd.isna(msg_text) else str(msg_text).strip(),
            )
        )
    return records


def load_images(filepath: str) -> List[ImageRecord]:
    df = load_raw_df(filepath)
    records = []
    for _, row in df.iterrows():
        req_id = row.get("request_id")
        rel_evt_id = row.get("related_event_id")
        ts_val = row.get("timestamp", "")
        fp_val = row.get("file_path", "")
        desc = row.get("description")

        records.append(
            ImageRecord(
                image_id=str(row["image_id"]).strip(),
                user_id=str(row["user_id"]).strip(),
                request_id=None if pd.isna(req_id) else str(req_id).strip(),
                related_event_id=None if pd.isna(rel_evt_id) else str(rel_evt_id).strip(),
                timestamp="" if pd.isna(ts_val) else str(ts_val).strip(),
                file_path="" if pd.isna(fp_val) else str(fp_val).strip(),
                description=None if pd.isna(desc) else str(desc).strip(),
            )
        )
    return records


def load_exchange_rates(filepath: str) -> List[ExchangeRate]:
    df = load_raw_df(filepath)
    records = []
    for _, row in df.iterrows():
        rate_val = row.get("rate", row.get("exchange_rate", row.get("fx_rate", 1.0)))
        date_val = row.get("rate_date", row.get("date", ""))
        from_val = row.get("from_currency", "USD")
        to_val = row.get("to_currency", "USD")

        records.append(
            ExchangeRate(
                rate_date=str(date_val).strip(),
                from_currency=str(from_val).strip(),
                to_currency=str(to_val).strip(),
                exchange_rate=Decimal(str(rate_val)),
            )
        )
    return records