from __future__ import annotations

import csv
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


def load_kpi_targets(targets_path: Path) -> list[dict[str, str]]:
    if not targets_path.exists():
        return []

    with targets_path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _safe_float(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_false_failure_rate(events: list[dict]) -> tuple[float | None, float, str]:
    total = len(events)
    if total == 0:
        return None, 0.0, "Requires classified governance events for the reporting window."

    false_failures = sum(
        1
        for event in events
        if str(event.get("classification", "")).strip() in {"flaky", "environment"}
    )
    return (false_failures / total) * 100.0, 100.0, "Derived from flaky/environment governance classifications."


def _compute_ai_test_yield(events: list[dict]) -> tuple[float | None, float, str]:
    ai_generated = [
        event
        for event in events
        if bool((event.get("metadata") or {}).get("ai_generated")) or bool(event.get("ai_generated"))
    ]
    if not ai_generated:
        return None, 0.0, "Requires ai_generated provenance on executed tests."

    defects = sum(1 for event in ai_generated if str(event.get("classification", "")).strip() == "real_defect")
    return (defects / len(ai_generated)) * 100.0, 100.0, "Defects found per 100 AI-generated tests executed."


def _compute_self_heal_effectiveness(events: list[dict]) -> tuple[float | None, float, str]:
    auto_resolved = [
        event
        for event in events
        if str(event.get("decision", "")).strip() == "auto_resolve"
    ]
    if not auto_resolved:
        return None, 0.0, "Requires heal outcome telemetry on auto-resolve decisions."

    healed = [event for event in auto_resolved if str(event.get("heal_outcome", "")).strip() == "stable_pass"]
    with_outcome = [event for event in auto_resolved if str(event.get("heal_outcome", "")).strip()]
    if not with_outcome:
        return None, 0.0, "Requires heal_outcome values such as stable_pass on auto-resolve decisions."

    return (len(healed) / len(with_outcome)) * 100.0, (len(with_outcome) / len(auto_resolved)) * 100.0, (
        "Uses recorded heal_outcome values for auto-resolve decisions."
    )


def _compute_mttt(events: list[dict]) -> tuple[float | None, float, str]:
    samples: list[float] = []
    covered = 0
    for event in events:
        triaged_at = str(event.get("timestamp", "")).strip()
        assigned_at = str(event.get("owner_assigned_at", "")).strip()
        if not triaged_at:
            continue
        if assigned_at:
            covered += 1
        try:
            start = datetime.fromisoformat(triaged_at.replace("Z", "+00:00"))
            end = datetime.fromisoformat(assigned_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        samples.append((end - start).total_seconds() / 3600.0)

    if not samples:
        return None, (covered / len(events)) * 100.0 if events else 0.0, "Requires owner_assigned_at timestamps on triage events."

    return sum(samples) / len(samples), (covered / len(events)) * 100.0, "Computed from triage timestamp to owner assignment."


def _compute_regression_escape_rate(events: list[dict]) -> tuple[float | None, float, str]:
    releases = [event for event in events if str(event.get("release_id", "")).strip()]
    if not releases:
        return None, 0.0, "Requires release-linked production defect events with release_id."

    by_release: dict[str, int] = defaultdict(int)
    for event in releases:
        if bool(event.get("escaped_defect")):
            by_release[str(event.get("release_id"))] += 1

    if not by_release:
        return 0.0, 100.0, "No escaped defects recorded for the sampled releases."

    return sum(by_release.values()) / len(by_release), 100.0, "Average escaped defects per release across release-linked events."


KPI_COMPUTATIONS: dict[str, callable] = {
    "regression_escape_rate": _compute_regression_escape_rate,
    "mttt_hours": _compute_mttt,
    "false_failure_rate_pct": _compute_false_failure_rate,
    "ai_test_yield": _compute_ai_test_yield,
    "self_heal_effectiveness_pct": _compute_self_heal_effectiveness,
}


def _measurement_status(completeness_pct: float, actual: float | None) -> str:
    if actual is None:
        return "blocked"
    if completeness_pct >= 95.0:
        return "valid"
    return "directional"


def _attainment_status(direction: str, actual: float | None, q1_target: float | None, q2_target: float | None) -> str:
    if actual is None or q1_target is None or q2_target is None:
        return "unavailable"

    if direction == "lower":
        if actual <= q2_target:
            return "meets_q2"
        if actual <= q1_target:
            return "meets_q1"
        return "below_q1"

    if direction == "higher":
        if actual >= q2_target:
            return "meets_q2"
        if actual >= q1_target:
            return "meets_q1"
        return "below_q1"

    return "unavailable"


def build_kpi_scorecard(events: list[dict], targets: list[dict[str, str]]) -> list[dict[str, str | float]]:
    rows: list[dict[str, str | float]] = []
    for target in targets:
        metric = str(target.get("metric", "")).strip()
        compute = KPI_COMPUTATIONS.get(metric)
        if compute is None:
            continue

        actual, completeness_pct, note = compute(events)
        q1_target = _safe_float(target.get("q1_target"))
        q2_target = _safe_float(target.get("q2_target"))
        direction = str(target.get("direction", "")).strip()
        status = _measurement_status(completeness_pct, actual)

        rows.append(
            {
                "metric": metric,
                "owner": str(target.get("owner", "")).strip(),
                "direction": direction,
                "unit": str(target.get("unit", "")).strip(),
                "baseline_b0": _safe_float(target.get("b0")),
                "q1_target": q1_target,
                "q2_target": q2_target,
                "actual": actual,
                "attainment": _attainment_status(direction, actual, q1_target, q2_target),
                "measurement_status": status,
                "data_completeness_pct": completeness_pct,
                "note": note,
            }
        )

    return rows
