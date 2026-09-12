import os
import glob
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from typing import List

from src.data_loader import (
    load_financial_profiles,
    load_requests,
    load_request_payment_options,
    load_financial_events,
    load_messages,
    load_images,
    load_exchange_rates,
)
from src.currency import CurrencyConverter, parse_iso_date
from src.token_tracker import TokenUsageTracker
from src.untrusted_extractor import UntrustedDataExtractor, ExtractedEventFact
from src.financial_state import FinancialStateReconstructor
from src.forecaster import FinancialForecaster
from src.plan_generator import CandidatePlanGenerator
from src.ranker import PlanRanker
from src.explanation_generator import ExplanationGenerator


class PipelineOrchestrator:
    def __init__(self, data_dir: str = "."):
        self.data_dir = data_dir
        self.tracker = TokenUsageTracker()

    def _find_file(self, possible_filenames: List[str]) -> str:
        search_dirs = [self.data_dir, "dataset", "."]
        for name in possible_filenames:
            for d in search_dirs:
                candidate = os.path.join(d, name)
                if os.path.exists(candidate):
                    return candidate
            matches = glob.glob(f"**/{name}", recursive=True)
            if matches:
                return matches[0]
        raise FileNotFoundError(f"None of {possible_filenames} found in search paths.")

    def run(self, output_csv_path: str = "output.csv", report_md_path: str = "usage_report.md"):
        requests_path = self._find_file(["requests.csv", "requests_2.csv", "sample_requests.csv"])
        profiles_path = self._find_file(["financial_profiles.csv"])
        options_path = self._find_file(["request_payment_options.csv"])
        events_path = self._find_file(["financial_events.csv"])
        messages_path = self._find_file(["messages.csv"])
        images_path = self._find_file(["images.csv"])
        rates_path = self._find_file(["exchange_rates.csv"])

        profiles = {prof.user_id: prof for prof in load_financial_profiles(profiles_path)}
        requests = load_requests(requests_path)
        options = load_request_payment_options(options_path)
        events = load_financial_events(events_path)
        messages = load_messages(messages_path)
        images = load_images(images_path)
        rates = load_exchange_rates(rates_path)

        converter = CurrencyConverter(rates)
        extractor = UntrustedDataExtractor(tracker=self.tracker)
        reconstructor = FinancialStateReconstructor(converter)
        forecaster = FinancialForecaster(forecast_days=90)
        generator = CandidatePlanGenerator()
        ranker = PlanRanker(forecaster=forecaster)
        exp_generator = ExplanationGenerator(tracker=self.tracker)

        output_rows = []

        for req in requests:
            profile = profiles[req.user_id]
            req_info = extractor.extract_request_currency(req.request_id, req.request_text)
            req_currency = req_info.currency

            requested_amt = Decimal(str(req.requested_amount))
            home_requested_amt = converter.convert(
                amount=requested_amt,
                from_curr=req_currency,
                to_curr=profile.home_currency,
                rate_date=req.request_date,
            )

            extracted_facts: List[ExtractedEventFact] = []
            user_msgs = [m for m in messages if m.user_id == req.user_id]
            for msg in user_msgs:
                if msg.related_event_id:
                    fact = extractor.extract_event_fact_from_text(
                        event_id=msg.related_event_id,
                        source_id=msg.message_id,
                        text_content=msg.message_text,
                        source_type="message",
                    )
                    extracted_facts.append(fact)

            fin_state = reconstructor.reconstruct_user_state(
                profile=profile,
                events=events,
                extracted_facts=extracted_facts,
            )

            initial_balance = Decimal(str(profile.current_available_balance))

            candidates = generator.generate_candidate_plans(
                request=req,
                profile=profile,
                financial_state=fin_state,
                options=options,
                home_requested_amount=home_requested_amt,
            )

            winning_plan, status = ranker.select_best_plan(
                request=req,
                initial_balance=initial_balance,
                financial_state=fin_state,
                candidates=candidates,
            )

            explanation = exp_generator.generate_explanation(
                request_id=req.request_id,
                affordability_status=status,
                winning_plan=winning_plan,
                requested_amount=home_requested_amt,
                home_currency=profile.home_currency,
            )

            amt_safe = f"{winning_plan.amount_safe_to_pay.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
            earliest_date_str = (
                winning_plan.earliest_date_for_full_payment.strftime("%Y-%m-%d")
                if winning_plan.earliest_date_for_full_payment
                else "none"
            )

            output_rows.append({
                "request_id": req.request_id,
                "amount_safe_to_pay": amt_safe,
                "affordability_status": status,
                "recommended_payment_method": winning_plan.method,
                "payment_plan": winning_plan.formatted_payment_plan,
                "earliest_date_for_full_payment": earliest_date_str,
                "spending_changes_needed": winning_plan.formatted_spending_changes,
                "decision_explanation": explanation,
            })

        df_out = pd.DataFrame(output_rows)
        cols_order = [
            "request_id",
            "amount_safe_to_pay",
            "affordability_status",
            "recommended_payment_method",
            "payment_plan",
            "earliest_date_for_full_payment",
            "spending_changes_needed",
            "decision_explanation",
        ]
        df_out[cols_order].to_csv(output_csv_path, index=False)
        self._generate_usage_report(report_md_path, len(requests))

    def _generate_usage_report(self, report_path: str, total_requests: int):
        summary = self.tracker.get_summary()
        avg_tokens = summary["avg_tokens_per_request"]
        report_content = f"""# Token Usage and Cost Report

## Summary
- **Total Requests Processed**: {total_requests}
- **Total LLM Calls**: {summary['total_calls']}
- **Total Input Tokens**: {summary['total_input_tokens']}
- **Total Output Tokens**: {summary['total_output_tokens']}
- **Total Tokens**: {summary['total_tokens']}
- **Average Tokens / Request**: {avg_tokens:.2f}
- **Estimated Total Cost ($)**: {summary['total_cost']:.4f}
"""
        with open(report_path, "w") as f:
            f.write(report_content)