import os
from typing import Any


def build_openai_compatible_client() -> Any:
    """Create the project-scoped OpenAI-compatible client without global SDK state."""
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The OpenAI-compatible client dependency is missing. Install requirements.txt."
        ) from exc
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Startup configuration error: GEMINI_API_KEY is missing from .env.")
    return AsyncOpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/",
        project=os.getenv("OPENAI_PROJECT") or None,
    )
