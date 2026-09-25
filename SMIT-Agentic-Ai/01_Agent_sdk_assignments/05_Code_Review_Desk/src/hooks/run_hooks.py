"""Run-level timing and token metrics."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any

from agents.lifecycle import RunHooks


@dataclass(frozen=True)
class HookMetrics:
    agent_name: str
    started_at: float
    ended_at: float
    duration_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int


_active_metrics: dict[str, HookMetrics] = {}


class ReviewRunHooks(RunHooks[Any]):
    """Shared run-level hook collecting actual SDK response usage."""

    def __init__(self) -> None:
        self._started: dict[str, float] = {}
        self._input: dict[str, int] = {}
        self._output: dict[str, int] = {}

    async def on_agent_start(self, context, agent) -> None:
        self._started.setdefault(agent.name, monotonic())

    async def on_llm_end(self, context, agent, response) -> None:
        usage = response.usage
        self._input[agent.name] = self._input.get(agent.name, 0) + int(
            getattr(usage, "input_tokens", 0) or 0
        )
        self._output[agent.name] = self._output.get(agent.name, 0) + int(
            getattr(usage, "output_tokens", 0) or 0
        )

    async def on_agent_end(self, context, agent, output) -> None:
        started = self._started.get(agent.name, monotonic())
        ended = monotonic()
        input_tokens = self._input.get(agent.name, 0)
        output_tokens = self._output.get(agent.name, 0)
        _active_metrics[agent.name] = HookMetrics(
            agent_name=agent.name,
            started_at=started,
            ended_at=ended,
            duration_ms=int((ended - started) * 1000),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )

    def metrics(self) -> list[HookMetrics]:
        return list(_active_metrics.values())


_registered_hooks = ReviewRunHooks()


def registered_run_hooks() -> ReviewRunHooks:
    """Return the one application-wide run-hook registration."""

    return _registered_hooks


def clear_metrics() -> None:
    _active_metrics.clear()
