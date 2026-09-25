"""Run-level timing and token metrics."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class HookMetrics:
    agent_name: str
    started_at: float
    ended_at: float
    duration_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int


def metrics_from_result(agent_name: str, started_at: float, result) -> HookMetrics:
    ended_at = monotonic()
    usage = getattr(result, "context_wrapper", None)
    usage_data = getattr(usage, "usage", None)
    input_tokens = int(getattr(usage_data, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage_data, "output_tokens", 0) or 0)
    return HookMetrics(
        agent_name=agent_name,
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=int((ended_at - started_at) * 1000),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )
