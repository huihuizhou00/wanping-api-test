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


import shutil
from html import escape
from urllib.parse import urlsplit


STATUS_PRIORITY = {
    "PASS": 0,
    "OBSERVE": 1,
    "WARNING": 2,
    "FAIL": 3,
}

METRIC_LABELS = {
    "sample_count": "样本数",
    "success_count": "成功数",
    "error_count": "错误数",
    "error_rate": "错误率",
    "duration_seconds": "持续时间（秒）",
    "throughput_rps": "吞吐量（RPS）",
    "mean_ms": "平均响应时间（ms）",
    "median_ms": "中位响应时间（ms）",
    "p90_ms": "P90（ms）",
    "p95_ms": "P95（ms）",
    "p99_ms": "P99（ms）",
    "max_ms": "最大响应时间（ms）",
}

BUSINESS_LABELS = {
    "voucher_id": "测试券 ID",
    "db_stock": "数据库库存",
    "order_count": "订单数",
    "distinct_user_count": "独立用户数",
    "duplicate_user_count": "重复用户数",
    "deduct_log_count": "库存扣减日志数",
    "restore_log_count": "库存恢复日志数",
    "verify_open_count": "待验证记录数",
    "recovery_task_count": "恢复任务数",
    "reconcile_task_count": "对账任务数",
    "redis_stock": "Redis 库存",
    "redis_order_count": "Redis 订单用户数",
    "redis_trace_count": "Redis Trace 数",
    "request_key_count": "残留请求键数",
}


def calculate_overall_status(
    required_reports: list[dict[str, Any]],
) -> str:
    if not required_reports:
        raise QualitySiteError(
            "至少需要一个必需报告"
        )

    highest = "PASS"

    for report in required_reports:
        status = require_status(
            report.get("status"),
            "required_report.status",
        )

        if status == "UNAVAILABLE":
            raise QualitySiteError(
                "必需报告不能为UNAVAILABLE"
            )

        if (
            STATUS_PRIORITY.get(status, 0)
            > STATUS_PRIORITY.get(highest, 0)
        ):
            highest = status

    return highest


def validate_ci_url(url: Any) -> str:
    if url in (None, ""):
        return ""

    normalized = require_non_empty_string(
        url,
        "CI链接",
    )
    parsed = urlsplit(normalized)

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
    ):
        raise QualitySiteError(
            f"CI链接不安全：{normalized}"
        )

    return normalized


def resolve_optional_file(
    repository_root: Path,
    relative_path: str,
) -> Path | None:
    path_text = require_non_empty_string(
        relative_path,
        "可选报告路径",
    )

    native = Path(path_text)
    windows = PureWindowsPath(path_text)

    if (
        native.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
    ):
        raise QualitySiteError(
            "可选报告路径必须是相对路径："
            f"{path_text}"
        )

    normalized = path_text.replace("\\", "/")
    parts = PurePosixPath(normalized).parts

    if ".." in parts:
        raise QualitySiteError(
            "可选报告路径不能包含上级目录："
            f"{path_text}"
        )

    root = repository_root.resolve(
        strict=True
    )
    candidate = root.joinpath(*parts)

    if not candidate.exists():
        return None

    return resolve_safe_file(
        root,
        path_text,
    )


def format_value(value: Any) -> str:
    if value is None:
        return "—"

    if isinstance(value, float):
        return f"{value:.6g}"

    return str(value)


def status_badge(status: str) -> str:
    normalized = require_status(
        status,
        "status",
    )

    return (
        '<span class="status '
        f'status-{normalized.lower()}">'
        f"{escape(normalized)}"
        "</span>"
    )


