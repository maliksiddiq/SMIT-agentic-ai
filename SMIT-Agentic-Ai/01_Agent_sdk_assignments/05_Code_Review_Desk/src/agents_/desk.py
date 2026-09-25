"""Top-level Desk agent with SDK tool and handoff delegation."""

from __future__ import annotations

import json

from agents import Agent
from agents.handoffs import handoff

from src.agents_.base_reviewer import create_gemini_model
from src.agents_.merge_specialist import merge_as_tool
from src.agents_.remediation_specialist import build_remediation_specialist
from src.config.settings import Settings
from src.guardrails.secret_guardrail import credential_output_guardrail
from src.models.report import RemediationHandoffInput


def build_desk(settings: Settings) -> Agent:
    remediation = build_remediation_specialist(settings)

    async def on_handoff(context, handoff_input: RemediationHandoffInput) -> None:
        del context
        setattr(remediation, "_triggering_finding", handoff_input.triggering_finding)

    remediation_handoff = handoff(
        remediation,
        tool_name_override="remediation_handoff",
        tool_description_override=(
            "Transfer a critical security finding to Remediation for a concrete fix."
        ),
        input_type=RemediationHandoffInput,
        on_handoff=on_handoff,
    )
    return Agent(
        name="Desk",
        model=create_gemini_model(settings),
        instructions=(
            "You are the Code Review Desk orchestrator. You receive serialized "
            "reviewer findings. Always call merge_findings first. If the merged "
            "findings contain a critical security finding, use remediation_handoff "
            "with the exact triggering_finding and all_findings. Otherwise return "
            "a concise final report. Never repeat credential-shaped text."
        ),
        tools=[merge_as_tool(settings)],
        handoffs=[remediation_handoff],
        output_guardrails=[credential_output_guardrail],
    )


def desk_input(results: list[dict]) -> str:
    return (
        "Merge and deliver these reviewer outputs. The security reviewer is the "
        "only source whose critical findings trigger handoff:\n"
        + json.dumps(results, default=str)
    )
