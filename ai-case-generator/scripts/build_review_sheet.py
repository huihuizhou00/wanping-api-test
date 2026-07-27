from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_DIR / "output"

JSON_PATH = OUTPUT_DIR / "generated-cases.json"
JSONL_PATH = OUTPUT_DIR / "generated-cases.jsonl"
REVIEW_PATH = OUTPUT_DIR / "human-review.csv"


def load_scenarios() -> List[Dict[str, Any]]:
    if JSON_PATH.exists():
        data = json.loads(
            JSON_PATH.read_text(encoding="utf-8")
        )

        if isinstance(data, dict):
            scenarios = data.get("scenarios", [])
        elif isinstance(data, list):
            scenarios = data
        else:
            raise RuntimeError(
                "generated-cases.json根节点格式不正确"
            )

        if not isinstance(scenarios, list):
            raise RuntimeError(
                "generated-cases.json中的scenarios必须是数组"
            )

        return scenarios

    if JSONL_PATH.exists():
        scenarios = []

        for line_number, line in enumerate(
            JSONL_PATH.read_text(
                encoding="utf-8"
            ).splitlines(),
            start=1,
        ):
            if not line.strip():
                continue

            value = json.loads(line)

            if not isinstance(value, dict):
                raise RuntimeError(
                    f"JSONL第{line_number}行不是对象"
                )

            scenarios.append(value)

        return scenarios

    raise FileNotFoundError(
        "没有找到generated-cases.json"
        "或generated-cases.jsonl"
    )


def main() -> None:
    scenarios = load_scenarios()

    fieldnames = [
        "case_id",
        "module",
        "title",
        "priority",
        "test_type",
        "endpoint",
        "method",
        "source_rules",
        "review_status",
        "review_comment",
        "executable",
        "automation_priority",
        "test_data_ready",
        "redis_assertion_ready",
        "mysql_assertion_ready",
        "selected_for_automation",
    ]

    with REVIEW_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()

        for scenario in scenarios:
            writer.writerow(
                {
                    "case_id": scenario.get(
                        "case_id", ""
                    ),
                    "module": scenario.get(
                        "module", ""
                    ),
                    "title": scenario.get(
                        "title", ""
                    ),
                    "priority": scenario.get(
                        "priority", ""
                    ),
                    "test_type": scenario.get(
                        "test_type", ""
                    ),
                    "endpoint": scenario.get(
                        "endpoint", ""
                    ),
                    "method": scenario.get(
                        "method", ""
                    ),
                    "source_rules": "|".join(
                        scenario.get(
                            "source_rules"
                        )
                        or []
                    ),
                    "review_status": "",
                    "review_comment": "",
                    "executable": "",
                    "automation_priority": "",
                    "test_data_ready": "",
                    "redis_assertion_ready": "",
                    "mysql_assertion_ready": "",
                    "selected_for_automation": "",
                }
            )

    print(f"REVIEW_ROWS={len(scenarios)}")
    print(f"REVIEW_FILE={REVIEW_PATH}")


if __name__ == "__main__":
    main()
