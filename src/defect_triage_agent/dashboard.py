from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from defect_triage_agent.models import TriageResult


@dataclass
class GovernanceDashboardClient:
    artifacts_dir: Path = Path("artifacts")

    def publish_event(self, result: TriageResult) -> None:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "test_id": result.input.test_id,
            "suite": result.input.suite,
            "classification": result.classification.value,
            "confidence": result.confidence,
            "decision": result.decision.value,
            "ticket_id": result.ticket_id,
            "attempts": result.attempts,
        }
        with (self.artifacts_dir / "governance_events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
