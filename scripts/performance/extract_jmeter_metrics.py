from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any


def percentile_nearest_rank(
    values: list[int],
    ratio: float,
) -> int:
    if not values:
        raise ValueError(
            "计算百分位时样本不能为空"
        )

    ordered = sorted(values)

    index = max(
        math.ceil(
            len(ordered) * ratio
        ) - 1,
        0,
    )

    return ordered[index]


def load_rows(
    path: Path,
) -> list[dict[str, str]]:
    with path.open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    if not rows:
        raise ValueError(
            f"JTL中没有样本：{path}"
        )

    required_columns = {
        "timeStamp",
        "elapsed",
        "success",
        "responseCode",
    }

    actual_columns = set(rows[0])

    missing = (
        required_columns
        - actual_columns
    )

    if missing:
        raise ValueError(
            "JTL缺少必要字段："
            + ", ".join(sorted(missing))
        )

    return rows


def extract_metrics(
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    elapsed = [
        int(row["elapsed"])
        for row in rows
    ]

    success_count = sum(
        row["success"].strip().lower()
        == "true"
        for row in rows
    )

    sample_count = len(rows)
    error_count = (
        sample_count - success_count
    )

    start_ms = min(
        int(row["timeStamp"])
        for row in rows
    )

    end_ms = max(
        int(row["timeStamp"])
        + int(row["elapsed"])
        for row in rows
    )

    duration_seconds = max(
        (end_ms - start_ms) / 1000,
        0.001,
    )

    response_codes: dict[str, int] = {}

    for row in rows:
        code = row["responseCode"]

        response_codes[code] = (
            response_codes.get(code, 0)
            + 1
        )

    return {
        "sample_count": sample_count,
        "success_count": success_count,
        "error_count": error_count,
        "error_rate": round(
            error_count / sample_count,
            6,
        ),
        "duration_seconds": round(
            duration_seconds,
            3,
        ),
        "throughput_rps": round(
            sample_count / duration_seconds,
            3,
        ),
        "min_ms": min(elapsed),
        "mean_ms": round(
            statistics.mean(elapsed),
            3,
        ),
        "median_ms": round(
            statistics.median(elapsed),
            3,
        ),
        "p90_ms": percentile_nearest_rank(
            elapsed,
            0.90,
        ),
        "p95_ms": percentile_nearest_rank(
            elapsed,
            0.95,
        ),
        "p99_ms": percentile_nearest_rank(
            elapsed,
            0.99,
        ),
        "max_ms": max(elapsed),
        "response_codes": response_codes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "从JMeter CSV JTL中提取"
            "性能回归指标"
        )
    )

    parser.add_argument(
        "--jtl",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--scenario",
        required=True,
    )
    parser.add_argument(
        "--run-type",
        required=True,
        choices={
            "pilot",
            "baseline",
            "candidate",
        },
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    rows = load_rows(args.jtl)
    metrics = extract_metrics(rows)

    report = {
        "scenario": args.scenario,
        "run_type": args.run_type,
        "source_jtl": str(args.jtl),
        "metrics": metrics,
    }

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )

    print(
        "METRICS_STATUS =",
        (
            "PASS"
            if metrics["error_count"] == 0
            else "HAS_ERRORS"
        ),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
