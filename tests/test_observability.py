import json

from src.runners.ledger_runner import append_ledger_entry, new_request_id
from src.services.concurrency import ReviewerResult
from src.services.report_builder import build_final_report, render_report
from src.models.finding import Finding


def test_report_footer_has_one_row_per_reviewer() -> None:
    results = [
        ReviewerResult("SecurityReviewer", [], 12, 10),
        ReviewerResult("TestsReviewer", [], 8, 7),
        ReviewerResult("StyleReviewer", [], 9, 6),
    ]
    report = build_final_report(results, [])
    assert [row.agent_name for row in report.footer] == [
        "SecurityReviewer",
        "TestsReviewer",
        "StyleReviewer",
    ]
    assert "Reviewer metrics" in render_report(report)


def test_ledger_entry_is_one_json_line(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    result = ReviewerResult(
        "SecurityReviewer",
        [Finding(file="a.py", line=1, severity="minor", message="note")],
        13,
        4,
    )
    request_id = new_request_id()
    append_ledger_entry(result, request_id=request_id, ledger_path=path)
    entry = json.loads(path.read_text(encoding="utf-8"))
    assert entry["request_id"] == request_id
    assert entry["agent"] == "SecurityReviewer"
    assert entry["ms"] == 13
    assert entry["findings"] == 1
