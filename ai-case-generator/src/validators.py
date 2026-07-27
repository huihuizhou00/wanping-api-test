from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Set

from jsonschema import Draft202012Validator


@dataclass
class ValidationReport:
    global_errors: List[str] = field(default_factory=list)
    case_errors: MutableMapping[str, List[str]] = field(default_factory=dict)
    schema_case_errors: MutableMapping[str, List[str]] = field(default_factory=dict)

    def add_case_error(self, case_id: str, message: str, schema: bool = False) -> None:
        target = self.schema_case_errors if schema else self.case_errors
        target.setdefault(case_id, []).append(message)

    @property
    def valid(self) -> bool:
        return not self.global_errors and not self.case_errors and not self.schema_case_errors


def _case_id_at(batch: Mapping[str, Any], index: int) -> str:
    scenarios = batch.get("scenarios")
    if isinstance(scenarios, list) and 0 <= index < len(scenarios):
        item = scenarios[index]
        if isinstance(item, dict) and isinstance(item.get("case_id"), str):
            return item["case_id"]
    return f"<index:{index}>"


def validate_schema(batch: Dict[str, Any], schema: Dict[str, Any], report: ValidationReport) -> None:
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(batch), key=lambda item: list(item.absolute_path)):
        path = list(error.absolute_path)
        if len(path) >= 2 and path[0] == "scenarios" and isinstance(path[1], int):
            case_id = _case_id_at(batch, path[1])
            suffix = ".".join(str(part) for part in path[2:])
            location = f"字段{suffix}: " if suffix else ""
            report.add_case_error(case_id, location + error.message, schema=True)
        else:
            report.global_errors.append(f"Schema: {error.message}")


def _contains_text(assertions: Iterable[Mapping[str, Any]], *needles: str) -> bool:
    combined = " ".join(
        f"{item.get('key_pattern', '')} {item.get('table', '')} "
        f"{item.get('assertion', '')} {item.get('expected', '')}"
        for item in assertions
    ).lower()
    return all(needle.lower() in combined for needle in needles)


def _assertion_text(assertions: Iterable[Mapping[str, Any]]) -> str:
    return " ".join(
        f"{item.get('key_pattern', '')} {item.get('table', '')} "
        f"{item.get('assertion', '')} {item.get('expected', '')}"
        for item in assertions
    ).lower()


def _expresses_unchanged(assertions: Iterable[Mapping[str, Any]]) -> bool:
    text = _assertion_text(assertions)
    phrases = (
        "保持不变",
        "无变化",
        "不发生变化",
        "不再扣减",
        "不扣减",
        "不新增",
        "没有新增",
        "仍为",
        "等于原值",
    )
    return any(phrase in text for phrase in phrases)


