#!/usr/bin/env python3
"""万评统一质量报告站点生成器。"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


ALLOWED_STATUSES = {
    "PASS",
    "WARNING",
    "FAIL",
    "OBSERVE",
    "UNAVAILABLE",
}

ALLOWED_KINDS = {
    "shop_performance",
    "seckill_performance",
    "optional_document",
}

REQUIRED_KINDS = {
    "shop_performance",
    "seckill_performance",
}


class QualitySiteError(ValueError):
    """质量站点输入不满足约束。"""


def require_non_empty_string(
    value: Any,
    field_name: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise QualitySiteError(
            f"{field_name}必须是非空字符串"
        )

    return value.strip()


def validate_report_entry(
    entry: Any,
    section_name: str,
    report_ids: set[str],
) -> None:
    if not isinstance(entry, dict):
        raise QualitySiteError(
            f"{section_name}中的报告必须是对象"
        )

    report_id = require_non_empty_string(
        entry.get("id"),
        f"{section_name}.id",
    )

    if report_id in report_ids:
        raise QualitySiteError(
            f"发现重复报告ID：{report_id}"
        )

    report_ids.add(report_id)

    require_non_empty_string(
        entry.get("title"),
        f"{report_id}.title",
    )

    kind = require_non_empty_string(
        entry.get("kind"),
        f"{report_id}.kind",
    )

    if kind not in ALLOWED_KINDS:
        raise QualitySiteError(
            f"{report_id}.kind不受支持：{kind}"
        )

    if (
        section_name == "required_reports"
        and kind not in REQUIRED_KINDS
    ):
        raise QualitySiteError(
            f"必需报告{report_id}不能使用"
            f"kind={kind}"
        )

    if (
        section_name == "optional_reports"
        and kind != "optional_document"
    ):
        raise QualitySiteError(
            f"可选报告{report_id}必须使用"
            "kind=optional_document"
        )

    require_non_empty_string(
        entry.get("source"),
        f"{report_id}.source",
    )

    if "detail" in entry:
        require_non_empty_string(
            entry.get("detail"),
            f"{report_id}.detail",
        )


def validate_manifest(
    manifest: Any,
) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise QualitySiteError(
            "Manifest根节点必须是对象"
        )

    schema_version = manifest.get(
        "schema_version"
    )

    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != 1
    ):
        raise QualitySiteError(
            "schema_version必须为整数1"
        )

    project = manifest.get("project")

    if not isinstance(project, dict):
        raise QualitySiteError(
            "project必须是对象"
        )

    require_non_empty_string(
        project.get("id"),
        "project.id",
    )
    require_non_empty_string(
        project.get("title"),
        "project.title",
    )

    required_reports = manifest.get(
        "required_reports"
    )
    optional_reports = manifest.get(
        "optional_reports"
    )

    if (
        not isinstance(required_reports, list)
        or not required_reports
    ):
        raise QualitySiteError(
            "required_reports必须是非空数组"
        )

    if not isinstance(optional_reports, list):
        raise QualitySiteError(
            "optional_reports必须是数组"
        )

    report_ids: set[str] = set()

    for entry in required_reports:
        validate_report_entry(
            entry,
            "required_reports",
            report_ids,
        )

    for entry in optional_reports:
        validate_report_entry(
            entry,
            "optional_reports",
            report_ids,
        )

    return manifest


def load_manifest(
    path: Path,
) -> dict[str, Any]:
    try:
        text = path.read_text(
            encoding="utf-8"
        )
    except FileNotFoundError as error:
        raise QualitySiteError(
            f"Manifest文件不存在：{path}"
        ) from error
    except OSError as error:
        raise QualitySiteError(
            f"无法读取Manifest：{path}"
        ) from error

    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as error:
        raise QualitySiteError(
            f"Manifest不是有效JSON：{path}"
        ) from error

    return validate_manifest(manifest)


def resolve_safe_file(
    repository_root: Path,
    relative_path: str,
) -> Path:
    path_text = require_non_empty_string(
        relative_path,
        "报告路径",
    )

    native_path = Path(path_text)
    windows_path = PureWindowsPath(path_text)

    if (
        native_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
    ):
        raise QualitySiteError(
            "报告路径必须是仓库内相对路径："
            f"{path_text}"
        )

    normalized = path_text.replace("\\", "/")
    path_parts = PurePosixPath(normalized).parts

    if ".." in path_parts:
        raise QualitySiteError(
            "报告路径不能包含上级目录："
            f"{path_text}"
        )

    try:
        root = repository_root.resolve(
            strict=True
        )
    except FileNotFoundError as error:
        raise QualitySiteError(
            f"仓库根目录不存在：{repository_root}"
        ) from error

    if not root.is_dir():
        raise QualitySiteError(
            f"仓库根路径不是目录：{root}"
        )

    candidate = root.joinpath(*path_parts)

    try:
        resolved = candidate.resolve(
            strict=True
        )
    except FileNotFoundError as error:
        raise QualitySiteError(
            f"报告文件不存在：{path_text}"
        ) from error

    if not resolved.is_relative_to(root):
        raise QualitySiteError(
            "报告路径越过仓库根目录："
            f"{path_text}"
        )

    if not resolved.is_file():
        raise QualitySiteError(
            "报告路径不是普通文件："
            f"{path_text}"
        )

    return resolved


DISPLAY_METRICS = (
    "sample_count",
    "success_count",
    "error_count",
    "error_rate",
    "duration_seconds",
    "throughput_rps",
    "mean_ms",
    "median_ms",
    "p90_ms",
    "p95_ms",
    "p99_ms",
    "max_ms",
)

REQUIRED_METRICS = (
    "sample_count",
    "error_rate",
    "throughput_rps",
    "p95_ms",
    "p99_ms",
    "max_ms",
)

REQUIRED_CHECKS = (
    "sample_count",
    "error_rate",
    "throughput_rps",
    "p95_ms",
    "p99_ms",
    "max_ms",
)

REQUIRED_BUSINESS_CHECKS = (
    "voucher_id",
    "db_stock",
    "order_count",
    "distinct_user_count",
    "duplicate_user_count",
    "deduct_log_count",
    "restore_log_count",
    "verify_open_count",
    "recovery_task_count",
    "reconcile_task_count",
    "redis_stock",
    "redis_order_count",
    "redis_trace_count",
    "request_key_count",
)

SENSITIVE_OPTIONAL_FIELDS = {
    "authorization",
    "password",
    "secret",
    "api_key",
    "access_token",
    "refresh_token",
    "prompt",
}


def load_json_report(
    path: Path,
) -> dict[str, Any]:
    try:
        text = path.read_text(
            encoding="utf-8"
        )
    except FileNotFoundError as error:
        raise QualitySiteError(
            f"报告文件不存在：{path}"
        ) from error
    except OSError as error:
        raise QualitySiteError(
            f"无法读取报告文件：{path}"
        ) from error

    try:
        report = json.loads(text)
    except json.JSONDecodeError as error:
        raise QualitySiteError(
            f"报告不是有效JSON：{path}"
        ) from error

    if not isinstance(report, dict):
        raise QualitySiteError(
            f"报告根节点必须是对象：{path}"
        )

    return report


def require_mapping(
    value: Any,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise QualitySiteError(
            f"{field_name}必须是对象"
        )

    return value


def require_integer(
    value: Any,
    field_name: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise QualitySiteError(
            f"{field_name}必须是整数"
        )

    return value


def require_number(
    value: Any,
    field_name: str,
) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise QualitySiteError(
            f"{field_name}必须是数值"
        )

    return value


def require_status(
    value: Any,
    field_name: str,
) -> str:
    status = require_non_empty_string(
        value,
        field_name,
    )

    if status not in ALLOWED_STATUSES:
        raise QualitySiteError(
            f"{field_name}状态非法：{status}"
        )

    return status


def normalize_scalar(
    value: Any,
    field_name: str,
) -> Any:
    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    raise QualitySiteError(
        f"{field_name}必须是标量"
    )


def extract_metrics(
    metrics: Any,
    field_name: str,
) -> dict[str, int | float]:
    source = require_mapping(
        metrics,
        field_name,
    )

    for metric_name in REQUIRED_METRICS:
        if metric_name not in source:
            raise QualitySiteError(
                f"{field_name}缺少{metric_name}"
            )

    result: dict[str, int | float] = {}

    for metric_name in DISPLAY_METRICS:
        if metric_name not in source:
            continue

        result[metric_name] = require_number(
            source[metric_name],
            f"{field_name}.{metric_name}",
        )

    return result


def normalize_checks(
    checks: Any,
) -> dict[str, dict[str, Any]]:
    source = require_mapping(
        checks,
        "checks",
    )

    result = {}

    for check_name in REQUIRED_CHECKS:
        if check_name not in source:
            raise QualitySiteError(
                f"checks缺少{check_name}"
            )

        check = require_mapping(
            source[check_name],
            f"checks.{check_name}",
        )

        normalized = {
            "status": require_status(
                check.get("status"),
                f"checks.{check_name}.status",
            )
        }

        for field_name in (
            "severity",
            "baseline",
            "candidate",
            "change_ratio",
            "threshold",
        ):
            if field_name in check:
                normalized[field_name] = (
                    normalize_scalar(
                        check[field_name],
                        (
                            f"checks.{check_name}."
                            f"{field_name}"
                        ),
                    )
                )

        result[check_name] = normalized

    return result


def normalize_business_checks(
    checks: Any,
) -> dict[str, dict[str, Any]]:
    source = require_mapping(
        checks,
        "business_checks",
    )

    result = {}

    for check_name in REQUIRED_BUSINESS_CHECKS:
        if check_name not in source:
            raise QualitySiteError(
                "business_checks缺少"
                f"{check_name}"
            )

        check = require_mapping(
            source[check_name],
            f"business_checks.{check_name}",
        )

        normalized = {
            "status": require_status(
                check.get("status"),
                (
                    "business_checks."
                    f"{check_name}.status"
                ),
            )
        }

        for field_name in (
            "baseline",
            "candidate",
            "expected",
        ):
            if field_name not in check:
                raise QualitySiteError(
                    "business_checks."
                    f"{check_name}缺少"
                    f"{field_name}"
                )

            normalized[field_name] = (
                normalize_scalar(
                    check[field_name],
                    (
                        "business_checks."
                        f"{check_name}."
                        f"{field_name}"
                    ),
                )
            )

        result[check_name] = normalized

    return result


def validate_common_performance_report(
    report: Any,
    expected_scenario: str,
) -> tuple[
    str,
    int,
    dict[str, int | float],
    dict[str, int | float],
    dict[str, dict[str, Any]],
]:
    source = require_mapping(
        report,
        "report",
    )

    scenario = require_non_empty_string(
        source.get("scenario"),
        "scenario",
    )

    if scenario != expected_scenario:
        raise QualitySiteError(
            f"报告场景必须为{expected_scenario}，"
            f"实际为{scenario}"
        )

    status = require_status(
        source.get("final_status"),
        "final_status",
    )

    exit_code = require_integer(
        source.get("exit_code"),
        "exit_code",
    )

    baseline_metrics = extract_metrics(
        source.get("baseline_metrics"),
        "baseline_metrics",
    )

    candidate_metrics = extract_metrics(
        source.get("candidate_metrics"),
        "candidate_metrics",
    )

    checks = normalize_checks(
        source.get("checks")
    )

    return (
        status,
        exit_code,
        baseline_metrics,
        candidate_metrics,
        checks,
    )


def adapt_shop_performance(
    report: dict[str, Any],
    title: str,
    detail_href: str,
) -> dict[str, Any]:
    (
        status,
        exit_code,
        baseline_metrics,
        candidate_metrics,
        checks,
    ) = validate_common_performance_report(
        report,
        "shop-query",
    )

    return {
        "kind": "shop_performance",
        "title": require_non_empty_string(
            title,
            "title",
        ),
        "scenario": "shop-query",
        "status": status,
        "exit_code": exit_code,
        "detail_href": require_non_empty_string(
            detail_href,
            "detail_href",
        ),
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
        "checks": checks,
    }


def adapt_seckill_performance(
    report: dict[str, Any],
    title: str,
    detail_href: str,
) -> dict[str, Any]:
    (
        status,
        exit_code,
        baseline_metrics,
        candidate_metrics,
        checks,
    ) = validate_common_performance_report(
        report,
        "seckill-plus",
    )

    return {
        "kind": "seckill_performance",
        "title": require_non_empty_string(
            title,
            "title",
        ),
        "scenario": "seckill-plus",
        "status": status,
        "exit_code": exit_code,
        "detail_href": require_non_empty_string(
            detail_href,
            "detail_href",
        ),
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
        "checks": checks,
        "business_checks": (
            normalize_business_checks(
                report.get("business_checks")
            )
        ),
    }


def extract_optional_summary(
    report: dict[str, Any],
) -> dict[str, Any]:
    summary = {}

    for key, value in report.items():
        lowered_key = key.lower()

        if any(
            fragment in lowered_key
            for fragment in SENSITIVE_OPTIONAL_FIELDS
        ):
            continue

        if not isinstance(
            value,
            (str, int, float, bool),
        ):
            continue

        if (
            isinstance(value, str)
            and len(value) > 160
        ):
            continue

        summary[key] = value

        if len(summary) >= 12:
            break

    return summary


def adapt_optional_document(
    path: Path | None,
    title: str,
    detail_href: str | None,
) -> dict[str, Any]:
    normalized_title = require_non_empty_string(
        title,
        "title",
    )

    if path is None or not path.is_file():
        return {
            "kind": "optional_document",
            "title": normalized_title,
            "status": "UNAVAILABLE",
            "available": False,
            "detail_href": detail_href,
            "summary": {},
        }

    report = load_json_report(path)

    raw_status = report.get(
        "final_status",
        report.get("status"),
    )

    status = (
        "OBSERVE"
        if raw_status is None
        else require_status(
            raw_status,
            "optional_report.status",
        )
    )

    return {
        "kind": "optional_document",
        "title": normalized_title,
        "status": status,
        "available": True,
        "detail_href": detail_href,
        "summary": extract_optional_summary(
            report
        ),
    }
