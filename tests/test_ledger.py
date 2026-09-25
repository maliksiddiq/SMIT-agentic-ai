import json

from src.config import settings
from src.runners.ledger_runner import new_request_id
from src.services.concurrency import ReviewerResult


def test_single_registration_point_enables_and_disables_ledger(tmp_path, monkeypatch) -> None:
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.chdir(tmp_path)
    result = ReviewerResult("TestsReviewer", [], 5, 3)
    settings.register_ledger(False)
    settings.record_run(result, request_id=new_request_id())
    assert not ledger.exists()
    settings.register_ledger(True)
    settings.record_run(result, request_id=new_request_id())
    entries = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(entries) == 1
    assert entries[0]["agent"] == "TestsReviewer"
