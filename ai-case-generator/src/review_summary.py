from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


REVIEW_STATUSES = {
    "pending",
    "accepted",
    "revised",
    "rejected",
}

IMPLEMENTATION_STATUSES = {
    "existing",
    "needs_update",
    "needs_new",
    "needs_manual_mapping",
    "java_file_missing",
}

EXECUTION_STATUSES = {
    "not_run",
    "passed",
    "failed",
    "skipped",
}


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")

    value = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须是对象：{path}")

    return value


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def validate_unique_ids(
    rows: List[Dict[str, str]],
    field: str,
    source_name: str,
) -> List[str]:
    ids = [str(row.get(field, "")).strip() for row in rows]

    empty_count = sum(not case_id for case_id in ids)
    if empty_count:
        raise ValueError(
            f"{source_name}存在{empty_count}条空场景ID"
        )

    duplicates = sorted(
        case_id
        for case_id, count in Counter(ids).items()
        if count > 1
    )

    if duplicates:
        raise ValueError(
            f"{source_name}存在重复场景ID："
            + ", ".join(duplicates)
        )

    return ids


def build_summary(
    validation: Dict[str, Any],
    review_rows: List[Dict[str, str]],
    traceability_rows: List[Dict[str, str]],
) -> Dict[str, Any]:
    total = int(validation.get("total_cases", 0))

    if total != len(review_rows):
        raise ValueError(
            "总场景数不一致："
            f"validation={total}，human-review={len(review_rows)}"
        )

    review_ids = validate_unique_ids(
        review_rows,
        "case_id",
        "human-review.csv",
    )
    traceability_ids = validate_unique_ids(
        traceability_rows,
        "ai_case_id",
        "ai-case-traceability.csv",
    )

    review_statuses = []
    selected_ids = []

    for row in review_rows:
        status = normalize(row.get("review_status")) or "pending"
        if status not in REVIEW_STATUSES:
            raise ValueError(
                "未知review_status："
                f"{row.get('case_id')}={status}"
            )
        review_statuses.append(status)

        selected = normalize(
            row.get("selected_for_automation")
        )
        if selected not in {"", "yes", "no"}:
            raise ValueError(
                "selected_for_automation只允许"
                f"yes、no或空值：{row.get('case_id')}={selected}"
            )
        if selected == "yes":
            selected_ids.append(str(row["case_id"]).strip())

    review_id_set = set(review_ids)
    selected_id_set = set(selected_ids)
    traceability_id_set = set(traceability_ids)

    orphan_traceability = sorted(
        traceability_id_set - review_id_set
    )
    if orphan_traceability:
        raise ValueError(
            "追踪矩阵包含评审表不存在的场景："
            + ", ".join(orphan_traceability)
        )

    missing_traceability = sorted(
        selected_id_set - traceability_id_set
    )
    if missing_traceability:
        raise ValueError(
            "选中自动化但缺少追踪记录："
            + ", ".join(missing_traceability)
        )

    unselected_traceability = sorted(
        traceability_id_set - selected_id_set
    )
    if unselected_traceability:
        raise ValueError(
            "追踪矩阵包含未选中的场景："
            + ", ".join(unselected_traceability)
        )

    implementation_statuses = []
    execution_statuses = []
    mapped_count = 0

    for row in traceability_rows:
        implementation = normalize(
            row.get("implementation_status")
        )
        if implementation not in IMPLEMENTATION_STATUSES:
            raise ValueError(
                "未知implementation_status："
                f"{row.get('ai_case_id')}={implementation}"
            )
        implementation_statuses.append(implementation)

        execution = normalize(
            row.get("execution_status")
        ) or "not_run"
        if execution not in EXECUTION_STATUSES:
            raise ValueError(
                "未知execution_status："
                f"{row.get('ai_case_id')}={execution}"
            )
        execution_statuses.append(execution)

        if (
            str(row.get("java_test_class", "")).strip()
            and str(row.get("java_test_method", "")).strip()
        ):
            mapped_count += 1

    status_counts = Counter(review_statuses)
    implementation_counts = Counter(implementation_statuses)
    execution_counts = Counter(execution_statuses)

    accepted = status_counts["accepted"]
    revised = status_counts["revised"]
    rejected = status_counts["rejected"]
    pending = status_counts["pending"]
    reviewed = accepted + revised + rejected
    adopted = accepted + revised

    selected_count = len(selected_ids)
    existing_count = implementation_counts["existing"]

    schema_pass = int(
        validation.get("schema_pass_count", 0)
    )
    business_pass = int(
        validation.get("business_pass_count", 0)
    )

    if not 0 <= schema_pass <= total:
        raise ValueError("schema_pass_count超出有效范围")
    if not 0 <= business_pass <= total:
        raise ValueError("business_pass_count超出有效范围")

    return {
        "total_cases": total,
        "schema_validation": {
            "pass_count": schema_pass,
            "pass_rate": safe_rate(schema_pass, total),
        },
        "business_validation": {
            "pass_count": business_pass,
            "pass_rate": safe_rate(business_pass, total),
            "global_errors": validation.get(
                "global_errors", []
            ),
        },
        "human_review": {
            "reviewed_count": reviewed,
            "pending_count": pending,
            "progress_rate": safe_rate(reviewed, total),
            "accepted_count": accepted,
            "revised_count": revised,
            "rejected_count": rejected,
            "adopted_count": adopted,
            "accepted_rate_among_reviewed": safe_rate(
                accepted, reviewed
            ),
            "revised_rate_among_reviewed": safe_rate(
                revised, reviewed
            ),
            "rejected_rate_among_reviewed": safe_rate(
                rejected, reviewed
            ),
            "adoption_rate_among_reviewed": safe_rate(
                adopted, reviewed
            ),
            "accepted_share_of_total": safe_rate(
                accepted, total
            ),
            "revised_share_of_total": safe_rate(
                revised, total
            ),
            "rejected_share_of_total": safe_rate(
                rejected, total
            ),
            "adopted_share_of_total": safe_rate(
                adopted, total
            ),
        },
        "automation": {
            "selected_count": selected_count,
            "mapped_count": mapped_count,
            "existing_count": existing_count,
            "needs_update_count": implementation_counts[
                "needs_update"
            ],
            "needs_new_count": implementation_counts[
                "needs_new"
            ],
            "reuse_rate": safe_rate(
                existing_count, selected_count
            ),
            "existing_share_of_total": safe_rate(
                existing_count, total
            ),
        },
        "execution": {
            "not_run_count": execution_counts["not_run"],
            "passed_count": execution_counts["passed"],
            "failed_count": execution_counts["failed"],
            "skipped_count": execution_counts["skipped"],
        },
    }


