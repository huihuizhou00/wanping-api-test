from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


SCENARIO = "seckill-plus"
ROUND_COUNT = 3

METRIC_NAMES = [
    "sample_count",
    "success_count",
    "error_count",
    "error_rate",
    "duration_seconds",
    "throughput_rps",
    "mean_ms",
    "median_ms",
    "p90_ms",
    "p95_ms",
    "p99_ms",
    "max_ms",
]

EXPECTED_BUSINESS = {
    "voucher_id": 900013,
    "db_stock": 0,
    "order_count": 20,
    "distinct_user_count": 20,
    "duplicate_user_count": 0,
    "deduct_log_count": 20,
    "restore_log_count": 0,
    "verify_open_count": 0,
    "recovery_task_count": 0,
    "reconcile_task_count": 0,
    "redis_stock": 0,
    "redis_order_count": 20,
    "redis_trace_count": 20,
    "request_key_count": 0,
}

BASELINE_THRESHOLDS = {
    "sample_count": {
        "expected": 20,
        "severity": "FAIL",
    },
    "error_rate": {
        "max": 0.0,
        "severity": "FAIL",
    },
    "throughput_rps": {
        "max_decrease_ratio": 0.15,
        "severity": "FAIL",
    },
    "p95_ms": {
        "max_increase_ratio": 0.15,
        "severity": "FAIL",
    },
    "p99_ms": {
        "max_increase_ratio": 0.20,
        "severity": "WARNING",
    },
    "max_ms": {
        "mode": "observe",
        "severity": "OBSERVE",
    },
    "business_consistency": {
        "expected": EXPECTED_BUSINESS,
        "severity": "FAIL",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def validate_report(
    report: dict[str, Any],
    *,
    run_type: str,
    expected_target: dict[str, Any] | None,
    expected_load_model: dict[str, Any] | None,
) -> None:
    if report.get("scenario") != SCENARIO:
        raise ValueError(
            "round scenario must be seckill-plus"
        )

    if report.get("run_type") != run_type:
        raise ValueError(
            "round run_type does not match"
        )

    if report.get("status") != "PASS":
        raise ValueError(
            "round status must be PASS"
        )

    target = report.get("target")

    if expected_target is not None:
        if target != expected_target:
            raise ValueError(
                "round target does not match"
            )

    load_model = report.get("load_model")

    if expected_load_model is not None:
        if load_model != expected_load_model:
            raise ValueError(
                "round load model does not match"
            )

    metrics = report.get("metrics") or {}

    if metrics.get("sample_count") != 20:
        raise ValueError(
            "round sample_count must be 20"
        )

    if metrics.get("success_count") != 20:
        raise ValueError(
            "round success_count must be 20"
        )

    if metrics.get("error_count") != 0:
        raise ValueError(
            "round error_count must be zero"
        )

    if metrics.get("error_rate") != 0.0:
        raise ValueError(
            "round error_rate must be zero"
        )

    business = (
        report.get("business_consistency")
        or {}
    )

    for name, expected in (
        EXPECTED_BUSINESS.items()
    ):
        actual = business.get(name)

        if actual != expected:
            raise ValueError(
                "business consistency failure: "
                f"{name}, expected={expected}, "
                f"actual={actual}"
            )


def build_summary(
    reports: list[dict[str, Any]],
    *,
    run_type: str,
) -> dict[str, Any]:
    if run_type not in {
        "baseline",
        "candidate",
    }:
        raise ValueError(
            "run_type must be baseline or candidate"
        )

    if len(reports) != ROUND_COUNT:
        raise ValueError(
            "exactly three rounds are required"
        )

    expected_target = reports[0].get("target")
    expected_load_model = reports[0].get(
        "load_model"
    )

    for report in reports:
        validate_report(
            report,
            run_type=run_type,
            expected_target=expected_target,
            expected_load_model=(
                expected_load_model
            ),
        )

    round_numbers = sorted(
        report.get("round")
        for report in reports
    )

    if round_numbers != [1, 2, 3]:
        raise ValueError(
            "round numbers must be 1, 2 and 3"
        )

    metrics: dict[str, int | float] = {}

    for name in METRIC_NAMES:
        values = [
            report["metrics"][name]
            for report in reports
        ]

        metrics[name] = statistics.median(
            values
        )

    root_usage_values = [
        (
            report.get("environment")
            or {}
        ).get(
            "root_disk_usage_percent",
            0,
        )
        for report in reports
    ]

    summary: dict[str, Any] = {
        "scenario": SCENARIO,
        "run_type": run_type,
        "round_count": ROUND_COUNT,
        "status": "PASS",
        "target": expected_target,
        "load_model": expected_load_model,
        "metrics": metrics,
        "business_consistency": (
            EXPECTED_BUSINESS.copy()
        ),
        "environment": {
            "root_disk_usage_percent_max":
                max(root_usage_values),
            "root_disk_warning": (
                max(root_usage_values) >= 90
            ),
        },
        "source_rounds": [
            {
                "round": report["round"],
                "raw_artifact_directory": (
                    report[
                        "raw_artifact_directory"
                    ]
                ),
                "metrics": report["metrics"],
            }
            for report in sorted(
                reports,
                key=lambda item: item["round"],
            )
        ],
    }

    if run_type == "baseline":
        summary["thresholds"] = (
            BASELINE_THRESHOLDS
        )

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--run-type",
        required=True,
        choices=[
            "baseline",
            "candidate",
        ],
    )

    parser.add_argument(
        "--round",
        action="append",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    reports = [
        load_json(path)
        for path in args.round
    ]

    summary = build_summary(
        reports,
        run_type=args.run_type,
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = summary["metrics"]

    print("SCENARIO =", summary["scenario"])
    print("RUN_TYPE =", summary["run_type"])
    print(
        "ROUND_COUNT =",
        summary["round_count"],
    )

    for name in METRIC_NAMES:
        print(
            name.upper(),
            "=",
            metrics[name],
        )

    print("OUTPUT =", args.output)
    print("SECKILL_SUMMARY_CHECK = PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
