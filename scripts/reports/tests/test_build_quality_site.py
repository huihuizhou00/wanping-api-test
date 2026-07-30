from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPORTS_DIR))

import build_quality_site


class ManifestValidationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()

        self.manifest_path = (
            self.repository
            / "quality-site"
            / "report-manifest.json"
        )
        self.manifest_path.parent.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def valid_manifest() -> dict:
        return {
            "schema_version": 1,
            "project": {
                "id": "wanping-api-test",
                "title": "万评 AI 测试与质量工程",
            },
            "required_reports": [
                {
                    "id": "shop-query-performance",
                    "title": "商铺查询性能回归",
                    "kind": "shop_performance",
                    "source": "reports/shop.json",
                    "detail": "reports/shop.md",
                }
            ],
            "optional_reports": [
                {
                    "id": "ai-case-review",
                    "title": "AI Case 人工评审",
                    "kind": "optional_document",
                    "source": "reports/review.json",
                    "detail": "reports/review.md",
                }
            ],
        }

    def write_manifest(self, manifest: dict) -> None:
        self.manifest_path.write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_loads_valid_manifest(self) -> None:
        self.write_manifest(self.valid_manifest())

        result = build_quality_site.load_manifest(
            self.manifest_path
        )

        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(
            len(result["required_reports"]),
            1,
        )
        self.assertEqual(
            len(result["optional_reports"]),
            1,
        )

    def test_rejects_missing_schema_version(self) -> None:
        manifest = self.valid_manifest()
        del manifest["schema_version"]
        self.write_manifest(manifest)

        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "schema_version",
        ):
            build_quality_site.load_manifest(
                self.manifest_path
            )

    def test_rejects_duplicate_report_id(self) -> None:
        manifest = self.valid_manifest()
        manifest["optional_reports"][0]["id"] = (
            "shop-query-performance"
        )
        self.write_manifest(manifest)

        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "重复",
        ):
            build_quality_site.load_manifest(
                self.manifest_path
            )

    def test_rejects_unsupported_kind(self) -> None:
        manifest = self.valid_manifest()
        manifest["required_reports"][0]["kind"] = (
            "unknown_kind"
        )
        self.write_manifest(manifest)

        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "kind",
        ):
            build_quality_site.load_manifest(
                self.manifest_path
            )

    def test_rejects_optional_kind_in_required_reports(
        self,
    ) -> None:
        manifest = self.valid_manifest()
        manifest["required_reports"][0]["kind"] = (
            "optional_document"
        )
        self.write_manifest(manifest)

        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "必需报告",
        ):
            build_quality_site.load_manifest(
                self.manifest_path
            )


class SafePathTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.repository = self.root / "repository"
        self.repository.mkdir()

        self.reports = self.repository / "reports"
        self.reports.mkdir()

        self.report_file = self.reports / "report.json"
        self.report_file.write_text(
            "{}",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_resolves_repository_file(self) -> None:
        result = build_quality_site.resolve_safe_file(
            self.repository,
            "reports/report.json",
        )

        self.assertEqual(
            result,
            self.report_file.resolve(),
        )

    def test_rejects_absolute_path(self) -> None:
        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "相对路径",
        ):
            build_quality_site.resolve_safe_file(
                self.repository,
                str(self.report_file.resolve()),
            )

    def test_rejects_windows_absolute_path(self) -> None:
        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "相对路径",
        ):
            build_quality_site.resolve_safe_file(
                self.repository,
                r"C:\temp\report.json",
            )

    def test_rejects_parent_traversal(self) -> None:
        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "上级目录",
        ):
            build_quality_site.resolve_safe_file(
                self.repository,
                "../outside.json",
            )

    def test_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "不存在",
        ):
            build_quality_site.resolve_safe_file(
                self.repository,
                "reports/missing.json",
            )

    def test_rejects_directory(self) -> None:
        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "普通文件",
        ):
            build_quality_site.resolve_safe_file(
                self.repository,
                "reports",
            )

    @unittest.skipUnless(
        hasattr(os, "symlink"),
        "当前平台不支持符号链接",
    )
    def test_rejects_symlink_escape(self) -> None:
        outside_file = self.root / "outside.json"
        outside_file.write_text(
            "{}",
            encoding="utf-8",
        )

        link = self.reports / "outside-link.json"
        link.symlink_to(outside_file)

        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "仓库根目录",
        ):
            build_quality_site.resolve_safe_file(
                self.repository,
                "reports/outside-link.json",
            )


if __name__ == "__main__":
    unittest.main()
