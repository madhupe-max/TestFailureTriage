from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from defect_triage_agent.models import TriageInput


DEFAULT_FLAKY_HISTORY = Path("artifacts/flaky_assessments.jsonl")


def append_flaky_assessment(
    triage_input: TriageInput,
    assessment: Any,
    history_path: Path = DEFAULT_FLAKY_HISTORY,
) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_id": triage_input.test_id,
        "suite": triage_input.suite,
        "score": assessment.score,
        "is_flaky": assessment.is_flaky,
        "rationale": assessment.rationale,
        "signals": [signal_to_dict(signal) for signal in assessment.signals],
        "metadata": triage_input.metadata,
    }
    with history_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(record) + "\n")


def load_flaky_assessments(history_path: Path = DEFAULT_FLAKY_HISTORY) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def aggregate_flaky_by_day(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, dict[str, float]] = defaultdict(lambda: {"assessments": 0, "flaky": 0})
    for record in records:
        day = _parse_day(str(record.get("timestamp", "")))
        by_day[day]["assessments"] += 1
        if bool(record.get("is_flaky")):
            by_day[day]["flaky"] += 1

    series = []
    for day, values in sorted(by_day.items(), key=lambda item: item[0]):
        assessments = int(values["assessments"])
        flaky = int(values["flaky"])
        series.append(
            {
                "day": day,
                "assessments": assessments,
                "flaky": flaky,
                "flaky_rate": flaky / assessments if assessments else 0.0,
            }
        )
    return series


def top_flaky_tests(records: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    counts = Counter(str(record.get("test_id", "unknown")) for record in records if bool(record.get("is_flaky")))
    return [{"test_id": test_id, "count": count} for test_id, count in counts.most_common(limit)]


def flaky_summary(records: list[dict[str, Any]]) -> dict[str, float]:
    total = len(records)
    flaky = sum(1 for record in records if bool(record.get("is_flaky")))
    average_score = sum(float(record.get("score", 0.0)) for record in records) / total if total else 0.0
    return {
        "total_assessments": float(total),
        "flaky_rate": flaky / total if total else 0.0,
        "average_score": average_score,
    }


def signal_to_dict(signal: Any) -> dict[str, Any]:
    return {
        "name": signal.name,
        "weight": signal.weight,
        "present": signal.present,
        "evidence": signal.evidence,
    }


def _parse_day(timestamp: str) -> str:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return "unknown"
