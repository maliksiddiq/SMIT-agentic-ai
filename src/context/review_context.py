"""Context shared by application code and local tools."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewContext:
    repo: str
    language: str
    ruleset_id: str
    strictness: str = "normal"

    def __post_init__(self) -> None:
        normalized = self.strictness.strip().lower()
        if normalized not in {"normal", "strict"}:
            raise ValueError("strictness must be 'normal' or 'strict'")
        object.__setattr__(self, "strictness", normalized)

