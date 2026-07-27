from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"

REVIEW_PATH = OUTPUT / "human-review.csv"
CASES_PATH = OUTPUT / "generated-cases.json"
SELECTED_PATH = OUTPUT / "selected-automation-cases.json"


PLAN = {
    "AI-SECKILL-001": {
        "review_comment": "无需业务数据，验证未登录请求被鉴权拦截",
        "test_data_ready": "yes",
        "redis_assertion_ready": "n/a",
        "mysql_assertion_ready": "n/a",
    },
    "AI-SECKILL-002": {
        "review_comment": "使用有效Token验证非数字voucherId返回HTTP 400",
        "test_data_ready": "no",
        "redis_assertion_ready": "n/a",
        "mysql_assertion_ready": "n/a",
    },
    "AI-SECKILL-003": {
        "review_comment": "删除对应Redis库存Key后验证库存未初始化",
        "test_data_ready": "no",
        "redis_assertion_ready": "yes",
        "mysql_assertion_ready": "n/a",
    },
    "AI-SECKILL-004": {
        "review_comment": "初始化券12库存并验证Redis预扣及MySQL订单落库",
        "test_data_ready": "no",
        "redis_assertion_ready": "yes",
        "mysql_assertion_ready": "yes",
    },
    "AI-SECKILL-005": {
        "review_comment": "先成功下单，再验证重复请求不产生额外副作用",
        "test_data_ready": "no",
        "redis_assertion_ready": "yes",
        "mysql_assertion_ready": "yes",
    },
    "AI-CONCURRENCY-001": {
        "review_comment": "20用户并发抢库存5，验证成功5单及库存非负",
        "test_data_ready": "no",
        "redis_assertion_ready": "yes",
        "mysql_assertion_ready": "yes",
    },
}


def update_review_csv() -> None:
    with REVIEW_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames

    if not fieldnames:
        raise RuntimeError("human-review.csv缺少表头")

    found = set()

    for row in rows:
        case_id = row.get("case_id")

        if case_id not in PLAN:
            continue

        found.add(case_id)
        plan = PLAN[case_id]

        row.update(
            {
                "review_status": "revised",
                "review_comment": plan["review_comment"],
                "executable": "yes",
                "automation_priority": "P0",
                "test_data_ready": plan["test_data_ready"],
                "redis_assertion_ready": plan[
                    "redis_assertion_ready"
                ],
                "mysql_assertion_ready": plan[
                    "mysql_assertion_ready"
                ],
                "selected_for_automation": "yes",
            }
        )

    missing = set(PLAN) - found
    if missing:
        raise RuntimeError(
            "评审表缺少场景：" + ", ".join(sorted(missing))
        )

    temporary_path = REVIEW_PATH.with_suffix(".tmp")

    with temporary_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)

    temporary_path.replace(REVIEW_PATH)


def export_selected_cases() -> None:
    data = json.loads(
        CASES_PATH.read_text(encoding="utf-8")
    )

    scenarios = data.get("scenarios", [])
    scenario_by_id = {
        item["case_id"]: item
        for item in scenarios
    }

    missing = set(PLAN) - set(scenario_by_id)
    if missing:
        raise RuntimeError(
            "生成结果缺少场景：" + ", ".join(sorted(missing))
        )

    selected = [
        scenario_by_id[case_id]
        for case_id in PLAN
    ]

    result = {
        "selected_count": len(selected),
        "selection_stage": "first_batch",
        "case_ids": list(PLAN),
        "scenarios": selected,
    }

    SELECTED_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    update_review_csv()
    export_selected_cases()

    print(f"REVIEW_FILE={REVIEW_PATH}")
    print(f"SELECTED_FILE={SELECTED_PATH}")
    print(f"SELECTED_COUNT={len(PLAN)}")

    for case_id in PLAN:
        print(case_id)


if __name__ == "__main__":
    main()
