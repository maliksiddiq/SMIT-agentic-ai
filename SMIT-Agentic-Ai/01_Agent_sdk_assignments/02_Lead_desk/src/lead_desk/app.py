from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agents import (
    Agent,
    AsyncOpenAI,
    OpenAIChatCompletionsModel,
    RunContextWrapper,
    Runner,
    function_tool,
)
from dotenv import load_dotenv
from openai import NotFoundError
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEADS_PATH = PROJECT_ROOT / "leads.json"
SAVED_PATH = PROJECT_ROOT / "saved.json"


@dataclass
class FreelancerProfile:
    name: str
    min_rate_pkr_hour: int
    skills: list[str]
    hours_free_per_week: int
    verified: bool
    rate_card: dict[str, int] = field(default_factory=dict)


class LeadTriage(BaseModel):
    intent: str
    budget_pkr: int | None = Field(default=None)
    red_flags: list[str]
    priority: Literal["high", "medium", "low"]
    suggested_reply: str


def create_profile() -> FreelancerProfile:
    return FreelancerProfile(
        name="Aisha Khan",
        min_rate_pkr_hour=5000,
        skills=["Python", "FastAPI", "React", "technical writing"],
        hours_free_per_week=20,
        verified=True,
        rate_card={
            "Python": 6500,
            "FastAPI": 7000,
            "React": 6000,
            "technical writing": 4000,
        },
    )


@function_tool
async def lookup_rate_card(
    ctx: RunContextWrapper[FreelancerProfile], skill_name: str
) -> str:
    """Look up the hourly PKR rate for a named skill before discussing any money.
    Return an explicit unknown result when the skill is not listed; never estimate a rate.
    """
    rate = ctx.context.rate_card.get(skill_name)
    if rate is None:
        return f"Unknown skill: {skill_name}. No rate is available."
    return f"{skill_name}: PKR {rate}/hour"


@function_tool
async def check_availability(ctx: RunContextWrapper[FreelancerProfile]) -> str:
    """Return the number of hours currently free this week from the private runtime profile."""
    return f"{ctx.context.hours_free_per_week} hours are free this week."


def save_lead(lead: dict[str, str], triage: LeadTriage) -> None:
    """Append one triage result to saved.json; the caller owns the save decision."""
    records: list[dict[str, object]] = []
    if SAVED_PATH.exists():
        records = json.loads(SAVED_PATH.read_text(encoding="utf-8"))
    records.append({"lead": lead, "triage": triage.model_dump()})
    SAVED_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")


def load_leads() -> list[dict[str, str]]:
    return json.loads(LEADS_PATH.read_text(encoding="utf-8"))


def protect_private_output(triage: LeadTriage, profile: FreelancerProfile) -> LeadTriage:
    private_values = (
        str(profile.min_rate_pkr_hour),
        f"{profile.min_rate_pkr_hour:,}",
        "min_rate_pkr_hour",
        "minimum rate",
    )
    data = triage.model_dump()
    for key in ("intent", "red_flags", "suggested_reply"):
        value = data[key]
        values = value if isinstance(value, list) else [value]
        for index, item in enumerate(values):
            for private_value in private_values:
                item = re.sub(re.escape(private_value), "[private]", item, flags=re.IGNORECASE)
            if isinstance(value, list):
                value[index] = item
            else:
                data[key] = item
    if data["budget_pkr"] == profile.min_rate_pkr_hour:
        data["budget_pkr"] = None
    return LeadTriage.model_validate(data)


def build_agent(model: OpenAIChatCompletionsModel) -> Agent[FreelancerProfile]:
    return Agent(
        name="Lead Desk",
        model=model,
        instructions=(
            "Triage the client message into the requested structured output. "
            "Use lookup_rate_card before discussing any money and use check_availability "
            "when timing or capacity matters. Detect revenue-share offers, vague scope, "
            "urgent requests, tiny jobs, and unreasonable deadlines as red flags where "
            "appropriate. Never disclose private application-side data. "
            "Do not save leads and do not claim to have saved anything."
        ),
        tools=[lookup_rate_card, check_availability],
        output_type=LeadTriage,
    )


def build_model(model_name: str = "gemini-2.5-flash") -> OpenAIChatCompletionsModel:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from .env")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


async def triage_lead(
    agent: Agent[FreelancerProfile],
    lead: dict[str, str],
    profile: FreelancerProfile,
) -> LeadTriage:
    prompt = f"Platform: {lead['platform']}\nClient message: {lead['message']}"
    result = await Runner.run(agent, prompt, context=profile)
    if not isinstance(result.final_output, LeadTriage):
        raise TypeError("The agent did not return a LeadTriage object")
    return protect_private_output(result.final_output, profile)


async def main_async() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    lead = load_leads()[0]
    profile = create_profile()
    try:
        agent = build_agent(build_model())
        triage = await triage_lead(agent, lead, profile)
    except NotFoundError as error:
        if "gemini-2.5-flash" not in str(error):
            raise
        print("gemini-2.5-flash is unavailable for this API account; retrying with Gemini's current model.")
        agent = build_agent(build_model("gemini-3.6-flash"))
        triage = await triage_lead(agent, lead, profile)
    print(triage.model_dump_json(indent=2))
    doubled_budget = triage.budget_pkr * 2 if triage.budget_pkr is not None else None
    print(f"numeric budget check: {doubled_budget}")
    if triage.priority == "high":
        print(f"HIGH PRIORITY | budget={triage.budget_pkr}")
        save_lead(lead, triage)


def main() -> None:
    asyncio.run(main_async())
