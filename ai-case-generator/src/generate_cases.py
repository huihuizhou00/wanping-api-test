from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .exporters import write_outputs
from .model_client import ModelOutputError, OpenAICompatibleClient, ensure_module_batch
from .normalizers import normalize_structural_defaults
from .prompting import render_prompt, render_repair_prompt
from .rule_repairs import apply_known_rule_repairs
from .settings import load_generator_settings, load_model_settings, load_yaml
from .validators import ValidationReport, validate_business, validate_schema


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成万评AI结构化测试场景")
    parser.add_argument("--input", type=Path, help="校验已有模型JSON，不调用模型")
    parser.add_argument("--dry-run", action="store_true", help="只生成各模块Prompt")
    parser.add_argument("--fail-on-invalid", action="store_true", help="存在校验失败时返回非0")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    return parser.parse_args()


def _flatten_report_errors(report: ValidationReport) -> List[str]:
    errors: List[str] = []

    errors.extend(f"全局错误: {message}" for message in report.global_errors)

    for case_id, messages in report.schema_case_errors.items():
        errors.extend(f"Schema[{case_id}]: {message}" for message in messages)

    for case_id, messages in report.case_errors.items():
        errors.extend(f"业务[{case_id}]: {message}" for message in messages)

    return list(dict.fromkeys(errors))


def validate_module_candidate(
    batch: Dict[str, Any],
    module: str,
    expected_count: int,
    schema: Dict[str, Any],
    rules: Dict[str, Any],
) -> List[str]:
    structure_errors = ensure_module_batch(batch, module, expected_count)
    if structure_errors:
        return structure_errors

    schema_report = ValidationReport()
    validate_schema(batch, schema, schema_report)
    schema_errors = _flatten_report_errors(schema_report)
    if schema_errors:
        return schema_errors

    business_report = ValidationReport()
    validate_business(
        batch,
        rules,
        {module: expected_count},
        business_report,
    )
    return _flatten_report_errors(business_report)


def prepare_module_candidate(
    batch: Dict[str, Any],
    module: str,
    expected_count: int,
    schema: Dict[str, Any],
    rules: Dict[str, Any],
):
    normalized, changes = normalize_structural_defaults(batch)
    errors = validate_module_candidate(
        normalized,
        module,
        expected_count,
        schema,
        rules,
    )
    return normalized, changes, errors

def determine_repair_fields(
    errors: List[str],
) -> List[str]:
    """
    根据确定性的校验错误，计算本轮允许模型修复的字段。

    没有明确映射的错误不会自动扩大修复范围，
    防止模型重写整条测试场景。
    """
    fields: List[str] = []

    def add(field: str) -> None:
        if field not in fields:
            fields.append(field)

    for error in errors:
        if "错误文案不正确" in error:
            add(
                "expected_business_result."
                "error_contains"
            )

        if (
            "缺少Redis" in error
            or "Redis库存断言" in error
        ):
            add("redis_assertions")

        if (
            "缺少MySQL库存" in error
            or "缺少订单数" in error
            or "缺少订单表断言" in error
        ):
            add("mysql_assertions")

        if "未携带Token" in error:
            add("request.headers")

        if "预期HTTP状态" in error:
            add("expected_http_status")

        if (
            "success必须" in error
            or "success不正确" in error
        ):
            add(
                "expected_business_result.success"
            )

        if (
            "空列表" in error
            or "data断言" in error
        ):
            add(
                "expected_business_result."
                "data_assertions"
            )

        if "并发防超卖场景必须包含非负库存断言" in error:
            add("redis_assertions")
            add("mysql_assertions")

        if "并发防超卖场景必须包含订单数不超过库存断言" in error:
            add("mysql_assertions")

    return fields


_MISSING = object()


def read_nested_value(
    data: Dict[str, Any],
    path: str,
):
    current: Any = data

    for part in path.split("."):
        if not isinstance(current, dict):
            return _MISSING

        if part not in current:
            return _MISSING

        current = current[part]

    return current


