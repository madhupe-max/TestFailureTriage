from defect_triage_agent.flaky_detector import FlakyDetector
from defect_triage_agent.models import TriageInput


def test_flaky_detector_flags_retry_and_timeout_signals():
    detector = FlakyDetector(threshold=0.6)
    triage_input = TriageInput(
        test_id="SearchTests::test_results_order",
        logs="Request timeout, retry succeeded on second attempt",
        metadata={"retry_count": 1, "retry_passed": True, "branch": "main", "commit": "abc123"},
    )

    assessment = detector.assess(triage_input)

    assert assessment.is_flaky is True
    assert assessment.score >= 0.6
    assert any(signal.present for signal in assessment.signals)


def test_flaky_detector_stays_low_for_deterministic_failures():
    detector = FlakyDetector(threshold=0.6)
    triage_input = TriageInput(
        test_id="CheckoutTests::test_submit_payment",
        logs="AssertionError: expected 200 got 500",
        metadata={"retry_count": 0, "retry_passed": False},
    )

    assessment = detector.assess(triage_input)

    assert assessment.is_flaky is False
    assert assessment.score < 0.6
