from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def _parse_ts_day(timestamp: str) -> str:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return "unknown"


def load_governance_events(events_path: Path) -> list[dict]:
    if not events_path.exists():
        return []

    events: list[dict] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def aggregate_by_day(events: list[dict]) -> list[dict]:
    by_day: dict[str, int] = defaultdict(int)
    for event in events:
        day = _parse_ts_day(str(event.get("timestamp", "")))
        by_day[day] += 1

    return [
        {"day": day, "count": count}
        for day, count in sorted(by_day.items(), key=lambda item: item[0])
    ]


def aggregate_classification(events: list[dict]) -> list[dict]:
    counts = Counter(str(event.get("classification", "unknown")) for event in events)
    return [
        {"classification": label, "count": count}
        for label, count in sorted(counts.items(), key=lambda item: item[0])
    ]


def aggregate_decision(events: list[dict]) -> list[dict]:
    counts = Counter(str(event.get("decision", "unknown")) for event in events)
    return [
        {"decision": label, "count": count}
        for label, count in sorted(counts.items(), key=lambda item: item[0])
    ]


def summary_metrics(events: list[dict]) -> dict[str, float]:
    total = len(events)
    if total == 0:
        return {
            "total_events": 0,
            "avg_confidence": 0.0,
            "auto_ticket_rate": 0.0,
            "human_review_rate": 0.0,
        }

    avg_conf = sum(float(event.get("confidence", 0.0)) for event in events) / total
    auto_ticket = sum(1 for event in events if str(event.get("decision")) == "auto_ticket")
    human_review = sum(1 for event in events if str(event.get("decision")) == "human_review")

    return {
        "total_events": float(total),
        "avg_confidence": avg_conf,
        "auto_ticket_rate": auto_ticket / total,
        "human_review_rate": human_review / total,
    }
