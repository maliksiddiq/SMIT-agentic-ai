"""Remediation handoff target."""

from agents import Agent

from src.agents_.base_reviewer import create_gemini_model
from src.config.settings import Settings


def build_remediation_specialist(settings: Settings) -> Agent:
    return Agent(
        name="RemediationSpecialist",
        model=create_gemini_model(settings),
        instructions=(
            "Propose a concrete fix for the triggering critical security "
            "finding. Name the finding without repeating any credential-shaped text."
        ),
    )

