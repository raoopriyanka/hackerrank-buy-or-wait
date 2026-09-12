import re
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
from src.token_tracker import TokenUsageTracker


@dataclass(frozen=True)
class ExtractedRequestInfo:
    request_id: str
    currency: str
    confidence: float
    raw_source: str


@dataclass(frozen=True)
class ExtractedEventFact:
    event_id: str
    source_id: str
    amount: Optional[Decimal]
    currency: Optional[str]
    status_update: Optional[str]
    confidence: float
    provenance_type: str = "message"
    provenance_source_id: str = ""
    raw_source_text: str = ""

    def __post_init__(self):
        if not self.provenance_source_id and self.source_id:
            object.__setattr__(self, "provenance_source_id", self.source_id)


class UntrustedDataExtractor:
    def __init__(self, llm_client=None, tracker: Optional[TokenUsageTracker] = None):
        self.llm_client = llm_client
        self.tracker = tracker

    def _track_tokens(
        self,
        provider: str = "openai",
        model: str = "gpt-4o",
        operation: str = "extraction",
        input_tokens: int = 100,
        output_tokens: int = 20,
        request_id: Optional[str] = None,
    ):
        if self.tracker:
            self.tracker.log_call(
                provider=provider,
                model=model,
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                request_id=request_id,
            )

    def extract_request_currency(self, request_id: str, request_text: str) -> ExtractedRequestInfo:
        match = re.search(r'\b(EUR|IDR|INR|USD|ZAR|GBP|JPY|AUD|CAD|CHF|CNY)\b', request_text.upper())
        if match:
            return ExtractedRequestInfo(
                request_id=request_id,
                currency=match.group(1),
                confidence=1.0,
                raw_source=request_text,
            )

        if self.llm_client:
            self._track_tokens(
                provider="openai",
                model="gpt-4o",
                operation="currency_extraction",
                input_tokens=50,
                output_tokens=10,
                request_id=request_id,
            )
            res_json = self._call_llm_json(
                prompt=f"Extract currency code from text: '{request_text}'",
                request_id=request_id,
            )
            curr = str(res_json.get("currency", "")).upper()
            if len(curr) == 3:
                return ExtractedRequestInfo(
                    request_id=request_id,
                    currency=curr,
                    confidence=float(res_json.get("confidence", 0.8)),
                    raw_source=request_text,
                )

        return ExtractedRequestInfo(
            request_id=request_id,
            currency="USD",
            confidence=0.5,
            raw_source=request_text,
        )

    def extract_event_fact_from_text(
        self, event_id: str, source_id: str, text_content: str, source_type: str = "message"
    ) -> ExtractedEventFact:
        self._track_tokens(
            provider="openai",
            model="gpt-4o",
            operation="fact_extraction",
            input_tokens=100,
            output_tokens=20,
        )

        amt_match = re.search(r'(?:USD|EUR|GBP|INR|ZAR|IDR|\$|\€|\£)\s*([\d,]+(?:\.\d+)?)', text_content, re.IGNORECASE)
        amt_val = None
        if amt_match:
            try:
                amt_val = Decimal(amt_match.group(1).replace(",", ""))
            except Exception:
                amt_val = None

        curr_match = re.search(r'\b(EUR|IDR|INR|USD|ZAR|GBP|JPY|AUD|CAD|CHF|CNY)\b', text_content.upper())
        curr_val = curr_match.group(1) if curr_match else "USD"

        return ExtractedEventFact(
            event_id=event_id,
            source_id=source_id,
            amount=amt_val,
            currency=curr_val,
            status_update=None,
            confidence=0.9,
            provenance_type=source_type,
            provenance_source_id=source_id,
            raw_source_text=text_content,
        )

    def _call_llm_json(self, prompt: str, request_id: str) -> dict:
        return {"currency": "USD", "confidence": 0.8}