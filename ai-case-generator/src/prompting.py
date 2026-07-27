from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


MODULE_RULE_SCOPE = {
    "seckill_plus": {
        "RULE-AUTH-UNAUTHORIZED",
        "RULE-PATH-LONG-INVALID",
        "RULE-SECKILL-STOCK-NOT-INITIALIZED",
        "RULE-SECKILL-SUCCESS",
        "RULE-SECKILL-DUPLICATE",
    },
    "cache_async": {
        "RULE-SHOP-CACHE-REBUILD",
        "RULE-RATING-MQ-DEGRADE",
        "RULE-RATING-CACHE-INVALIDATE",
    },
    "concurrency_consistency": {
        "RULE-SECKILL-NO-OVERSALE",
    },
}


MODULE_GENERATION_CONSTRAINTS = {
    "seckill_plus": {
        "required_case_plan": [
            {
                "case_id": "AI-SECKILL-001",
                "primary_rule": "RULE-AUTH-UNAUTHORIZED",
                "authorization": "<MISSING>",
                "expected_http_status": 401,
                "focus": "唯一未登录场景，headers中不得出现authorization",
            },
            {
                "case_id": "AI-SECKILL-002",
                "primary_rule": "RULE-PATH-LONG-INVALID",
                "authorization": "<VALID_TOKEN>",
                "expected_http_status": 400,
                "focus": "携带有效Token后传入非数字voucherId，验证Long路径参数校验",
            },
            {
                "case_id": "AI-SECKILL-003",
                "primary_rule": "RULE-SECKILL-STOCK-NOT-INITIALIZED",
                "authorization": "<VALID_TOKEN>",
                "expected_http_status": 200,
                "focus": "携带有效Token，错误文案逐字包含秒杀库存未初始化",
            },
            {
                "case_id": "AI-SECKILL-004",
                "primary_rule": "RULE-SECKILL-SUCCESS",
                "authorization": "<VALID_TOKEN>",
                "expected_http_status": 200,
                "focus": "携带有效Token并完整断言Redis与MySQL副作用",
            },
            {
                "case_id": "AI-SECKILL-005",
                "primary_rule": "RULE-SECKILL-DUPLICATE",
                "authorization": "<VALID_TOKEN>",
                "expected_http_status": 200,
                "focus": "携带有效Token并完整断言重复下单无额外副作用",
            },
        ],
        "auth_policy": (
            "除AI-SECKILL-001外，其余秒杀场景即使属于参数异常、边界或业务失败，"
            "request.headers.authorization也必须逐字填写<VALID_TOKEN>，"
            "避免鉴权401遮蔽目标规则。"
        ),
        "source_rule_policy": (
            "每条场景的source_rules必须且只能包含required_case_plan指定的一个主规则，"
            "不得把本模块全部规则复制到每条场景。"
        ),
        "duplicate_assertions": [
            "Redis seckill:stock:{voucherId}库存保持不变",
            "MySQL tb_seckill_voucher库存保持不变",
            "MySQL tb_voucher_order订单数保持不变且不新增订单",
        ],
        "forbidden_rules": ["RULE-SECKILL-NO-OVERSALE"],
    },
    "concurrency_consistency": {
        "required_case_plan": [
            {
                "case_id": "AI-CONCURRENCY-001",
                "primary_rule": "RULE-SECKILL-NO-OVERSALE",
                "test_type": "concurrency",
                "focus": "20个请求严格成功5、失败15，库存不为负",
            },
            {
                "case_id": "AI-CONCURRENCY-002",
                "primary_rule": "RULE-SECKILL-NO-OVERSALE",
                "test_type": "consistency",
                "focus": "等待RocketMQ落库后Redis库存、MySQL库存、订单数和用户数一致",
            },
        ],
        "source_rule_policy": (
            "每条场景source_rules只能包含RULE-SECKILL-NO-OVERSALE。"
        ),
    },
}


def select_module_rules(rules: Dict[str, Any], module: str) -> Dict[str, Any]:
    allowed_endpoint_modules = {
        "cache_async": {"shop_query", "shop_detail_voucher"},
        "concurrency_consistency": {"seckill_plus"},
    }.get(module, {module})

    raw_endpoints = [
        item
        for item in rules.get("endpoints", [])
        if item.get("module") in allowed_endpoint_modules
    ]

    explicit_scope = MODULE_RULE_SCOPE.get(module)
    if explicit_scope is not None:
        endpoints = []
        for endpoint in raw_endpoints:
            filtered_endpoint = dict(endpoint)
            filtered_endpoint["rules"] = [
                rule_id
                for rule_id in endpoint.get("rules", [])
                if rule_id in explicit_scope
            ]
            endpoints.append(filtered_endpoint)
    else:
        endpoints = [dict(endpoint) for endpoint in raw_endpoints]

    endpoint_rule_ids = {
        rule_id
        for endpoint in endpoints
        for rule_id in endpoint.get("rules", [])
    }

    if explicit_scope is not None:
        selected_rule_ids = endpoint_rule_ids & explicit_scope
    else:
        selected_rule_ids = {
            item.get("id")
            for item in rules.get("business_rules", [])
            if item.get("id") in endpoint_rule_ids
            or item.get("module") in {module, "shared"}
        }

    business_rules = [
        item
        for item in rules.get("business_rules", [])
        if item.get("id") in selected_rule_ids
    ]

    return {
        "module": module,
        "endpoint_rules": endpoints,
        "business_rules": business_rules,
        "generation_constraints": MODULE_GENERATION_CONSTRAINTS.get(module, {}),
        "known_data": rules.get("known_data", {}),
        "redis_keys": rules.get("redis_keys", {}),
        "mysql_tables": rules.get("mysql_tables", []),
    }


