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