def render_markdown(summary: Dict[str, Any]) -> str:
    total = summary["total_cases"]
    schema = summary["schema_validation"]
    business = summary["business_validation"]
    human = summary["human_review"]
    automation = summary["automation"]
    execution = summary["execution"]

    return (
        "# AI结构化测试场景审核摘要\n\n"
        "## 一、机器校验\n\n"
        f"- 场景总数：{total}\n"
        f"- Schema通过：{schema['pass_count']}/{total}"
        f"（{schema['pass_rate']:.2%}）\n"
        f"- 业务规则通过：{business['pass_count']}/{total}"
        f"（{business['pass_rate']:.2%}）\n\n"
        "## 二、人工评审进度\n\n"
        f"- 已评审：{human['reviewed_count']}/{total}"
        f"（{human['progress_rate']:.2%}）\n"
        f"- 待评审：{human['pending_count']}/{total}"
        f"（{safe_rate(human['pending_count'], total):.2%}）\n\n"
        "## 三、已评审场景质量\n\n"
        f"- 直接采纳：{human['accepted_count']}/"
        f"{human['reviewed_count']}"
        f"（{human['accepted_rate_among_reviewed']:.2%}）\n"
        f"- 修改后采纳：{human['revised_count']}/"
        f"{human['reviewed_count']}"
        f"（{human['revised_rate_among_reviewed']:.2%}）\n"
        f"- 拒绝：{human['rejected_count']}/"
        f"{human['reviewed_count']}"
        f"（{human['rejected_rate_among_reviewed']:.2%}）\n"
        f"- 总体采纳：{human['adopted_count']}/"
        f"{human['reviewed_count']}"
        f"（{human['adoption_rate_among_reviewed']:.2%}）\n\n"
        "## 四、全量场景当前状态\n\n"
        f"- 直接采纳占比：{human['accepted_count']}/{total}"
        f"（{human['accepted_share_of_total']:.2%}）\n"
        f"- 修改后采纳占比：{human['revised_count']}/{total}"
        f"（{human['revised_share_of_total']:.2%}）\n"
        f"- 已采纳占比：{human['adopted_count']}/{total}"
        f"（{human['adopted_share_of_total']:.2%}）\n\n"
        "## 五、自动化追踪\n\n"
        f"- 进入首批自动化：{automation['selected_count']}\n"
        f"- 映射到Java测试：{automation['mapped_count']}\n"
        f"- 现有自动化复用：{automation['existing_count']}/"
        f"{automation['selected_count']}"
        f"（{automation['reuse_rate']:.2%}）\n"
        f"- 全量已有自动化占比：{automation['existing_count']}/"
        f"{total}（{automation['existing_share_of_total']:.2%}）\n"
        f"- 本轮已通过：{execution['passed_count']}\n"
        f"- 本轮失败：{execution['failed_count']}\n"
        f"- 本轮未执行：{execution['not_run_count']}\n"
        f"- 本轮跳过：{execution['skipped_count']}\n\n"
        "## 六、阶段结论\n\n"
        "当前机器校验结果只能证明结构和程序化规则通过。"
        "已完成人工评审的场景仍需结合业务语义、测试数据和"
        "断言完整性判断是否能够直接采用。自动化代码已映射"
        "不代表本轮已经执行，执行状态必须以新的日志或报告"
        "为证据。\n"
    )


def generate_summary(
    validation_path: Path,
    review_path: Path,
    traceability_path: Path,
    markdown_output: Path,
    json_output: Path,
) -> Dict[str, Any]:
    summary = build_summary(
        read_json(validation_path),
        read_csv(review_path),
        read_csv(traceability_path),
    )

    markdown_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    json_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    markdown_output.write_text(
        render_markdown(summary),
        encoding="utf-8",
    )
    json_output.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="汇总AI场景校验、人工评审和自动化追踪指标"
    )
    parser.add_argument(
        "--validation",
        type=Path,
        default=Path("output/validation-summary.json"),
    )
    parser.add_argument(
        "--review",
        type=Path,
        default=Path("output/human-review.csv"),
    )
    parser.add_argument(
        "--traceability",
        type=Path,
        default=Path("output/ai-case-traceability.csv"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("output/review-summary.md"),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("output/review-summary.json"),
    )
    args = parser.parse_args()

    summary = generate_summary(
        validation_path=args.validation,
        review_path=args.review,
        traceability_path=args.traceability,
        markdown_output=args.markdown_output,
        json_output=args.json_output,
    )

    print(
        render_markdown(summary),
        end="",
    )
    print(f"JSON_FILE={args.json_output}")
    print(f"MARKDOWN_FILE={args.markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
