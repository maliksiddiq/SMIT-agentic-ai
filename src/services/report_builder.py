"""Final report assembly and rendering."""

from __future__ import annotations

from src.hooks.run_hooks import HookMetrics
from src.models.report import FinalReport
from src.services.concurrency import ReviewerResult


def build_final_report(
    results: list[ReviewerResult],
    findings,
    *,
    metrics: list[HookMetrics] | None = None,
    remediation_triggered: bool = False,
) -> FinalReport:
    footer = metrics or [
        HookMetrics(
            agent_name=result.agent_name,
            started_at=0.0,
            ended_at=result.duration_ms / 1000,
            duration_ms=result.duration_ms,
            input_tokens=0,
            output_tokens=result.tokens_used,
            total_tokens=result.tokens_used,
        )
        for result in results
    ]
    return FinalReport(
        findings=findings,
        footer=footer,
        partial=any(result.partial for result in results),
        remediation_triggered=remediation_triggered,
    )


def render_report(report: FinalReport) -> str:
    lines = ["## Findings"]
    for finding in report.findings:
        lines.append(
            f"- **{finding.severity}** `{finding.file}:{finding.line}` — {finding.message}"
        )
    if report.partial:
        lines.append("\n> Partial review: one or more reviewers reached the turn ceiling.")
    lines.append("\n## Reviewer metrics")
    for row in report.footer:
        lines.append(
            f"- {row.agent_name}: {row.duration_ms}ms, "
            f"{row.total_tokens} tokens"
        )
    return "\n".join(lines)
