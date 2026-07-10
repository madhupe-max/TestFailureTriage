from pathlib import Path

from defect_triage_agent.dashboard_data import (
    aggregate_by_day,
    aggregate_classification,
    aggregate_decision,
    load_governance_events,
    summary_metrics,
)


def test_load_governance_events_handles_missing_file(tmp_path):
    events = load_governance_events(tmp_path / "missing.jsonl")
    assert events == []


def test_aggregations_and_summary(tmp_path):
    events_path = tmp_path / "governance_events.jsonl"
    events_path.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-07-10T00:00:00+00:00","classification":"real_defect","decision":"auto_ticket","confidence":0.9}',
                '{"timestamp":"2026-07-10T01:00:00+00:00","classification":"flaky","decision":"auto_resolve","confidence":0.8}',
                '{"timestamp":"2026-07-11T01:00:00+00:00","classification":"unknown","decision":"human_review","confidence":0.4}',
            ]
        ),
        encoding="utf-8",
    )

    events = load_governance_events(events_path)

    by_day = aggregate_by_day(events)
    assert by_day == [{"day": "2026-07-10", "count": 2}, {"day": "2026-07-11", "count": 1}]

    by_class = aggregate_classification(events)
    assert {item["classification"] for item in by_class} == {"real_defect", "flaky", "unknown"}

    by_decision = aggregate_decision(events)
    assert {item["decision"] for item in by_decision} == {"auto_ticket", "auto_resolve", "human_review"}

    metrics = summary_metrics(events)
    assert metrics["total_events"] == 3.0
    assert 0.0 <= metrics["avg_confidence"] <= 1.0
    assert metrics["auto_ticket_rate"] == 1 / 3
    assert metrics["human_review_rate"] == 1 / 3
