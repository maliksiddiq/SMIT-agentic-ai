"""Merged and final report models."""

from pydantic import BaseModel, ConfigDict

from src.hooks.run_hooks import HookMetrics
from src.models.finding import Finding


class MergedReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[Finding]


class RemediationHandoffInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    triggering_finding: Finding
    all_findings: list[Finding]


class FinalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[Finding]
    footer: list[HookMetrics]
    partial: bool = False
    remediation_triggered: bool = False
