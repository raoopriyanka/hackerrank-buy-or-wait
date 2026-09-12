from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Optional, Set
from datetime import date

from src.schemas import FinancialEvent, FinancialProfile, ExchangeRate
from src.currency import CurrencyConverter, parse_iso_date, MissingExchangeRateError
from src.untrusted_extractor import ExtractedEventFact


class ResolutionStatus(Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class UnresolvedFinancialAmountError(Exception):
    """Raised when a baseline financial event cannot be resolved to a numeric amount."""
    pass


@dataclass(frozen=True)
class Provenance:
    origin: str  # "csv", "message", "image"
    source_id: str
    is_converted: bool = False
    original_currency: Optional[str] = None
    original_amount: Optional[Decimal] = None


@dataclass(frozen=True)
class ReconstructedEvent:
    event_id: str
    user_id: str
    event_date: date
    amount: Decimal
    home_currency: str
    event_type: str
    status: str
    flexible: bool
    resolution_status: ResolutionStatus
    provenance: Provenance


@dataclass
class FinancialState:
    user_id: str
    home_currency: str
    minimum_balance_to_keep: Decimal
    recurring_income: List[ReconstructedEvent] = field(default_factory=list)
    recurring_expenses: List[ReconstructedEvent] = field(default_factory=list)
    one_time_events: List[ReconstructedEvent] = field(default_factory=list)
    unresolved_events: List[ReconstructedEvent] = field(default_factory=list)


class FinancialStateReconstructor:
    """
    Deterministic Financial State Reconstruction Engine.
    Filters ignored events, resolves blank amounts via Step 3 facts, converts currencies,
    applies conflict resolution, and builds authoritative user financial ledgers.
    """

    # Event statuses to explicitly ignore per problem statement
    IGNORED_STATUSES: Set[str] = {"cancelled", "failed", "pending_credit", "unrealized"}
    
    # Event types that represent unrealized investments or non-liquid events
    IGNORED_EVENT_TYPES: Set[str] = {"unrealized_investment", "pending_credit"}

    def __init__(self, currency_converter: CurrencyConverter):
        self.converter = currency_converter

    def reconstruct_user_state(
        self,
        profile: FinancialProfile,
        events: List[FinancialEvent],
        extracted_facts: Optional[List[ExtractedEventFact]] = None,
    ) -> FinancialState:
        fact_map: Dict[str, ExtractedEventFact] = {}
        if extracted_facts:
            for fact in extracted_facts:
                fact_map[fact.event_id] = fact

        # Step A: Filter user events & apply exact deduplication
        user_events = [e for e in events if e.user_id == profile.user_id]
        unique_events = self._deduplicate_events(user_events)

        # Step B: Process events into reconstructed items
        reconstructed_list: List[ReconstructedEvent] = []
        
        # Group by event_id to resolve conflicts between multiple versions of the same event
        grouped: Dict[str, List[FinancialEvent]] = {}
        for ev in unique_events:
            grouped.setdefault(ev.event_id, []).append(ev)

        for event_id, ev_group in grouped.items():
            resolved_ev = self._resolve_event_group(
                event_id=event_id,
                group=ev_group,
                profile=profile,
                fact=fact_map.get(event_id),
            )
            if resolved_ev is not None:
                reconstructed_list.append(resolved_ev)

        # Step C: Assemble structured FinancialState
        state = FinancialState(
            user_id=profile.user_id,
            home_currency=profile.home_currency,
            minimum_balance_to_keep=Decimal(str(profile.minimum_balance_to_keep)),
        )

        for rev in reconstructed_list:
            if rev.resolution_status == ResolutionStatus.UNRESOLVED:
                state.unresolved_events.append(rev)
            elif "recurring_income" in rev.event_type or rev.event_type == "recurring_income":
                state.recurring_income.append(rev)
            elif "recurring_expense" in rev.event_type or rev.event_type == "recurring_expense":
                state.recurring_expenses.append(rev)
            else:
                state.one_time_events.append(rev)

        return state

    def _deduplicate_events(self, events: List[FinancialEvent]) -> List[FinancialEvent]:
        """Deduplicates exact row duplicates preserving order."""
        seen = set()
        unique = []
        for ev in events:
            key = (
                ev.event_id,
                ev.user_id,
                ev.event_date,
                ev.amount,
                ev.currency,
                ev.event_type,
                ev.status,
                ev.flexible,
            )
            if key not in seen:
                seen.add(key)
                unique.append(ev)
        return unique

    def _resolve_event_group(
        self,
        event_id: str,
        group: List[FinancialEvent],
        profile: FinancialProfile,
        fact: Optional[ExtractedEventFact],
    ) -> Optional[ReconstructedEvent]:
        """Applies conflict resolution and status filtering to a group of records sharing event_id."""

        # 1. Check if extracted fact indicates explicit cancellation
        if fact and fact.status_update == "cancelled":
            return None

        # 2. Filter out records with ignored statuses or types
        valid_records = []
        for ev in group:
            st = ev.status.strip().lower()
            et = ev.event_type.strip().lower()
            if st in self.IGNORED_STATUSES or et in self.IGNORED_EVENT_TYPES:
                continue
            valid_records.append(ev)

        if not valid_records:
            return None

        # 3. Conflict Resolution: Select authoritative record
        # Precedence: Explicit settled status over estimates, then financially conservative interpretation
        selected_record = self._select_authoritative_record(valid_records)

        # Check for status override from extracted fact (e.g. settled/amended)
        effective_status = selected_record.status
        if fact and fact.status_update:
            effective_status = fact.status_update

        # 4. Amount Resolution
        raw_amt = selected_record.amount
        prov_origin = "csv"
        prov_source_id = selected_record.event_id
        is_unresolved = False

        if raw_amt is None:
            if fact and fact.amount is not None:
                raw_amt = float(fact.amount)
                prov_origin = fact.provenance_type
                prov_source_id = fact.provenance_source_id
            else:
                is_unresolved = True

        parsed_date = parse_iso_date(selected_record.event_date)
        home_curr = profile.home_currency.strip().upper()
        event_curr = (selected_record.currency or home_curr).strip().upper()

        if is_unresolved:
            return ReconstructedEvent(
                event_id=event_id,
                user_id=profile.user_id,
                event_date=parsed_date,
                amount=Decimal("0.0"),
                home_currency=home_curr,
                event_type=selected_record.event_type,
                status=effective_status,
                flexible=bool(selected_record.flexible),
                resolution_status=ResolutionStatus.UNRESOLVED,
                provenance=Provenance(origin=prov_origin, source_id=prov_source_id),
            )

        # 5. Strict Currency Conversion at event_date
        amt_decimal = Decimal(str(raw_amt))
        if event_curr != home_curr:
            converted_amt = self.converter.convert(
                amount=amt_decimal,
                from_curr=event_curr,
                to_curr=home_curr,
                rate_date=selected_record.event_date,
            )
            prov = Provenance(
                origin=prov_origin,
                source_id=prov_source_id,
                is_converted=True,
                original_currency=event_curr,
                original_amount=amt_decimal,
            )
            final_amt = converted_amt
        else:
            converted_amt = amt_decimal
            prov = Provenance(
                origin=prov_origin,
                source_id=prov_source_id,
                is_converted=False,
                original_currency=home_curr,
                original_amount=amt_decimal,
            )
            final_amt = converted_amt

        return ReconstructedEvent(
            event_id=event_id,
            user_id=profile.user_id,
            event_date=parsed_date,
            amount=final_amt,
            home_currency=home_curr,
            event_type=selected_record.event_type,
            status=effective_status,
            flexible=bool(selected_record.flexible),
            resolution_status=ResolutionStatus.RESOLVED,
            provenance=prov,
        )

    def _select_authoritative_record(self, records: List[FinancialEvent]) -> FinancialEvent:
        """Selects authoritative record using status hierarchy and conservative financial fallback."""
        if len(records) == 1:
            return records[0]

        # Priority 1: Settled records over estimated/forecasted
        settled = [r for r in records if r.status.lower() == "settled"]
        if settled:
            return settled[0]

        # Priority 2: Financially conservative interpretation (higher expense or lower income)
        # If income type, choose min amount; if expense type, choose max amount
        is_income = "income" in records[0].event_type.lower()
        valid_amts = [r for r in records if r.amount is not None]
        if valid_amts:
            if is_income:
                return min(valid_amts, key=lambda r: r.amount)
            else:
                return max(valid_amts, key=lambda r: r.amount)

        return records[0]