from __future__ import annotations

import copy
import unittest

from scripts.performance import (
    compare_seckill_performance,
)


def baseline_report() -> dict:
    business = {
        "voucher_id": 900013,
        "db_stock": 0,
        "order_count": 20,
        "distinct_user_count": 20,
        "duplicate_user_count": 0,
        "deduct_log_count": 20,
        "restore_log_count": 0,
        "verify_open_count": 0,
        "recovery_task_count": 0,
        "reconcile_task_count": 0,
        "redis_stock": 0,
        "redis_order_count": 20,
        "redis_trace_count": 20,
        "request_key_count": 0,
    }

    return {
        "scenario": "seckill-plus",
        "run_type": "baseline",
        "round_count": 3,
        "status": "PASS",
        "target": {
            "protocol": "http",
            "host": "127.0.0.1",
            "port": 8082,
            "voucher_id": 900013,
            "redis_database": 1,
        },
        "load_model": {
            "threads": 20,
            "ramp_up_seconds": 2,
            "loops_per_thread": 1,
            "unique_tokens": 20,
            "expected_samples": 20,
        },
        "metrics": {
            "sample_count": 20,
            "success_count": 20,
            "error_count": 0,
            "error_rate": 0.0,
            "duration_seconds": 4.719,
            "throughput_rps": 4.238,
            "mean_ms": 3023.55,
            "median_ms": 3012.0,
            "p90_ms": 3071,
            "p95_ms": 3082,
            "p99_ms": 3082,
            "max_ms": 3082,
        },
        "business_consistency": business,
        "environment": {
            "root_disk_usage_percent_max": 92,
            "root_disk_warning": True,
        },
        "thresholds": {
            "sample_count": {
                "expected": 20,
                "severity": "FAIL",
            },
            "error_rate": {
                "max": 0.0,
                "severity": "FAIL",
            },
            "throughput_rps": {
                "max_decrease_ratio": 0.15,
                "severity": "FAIL",
            },
            "p95_ms": {
                "max_increase_ratio": 0.15,
                "severity": "FAIL",
            },
            "p99_ms": {
                "max_increase_ratio": 0.20,
                "severity": "WARNING",
            },
            "max_ms": {
                "mode": "observe",
                "severity": "OBSERVE",
            },
            "business_consistency": {
                "expected": business.copy(),
                "severity": "FAIL",
            },
        },
        "source_rounds": [],
    }


def candidate_report() -> dict:
    report = copy.deepcopy(
        baseline_report()
    )

    report["run_type"] = "candidate"
    report.pop("thresholds")

    report["metrics"][
        "throughput_rps"
    ] = 4.219
    report["metrics"]["p95_ms"] = 3054
    report["metrics"]["p99_ms"] = 3054
    report["metrics"]["max_ms"] = 3054

    return report


class CompareSeckillPerformanceTest(
    unittest.TestCase,
):

    def test_returns_pass_when_all_checks_pass(
        self,
    ) -> None:
        result = (
            compare_seckill_performance
            .compare_reports(
                baseline_report(),
                candidate_report(),
            )
        )

        self.assertEqual(
            result["final_status"],
            "PASS",
        )
        self.assertEqual(
            result["exit_code"],
            0,
        )
        self.assertTrue(
            all(
                check["status"] == "PASS"
                for check in (
                    result[
                        "business_checks"
                    ].values()
                )
            )
        )

    def test_returns_warning_for_p99_only(
        self,
    ) -> None:
        candidate = candidate_report()

        candidate["metrics"]["p99_ms"] = 3800

        result = (
            compare_seckill_performance
            .compare_reports(
                baseline_report(),
                candidate,
            )
        )

        self.assertEqual(
            result["checks"]["p99_ms"][
                "status"
            ],
            "WARNING",
        )
        self.assertEqual(
            result["final_status"],
            "WARNING",
        )
        self.assertEqual(
            result["exit_code"],
            0,
        )

    def test_returns_fail_for_p95_regression(
        self,
    ) -> None:
        candidate = candidate_report()

        candidate["metrics"]["p95_ms"] = 3600

        result = (
            compare_seckill_performance
            .compare_reports(
                baseline_report(),
                candidate,
            )
        )

        self.assertEqual(
            result["checks"]["p95_ms"][
                "status"
            ],
            "FAIL",
        )
        self.assertEqual(
            result["final_status"],
            "FAIL",
        )
        self.assertEqual(
            result["exit_code"],
            1,
        )

    def test_returns_fail_for_business_error(
        self,
    ) -> None:
        candidate = candidate_report()

        candidate[
            "business_consistency"
        ]["order_count"] = 19

        result = (
            compare_seckill_performance
            .compare_reports(
                baseline_report(),
                candidate,
            )
        )

        self.assertEqual(
            result["business_checks"][
                "order_count"
            ]["status"],
            "FAIL",
        )
        self.assertEqual(
            result["final_status"],
            "FAIL",
        )

    def test_returns_fail_for_duplicate_order(
        self,
    ) -> None:
        candidate = candidate_report()

        candidate[
            "business_consistency"
        ]["duplicate_user_count"] = 1

        result = (
            compare_seckill_performance
            .compare_reports(
                baseline_report(),
                candidate,
            )
        )

        self.assertEqual(
            result["business_checks"][
                "duplicate_user_count"
            ]["status"],
            "FAIL",
        )

    def test_rejects_different_target(
        self,
    ) -> None:
        candidate = candidate_report()

        candidate["target"][
            "redis_database"
        ] = 0

        with self.assertRaises(ValueError):
            (
                compare_seckill_performance
                .compare_reports(
                    baseline_report(),
                    candidate,
                )
            )

    def test_rejects_different_load_model(
        self,
    ) -> None:
        candidate = candidate_report()

        candidate["load_model"][
            "threads"
        ] = 10

        with self.assertRaises(ValueError):
            (
                compare_seckill_performance
                .compare_reports(
                    baseline_report(),
                    candidate,
                )
            )

    def test_rejects_wrong_scenario(
        self,
    ) -> None:
        candidate = candidate_report()
        candidate["scenario"] = "shop-query"

        with self.assertRaises(ValueError):
            (
                compare_seckill_performance
                .compare_reports(
                    baseline_report(),
                    candidate,
                )
            )

    def test_markdown_contains_required_sections(
        self,
    ) -> None:
        result = (
            compare_seckill_performance
            .compare_reports(
                baseline_report(),
                candidate_report(),
            )
        )

        markdown = (
            compare_seckill_performance
            .render_markdown(result)
        )

        required = [
            "# Seckill Plus Performance Regression",
            "## Final Status",
            "## Fixed Load Model",
            "## Baseline Metrics",
            "## Candidate Metrics",
            "## Performance Regression Checks",
            "## Business Consistency Checks",
            "## Environment Warnings",
            "## Raw Artifact Policy",
        ]

        for section in required:
            with self.subTest(section=section):
                self.assertIn(
                    section,
                    markdown,
                )


if __name__ == "__main__":
    unittest.main()
