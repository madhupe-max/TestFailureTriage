from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from defect_triage_agent.dashboard_data import (
    aggregate_flaky_rate_by_day,
    aggregate_by_day,
    aggregate_classification,
    aggregate_decision,
    flaky_summary,
    load_governance_events,
    load_flaky_assessment_records,
    top_flaky_tests,
    summary_metrics,
)

st.set_page_config(page_title="Defect Triage Governance Dashboard", layout="wide")
st.title("Defect triage governance dashboard")
st.caption("Trend visibility for triage outcomes, confidence, routing decisions, and flaky-test drift")

artifacts_dir = Path("artifacts")
events_path = artifacts_dir / "governance_events.jsonl"
flaky_history_path = artifacts_dir / "flaky_assessments.jsonl"

events = load_governance_events(events_path)
flaky_records = load_flaky_assessment_records(flaky_history_path)
metrics = summary_metrics(events)
flaky_metrics = flaky_summary(flaky_records)

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
