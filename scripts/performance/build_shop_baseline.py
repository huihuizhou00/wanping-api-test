from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

ROUND_ROOT = (
    REPO_ROOT
    / "performance"
    / "baselines"
    / "runs"
)

OUTPUT_PATH = (
    REPO_ROOT
    / "performance"
    / "baselines"
    / "shop-query.json"
)

ROUND_COUNT = 3

MEDIAN_FIELDS = [
    "throughput_rps",
    "mean_ms",
    "median_ms",
    "p90_ms",
    "p95_ms",
    "p99_ms",
    "max_ms",
]


def load_round(
    round_number: int,
) -> dict[str, Any]:
    path = (
        ROUND_ROOT
        / f"shop-query-round{round_number}.json"
    )

    if not path.is_file():
        raise FileNotFoundError(
            f"缺少基线轮次文件：{path}"
        )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if data.get("scenario") != "shop-query":
        raise ValueError(
            f"场景不匹配：{path}"
        )

    metrics = data.get("metrics")

    if not isinstance(metrics, dict):
        raise ValueError(
            f"缺少metrics：{path}"
        )

    if metrics.get("sample_count") != 400:
        raise ValueError(
            f"样本数不是400：{path}"
        )

    if metrics.get("error_count") != 0:
        raise ValueError(
            f"基线轮次存在错误：{path}"
        )

    return {
        "round": round_number,
        "source": str(
            path.relative_to(REPO_ROOT)
        ),
        "metrics": metrics,
    }


def median_metric(
    rounds: list[dict[str, Any]],
    field: str,
) -> int | float:
    values = [
        report["metrics"][field]
        for report in rounds
    ]

    return statistics.median(values)


def main() -> int:
    rounds = [
        load_round(round_number)
        for round_number in range(
            1,
            ROUND_COUNT + 1,
        )
    ]

    baseline_metrics = {
        "sample_count": 400,
        "error_count": 0,
        "error_rate": 0.0,
    }

    for field in MEDIAN_FIELDS:
        baseline_metrics[field] = (
            median_metric(rounds, field)
        )

    baseline = {
        "schema_version": "1.0",
        "scenario": "shop-query",
        "status": "provisional",
        "baseline_method": (
            "median_of_three_rounds"
        ),
        "round_count": ROUND_COUNT,
        "target": {
            "protocol": "http",
            "host": "127.0.0.1",
            "port": 8082,
            "path": "/shop/of/type",
        },
        "load_model": {
            "threads": 20,
            "ramp_up_seconds": 2,
            "loops_per_thread": 20,
            "expected_samples": 400,
            "warmup_samples": 20,
        },
        "environment": {
            "root_disk_usage_percent": 92,
            "environment_warning": (
                "root_disk_usage_high"
            ),
            "jmeter_result_storage": (
                "/mnt/wanping-performance"
            ),
        },
        "metrics": baseline_metrics,
        "thresholds": {
            "sample_count": {
                "severity": "hard",
                "operator": "equal",
                "value": 400,
            },
            "error_rate": {
                "severity": "hard",
                "operator": "less_than_or_equal",
                "absolute_max": 0.01,
            },
            "throughput_rps": {
                "severity": "hard",
                "operator": (
                    "decrease_ratio_less_than_or_equal"
                ),
                "max_decrease_ratio": 0.15,
            },
            "p95_ms": {
                "severity": "hard",
                "operator": (
                    "increase_ratio_less_than_or_equal"
                ),
                "max_increase_ratio": 0.20,
            },
            "p99_ms": {
                "severity": "warning",
                "operator": (
                    "increase_ratio_less_than_or_equal"
                ),
                "max_increase_ratio": 0.25,
            },
            "max_ms": {
                "severity": "observe",
            },
        },
        "source_rounds": rounds,
        "notes": [
            (
                "This baseline represents a fixed "
                "regression workload, not maximum "
                "system capacity."
            ),
            (
                "P99 and maximum latency showed "
                "higher variation than P95."
            ),
            (
                "Rebuild the baseline after root "
                "disk usage is reduced."
            ),
        ],
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            baseline,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("BASELINE_OUTPUT =", OUTPUT_PATH)
    print("BASELINE_STATUS = provisional")

    for name, value in baseline_metrics.items():
        print(
            f"BASELINE_{name.upper()} =",
            value,
        )

    print("BASELINE_BUILD_CHECK = PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
