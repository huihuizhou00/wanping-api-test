from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List


class DiagnosisInputError(ValueError):
    """诊断输入无法安全构建时抛出。"""


REQUIRED_GOLD_FIELDS = {
    "failure_id",
    "title",
    "diagnosis_title",
    "module",
    "actual_result",
    "expected_result",
    "source_file",
}

FORBIDDEN_INPUT_FIELDS = {
    "failure_layer",
    "root_cause_tag",
    "root_cause",
    "remediation",
    "evidence_keywords",
    "source_section",
    "status",
}


def build_diagnosis_input(
    gold_record: Dict[str, Any],
) -> Dict[str, Any]:
    missing = (
        REQUIRED_GOLD_FIELDS
        - set(gold_record)
    )

    if missing:
        raise DiagnosisInputError(
            "Gold记录缺少字段："
            + ", ".join(sorted(missing))
        )

    failure_id = str(
        gold_record["failure_id"]
    ).strip()

    if not failure_id:
        raise DiagnosisInputError(
            "failure_id不能为空"
        )

    diagnosis_input = {
        "failure_id": failure_id,
        "title": str(
            gold_record["diagnosis_title"]
        ).strip(),
        "module": str(
            gold_record["module"]
        ).strip(),
        "evidence_sources": [
            {
                "source": "actual_result",
                "content": str(
                    gold_record[
                        "actual_result"
                    ]
                ).strip(),
            },
            {
                "source": "expected_result",
                "content": str(
                    gold_record[
                        "expected_result"
                    ]
                ).strip(),
            },
        ],
        "source_file": str(
            gold_record["source_file"]
        ).strip(),
    }

    leaked_fields = (
        FORBIDDEN_INPUT_FIELDS
        & set(diagnosis_input)
    )

    if leaked_fields:
        raise DiagnosisInputError(
            "诊断输入包含答案字段："
            + ", ".join(
                sorted(leaked_fields)
            )
        )

    return diagnosis_input


def build_diagnosis_inputs(
    gold_records:
        Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen_ids = set()

    for gold_record in gold_records:
        diagnosis_input = (
            build_diagnosis_input(
                gold_record
            )
        )

        failure_id = diagnosis_input[
            "failure_id"
        ]

        if failure_id in seen_ids:
            raise DiagnosisInputError(
                "诊断输入存在重复failure_id："
                f"{failure_id}"
            )

        seen_ids.add(failure_id)
        result.append(diagnosis_input)

    return result


def render_diagnosis_prompt(
    diagnosis_input: Dict[str, Any],
    template: str,
) -> str:
    marker = (
        "{{DIAGNOSIS_INPUT_JSON}}"
    )

    if marker not in template:
        raise DiagnosisInputError(
            "Prompt模板缺少输入占位符"
        )

    payload = json.dumps(
        diagnosis_input,
        ensure_ascii=False,
        indent=2,
    )

    return template.replace(
        marker,
        payload,
        1,
    )
