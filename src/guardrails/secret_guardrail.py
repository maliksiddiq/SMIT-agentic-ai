"""Credential-shaped output detection."""

from __future__ import annotations

import re
from dataclasses import dataclass


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

