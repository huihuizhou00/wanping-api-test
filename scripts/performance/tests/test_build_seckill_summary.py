from __future__ import annotations

import copy
import unittest

from scripts.performance import build_seckill_summary


def round_report(
    round_number: int,
    *,
    run_type: str = "baseline",
) -> dict:
    return {
        "scenario": "seckill-plus",
        "run_type": run_type,
        "round": round_number,
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
            "duration_seconds": 4.7 + round_number / 100,
            "throughput_rps": [
                4.216,
                4.238,
                4.239,
            ][round_number - 1],
            "mean_ms": [
                3023.55,
                3019.95,
                3055.7,
            ][round_number - 1],
            "median_ms": [
                3012.0,
                3012.0,
                3011.0,
            ][round_number - 1],
            "p90_ms": [
                3071,
                3049,
                3215,
            ][round_number - 1],
            "p95_ms": [
                3082,
                3067,
                3245,
            ][round_number - 1],
            "p99_ms": [
                3082,
                3067,
                3245,
            ][round_number - 1],
            "max_ms": [
                3082,
                3067,
                3245,
            ][round_number - 1],
        },
        "business_consistency": {
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
        },
        "environment": {
            "root_disk_usage_percent": 92,
        },
        "raw_artifact_directory": (
            f"/mnt/wanping-performance/"
            f"seckill-round{round_number}"
        ),
    }


class BuildSeckillSummaryTest(unittest.TestCase):

    def test_builds_three_round_medians(
        self,
    ) -> None:
        result = build_seckill_summary.build_summary(
            [
                round_report(1),
                round_report(2),
                round_report(3),
            ],
            run_type="baseline",
        )

        metrics = result["metrics"]

        self.assertEqual(
            metrics["sample_count"],
            20,
        )
        self.assertEqual(
            metrics["throughput_rps"],
            4.238,
        )
        self.assertEqual(
            metrics["median_ms"],
            3012.0,
        )
        self.assertEqual(
            metrics["p95_ms"],
            3082,
        )
        self.assertEqual(
            metrics["p99_ms"],
            3082,
        )
        self.assertEqual(
            result["round_count"],
            3,
        )

    def test_rejects_wrong_round_count(
        self,
    ) -> None:
        with self.assertRaises(ValueError):
            build_seckill_summary.build_summary(
                [
                    round_report(1),
                    round_report(2),
                ],
                run_type="baseline",
            )

    def test_rejects_wrong_scenario(
        self,
    ) -> None:
        reports = [
            round_report(1),
            round_report(2),
            round_report(3),
        ]

        reports[1]["scenario"] = "shop-query"

        with self.assertRaises(ValueError):
            build_seckill_summary.build_summary(
                reports,
                run_type="baseline",
            )

    def test_rejects_wrong_run_type(
        self,
    ) -> None:
        reports = [
            round_report(1),
            round_report(2),
            round_report(3),
        ]

        reports[2]["run_type"] = "candidate"

        with self.assertRaises(ValueError):
            build_seckill_summary.build_summary(
                reports,
                run_type="baseline",
            )

    def test_rejects_http_errors(
        self,
    ) -> None:
        reports = [
            round_report(1),
            round_report(2),
            round_report(3),
        ]

        reports[0]["metrics"]["error_count"] = 1
        reports[0]["metrics"]["error_rate"] = 0.05

        with self.assertRaises(ValueError):
            build_seckill_summary.build_summary(
                reports,
                run_type="baseline",
            )

    def test_rejects_business_inconsistency(
        self,
    ) -> None:
        reports = [
            round_report(1),
            round_report(2),
            round_report(3),
        ]

        reports[2][
            "business_consistency"
        ]["order_count"] = 19

        with self.assertRaises(ValueError):
            build_seckill_summary.build_summary(
                reports,
                run_type="baseline",
            )

    def test_rejects_different_load_model(
        self,
    ) -> None:
        reports = [
            round_report(1),
            round_report(2),
            round_report(3),
        ]

        reports[1]["load_model"] = copy.deepcopy(
            reports[1]["load_model"]
        )
        reports[1]["load_model"]["threads"] = 10

        with self.assertRaises(ValueError):
            build_seckill_summary.build_summary(
                reports,
                run_type="baseline",
            )

    def test_baseline_contains_thresholds(
        self,
    ) -> None:
        result = build_seckill_summary.build_summary(
            [
                round_report(1),
                round_report(2),
                round_report(3),
            ],
            run_type="baseline",
        )

        thresholds = result["thresholds"]

        self.assertEqual(
            thresholds["sample_count"]["expected"],
            20,
        )
        self.assertEqual(
            thresholds["error_rate"]["max"],
            0.0,
        )
        self.assertEqual(
            thresholds[
                "throughput_rps"
            ]["max_decrease_ratio"],
            0.15,
        )
        self.assertEqual(
            thresholds[
                "p95_ms"
            ]["max_increase_ratio"],
            0.15,
        )

    def test_candidate_has_no_thresholds(
        self,
    ) -> None:
        result = build_seckill_summary.build_summary(
            [
                round_report(
                    1,
                    run_type="candidate",
                ),
                round_report(
                    2,
                    run_type="candidate",
                ),
                round_report(
                    3,
                    run_type="candidate",
                ),
            ],
            run_type="candidate",
        )

        self.assertNotIn(
            "thresholds",
            result,
        )


if __name__ == "__main__":
    unittest.main()