def write_nested_value(
    data: Dict[str, Any],
    path: str,
    value: Any,
) -> None:
    parts = path.split(".")
    current = data

    for part in parts[:-1]:
        child = current.get(part)

        if not isinstance(child, dict):
            child = {}
            current[part] = child

        current = child

    current[parts[-1]] = copy.deepcopy(value)


def merge_repair_candidate(
    original_scenario: Dict[str, Any],
    candidate_scenario: Dict[str, Any],
    allowed_fields: List[str],
) -> Tuple[
    Dict[str, Any],
    List[str],
    List[str],
]:
    """
    只把允许修复的字段从候选场景合并到原始场景。

    返回：
    1. 合并后的场景
    2. 实际应用的字段
    3. 候选中缺失的允许字段
    """
    merged = copy.deepcopy(
        original_scenario
    )
    applied_fields: List[str] = []
    missing_fields: List[str] = []

    for field in allowed_fields:
        value = read_nested_value(
            candidate_scenario,
            field,
        )

        if value is _MISSING:
            missing_fields.append(field)
            continue

        write_nested_value(
            merged,
            field,
            value,
        )
        applied_fields.append(field)

    return (
        merged,
        applied_fields,
        missing_fields,
    )


def validate_single_scenario(
    scenario: Dict[str, Any],
    schema: Dict[str, Any],
    rules: Dict[str, Any],
) -> List[str]:
    batch = {"scenarios": [scenario]}
    schema_report = ValidationReport()
    validate_schema(batch, schema, schema_report)
    schema_errors = _flatten_report_errors(schema_report)
    if schema_errors:
        return schema_errors

    business_report = ValidationReport()
    validate_business(batch, rules, {}, business_report)
    return _flatten_report_errors(business_report)


def ensure_single_scenario_batch(
    batch: Dict[str, Any],
    expected_case_id: str,
    expected_module: str,
) -> List[str]:
    scenarios = batch.get("scenarios")
    if not isinstance(scenarios, list):
        return ["修复结果顶层scenarios必须是数组"]
    if len(scenarios) != 1:
        return [f"修复结果必须恰好包含1条场景，实际{len(scenarios)}条"]
    scenario = scenarios[0]
    if not isinstance(scenario, dict):
        return ["修复结果scenarios[0]必须是对象"]

    errors: List[str] = []
    if scenario.get("case_id") != expected_case_id:
        errors.append(f"修复场景case_id必须保持为{expected_case_id}")
    if scenario.get("module") != expected_module:
        errors.append(f"修复场景module必须保持为{expected_module}")
    return errors


def ensure_repairable_module_batch(
    batch: Dict[str, Any],
    module: str,
    expected_count: int,
) -> List[str]:
    errors = ensure_module_batch(batch, module, expected_count)
    scenarios = batch.get("scenarios")
    if not isinstance(scenarios, list):
        return errors

    seen = set()
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            continue
        case_id = scenario.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"scenarios[{index}].case_id必须是非空字符串")
            continue
        if case_id in seen:
            errors.append(f"case_id重复，无法定向修复: {case_id}")
        seen.add(case_id)
    return list(dict.fromkeys(errors))


