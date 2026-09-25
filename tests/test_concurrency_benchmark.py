import asyncio
from time import monotonic

from src.context.review_context import ReviewContext
from src.services import concurrency
from src.services.concurrency import ReviewerResult


def test_concurrent_and_sequential_wall_clock_benchmark(monkeypatch, capsys) -> None:
    async def fake_run(agent, *, context, files, max_turns):
        await asyncio.sleep(0.03)
        return ReviewerResult(agent, [], 30, 0)

    monkeypatch.setattr(concurrency, "run_one_reviewer", fake_run)
    context = ReviewContext("repo", "Python", "default")
    agents = ("security", "tests", "style")

    started = monotonic()
    asyncio.run(
        concurrency.run_reviewers_concurrently(
            agents, context=context, files=["a.py"], max_turns=8
        )
    )
    concurrent_seconds = monotonic() - started

    started = monotonic()
    asyncio.run(
        concurrency.run_reviewers_sequentially(
            agents, context=context, files=["a.py"], max_turns=8
        )
    )
    sequential_seconds = monotonic() - started
    print(f"concurrent={concurrent_seconds:.3f}s sequential={sequential_seconds:.3f}s")
    assert concurrent_seconds < sequential_seconds
    assert "concurrent=" in capsys.readouterr().out
