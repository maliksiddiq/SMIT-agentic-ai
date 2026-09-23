from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True)
class StudentProfile:
    name: str
    roll_no: str
    course_id: str
    tier: Literal["regular", "scholarship"] = "regular"
    open_tickets: int = 0


class Ticket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["assignment", "career", "admin"]
    summary: str
    next_step: str
    resolved: bool
    escalate: bool

