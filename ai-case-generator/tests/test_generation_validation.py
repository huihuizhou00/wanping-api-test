from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.generate_cases import validate_module_candidate
from src.prompting import select_module_rules
from src.settings import load_yaml


ROOT = Path(__file__).resolve().parents[1]


class GenerationValidationTest(unittest.TestCase):
    def load_json(self, relative: str):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_valid_module_candidate_is_accepted(self):
        full_batch = self.load_json("tests/fixtures/valid_batch.json")
        login_case = full_batch["scenarios"][0]
        batch = {"scenarios": [login_case]}
        schema = self.load_json("schemas/test-case-batch.schema.json")
        rules = load_yaml(ROOT / "config/api_rules.yaml")

        errors = validate_module_candidate(
            batch,
            "login_auth",
            1,
            schema,
            rules,
        )

        self.assertEqual([], errors)

    def test_schema_errors_are_returned_before_business_errors(self):
        batch = {
            "scenarios": [
                {
                    "case_id": "AI-LOGIN-001",
                    "module": "login_auth",
                }
            ]
        }
        schema = self.load_json("schemas/test-case-batch.schema.json")
        rules = load_yaml(ROOT / "config/api_rules.yaml")

        errors = validate_module_candidate(
            batch,
            "login_auth",
            1,
            schema,
            rules,
        )

        combined = " ".join(errors)
        self.assertIn("Schema[AI-LOGIN-001]", combined)
        self.assertIn("endpoint", combined)
        self.assertNotIn("未知接口", combined)

    def test_selected_seckill_rules_include_endpoint_referenced_auth_rule(self):
        rules = load_yaml(ROOT / "config/api_rules.yaml")

        selected = select_module_rules(rules, "seckill_plus")
        rule_ids = {
            item["id"]
            for item in selected["business_rules"]
        }

        self.assertIn("RULE-AUTH-UNAUTHORIZED", rule_ids)
        self.assertIn("RULE-PATH-LONG-INVALID", rule_ids)
        self.assertIn("RULE-SECKILL-SUCCESS", rule_ids)


class StructuralNormalizationTest(unittest.TestCase):
    def test_missing_request_body_is_filled_with_null(self):
        from src.normalizers import normalize_structural_defaults

        batch = {
            "scenarios": [
                {
                    "case_id": "AI-LOGIN-004",
                    "request": {
                        "path_params": {},
                        "query_params": {},
                        "headers": {},
                    },
                }
            ]
        }

        normalized, changes = normalize_structural_defaults(batch)

        self.assertIsNone(normalized["scenarios"][0]["request"]["body"])
        self.assertEqual(
            [
                {
                    "case_id": "AI-LOGIN-004",
                    "path": "request.body",
                    "action": "filled_default",
                    "value": None,
                }
            ],
            changes,
        )

    def test_existing_request_body_is_preserved(self):
        from src.normalizers import normalize_structural_defaults

        body = {"phone": "18800000000"}
        batch = {
            "scenarios": [
                {
                    "case_id": "AI-LOGIN-001",
                    "request": {
                        "path_params": {},
                        "query_params": {},
                        "headers": {},
                        "body": body,
                    },
                }
            ]
        }

        normalized, changes = normalize_structural_defaults(batch)

        self.assertEqual(body, normalized["scenarios"][0]["request"]["body"])
        self.assertEqual([], changes)

    def test_semantic_fields_are_not_invented(self):
        from src.normalizers import normalize_structural_defaults

        batch = {
            "scenarios": [
                {
                    "case_id": "AI-LOGIN-004",
                    "request": {},
                }
            ]
        }

        normalized, changes = normalize_structural_defaults(batch)

        scenario = normalized["scenarios"][0]
        self.assertNotIn("endpoint", scenario)
        self.assertNotIn("method", scenario)
        self.assertNotIn("expected_http_status", scenario)
        self.assertEqual({"body": None}, scenario["request"])
        self.assertEqual(1, len(changes))

