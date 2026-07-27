from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]

MODULE_PATH = (
    PROJECT_DIR
    / "src"
    / "failure_diagnosis.py"
)

SCHEMA_PATH = (
    PROJECT_DIR
    / "schemas"
    / "failure-diagnosis.schema.json"
)


class FailureDiagnosisTest(unittest.TestCase):

    def require_feature(self):
        if (
            not MODULE_PATH.exists()
            or not SCHEMA_PATH.exists()
        ):
            self.skipTest(
                "失败诊断模块或Schema尚未实现"
            )

        from src.failure_diagnosis import load_json

        return load_json(SCHEMA_PATH)

    @staticmethod
    def prediction(
        failure_id: str,
        layer: str,
        tag: str,
        root_cause: str,
    ):
        return {
            "failure_id": failure_id,
            "diagnosis_summary":
                "根据日志和调用链定位故障",
            "failure_layer": layer,
            "root_cause_tag": tag,
            "root_cause": root_cause,
            "evidence": [
                {
                    "source": "application.log",
                    "excerpt": root_cause,
                }
            ],
            "confidence": 0.9,
            "troubleshooting_steps": [
                "核对异常日志和相关配置"
            ],
            "human_review_required": False,
        }

    def test_schema_and_module_files_exist(self):
        self.assertTrue(MODULE_PATH.exists())
        self.assertTrue(SCHEMA_PATH.exists())

    def test_schema_accepts_valid_and_rejects_invalid_result(
        self,
    ):
        schema = self.require_feature()

        from src.failure_diagnosis import (
            validate_diagnosis,
        )

        valid = self.prediction(
            "DEFECT-001",
            "application",
            "INTERCEPTOR_ROUTING",
            "/error再次被LoginInterceptor拦截",
        )

        self.assertEqual(
            [],
            validate_diagnosis(valid, schema),
        )

        invalid = dict(valid)
        invalid["confidence"] = 1.5

        errors = validate_diagnosis(
            invalid,
            schema,
        )

        self.assertTrue(errors)

        self.assertTrue(
            any(
                "confidence" in error
                for error in errors
            )
        )

    def test_evaluator_calculates_deterministic_metrics(
        self,
    ):
        schema = self.require_feature()

        from src.failure_diagnosis import (
            evaluate_diagnoses,
        )

        gold = [
            {
                "failure_id": "DEFECT-001",
                "failure_layer": "application",
                "root_cause_tag":
                    "INTERCEPTOR_ROUTING",
                "evidence_keywords": [
                    "/error",
                    "LoginInterceptor",
                ],
            },
            {
                "failure_id": "DEFECT-005",
                "failure_layer": "context",
                "root_cause_tag":
                    "THREADLOCAL_CONTEXT_LEAK",
                "evidence_keywords": [
                    "ThreadLocal",
                    "removeUser",
                ],
            },
        ]

        predictions = [
            self.prediction(
                "DEFECT-001",
                "application",
                "INTERCEPTOR_ROUTING",
                "/error被LoginInterceptor再次拦截",
            ),
            self.prediction(
                "DEFECT-005",
                "context",
                "AUTHENTICATION_FAILURE",
                "ThreadLocal中残留历史身份",
            ),
        ]

        summary = evaluate_diagnoses(
            gold,
            predictions,
            schema,
        )

        self.assertEqual(
            2,
            summary["total_cases"],
        )

        self.assertEqual(
            1.0,
            summary["schema_pass_rate"],
        )

        self.assertEqual(
            1.0,
            summary["failure_layer_accuracy"],
        )

        self.assertEqual(
            0.5,
            summary["root_cause_tag_accuracy"],
        )

        self.assertEqual(
            1,
            summary["full_match_count"],
        )

        self.assertEqual(
            0.75,
            summary[
                "average_evidence_keyword_recall"
            ],
        )

        self.assertEqual(
            2,
            summary[
                "manual_text_review_count"
            ],
        )

    def test_evaluator_rejects_missing_prediction(
        self,
    ):
        schema = self.require_feature()

        from src.failure_diagnosis import (
            DiagnosisDataError,
            evaluate_diagnoses,
        )

        gold = [
            {
                "failure_id": "DEFECT-001",
                "failure_layer": "application",
                "root_cause_tag":
                    "INTERCEPTOR_ROUTING",
                "evidence_keywords": [
                    "/error"
                ],
            }
        ]

        with self.assertRaisesRegex(
            DiagnosisDataError,
            "缺少诊断",
        ):
            evaluate_diagnoses(
                gold,
                [],
                schema,
            )


if __name__ == "__main__":
    unittest.main()
