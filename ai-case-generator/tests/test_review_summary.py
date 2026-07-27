from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src import review_summary


class ReviewSummaryTest(unittest.TestCase):
    @staticmethod
    def write_json(path: Path, data: dict) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def write_csv(
        path: Path,
        fieldnames: list[str],
        rows: list[dict[str, str]],
    ) -> None:
        with path.open(
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

    def create_valid_inputs(self, directory: Path):
        validation_path = directory / "validation-summary.json"
        review_path = directory / "human-review.csv"
        traceability_path = directory / "ai-case-traceability.csv"

        self.write_json(
            validation_path,
            {
                "total_cases": 24,
                "schema_pass_count": 24,
                "schema_pass_rate": 1.0,
                "business_pass_count": 24,
                "business_pass_rate": 1.0,
                "global_errors": [],
            },
        )

        review_rows = []
        for index in range(1, 25):
            selected = index <= 6
            review_rows.append(
                {
                    "case_id": f"AI-CASE-{index:03d}",
                    "review_status": (
                        "revised" if selected else ""
                    ),
                    "selected_for_automation": (
                        "yes" if selected else ""
                    ),
                }
            )

        self.write_csv(
            review_path,
            [
                "case_id",
                "review_status",
                "selected_for_automation",
            ],
            review_rows,
        )

        traceability_rows = [
            {
                "ai_case_id": f"AI-CASE-{index:03d}",
                "implementation_status": "existing",
                "java_test_class": "ExampleTest",
                "java_test_method": f"testCase{index}",
                "execution_status": "not_run",
            }
            for index in range(1, 7)
        ]

        self.write_csv(
            traceability_path,
            [
                "ai_case_id",
                "implementation_status",
                "java_test_class",
                "java_test_method",
                "execution_status",
            ],
            traceability_rows,
        )

        return (
            validation_path,
            review_path,
            traceability_path,
        )

    def test_generates_dual_denominator_metrics(self):
        self.assertTrue(
            hasattr(review_summary, "generate_summary"),
            "review_summary应提供generate_summary函数",
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (
                validation_path,
                review_path,
                traceability_path,
            ) = self.create_valid_inputs(root)

            markdown_path = root / "review-summary.md"
            json_path = root / "review-summary.json"

            summary = review_summary.generate_summary(
                validation_path=validation_path,
                review_path=review_path,
                traceability_path=traceability_path,
                markdown_output=markdown_path,
                json_output=json_path,
            )

            human = summary["human_review"]
            automation = summary["automation"]
            execution = summary["execution"]

            self.assertEqual(24, summary["total_cases"])
            self.assertEqual(6, human["reviewed_count"])
            self.assertEqual(18, human["pending_count"])
            self.assertEqual(
                1.0,
                human["revised_rate_among_reviewed"],
            )
            self.assertEqual(
                0.25,
                human["revised_share_of_total"],
            )
            self.assertEqual(6, automation["selected_count"])
            self.assertEqual(6, automation["existing_count"])
            self.assertEqual(1.0, automation["reuse_rate"])
            self.assertEqual(
                0.25,
                automation["existing_share_of_total"],
            )
            self.assertEqual(6, execution["not_run_count"])
            self.assertEqual(0, execution["passed_count"])
            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())

            markdown = markdown_path.read_text(
                encoding="utf-8"
            )
            self.assertIn("已评审：6/24（25.00%）", markdown)
            self.assertIn("修改后采纳：6/6（100.00%）", markdown)
            self.assertIn("现有自动化复用：6/6（100.00%）", markdown)

    def test_rejects_selected_case_without_traceability(self):
        self.assertTrue(
            hasattr(review_summary, "generate_summary"),
            "review_summary应提供generate_summary函数",
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (
                validation_path,
                review_path,
                traceability_path,
            ) = self.create_valid_inputs(root)

            rows = []
            with traceability_path.open(
                encoding="utf-8-sig",
                newline="",
            ) as file:
                rows = list(csv.DictReader(file))

            self.write_csv(
                traceability_path,
                list(rows[0].keys()),
                rows[:-1],
            )

            with self.assertRaisesRegex(
                ValueError,
                "选中自动化但缺少追踪记录",
            ):
                review_summary.generate_summary(
                    validation_path=validation_path,
                    review_path=review_path,
                    traceability_path=traceability_path,
                    markdown_output=root / "summary.md",
                    json_output=root / "summary.json",
                )

    def test_rejects_unknown_review_status(self):
        self.assertTrue(
            hasattr(review_summary, "generate_summary"),
            "review_summary应提供generate_summary函数",
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (
                validation_path,
                review_path,
                traceability_path,
            ) = self.create_valid_inputs(root)

            with review_path.open(
                encoding="utf-8-sig",
                newline="",
            ) as file:
                reader = csv.DictReader(file)
                rows = list(reader)
                fieldnames = reader.fieldnames

            rows[0]["review_status"] = "approve"
            self.write_csv(
                review_path,
                fieldnames or [],
                rows,
            )

            with self.assertRaisesRegex(
                ValueError,
                "未知review_status",
            ):
                review_summary.generate_summary(
                    validation_path=validation_path,
                    review_path=review_path,
                    traceability_path=traceability_path,
                    markdown_output=root / "summary.md",
                    json_output=root / "summary.json",
                )


if __name__ == "__main__":
    unittest.main()