class CandidatePreparationTest(unittest.TestCase):
    def load_json(self, relative: str):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_missing_request_body_is_normalized_before_validation(self):
        from src.generate_cases import prepare_module_candidate

        full_batch = self.load_json("tests/fixtures/valid_batch.json")
        login_case = full_batch["scenarios"][0]
        login_case["request"].pop("body")
        batch = {"scenarios": [login_case]}
        schema = self.load_json("schemas/test-case-batch.schema.json")
        rules = load_yaml(ROOT / "config/api_rules.yaml")

        normalized, changes, errors = prepare_module_candidate(
            batch,
            "login_auth",
            1,
            schema,
            rules,
        )

        self.assertEqual([], errors)
        self.assertIsNone(normalized["scenarios"][0]["request"]["body"])
        self.assertEqual("request.body", changes[0]["path"])


if __name__ == "__main__":
    unittest.main()


class ModuleRuleScopeTest(unittest.TestCase):
    def test_seckill_rules_exclude_concurrency_rule(self):
        rules = load_yaml(ROOT / "config/api_rules.yaml")

        selected = select_module_rules(rules, "seckill_plus")
        rule_ids = {item["id"] for item in selected["business_rules"]}

        self.assertEqual(
            {
                "RULE-AUTH-UNAUTHORIZED",
                "RULE-PATH-LONG-INVALID",
                "RULE-SECKILL-STOCK-NOT-INITIALIZED",
                "RULE-SECKILL-SUCCESS",
                "RULE-SECKILL-DUPLICATE",
            },
            rule_ids,
        )
        self.assertNotIn("RULE-SECKILL-NO-OVERSALE", rule_ids)

    def test_seckill_endpoint_rule_list_excludes_concurrency_rule(self):
        rules = load_yaml(ROOT / "config/api_rules.yaml")

        selected = select_module_rules(rules, "seckill_plus")
        endpoint_rule_ids = {
            rule_id
            for endpoint in selected["endpoint_rules"]
            for rule_id in endpoint.get("rules", [])
        }

        self.assertNotIn(
            "RULE-SECKILL-NO-OVERSALE",
            endpoint_rule_ids,
        )
        self.assertIn(
            "RULE-SECKILL-NO-OVERSALE",
            selected["generation_constraints"]["forbidden_rules"],
        )

    def test_non_auth_seckill_cases_require_valid_token(self):
        rules = load_yaml(ROOT / "config/api_rules.yaml")

        selected = select_module_rules(rules, "seckill_plus")
        constraints = selected["generation_constraints"]
        plan_by_id = {
            item["case_id"]: item
            for item in constraints["required_case_plan"]
        }

        self.assertEqual(
            "<VALID_TOKEN>",
            plan_by_id["AI-SECKILL-002"]["authorization"],
        )
        self.assertEqual(
            400,
            plan_by_id["AI-SECKILL-002"]["expected_http_status"],
        )
        self.assertIn(
            "除AI-SECKILL-001外",
            constraints["auth_policy"],
        )

    def test_concurrency_rules_only_include_no_oversale(self):
        rules = load_yaml(ROOT / "config/api_rules.yaml")

        selected = select_module_rules(rules, "concurrency_consistency")
        rule_ids = {item["id"] for item in selected["business_rules"]}

        self.assertEqual({"RULE-SECKILL-NO-OVERSALE"}, rule_ids)

    def test_generation_quota_remains_twenty_four(self):
        generator = load_yaml(ROOT / "config/generator.yaml")

        quotas = generator["module_quotas"]

        self.assertEqual(24, sum(quotas.values()))
        self.assertEqual(5, quotas["seckill_plus"])
        self.assertEqual(5, quotas["shop_query"])
        self.assertEqual(5, quotas["shop_detail_voucher"])


