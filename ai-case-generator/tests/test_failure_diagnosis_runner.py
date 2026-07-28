from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.failure_diagnosis_runner import (
    generate_diagnoses,
    render_evaluation_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas/failure-diagnosis.schema.json").read_text(
        encoding="utf-8"
    )
)
TEMPLATE = (
    ROOT / "prompts/failure-diagnosis.txt"
).read_text(encoding="utf-8")


class FakeClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        if not self.outputs:
            raise AssertionError("没有剩余伪造输出")
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


def valid_prediction(failure_id="DEFECT-001"):
    return {
        "failure_id": failure_id,
        "diagnosis_summary": "根据可观察事实定位异常",
        "failure_layer": "application",
        "root_cause_tag": "INTERCEPTOR_ROUTING",
        "root_cause": "异常路由再次经过登录拦截器",
        "evidence": [
            {
                "source": "actual_result",
                "excerpt": "无Token时返回HTTP 401",
            }
        ],
        "confidence": 0.9,
        "troubleshooting_steps": ["检查/error路由和拦截器配置"],
        "human_review_required": False,
    }


class FailureDiagnosisRunnerTest(unittest.TestCase):
    def test_generates_valid_diagnosis(self):
        client = FakeClient([valid_prediction()])
        diagnosis_inputs = [
            {
                "failure_id": "DEFECT-001",
                "title": "参数异常请求被错误返回401",
                "module": "登录拦截与异常处理",
                "evidence_sources": [
                    {
                        "source": "actual_result",
                        "content": "无Token时返回HTTP 401",
                    },
                    {
                        "source": "expected_result",
                        "content": "应统一返回HTTP 400",
                    },
                ],
                "source_file": "docs/defects/api-automation-defects.md",
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            predictions, events = generate_diagnoses(
                diagnosis_inputs,
                TEMPLATE,
                SCHEMA,
                client,
                Path(directory),
                max_retries=1,
            )

        self.assertEqual(1, len(predictions))
        self.assertEqual("passed", events[0]["status"])
        self.assertEqual(1, len(client.prompts))

    def test_retries_schema_invalid_output(self):
        invalid = valid_prediction()
        invalid["confidence"] = 1.5
        client = FakeClient([invalid, valid_prediction()])
        diagnosis_inputs = [
            {
                "failure_id": "DEFECT-001",
                "title": "参数异常请求被错误返回401",
                "module": "登录拦截与异常处理",
                "evidence_sources": [
                    {
                        "source": "actual_result",
                        "content": "无Token时返回HTTP 401",
                    },
                    {
                        "source": "expected_result",
                        "content": "应统一返回HTTP 400",
                    },
                ],
                "source_file": "docs/defects/api-automation-defects.md",
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            predictions, events = generate_diagnoses(
                diagnosis_inputs,
                TEMPLATE,
                SCHEMA,
                client,
                Path(directory),
                max_retries=1,
            )

        self.assertEqual(1, len(predictions))
        self.assertEqual(
            ["validation_failed", "passed"],
            [event["status"] for event in events],
        )
        self.assertIn("上一次输出未通过程序校验", client.prompts[1])

    def test_retries_hallucinated_evidence_source(self):
        invalid = valid_prediction()
        invalid["evidence"] = [
            {
                "source": "application.log",
                "excerpt": "不存在于输入中的日志",
            }
        ]
        client = FakeClient([invalid, valid_prediction()])
        diagnosis_inputs = [
            {
                "failure_id": "DEFECT-001",
                "title": "参数异常请求被错误返回401",
                "module": "登录拦截与异常处理",
                "evidence_sources": [
                    {
                        "source": "actual_result",
                        "content": "无Token时返回HTTP 401",
                    },
                    {
                        "source": "expected_result",
                        "content": "应统一返回HTTP 400",
                    },
                ],
                "source_file": "docs/defects/api-automation-defects.md",
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            predictions, events = generate_diagnoses(
                diagnosis_inputs,
                TEMPLATE,
                SCHEMA,
                client,
                Path(directory),
                max_retries=1,
            )

        self.assertEqual(1, len(predictions))
        self.assertEqual(
            ["validation_failed", "passed"],
            [event["status"] for event in events],
        )
        self.assertIn(
            "evidence.0.source只能来自诊断输入",
            events[0]["errors"][0],
        )

    def test_markdown_contains_core_metrics(self):
        summary = {
            "total_cases": 5,
            "schema_pass_count": 5,
            "schema_pass_rate": 1.0,
            "failure_layer_match_count": 4,
            "failure_layer_accuracy": 0.8,
            "root_cause_tag_match_count": 3,
            "root_cause_tag_accuracy": 0.6,
            "full_match_count": 3,
            "full_match_rate": 0.6,
            "average_evidence_keyword_recall": 0.7,
            "manual_text_review_count": 5,
            "details": [
                {
                    "failure_id": "DEFECT-001",
                    "schema_pass": True,
                    "expected_failure_layer": "application",
                    "predicted_failure_layer": "application",
                    "failure_layer_match": True,
                    "expected_root_cause_tag": "INTERCEPTOR_ROUTING",
                    "predicted_root_cause_tag": "INTERCEPTOR_ROUTING",
                    "root_cause_tag_match": True,
                    "keyword_hit_count": 2,
                    "keyword_total": 4,
                    "keyword_recall": 0.5,
                }
            ],
        }

        markdown = render_evaluation_markdown(summary, "qwen-test")

        self.assertIn("故障层级准确率：4/5（80.00%）", markdown)
        self.assertIn("根因标签准确率：3/5（60.00%）", markdown)
        self.assertIn("DEFECT-001", markdown)


if __name__ == "__main__":
    unittest.main()
