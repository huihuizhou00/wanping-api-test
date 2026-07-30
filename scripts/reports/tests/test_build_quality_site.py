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


PERFORMANCE_CHECK_NAMES = (
    "sample_count",
    "error_rate",
    "throughput_rps",
    "p95_ms",
    "p99_ms",
    "max_ms",
)

BUSINESS_CHECK_NAMES = (
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


def build_metrics(
    sample_count: int,
    throughput_rps: float,
    p95_ms: int,
    p99_ms: int,
) -> dict:
    return {
        "sample_count": sample_count,
        "success_count": sample_count,
        "error_count": 0,
        "error_rate": 0.0,
        "duration_seconds": 4.7,
        "throughput_rps": throughput_rps,
        "mean_ms": float(p95_ms),
        "median_ms": float(p95_ms),
        "p90_ms": p95_ms,
        "p95_ms": p95_ms,
        "p99_ms": p99_ms,
        "max_ms": p99_ms,
    }


def build_performance_checks(
    baseline: dict,
    candidate: dict,
) -> dict:
    checks = {}

    for name in PERFORMANCE_CHECK_NAMES:
        checks[name] = {
            "baseline": baseline[name],
            "candidate": candidate[name],
            "change_ratio": 0.0,
            "threshold": "test threshold",
            "status": (
                "OBSERVE"
                if name == "max_ms"
                else "PASS"
            ),
        }

    return checks


def build_shop_report() -> dict:
    baseline = build_metrics(
        400,
        209.205,
        8,
        16,
    )
    candidate = build_metrics(
        400,
        213.447,
        8,
        9,
    )

    return {
        "scenario": "shop-query",
        "final_status": "PASS",
        "exit_code": 0,
        "baseline_metrics": baseline,
        "candidate_metrics": candidate,
        "checks": build_performance_checks(
            baseline,
            candidate,
        ),
    }


def business_value(name: str) -> int:
    if name == "voucher_id":
        return 900013

    if name in {
        "order_count",
        "distinct_user_count",
        "deduct_log_count",
        "redis_order_count",
        "redis_trace_count",
    }:
        return 20

    return 0


def build_seckill_report() -> dict:
    baseline = build_metrics(
        20,
        4.238,
        3082,
        3082,
    )
    candidate = build_metrics(
        20,
        4.219,
        3054,
        3054,
    )

    business_checks = {
        name: {
            "baseline": business_value(name),
            "candidate": business_value(name),
            "expected": business_value(name),
            "status": "PASS",
        }
        for name in BUSINESS_CHECK_NAMES
    }

    return {
        "scenario": "seckill-plus",
        "final_status": "PASS",
        "exit_code": 0,
        "baseline_metrics": baseline,
        "candidate_metrics": candidate,
        "checks": build_performance_checks(
            baseline,
            candidate,
        ),
        "business_checks": business_checks,
    }


class ReportAdapterTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_loads_valid_json_report(self) -> None:
        path = self.root / "report.json"
        path.write_text(
            json.dumps(build_shop_report()),
            encoding="utf-8",
        )

        result = build_quality_site.load_json_report(
            path
        )

        self.assertEqual(
            result["scenario"],
            "shop-query",
        )

    def test_rejects_invalid_json_report(self) -> None:
        path = self.root / "invalid.json"
        path.write_text(
            "{invalid",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "有效JSON",
        ):
            build_quality_site.load_json_report(
                path
            )

    def test_adapts_shop_report(self) -> None:
        result = (
            build_quality_site
            .adapt_shop_performance(
                build_shop_report(),
                "商铺查询性能回归",
                "reports/shop.md",
            )
        )

        self.assertEqual(
            result["status"],
            "PASS",
        )
        self.assertEqual(
            result["baseline_metrics"][
                "throughput_rps"
            ],
            209.205,
        )
        self.assertEqual(
            result["candidate_metrics"][
                "p99_ms"
            ],
            9,
        )

    def test_rejects_wrong_shop_scenario(self) -> None:
        report = build_shop_report()
        report["scenario"] = "other"

        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "shop-query",
        ):
            build_quality_site.adapt_shop_performance(
                report,
                "商铺查询性能回归",
                "reports/shop.md",
            )

    def test_rejects_invalid_status(self) -> None:
        report = build_shop_report()
        report["final_status"] = "SUCCESS"

        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "final_status",
        ):
            build_quality_site.adapt_shop_performance(
                report,
                "商铺查询性能回归",
                "reports/shop.md",
            )

    def test_rejects_missing_metric(self) -> None:
        report = build_shop_report()
        del report["candidate_metrics"]["p95_ms"]

        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "p95_ms",
        ):
            build_quality_site.adapt_shop_performance(
                report,
                "商铺查询性能回归",
                "reports/shop.md",
            )

    def test_adapts_seckill_report(self) -> None:
        result = (
            build_quality_site
            .adapt_seckill_performance(
                build_seckill_report(),
                "秒杀 Plus 性能回归",
                "reports/seckill.md",
            )
        )

        self.assertEqual(
            result["candidate_metrics"]["p95_ms"],
            3054,
        )
        self.assertEqual(
            result["business_checks"][
                "order_count"
            ]["candidate"],
            20,
        )
        self.assertEqual(
            result["business_checks"][
                "duplicate_user_count"
            ]["candidate"],
            0,
        )

    def test_rejects_missing_business_check(
        self,
    ) -> None:
        report = build_seckill_report()
        del report["business_checks"]["redis_stock"]

        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "redis_stock",
        ):
            build_quality_site.adapt_seckill_performance(
                report,
                "秒杀 Plus 性能回归",
                "reports/seckill.md",
            )

    def test_optional_missing_is_unavailable(
        self,
    ) -> None:
        result = (
            build_quality_site
            .adapt_optional_document(
                self.root / "missing.json",
                "AI Case 人工评审",
                None,
            )
        )

        self.assertFalse(result["available"])
        self.assertEqual(
            result["status"],
            "UNAVAILABLE",
        )

    def test_optional_without_status_is_observe(
        self,
    ) -> None:
        path = self.root / "optional.json"
        path.write_text(
            json.dumps(
                {
                    "total_cases": 12,
                    "selected_cases": 7,
                }
            ),
            encoding="utf-8",
        )

        result = (
            build_quality_site
            .adapt_optional_document(
                path,
                "AI Case 人工评审",
                "reports/review.md",
            )
        )

        self.assertTrue(result["available"])
        self.assertEqual(
            result["status"],
            "OBSERVE",
        )
        self.assertEqual(
            result["summary"]["total_cases"],
            12,
        )
