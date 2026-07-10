from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from defect_triage_agent.dashboard_data import (
    aggregate_by_day,
    aggregate_classification,
    aggregate_decision,
    load_governance_events,
    summary_metrics,
)

st.set_page_config(page_title="Defect Triage Governance Dashboard", layout="wide")
st.title("Defect Triage Governance Dashboard")
st.caption("Trend visibility for triage outcomes, confidence, and routing decisions")

artifacts_dir = Path("artifacts")
events_path = artifacts_dir / "governance_events.jsonl"

events = load_governance_events(events_path)
metrics = summary_metrics(events)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Triaged Failures", int(metrics["total_events"]))
c2.metric("Average Confidence", f"{metrics['avg_confidence']:.2%}")
c3.metric("Auto-Ticket Rate", f"{metrics['auto_ticket_rate']:.2%}")
c4.metric("Human-Review Rate", f"{metrics['human_review_rate']:.2%}")

if not events:
    st.info("No governance events found yet. Run triage to generate artifacts/governance_events.jsonl.")
    st.stop()

line_df = pd.DataFrame(aggregate_by_day(events))
class_df = pd.DataFrame(aggregate_classification(events))
decision_df = pd.DataFrame(aggregate_decision(events))
raw_df = pd.DataFrame(events)

col_left, col_right = st.columns(2)
with col_left:
    st.subheader("Failures Triaged Over Time")
    fig_line = px.line(line_df, x="day", y="count", markers=True)
    fig_line.update_layout(margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_line, width="stretch")

with col_right:
    st.subheader("Classification Distribution")
    fig_class = px.pie(class_df, names="classification", values="count", hole=0.45)
    fig_class.update_layout(margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_class, width="stretch")

st.subheader("Routing Decisions")
fig_decision = px.bar(decision_df, x="decision", y="count", text_auto=True)
fig_decision.update_layout(margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig_decision, width="stretch")

st.subheader("Recent Events")
st.dataframe(raw_df.sort_values(by="timestamp", ascending=False), width="stretch")
