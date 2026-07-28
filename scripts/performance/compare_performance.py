from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_METRICS = [
    "sample_count",
    "error_rate",
    "throughput_rps",
    "p95_ms",
    "p99_ms",
    "max_ms",
]


def load_json(
    path: Path,
) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"文件不存在：{path}"
        )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(data, dict):
        raise ValueError(
            f"JSON根节点必须是对象：{path}"
        )

    return data


def validate_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> None:
    baseline_scenario = baseline.get(
        "scenario"
    )
    candidate_scenario = candidate.get(
        "scenario"
    )

    if (
        baseline_scenario
        != candidate_scenario
    ):
        raise ValueError(
            "scenario mismatch: "
            f"baseline={baseline_scenario}, "
            f"candidate={candidate_scenario}"
        )

    baseline_load = baseline.get(
        "load_model"
    )
    candidate_load = candidate.get(
        "load_model"
    )

    if baseline_load != candidate_load:
        raise ValueError(
            "load_model mismatch"
        )

    for report_name, report in [
        ("baseline", baseline),
        ("candidate", candidate),
    ]:
        metrics = report.get("metrics")

        if not isinstance(metrics, dict):
            raise ValueError(
                f"{report_name} metrics "
                "must be an object"
            )

        missing = [
            field
            for field in REQUIRED_METRICS
            if field not in metrics
        ]

        if missing:
            raise ValueError(
                f"{report_name} missing metrics: "
                + ", ".join(missing)
            )

    baseline_metrics = baseline["metrics"]

    for field in [
        "throughput_rps",
        "p95_ms",
        "p99_ms",
    ]:
        value = baseline_metrics[field]

        if value <= 0:
            raise ValueError(
                f"baseline {field} must be "
                f"greater than 0, actual={value}"
            )

    thresholds = baseline.get(
        "thresholds"
    )

    if not isinstance(thresholds, dict):
        raise ValueError(
            "baseline thresholds must be "
            "an object"
        )


def calculate_decrease_ratio(
    baseline_value: float,
    candidate_value: float,
) -> float:
    return (
        baseline_value - candidate_value
    ) / baseline_value


def calculate_increase_ratio(
    baseline_value: float,
    candidate_value: float,
) -> float:
    return (
        candidate_value - baseline_value
    ) / baseline_value


def percentage(
    value: float,
) -> str:
    return f"{value * 100:.2f}%"


