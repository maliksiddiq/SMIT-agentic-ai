from src.config.settings import Settings
from src.services.desk_flow import desk_input
from src.services.report_builder import build_final_report
from src.services.concurrency import ReviewerResult


def test_desk_input_contains_only_serialized_review_results() -> None:
    prompt = desk_input(
        [{"agent_name": "SecurityReviewer", "findings": [], "partial": False}]
    )
    assert "SecurityReviewer" in prompt
    assert "ReviewContext" not in prompt


def test_final_report_can_mark_remediation() -> None:
    report = build_final_report(
        [ReviewerResult("SecurityReviewer", [], 1, 2)],
        [],
        remediation_triggered=True,
    )
    assert report.remediation_triggered
