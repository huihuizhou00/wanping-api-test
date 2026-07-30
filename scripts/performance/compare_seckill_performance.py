from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCENARIO = "seckill-plus"


def load_json(
    path: Path,
) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def decrease_ratio(
    baseline: float,
    candidate: float,
) -> float:
    return (
        baseline - candidate
    ) / baseline


def increase_ratio(
    baseline: float,
    candidate: float,
) -> float:
    return (
        candidate - baseline
    ) / baseline


def validate_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> None:
    if baseline.get("scenario") != SCENARIO:
        raise ValueError(
            "baseline scenario must be "
            "seckill-plus"
        )

    if candidate.get("scenario") != SCENARIO:
        raise ValueError(
            "candidate scenario must be "
            "seckill-plus"
        )

    if baseline.get("run_type") != "baseline":
        raise ValueError(
            "baseline run_type is invalid"
        )

    if candidate.get("run_type") != "candidate":
        raise ValueError(
            "candidate run_type is invalid"
        )

    if baseline.get("target") != candidate.get(
        "target"
    ):
        raise ValueError(
            "baseline and candidate target differ"
        )

    if baseline.get(
        "load_model"
    ) != candidate.get("load_model"):
        raise ValueError(
            "baseline and candidate load model differ"
        )

    thresholds = baseline.get("thresholds")

    if not isinstance(thresholds, dict):
        raise ValueError(
            "baseline thresholds are missing"
        )

    base_metrics = baseline.get("metrics") or {}

    for name in [
        "throughput_rps",
        "p95_ms",
        "p99_ms",
    ]:
        value = base_metrics.get(name)

        if not isinstance(
            value,
            (int, float),
        ) or value <= 0:
            raise ValueError(
                f"baseline {name} must be positive"
            )

    business_threshold = thresholds.get(
        "business_consistency"
    )

    if not isinstance(
        business_threshold,
        dict,
    ):
        raise ValueError(
            "business consistency threshold "
            "is missing"
        )

    if not isinstance(
        business_threshold.get("expected"),
        dict,
    ):
        raise ValueError(
            "expected business state is missing"
        )


def compare_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    validate_reports(
        baseline,
        candidate,
    )

    base = baseline["metrics"]
    current = candidate["metrics"]
    thresholds = baseline["thresholds"]

    throughput_change = decrease_ratio(
        base["throughput_rps"],
        current["throughput_rps"],
    )

    p95_change = increase_ratio(
        base["p95_ms"],
        current["p95_ms"],
    )

    p99_change = increase_ratio(
        base["p99_ms"],
        current["p99_ms"],
    )

    checks = {
        "sample_count": {
            "baseline":
                base["sample_count"],
            "candidate":
                current["sample_count"],
            "change_ratio": None,
            "threshold": (
                thresholds[
                    "sample_count"
                ]["expected"]
            ),
            "status": (
                "PASS"
                if current["sample_count"]
                == thresholds[
                    "sample_count"
                ]["expected"]
                else "FAIL"
            ),
        },
        "error_rate": {
            "baseline":
                base["error_rate"],
            "candidate":
                current["error_rate"],
            "change_ratio": (
                current["error_rate"]
                - base["error_rate"]
            ),
            "threshold": (
                thresholds[
                    "error_rate"
                ]["max"]
            ),
            "status": (
                "PASS"
                if current["error_rate"]
                <= thresholds[
                    "error_rate"
                ]["max"]
                else "FAIL"
            ),
        },
        "throughput_rps": {
            "baseline":
                base["throughput_rps"],
            "candidate":
                current["throughput_rps"],
            "change_ratio":
                throughput_change,
            "threshold": (
                thresholds[
                    "throughput_rps"
                ]["max_decrease_ratio"]
            ),
            "status": (
                "PASS"
                if throughput_change
                <= thresholds[
                    "throughput_rps"
                ]["max_decrease_ratio"]
                else "FAIL"
            ),
        },
        "p95_ms": {
            "baseline": base["p95_ms"],
            "candidate": current["p95_ms"],
            "change_ratio": p95_change,
            "threshold": (
                thresholds[
                    "p95_ms"
                ]["max_increase_ratio"]
            ),
            "status": (
                "PASS"
                if p95_change
                <= thresholds[
                    "p95_ms"
                ]["max_increase_ratio"]
                else "FAIL"
            ),
        },
        "p99_ms": {
            "baseline": base["p99_ms"],
            "candidate": current["p99_ms"],
            "change_ratio": p99_change,
            "threshold": (
                thresholds[
                    "p99_ms"
                ]["max_increase_ratio"]
            ),
            "status": (
                "PASS"
                if p99_change
                <= thresholds[
                    "p99_ms"
                ]["max_increase_ratio"]
                else "WARNING"
            ),
        },
        "max_ms": {
            "baseline": base["max_ms"],
            "candidate": current["max_ms"],
            "change_ratio": increase_ratio(
                base["max_ms"],
                current["max_ms"],
            ),
            "threshold": "observe",
            "status": "OBSERVE",
        },
    }

    expected_business = (
        thresholds[
            "business_consistency"
        ]["expected"]
    )

    candidate_business = (
        candidate.get(
            "business_consistency"
        )
        or {}
    )

    baseline_business = (
        baseline.get(
            "business_consistency"
        )
        or {}
    )

    business_checks = {}

    for name, expected in (
        expected_business.items()
    ):
        baseline_value = (
            baseline_business.get(name)
        )
        candidate_value = (
            candidate_business.get(name)
        )

        business_checks[name] = {
            "baseline": baseline_value,
            "candidate": candidate_value,
            "expected": expected,
            "status": (
                "PASS"
                if candidate_value == expected
                else "FAIL"
            ),
        }

    performance_statuses = [
        check["status"]
        for check in checks.values()
    ]

    business_statuses = [
        check["status"]
        for check in business_checks.values()
    ]

    if (
        "FAIL" in performance_statuses
        or "FAIL" in business_statuses
    ):
        final_status = "FAIL"
    elif "WARNING" in performance_statuses:
        final_status = "WARNING"
    else:
        final_status = "PASS"

    return {
        "scenario": SCENARIO,
        "final_status": final_status,
        "exit_code": (
            1
            if final_status == "FAIL"
            else 0
        ),
        "target": baseline["target"],
        "load_model": baseline[
            "load_model"
        ],
        "baseline_metrics": base,
        "candidate_metrics": current,
        "checks": checks,
        "business_checks": business_checks,
        "baseline_environment": (
            baseline.get("environment") or {}
        ),
        "candidate_environment": (
            candidate.get("environment") or {}
        ),
        "baseline_source_rounds": (
            baseline.get("source_rounds")
            or []
        ),
        "candidate_source_rounds": (
            candidate.get("source_rounds")
            or []
        ),
    }


