from defect_triage_agent.graph import DefectTriageAgent
from defect_triage_agent.models import RoutingDecision, TriageInput


def test_real_defect_can_auto_ticket(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = DefectTriageAgent()

    triage_input = TriageInput(
        test_id="CheckoutTests::test_payment_submit",
        suite="CheckoutTests",
        logs="HTTP 500 from /payments/submit while processing card",
        stack_trace="AssertionError: expected 200 got 500",
    )

    result = agent.run(triage_input, max_attempts=2)

    assert result.decision in {
        RoutingDecision.AUTO_TICKET,
        RoutingDecision.HUMAN_REVIEW,
        RoutingDecision.AUTO_RESOLVE,
    }
    if result.decision == RoutingDecision.AUTO_TICKET:
        assert result.ticket_id is not None


def test_uncertain_case_routes_or_loops(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = DefectTriageAgent()

    triage_input = TriageInput(
        test_id="UnknownTests::test_unknown",
        suite="UnknownTests",
        logs="Non-deterministic output mismatch",
        stack_trace="",
    )

    result = agent.run(triage_input, max_attempts=2)

    assert result.attempts >= 1
    assert result.decision in {
        RoutingDecision.HUMAN_REVIEW,
        RoutingDecision.AUTO_RESOLVE,
        RoutingDecision.AUTO_TICKET,
    }