def compare_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    validate_reports(
        baseline,
        candidate,
    )

    baseline_metrics = baseline["metrics"]
    candidate_metrics = candidate["metrics"]
    thresholds = baseline["thresholds"]

    expected_samples = thresholds[
        "sample_count"
    ]["value"]

    error_rate_max = thresholds[
        "error_rate"
    ]["absolute_max"]

    throughput_max_decrease = thresholds[
        "throughput_rps"
    ]["max_decrease_ratio"]

    p95_max_increase = thresholds[
        "p95_ms"
    ]["max_increase_ratio"]

    p99_max_increase = thresholds[
        "p99_ms"
    ]["max_increase_ratio"]

    throughput_change = (
        calculate_decrease_ratio(
            baseline_metrics[
                "throughput_rps"
            ],
            candidate_metrics[
                "throughput_rps"
            ],
        )
    )

    p95_change = calculate_increase_ratio(
        baseline_metrics["p95_ms"],
        candidate_metrics["p95_ms"],
    )

    p99_change = calculate_increase_ratio(
        baseline_metrics["p99_ms"],
        candidate_metrics["p99_ms"],
    )

    checks: dict[str, dict[str, Any]] = {
        "sample_count": {
            "severity": "hard",
            "baseline": (
                baseline_metrics[
                    "sample_count"
                ]
            ),
            "candidate": (
                candidate_metrics[
                    "sample_count"
                ]
            ),
            "change_ratio": None,
            "threshold": (
                f"equal to {expected_samples}"
            ),
            "status": (
                "PASS"
                if candidate_metrics[
                    "sample_count"
                ] == expected_samples
                else "FAIL"
            ),
        },
        "error_rate": {
            "severity": "hard",
            "baseline": (
                baseline_metrics[
                    "error_rate"
                ]
            ),
            "candidate": (
                candidate_metrics[
                    "error_rate"
                ]
            ),
            "change_ratio": (
                candidate_metrics[
                    "error_rate"
                ]
                - baseline_metrics[
                    "error_rate"
                ]
            ),
            "threshold": (
                f"<= {percentage(error_rate_max)}"
            ),
            "status": (
                "PASS"
                if candidate_metrics[
                    "error_rate"
                ] <= error_rate_max
                else "FAIL"
            ),
        },
        "throughput_rps": {
            "severity": "hard",
            "baseline": (
                baseline_metrics[
                    "throughput_rps"
                ]
            ),
            "candidate": (
                candidate_metrics[
                    "throughput_rps"
                ]
            ),
            "change_ratio": (
                throughput_change
            ),
            "threshold": (
                "decrease <= "
                + percentage(
                    throughput_max_decrease
                )
            ),
            "status": (
                "PASS"
                if throughput_change
                <= throughput_max_decrease
                else "FAIL"
            ),
        },
        "p95_ms": {
            "severity": "hard",
            "baseline": (
                baseline_metrics["p95_ms"]
            ),
            "candidate": (
                candidate_metrics["p95_ms"]
            ),
            "change_ratio": p95_change,
            "threshold": (
                "increase <= "
                + percentage(
                    p95_max_increase
                )
            ),
            "status": (
                "PASS"
                if p95_change
                <= p95_max_increase
                else "FAIL"
            ),
        },
        "p99_ms": {
            "severity": "warning",
            "baseline": (
                baseline_metrics["p99_ms"]
            ),
            "candidate": (
                candidate_metrics["p99_ms"]
            ),
            "change_ratio": p99_change,
            "threshold": (
                "increase <= "
                + percentage(
                    p99_max_increase
                )
            ),
            "status": (
                "PASS"
                if p99_change
                <= p99_max_increase
                else "WARNING"
            ),
        },
        "max_ms": {
            "severity": "observe",
            "baseline": (
                baseline_metrics["max_ms"]
            ),
            "candidate": (
                candidate_metrics["max_ms"]
            ),
            "change_ratio": (
                calculate_increase_ratio(
                    baseline_metrics["max_ms"],
                    candidate_metrics["max_ms"],
                )
                if baseline_metrics["max_ms"] > 0
                else None
            ),
            "threshold": "observe only",
            "status": "OBSERVE",
        },
    }

    hard_failed = any(
        check["status"] == "FAIL"
        for check in checks.values()
    )

    warning_found = any(
        check["status"] == "WARNING"
        for check in checks.values()
    )

    if hard_failed:
        final_status = "FAIL"
        exit_code = 1
    elif warning_found:
        final_status = "WARNING"
        exit_code = 0
    else:
        final_status = "PASS"
        exit_code = 0

    return {
        "schema_version": "1.0",
        "scenario": baseline["scenario"],
        "final_status": final_status,
        "exit_code": exit_code,
        "baseline_status": baseline.get(
            "status"
        ),
        "candidate_status": candidate.get(
            "status"
        ),
        "load_model": baseline["load_model"],
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
        "checks": checks,
        "environment": {
            "baseline": baseline.get(
                "environment",
                {},
            ),
            "candidate": candidate.get(
                "environment",
                {},
            ),
        },
    }


def format_change(
    value: float | None,
) -> str:
    if value is None:
        return "N/A"

    return percentage(value)


def render_metrics_table(
    metrics: dict[str, Any],
) -> str:
    rows = [
        "| Metric | Value |",
        "|---|---:|",
    ]

    for field in [
        "sample_count",
        "error_count",
        "error_rate",
        "throughput_rps",
        "mean_ms",
        "median_ms",
        "p90_ms",
        "p95_ms",
        "p99_ms",
        "max_ms",
    ]:
        if field not in metrics:
            continue

        value = metrics[field]

        if field == "error_rate":
            rendered = percentage(value)
        else:
            rendered = str(value)

        rows.append(
            f"| {field} | {rendered} |"
        )

    return "\n".join(rows)


