from pathlib import Path

from defect_triage_agent.dashboard_data import (
    aggregate_by_day,
    aggregate_classification,
    aggregate_decision,
    build_kpi_scorecard,
    load_governance_events,
    load_kpi_targets,
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


def test_load_kpi_targets_and_build_scorecard(tmp_path):
    targets_path = tmp_path / "kpi_targets.csv"
    targets_path.write_text(
        "\n".join(
            [
                "metric,direction,unit,owner,b0,q1_target,q2_target,q2_formula",
                "regression_escape_rate,lower,defects/release,Staff SDET,6.0,5.1,4.2,B0 * 0.70",
                "mttt_hours,lower,hours,QA Platform Lead,12.0,9.0,6.0,B0 * 0.50",
                'false_failure_rate_pct,lower,percent,Test Reliability Lead,14.0,11.0,8.0,"min(B0 * 0.75, 8.0)"',
                'ai_test_yield,higher,defects/100-tests,AI Quality Engineer,1.2,1.6,2.0,"max(B0 * 1.25, 2.0)"',
                'self_heal_effectiveness_pct,higher,percent,Automation Architect,45.0,57.5,70.0,"max(B0 + 15, 70)"',
            ]
        ),
        encoding="utf-8",
    )

    targets = load_kpi_targets(targets_path)
    scorecard = build_kpi_scorecard(
        [
            {
                "timestamp": "2026-07-10T00:00:00+00:00",
                "classification": "real_defect",
                "decision": "auto_ticket",
            },
            {
                "timestamp": "2026-07-10T01:00:00+00:00",
                "classification": "flaky",
                "decision": "auto_resolve",
            },
            {
                "timestamp": "2026-07-10T02:00:00+00:00",
                "classification": "environment",
                "decision": "human_review",
            },
        ],
        targets,
    )

    assert len(targets) == 5
    by_metric = {row["metric"]: row for row in scorecard}

    false_failure = by_metric["false_failure_rate_pct"]
    assert false_failure["actual"] == 66.66666666666666
    assert false_failure["measurement_status"] == "valid"
    assert false_failure["attainment"] == "below_q1"

    assert by_metric["mttt_hours"]["measurement_status"] == "blocked"
    assert by_metric["mttt_hours"]["actual"] is None
    assert by_metric["self_heal_effectiveness_pct"]["measurement_status"] == "blocked"
