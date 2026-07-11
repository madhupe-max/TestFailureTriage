# AI-Driven Defect Triage Agent (LangGraph)

This project implements a stateful defect triage workflow using LangGraph for CI/CD test failures.

## What It Does

1. Ingests a failed test result (logs, stack trace, screenshot path, metadata)
2. Classifies failure type using an LLM-enabled classifier (with heuristic fallback)
3. Loops to gather more context when confidence is low
4. Makes a routing decision:
   - High confidence real defect -> auto-file ticket
   - Low confidence or unknown -> human review
   - High confidence flaky/environment -> automated non-ticket action
5. Writes governance trend data for dashboarding

## Architecture

Graph nodes in order:

- `ingest_failure`
- `classify_failure`
- `gather_more_context` (conditional loop)
- `decide_routing`
- `execute_routing`
- `update_dashboard`

The graph loops between classification and context-gathering until confidence improves or `max_attempts` is reached.

## Quick Start

### 1) Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2) Optional LLM configuration

Create `.env` from `.env.example` and set your OpenAI key.

### 3) Run a demo triage

```bash
defect-triage demo
```

### 4) Triage from JSON input

```bash
defect-triage triage --input examples/failure_real_defect.json
```

## JSON Input Example

```json
{
  "test_id": "CheckoutTests::test_payment_submit",
  "suite": "CheckoutTests",
  "logs": "HTTP 500 from /payments/submit, retries exhausted",
  "stack_trace": "AssertionError: expected 200 got 500\n...",
  "screenshot_path": "artifacts/payment_error.png",
  "metadata": {
    "branch": "main",
    "commit": "a1b2c3d",
    "pipeline": "github-actions",
    "run_id": "12345"
  }
}
```

## Output Artifacts

- `artifacts/tickets.jsonl`: Auto-filed defect tickets
- `artifacts/governance_events.jsonl`: Dashboard/trend events

## Governance Dashboard

Run the dashboard after generating triage events:

```bash
defect-triage dashboard --port 8501
```

Then open http://localhost:8501 to view:

- Failures triaged over time
- Classification distribution (real defect, flaky, environment, unknown)
- Routing decisions (auto ticket, human review, auto resolve)
- Recent event table

## Flaky Detector

Run the standalone flaky detector against a failure payload:

```bash
defect-triage flaky --input examples/failure_flaky.json
```

The detector scores retry-pass behavior, timeout signatures, intermittent wording, ordering issues, and recent outcome history.

## Notes

- If no LLM is configured, the classifier uses deterministic heuristics.
- You can replace adapters with real integrations (Jira, Azure DevOps, Datadog, Grafana, etc.).
