from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPORTS_DIR))

import build_quality_site


PERFORMANCE_CHECKS = (
    "sample_count",
    "error_rate",
    "throughput_rps",
    "p95_ms",
    "p99_ms",
    "max_ms",
)

BUSINESS_CHECKS = (
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


def metrics(
    samples: int,
    rps: float,
    p95: int,
    p99: int,
) -> dict:
    return {
        "sample_count": samples,
        "success_count": samples,
        "error_count": 0,
        "error_rate": 0.0,
        "duration_seconds": 4.7,
        "throughput_rps": rps,
        "mean_ms": float(p95),
        "median_ms": float(p95),
        "p90_ms": p95,
        "p95_ms": p95,
        "p99_ms": p99,
        "max_ms": p99,
    }


def checks(
    baseline: dict,
    candidate: dict,
) -> dict:
    return {
        name: {
            "baseline": baseline[name],
            "candidate": candidate[name],
            "change_ratio": 0.0,
            "threshold": "test",
            "status": (
                "OBSERVE"
                if name == "max_ms"
                else "PASS"
            ),
        }
        for name in PERFORMANCE_CHECKS
    }


def shop_report() -> dict:
    baseline = metrics(400, 209.205, 8, 16)
    candidate = metrics(400, 213.447, 8, 9)

    return {
        "scenario": "shop-query",
        "final_status": "PASS",
        "exit_code": 0,
        "baseline_metrics": baseline,
        "candidate_metrics": candidate,
        "checks": checks(
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


def seckill_report() -> dict:
    baseline = metrics(20, 4.238, 3082, 3082)
    candidate = metrics(20, 4.219, 3054, 3054)

    return {
        "scenario": "seckill-plus",
        "final_status": "PASS",
        "exit_code": 0,
        "baseline_metrics": baseline,
        "candidate_metrics": candidate,
        "checks": checks(
            baseline,
            candidate,
        ),
        "business_checks": {
            name: {
                "baseline": business_value(name),
                "candidate": business_value(name),
                "expected": business_value(name),
                "status": "PASS",
            }
            for name in BUSINESS_CHECKS
        },
    }


class QualitySiteBuildTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = (
            Path(self.temp_dir.name)
            / "repository"
        )
        self.repository.mkdir()

        assets = (
            self.repository
            / "quality-site"
            / "assets"
        )
        assets.mkdir(parents=True)

        (assets / "style.css").write_text(
            "body { font-family: sans-serif; }\n",
            encoding="utf-8",
        )

        reports = self.repository / "reports"
        reports.mkdir()

        (reports / "shop.json").write_text(
            json.dumps(shop_report()),
            encoding="utf-8",
        )
        (reports / "shop.md").write_text(
            "# 商铺查询报告\n",
            encoding="utf-8",
        )

        (reports / "seckill.json").write_text(
            json.dumps(seckill_report()),
            encoding="utf-8",
        )
        (reports / "seckill.md").write_text(
            "# 秒杀 Plus 报告\n",
            encoding="utf-8",
        )

        manifest = {
            "schema_version": 1,
            "project": {
                "id": "wanping-api-test",
                "title": "万评 <质量> 工程",
            },
            "required_reports": [
                {
                    "id": "shop-query-performance",
                    "title": "商铺查询性能回归",
                    "kind": "shop_performance",
                    "source": "reports/shop.json",
                    "detail": "reports/shop.md",
                },
                {
                    "id": "seckill-plus-performance",
                    "title": "秒杀 Plus 性能回归",
                    "kind": "seckill_performance",
                    "source": "reports/seckill.json",
                    "detail": "reports/seckill.md",
                },
            ],
            "optional_reports": [
                {
                    "id": "ai-case-review",
                    "title": "AI Case 人工评审",
                    "kind": "optional_document",
                    "source": "reports/missing.json",
                    "detail": "reports/missing.md",
                }
            ],
        }

        self.manifest = (
            self.repository
            / "quality-site"
            / "report-manifest.json"
        )
        self.manifest.write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        self.output = (
            self.repository
            / "build"
            / "quality-site"
        )

        self.metadata = {
            "commit_sha": "abc123def456",
            "branch": "main",
            "publish_mode": "local",
            "ci_run_url": (
                "https://github.com/example/"
                "actions/runs/123"
            ),
            "published_at": (
                "2026-07-30T10:00:00Z"
            ),
            "repository": "wanping-api-test",
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_calculates_overall_status(self) -> None:
        self.assertEqual(
            build_quality_site
            .calculate_overall_status(
                [{"status": "PASS"}]
            ),
            "PASS",
        )
        self.assertEqual(
            build_quality_site
            .calculate_overall_status(
                [
                    {"status": "PASS"},
                    {"status": "WARNING"},
                ]
            ),
            "WARNING",
        )
        self.assertEqual(
            build_quality_site
            .calculate_overall_status(
                [
                    {"status": "WARNING"},
                    {"status": "FAIL"},
                ]
            ),
            "FAIL",
        )

    def test_builds_complete_site(self) -> None:
        result = build_quality_site.build_site(
            repository_root=self.repository,
            manifest_path=self.manifest,
            output_directory=self.output,
            metadata=self.metadata,
        )

        index = (
            self.output / "index.html"
        ).read_text(encoding="utf-8")

        build_metadata = json.loads(
            (
                self.output
                / "build-metadata.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(
            result["overall_status"],
            "PASS",
        )
        self.assertEqual(
            build_metadata["commit_sha"],
            "abc123def456",
        )
        self.assertEqual(
            build_metadata["overall_status"],
            "PASS",
        )

        self.assertIn(
            "万评 &lt;质量&gt; 工程",
            index,
        )
        self.assertIn("213.447", index)
        self.assertIn("3054", index)
        self.assertIn("UNAVAILABLE", index)
        self.assertIn(
            "异步订单确认等待",
            index,
        )
        self.assertIn(
            "abc123def456",
            index,
        )

        self.assertTrue(
            (
                self.output
                / "assets"
                / "style.css"
            ).is_file()
        )
        self.assertTrue(
            (
                self.output
                / "reports"
                / "shop-query-performance.md"
            ).is_file()
        )
        self.assertTrue(
            (
                self.output
                / "reports"
                / "seckill-plus-performance.md"
            ).is_file()
        )

    def test_missing_required_report_fails(
        self,
    ) -> None:
        (
            self.repository
            / "reports"
            / "shop.json"
        ).unlink()

        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "不存在",
        ):
            build_quality_site.build_site(
                repository_root=self.repository,
                manifest_path=self.manifest,
                output_directory=self.output,
                metadata=self.metadata,
            )

    def test_rejects_unsafe_ci_url(self) -> None:
        metadata = dict(self.metadata)
        metadata["ci_run_url"] = (
            "javascript:alert(1)"
        )

        with self.assertRaisesRegex(
            build_quality_site.QualitySiteError,
            "CI链接",
        ):
            build_quality_site.build_site(
                repository_root=self.repository,
                manifest_path=self.manifest,
                output_directory=self.output,
                metadata=metadata,
            )


if __name__ == "__main__":
    unittest.main()