class DuplicateSideEffectValidationTest(unittest.TestCase):
    def load_json(self, relative: str):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def duplicate_case(self):
        return {
            "case_id": "AI-SECKILL-005",
            "module": "seckill_plus",
            "title": "同一用户重复秒杀无副作用",
            "priority": "P0",
            "test_type": "negative",
            "endpoint": "/voucher-order/seckill-plus/{voucherId}",
            "method": "POST",
            "preconditions": ["用户已成功购买券12"],
            "request": {
                "path_params": {"voucherId": 12},
                "query_params": {},
                "headers": {"authorization": "<VALID_TOKEN>"},
                "body": None,
            },
            "expected_http_status": 200,
            "expected_business_result": {
                "success": False,
                "error_contains": "不能重复下单",
                "data_assertions": [],
            },
            "redis_assertions": [],
            "mysql_assertions": [],
            "risk_tags": ["duplicate-order"],
            "source_rules": ["RULE-SECKILL-DUPLICATE"],
        }

    def validate(self, case):
        from src.validators import ValidationReport, validate_business

        rules = load_yaml(ROOT / "config/api_rules.yaml")
        report = ValidationReport()
        validate_business(
            {"scenarios": [case]},
            rules,
            {"seckill_plus": 1},
            report,
        )
        return report

    def test_duplicate_requires_three_explicit_no_side_effect_assertions(self):
        report = self.validate(self.duplicate_case())

        errors = " ".join(report.case_errors["AI-SECKILL-005"])
        self.assertIn("Redis库存保持不变", errors)
        self.assertIn("MySQL库存保持不变", errors)
        self.assertIn("订单数保持不变", errors)


    def test_duplicate_accepts_all_three_no_side_effect_assertions(self):
        case = self.duplicate_case()
        case["redis_assertions"] = [
            {
                "key_pattern": "seckill:stock:{voucherId}",
                "assertion": "Redis库存保持不变",
                "expected": "与请求前一致",
            }
        ]
        case["mysql_assertions"] = [
            {
                "table": "tb_seckill_voucher",
                "assertion": "MySQL库存保持不变",
                "expected": "与请求前一致",
            },
            {
                "table": "tb_voucher_order",
                "assertion": "订单数保持不变且不新增订单",
                "expected": 1,
            },
        ]

        def test_rejected_candidate_is_not_used_as_next_repair_baseline(
            self,
        ):
            original_case = self.duplicate_case(
                include_redis=False
            )

            bad_candidate = self.duplicate_case(
                include_redis=False
            )
            bad_candidate[
                "expected_business_result"
            ]["error_contains"] = "错误文案"

            good_candidate = self.duplicate_case(
                include_redis=True
            )

            client = FakeClient(
                [
                    {
                        "scenarios": [
                            bad_candidate
                        ]
                    },
                    {
                        "scenarios": [
                            good_candidate
                        ]
                    },
                ]
            )

            with tempfile.TemporaryDirectory() as directory:
                result, _, _ = (
                    repair_invalid_scenarios(
                        batch={
                            "scenarios": [
                                original_case
                            ]
                        },
                        module="seckill_plus",
                        module_name="秒杀Plus",
                        case_id_prefix="AI-SECKILL",
                        schema=self.schema,
                        rules=self.rules,
                        client=client,
                        prompt_template=(
                            ROOT
                            / "prompts"
                            / "generate_cases.txt"
                        ),
                        raw_dir=Path(directory),
                        max_retries=1,
                    )
                )

            repaired = result["scenarios"][0]

            self.assertEqual(
                "不能重复下单",
                repaired[
                    "expected_business_result"
                ]["error_contains"],
            )
            self.assertTrue(
                repaired["redis_assertions"]
            )

            # 第二次Prompt仍应包含最初正确的错误文案。
            self.assertIn(
                '"error_contains": "不能重复下单"',
                client.prompts[1],
            )

        report = self.validate(case)

        self.assertNotIn("AI-SECKILL-005", report.case_errors)
