from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from defect_triage_agent.dashboard_data import (
    aggregate_flaky_rate_by_day,
    aggregate_by_day,
    aggregate_classification,
    aggregate_decision,
    build_kpi_scorecard,
    flaky_summary,
    load_governance_events,
    load_flaky_assessment_records,
    load_kpi_targets,
    top_flaky_tests,
    summary_metrics,
)

st.set_page_config(page_title="Defect Triage Governance Dashboard", layout="wide")
st.title("Defect triage governance dashboard")
st.caption("Trend visibility for triage outcomes, confidence, routing decisions, and flaky-test drift")

artifacts_dir = Path("artifacts")
events_path = artifacts_dir / "governance_events.jsonl"
flaky_history_path = artifacts_dir / "flaky_assessments.jsonl"
targets_path = artifacts_dir / "kpi_targets.csv"

events = load_governance_events(events_path)
flaky_records = load_flaky_assessment_records(flaky_history_path)
kpi_targets = load_kpi_targets(targets_path)
kpi_scorecard = pd.DataFrame(build_kpi_scorecard(events, kpi_targets))
metrics = summary_metrics(events)
flaky_metrics = flaky_summary(flaky_records)


def _format_metric_value(value: object, unit: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    if unit == "percent":
        return f"{float(value):.2f}%"
    return f"{float(value):.2f}"

with st.container(horizontal=True):
    st.metric("triaged failures", int(metrics["total_events"]), border=True)
    st.metric("average confidence", f"{metrics['avg_confidence']:.2%}", border=True)
    st.metric("auto-ticket rate", f"{metrics['auto_ticket_rate']:.2%}", border=True)
    st.metric("flaky assessments", int(flaky_metrics["total_assessments"]), border=True)

if not events and not flaky_records:
    st.info("No governance or flaky-history records found yet. Run triage or flaky analysis to generate artifacts.")
    st.stop()

line_df = pd.DataFrame(aggregate_by_day(events))
class_df = pd.DataFrame(aggregate_classification(events))
decision_df = pd.DataFrame(aggregate_decision(events))
flaky_trend_df = pd.DataFrame(aggregate_flaky_rate_by_day(flaky_records))
top_flaky_df = pd.DataFrame(top_flaky_tests(flaky_records))
raw_df = pd.DataFrame(events)

with st.container(border=True):
    st.subheader("KPI scorecard")
    if not kpi_scorecard.empty:
        highlighted = kpi_scorecard[kpi_scorecard["measurement_status"] == "valid"]
        directional = kpi_scorecard[kpi_scorecard["measurement_status"] == "directional"]
        blocked = kpi_scorecard[kpi_scorecard["measurement_status"] == "blocked"]

        with st.container(horizontal=True):
            st.metric("trusted KPIs", int(len(highlighted)), border=True)
            st.metric("directional KPIs", int(len(directional)), border=True)
            st.metric("blocked KPIs", int(len(blocked)), border=True)
            st.metric(
                "false failure rate",
                _format_metric_value(
                    kpi_scorecard.loc[
                        kpi_scorecard["metric"] == "false_failure_rate_pct", "actual"
                    ].iloc[0]
                    if not kpi_scorecard.loc[kpi_scorecard["metric"] == "false_failure_rate_pct"].empty
                    else None,
                    "percent",
                ),
                border=True,
            )

        display_df = kpi_scorecard.copy()
        for column in ["baseline_b0", "q1_target", "q2_target", "actual", "data_completeness_pct"]:
            display_df[column] = display_df[column].map(lambda value: None if pd.isna(value) else float(value))

        st.dataframe(
            display_df,
            hide_index=True,
            column_config={
                "metric": "Metric",
                "owner": "Owner",
                "direction": "Direction",
                "unit": "Unit",
                "baseline_b0": st.column_config.NumberColumn("Baseline", format="%.2f"),
                "q1_target": st.column_config.NumberColumn("Q+1 target", format="%.2f"),
                "q2_target": st.column_config.NumberColumn("Q+2 target", format="%.2f"),
                "actual": st.column_config.NumberColumn("Current", format="%.2f"),
                "attainment": "Target status",
                "measurement_status": "Measurement status",
                "data_completeness_pct": st.column_config.NumberColumn("Completeness %", format="%.1f"),
                "note": "Evidence",
            },
        )
    else:
        st.info("No KPI targets found yet. Generate artifacts/kpi_targets.csv to populate the scorecard.")

col_left, col_right = st.columns(2)
with col_left:
    with st.container(border=True):
        st.subheader("Failures triaged over time")
        if not line_df.empty:
            st.line_chart(line_df, x="day", y="count")
        else:
            st.info("No triage events yet.")

with col_right:
    with st.container(border=True):
        st.subheader("Flaky rate over time")
        if not flaky_trend_df.empty:
            st.line_chart(flaky_trend_df, x="day", y="flaky_rate")
        else:
            st.info("No flaky assessments yet.")

col_left, col_right = st.columns(2)
with col_left:
    with st.container(border=True):
        st.subheader("Classification distribution")
        if not class_df.empty:
            st.bar_chart(class_df, x="classification", y="count")
        else:
            st.info("No classification data yet.")

with col_right:
    with st.container(border=True):
        st.subheader("Routing decisions")
        if not decision_df.empty:
            st.bar_chart(decision_df, x="decision", y="count")
        else:
            st.info("No routing data yet.")

col_left, col_right = st.columns(2)
with col_left:
    with st.container(border=True):
        st.subheader("Top flaky tests")
        if not top_flaky_df.empty:
            st.bar_chart(top_flaky_df, x="test_id", y="count")
        else:
            st.info("No flaky detections yet.")

with col_right:
    with st.container(border=True):
        st.subheader("Flaky detector summary")
        st.metric("flaky rate", f"{flaky_metrics['flaky_rate']:.2%}")
        st.metric("average flaky score", f"{flaky_metrics['average_score']:.2f}")

with st.container(border=True):
    st.subheader("Recent governance events")
    st.dataframe(raw_df.sort_values(by="timestamp", ascending=False), hide_index=True)
