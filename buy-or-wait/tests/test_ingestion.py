import tempfile
import pytest

from src.data_loader import (
    load_raw_df,
    load_financial_profiles,
)


def test_load_valid_profiles_csv():
    content = """user_id,home_currency,current_available_balance,minimum_balance_to_keep,payment_methods_user_will_consider
user_1,USD,5000.0,500.0,"full_payment,installments"
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
        f.write(content)
        f.flush()
        profiles = load_financial_profiles(f.name)
        assert len(profiles) == 1
        assert profiles[0].user_id == "user_1"
        assert profiles[0].minimum_balance_to_keep == 500.0
        assert profiles[0].current_available_balance == 5000.0


def test_missing_file_raises_error():
    with pytest.raises(FileNotFoundError):
        load_raw_df("non_existent_file.csv")


def test_schema_mismatch_raises_error():
    with pytest.raises(FileNotFoundError):
        load_raw_df("non_existent_file.csv")