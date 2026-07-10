from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FailureClassification(str, Enum):
    REAL_DEFECT = "real_defect"
    FLAKY = "flaky"
    ENVIRONMENT = "environment"
    UNKNOWN = "unknown"


class RoutingDecision(str, Enum):
    AUTO_TICKET = "auto_ticket"
    HUMAN_REVIEW = "human_review"
    AUTO_RESOLVE = "auto_resolve"


class TriageInput(BaseModel):
    test_id: str
    suite: str | None = None
    logs: str = ""
    stack_trace: str = ""
    screenshot_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    classification: FailureClassification
    confidence: float
    rationale: str
    root_cause_summary: str


class TriageResult(BaseModel):
    input: TriageInput
    classification: FailureClassification
    confidence: float
    rationale: str
    root_cause_summary: str
    decision: RoutingDecision
    ticket_id: str | None = None
    additional_context: list[str] = Field(default_factory=list)
    attempts: int = 1
    history: list[dict[str, Any]] = Field(default_factory=list)
