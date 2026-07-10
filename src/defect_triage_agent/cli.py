from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich import print

from defect_triage_agent.graph import DefectTriageAgent
from defect_triage_agent.models import TriageInput

app = typer.Typer(help="AI-driven defect triage agent")


def _print_result(result):
    print(
        {
            "test_id": result.input.test_id,
            "classification": result.classification.value,
            "confidence": round(result.confidence, 3),
            "decision": result.decision.value,
            "ticket_id": result.ticket_id,
            "attempts": result.attempts,
            "root_cause_summary": result.root_cause_summary,
        }
    )


@app.command()
def triage(
    input: Path = typer.Option(..., exists=True, readable=True, help="Path to failure JSON"),
    max_attempts: int = typer.Option(2, min=1, max=5, help="Max loop attempts for uncertain cases"),
):
    load_dotenv()
    payload = json.loads(input.read_text(encoding="utf-8"))
    triage_input = TriageInput.model_validate(payload)
    agent = DefectTriageAgent()
    result = agent.run(triage_input, max_attempts=max_attempts)
    _print_result(result)


@app.command()
def demo():
    load_dotenv()
    triage_input = TriageInput(
        test_id="CheckoutTests::test_payment_submit",
        suite="CheckoutTests",
        logs="HTTP 500 from /payments/submit while processing card, retries exhausted",
        stack_trace="AssertionError: expected 200 got 500",
        screenshot_path="artifacts/payment_error.png",
        metadata={"branch": "main", "commit": "a1b2c3d", "pipeline": "github-actions", "run_id": "12345"},
    )
    agent = DefectTriageAgent()
    result = agent.run(triage_input)
    _print_result(result)


@app.command()
def dashboard(port: int = typer.Option(8501, min=1, max=65535, help="Dashboard port")):
    app_file = Path(__file__).with_name("dashboard_app.py")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_file),
            "--server.port",
            str(port),
        ],
        check=True,
    )


if __name__ == "__main__":
    app()