def render_prompt(
    template_path: Path,
    rules: Dict[str, Any],
    module: str,
    module_name: str,
    case_id_prefix: str,
    case_count: int,
    retry_errors: List[str] | None = None,
) -> str:
    template = template_path.read_text(encoding="utf-8")

    retry_feedback = ""
    if retry_errors:
        unique_errors = list(dict.fromkeys(retry_errors))
        retry_feedback = (
            "上一次输出没有通过程序校验。请重新生成整批数据，并全部修正以下问题：\n- "
            + "\n- ".join(unique_errors[:40])
        )

    module_rules = select_module_rules(rules, module)
    endpoint_rules = module_rules["endpoint_rules"]
    if not endpoint_rules:
        raise ValueError(f"模块{module}没有可用接口规则")
    example_endpoint = endpoint_rules[0]

    replacements = {
        "{{MODULE}}": module,
        "{{MODULE_NAME}}": module_name,
        "{{CASE_ID_PREFIX}}": case_id_prefix,
        "{{CASE_COUNT}}": str(case_count),
        "{{EXAMPLE_ENDPOINT}}": str(example_endpoint["path"]),
        "{{EXAMPLE_METHOD}}": str(example_endpoint["method"]),
        "{{RULES_JSON}}": json.dumps(
            module_rules,
            ensure_ascii=False,
            indent=2,
        ),
        "{{RETRY_FEEDBACK}}": retry_feedback,
    }

    for key, value in replacements.items():
        template = template.replace(key, value)

    return template


def render_repair_prompt(
    template_path: Path,
    rules: Dict[str, Any],
    module: str,
    module_name: str,
    case_id_prefix: str,
    original_scenario: Dict[str, Any],
    validation_errors: List[str],
    allowed_fields: List[str],
) -> str:
    """Render a prompt that repairs exactly one invalid scenario."""
    # Read the template so a missing project asset fails early in the same way as
    # the full-batch path. The repair prompt itself is intentionally narrower.
    template_path.read_text(encoding="utf-8")
    module_rules = select_module_rules(rules, module)
    case_id = str(original_scenario.get("case_id", ""))
    unique_errors = list(dict.fromkeys(validation_errors))
    allowed_fields_text = "\n".join(
    f"- {field}"
    for field in allowed_fields
)

    return (
        "你是资深接口测试设计工程师。现在只修复一条未通过校验的结构化测试场景，"
        "不得重新生成或改写其他场景。\n\n"
        f"模块：{module}（{module_name}）\n"
        f"case_id前缀：{case_id_prefix}\n"
        f"必须保持case_id逐字为：{case_id}\n"
        f"必须保持module逐字为：{module}\n\n"
        "只输出一个JSON对象，不要Markdown代码块，不要解释文字。顶层必须且只能是：\n"
        '{"scenarios": [修复后的唯一一条场景]}\n\n'
        "本轮程序只允许修复以下字段：\n"
        + allowed_fields_text
        + "\n\n"
        "即使你输出的其他字段发生变化，"
        "程序也会忽略这些变化。"
        "请保持其他字段与原场景完全一致。\n\n"
        "强制要求：\n"
        "1. scenarios数组必须恰好包含1条场景。\n"
        "2. case_id和module不得改变。\n"
        "3. 只修改“允许修复字段”列表中的字段。不得修改错误文案、请求参数、MySQL断言等未列出的字段。\n"
        "4. 15个顶层字段和所有嵌套必填字段必须齐全，不得增加别名字段。\n"
        "5. 不得发明接口、错误文案、Redis Key、MySQL表或业务行为。\n"
        "6. source_rules必须遵守已验证规则和generation_constraints。\n\n"
        "程序校验错误：\n- "
        + "\n- ".join(unique_errors)
        + "\n\n待修复原场景：\n"
        + json.dumps(original_scenario, ensure_ascii=False, indent=2)
        + "\n\n已验证规则：\n"
        + json.dumps(module_rules, ensure_ascii=False, indent=2)
    )
