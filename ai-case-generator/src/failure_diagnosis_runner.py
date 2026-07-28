from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Protocol, Tuple

from .failure_diagnosis import validate_diagnosis
from .failure_diagnosis_inputs import render_diagnosis_prompt


class DiagnosisGenerationError(RuntimeError):
    """模型在限定重试次数内未生成可用诊断时抛出。"""


class DiagnosisClient(Protocol):
    def generate(self, prompt: str) -> Dict[str, Any]:
        ...


def _normalize_evidence_text(value: str) -> str:
    return re.sub(r"\s+", "", value.casefold())


def validate_prediction_against_input(
    prediction: Dict[str, Any],
    diagnosis_input: Dict[str, Any],
) -> List[str]:
    errors: List[str] = []
    source_map = {
        str(item.get("source", "")): str(item.get("content", ""))
        for item in diagnosis_input.get("evidence_sources", [])
        if isinstance(item, dict)
    }

    for index, evidence in enumerate(prediction.get("evidence", [])):
        if not isinstance(evidence, dict):
            continue
        source = str(evidence.get("source", ""))
        excerpt = str(evidence.get("excerpt", ""))
        if source not in source_map:
            errors.append(
                f"evidence.{index}.source只能来自诊断输入：{source}"
            )
            continue
        normalized_excerpt = _normalize_evidence_text(excerpt)
        normalized_source = _normalize_evidence_text(source_map[source])
        if normalized_excerpt not in normalized_source:
            errors.append(
                f"evidence.{index}.excerpt必须是{source}中的原始片段"
            )

    confidence = prediction.get("confidence")
    human_review_required = prediction.get("human_review_required")
    if (
        isinstance(confidence, (int, float))
        and confidence < 0.8
        and human_review_required is not True
    ):
        errors.append(
            "confidence低于0.80时human_review_required必须为true"
        )
    if (
        prediction.get("failure_layer") == "unknown"
        and human_review_required is not True
    ):
        errors.append(
            "failure_layer为unknown时human_review_required必须为true"
        )

    return errors


def _build_retry_prompt(
    base_prompt: str,
    errors: List[str],
) -> str:
    feedback = "\n".join(f"- {error}" for error in errors)
    return (
        base_prompt
        + "\n\n上一次输出未通过程序校验，请只修正下列问题，"
        "并重新输出完整JSON对象：\n"
        + feedback
    )


def generate_diagnoses(
    diagnosis_inputs: List[Dict[str, Any]],
    template: str,
    schema: Dict[str, Any],
    client: DiagnosisClient,
    raw_dir: Path,
    max_retries: int = 1,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if max_retries < 0:
        raise ValueError("max_retries不能小于0")

    raw_dir.mkdir(parents=True, exist_ok=True)
    predictions: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []

    for diagnosis_input in diagnosis_inputs:
        failure_id = str(diagnosis_input.get("failure_id", "")).strip()
        if not failure_id:
            raise DiagnosisGenerationError("诊断输入缺少failure_id")

        base_prompt = render_diagnosis_prompt(diagnosis_input, template)
        validation_errors: List[str] = []

        for attempt in range(1, max_retries + 2):
            prompt = (
                base_prompt
                if attempt == 1
                else _build_retry_prompt(base_prompt, validation_errors)
            )
            prompt_path = raw_dir / f"{failure_id}-attempt-{attempt}.prompt.txt"
            output_path = raw_dir / f"{failure_id}-attempt-{attempt}.json"
            prompt_path.write_text(prompt, encoding="utf-8")

            try:
                prediction = client.generate(prompt)
            except Exception as exc:  # noqa: BLE001
                validation_errors = [f"模型调用失败：{exc}"]
                events.append(
                    {
                        "failure_id": failure_id,
                        "attempt": attempt,
                        "status": "call_error",
                        "errors": validation_errors,
                    }
                )
                if attempt > max_retries:
                    raise DiagnosisGenerationError(
                        f"{failure_id}模型调用失败：{exc}"
                    ) from exc
                continue

            output_path.write_text(
                json.dumps(prediction, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            validation_errors = validate_diagnosis(prediction, schema)
            validation_errors.extend(
                validate_prediction_against_input(
                    prediction,
                    diagnosis_input,
                )
            )
            if prediction.get("failure_id") != failure_id:
                validation_errors.append(
                    "failure_id必须与输入一致："
                    f"期望{failure_id}，实际{prediction.get('failure_id')}"
                )

            if not validation_errors:
                predictions.append(prediction)
                events.append(
                    {
                        "failure_id": failure_id,
                        "attempt": attempt,
                        "status": "passed",
                        "errors": [],
                    }
                )
                break

            events.append(
                {
                    "failure_id": failure_id,
                    "attempt": attempt,
                    "status": "validation_failed",
                    "errors": list(validation_errors),
                }
            )

            if attempt > max_retries:
                raise DiagnosisGenerationError(
                    f"{failure_id}在{max_retries + 1}次生成后仍未通过："
                    + "; ".join(validation_errors)
                )

    return predictions, events


def render_evaluation_markdown(
    summary: Dict[str, Any],
    model_name: str,
) -> str:
    total = summary["total_cases"]

    def percent(value: float) -> str:
        return f"{value * 100:.2f}%"

    lines = [
        "# AI失败诊断首轮评估报告",
        "",
        "## 一、评估信息",
        "",
        f"- 模型：{model_name}",
        f"- 故障样本数：{total}",
        "",
        "## 二、确定性指标",
        "",
        (
            "- Schema通过率："
            f"{summary['schema_pass_count']}/{total}"
            f"（{percent(summary['schema_pass_rate'])}）"
        ),
        (
            "- 故障层级准确率："
            f"{summary['failure_layer_match_count']}/{total}"
            f"（{percent(summary['failure_layer_accuracy'])}）"
        ),
        (
            "- 根因标签准确率："
            f"{summary['root_cause_tag_match_count']}/{total}"
            f"（{percent(summary['root_cause_tag_accuracy'])}）"
        ),
        (
            "- 层级与标签完全匹配率："
            f"{summary['full_match_count']}/{total}"
            f"（{percent(summary['full_match_rate'])}）"
        ),
        (
            "- 平均证据关键词召回率："
            f"{percent(summary['average_evidence_keyword_recall'])}"
        ),
        "",
        "## 三、人工复核",
        "",
        (
            "- 需要人工复核根因文本："
            f"{summary['manual_text_review_count']}/{total}"
        ),
        "- 说明：结构化指标由程序计算，自由文本因果关系仍需人工确认。",
        "",
        "## 四、逐条结果",
        "",
    ]

    for detail in summary["details"]:
        lines.extend(
            [
                f"### {detail['failure_id']}",
                "",
                f"- Schema通过：{detail['schema_pass']}",
                (
                    "- 故障层级："
                    f"期望 `{detail['expected_failure_layer']}`，"
                    f"实际 `{detail['predicted_failure_layer']}`，"
                    f"命中={detail['failure_layer_match']}"
                ),
                (
                    "- 根因标签："
                    f"期望 `{detail['expected_root_cause_tag']}`，"
                    f"实际 `{detail['predicted_root_cause_tag']}`，"
                    f"命中={detail['root_cause_tag_match']}"
                ),
                (
                    "- 证据关键词召回："
                    f"{detail['keyword_hit_count']}/"
                    f"{detail['keyword_total']}"
                    f"（{percent(detail['keyword_recall'])}）"
                ),
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"