def repair_invalid_scenarios(
    batch: Dict[str, Any],
    module: str,
    module_name: str,
    case_id_prefix: str,
    schema: Dict[str, Any],
    rules: Dict[str, Any],
    client: OpenAICompatibleClient,
    prompt_template: Path,
    raw_dir: Path,
    max_retries: int,
    audit_path: Path | None = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    repaired_batch = copy.deepcopy(batch)
    scenarios = repaired_batch["scenarios"]
    repair_events: List[Dict[str, Any]] = []
    normalization_events: List[Dict[str, Any]] = []

    def persist_repair_events() -> None:
        if audit_path is None:
            return
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(
            json.dumps(repair_events, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    for index, scenario in enumerate(list(scenarios)):
        errors = validate_single_scenario(scenario, schema, rules)
        if not errors:
            continue

        case_id = str(
            scenario.get(
                "case_id",
                f"<index:{index}>",
            )
        )
        repair_base_scenario = copy.deepcopy(scenario)
        repair_base_errors = list(errors)

        (
            rule_repaired_scenario,
            rule_repair_changes,
        ) = apply_known_rule_repairs(
            repair_base_scenario,
            repair_base_errors,
        )

        if rule_repair_changes:
            rule_errors_after = validate_single_scenario(
                rule_repaired_scenario,
                schema,
                rules,
            )
            rule_status = (
                "accepted"
                if not rule_errors_after
                else "partial"
            )
            repair_events.append(
                {
                    "module": module,
                    "case_id": case_id,
                    "repair_attempt": 0,
                    "actor": "rule_engine",
                    "status": rule_status,
                    "errors_before": repair_base_errors,
                    "errors_after": rule_errors_after,
                    "changes": rule_repair_changes,
                }
            )
            persist_repair_events()

            repair_base_scenario = rule_repaired_scenario
            repair_base_errors = rule_errors_after

            if not repair_base_errors:
                scenarios[index] = repair_base_scenario
                print(f"场景{case_id}规则引擎修复通过")
                continue

        allowed_fields = determine_repair_fields(
            repair_base_errors
        )
        if not allowed_fields:
            raise RuntimeError(
                f"场景{case_id}存在无法安全定向修复的错误: "
                + "; ".join(repair_base_errors)
            )

        feedback_errors = list(repair_base_errors)

        for repair_attempt in range(1, max_retries + 2):
            prompt = render_repair_prompt(
                prompt_template,
                rules,
                module,
                module_name,
                case_id_prefix,
                repair_base_scenario,
                feedback_errors,
                allowed_fields,
            )
            stem = f"{module}-repair-{case_id}-attempt-{repair_attempt}"
            (raw_dir / f"{stem}-prompt.txt").write_text(
                prompt,
                encoding="utf-8",
            )

            try:
                candidate_batch = client.generate(prompt)
                (raw_dir / f"{stem}.json").write_text(
                    json.dumps(candidate_batch, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                normalized, changes = normalize_structural_defaults(candidate_batch)

                if changes:
                    (raw_dir / f"{stem}-normalized.json").write_text(
                        json.dumps(normalized, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    normalization_events.extend(
                        {
                            "module": module,
                            "case_id": case_id,
                            "stage": "targeted_repair",
                            "repair_attempt": repair_attempt,
                            **change,
                        }
                        for change in changes
                    )

                candidate_errors = ensure_single_scenario_batch(
                    normalized,
                    expected_case_id=case_id,
                    expected_module=module,
                )
                candidate_scenario = None
                applied_fields: List[str] = []
                missing_repair_fields: List[str] = []

                if not candidate_errors:
                    raw_candidate_scenario = normalized["scenarios"][0]
                    (
                        candidate_scenario,
                        applied_fields,
                        missing_repair_fields,
                    ) = merge_repair_candidate(
                        repair_base_scenario,
                        raw_candidate_scenario,
                        allowed_fields,
                    )

                    if missing_repair_fields:
                        candidate_errors.extend(
                            "修复结果缺少允许修复字段: " + field
                            for field in missing_repair_fields
                        )

                    if not candidate_errors:
                        candidate_errors = validate_single_scenario(
                            candidate_scenario,
                            schema,
                            rules,
                        )

                status = "accepted" if not candidate_errors else "rejected"
                repair_events.append(
                    {
                        "module": module,
                        "case_id": case_id,
                        "repair_attempt": repair_attempt,
                        "actor": "llm",
                        "status": status,
                        "errors_before": feedback_errors,
                        "errors_after": candidate_errors,
                        "allowed_fields": allowed_fields,
                        "applied_fields": applied_fields,
                        "missing_repair_fields": missing_repair_fields,
                    }
                )
                persist_repair_events()

                if not candidate_errors and candidate_scenario is not None:
                    scenarios[index] = candidate_scenario
                    print(
                        f"场景{case_id}定向修复通过，"
                        f"attempt={repair_attempt}"
                    )
                    break

                feedback_errors = candidate_errors
                print(
                    f"场景{case_id}第{repair_attempt}次定向修复未通过，"
                    f"错误数={len(candidate_errors)}"
                )

            except ModelOutputError as exc:
                feedback_errors = [str(exc)]
                repair_events.append(
                    {
                        "module": module,
                        "case_id": case_id,
                        "repair_attempt": repair_attempt,
                        "status": "model_output_error",
                        "actor": "llm",
                        "errors_before": repair_base_errors,
                        "errors_after": feedback_errors,
                    }
                )
                persist_repair_events()
            except Exception as exc:  # noqa: BLE001
                feedback_errors = [str(exc)]
                repair_events.append(
                    {
                        "module": module,
                        "case_id": case_id,
                        "repair_attempt": repair_attempt,
                        "status": "call_error",
                        "actor": "llm",
                        "errors_before": repair_base_errors,
                        "errors_after": feedback_errors,
                    }
                )
                persist_repair_events()
        else:
            raise RuntimeError(
                f"场景{case_id}在{max_retries + 1}次定向修复后仍未通过: "
                + "; ".join(feedback_errors)
            )

    return repaired_batch, repair_events, normalization_events

def generate_live(project_dir: Path, output_dir: Path) -> Dict[str, Any]:
    generator = load_generator_settings(project_dir / "config/generator.yaml")
    model = load_model_settings(project_dir)
    rules = load_yaml(project_dir / "config/api_rules.yaml")
    schema = json.loads(
        (project_dir / "schemas/test-case-batch.schema.json").read_text(
            encoding="utf-8"
        )
    )
    modules = rules["modules"]
    client = OpenAICompatibleClient(model, generator, schema)
    all_scenarios: List[Dict[str, Any]] = []
    normalization_events: List[Dict[str, Any]] = []
    repair_events: List[Dict[str, Any]] = []
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for module, count in generator.module_quotas.items():
        retry_errors: List[str] = []
        last_error = ""
        module_batch = None
        initial_attempt_number = 0
        initial_normalization_count = 0

        # Full-batch retries are now limited to outputs that cannot be repaired
        # safely by case id, such as wrong counts, wrong modules, or duplicate ids.
        for attempt in range(generator.max_retries + 1):
            prompt = render_prompt(
                project_dir / "prompts/generate_cases.txt",
                rules,
                module,
                modules[module]["name"],
                modules[module]["case_id_prefix"],
                count,
                retry_errors,
            )

            attempt_number = attempt + 1
            (raw_dir / f"{module}-attempt-{attempt_number}-prompt.txt").write_text(
                prompt,
                encoding="utf-8",
            )

            try:
                batch = client.generate(prompt)
                (raw_dir / f"{module}-attempt-{attempt_number}.json").write_text(
                    json.dumps(batch, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                normalized_batch, changes = normalize_structural_defaults(batch)

                if changes:
                    initial_normalization_count += len(changes)
                    normalization_events.extend(
                        {
                            "module": module,
                            "attempt": attempt_number,
                            "stage": "initial_batch",
                            **change,
                        }
                        for change in changes
                    )
                    (
                        raw_dir
                        / f"{module}-attempt-{attempt_number}-normalized.json"
                    ).write_text(
                        json.dumps(
                            normalized_batch,
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )

                retry_errors = ensure_repairable_module_batch(
                    normalized_batch,
                    module,
                    count,
                )
                if not retry_errors:
                    module_batch = normalized_batch
                    initial_attempt_number = attempt_number
                    break

                last_error = "; ".join(retry_errors)
                print(
                    f"模块{module}第{attempt_number}次初始批次不可定向修复，"
                    f"错误数={len(retry_errors)}"
                )

            except ModelOutputError as exc:
                last_error = str(exc)
                retry_errors = [last_error]
                print(
                    f"模块{module}第{attempt_number}次模型输出无效: {last_error}"
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                retry_errors = [last_error]
                print(
                    f"模块{module}第{attempt_number}次调用异常: {last_error}"
                )
        else:
            raise RuntimeError(
                f"模块{module}在{generator.max_retries + 1}次初始生成后仍不可定向修复: "
                f"{last_error}"
            )

        repaired_batch, module_repair_events, repair_normalizations = (
            repair_invalid_scenarios(
                batch=module_batch,
                module=module,
                module_name=modules[module]["name"],
                case_id_prefix=modules[module]["case_id_prefix"],
                schema=schema,
                rules=rules,
                client=client,
                prompt_template=project_dir / "prompts/generate_cases.txt",
                raw_dir=raw_dir,
                max_retries=generator.max_retries,
                audit_path=output_dir / f"{module}-repair-events.json",
            )
        )
        repair_events.extend(module_repair_events)
        normalization_events.extend(repair_normalizations)

        final_errors = validate_module_candidate(
            repaired_batch,
            module,
            count,
            schema,
            rules,
        )
        if final_errors:
            raise RuntimeError(
                f"模块{module}定向修复后整体校验仍未通过: "
                + "; ".join(final_errors)
            )

        all_scenarios.extend(repaired_batch["scenarios"])
        rule_engine_repairs = sum(
            event.get("actor") == "rule_engine"
            and event.get("status") == "accepted"
            for event in module_repair_events
        )
        llm_repairs = sum(
            event.get("actor") == "llm"
            and event.get("status") == "accepted"
            for event in module_repair_events
        )
        print(
            f"模块{module}生成通过，"
            f"initial_attempt={initial_attempt_number}，cases={count}，"
            f"规则修复={rule_engine_repairs}，"
            f"LLM定向修复={llm_repairs}，"
            f"结构归一化={initial_normalization_count + len(repair_normalizations)}"
        )

        (output_dir / "normalization-events.json").write_text(
            json.dumps(
                normalization_events,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (output_dir / "repair-events.json").write_text(
            json.dumps(
                repair_events,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    if not normalization_events:
        (output_dir / "normalization-events.json").write_text(
            "[]\n",
            encoding="utf-8",
        )
    if not repair_events:
        (output_dir / "repair-events.json").write_text(
            "[]\n",
            encoding="utf-8",
        )

    return {"scenarios": all_scenarios}

def dry_run(project_dir: Path, output_dir: Path) -> None:
    generator = load_generator_settings(project_dir / "config/generator.yaml")
    rules = load_yaml(project_dir / "config/api_rules.yaml")
    modules = rules["modules"]
    prompt_dir = output_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    for module, count in generator.module_quotas.items():
        prompt = render_prompt(
            project_dir / "prompts/generate_cases.txt",
            rules,
            module,
            modules[module]["name"],
            modules[module]["case_id_prefix"],
            count,
        )
        (prompt_dir / f"{module}.txt").write_text(prompt, encoding="utf-8")

    print(f"已生成{len(generator.module_quotas)}个模块Prompt: {prompt_dir}")


def main() -> int:
    args = parse_args()
    project_dir = Path(__file__).resolve().parents[1]
    output_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else project_dir / args.output_dir
    )

    if args.dry_run:
        dry_run(project_dir, output_dir)
        return 0

    if args.input:
        input_path = (
            args.input
            if args.input.is_absolute()
            else Path.cwd() / args.input
        )
        batch = json.loads(input_path.read_text(encoding="utf-8"))
    else:
        batch = generate_live(project_dir, output_dir)

    schema = json.loads(
        (project_dir / "schemas/test-case-batch.schema.json").read_text(
            encoding="utf-8"
        )
    )
    rules = load_yaml(project_dir / "config/api_rules.yaml")
    generator = load_generator_settings(project_dir / "config/generator.yaml")
    report = ValidationReport()
    validate_schema(batch, schema, report)
    validate_business(batch, rules, generator.module_quotas, report)
    write_outputs(output_dir, batch, report)

    print(f"生成场景数: {len(batch.get('scenarios', []))}")
    print(f"全局错误数: {len(report.global_errors)}")
    print(f"Schema失败场景数: {len(report.schema_case_errors)}")
    print(f"业务失败场景数: {len(report.case_errors)}")
    print(f"结果目录: {output_dir}")

    if args.fail_on_invalid and not report.valid:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
