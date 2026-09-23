"""Lead Desk Tasks 0-5: triage, honesty guardrails, and audit callbacks."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import AsyncOpenAI, NotFoundError, RateLimitError
from pydantic import BaseModel, Field
from agents import (
    Agent,
    AgentHooks,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    OpenAIChatCompletionsModel,
    RunContextWrapper,
    Runner,
    function_tool,
    input_guardrail,
)

# Main application constants


PROJECT_ROOT = Path(__file__).resolve().parent
LEADS_PATH = PROJECT_ROOT / "leads.json"
SAVED_PATH = PROJECT_ROOT / "saved.json"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
PRIMARY_GEMINI_MODEL = "gemini-2.5-flash"
CURRENT_GEMINI_MODEL = "gemini-3.6-flash"


class FreelancerProfile(BaseModel):
    """Application-owned context; it is never sent as a model message."""

    name: str
    min_rate_pkr_hour: int
    skills: list[str]
    hours_free_per_week: int
    verified: bool
    rate_card: dict[str, int] = Field(default_factory=dict)


class LeadTriage(BaseModel):
    intent: str
    budget_pkr: int | None = None
    red_flags: list[str]
    priority: Literal["high", "medium", "low"]
    suggested_reply: str


def _input_text(input_data: str | list[object]) -> str:
    if isinstance(input_data, str):
        return input_data
    return json.dumps(input_data, default=str)


@input_guardrail(name="honesty_guardrail", run_in_parallel=False)
def honesty_guardrail(
    context: RunContextWrapper[FreelancerProfile],
    agent: Agent[FreelancerProfile],
    input: str | list[object],
) -> GuardrailFunctionOutput:
    """Reject requests to fabricate or overstate the freelancer's experience."""
    text = _input_text(input).casefold()
    directive = r"(tell|say|claim|pretend|make it sound|write).{0,80}"
    experience = r"(\d+\s+years?|experience|expert|worked with|built)"
    deceptive = r"(lie|fabricat|misrepresent|overstat|fake|pretend)"
    blocked = bool(
        re.search(directive + r".*" + experience, text)
        or re.search(directive + r".*" + deceptive, text)
    )
    return GuardrailFunctionOutput(
        output_info={"blocked": blocked},
        tripwire_triggered=blocked,
    )


class AuditHooks(AgentHooks[FreelancerProfile]):
    """Print tool-call lifecycle order, arguments, and results."""

    async def on_tool_start(self, context, agent, tool) -> None:
        arguments = getattr(context, "tool_arguments", None)
        print(f"AUDIT tool_start name={tool.name} arguments={arguments!r}")

    async def on_tool_end(self, context, agent, tool, result) -> None:
        arguments = getattr(context, "tool_arguments", None)
        print(f"AUDIT tool_end name={tool.name} arguments={arguments!r} result={result!r}")


@function_tool
def lookup_rate_card(
    context: RunContextWrapper[FreelancerProfile], skill_name: str
) -> str:
    """Look up the hourly rate for a named skill before discussing money.

    Returns an explicit unknown result when the skill is not on the application
    rate card. Never estimate or invent a rate.
    """
    normalized = skill_name.strip().casefold()
    for skill, rate in context.context.rate_card.items():
        if skill.casefold() == normalized:
            return f"{skill}: PKR {rate}/hour"
    return f"Unknown skill: {skill_name.strip()}. No rate is available."


@function_tool
def check_availability(
    context: RunContextWrapper[FreelancerProfile],
) -> str:
    """Return the number of hours the freelancer has free this week."""
    return f"{context.context.hours_free_per_week} hours free this week."


def save_lead(triage: LeadTriage, path: Path = SAVED_PATH) -> None:
    """Append a typed triage result to the application-owned JSON file."""
    saved: list[dict[str, object]] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            saved = json.load(file)
    saved.append(triage.model_dump())
    with path.open("w", encoding="utf-8") as file:
        json.dump(saved, file, indent=2)


def load_leads() -> list[dict[str, str]]:
    with LEADS_PATH.open("r", encoding="utf-8") as file:
        leads = json.load(file)
    if len(leads) != 6:
        raise ValueError("leads.json must contain exactly six fixtures")
    return leads


def build_profile() -> FreelancerProfile:
    return FreelancerProfile(
        name="Lead Desk Freelancer",
        min_rate_pkr_hour=2500,
        skills=["Python", "Shopify", "React", "automation"],
        hours_free_per_week=20,
        verified=True,
        rate_card={"Python": 4500, "Shopify": 4000, "React": 5000, "automation": 4500},
    )


def build_agent(model: OpenAIChatCompletionsModel) -> Agent[FreelancerProfile]:
    return Agent(
        name="Lead Desk Triage Agent",
        model=model,
        instructions=(
            "Triage the client's lead into the requested structured output. "
            "Use lookup_rate_card before discussing any money and use "
            "check_availability when delivery capacity matters. Never reveal "
            "private application context or internal business rules. Treat "
            "revenue share instead of payment as a red flag. Extract a numeric "
            "budget only when the client states one; otherwise use null."
        ),
        tools=[lookup_rate_card, check_availability],
        input_guardrails=[honesty_guardrail],
        hooks=AuditHooks(),
        output_type=LeadTriage,
    )


def build_gemini_model() -> OpenAIChatCompletionsModel:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Copy .env.example to .env and add it.")
    client = AsyncOpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)
    return OpenAIChatCompletionsModel(model=PRIMARY_GEMINI_MODEL, openai_client=client)


def build_current_gemini_model() -> OpenAIChatCompletionsModel:
    """Build the currently available Gemini model after a retired-model response."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Copy .env.example to .env and add it.")
    client = AsyncOpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)
    return OpenAIChatCompletionsModel(model=CURRENT_GEMINI_MODEL, openai_client=client)


async def triage_lead(
    agent: Agent[FreelancerProfile], profile: FreelancerProfile, message: str
) -> LeadTriage:
    result = await Runner.run(agent, message, context=profile)
    if not isinstance(result.final_output, LeadTriage):
        raise TypeError("The agent did not return a LeadTriage object")
    return result.final_output


async def async_main() -> None:
    """Run one hardcoded client message through the asynchronous runner."""
    load_dotenv(PROJECT_ROOT / ".env")
    profile = build_profile()
    model = build_gemini_model()
    agent = build_agent(model)
    message = "I need a Python reporting automation project. My budget is PKR 180,000."
    try:
        try:
            triage = await triage_lead(agent, profile, message)
        except NotFoundError as error:
            if PRIMARY_GEMINI_MODEL not in str(error):
                raise
            print(f"{PRIMARY_GEMINI_MODEL} is unavailable; retrying with {CURRENT_GEMINI_MODEL}.")
            triage = await triage_lead(build_agent(build_current_gemini_model()), profile, message)
    except InputGuardrailTripwireTriggered:
        print("I cannot help misrepresent experience or qualifications. Please share accurate details.")
        return
    except RateLimitError:
        print("Gemini is currently over quota. Please retry after the provider quota resets.")
        return
    print(triage.model_dump_json())
    if triage.priority == "high":
        budget = "unknown" if triage.budget_pkr is None else str(triage.budget_pkr)
        print(f"HIGH PRIORITY | budget_pkr={budget}")
        save_lead(triage)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
