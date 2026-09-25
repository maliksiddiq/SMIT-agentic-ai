import pytest
from pydantic import ValidationError

from src.agents_.base_reviewer import build_base_reviewer
from src.config import settings as settings_module
from src.config.settings import ConfigurationError, Settings, load_settings
from src.context.review_context import ReviewContext
from src.models.finding import Finding
from src.services.diff_splitter import split_unified_diff
from src.tools.diff_tools import read_diff_chunk
from src.tools.ruleset_tool import lookup_ruleset


def test_review_context_defaults_and_validates_strictness() -> None:
    assert ReviewContext("repo", "Python", "python_default").strictness == "normal"
    with pytest.raises(ValueError, match="strictness"):
        ReviewContext("repo", "Python", "python_default", strictness="loose")


def test_finding_rejects_unknown_severity() -> None:
    finding = Finding(file="src/app.py", line=4, severity="minor", message="Prefer a guard.")
    assert finding.severity == "minor"
    with pytest.raises(ValidationError):
        Finding(file="src/app.py", line=4, severity="info", message="Not allowed")


def test_unified_diff_splits_by_file() -> None:
    result = split_unified_diff(
        "diff --git a/a.py b/a.py\n@@ -1 +1 @@\n-old\n+new\n"
        "diff --git a/b.py b/b.py\n@@ -1 +1 @@\n-old\n+new\n"
    )
    assert result.ok
    assert [chunk.file for chunk in result.chunks] == ["a.py", "b.py"]


def test_malformed_diff_returns_message() -> None:
    result = split_unified_diff("not a unified diff")
    assert result.error == "The input is not a valid unified diff."


def test_tools_return_messages_for_missing_inputs(tmp_path) -> None:
    assert "Could not read diff" in read_diff_chunk("missing.py", chunks={})
    context = ReviewContext("repo", "Python", "missing")
    assert "No ruleset found" in lookup_ruleset(context, rulesets_dir=tmp_path)


def test_base_reviewer_has_typed_output_and_explicit_model() -> None:
    settings = Settings(
        gemini_api_key="test-key",
        gemini_model_primary="gemini-3.5-flash",
        gemini_model_fallback="gemini-2.5-flash",
        tracing_api_key=None,
        turn_ceiling=8,
        chainlit_port=None,
    )
    agent = build_base_reviewer(chunks={"app.py": "diff"}, settings=settings)
    assert agent.output_type == list[Finding]
    assert agent.model is not None
    assert {tool.name for tool in agent.tools} == {"read_diff_chunk", "lookup_ruleset"}


def test_missing_api_key_is_a_clear_configuration_error(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(settings_module, "load_dotenv", lambda **_: None)
    with pytest.raises(ConfigurationError, match="API key required"):
        load_settings()
