from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]

GOLD_PATH = (
    PROJECT_DIR
    / "data"
    / "failure-diagnosis"
    / "gold-failures.jsonl"
)

TEMPLATE_PATH = (
    PROJECT_DIR
    / "prompts"
    / "failure-diagnosis.txt"
)


class FailureDiagnosisInputsTest(unittest.TestCase):

    @staticmethod
    def load_gold_records():
        records = []

        with GOLD_PATH.open(
            encoding="utf-8"
        ) as file:
            for line in file:
                if line.strip():
                    records.append(
                        json.loads(line)
                    )

        return records

    def test_input_excludes_gold_answer_fields(self):
        from src.failure_diagnosis_inputs import (
            build_diagnosis_input,
        )

        for gold in self.load_gold_records():
            diagnosis_input = (
                build_diagnosis_input(gold)
            )

            self.assertNotIn(
                "failure_layer",
                diagnosis_input,
            )
            self.assertNotIn(
                "root_cause_tag",
                diagnosis_input,
            )
            self.assertNotIn(
                "root_cause",
                diagnosis_input,
            )
            self.assertNotIn(
                "remediation",
                diagnosis_input,
            )
            self.assertNotIn(
                "evidence_keywords",
                diagnosis_input,
            )

            serialized = json.dumps(
                diagnosis_input,
                ensure_ascii=False,
            )

            self.assertNotIn(
                gold["root_cause_tag"],
                serialized,
            )
            self.assertNotIn(
                gold["root_cause"],
                serialized,
            )
            self.assertNotIn(
                gold["remediation"],
                serialized,
            )

    def test_input_preserves_observable_information(self):
        from src.failure_diagnosis_inputs import (
            build_diagnosis_input,
        )

        gold = self.load_gold_records()[0]

        diagnosis_input = (
            build_diagnosis_input(gold)
        )

        self.assertEqual(
            gold["failure_id"],
            diagnosis_input["failure_id"],
        )
        self.assertEqual(
            gold["diagnosis_title"],
            diagnosis_input["title"],
        )

        self.assertNotEqual(
            gold["title"],
            diagnosis_input["title"],
        )
        self.assertEqual(
            gold["module"],
            diagnosis_input["module"],
        )

        sources = {
            item["source"]
            for item in diagnosis_input[
                "evidence_sources"
            ]
        }

        self.assertEqual(
            {
                "actual_result",
                "expected_result",
            },
            sources,
        )

    def test_prompt_contains_input_but_not_gold_answer(
        self,
    ):
        from src.failure_diagnosis_inputs import (
            build_diagnosis_input,
            render_diagnosis_prompt,
        )

        gold = self.load_gold_records()[0]

        diagnosis_input = (
            build_diagnosis_input(gold)
        )

        template = TEMPLATE_PATH.read_text(
            encoding="utf-8"
        )

        prompt = render_diagnosis_prompt(
            diagnosis_input,
            template,
        )

        self.assertIn(
            gold["failure_id"],
            prompt,
        )
        self.assertIn(
            gold["actual_result"],
            prompt,
        )
        self.assertNotIn(
            gold["root_cause_tag"],
            prompt,
        )
        self.assertNotIn(
            gold["root_cause"],
            prompt,
        )

    def test_diagnosis_titles_do_not_repeat_known_root_cause_terms(
        self,
    ):
        from src.failure_diagnosis_inputs import (
            build_diagnosis_input,
        )

        forbidden_terms = {
            "DEFECT-001": [
                "/error",
                "LoginInterceptor",
                "二次拦截",
            ],
            "DEFECT-002": [
                "syncSend",
                "异常向上抛出",
                "降级隔离",
            ],
            "DEFECT-003": [
                "挂载丢失",
                "不可写",
                "根分区",
            ],
            "DEFECT-004": [
                "unLock",
                "未回源MySQL",
                "释放错误Key",
            ],
            "DEFECT-005": [
                "ThreadLocal未清理",
                "removeUser",
                "afterCompletion",
            ],
        }

        for gold in self.load_gold_records():
            diagnosis_input = (
                build_diagnosis_input(gold)
            )

            title = diagnosis_input["title"]

            for term in forbidden_terms[
                gold["failure_id"]
            ]:
                self.assertNotIn(
                    term,
                    title,
                    (
                        f'{gold["failure_id"]}'
                        f"标题泄漏根因词：{term}"
                    ),
                )

    def test_all_five_inputs_have_unique_ids(self):
        from src.failure_diagnosis_inputs import (
            build_diagnosis_inputs,
        )

        inputs = build_diagnosis_inputs(
            self.load_gold_records()
        )

        self.assertEqual(5, len(inputs))

        failure_ids = [
            item["failure_id"]
            for item in inputs
        ]

        self.assertEqual(
            len(failure_ids),
            len(set(failure_ids)),
        )


if __name__ == "__main__":
    unittest.main()
