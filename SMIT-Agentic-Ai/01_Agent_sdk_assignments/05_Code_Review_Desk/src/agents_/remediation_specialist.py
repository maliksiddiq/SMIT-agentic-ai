"""Remediation handoff target."""

from agents import Agent

from src.agents_.base_reviewer import create_gemini_model
from src.config.settings import Settings
from src.models.report import RemediationHandoffInput


def build_remediation_specialist(settings: Settings) -> Agent:
    return Agent(
        name="RemediationSpecialist",
        model=create_gemini_model(settings),
        instructions=(
            "Propose a concrete fix for the triggering critical security "
            "finding. State which file and line triggered this handoff, then "
            "propose a concrete fix without repeating credential-shaped text."
        ),
    )
