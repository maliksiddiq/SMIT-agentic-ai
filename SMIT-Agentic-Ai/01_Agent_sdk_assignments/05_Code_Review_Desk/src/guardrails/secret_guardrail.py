"""Credential-shaped output detection."""

from __future__ import annotations

import re
from dataclasses import dataclass

from agents import Agent, GuardrailFunctionOutput, InputGuardrail, OutputGuardrail
from agents.run_context import RunContextWrapper

@dataclass(frozen=True)
class GuardrailResult:
    tripwire_triggered: bool
    reason: str | None = None


_SECRET_PATTERNS = (
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bsk-[0-9A-Za-z]{20,}\b"),
    re.compile(r"(?i)\b(?:api[_ -]?key|secret|password|token)\s*[:=]\s*\S+"),
)


def inspect_report(text: str) -> GuardrailResult:
    """Refuse reports containing credential-shaped text without echoing it."""

    if any(pattern.search(text) for pattern in _SECRET_PATTERNS):
        return GuardrailResult(
            tripwire_triggered=True,
            reason="Report refused because it contains credential-shaped content.",
        )
    return GuardrailResult(tripwire_triggered=False)


async def credential_output_guardrail(
    context: RunContextWrapper,
    agent: Agent,
    output: object,
) -> GuardrailFunctionOutput:
    """Native Agents SDK output guardrail for credential-shaped content."""

    del context, agent
    result = inspect_report(str(output))
    return GuardrailFunctionOutput(
        output_info=result.reason or "No credential-shaped content detected.",
        tripwire_triggered=result.tripwire_triggered,
    )


credential_output_guardrail = OutputGuardrail(
    guardrail_function=credential_output_guardrail,
    name="credential_output_guardrail",
)


async def credential_input_guardrail(
    context: RunContextWrapper,
    agent: Agent,
    input: object,
) -> GuardrailFunctionOutput:
    """Native input guardrail that blocks secrets supplied in a diff."""

    del context, agent
    result = inspect_report(str(input))
    return GuardrailFunctionOutput(
        output_info=result.reason or "No credential-shaped content detected.",
        tripwire_triggered=result.tripwire_triggered,
    )


credential_input_guardrail = InputGuardrail(
    guardrail_function=credential_input_guardrail,
    name="credential_input_guardrail",
    run_in_parallel=False,
)
