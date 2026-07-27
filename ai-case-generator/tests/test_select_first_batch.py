from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import select_first_batch


REVIEW_FIELDS = [
    "case_id",
    "module",
    "title",
    "priority",
    "test_type",
    "endpoint",
    "method",
    "source_rules",
    "review_status",
    "review_comment",
    "executable",
    "automation_priority",
    "test_data_ready",
    "redis_assertion_ready",
    "mysql_assertion_ready",
    "selected_for_automation",
]


class SelectFirstBatchReviewStatusTest(unittest.TestCase):
    def test_selected_cases_are_marked_revised(self):
        with tempfile.TemporaryDirectory() as directory:
            review_path = (
                Path(directory) / "human-review.csv"
            )

            with review_path.open(
                "w",
                encoding="utf-8-sig",
                newline="",
            ) as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=REVIEW_FIELDS,
                )
                writer.writeheader()

                for case_id in select_first_batch.PLAN:
                    writer.writerow(
                        {"case_id": case_id}
                    )

            with patch.object(
                select_first_batch,
                "REVIEW_PATH",
                review_path,
            ):
                select_first_batch.update_review_csv()

            with review_path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as file:
                rows = list(csv.DictReader(file))

        actual_statuses = {
            row["case_id"]: row["review_status"]
            for row in rows
        }

        expected_statuses = {
            case_id: "revised"
            for case_id in select_first_batch.PLAN
        }

        self.assertEqual(
            expected_statuses,
            actual_statuses,
        )


if __name__ == "__main__":
    unittest.main()