def validate_business(
    batch: Dict[str, Any], rules: Dict[str, Any], quotas: Dict[str, int], report: ValidationReport
) -> None:
    scenarios = batch.get("scenarios")
    if not isinstance(scenarios, list):
        return

    endpoint_map = {
        (item["path"], item["method"]): item for item in rules.get("endpoints", [])
    }
    known_paths = {item["path"] for item in rules.get("endpoints", [])}
    known_rule_ids: Set[str] = {
        item["id"] for item in rules.get("business_rules", [])
    }
    mysql_tables = set(rules.get("mysql_tables", []))
    module_counts = {module: 0 for module in quotas}
    seen_ids: Set[str] = set()
    seckill_primary_rules = {
        "RULE-AUTH-UNAUTHORIZED",
        "RULE-PATH-LONG-INVALID",
        "RULE-SECKILL-STOCK-NOT-INITIALIZED",
        "RULE-SECKILL-SUCCESS",
        "RULE-SECKILL-DUPLICATE",
    }
    seckill_rule_counts = {rule_id: 0 for rule_id in seckill_primary_rules}

    for index, case in enumerate(scenarios):
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("case_id", f"<index:{index}>"))
        module = case.get("module")
        if module in module_counts:
            module_counts[module] += 1

        if case_id in seen_ids:
            report.add_case_error(case_id, "case_id重复")
        seen_ids.add(case_id)

        endpoint = case.get("endpoint")
        method = case.get("method")
        if endpoint not in known_paths:
            report.add_case_error(case_id, f"未知接口: {endpoint}")
            endpoint_rule = None
        else:
            endpoint_rule = endpoint_map.get((endpoint, method))
            if endpoint_rule is None:
                expected_methods = sorted(
                    item["method"] for item in rules.get("endpoints", []) if item["path"] == endpoint
                )
                report.add_case_error(
                    case_id, f"接口{endpoint}的方法应为{expected_methods}，实际为{method}"
                )

        source_rules = case.get("source_rules", [])
        for rule_id in source_rules:
            if rule_id not in known_rule_ids:
                report.add_case_error(case_id, f"引用未知规则: {rule_id}")

        if module == "seckill_plus":
            selected_primary_rules = seckill_primary_rules & set(source_rules)
            if len(selected_primary_rules) != 1:
                report.add_case_error(
                    case_id,
                    "秒杀Plus场景必须且只能引用一个主规则",
                )
            else:
                primary_rule = next(iter(selected_primary_rules))
                seckill_rule_counts[primary_rule] += 1
            if "RULE-SECKILL-NO-OVERSALE" in source_rules:
                report.add_case_error(
                    case_id,
                    "秒杀Plus模块不得引用并发防超卖规则",
                )

        if module == "concurrency_consistency":
            if source_rules != ["RULE-SECKILL-NO-OVERSALE"]:
                report.add_case_error(
                    case_id,
                    "并发一致性场景source_rules只能包含RULE-SECKILL-NO-OVERSALE",
                )

        request = case.get("request") or {}
        headers = request.get("headers") or {}
        auth_value = headers.get("authorization")
        http_status = case.get("expected_http_status")
        business = case.get("expected_business_result") or {}
        error_text = business.get("error_contains")

        if endpoint_rule:
            allowed_endpoint_modules = {
                "cache_async": {"shop_query", "shop_detail_voucher"},
                "concurrency_consistency": {"seckill_plus"},
            }.get(module, {module})
            if endpoint_rule.get("module") not in allowed_endpoint_modules:
                report.add_case_error(
                    case_id,
                    f"模块{module}不能使用接口{endpoint}",
                )

        if endpoint_rule and endpoint_rule.get("auth_required"):
            if auth_value in (None, "", "<MISSING>"):
                if http_status != 401:
                    report.add_case_error(case_id, "受保护接口未携带Token时预期HTTP状态必须为401")
                if business.get("success") is not False:
                    report.add_case_error(case_id, "未登录场景业务success必须为false")
            elif auth_value == "<VALID_TOKEN>" and http_status == 401:
                report.add_case_error(case_id, "有效Token场景不应预期401")
        elif endpoint_rule and http_status == 401:
            report.add_case_error(case_id, "公开接口不应预期401")

        if "RULE-LOGIN-INVALID-PHONE" in case.get("source_rules", []):
            if http_status != 200 or error_text is None or "手机号格式错误" not in error_text:
                report.add_case_error(case_id, "非法手机号场景必须HTTP 200且错误包含“手机号格式错误”")

        if "RULE-LOGIN-WRONG-CODE" in case.get("source_rules", []):
            if error_text is None or "验证码不一致，请重新输入" not in error_text:
                report.add_case_error(case_id, "错误验证码场景错误文案不正确")

        if "RULE-SHOP-NOT-FOUND" in case.get("source_rules", []):
            if http_status != 200 or error_text is None or "店铺不存在！" not in error_text:
                report.add_case_error(case_id, "不存在商铺场景必须HTTP 200且错误包含“店铺不存在！”")

        if "RULE-SHOP-TYPE-MISSING" in case.get("source_rules", []) and http_status != 400:
            report.add_case_error(case_id, "缺少typeId场景必须预期HTTP 400")

        if "RULE-PATH-LONG-INVALID" in case.get("source_rules", []) and http_status != 400:
            report.add_case_error(case_id, "非数字Long路径参数场景必须预期HTTP 400")

        if "RULE-VOUCHER-UNKNOWN-SHOP" in case.get("source_rules", []):
            if http_status != 200 or business.get("success") is not True:
                report.add_case_error(case_id, "不存在商铺优惠券场景必须HTTP 200且success=true")
            if not any("空" in assertion for assertion in business.get("data_assertions", [])):
                report.add_case_error(case_id, "不存在商铺优惠券场景必须断言空列表")

        if "RULE-SECKILL-STOCK-NOT-INITIALIZED" in case.get("source_rules", []):
            if error_text is None or "秒杀库存未初始化" not in error_text:
                report.add_case_error(case_id, "库存未初始化场景错误文案不正确")

        redis_assertions = case.get("redis_assertions") or []
        mysql_assertions = case.get("mysql_assertions") or []
        if "RULE-SECKILL-SUCCESS" in case.get("source_rules", []):
            if not redis_assertions or not mysql_assertions:
                report.add_case_error(case_id, "秒杀成功场景必须包含Redis和MySQL断言")
            if not _contains_text(redis_assertions, "stock") and not _contains_text(redis_assertions, "库存"):
                report.add_case_error(case_id, "秒杀成功场景缺少Redis库存断言")
            if not _contains_text(mysql_assertions, "tb_voucher_order"):
                report.add_case_error(case_id, "秒杀成功场景缺少订单表断言")

        if "RULE-SECKILL-DUPLICATE" in case.get("source_rules", []):
            if error_text is None or "不能重复下单" not in error_text:
                report.add_case_error(case_id, "重复秒杀场景错误文案不正确")

            redis_stock_assertions = [
                item
                for item in redis_assertions
                if "stock" in _assertion_text([item])
                or "库存" in _assertion_text([item])
            ]
            mysql_stock_assertions = [
                item
                for item in mysql_assertions
                if item.get("table") == "tb_seckill_voucher"
                and (
                    "stock" in _assertion_text([item])
                    or "库存" in _assertion_text([item])
                )
            ]
            order_assertions = [
                item
                for item in mysql_assertions
                if item.get("table") == "tb_voucher_order"
            ]

            if not redis_stock_assertions or not _expresses_unchanged(redis_stock_assertions):
                report.add_case_error(case_id, "重复秒杀场景缺少Redis库存保持不变断言")
            if not mysql_stock_assertions or not _expresses_unchanged(mysql_stock_assertions):
                report.add_case_error(case_id, "重复秒杀场景缺少MySQL库存保持不变断言")
            if not order_assertions or not _expresses_unchanged(order_assertions):
                report.add_case_error(case_id, "重复秒杀场景缺少订单数保持不变断言")

        if module == "concurrency_consistency" or "RULE-SECKILL-NO-OVERSALE" in case.get("source_rules", []):
            all_assertions = redis_assertions + mysql_assertions
            if case.get("test_type") not in {"concurrency", "consistency"}:
                report.add_case_error(case_id, "并发一致性模块test_type必须为concurrency或consistency")
            if not _contains_text(all_assertions, "5"):
                report.add_case_error(case_id, "并发防超卖场景必须包含库存或订单边界5")
            combined = " ".join(str(item) for item in all_assertions)
            if "负" not in combined and ">= 0" not in combined and "不小于0" not in combined:
                report.add_case_error(case_id, "并发防超卖场景必须包含非负库存断言")
            if "订单" not in combined or ("不超过" not in combined and "<= 5" not in combined and "等于5" not in combined):
                report.add_case_error(case_id, "并发防超卖场景必须包含订单数不超过库存断言")

        for assertion in mysql_assertions:
            table = assertion.get("table")
            if table not in mysql_tables:
                report.add_case_error(case_id, f"引用未知MySQL表: {table}")

    if "seckill_plus" in quotas:
        for rule_id, count in sorted(seckill_rule_counts.items()):
            if count != 1:
                report.global_errors.append(
                    f"秒杀Plus主规则{rule_id}要求恰好覆盖1次，实际{count}次"
                )

    for module, expected in quotas.items():
        actual = module_counts.get(module, 0)
        if actual != expected:
            report.global_errors.append(f"模块{module}要求{expected}条，实际{actual}条")
