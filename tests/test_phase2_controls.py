import asyncio

from src.agents_.base_reviewer import build_base_reviewer, run_with_model_override
from src.config.settings import Settings
from src.context.review_context import ReviewContext
from src.guardrails.secret_guardrail import inspect_report
from src.models.finding import Finding
from src.services import concurrency
from src.services.concurrency import ReviewerResult
from src.agents_.merge_specialist import merge_findings


def test_guardrail_refuses_secret_shaped_output_and_passes_clean_text() -> None:
    refused = inspect_report("Finding: api_key=AIza123456789012345678901234567890")
    assert refused.tripwire_triggered
    assert "credential" in refused.reason
    assert not inspect_report("No credentials are present.").tripwire_triggered


def test_merge_deduplicates_and_orders_by_severity() -> None:
    results = [
        ReviewerResult(
            "SecurityReviewer",
            [
                Finding(file="b.py", line=2, severity="minor", message="Style"),
                Finding(file="a.py", line=1, severity="critical", message="Exploit"),
            ],
            1,
            2,
        ),
        ReviewerResult(
            "TestsReviewer",
            [Finding(file="a.py", line=1, severity="critical", message="Exploit")],
            1,
            2,
        ),
    ]
    report = merge_findings(results)
    assert [finding.severity for finding in report.findings] == ["critical", "minor"]


def test_concurrency_starts_all_reviewers_before_results(monkeypatch) -> None:
    started: list[str] = []

    async def fake_run_one(agent, *, context, files, max_turns):
        started.append(agent)
        await asyncio.sleep(0)
        return ReviewerResult(agent, [], 1, 0)

    monkeypatch.setattr(concurrency, "run_one_reviewer", fake_run_one)
    result = asyncio.run(
        concurrency.run_reviewers_concurrently(
            ("security", "tests", "style"),
            context=ReviewContext("repo", "Python", "rules"),
            files=["a.py"],
            max_turns=8,
        )
    )
    assert started == ["security", "tests", "style"]
    assert len(result) == 3


def test_run_level_override_does_not_mutate_agent(monkeypatch) -> None:
    settings = Settings("key", "gemini-3.5-flash", "gemini-2.5-flash", None, 8, None)
    agent = build_base_reviewer(chunks={"a.py": "diff"}, settings=settings)
    original_model = agent.model
    captured = {}

    async def fake_run(agent_arg, prompt, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("src.agents_.base_reviewer.Runner.run", fake_run)
    asyncio.run(
        run_with_model_override(
            agent,
            settings=settings,
            context=ReviewContext("repo", "Python", "rules"),
            files=["a.py"],
            max_turns=8,
        )
    )
    assert agent.model is original_model
    assert captured["run_config"].model is not None
