from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from defect_triage_agent.flaky_history import append_flaky_assessment
from defect_triage_agent.models import TriageInput


@dataclass
class FlakySignal:
    name: str
    weight: float
    present: bool
    evidence: str


@dataclass
class FlakyAssessment:
    is_flaky: bool
    score: float
    rationale: str
    signals: list[FlakySignal] = field(default_factory=list)


@dataclass
class FlakyDetector:
    """Heuristic flakiness detector based on repeated-run and symptom signals."""

    threshold: float = 0.7

    def assess(self, triage_input: TriageInput, additional_context: list[str] | None = None) -> FlakyAssessment:
        additional_context = additional_context or []
        text = " ".join(
            [
                triage_input.logs,
                triage_input.stack_trace,
                " ".join(additional_context),
            ]
        ).lower()
        metadata = triage_input.metadata

        signals = [
            self._retry_signal(text, metadata),
            self._intermittent_signal(text),
            self._timeout_signal(text),
            self._ordering_signal(text),
            self._history_signal(metadata),
        ]

        score = self._normalize(sum(signal.weight for signal in signals if signal.present))
        is_flaky = score >= self.threshold
        rationale = self._build_rationale(score, signals, metadata)
        assessment = FlakyAssessment(is_flaky=is_flaky, score=score, rationale=rationale, signals=signals)
        append_flaky_assessment(triage_input, assessment)
        return assessment

    def _retry_signal(self, text: str, metadata: dict[str, Any]) -> FlakySignal:
        retry_count = self._coerce_int(metadata.get("retry_count") or metadata.get("retries") or 0)
        retry_passed = bool(metadata.get("retry_passed"))
        log_retry_pass = any(
            keyword in text
            for keyword in ["retry succeeded", "passed on retry", "passed after retry", "second attempt passed"]
        )
        present = (retry_count > 0 and retry_passed) or log_retry_pass
        weight = 0.45 if present else 0.0
        evidence = f"retry_count={retry_count}, retry_passed={retry_passed}, log_retry_pass={log_retry_pass}"
        return FlakySignal("retry_pass", weight, present, evidence)

    def _intermittent_signal(self, text: str) -> FlakySignal:
        keywords = ["intermittent", "retry succeeded", "passed on retry", "flaky", "non-deterministic"]
        present = any(keyword in text for keyword in keywords)
        weight = 0.25 if present else 0.0
        evidence = "matched intermittent keywords" if present else "no intermittent keywords"
        return FlakySignal("intermittent_text", weight, present, evidence)

    def _timeout_signal(self, text: str) -> FlakySignal:
        keywords = ["timeout", "timed out", "connection reset", "request aborted", "read timed out"]
        present = any(keyword in text for keyword in keywords)
        weight = 0.2 if present else 0.0
        evidence = "matched timeout-style symptoms" if present else "no timeout symptoms"
        return FlakySignal("timeout_symptom", weight, present, evidence)

    def _ordering_signal(self, text: str) -> FlakySignal:
        keywords = ["order-dependent", "race condition", "shared state", "test order", "ordering"]
        present = any(keyword in text for keyword in keywords)
        weight = 0.15 if present else 0.0
        evidence = "matched ordering/shared-state symptoms" if present else "no ordering symptoms"
        return FlakySignal("ordering_or_state", weight, present, evidence)

    def _history_signal(self, metadata: dict[str, Any]) -> FlakySignal:
        recent_outcomes = metadata.get("recent_outcomes")
        present = False
        weight = 0.0
        evidence = "no recent outcome history"

        if isinstance(recent_outcomes, list) and recent_outcomes:
            normalized = [str(item).lower() for item in recent_outcomes]
            passes = sum(1 for item in normalized if item == "pass")
            fails = sum(1 for item in normalized if item == "fail")
            mixed_history = passes > 0 and fails > 0
            present = mixed_history and len(normalized) >= 3
            if present:
                weight = 0.2
                evidence = f"recent_outcomes={normalized}"
            else:
                evidence = f"recent_outcomes={normalized}"

        return FlakySignal("mixed_history", weight, present, evidence)

    def _build_rationale(self, score: float, signals: list[FlakySignal], metadata: dict[str, Any]) -> str:
        active = [signal.name for signal in signals if signal.present]
        if not active:
            return "No flaky-test indicators detected."
        branch = metadata.get("branch", "unknown")
        commit = metadata.get("commit", "unknown")
        return (
            f"Detected flaky indicators {active} for branch={branch}, commit={commit}; "
            f"flakiness score={score:.2f}."
        )

    def _normalize(self, score: float) -> float:
        return max(0.0, min(1.0, score))

    def _coerce_int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
