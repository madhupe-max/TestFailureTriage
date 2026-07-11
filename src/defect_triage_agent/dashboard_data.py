from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import streamlit as st


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


@st.cache_data(ttl=60)
def load_flaky_assessment_records(history_path: Path) -> list[dict]:
    if not history_path.exists():
        return []

    records: list[dict] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


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


def aggregate_flaky_rate_by_day(records: list[dict]) -> list[dict]:
    by_day: dict[str, dict[str, int]] = defaultdict(lambda: {"assessments": 0, "flaky": 0})
    for record in records:
        day = _parse_ts_day(str(record.get("timestamp", "")))
        by_day[day]["assessments"] += 1
        if bool(record.get("is_flaky")):
            by_day[day]["flaky"] += 1

    return [
        {
            "day": day,
            "assessments": values["assessments"],
            "flaky": values["flaky"],
            "flaky_rate": values["flaky"] / values["assessments"] if values["assessments"] else 0.0,
        }
        for day, values in sorted(by_day.items(), key=lambda item: item[0])
    ]


def top_flaky_tests(records: list[dict], limit: int = 10) -> list[dict]:
    counts = Counter(str(record.get("test_id", "unknown")) for record in records if bool(record.get("is_flaky")))
    return [{"test_id": test_id, "count": count} for test_id, count in counts.most_common(limit)]


def flaky_summary(records: list[dict]) -> dict[str, float]:
    total = len(records)
    flaky = sum(1 for record in records if bool(record.get("is_flaky")))
    average_score = sum(float(record.get("score", 0.0)) for record in records) / total if total else 0.0
    return {
        "total_assessments": float(total),
        "flaky_rate": flaky / total if total else 0.0,
        "average_score": average_score,
    }