def render_markdown(
    comparison: dict[str, Any],
) -> str:
    load = comparison["load_model"]
    checks = comparison["checks"]

    check_rows = [
        (
            "| Metric | Baseline | Candidate | "
            "Change | Threshold | Status |"
        ),
        "|---|---:|---:|---:|---|---|",
    ]

    display_names = {
        "sample_count": "Sample Count",
        "error_rate": "Error Rate",
        "throughput_rps": "Throughput",
        "p95_ms": "P95",
        "p99_ms": "P99",
        "max_ms": "Max",
    }

    for field in [
        "sample_count",
        "error_rate",
        "throughput_rps",
        "p95_ms",
        "p99_ms",
        "max_ms",
    ]:
        check = checks[field]

        check_rows.append(
            "| "
            + display_names[field]
            + " | "
            + str(check["baseline"])
            + " | "
            + str(check["candidate"])
            + " | "
            + format_change(
                check["change_ratio"]
            )
            + " | "
            + str(check["threshold"])
            + " | "
            + str(check["status"])
            + " |"
        )

    baseline_environment = (
        comparison["environment"][
            "baseline"
        ]
    )
    candidate_environment = (
        comparison["environment"][
            "candidate"
        ]
    )

    root_usage = candidate_environment.get(
        "root_disk_usage_percent",
        baseline_environment.get(
            "root_disk_usage_percent",
            "unknown",
        ),
    )

    storage = candidate_environment.get(
        "jmeter_result_storage",
        baseline_environment.get(
            "jmeter_result_storage",
            "/mnt/wanping-performance",
        ),
    )

    return (
        "# Shop Query Performance Regression\n\n"
        "## Final Status\n\n"
        f"**{comparison['final_status']}**\n\n"
        "## Fixed Load Model\n\n"
        f"- Threads: {load['threads']}\n"
        f"- Ramp-up: {load['ramp_up_seconds']} seconds\n"
        f"- Loops per thread: {load['loops_per_thread']}\n"
        f"- Expected samples: {load['expected_samples']}\n"
        f"- Warm-up samples: {load['warmup_samples']}\n\n"
        "## Baseline Metrics\n\n"
        + render_metrics_table(
            comparison["baseline_metrics"]
        )
        + "\n\n"
        "## Candidate Metrics\n\n"
        + render_metrics_table(
            comparison["candidate_metrics"]
        )
        + "\n\n"
        "## Regression Checks\n\n"
        + "\n".join(check_rows)
        + "\n\n"
        "## Environment Warnings\n\n"
        f"- Root disk usage: {root_usage}%\n"
        "- Baseline status: "
        f"{comparison['baseline_status']}\n"
        "- Candidate status: "
        f"{comparison['candidate_status']}\n\n"
        "## Raw Artifact Policy\n\n"
        f"- Raw JTL and JMeter logs: `{storage}`\n"
        "- Raw runtime artifacts are not committed to Git.\n"
    )


def write_json(
    data: dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_text(
    text: str,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        text,
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare JMeter candidate metrics "
            "against a performance baseline."
        )
    )

    parser.add_argument(
        "--baseline",
        required=True,
    )
    parser.add_argument(
        "--candidate",
        required=True,
    )
    parser.add_argument(
        "--json-output",
        required=True,
    )
    parser.add_argument(
        "--markdown-output",
        required=True,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    baseline = load_json(
        Path(args.baseline)
    )
    candidate = load_json(
        Path(args.candidate)
    )

    comparison = compare_reports(
        baseline,
        candidate,
    )

    write_json(
        comparison,
        Path(args.json_output),
    )

    write_text(
        render_markdown(comparison),
        Path(args.markdown_output),
    )

    print(
        "PERFORMANCE_STATUS =",
        comparison["final_status"],
    )

    for field, check in (
        comparison["checks"].items()
    ):
        print(
            f"CHECK_{field.upper()} =",
            check["status"],
        )

    print(
        "COMPARISON_JSON =",
        args.json_output,
    )
    print(
        "COMPARISON_MARKDOWN =",
        args.markdown_output,
    )

    return comparison["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
