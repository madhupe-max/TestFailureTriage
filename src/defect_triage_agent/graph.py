from __future__ import annotations

import os
from dataclasses import dataclass

from langgraph.graph import END, START, StateGraph

from defect_triage_agent.context import ContextProvider
from defect_triage_agent.dashboard import GovernanceDashboardClient
from defect_triage_agent.llm import FailureClassifier
from defect_triage_agent.models import RoutingDecision, TriageInput, TriageResult
from defect_triage_agent.state import TriageState
from defect_triage_agent.ticketing import TicketingClient


@dataclass
class DefectTriageAgent:
    classifier: FailureClassifier
    context_provider: ContextProvider
    ticketing_client: TicketingClient
    dashboard_client: GovernanceDashboardClient

    def __init__(self) -> None:
        self.classifier = FailureClassifier()
        self.context_provider = ContextProvider()
        self.ticketing_client = TicketingClient()
        self.dashboard_client = GovernanceDashboardClient()
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(TriageState)
        graph.add_node("ingest_failure", self.ingest_failure)
        graph.add_node("classify_failure", self.classify_failure)
        graph.add_node("gather_more_context", self.gather_more_context)
        graph.add_node("decide_routing", self.decide_routing)
        graph.add_node("execute_routing", self.execute_routing)
        graph.add_node("update_dashboard", self.update_dashboard)

        graph.add_edge(START, "ingest_failure")
        graph.add_edge("ingest_failure", "classify_failure")
        graph.add_conditional_edges(
            "classify_failure",
            self.next_after_classification,
            {
                "gather_more_context": "gather_more_context",
                "decide_routing": "decide_routing",
            },
        )
        graph.add_edge("gather_more_context", "classify_failure")
        graph.add_edge("decide_routing", "execute_routing")
        graph.add_edge("execute_routing", "update_dashboard")
        graph.add_edge("update_dashboard", END)

        return graph.compile()

    def run(self, triage_input: TriageInput, max_attempts: int = 2) -> TriageResult:
        auto_ticket_conf = float(os.getenv("AUTO_TICKET_CONFIDENCE", "0.82"))
        human_review_conf = float(os.getenv("HUMAN_REVIEW_CONFIDENCE", "0.65"))

        initial: TriageState = {
            "triage_input": triage_input,
            "classification": "unknown",  # type: ignore[assignment]
            "confidence": 0.0,
            "rationale": "",
            "root_cause_summary": "",
            "additional_context": [],
            "history": [],
            "decision": "human_review",  # type: ignore[assignment]
            "ticket_id": None,
            "attempt": 1,
            "max_attempts": max(1, max_attempts),
            "auto_ticket_confidence": auto_ticket_conf,
            "human_review_confidence": human_review_conf,
            "needs_more_context": False,
        }
        final_state = self._graph.invoke(initial)

        return TriageResult(
            input=final_state["triage_input"],
            classification=final_state["classification"],
            confidence=final_state["confidence"],
            rationale=final_state["rationale"],
            root_cause_summary=final_state["root_cause_summary"],
            decision=final_state["decision"],
            ticket_id=final_state["ticket_id"],
            additional_context=final_state["additional_context"],
            attempts=final_state["attempt"],
            history=final_state["history"],
        )

    def ingest_failure(self, state: TriageState) -> TriageState:
        return state

    def classify_failure(self, state: TriageState) -> TriageState:
        result = self.classifier.classify(state["triage_input"], state["additional_context"])
        history = list(state["history"])
        history.append(
            {
                "attempt": state["attempt"],
                "classification": result.classification.value,
                "confidence": result.confidence,
                "rationale": result.rationale,
            }
        )

        needs_more_context = (
            result.confidence < state["human_review_confidence"]
            and state["attempt"] < state["max_attempts"]
        )

        state["classification"] = result.classification
        state["confidence"] = result.confidence
        state["rationale"] = result.rationale
        state["root_cause_summary"] = result.root_cause_summary
        state["history"] = history
        state["needs_more_context"] = needs_more_context
        return state

    def next_after_classification(self, state: TriageState) -> str:
        if state["needs_more_context"]:
            return "gather_more_context"
        return "decide_routing"

    def gather_more_context(self, state: TriageState) -> TriageState:
        context = self.context_provider.gather(state["triage_input"])
        state["additional_context"] = state["additional_context"] + context
        state["attempt"] += 1
        return state

    def decide_routing(self, state: TriageState) -> TriageState:
        if state["confidence"] < state["human_review_confidence"] or state["classification"].value == "unknown":
            state["decision"] = RoutingDecision.HUMAN_REVIEW
            return state

        if (
            state["classification"].value == "real_defect"
            and state["confidence"] >= state["auto_ticket_confidence"]
        ):
            state["decision"] = RoutingDecision.AUTO_TICKET
            return state

        state["decision"] = RoutingDecision.AUTO_RESOLVE
        return state

    def execute_routing(self, state: TriageState) -> TriageState:
        result = TriageResult(
            input=state["triage_input"],
            classification=state["classification"],
            confidence=state["confidence"],
            rationale=state["rationale"],
            root_cause_summary=state["root_cause_summary"],
            decision=state["decision"],
            ticket_id=state["ticket_id"],
            additional_context=state["additional_context"],
            attempts=state["attempt"],
            history=state["history"],
        )

        if state["decision"] == RoutingDecision.AUTO_TICKET:
            state["ticket_id"] = self.ticketing_client.create_ticket(result)
        elif state["decision"] == RoutingDecision.HUMAN_REVIEW:
            state["ticket_id"] = None
        else:
            state["ticket_id"] = None

        return state

    def update_dashboard(self, state: TriageState) -> TriageState:
        result = TriageResult(
            input=state["triage_input"],
            classification=state["classification"],
            confidence=state["confidence"],
            rationale=state["rationale"],
            root_cause_summary=state["root_cause_summary"],
            decision=state["decision"],
            ticket_id=state["ticket_id"],
            additional_context=state["additional_context"],
            attempts=state["attempt"],
            history=state["history"],
        )
        self.dashboard_client.publish_event(result)
        return state
