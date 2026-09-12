import tempfile
import pytest
import pandas as pd
from src.data_loader import (
    load_requests,
    load_financial_events,
    load_raw_df,
)


def test_requests_loading():
    content = """request_id,user_id,request_date,request_type,requested_amount,desired_completion_date,allows_partial_payment,request_text
request_1,user_1,2026-01-01,purchase,100.0,2026-02-01,True,Buy item USD 100
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
        f.write(content)
        f.flush()
        records = load_requests(f.name)
        assert len(records) == 1
        assert records[0].request_id == "request_1"
        assert records[0].allows_partial_payment is True
        assert records[0].requested_amount == 100.0


def test_blank_amount_preserved_as_none():
    content = """event_id,user_id,event_date,amount,currency,event_type,status,flexible
evt_1,user_1,2026-01-01,,USD,one_time_expense,confirmed,False
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
        f.write(content)
        f.flush()
        records = load_financial_events(f.name)
        assert len(records) == 1
        assert records[0].amount is None  # Ensures blank amount is NOT modified to 0.0


def test_schema_mismatch_raises_error():
    content = """invalid_col,user_id
1,2
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
        f.write(content)
        f.flush()
        with pytest.raises(ValueError, match="Schema mismatch"):
            load_raw_df(f.name, "requests.csv")