def render_metrics_table(
    report: dict[str, Any],
) -> str:
    baseline = report["baseline_metrics"]
    candidate = report["candidate_metrics"]

    rows = []

    for name in METRIC_LABELS:
        if (
            name not in baseline
            or name not in candidate
        ):
            continue

        rows.append(
            "<tr>"
            f"<th>{escape(METRIC_LABELS[name])}</th>"
            f"<td>{escape(format_value(baseline[name]))}</td>"
            f"<td>{escape(format_value(candidate[name]))}</td>"
            "</tr>"
        )

    return (
        '<div class="table-wrapper">'
        "<table>"
        "<thead><tr>"
        "<th>指标</th>"
        "<th>Baseline</th>"
        "<th>Candidate</th>"
        "</tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def render_checks_table(
    report: dict[str, Any],
) -> str:
    rows = []

    for name, check in report["checks"].items():
        rows.append(
            "<tr>"
            f"<th>{escape(METRIC_LABELS.get(name, name))}</th>"
            f"<td>{escape(format_value(check.get('baseline')))}</td>"
            f"<td>{escape(format_value(check.get('candidate')))}</td>"
            f"<td>{escape(format_value(check.get('threshold')))}</td>"
            f"<td>{status_badge(check['status'])}</td>"
            "</tr>"
        )

    return (
        "<h4>质量门禁</h4>"
        '<div class="table-wrapper">'
        "<table>"
        "<thead><tr>"
        "<th>检查项</th>"
        "<th>Baseline</th>"
        "<th>Candidate</th>"
        "<th>阈值</th>"
        "<th>状态</th>"
        "</tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def render_business_table(
    report: dict[str, Any],
) -> str:
    checks = report.get("business_checks")

    if not checks:
        return ""

    rows = []

    for name, check in checks.items():
        rows.append(
            "<tr>"
            f"<th>{escape(BUSINESS_LABELS.get(name, name))}</th>"
            f"<td>{escape(format_value(check['candidate']))}</td>"
            f"<td>{escape(format_value(check['expected']))}</td>"
            f"<td>{status_badge(check['status'])}</td>"
            "</tr>"
        )

    return (
        "<h4>业务一致性</h4>"
        '<div class="table-wrapper">'
        "<table>"
        "<thead><tr>"
        "<th>检查项</th>"
        "<th>Candidate</th>"
        "<th>期望值</th>"
        "<th>状态</th>"
        "</tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def render_performance_card(
    report: dict[str, Any],
) -> str:
    notice = ""

    if report["kind"] == "seckill_performance":
        notice = (
            '<p class="notice">'
            "当前约 3 秒响应时间包含应用层"
            "异步订单确认等待，不应直接解释为 "
            "Lua 或 Redis 原子校验本身耗时。"
            "</p>"
        )

    return (
        '<article class="card">'
        f"<h3>{escape(report['title'])}</h3>"
        f"<p>{status_badge(report['status'])}</p>"
        f"{render_metrics_table(report)}"
        f"{render_checks_table(report)}"
        f"{render_business_table(report)}"
        f"{notice}"
        '<p><a href="'
        f"{escape(report['detail_href'], quote=True)}"
        '">查看版本化明细报告</a></p>'
        "</article>"
    )


def render_optional_card(
    report: dict[str, Any],
) -> str:
    items = []

    for key, value in report["summary"].items():
        items.append(
            "<dt>"
            f"{escape(str(key))}"
            "</dt><dd>"
            f"{escape(format_value(value))}"
            "</dd>"
        )

    summary = (
        '<dl class="meta-list">'
        + "".join(items)
        + "</dl>"
        if items
        else "<p>当前版本未提供可展示的结构化指标。</p>"
    )

    detail = ""

    if (
        report.get("available")
        and report.get("detail_href")
    ):
        detail = (
            '<p><a href="'
            f"{escape(report['detail_href'], quote=True)}"
            '">查看版本化明细报告</a></p>'
        )

    return (
        '<article class="card">'
        f"<h3>{escape(report['title'])}</h3>"
        f"<p>{status_badge(report['status'])}</p>"
        f"{summary}"
        f"{detail}"
        "</article>"
    )


