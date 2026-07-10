from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from defect_triage_agent.models import TriageResult


@dataclass
class TicketingClient:
    artifacts_dir: Path = Path("artifacts")

    def create_ticket(self, result: TriageResult) -> str:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        ticket_id = f"BUG-{str(uuid4())[:8].upper()}"
        payload = {
            "ticket_id": ticket_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "test_id": result.input.test_id,
            "classification": result.classification.value,
            "confidence": result.confidence,
            "root_cause_summary": result.root_cause_summary,
            "rationale": result.rationale,
            "metadata": result.input.metadata,
        }
        with (self.artifacts_dir / "tickets.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
        return ticket_id
