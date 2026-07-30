from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


EXPECTED_ROUND_COUNT = 3
EXPECTED_SAMPLE_COUNT = 400
EXPECTED_SCENARIO = "shop-query"
EXPECTED_RUN_TYPE = "candidate"

MEDIAN_FIELDS = [
    "throughput_rps",
    "mean_ms",
    "median_ms",
    "p90_ms",
    "p95_ms",
    "p99_ms",
    "max_ms",
]

REQUIRED_METRIC_FIELDS = [
    "sample_count",
    "error_count",
    "error_rate",
    *MEDIAN_FIELDS,
]


def validate_round_reports(
    round_reports: list[dict[str, Any]],
) -> None:
    """
    验证三轮 Candidate 是否具备汇总资格。
    """

    if (
        len(round_reports)
        != EXPECTED_ROUND_COUNT
    ):
        raise ValueError(
            "round_count must be "
            f"{EXPECTED_ROUND_COUNT}, actual="
            f"{len(round_reports)}"
        )

    for index, report in enumerate(
        round_reports,
        start=1,
    ):
        scenario = report.get("scenario")

        if scenario != EXPECTED_SCENARIO:
            raise ValueError(
                f"round {index} scenario must be "
                f"{EXPECTED_SCENARIO}, actual="
                f"{scenario}"
            )

        run_type = report.get("run_type")

        if run_type != EXPECTED_RUN_TYPE:
            raise ValueError(
                f"round {index} run_type must be "
                f"{EXPECTED_RUN_TYPE}, actual="
                f"{run_type}"
            )

        metrics = report.get("metrics")

        if not isinstance(metrics, dict):
            raise ValueError(
                f"round {index} metrics must be "
                "an object"
            )

        missing_fields = [
            field
            for field in REQUIRED_METRIC_FIELDS
            if field not in metrics
        ]

        if missing_fields:
            raise ValueError(
                f"round {index} missing metrics: "
                + ", ".join(missing_fields)
            )

        sample_count = metrics["sample_count"]

        if sample_count != EXPECTED_SAMPLE_COUNT:
            raise ValueError(
                f"round {index} sample_count "
                f"must be {EXPECTED_SAMPLE_COUNT}, "
                f"actual={sample_count}"
            )

        error_count = metrics["error_count"]

        if error_count != 0:
            raise ValueError(
                f"round {index} error_count "
                f"must be 0, actual={error_count}"
            )


def build_candidate(
    round_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    根据三轮 Candidate 结果构建中位数报告。
    """

    validate_round_reports(round_reports)

    metrics: dict[str, int | float] = {
        "sample_count": EXPECTED_SAMPLE_COUNT,
        "error_count": 0,
        "error_rate": 0.0,
    }

    for field in MEDIAN_FIELDS:
        values = [
            report["metrics"][field]
            for report in round_reports
        ]

        metrics[field] = statistics.median(
            values
        )

    return {
        "schema_version": "1.0",
        "scenario": EXPECTED_SCENARIO,
        "run_type": EXPECTED_RUN_TYPE,
        "status": "provisional",
        "candidate_method": (
            "median_of_three_rounds"
        ),
        "round_count": EXPECTED_ROUND_COUNT,
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
        "metrics": metrics,
        "source_rounds": round_reports,
    }


def load_json(path: Path) -> dict[str, Any]:
    """
    读取单个 JSON 文件。
    """

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


def write_candidate(
    candidate: dict[str, Any],
    output_path: Path,
) -> None:
    """
    写出 Candidate 汇总 JSON。
    """

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            candidate,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build shop-query candidate metrics "
            "from three rounds."
        )
    )

    parser.add_argument(
        "--round",
        dest="round_paths",
        action="append",
        required=True,
        help=(
            "Candidate round JSON path. "
            "Specify exactly three times."
        ),
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Candidate summary output path.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    round_paths = [
        Path(value)
        for value in args.round_paths
    ]

    reports = [
        load_json(path)
        for path in round_paths
    ]

    candidate = build_candidate(reports)

    output_path = Path(args.output)

    write_candidate(
        candidate,
        output_path,
    )

    print(
        "CANDIDATE_OUTPUT =",
        output_path,
    )
    print(
        "CANDIDATE_ROUND_COUNT =",
        candidate["round_count"],
    )

    for name, value in (
        candidate["metrics"].items()
    ):
        print(
            f"CANDIDATE_{name.upper()} =",
            value,
        )

    print("CANDIDATE_BUILD_CHECK = PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
