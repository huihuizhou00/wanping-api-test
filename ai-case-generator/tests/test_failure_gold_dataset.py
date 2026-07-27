from __future__ import annotations

import json
import unittest
from pathlib import Path


DATASET_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "failure-diagnosis"
    / "gold-failures.jsonl"
)

REQUIRED_FIELDS = {
    "failure_id",
    "title",
    "module",
    "failure_layer",
    "root_cause_tag",
    "actual_result",
    "expected_result",
    "root_cause",
    "remediation",
    "evidence_keywords",
    "source_file",
    "source_section",
    "status",
}

ALLOWED_LAYERS = {
    "application",
    "middleware",
    "cache",
    "context",
}

ALLOWED_STATUS = {
    "resolved",
}


class FailureGoldDatasetTest(unittest.TestCase):
    def load_records(self):
        records = []

        with DATASET_PATH.open(
            encoding="utf-8"
        ) as file:
            for line_number, line in enumerate(
                file,
                start=1,
            ):
                if not line.strip():
                    continue

                try:
                    records.append(
                        json.loads(line)
                    )
                except json.JSONDecodeError as error:
                    self.fail(
                        "第"
                        f"{line_number}"
                        "行不是合法JSON："
                        f"{error}"
                    )

        return records

    def test_contains_five_real_defects(self):
        records = self.load_records()

        self.assertEqual(5, len(records))

        actual_ids = {
            record["failure_id"]
            for record in records
        }

        expected_ids = {
            "DEFECT-001",
            "DEFECT-002",
            "DEFECT-003",
            "DEFECT-004",
            "DEFECT-005",
        }

        self.assertEqual(
            expected_ids,
            actual_ids,
        )

    def test_records_have_complete_labels(self):
        records = self.load_records()

        for record in records:
            missing = (
                REQUIRED_FIELDS
                - set(record)
            )

            self.assertFalse(
                missing,
                (
                    f'{record.get("failure_id")} '
                    f"缺少字段：{sorted(missing)}"
                ),
            )

            self.assertIn(
                record["failure_layer"],
                ALLOWED_LAYERS,
            )

            self.assertIn(
                record["status"],
                ALLOWED_STATUS,
            )

            self.assertTrue(
                record["root_cause"].strip()
            )

            self.assertTrue(
                record["evidence_keywords"]
            )

            self.assertEqual(
                "docs/defects/"
                "api-automation-defects.md",
                record["source_file"],
            )

    def test_failure_ids_are_unique(self):
        records = self.load_records()

        failure_ids = [
            record["failure_id"]
            for record in records
        ]

        self.assertEqual(
            len(failure_ids),
            len(set(failure_ids)),
        )


if __name__ == "__main__":
    unittest.main()
