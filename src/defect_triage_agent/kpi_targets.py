from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class MetricRule:
    direction: str
    unit: str
    owner: str
    q2_formula: str
    q2_fn: Callable[[float], float]


METRIC_RULES: dict[str, MetricRule] = {
    "regression_escape_rate": MetricRule(
        direction="lower",
        unit="defects/release",
        owner="Staff SDET",
        q2_formula="B0 * 0.70",
        q2_fn=lambda b0: b0 * 0.70,
    ),
    "mttt_hours": MetricRule(
        direction="lower",
        unit="hours",
        owner="QA Platform Lead",
        q2_formula="B0 * 0.50",
        q2_fn=lambda b0: b0 * 0.50,
    ),
    "false_failure_rate_pct": MetricRule(
        direction="lower",
        unit="percent",
        owner="Test Reliability Lead",
        q2_formula="min(B0 * 0.75, 8.0)",
        q2_fn=lambda b0: min(b0 * 0.75, 8.0),
    ),
    "ai_test_yield": MetricRule(
        direction="higher",
        unit="defects/100-tests",
        owner="AI Quality Engineer",
        q2_formula="max(B0 * 1.25, 2.0)",
        q2_fn=lambda b0: max(b0 * 1.25, 2.0),
    ),
    "self_heal_effectiveness_pct": MetricRule(
        direction="higher",
        unit="percent",
        owner="Automation Architect",
        q2_formula="max(B0 + 15, 70)",
        q2_fn=lambda b0: max(b0 + 15.0, 70.0),
    ),
}


def _parse_baselines(input_csv: Path) -> dict[str, float]:
    baselines: dict[str, float] = {}
    with input_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = {"metric", "b0"}
        if reader.fieldnames is None or not expected.issubset(set(reader.fieldnames)):
            raise ValueError("Input CSV must include columns: metric,b0")

        for row in reader:
            metric = (row.get("metric") or "").strip()
            raw_b0 = (row.get("b0") or "").strip()
            if not metric:
                continue
            if metric not in METRIC_RULES:
                valid = ", ".join(sorted(METRIC_RULES))
                raise ValueError(f"Unknown metric '{metric}'. Valid metrics: {valid}")
            if not raw_b0:
                raise ValueError(f"Missing b0 value for metric '{metric}'")
            baselines[metric] = float(raw_b0)

    missing = sorted(set(METRIC_RULES) - set(baselines))
    if missing:
        raise ValueError(f"Missing metrics in input CSV: {', '.join(missing)}")

    return baselines


def _q1_target(b0: float, q2: float, direction: str) -> float:
    if direction == "lower":
        return b0 - 0.5 * (b0 - q2)
    if direction == "higher":
        return b0 + 0.5 * (q2 - b0)
    raise ValueError(f"Unsupported direction: {direction}")


def compute_targets(baselines: dict[str, float]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for metric, rule in METRIC_RULES.items():
        b0 = baselines[metric]
        q2 = rule.q2_fn(b0)
        q1 = _q1_target(b0, q2, rule.direction)
        rows.append(
            {
                "metric": metric,
                "direction": rule.direction,
                "unit": rule.unit,
                "owner": rule.owner,
                "b0": f"{b0:.4f}",
                "q1_target": f"{q1:.4f}",
                "q2_target": f"{q2:.4f}",
                "q2_formula": rule.q2_formula,
            }
        )
    return rows


def write_targets(output_csv: Path, rows: list[dict[str, str]]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "metric",
        "direction",
        "unit",
        "owner",
        "b0",
        "q1_target",
        "q2_target",
        "q2_formula",
    ]
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute Q+1 and Q+2 KPI targets from baseline values."
    )
    parser.add_argument(
        "--input",
        default="examples/kpi_baseline_input.csv",
        help="Path to baseline CSV with columns metric,b0",
    )
    parser.add_argument(
        "--output",
        default="artifacts/kpi_targets.csv",
        help="Path for computed target CSV output",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_csv = Path(args.input)
    output_csv = Path(args.output)

    baselines = _parse_baselines(input_csv)
    rows = compute_targets(baselines)
    write_targets(output_csv, rows)

    print(f"Computed KPI targets written to {output_csv}")


if __name__ == "__main__":
    main()
