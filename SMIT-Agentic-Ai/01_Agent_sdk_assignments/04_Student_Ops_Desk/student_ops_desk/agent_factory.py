from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any

from agents import (
    Agent,
    AgentHooks,
    ModelSettings,
    RunContextWrapper,
    function_tool,
    handoff,
    input_guardrail,
    GuardrailFunctionOutput,
)

from .models import StudentProfile, Ticket

MODEL_NAME = "gemini-3.6-flash"
TURN_CEILING = 10
COURSES_PATH = Path(__file__).resolve().parent.parent / "courses.json"


def build_dynamic_prompt(profile: StudentProfile) -> str:
    if profile.open_tickets >= 3:
        return (
            f"Hello {profile.name}. You are enrolled in {profile.course_id}. "
            "Be concise. Use tools for facts, route specialist questions, and close with a Ticket."
        )
    return (
        f"Hello {profile.name}. You are enrolled in {profile.course_id}. "
        "You are the Saylani Student Operations Desk. Classify the request as assignment, "
        "career, or admin. Use course tools for every course fact. Handoff assignment and "
        "career requests. Use the policy summariser when an administrative answer is long. "
        "Always finish an in-scope conversation by calling close_ticket with a complete Ticket."
    )


def dynamic_instructions(context: RunContextWrapper[StudentProfile], agent: Agent[StudentProfile]) -> str:
    del agent
    return build_dynamic_prompt(context.context)


def _load_courses() -> list[dict[str, Any]]:
    try:
        payload = json.loads(COURSES_PATH.read_text(encoding="utf-8"))
        return [item for item in payload.get("courses", []) if isinstance(item, dict)]
    except (OSError, json.JSONDecodeError):
        return []


@function_tool
def list_courses() -> str:
    """List the authoritative courses available to students."""
    courses = _load_courses()
    return "\n".join(f"{c.get('id')}: {c.get('title')}" for c in courses) or "No courses are currently available."


@function_tool
def get_course(course_id: str) -> str:
    """Retrieve the schedule and policies for one authoritative course."""
    course = next((item for item in _load_courses() if item.get("id") == course_id), None)
    if course is None:
        return f"No course with id {course_id} exists."
    return json.dumps(
        {"id": course.get("id"), "title": course.get("title"), "schedule": course.get("schedule"), "policies": course.get("policies", {})},
        ensure_ascii=False,
    )


@function_tool
def get_assignment(course_id: str, assignment_id: str) -> str:
    """Look up one assignment by ID in the authoritative course data."""
    course = next((item for item in _load_courses() if item.get("id") == course_id), None)
    if course is None:
        return f"No course with id {course_id} exists."
    assignment = next((item for item in course.get("assignments", []) if item.get("id") == assignment_id), None)
    if assignment is None:
        return f"No assignment with id {assignment_id} exists for course {course_id}."
    return json.dumps(assignment, ensure_ascii=False)


@function_tool
def get_scholarship_resources(context: RunContextWrapper[StudentProfile]) -> str:
    """List scholarship resources for the current scholarship student."""
    if context.context.tier != "scholarship":
        return "This tool is only available to scholarship students."
    return f"Scholarship resources for {context.context.course_id}: mentor office hours and course-support grant."


@function_tool
def summarise_policy(policy_text: str) -> str:
    """Reduce a long policy answer to exactly three concise lines."""
    lines = [line.strip() for line in policy_text.splitlines() if line.strip()]
    return "\n".join((lines + ["No additional policy detail."] * 3)[:3])


@function_tool
def close_ticket(ticket: Ticket) -> Ticket:
    """End the run and return the final structured Ticket."""
    return ticket


@input_guardrail(name="bootcamp_scope_guardrail", run_in_parallel=False)
async def bootcamp_scope_guardrail(
    context: RunContextWrapper[StudentProfile], agent: Agent[StudentProfile], input: str
) -> GuardrailFunctionOutput:
    del context, agent
    terms = {
        "course", "class", "bootcamp", "assignment", "deadline", "submission", "career",
        "job", "skill", "schedule", "batch", "attendance", "scholarship", "policy",
        "student", "mentor", "enrol", "enroll",
    }
    in_scope = isinstance(input, str) and any(term in input.lower() for term in terms)
    return GuardrailFunctionOutput(
        output_info="in scope" if in_scope else "This desk only handles bootcamp questions.",
        tripwire_triggered=not in_scope,
    )


class SpecialistHooks(AgentHooks[StudentProfile]):
    """Agent-level hooks attached only to the assignments specialist."""

    def __init__(self, timeline: Any) -> None:
        self.timeline = timeline

    async def on_start(self, context: Any, agent: Agent[StudentProfile]) -> None:
        self.timeline.record("agent_start", agent.name, "specialist hook")

    async def on_end(self, context: Any, agent: Agent[StudentProfile], output: Any) -> None:
        self.timeline.record("agent_end", agent.name, "specialist hook")


def build_agents(
    profile: StudentProfile,
    timeline: Any = None,
) -> tuple[Agent[StudentProfile], Agent[StudentProfile], Agent[StudentProfile]]:
    specialist_base = Agent[StudentProfile](
        name="Base Specialist",
        instructions="Use the course tools for facts. Stay within the bootcamp domain and finish with close_ticket.",
        model=MODEL_NAME,
        model_settings=ModelSettings(max_tokens=700),
    )
    assignments = specialist_base.clone(
        name="Assignments Specialist",
        instructions="Be cold and factual. Handle assignment deadlines, submission rules, and assignment content.",
        model_settings=ModelSettings(temperature=0.2, max_tokens=700),
        hooks=SpecialistHooks(timeline) if timeline else None,
        output_type=Ticket,
        tools=[get_assignment, get_course, close_ticket],
    )
    careers = specialist_base.clone(
        name="Careers Specialist",
        instructions="Be warm and practical. Handle bootcamp career paths and skill development. Finish with close_ticket.",
        model_settings=ModelSettings(temperature=0.7, max_tokens=700),
        output_type=Ticket,
        tools=[get_course, close_ticket],
    )
    summariser = Agent[StudentProfile](
        name="Policy Summariser",
        instructions="Summarise the supplied policy text into exactly three concise lines.",
        model=MODEL_NAME,
        output_type=str,
        tools=[],
    )
    summariser_tool = summariser.as_tool(
        tool_name="summarise_policy_with_agent",
        tool_description="Use this specialist as a tool to compress a long policy answer.",
        max_turns=TURN_CEILING,
    )
    desk_tools = [list_courses, get_course, get_assignment, summarise_policy, summariser_tool, close_ticket]
    if profile.tier == "scholarship":
        desk_tools.append(get_scholarship_resources)
    desk = Agent[StudentProfile](
        name="Desk",
        instructions=dynamic_instructions,
        model=MODEL_NAME,
        model_settings=ModelSettings(max_tokens=900),
        tools=desk_tools,
        handoffs=[
            handoff(assignments, tool_description_override="Hand off assignment and deadline questions."),
            handoff(careers, tool_description_override="Hand off career and skill-development questions."),
        ],
        input_guardrails=[bootcamp_scope_guardrail],
        output_type=Ticket,
    )
    return desk, assignments, careers
