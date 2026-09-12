from decimal import Decimal
from datetime import date
from typing import List, Tuple, Optional
from src.candidate_plan import CandidatePlan
from src.financial_state import FinancialState
from src.forecaster import FinancialForecaster
from src.schemas import RequestRecord
from src.currency import parse_iso_date


class PlanRanker:
    """
    Deterministic Safety Verification & Multi-Criteria Plan Ranker Engine.
    Evaluates candidate payment plans through 90-day balance simulation and ranks safe options.
    """

    def __init__(self, forecaster: Optional[FinancialForecaster] = None):
        self.forecaster = forecaster or FinancialForecaster(forecast_days=90)

    def select_best_plan(
        self,
        request: RequestRecord,
        initial_balance: Decimal,
        financial_state: FinancialState,
        candidates: List[CandidatePlan],
    ) -> Tuple[CandidatePlan, str]:
        """
        Evaluates candidate plans, filters safe options, and returns the top-ranked plan
        along with its corresponding affordability_status string.
        """
        req_date = parse_iso_date(request.request_date)
        desired_date = parse_iso_date(request.desired_completion_date)

        safe_evaluated: List[Tuple[CandidatePlan, Decimal, bool]] = []

        for plan in candidates:
            if plan.method == "not_recommended":
                continue

            # Check completion date constraint
            if plan.earliest_date_for_full_payment and plan.earliest_date_for_full_payment > desired_date:
                continue

            # Build candidate payment schedule dict for forecaster
            sched_map = {item.payment_date: item.amount for item in plan.schedule}

            # If spending changes are specified, construct modified state for simulation
            effective_state = self._apply_spending_changes_to_state(financial_state, plan.spending_changes_needed)

            # Run 90-day simulation
            sim_result = self.forecaster.forecast_90_days(
                initial_balance=initial_balance,
                financial_state=effective_state,
                request_date=req_date,
                additional_candidate_payments=sched_map,
            )

            if sim_result.is_entire_forecast_safe:
                is_full = (plan.method in ("full_payment", "wait"))
                safe_evaluated.append((plan, plan.total_amount_paid, is_full))

        if not safe_evaluated:
            # Fallback when no candidate option is safe
            fallback_plan = CandidatePlan(
                method="not_recommended",
                payment_option_id=None,
                schedule=[],
                total_amount_paid=Decimal("0.0"),
                amount_safe_to_pay=Decimal("0.0"),
                earliest_date_for_full_payment=None,
                spending_changes_needed=[],
            )
            return fallback_plan, "not_affordable"

        # Sort safe candidates according to authoritative ranking rules
        sorted_candidates = sorted(
            safe_evaluated,
            key=lambda x: self._ranking_sort_key(x[0], desired_date)
        )

        winning_plan = sorted_candidates[0][0]
        status = self._determine_affordability_status(winning_plan, req_date)
        return winning_plan, status

    def _apply_spending_changes_to_state(
        self,
        state: FinancialState,
        changes: List[str],
    ) -> FinancialState:
        """Applies candidate spending changes (e.g. stop:event_id) to flexible expenses for simulation."""
        if not changes:
            return state

        stops = {c.split(":")[1] for c in changes if c.startswith("stop:")}
        
        modified_expenses = [
            e for e in state.recurring_expenses if e.event_id not in stops
        ]

        return FinancialState(
            user_id=state.user_id,
            home_currency=state.home_currency,
            minimum_balance_to_keep=state.minimum_balance_to_keep,
            recurring_income=state.recurring_income,
            recurring_expenses=modified_expenses,
            one_time_events=state.one_time_events,
            unresolved_events=state.unresolved_events,
        )

    def _ranking_sort_key(self, plan: CandidatePlan, desired_date: date) -> Tuple:
        """
        Calculates sort key based on challenge rules:
        1. Complete full request by desired_completion_date (0 if completed by desired_date, 1 otherwise)
        2. Require no spending changes (0 if empty, 1 if changes needed)
        3. Minimize total amount paid
        4. Start payment earlier (first payment date)
        5. Use fewer payments (len(schedule))
        6. Lowest payment_option_id
        """
        # Rule 1: Full request completed by desired_completion_date
        completed_on_time = 0 if (plan.earliest_date_for_full_payment and plan.earliest_date_for_full_payment <= desired_date) else 1
        
        # Rule 2: Require no spending changes
        no_changes = 0 if len(plan.spending_changes_needed) == 0 else 1

        # Rule 3: Minimize total amount paid
        tot_amt = plan.total_amount_paid

        # Rule 4: Start payment earlier
        first_date = plan.schedule[0].payment_date if plan.schedule else date.max

        # Rule 5: Fewer payments
        num_payments = len(plan.schedule)

        # Rule 6: Lowest payment_option_id
        opt_id = plan.payment_option_id or ""

        return (completed_on_time, no_changes, tot_amt, first_date, num_payments, opt_id)

    def _determine_affordability_status(self, plan: CandidatePlan, req_date: date) -> str:
        """Maps winning plan to allowed affordability_status string."""
        if plan.method == "not_recommended":
            return "not_affordable"
        if plan.method == "full_payment" and not plan.spending_changes_needed:
            return "affordable_now"
        if plan.method == "wait":
            return "affordable_later"
        return "affordable_with_plan"