from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from src.rule_repairs import (
    apply_known_rule_repairs,
)
from src.generate_cases import (
    determine_repair_fields,
    ensure_single_scenario_batch,
    repair_invalid_scenarios,
    validate_single_scenario,
)
from src.settings import load_yaml


ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return copy.deepcopy(self._responses.pop(0))


class TargetedRepairTest(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(
            (ROOT / "schemas/test-case-batch.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.rules = load_yaml(ROOT / "config/api_rules.yaml")

    @staticmethod
    def unauthenticated_case():
        return {
            "case_id": "AI-SECKILL-001",
            "module": "seckill_plus",
            "title": "未登录秒杀请求被拦截",
            "priority": "P0",
            "test_type": "security",
            "endpoint": "/voucher-order/seckill-plus/{voucherId}",
            "method": "POST",
            "preconditions": [],
            "request": {
                "path_params": {"voucherId": 12},
                "query_params": {},
                "headers": {},
                "body": None,
            },
            "expected_http_status": 401,
            "expected_business_result": {
                "success": False,
                "error_contains": None,
                "data_assertions": [],
            },
            "redis_assertions": [],
            "mysql_assertions": [],
            "risk_tags": ["unauthorized"],
            "source_rules": ["RULE-AUTH-UNAUTHORIZED"],
        }

    @staticmethod
    def duplicate_case(include_redis=False):
        redis_assertions = []
        if include_redis:
            redis_assertions = [
                {
                    "key_pattern": "seckill:stock:{voucherId}",
                    "assertion": "Redis库存保持不变",
                    "expected": "与请求前一致",
                }
            ]

        return {
            "case_id": "AI-SECKILL-005",
            "module": "seckill_plus",
            "title": "重复下单不产生额外副作用",
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
            "redis_assertions": redis_assertions,
            "mysql_assertions": [
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
            ],
            "risk_tags": ["duplicate-order"],
            "source_rules": ["RULE-SECKILL-DUPLICATE"],
        }

    @staticmethod
    def stock_not_initialized_case(correct_error=False):
        error_contains = (
            "秒杀库存未初始化"
            if correct_error
            else "库存不存在"
        )
        return {
            "case_id": "AI-SECKILL-003",
            "module": "seckill_plus",
            "title": "Redis库存未初始化时拒绝下单",
            "priority": "P0",
            "test_type": "negative",
            "endpoint": "/voucher-order/seckill-plus/{voucherId}",
            "method": "POST",
            "preconditions": ["Redis库存Key不存在"],
            "request": {
                "path_params": {"voucherId": 12},
                "query_params": {},
                "headers": {"authorization": "<VALID_TOKEN>"},
                "body": None,
            },
            "expected_http_status": 200,
            "expected_business_result": {
                "success": False,
                "error_contains": error_contains,
                "data_assertions": [],
            },
            "redis_assertions": [],
            "mysql_assertions": [],
            "risk_tags": ["stock-not-initialized"],
            "source_rules": ["RULE-SECKILL-STOCK-NOT-INITIALIZED"],
        }

    @staticmethod
    def concurrency_case():
        return {
            "case_id": "AI-CONCURRENCY-001",
            "module": "concurrency_consistency",
            "title": "20用户并发抢购库存5不超卖",
            "priority": "P0",
            "test_type": "concurrency",
            "endpoint": "/voucher-order/seckill-plus/{voucherId}",
            "method": "POST",
            "preconditions": ["券13 Redis和MySQL库存均为5", "20个用户Token有效"],
            "request": {
                "path_params": {"voucherId": 13},
                "query_params": {},
                "headers": {"authorization": "<VALID_TOKEN>"},
                "body": None,
            },
            "expected_http_status": 200,
            "expected_business_result": {
                "success": True,
                "error_contains": None,
                "data_assertions": ["成功5个", "失败15个"],
            },
            "redis_assertions": [
                {
                    "key_pattern": "seckill:stock:{voucherId}",
                    "assertion": "最终库存等于0",
                    "expected": 0,
                }
            ],
            "mysql_assertions": [
                {
                    "table": "tb_voucher_order",
                    "assertion": "订单数等于成功数",
                    "expected": 5,
                },
                {
                    "table": "tb_seckill_voucher",
                    "assertion": "最终库存等于0",
                    "expected": 0,
                },
            ],
            "risk_tags": ["oversell", "eventual-consistency"],
            "source_rules": ["RULE-SECKILL-NO-OVERSALE"],
        }

    def test_single_scenario_validation_reports_only_the_failed_case(self):
        errors = validate_single_scenario(
            self.duplicate_case(include_redis=False),
            self.schema,
            self.rules,
        )

        self.assertEqual(
            [
                "业务[AI-SECKILL-005]: "
                "重复秒杀场景缺少Redis库存保持不变断言"
            ],
            errors,
        )

    def test_repair_keeps_valid_scenario_and_replaces_only_failed_case(self):
        valid_case = self.unauthenticated_case()
        invalid_case = self.stock_not_initialized_case(correct_error=False)
        repaired_case = self.stock_not_initialized_case(correct_error=True)
        client = FakeClient([{"scenarios": [repaired_case]}])

        with tempfile.TemporaryDirectory() as directory:
            result, repair_events, normalization_events = (
                repair_invalid_scenarios(
                    batch={"scenarios": [valid_case, invalid_case]},
                    module="seckill_plus",
                    module_name="秒杀Plus",
                    case_id_prefix="AI-SECKILL",
                    schema=self.schema,
                    rules=self.rules,
                    client=client,
                    prompt_template=ROOT / "prompts/generate_cases.txt",
                    raw_dir=Path(directory),
                    max_retries=2,
                )
            )

        self.assertEqual(valid_case, result["scenarios"][0])
        self.assertEqual(repaired_case, result["scenarios"][1])
        self.assertEqual(1, len(client.prompts))
        self.assertEqual("AI-SECKILL-003", repair_events[0]["case_id"])
        self.assertEqual("llm", repair_events[0]["actor"])
        self.assertEqual("accepted", repair_events[0]["status"])
        self.assertEqual([], normalization_events)

    def test_failed_targeted_repair_persists_audit_record(self):
        invalid_case = self.stock_not_initialized_case(correct_error=False)
        client = FakeClient([{"scenarios": [invalid_case]}])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            audit_path = root / "seckill_plus-repair-events.json"

            with self.assertRaises(RuntimeError):
                repair_invalid_scenarios(
                    batch={"scenarios": [invalid_case]},
                    module="seckill_plus",
                    module_name="秒杀Plus",
                    case_id_prefix="AI-SECKILL",
                    schema=self.schema,
                    rules=self.rules,
                    client=client,
                    prompt_template=ROOT / "prompts/generate_cases.txt",
                    raw_dir=raw_dir,
                    max_retries=0,
                    audit_path=audit_path,
                )

            events = json.loads(audit_path.read_text(encoding="utf-8"))

        self.assertEqual(1, len(events))
        self.assertEqual("rejected", events[0]["status"])
        self.assertEqual("llm", events[0]["actor"])
        self.assertEqual("AI-SECKILL-003", events[0]["case_id"])

    def test_repair_batch_must_keep_case_id_and_module(self):
        errors = ensure_single_scenario_batch(
            {
                "scenarios": [
                    {
                        "case_id": "AI-SECKILL-004",
                        "module": "seckill_plus",
                    }
                ]
            },
            expected_case_id="AI-SECKILL-005",
            expected_module="seckill_plus",
        )

        self.assertIn(
            "修复场景case_id必须保持为AI-SECKILL-005",
            errors,
        )

    def test_repair_only_applies_fields_related_to_original_errors(self):
        original_case = self.stock_not_initialized_case(correct_error=False)

        # 模型修正错误文案，但同时破坏了原本正确的请求和数据层字段。
        regressed_candidate = self.stock_not_initialized_case(correct_error=True)
        regressed_candidate["request"]["headers"] = {}
        regressed_candidate["mysql_assertions"] = [
            {
                "table": "tb_voucher_order",
                "assertion": "不应被应用",
                "expected": 99,
            }
        ]

        client = FakeClient([{"scenarios": [regressed_candidate]}])

        with tempfile.TemporaryDirectory() as directory:
            result, repair_events, _ = repair_invalid_scenarios(
                batch={"scenarios": [original_case]},
                module="seckill_plus",
                module_name="秒杀Plus",
                case_id_prefix="AI-SECKILL",
                schema=self.schema,
                rules=self.rules,
                client=client,
                prompt_template=ROOT / "prompts/generate_cases.txt",
                raw_dir=Path(directory),
                max_retries=0,
            )

        repaired = result["scenarios"][0]

        self.assertEqual(
            "秒杀库存未初始化",
            repaired["expected_business_result"]["error_contains"],
        )
        self.assertEqual(
            original_case["request"],
            repaired["request"],
        )
        self.assertEqual(
            original_case["mysql_assertions"],
            repaired["mysql_assertions"],
        )
        self.assertEqual("llm", repair_events[0]["actor"])
        self.assertEqual("accepted", repair_events[0]["status"])

    def test_rule_engine_repairs_duplicate_side_effects(
        self,
    ):
        scenario = self.duplicate_case(
            include_redis=False
        )

        scenario[
            "expected_business_result"
        ]["error_contains"] = "库存不足"

        scenario["mysql_assertions"] = []

        errors = [
            (
                "业务[AI-SECKILL-005]: "
                "重复秒杀场景错误文案不正确"
            ),
            (
                "业务[AI-SECKILL-005]: "
                "重复秒杀场景缺少Redis库存保持不变断言"
            ),
            (
                "业务[AI-SECKILL-005]: "
                "重复秒杀场景缺少MySQL库存保持不变断言"
            ),
            (
                "业务[AI-SECKILL-005]: "
                "重复秒杀场景缺少订单数保持不变断言"
            ),
        ]

        repaired, events = (
            apply_known_rule_repairs(
                scenario,
                errors,
            )
        )

        self.assertEqual(
            "不能重复下单",
            repaired[
                "expected_business_result"
            ]["error_contains"],
        )

        self.assertEqual(
            "库存保持不变",
            repaired[
                "redis_assertions"
            ][0]["assertion"],
        )

        self.assertEqual(
            2,
            len(repaired["mysql_assertions"]),
        )

        validation_errors = (
            validate_single_scenario(
                repaired,
                self.schema,
                self.rules,
            )
        )

        self.assertEqual(
            [],
            validation_errors,
        )

        self.assertTrue(events)

    def test_known_duplicate_rule_is_repaired_without_llm_call(self):
        scenario = self.duplicate_case(include_redis=False)
        scenario["expected_business_result"]["error_contains"] = "库存不足"
        scenario["mysql_assertions"] = []
        client = FakeClient([])

        with tempfile.TemporaryDirectory() as directory:
            result, repair_events, normalization_events = (
                repair_invalid_scenarios(
                    batch={"scenarios": [scenario]},
                    module="seckill_plus",
                    module_name="秒杀Plus",
                    case_id_prefix="AI-SECKILL",
                    schema=self.schema,
                    rules=self.rules,
                    client=client,
                    prompt_template=ROOT / "prompts/generate_cases.txt",
                    raw_dir=Path(directory),
                    max_retries=2,
                )
            )

        repaired = result["scenarios"][0]
        self.assertEqual([], client.prompts)
        self.assertEqual([], normalization_events)
        self.assertEqual([], validate_single_scenario(repaired, self.schema, self.rules))
        self.assertEqual("rule_engine", repair_events[0]["actor"])
        self.assertEqual("accepted", repair_events[0]["status"])
        self.assertEqual(0, repair_events[0]["repair_attempt"])

    def test_rule_engine_repairs_concurrency_safety_assertions(self):
        scenario = self.concurrency_case()
        errors = validate_single_scenario(
            scenario,
            self.schema,
            self.rules,
        )

        self.assertEqual(
            [
                "业务[AI-CONCURRENCY-001]: "
                "并发防超卖场景必须包含非负库存断言",
                "业务[AI-CONCURRENCY-001]: "
                "并发防超卖场景必须包含订单数不超过库存断言",
            ],
            errors,
        )

        repaired, changes = apply_known_rule_repairs(
            scenario,
            errors,
        )

        self.assertEqual(
            [],
            validate_single_scenario(
                repaired,
                self.schema,
                self.rules,
            ),
        )
        self.assertTrue(changes)

    def test_known_concurrency_rule_is_repaired_without_llm_call(self):
        scenario = self.concurrency_case()
        client = FakeClient([])

        with tempfile.TemporaryDirectory() as directory:
            result, repair_events, normalization_events = (
                repair_invalid_scenarios(
                    batch={"scenarios": [scenario]},
                    module="concurrency_consistency",
                    module_name="并发一致性",
                    case_id_prefix="AI-CONCURRENCY",
                    schema=self.schema,
                    rules=self.rules,
                    client=client,
                    prompt_template=ROOT / "prompts/generate_cases.txt",
                    raw_dir=Path(directory),
                    max_retries=2,
                )
            )

        repaired = result["scenarios"][0]
        self.assertEqual([], client.prompts)
        self.assertEqual([], normalization_events)
        self.assertEqual(
            [],
            validate_single_scenario(
                repaired,
                self.schema,
                self.rules,
            ),
        )
        self.assertEqual("rule_engine", repair_events[0]["actor"])
        self.assertEqual("accepted", repair_events[0]["status"])
        self.assertEqual(0, repair_events[0]["repair_attempt"])

    def test_concurrency_errors_have_safe_llm_repair_fields(self):
        fields = determine_repair_fields(
            [
                "业务[AI-CONCURRENCY-001]: "
                "并发防超卖场景必须包含非负库存断言",
                "业务[AI-CONCURRENCY-001]: "
                "并发防超卖场景必须包含订单数不超过库存断言",
            ]
        )

        self.assertEqual(
            {"redis_assertions", "mysql_assertions"},
            set(fields),
        )



if __name__ == "__main__":
    unittest.main()
