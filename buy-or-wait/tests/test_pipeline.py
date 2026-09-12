import tempfile
import os
import pandas as pd
import pytest
from src.pipeline import PipelineOrchestrator


def test_pipeline_end_to_end_mock():
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(f"{tmpdir}/financial_profiles.csv", "w") as f:
            f.write('user_id,home_currency,current_available_balance,minimum_balance_to_keep,payment_methods_user_will_consider\nuser_1,USD,5000.0,500.0,"full_payment,installments"\n')
        with open(f"{tmpdir}/requests.csv", "w") as f:
            f.write("request_id,user_id,request_date,request_type,requested_amount,desired_completion_date,allows_partial_payment,request_text\nreq_1,user_1,2026-07-01,purchase,100.0,2026-07-15,True,Buy laptop USD 100\n")
        with open(f"{tmpdir}/request_payment_options.csv", "w") as f:
            f.write("payment_option_id,request_id,payment_method,payment_amount,number_of_payments,first_payment_date,payment_frequency_days,financing_fee,total_payable_amount\n")
        with open(f"{tmpdir}/financial_events.csv", "w") as f:
            f.write("event_id,user_id,event_date,amount,currency,event_type,status,flexibility\n")
        with open(f"{tmpdir}/messages.csv", "w") as f:
            f.write("message_id,user_id,request_id,related_event_id,sent_at,source_type,message_text\n")
        with open(f"{tmpdir}/images.csv", "w") as f:
            f.write("image_id,user_id,request_id,related_event_id,timestamp,file_path,description\n")
        with open(f"{tmpdir}/exchange_rates.csv", "w") as f:
            f.write("rate_date,from_currency,to_currency,rate\n")

        out_csv = f"{tmpdir}/output.csv"
        report_md = f"{tmpdir}/usage_report.md"

        orchestrator = PipelineOrchestrator(data_dir=tmpdir)
        orchestrator.run(output_csv_path=out_csv, report_md_path=report_md)

        assert os.path.exists(out_csv)
        assert os.path.exists(report_md)

        df_out = pd.read_csv(out_csv)
        expected_cols = [
            "request_id",
            "amount_safe_to_pay",
            "affordability_status",
            "recommended_payment_method",
            "payment_plan",
            "earliest_date_for_full_payment",
            "spending_changes_needed",
            "decision_explanation",
        ]
        assert df_out.columns.tolist() == expected_cols
        assert len(df_out) == 1
        assert df_out.iloc[0]["request_id"] == "req_1"