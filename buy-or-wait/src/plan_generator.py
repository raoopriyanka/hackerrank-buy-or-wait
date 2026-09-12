from decimal import Decimal
from datetime import date, timedelta
from typing import List, Optional
from src.schemas import RequestRecord, FinancialProfile, RequestPaymentOption
from src.financial_state import FinancialState
from src.candidate_plan import CandidatePlan, PaymentScheduleItem
from src.currency import parse_iso_date


class CandidatePlanGenerator:
    """Deterministic Candidate Payment Plan Generator."""

    def generate_candidate_plans(
        self,
        request: RequestRecord,
        profile: FinancialProfile,
        financial_state: FinancialState,
        options: List[RequestPaymentOption],
        home_requested_amount: Decimal,
    ) -> List[CandidatePlan]:
        candidates: List[CandidatePlan] = []
        user_methods = [m.strip() for m in profile.payment_methods_user_will_consider.split(",")]
        req_date = parse_iso_date(request.request_date)
        desired_date = parse_iso_date(request.desired_completion_date)

        # 1. Full Payment Candidate (Immediate)
        if "full_payment" in user_methods:
            candidates.append(
                CandidatePlan(
                    method="full_payment",
                    payment_option_id=None,
                    schedule=[PaymentScheduleItem(payment_date=req_date, amount=home_requested_amount)],
                    total_amount_paid=home_requested_amount,
                    amount_safe_to_pay=home_requested_amount,
                    earliest_date_for_full_payment=req_date,
                    spending_changes_needed=[],
                )
            )

        # 2. Supplied Installment Options from request_payment_options.csv
        if "installments" in user_methods:
            for opt in options:
                if opt.request_id == request.request_id:
                    plan = self._build_installment_candidate(opt, req_date, home_requested_amount)
                    if plan:
                        candidates.append(plan)

        # 3. Partial Payment Candidates
        if request.allows_partial_payment and "partial_payment" in user_methods:
            partial_plans = self._generate_partial_payment_candidates(
                req_date, desired_date, home_requested_amount
            )
            candidates.extend(partial_plans)

        # 4. Wait Candidates
        if "full_payment" in user_methods and "wait" in user_methods:
            curr_d = req_date + timedelta(days=1)
            while curr_d <= desired_date:
                candidates.append(
                    CandidatePlan(
                        method="wait",
                        payment_option_id=None,
                        schedule=[PaymentScheduleItem(payment_date=curr_d, amount=home_requested_amount)],
                        total_amount_paid=home_requested_amount,
                        amount_safe_to_pay=Decimal("0.0"),
                        earliest_date_for_full_payment=curr_d,
                        spending_changes_needed=[],
                    )
                )
                curr_d += timedelta(days=1)

        # 5. Permute Candidates with Flexible Spending Changes
        expanded_candidates = self._attach_spending_changes(candidates, financial_state)

        # Fallback
        fallback = CandidatePlan(
            method="not_recommended",
            payment_option_id=None,
            schedule=[],
            total_amount_paid=Decimal("0.0"),
            amount_safe_to_pay=Decimal("0.0"),
            earliest_date_for_full_payment=None,
            spending_changes_needed=[],
        )
        expanded_candidates.append(fallback)

        return expanded_candidates

    def _build_installment_candidate(
        self,
        option: RequestPaymentOption,
        req_date: date,
        requested_amount: Decimal,
    ) -> Optional[CandidatePlan]:
        num_payments = option.number_of_payments
        fee = Decimal(str(option.installment_fee))
        total_amount = requested_amount + fee
        installment_amt = total_amount / Decimal(num_payments)

        schedule = []
        for i in range(num_payments):
            p_date = req_date + timedelta(days=30 * i)
            schedule.append(PaymentScheduleItem(payment_date=p_date, amount=installment_amt))

        return CandidatePlan(
            method="installments",
            payment_option_id=option.payment_option_id,
            schedule=schedule,
            total_amount_paid=total_amount,
            amount_safe_to_pay=installment_amt,
            earliest_date_for_full_payment=schedule[-1].payment_date,
            spending_changes_needed=[],
        )

    def _generate_partial_payment_candidates(
        self,
        req_date: date,
        desired_date: date,
        requested_amount: Decimal,
    ) -> List[CandidatePlan]:
        plans = []
        half_amt = requested_amount / Decimal("2.0")
        
        curr_d = req_date + timedelta(days=1)
        while curr_d <= desired_date:
            plans.append(
                CandidatePlan(
                    method="partial_payment",
                    payment_option_id=None,
                    schedule=[
                        PaymentScheduleItem(payment_date=req_date, amount=half_amt),
                        PaymentScheduleItem(payment_date=curr_d, amount=requested_amount - half_amt),
                    ],
                    total_amount_paid=requested_amount,
                    amount_safe_to_pay=half_amt,
                    earliest_date_for_full_payment=curr_d,
                    spending_changes_needed=[],
                )
            )
            curr_d += timedelta(days=1)
        return plans

    def _attach_spending_changes(
        self,
        base_candidates: List[CandidatePlan],
        financial_state: FinancialState,
    ) -> List[CandidatePlan]:
        flexible_expenses = [e for e in financial_state.recurring_expenses if e.flexible]
        if not flexible_expenses:
            return base_candidates

        all_candidates = list(base_candidates)
        for cand in base_candidates:
            for exp in flexible_expenses[:3]:
                stop_change = [f"stop:{exp.event_id}"]
                new_cand = CandidatePlan(
                    method=cand.method,
                    payment_option_id=cand.payment_option_id,
                    schedule=cand.schedule,
                    total_amount_paid=cand.total_amount_paid,
                    amount_safe_to_pay=cand.amount_safe_to_pay,
                    earliest_date_for_full_payment=cand.earliest_date_for_full_payment,
                    spending_changes_needed=stop_change,
                )
                all_candidates.append(new_cand)

        return all_candidates