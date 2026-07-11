from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from defect_triage_agent.flaky_detector import FlakyDetector
from defect_triage_agent.models import ClassificationResult, FailureClassification, TriageInput


@dataclass
class FailureClassifier:
    model: str = "gpt-4o-mini"
    flaky_detector: FlakyDetector = field(default_factory=FlakyDetector)

    def classify(self, triage_input: TriageInput, additional_context: list[str]) -> ClassificationResult:
        flaky_assessment = self.flaky_detector.assess(triage_input, additional_context)
        if flaky_assessment.is_flaky:
            return ClassificationResult(
                classification=FailureClassification.FLAKY,
                confidence=flaky_assessment.score,
                rationale=flaky_assessment.rationale,
                root_cause_summary="Likely intermittent failure driven by retry, timeout, or shared-state signals.",
            )

        llm_result = self._classify_with_llm(triage_input, additional_context)
        if llm_result is not None:
            return llm_result
        return self._classify_with_heuristics(triage_input, additional_context)

    def _classify_with_llm(
        self, triage_input: TriageInput, additional_context: list[str]
    ) -> ClassificationResult | None:
        api_key = os.getenv("OPENAI_API_KEY")
        model_name = os.getenv("OPENAI_MODEL", self.model)
        if not api_key:
            return None

        try:
            from langchain_openai import ChatOpenAI
        except Exception:
            return None

        system_prompt = (
            "You are a senior SDET triage analyst. "
            "Classify the failure as one of: real_defect, flaky, environment, unknown. "
            "Return strict JSON with keys: classification, confidence, rationale, root_cause_summary."
        )
        user_prompt = {
            "test_id": triage_input.test_id,
            "suite": triage_input.suite,
            "logs": triage_input.logs,
            "stack_trace": triage_input.stack_trace,
            "metadata": triage_input.metadata,
            "additional_context": additional_context,
        }

        llm = ChatOpenAI(model=model_name, temperature=0)
        response = llm.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt)},
            ]
        )

        try:
            payload = json.loads(response.content)
            classification = FailureClassification(payload["classification"])
            confidence = max(0.0, min(1.0, float(payload["confidence"])))
            rationale = str(payload["rationale"])
            root_cause_summary = str(payload["root_cause_summary"])
            return ClassificationResult(
                classification=classification,
                confidence=confidence,
                rationale=rationale,
                root_cause_summary=root_cause_summary,
            )
        except Exception:
            return None

    def _classify_with_heuristics(
        self, triage_input: TriageInput, additional_context: list[str]
    ) -> ClassificationResult:
        text = " ".join(
            [
                triage_input.logs.lower(),
                triage_input.stack_trace.lower(),
                " ".join(ctx.lower() for ctx in additional_context),
            ]
        )

        classification = FailureClassification.UNKNOWN
        confidence = 0.45
        rationale = "Insufficient signals in failure evidence."
        summary = "Unable to determine root cause from current artifacts."

        if any(k in text for k in ["timeout", "connection reset", "retry succeeded", "intermittent", "flaky"]):
            classification = FailureClassification.FLAKY
            confidence = 0.78
            rationale = "Intermittent or retry-driven signatures indicate flakiness."
            summary = "Failure appears intermittent and likely flaky test behavior."
        elif any(k in text for k in ["disk full", "no space left", "out of memory", "dns", "agent lost"]):
            classification = FailureClassification.ENVIRONMENT
            confidence = 0.86
            rationale = "Infrastructure/system-level errors indicate environment instability."
            summary = "Failure likely caused by CI runner or environment constraints."
        elif any(k in text for k in ["assertionerror", "nullpointer", "http 500", "expected", "regression"]):
            classification = FailureClassification.REAL_DEFECT
            confidence = 0.83
            rationale = "Application-level assertions and server errors indicate a code defect."
            summary = "Probable application regression causing deterministic test failure."

        if additional_context and classification == FailureClassification.UNKNOWN:
            confidence = 0.62
            rationale = "Additional context improved signal, but confidence remains moderate."
            summary = "Partial correlation found in recent code/test trends; needs review."

        return ClassificationResult(
            classification=classification,
            confidence=confidence,
            rationale=rationale,
            root_cause_summary=summary,
        )
