from __future__ import annotations

from dataclasses import dataclass

from defect_triage_agent.models import TriageInput


@dataclass
class ContextProvider:
    """Fetches additional context for uncertain triage outcomes."""

    def get_recent_code_changes(self, triage_input: TriageInput) -> str:
        branch = triage_input.metadata.get("branch", "unknown")
        commit = triage_input.metadata.get("commit", "unknown")
        return (
            f"Recent code changes near failing area on branch={branch}, "
            f"commit={commit}: payment retry policy was modified in checkout service."
        )

    def get_test_history(self, triage_input: TriageInput) -> str:
        return (
            f"Historical trend for {triage_input.test_id}: 6 failures in 30 days; "
            "4 after infra maintenance windows; 2 correlated with API behavior change."
        )

    def gather(self, triage_input: TriageInput) -> list[str]:
        return [
            self.get_recent_code_changes(triage_input),
            self.get_test_history(triage_input),
        ]
