from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict


def as_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def main() -> int:
    parser = argparse.ArgumentParser(description="统计AI测试场景格式通过率和人工采纳率")
    parser.add_argument("csv_path", type=Path, nargs="?", default=Path("output/generated-cases.csv"))
    parser.add_argument("--output", type=Path, default=Path("output/review-summary.md"))
    args = parser.parse_args()

    with args.csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    total = len(rows)
    schema_pass = sum(as_bool(row.get("schema_valid", "")) for row in rows)
    business_pass = sum(as_bool(row.get("business_valid", "")) for row in rows)
    statuses: Dict[str, int] = {"pending": 0, "accepted": 0, "rejected": 0, "revised": 0}
    for row in rows:
        status = (row.get("business_review_status") or "pending").strip().lower()
        statuses[status] = statuses.get(status, 0) + 1

    reviewed = statuses.get("accepted", 0) + statuses.get("rejected", 0) + statuses.get("revised", 0)
    adopted = statuses.get("accepted", 0) + statuses.get("revised", 0)
    adoption_rate = adopted / reviewed if reviewed else 0

    summary = {
        "total_cases": total,
        "schema_pass_count": schema_pass,
        "schema_pass_rate": schema_pass / total if total else 0,
        "business_pass_count": business_pass,
        "business_pass_rate": business_pass / total if total else 0,
        "review_status_counts": statuses,
        "reviewed_count": reviewed,
        "adopted_count": adopted,
        "human_adoption_rate": adoption_rate,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "# AI结构化测试场景审核摘要\n\n"
        f"- 场景总数：{total}\n"
        f"- Schema通过：{schema_pass}（{summary['schema_pass_rate']:.2%}）\n"
        f"- 业务规则通过：{business_pass}（{summary['business_pass_rate']:.2%}）\n"
        f"- 已审核：{reviewed}\n"
        f"- 采纳或修改后采纳：{adopted}\n"
        f"- 人工采纳率：{adoption_rate:.2%}\n"
        f"- 待审核：{statuses.get('pending', 0)}\n"
        f"- 直接采纳：{statuses.get('accepted', 0)}\n"
        f"- 拒绝：{statuses.get('rejected', 0)}\n"
        f"- 修改后采纳：{statuses.get('revised', 0)}\n",
        encoding="utf-8",
    )
    (args.output.with_suffix(".json")).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(args.output.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
