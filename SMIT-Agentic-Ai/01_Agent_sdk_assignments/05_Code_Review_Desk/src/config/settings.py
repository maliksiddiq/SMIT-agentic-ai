"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from agents import set_tracing_export_api_key
from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when required runtime configuration is unavailable."""


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model_primary: str
    gemini_model_fallback: str
    tracing_api_key: str | None
    turn_ceiling: int
    chainlit_port: int | None
    tracing_enabled: bool = False


_ledger_registration = True


def register_ledger(enabled: bool = True) -> None:
    """Central application registration point for ledger recording."""

    global _ledger_registration
    _ledger_registration = enabled


def record_run(result, *, request_id: str) -> None:
    if not _ledger_registration:
        return
    from src.runners.ledger_runner import append_ledger_entry

    append_ledger_entry(result, request_id=request_id)


def load_settings(*, require_api_key: bool = True) -> Settings:
    """Load and validate settings from the project .env file."""

    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=project_env)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if require_api_key and (not api_key or api_key == "your-key-here"):
        raise ConfigurationError("API key required")

    try:
        turn_ceiling = int(os.getenv("TURN_CEILING", "8"))
    except ValueError as exc:
        raise ConfigurationError("TURN_CEILING must be an integer") from exc
    if turn_ceiling < 1:
        raise ConfigurationError("TURN_CEILING must be at least 1")

    port_value = os.getenv("CHAINLIT_PORT", "").strip()
    try:
        chainlit_port = int(port_value) if port_value else None
    except ValueError as exc:
        raise ConfigurationError("CHAINLIT_PORT must be an integer") from exc

    tracing_api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
    if tracing_api_key:
        set_tracing_export_api_key(tracing_api_key)

    return Settings(
        gemini_api_key=api_key,
        gemini_model_primary=os.getenv(
            "GEMINI_MODEL_PRIMARY", "gemini-3.1-flash-lite"
        ),
        gemini_model_fallback=os.getenv(
            "GEMINI_MODEL_FALLBACK", "gemini-3.1-flash-lite"
        ),
        tracing_api_key=tracing_api_key,
        turn_ceiling=turn_ceiling,
        chainlit_port=chainlit_port,
        tracing_enabled=bool(tracing_api_key),
    )
