"""Merge specialist exposed as an agents-as-tool."""

from __future__ import annotations

from agents import Agent

from src.agents_.base_reviewer import create_gemini_model
from src.config.settings import Settings
from src.models.report import MergedReport
from src.services.concurrency import ReviewerResult


def merge_findings(results: list[ReviewerResult]) -> MergedReport:
    """Deduplicate findings and order them by severity."""

    unique: dict[tuple[str, int, str], object] = {}
    rank = {"critical": 0, "major": 1, "minor": 2}
    for result in results:
        for finding in result.findings:
            unique.setdefault((finding.file, finding.line, finding.message), finding)
    findings = sorted(
        unique.values(),
        key=lambda finding: (rank[finding.severity], finding.file, finding.line),
    )
    return MergedReport(findings=findings)


def build_merge_specialist(settings: Settings) -> Agent:
    return Agent(
        name="MergeSpecialist",
        model=create_gemini_model(settings),
        instructions=(
            "Deduplicate the supplied reviewer findings and order them by "
            "critical, major, then minor severity."
        ),
        output_type=MergedReport,
    )


def merge_as_tool(settings: Settings):
    """Expose MergeSpecialist through the SDK's agents-as-tools API."""

    return build_merge_specialist(settings).as_tool(
        tool_name="merge_findings",
        tool_description=(
            "Deduplicate reviewer findings and order them critical, major, minor."
        ),
    )
