from __future__ import annotations

from typing import Any, TypedDict

from defect_triage_agent.models import FailureClassification, RoutingDecision, TriageInput


class TriageState(TypedDict):
    triage_input: TriageInput
    classification: FailureClassification
    confidence: float
    rationale: str
    root_cause_summary: str
    additional_context: list[str]
    history: list[dict[str, Any]]
    decision: RoutingDecision
    ticket_id: str | None
    attempt: int
    max_attempts: int
    auto_ticket_confidence: float
    human_review_confidence: float
    needs_more_context: bool
