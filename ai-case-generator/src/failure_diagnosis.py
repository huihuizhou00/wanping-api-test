from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from jsonschema import Draft202012Validator


class DiagnosisDataError(ValueError):
    """Gold数据与AI结果无法安全比较时抛出。"""


def load_json(
    path: Path,
) -> Dict[str, Any]:
    with path.open(
        encoding="utf-8"
    ) as file:
        value = json.load(file)

    if not isinstance(value, dict):
        raise DiagnosisDataError(
            f"JSON根节点必须是对象：{path}"
        )

    return value


def load_jsonl(
    path: Path,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []

    with path.open(
        encoding="utf-8"
    ) as file:
        for line_number, line in enumerate(
            file,
            start=1,
        ):
            if not line.strip():
                continue

            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise DiagnosisDataError(
                    f"{path}第{line_number}行"
                    f"不是合法JSON：{error}"
                ) from error

            if not isinstance(value, dict):
                raise DiagnosisDataError(
                    f"{path}第{line_number}行"
                    "根节点必须是对象"
                )

            records.append(value)

    return records


def validate_diagnosis(
    diagnosis: Dict[str, Any],
    schema: Dict[str, Any],
) -> List[str]:
    validator = Draft202012Validator(schema)

    errors = sorted(
        validator.iter_errors(diagnosis),
        key=lambda error: list(
            error.absolute_path
        ),
    )

    messages: List[str] = []

    for error in errors:
        path = ".".join(
            str(item)
            for item in error.absolute_path
        )

        if path:
            messages.append(
                f"{path}: {error.message}"
            )
        else:
            messages.append(error.message)

    return messages


def _index_unique(
    records: Iterable[Dict[str, Any]],
    id_field: str,
    dataset_name: str,
) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}

    for record in records:
        record_id = str(
            record.get(id_field, "")
        ).strip()

        if not record_id:
            raise DiagnosisDataError(
                f"{dataset_name}存在缺少"
                f"{id_field}的记录"
            )

        if record_id in index:
            raise DiagnosisDataError(
                f"{dataset_name}存在重复"
                f"{id_field}：{record_id}"
            )

        index[record_id] = record

    return index


def _normalize_text(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        "",
        value.casefold(),
    )


def _prediction_text(
    prediction: Dict[str, Any],
) -> str:
    parts = [
        str(
            prediction.get(
                "diagnosis_summary",
                "",
            )
        ),
        str(
            prediction.get(
                "root_cause",
                "",
            )
        ),
    ]

    for evidence in prediction.get(
        "evidence",
        [],
    ):
        if isinstance(evidence, dict):
            parts.append(
                str(
                    evidence.get(
                        "excerpt",
                        "",
                    )
                )
            )

    for step in prediction.get(
        "troubleshooting_steps",
        [],
    ):
        parts.append(str(step))

    return _normalize_text(
        " ".join(parts)
    )


def _evidence_keyword_metrics(
    gold: Dict[str, Any],
    prediction: Dict[str, Any],
) -> Dict[str, Any]:
    keywords = [
        str(keyword)
        for keyword in gold.get(
            "evidence_keywords",
            [],
        )
        if str(keyword).strip()
    ]

    prediction_text = _prediction_text(
        prediction
    )

    hits = [
        keyword
        for keyword in keywords
        if _normalize_text(keyword)
        in prediction_text
    ]

    if keywords:
        recall = (
            len(hits)
            / len(keywords)
        )
    else:
        recall = 1.0

    return {
        "keyword_total": len(keywords),
        "keyword_hits": hits,
        "keyword_hit_count": len(hits),
        "keyword_recall": recall,
    }


def evaluate_diagnoses(
    gold_records: List[Dict[str, Any]],
    prediction_records:
        List[Dict[str, Any]],
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    gold_by_id = _index_unique(
        gold_records,
        "failure_id",
        "Gold Dataset",
    )

    predictions_by_id = _index_unique(
        prediction_records,
        "failure_id",
        "AI诊断结果",
    )

    gold_ids = set(gold_by_id)
    prediction_ids = set(
        predictions_by_id
    )

    missing = sorted(
        gold_ids - prediction_ids
    )

    extra = sorted(
        prediction_ids - gold_ids
    )

    if missing or extra:
        parts = []

        if missing:
            parts.append(
                "缺少诊断："
                + ", ".join(missing)
            )

        if extra:
            parts.append(
                "存在未知诊断："
                + ", ".join(extra)
            )

        raise DiagnosisDataError(
            "；".join(parts)
        )

    details: List[Dict[str, Any]] = []

    schema_pass_count = 0
    layer_match_count = 0
    tag_match_count = 0
    full_match_count = 0
    evidence_recall_sum = 0.0

    for failure_id in sorted(
        gold_by_id
    ):
        gold = gold_by_id[failure_id]

        prediction = (
            predictions_by_id[
                failure_id
            ]
        )

        schema_errors = (
            validate_diagnosis(
                prediction,
                schema,
            )
        )

        schema_pass = (
            not schema_errors
        )

        layer_match = (
            prediction.get(
                "failure_layer"
            )
            == gold.get(
                "failure_layer"
            )
        )

        tag_match = (
            prediction.get(
                "root_cause_tag"
            )
            == gold.get(
                "root_cause_tag"
            )
        )

        evidence_metrics = (
            _evidence_keyword_metrics(
                gold,
                prediction,
            )
        )

        schema_pass_count += int(
            schema_pass
        )

        layer_match_count += int(
            layer_match
        )

        tag_match_count += int(
            tag_match
        )

        full_match_count += int(
            layer_match
            and tag_match
        )

        evidence_recall_sum += (
            evidence_metrics[
                "keyword_recall"
            ]
        )

        details.append(
            {
                "failure_id":
                    failure_id,
                "schema_pass":
                    schema_pass,
                "schema_errors":
                    schema_errors,
                "expected_failure_layer":
                    gold.get(
                        "failure_layer"
                    ),
                "predicted_failure_layer":
                    prediction.get(
                        "failure_layer"
                    ),
                "failure_layer_match":
                    layer_match,
                "expected_root_cause_tag":
                    gold.get(
                        "root_cause_tag"
                    ),
                "predicted_root_cause_tag":
                    prediction.get(
                        "root_cause_tag"
                    ),
                "root_cause_tag_match":
                    tag_match,
                **evidence_metrics,
                "manual_text_review_required":
                    True,
            }
        )

    total = len(gold_by_id)

    return {
        "total_cases": total,
        "schema_pass_count":
            schema_pass_count,
        "schema_pass_rate": (
            schema_pass_count / total
            if total
            else 0.0
        ),
        "failure_layer_match_count":
            layer_match_count,
        "failure_layer_accuracy": (
            layer_match_count / total
            if total
            else 0.0
        ),
        "root_cause_tag_match_count":
            tag_match_count,
        "root_cause_tag_accuracy": (
            tag_match_count / total
            if total
            else 0.0
        ),
        "full_match_count":
            full_match_count,
        "full_match_rate": (
            full_match_count / total
            if total
            else 0.0
        ),
        "average_evidence_keyword_recall": (
            evidence_recall_sum / total
            if total
            else 0.0
        ),
        "manual_text_review_count":
            total,
        "details": details,
    }
