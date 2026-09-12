from dataclasses import dataclass, field
from typing import Dict, List, Optional
from decimal import Decimal


@dataclass
class LLMCallMetrics:
    provider: str
    model: str
    operation: str
    request_id: Optional[str]
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: Decimal


class TokenUsageTracker:
    """Provider-agnostic token and cost tracking system."""

    def __init__(self, cost_per_1k_input: Dict[str, Decimal] = None, cost_per_1k_output: Dict[str, Decimal] = None):
        self.calls: List[LLMCallMetrics] = []
        self.cost_per_1k_input = cost_per_1k_input or {}
        self.cost_per_1k_output = cost_per_1k_output or {}

    def log_call(
        self,
        provider: str,
        model: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        request_id: Optional[str] = None,
    ) -> LLMCallMetrics:
        total_tokens = input_tokens + output_tokens

        inp_rate = self.cost_per_1k_input.get(model, Decimal("0.0"))
        out_rate = self.cost_per_1k_output.get(model, Decimal("0.0"))

        cost = (Decimal(input_tokens) / Decimal(1000) * inp_rate) + (
            Decimal(output_tokens) / Decimal(1000) * out_rate
        )

        metrics = LLMCallMetrics(
            provider=provider,
            model=model,
            operation=operation,
            request_id=request_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=cost,
        )
        self.calls.append(metrics)
        return metrics

    def get_summary(self) -> Dict:
        total_calls = len(self.calls)
        total_input = sum(c.input_tokens for c in self.calls)
        total_output = sum(c.output_tokens for c in self.calls)
        total_tokens = sum(c.total_tokens for c in self.calls)
        total_cost = sum(c.estimated_cost for c in self.calls)

        per_model = {}
        for c in self.calls:
            if c.model not in per_model:
                per_model[c.model] = {"calls": 0, "tokens": 0, "cost": Decimal("0.0")}
            per_model[c.model]["calls"] += 1
            per_model[c.model]["tokens"] += c.total_tokens
            per_model[c.model]["cost"] += c.estimated_cost

        return {
            "total_calls": total_calls,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "avg_tokens_per_request": (total_tokens / total_calls) if total_calls > 0 else 0,
            "per_model": per_model,
        }