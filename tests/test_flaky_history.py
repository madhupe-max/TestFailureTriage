from pathlib import Path

from defect_triage_agent.flaky_history import (
    aggregate_flaky_by_day,
    flaky_summary,
    load_flaky_assessments,
    top_flaky_tests,
)


def test_load_flaky_assessments_handles_missing_file(tmp_path):
    records = load_flaky_assessments(tmp_path / "missing.jsonl")
    assert records == []


def test_flaky_history_aggregations(tmp_path):
    history_path = tmp_path / "flaky_assessments.jsonl"
    history_path.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-07-10T00:00:00+00:00","test_id":"A","is_flaky":true,"score":0.9}',
                '{"timestamp":"2026-07-10T01:00:00+00:00","test_id":"A","is_flaky":true,"score":0.8}',
                '{"timestamp":"2026-07-11T00:00:00+00:00","test_id":"B","is_flaky":false,"score":0.3}',
            ]
        ),
        encoding="utf-8",
    )

    records = load_flaky_assessments(history_path)
    by_day = aggregate_flaky_by_day(records)
    assert by_day == [
        {"day": "2026-07-10", "assessments": 2, "flaky": 2, "flaky_rate": 1.0},
        {"day": "2026-07-11", "assessments": 1, "flaky": 0, "flaky_rate": 0.0},
    ]

    top_tests = top_flaky_tests(records)
    assert top_tests == [{"test_id": "A", "count": 2}]

    summary = flaky_summary(records)
    assert summary["total_assessments"] == 3.0
    assert summary["flaky_rate"] == 2 / 3
    assert 0.0 <= summary["average_score"] <= 1.0
