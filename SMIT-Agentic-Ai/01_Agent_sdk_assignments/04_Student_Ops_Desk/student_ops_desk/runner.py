from __future__ import annotations

from time import perf_counter
from dataclasses import dataclass

from agents import RunHooks

from .observability import AuditTimeline


@dataclass(frozen=True)
class RunMetadata:
    request_id: str
    elapsed_ms: float


class DeskRunHooks(RunHooks):
    def __init__(self, timeline: AuditTimeline) -> None:
        self.timeline = timeline
        self.started = perf_counter()

    async def on_agent_start(self, context, agent) -> None:
        self.timeline.record("agent_start", agent.name)

    async def on_handoff(self, context, from_agent, to_agent) -> None:
        self.timeline.record("handoff", from_agent.name, to_agent.name)

    async def on_tool_start(self, context, agent, tool) -> None:
        self.timeline.record("tool_start", agent.name, tool.name)

    async def on_tool_end(self, context, agent, tool, result) -> None:
        self.timeline.record("tool_end", agent.name, tool.name)

    async def on_agent_end(self, context, agent, output) -> None:
        self.timeline.record("agent_end", agent.name)

    def metadata(self) -> RunMetadata:
        return RunMetadata(self.timeline.request_id, (perf_counter() - self.started) * 1000)
