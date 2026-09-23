from __future__ import annotations

import asyncio
import os
from pathlib import Path

from agents import (
    Agent,
    InputGuardrailTripwireTriggered,
    OpenAIChatCompletionsModel,
    RunConfig,
    Runner,
)

from .agent_factory import TURN_CEILING, build_agents, build_dynamic_prompt
from .models import StudentProfile, Ticket
from .observability import AuditTimeline
from .provider import build_openai_compatible_client
from .runner import DeskRunHooks, RunMetadata


class StudentOpsDesk:
    def __init__(self, profile: StudentProfile, timeline: AuditTimeline | None = None) -> None:
        self.timeline = timeline or AuditTimeline()
        self.client = build_openai_compatible_client()
        self.model = OpenAIChatCompletionsModel(model="gemini-3.6-flash", openai_client=self.client)
        self.profile = profile
        self.desk, self.assignments, self.careers = build_agents(profile, self.timeline)
        self.desk.model = self.model
        self.assignments.model = self.model
        self.careers.model = self.model
        self.last_prompt = ""
        self.last_metadata: RunMetadata | None = None

    def available_tools(self) -> tuple[str, ...]:
        return tuple(tool.name for tool in self.desk.tools)

    async def answer(self, question: str) -> Ticket | str:
        self.last_prompt = build_dynamic_prompt(self.profile)
        self.timeline.record("prompt_ready", "Desk", self.last_prompt)
        hooks = DeskRunHooks(self.timeline)
        run_config = RunConfig(
            workflow_name="Saylani Student Ops Desk",
            trace_metadata={"project": "04_Student_Ops_Desk", "request_id": self.timeline.request_id},
        )
        try:
            result = await Runner.run(
                self.desk,
                question,
                context=self.profile,
                max_turns=TURN_CEILING,
                hooks=hooks,
                run_config=run_config,
            )
        except InputGuardrailTripwireTriggered:
            self.timeline.record("guardrail_refusal", "Input Guardrail")
            self.last_metadata = hooks.metadata()
            return "I can only help with questions about the Saylani bootcamp."
        self.last_metadata = hooks.metadata()
        if type(result.final_output) is not Ticket:
            raise TypeError("The Desk returned non-Ticket structured output.")
        if result.final_output.resolved:
            self.timeline.record("resolved", result.last_agent.name)
        else:
            self.timeline.record("escalated", result.last_agent.name)
        return result.final_output


def build_demo_profile() -> StudentProfile:
    return StudentProfile(name="Demo Student", roll_no="DEMO-001", course_id="agentic-ai-w4", tier="regular", open_tickets=0)


def validate_startup() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError("Startup configuration error: install requirements.txt first.") from exc
    load_dotenv()
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")):
        raise RuntimeError("Startup configuration error: GEMINI_API_KEY is missing from .env.")


async def main() -> None:
    validate_startup()
    profile = build_demo_profile()
    desk = StudentOpsDesk(profile)
    result = await desk.answer("What are the batch timings for my course?")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
