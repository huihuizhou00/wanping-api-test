from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.settings import load_yaml
from src.validators import ValidationReport, validate_business, validate_schema


ROOT = Path(__file__).resolve().parents[1]


class ValidatorTest(unittest.TestCase):
    def load_json(self, relative: str):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_schema_accepts_valid_fixture(self):
        batch = self.load_json("tests/fixtures/valid_batch.json")
        schema = self.load_json("schemas/test-case-batch.schema.json")
        report = ValidationReport()
        validate_schema(batch, schema, report)
        self.assertEqual({}, report.schema_case_errors)
        self.assertEqual([], report.global_errors)

    def test_business_rejects_unknown_endpoint_and_rule(self):
        batch = self.load_json("tests/fixtures/invalid_batch.json")
        rules = load_yaml(ROOT / "config/api_rules.yaml")
        report = ValidationReport()
        validate_business(batch, rules, {"login_auth": 1}, report)
        errors = " ".join(report.case_errors["AI-BAD-001"])
        self.assertIn("未知接口", errors)
        self.assertIn("未知规则", errors)

    def test_business_rejects_duplicate_case_id(self):
        batch = self.load_json("tests/fixtures/valid_batch.json")
        batch["scenarios"][1]["case_id"] = batch["scenarios"][0]["case_id"]
        rules = load_yaml(ROOT / "config/api_rules.yaml")
        report = ValidationReport()
        validate_business(
            batch,
            rules,
            {"login_auth": 1, "concurrency_consistency": 1},
            report,
        )
        self.assertTrue(
            any("case_id重复" in message for message in report.case_errors["AI-LOGIN-001"])
        )

    def test_concurrency_requires_non_negative_and_order_boundary(self):
        batch = self.load_json("tests/fixtures/valid_batch.json")
        case = batch["scenarios"][1]
        case["redis_assertions"] = []
        case["mysql_assertions"] = []
        rules = load_yaml(ROOT / "config/api_rules.yaml")
        report = ValidationReport()
        validate_business(
            batch,
            rules,
            {"login_auth": 1, "concurrency_consistency": 1},
            report,
        )
        errors = " ".join(report.case_errors["AI-CONCURRENCY-001"])
        self.assertIn("非负库存", errors)
        self.assertIn("订单数不超过库存", errors)


if __name__ == "__main__":
    unittest.main()