def format_ratio(
    value: float | None,
) -> str:
    if value is None:
        return "-"

    return f"{value * 100:.2f}%"


def render_markdown(
    result: dict[str, Any],
) -> str:
    load = result["load_model"]
    target = result["target"]

    base = result["baseline_metrics"]
    candidate = result[
        "candidate_metrics"
    ]

    lines = [
        "# Seckill Plus Performance Regression",
        "",
        "## Final Status",
        "",
        f"**{result['final_status']}**",
        "",
        "## Fixed Load Model",
        "",
        f"- Voucher ID: `{target['voucher_id']}`",
        (
            "- Redis database: "
            f"`{target['redis_database']}`"
        ),
        f"- Threads: `{load['threads']}`",
        (
            "- Ramp-up: "
            f"`{load['ramp_up_seconds']} seconds`"
        ),
        (
            "- Loops per thread: "
            f"`{load['loops_per_thread']}`"
        ),
        (
            "- Unique tokens: "
            f"`{load['unique_tokens']}`"
        ),
        (
            "- Expected samples: "
            f"`{load['expected_samples']}`"
        ),
        "",
        "## Baseline Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]

    metric_names = [
        "sample_count",
        "error_rate",
        "throughput_rps",
        "mean_ms",
        "median_ms",
        "p95_ms",
        "p99_ms",
        "max_ms",
    ]

    for name in metric_names:
        lines.append(
            f"| {name} | {base[name]} |"
        )

    lines.extend([
        "",
        "## Candidate Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ])

    for name in metric_names:
        lines.append(
            f"| {name} | {candidate[name]} |"
        )

    lines.extend([
        "",
        "## Performance Regression Checks",
        "",
        (
            "| Check | Baseline | Candidate | "
            "Change | Threshold | Status |"
        ),
        (
            "|---|---:|---:|---:|---:|---|"
        ),
    ])

    for name, check in (
        result["checks"].items()
    ):
        lines.append(
            f"| {name} "
            f"| {check['baseline']} "
            f"| {check['candidate']} "
            f"| {format_ratio(check['change_ratio'])} "
            f"| {check['threshold']} "
            f"| {check['status']} |"
        )

    lines.extend([
        "",
        "## Business Consistency Checks",
        "",
        (
            "| Check | Baseline | Candidate | "
            "Expected | Status |"
        ),
        "|---|---:|---:|---:|---|",
    ])

    for name, check in (
        result["business_checks"].items()
    ):
        lines.append(
            f"| {name} "
            f"| {check['baseline']} "
            f"| {check['candidate']} "
            f"| {check['expected']} "
            f"| {check['status']} |"
        )

    baseline_environment = result[
        "baseline_environment"
    ]
    candidate_environment = result[
        "candidate_environment"
    ]

    lines.extend([
        "",
        "## Environment Warnings",
        "",
        (
            "- Baseline root disk warning: "
            f"`{baseline_environment.get('root_disk_warning')}`"
        ),
        (
            "- Candidate root disk warning: "
            f"`{candidate_environment.get('root_disk_warning')}`"
        ),
        (
            "- Performance raw artifacts were written "
            "to `/mnt/wanping-performance`."
        ),
        "",
        "## Raw Artifact Policy",
        "",
        (
            "JTL files, JMeter logs, console logs and "
            "token CSV files are excluded from Git."
        ),
        (
            "Only compact round metrics, comparison JSON "
            "and this Markdown report are versioned."
        ),
        "",
        "Successful requests include the application's "
        "approximately three-second asynchronous order "
        "confirmation wait.",
        "",
    ])

    return "\n".join(lines)


def write_json(
    path: Path,
    result: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_markdown(
    path: Path,
    result: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        render_markdown(result),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--baseline",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--candidate",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--json-output",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--markdown-output",
        required=True,
        type=Path,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    result = compare_reports(
        load_json(args.baseline),
        load_json(args.candidate),
    )

    write_json(
        args.json_output,
        result,
    )
    write_markdown(
        args.markdown_output,
        result,
    )

    print(
        "FINAL_STATUS =",
        result["final_status"],
    )

    for name, check in (
        result["checks"].items()
    ):
        print(
            name.upper(),
            "BASELINE=",
            check["baseline"],
            "CANDIDATE=",
            check["candidate"],
            "CHANGE=",
            check["change_ratio"],
            "STATUS=",
            check["status"],
        )

    failed_business = [
        name
        for name, check in (
            result[
                "business_checks"
            ].items()
        )
        if check["status"] != "PASS"
    ]

    print(
        "BUSINESS_FAILURES =",
        failed_business,
    )

    print(
        "COMPARISON_EXIT_CODE =",
        result["exit_code"],
    )

    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
