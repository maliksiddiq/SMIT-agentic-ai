from src.agents_.desk import build_desk
from src.agents_.reviewers import build_reviewers
from src.config.settings import Settings
from src.context.review_context import ReviewContext
from src.models.report import RemediationHandoffInput
from src.services.concurrency import ReviewerResult
from src.tools.ruleset_tool import lookup_ruleset


def _settings() -> Settings:
    return Settings("test-key", "gemini-3.5-flash", "gemini-2.5-flash", None, 8, None)


def test_desk_has_sdk_as_tool_and_typed_handoff() -> None:
    desk = build_desk(_settings())
    assert [tool.name for tool in desk.tools] == ["merge_findings"]
    assert [handoff.tool_name for handoff in desk.handoffs] == ["remediation_handoff"]
    assert desk.handoffs[0].input_json_schema["properties"]["triggering_finding"]


def test_security_reviewer_requires_a_tool_call() -> None:
    security, tests, style = build_reviewers(chunks={"a.py": "diff"}, settings=_settings())
    assert security.model_settings.tool_choice == "required"
    assert tests.model_settings.tool_choice is None
    assert style.model_settings.tool_choice is None


def test_missing_ruleset_is_non_raising_for_all_reviewer_tools(tmp_path) -> None:
    agents = build_reviewers(
        chunks={"a.py": "diff"},
        settings=_settings(),
        rulesets_dir=str(tmp_path),
    )
    context = ReviewContext("repo", "Python", "missing")
    for agent in agents:
        ruleset = next(tool for tool in agent.tools if tool.name == "lookup_ruleset")
        assert ruleset.params_json_schema["properties"] == {}
        assert "No ruleset found" in lookup_ruleset(context, rulesets_dir=tmp_path)
