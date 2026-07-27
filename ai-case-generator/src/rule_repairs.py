from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Mapping, Tuple


DUPLICATE_RULE_ID = "RULE-SECKILL-DUPLICATE"
NO_OVERSALE_RULE_ID = "RULE-SECKILL-NO-OVERSALE"


def _has_error(errors: Iterable[str], message: str) -> bool:
    return any(message in error for error in errors)


def _contains_assertion(
    assertions: Iterable[Mapping[str, Any]],
    identity_field: str,
    identity_value: str,
    required_text: str,
) -> bool:
    for item in assertions:
        if item.get(identity_field) != identity_value:
            continue
        text = f"{item.get('assertion', '')} {item.get('expected', '')}"
        if required_text in text:
            return True
    return False


def _append_if_missing(
    assertions: List[Dict[str, Any]],
    identity_field: str,
    identity_value: str,
    required_text: str,
    canonical_assertion: Dict[str, Any],
) -> bool:
    if _contains_assertion(
        assertions,
        identity_field,
        identity_value,
        required_text,
    ):
        return False

    assertions.append(copy.deepcopy(canonical_assertion))
    return True


def _repair_duplicate_rule(
    repaired: Dict[str, Any],
    errors: List[str],
    changes: List[Dict[str, Any]],
) -> None:
    if _has_error(errors, "重复秒杀场景错误文案不正确"):
        business_result = repaired.setdefault("expected_business_result", {})
        old_value = business_result.get("error_contains")
        new_value = "不能重复下单"
        if old_value != new_value:
            business_result["error_contains"] = new_value
            changes.append(
                {
                    "field": "expected_business_result.error_contains",
                    "action": "set_canonical_value",
                    "before": old_value,
                    "after": new_value,
                }
            )

    if _has_error(errors, "重复秒杀场景缺少Redis库存保持不变断言"):
        redis_assertions = list(repaired.get("redis_assertions") or [])
        appended = _append_if_missing(
            redis_assertions,
            "key_pattern",
            "seckill:stock:{voucherId}",
            "保持不变",
            {
                "key_pattern": "seckill:stock:{voucherId}",
                "assertion": "库存保持不变",
                "expected": "与请求前一致",
            },
        )
        repaired["redis_assertions"] = redis_assertions
        if appended:
            changes.append(
                {
                    "field": "redis_assertions",
                    "action": "append_canonical_assertion",
                    "target": "seckill:stock:{voucherId}",
                }
            )

    if _has_error(errors, "重复秒杀场景缺少MySQL库存保持不变断言"):
        mysql_assertions = list(repaired.get("mysql_assertions") or [])
        appended = _append_if_missing(
            mysql_assertions,
            "table",
            "tb_seckill_voucher",
            "保持不变",
            {
                "table": "tb_seckill_voucher",
                "assertion": "库存保持不变",
                "expected": "与请求前一致",
            },
        )
        repaired["mysql_assertions"] = mysql_assertions
        if appended:
            changes.append(
                {
                    "field": "mysql_assertions",
                    "action": "append_canonical_assertion",
                    "target": "tb_seckill_voucher",
                }
            )

    if _has_error(errors, "重复秒杀场景缺少订单数保持不变断言"):
        mysql_assertions = list(repaired.get("mysql_assertions") or [])
        appended = _append_if_missing(
            mysql_assertions,
            "table",
            "tb_voucher_order",
            "保持不变",
            {
                "table": "tb_voucher_order",
                "assertion": "订单数保持不变且不新增订单",
                "expected": "与请求前一致",
            },
        )
        repaired["mysql_assertions"] = mysql_assertions
        if appended:
            changes.append(
                {
                    "field": "mysql_assertions",
                    "action": "append_canonical_assertion",
                    "target": "tb_voucher_order",
                }
            )


def _repair_no_oversale_rule(
    repaired: Dict[str, Any],
    errors: List[str],
    changes: List[Dict[str, Any]],
) -> None:
    if _has_error(errors, "并发防超卖场景必须包含非负库存断言"):
        redis_assertions = list(repaired.get("redis_assertions") or [])
        redis_appended = _append_if_missing(
            redis_assertions,
            "key_pattern",
            "seckill:stock:{voucherId}",
            "不为负",
            {
                "key_pattern": "seckill:stock:{voucherId}",
                "assertion": "最终库存等于0且不为负",
                "expected": 0,
            },
        )
        repaired["redis_assertions"] = redis_assertions
        if redis_appended:
            changes.append(
                {
                    "field": "redis_assertions",
                    "action": "append_canonical_assertion",
                    "target": "seckill:stock:{voucherId}",
                }
            )

        mysql_assertions = list(repaired.get("mysql_assertions") or [])
        mysql_appended = _append_if_missing(
            mysql_assertions,
            "table",
            "tb_seckill_voucher",
            "不为负",
            {
                "table": "tb_seckill_voucher",
                "assertion": "最终库存等于0且不为负",
                "expected": 0,
            },
        )
        repaired["mysql_assertions"] = mysql_assertions
        if mysql_appended:
            changes.append(
                {
                    "field": "mysql_assertions",
                    "action": "append_canonical_assertion",
                    "target": "tb_seckill_voucher",
                }
            )

    if _has_error(errors, "并发防超卖场景必须包含订单数不超过库存断言"):
        mysql_assertions = list(repaired.get("mysql_assertions") or [])
        appended = _append_if_missing(
            mysql_assertions,
            "table",
            "tb_voucher_order",
            "不超过",
            {
                "table": "tb_voucher_order",
                "assertion": "订单数等于5且不超过初始库存5",
                "expected": 5,
            },
        )
        repaired["mysql_assertions"] = mysql_assertions
        if appended:
            changes.append(
                {
                    "field": "mysql_assertions",
                    "action": "append_canonical_assertion",
                    "target": "tb_voucher_order",
                }
            )


def apply_known_rule_repairs(
    scenario: Dict[str, Any],
    errors: List[str],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Apply deterministic repairs for source-backed canonical business facts."""
    repaired = copy.deepcopy(scenario)
    changes: List[Dict[str, Any]] = []
    source_rules = set(repaired.get("source_rules") or [])

    if DUPLICATE_RULE_ID in source_rules:
        _repair_duplicate_rule(repaired, errors, changes)

    if NO_OVERSALE_RULE_ID in source_rules:
        _repair_no_oversale_rule(repaired, errors, changes)

    return repaired, changes