def render_index_html(
    project: dict[str, Any],
    reports: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> str:
    title = require_non_empty_string(
        project.get("title"),
        "project.title",
    )

    required = [
        report
        for report in reports
        if report["kind"]
        in {
            "shop_performance",
            "seckill_performance",
        }
    ]

    optional = [
        report
        for report in reports
        if report["kind"]
        == "optional_document"
    ]

    performance_cards = "".join(
        render_performance_card(report)
        for report in required
    )

    optional_cards = "".join(
        render_optional_card(report)
        for report in optional
    )

    ci_url = metadata["ci_run_url"]

    ci_link = (
        '<a href="'
        f"{escape(ci_url, quote=True)}"
        '">查看上游 CI</a>'
        if ci_url
        else "本地构建，无上游 CI 链接"
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>{escape(title)}｜统一质量报告</title>
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  <header class="site-header">
    <div class="site-header-inner">
      <h1 class="site-title">{escape(title)}</h1>
      <p class="site-description">
        汇总接口自动化、AI 测试、性能回归和业务一致性结果。
      </p>
      <p>{status_badge(metadata["overall_status"])}</p>
    </div>
  </header>

  <main class="page-content">
    <section class="section">
      <article class="card">
        <h2>发布信息</h2>
        <dl class="meta-list">
          <dt>Commit</dt>
          <dd>{escape(metadata["commit_sha"])}</dd>
          <dt>分支</dt>
          <dd>{escape(metadata["branch"])}</dd>
          <dt>发布方式</dt>
          <dd>{escape(metadata["publish_mode"])}</dd>
          <dt>发布时间</dt>
          <dd>{escape(metadata["published_at"])}</dd>
          <dt>上游 CI</dt>
          <dd>{ci_link}</dd>
        </dl>
      </article>
    </section>

    <section class="section">
      <h2>性能回归与一致性</h2>
      <div class="card-grid">
        {performance_cards}
      </div>
    </section>

    <section class="section">
      <h2>AI 测试结果</h2>
      <div class="card-grid">
        {optional_cards}
      </div>
    </section>
  </main>

  <footer class="site-footer">
    由版本化测试报告自动生成，不执行在线压测或模型调用。
  </footer>
</body>
</html>
"""


def validate_metadata(
    metadata: dict[str, Any],
) -> dict[str, str]:
    required_fields = (
        "commit_sha",
        "branch",
        "publish_mode",
        "published_at",
        "repository",
    )

    result = {}

    for field_name in required_fields:
        result[field_name] = (
            require_non_empty_string(
                metadata.get(field_name),
                field_name,
            )
        )

    result["ci_run_url"] = validate_ci_url(
        metadata.get("ci_run_url", "")
    )

    return result


def build_site(
    repository_root: Path,
    manifest_path: Path,
    output_directory: Path,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    root = repository_root.resolve(
        strict=True
    )

    normalized_metadata = validate_metadata(
        metadata
    )

    manifest = load_manifest(
        manifest_path
    )

    if output_directory.is_symlink():
        raise QualitySiteError(
            "输出目录不能是符号链接"
        )

    if output_directory.exists():
        shutil.rmtree(output_directory)

    assets_output = (
        output_directory / "assets"
    )
    reports_output = (
        output_directory / "reports"
    )

    assets_output.mkdir(
        parents=True,
        exist_ok=True,
    )
    reports_output.mkdir(
        parents=True,
        exist_ok=True,
    )

    style_source = resolve_safe_file(
        root,
        "quality-site/assets/style.css",
    )
    shutil.copyfile(
        style_source,
        assets_output / "style.css",
    )

    adapted_reports = []

    for entry in manifest["required_reports"]:
        source = resolve_safe_file(
            root,
            entry["source"],
        )
        detail = resolve_safe_file(
            root,
            entry["detail"],
        )

        output_name = f"{entry['id']}.md"
        detail_href = f"reports/{output_name}"

        shutil.copyfile(
            detail,
            reports_output / output_name,
        )

        raw_report = load_json_report(source)

        if entry["kind"] == "shop_performance":
            adapted = adapt_shop_performance(
                raw_report,
                entry["title"],
                detail_href,
            )
        elif entry["kind"] == "seckill_performance":
            adapted = adapt_seckill_performance(
                raw_report,
                entry["title"],
                detail_href,
            )
        else:
            raise QualitySiteError(
                "不支持的必需报告类型："
                f"{entry['kind']}"
            )

        adapted_reports.append(adapted)

    for entry in manifest["optional_reports"]:
        source = resolve_optional_file(
            root,
            entry["source"],
        )
        detail = resolve_optional_file(
            root,
            entry["detail"],
        )

        detail_href = None

        if source is not None and detail is not None:
            output_name = f"{entry['id']}.md"
            detail_href = f"reports/{output_name}"

            shutil.copyfile(
                detail,
                reports_output / output_name,
            )

        adapted_reports.append(
            adapt_optional_document(
                source,
                entry["title"],
                detail_href,
            )
        )

    required_reports = [
        report
        for report in adapted_reports
        if report["kind"]
        in {
            "shop_performance",
            "seckill_performance",
        }
    ]

    overall_status = calculate_overall_status(
        required_reports
    )

    build_metadata = {
        "schema_version": 1,
        **normalized_metadata,
        "required_report_count": len(
            manifest["required_reports"]
        ),
        "optional_report_count": len(
            manifest["optional_reports"]
        ),
        "overall_status": overall_status,
    }

    index_html = render_index_html(
        manifest["project"],
        adapted_reports,
        build_metadata,
    )

    (output_directory / "index.html").write_text(
        index_html,
        encoding="utf-8",
    )

    (
        output_directory
        / "build-metadata.json"
    ).write_text(
        json.dumps(
            build_metadata,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    return build_metadata


def parse_arguments() -> Any:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "生成万评统一质量报告站点"
        )
    )

    parser.add_argument(
        "--repository-root",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--commit-sha",
        required=True,
    )
    parser.add_argument(
        "--branch",
        required=True,
    )
    parser.add_argument(
        "--publish-mode",
        required=True,
    )
    parser.add_argument(
        "--ci-run-url",
        default="",
    )
    parser.add_argument(
        "--published-at",
        required=True,
    )
    parser.add_argument(
        "--repository",
        required=True,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    repository_root = (
        args.repository_root.resolve(
            strict=True
        )
    )

    manifest_path = args.manifest

    if not manifest_path.is_absolute():
        manifest_path = (
            repository_root / manifest_path
        )

    output_directory = args.output

    if not output_directory.is_absolute():
        output_directory = (
            repository_root / output_directory
        )

    result = build_site(
        repository_root=repository_root,
        manifest_path=manifest_path,
        output_directory=output_directory,
        metadata={
            "commit_sha": args.commit_sha,
            "branch": args.branch,
            "publish_mode": args.publish_mode,
            "ci_run_url": args.ci_run_url,
            "published_at": args.published_at,
            "repository": args.repository,
        },
    )

    print(
        "QUALITY_SITE_BUILD = PASS"
    )
    print(
        "OVERALL_STATUS =",
        result["overall_status"],
    )
    print(
        "OUTPUT_DIRECTORY =",
        output_directory,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
