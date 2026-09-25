"""Structured reviewer findings."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str = Field(min_length=1)
    line: int = Field(ge=1)
    severity: Literal["critical", "major", "minor"]
    message: str = Field(min_length=1)

