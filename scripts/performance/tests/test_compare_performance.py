from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]

MODULE_PATH = (
    REPO_ROOT
    / "scripts"
    / "performance"
    / "compare_performance.py"
)


def load_compare_module() -> ModuleType:
    if not MODULE_PATH.is_file():
        raise AssertionError(
            "缺少生产文件："
            "scripts/performance/compare_performance.py"
        )

    spec = importlib.util.spec_from_file_location(
        "compare_performance",
        MODULE_PATH,
    )

    if spec is None or spec.loader is None:
        raise AssertionError(
            f"无法加载模块：{MODULE_PATH}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def load_model() -> dict[str, Any]:
    return {
        "threads": 20,
        "ramp_up_seconds": 2,
        "loops_per_thread": 20,
        "expected_samples": 400,
        "warmup_samples": 20,
    }


def baseline_report() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "scenario": "shop-query",
        "status": "provisional",
        "baseline_method": "median_of_three_rounds",
        "round_count": 3,
        "load_model": load_model(),
        "environment": {
            "root_disk_usage_percent": 92,
            "environment_warning": (
                "root_disk_usage_high"
            ),
            "jmeter_result_storage": (
                "/mnt/wanping-performance"
            ),
        },
        "metrics": {
            "sample_count": 400,
            "error_count": 0,
            "error_rate": 0.0,
            "throughput_rps": 209.205,
            "mean_ms": 6.595,
            "median_ms": 6.0,
            "p90_ms": 8,
            "p95_ms": 8,
            "p99_ms": 16,
            "max_ms": 57,
        },
        "thresholds": {
            "sample_count": {
                "severity": "hard",
                "operator": "equal",
                "value": 400,
            },
            "error_rate": {
                "severity": "hard",
                "operator": "less_than_or_equal",
                "absolute_max": 0.01,
            },
            "throughput_rps": {
                "severity": "hard",
                "operator": (
                    "decrease_ratio_less_than_or_equal"
                ),
                "max_decrease_ratio": 0.15,
            },
            "p95_ms": {
                "severity": "hard",
                "operator": (
                    "increase_ratio_less_than_or_equal"
                ),
                "max_increase_ratio": 0.20,
            },
            "p99_ms": {
                "severity": "warning",
                "operator": (
                    "increase_ratio_less_than_or_equal"
                ),
                "max_increase_ratio": 0.25,
            },
            "max_ms": {
                "severity": "observe",
            },
        },
    }


def candidate_report(
    *,
    sample_count: int = 400,
    error_rate: float = 0.0,
    throughput_rps: float = 205.0,
    p95_ms: float = 9,
    p99_ms: float = 18,
    max_ms: float = 60,
) -> dict[str, Any]:
    error_count = round(
        sample_count * error_rate
    )

    return {
        "schema_version": "1.0",
        "scenario": "shop-query",
        "run_type": "candidate",
        "status": "provisional",
        "candidate_method": (
            "median_of_three_rounds"
        ),
        "round_count": 3,
        "load_model": load_model(),
        "environment": {
            "root_disk_usage_percent": 92,
            "environment_warning": (
                "root_disk_usage_high"
            ),
            "jmeter_result_storage": (
                "/mnt/wanping-performance"
            ),
        },
        "metrics": {
            "sample_count": sample_count,
            "error_count": error_count,
            "error_rate": error_rate,
            "throughput_rps": throughput_rps,
            "mean_ms": 7.0,
            "median_ms": 6.0,
            "p90_ms": 9,
            "p95_ms": p95_ms,
            "p99_ms": p99_ms,
            "max_ms": max_ms,
        },
    }


class ComparePerformanceTest(unittest.TestCase):

    def test_returns_pass_when_all_gates_pass(
        self,
    ) -> None:
        module = load_compare_module()

        result = module.compare_reports(
            baseline_report(),
            candidate_report(),
        )

        self.assertEqual(
            result["final_status"],
            "PASS",
        )
        self.assertEqual(
            result["exit_code"],
            0,
        )
        self.assertEqual(
            result["checks"]["sample_count"][
                "status"
            ],
            "PASS",
        )
        self.assertEqual(
            result["checks"]["error_rate"][
                "status"
            ],
            "PASS",
        )
        self.assertEqual(
            result["checks"]["throughput_rps"][
                "status"
            ],
            "PASS",
        )
        self.assertEqual(
            result["checks"]["p95_ms"][
                "status"
            ],
            "PASS",
        )
        self.assertEqual(
            result["checks"]["p99_ms"][
                "status"
            ],
            "PASS",
        )
        self.assertEqual(
            result["checks"]["max_ms"][
                "status"
            ],
            "OBSERVE",
        )

    def test_returns_warning_when_only_p99_fails(
        self,
    ) -> None:
        module = load_compare_module()

        result = module.compare_reports(
            baseline_report(),
            candidate_report(
                p99_ms=21,
            ),
        )

        self.assertEqual(
            result["final_status"],
            "WARNING",
        )
        self.assertEqual(
            result["exit_code"],
            0,
        )
        self.assertEqual(
            result["checks"]["p99_ms"][
                "status"
            ],
            "WARNING",
        )

    def test_returns_fail_for_wrong_sample_count(
        self,
    ) -> None:
        module = load_compare_module()

        result = module.compare_reports(
            baseline_report(),
            candidate_report(
                sample_count=399,
            ),
        )

        self.assertEqual(
            result["final_status"],
            "FAIL",
        )
        self.assertEqual(
            result["exit_code"],
            1,
        )
        self.assertEqual(
            result["checks"]["sample_count"][
                "status"
            ],
            "FAIL",
        )

    def test_returns_fail_for_error_rate(
        self,
    ) -> None:
        module = load_compare_module()

        result = module.compare_reports(
            baseline_report(),
            candidate_report(
                error_rate=0.02,
            ),
        )

        self.assertEqual(
            result["final_status"],
            "FAIL",
        )
        self.assertEqual(
            result["checks"]["error_rate"][
                "status"
            ],
            "FAIL",
        )

    def test_returns_fail_for_throughput_regression(
        self,
    ) -> None:
        module = load_compare_module()

        result = module.compare_reports(
            baseline_report(),
            candidate_report(
                throughput_rps=170.0,
            ),
        )

        self.assertEqual(
            result["final_status"],
            "FAIL",
        )
        self.assertEqual(
            result["checks"]["throughput_rps"][
                "status"
            ],
            "FAIL",
        )

    def test_returns_fail_for_p95_regression(
        self,
    ) -> None:
        module = load_compare_module()

        result = module.compare_reports(
            baseline_report(),
            candidate_report(
                p95_ms=10,
            ),
        )

        self.assertEqual(
            result["final_status"],
            "FAIL",
        )
        self.assertEqual(
            result["checks"]["p95_ms"][
                "status"
            ],
            "FAIL",
        )

    def test_rejects_different_scenario(
        self,
    ) -> None:
        module = load_compare_module()

        candidate = candidate_report()
        candidate["scenario"] = "other-scenario"

        with self.assertRaisesRegex(
            ValueError,
            "scenario",
        ):
            module.compare_reports(
                baseline_report(),
                candidate,
            )

    def test_rejects_different_load_model(
        self,
    ) -> None:
        module = load_compare_module()

        candidate = candidate_report()
        candidate["load_model"]["threads"] = 30

        with self.assertRaisesRegex(
            ValueError,
            "load_model",
        ):
            module.compare_reports(
                baseline_report(),
                candidate,
            )

    def test_rejects_non_positive_baseline_metrics(
        self,
    ) -> None:
        module = load_compare_module()

        invalid_fields = [
            "throughput_rps",
            "p95_ms",
            "p99_ms",
        ]

        for field in invalid_fields:
            with self.subTest(field=field):
                baseline = baseline_report()
                baseline["metrics"][field] = 0

                with self.assertRaisesRegex(
                    ValueError,
                    field,
                ):
                    module.compare_reports(
                        baseline,
                        candidate_report(),
                    )

    def test_render_markdown_contains_report_sections(
        self,
    ) -> None:
        module = load_compare_module()

        comparison = module.compare_reports(
            baseline_report(),
            candidate_report(),
        )

        report = module.render_markdown(
            comparison
        )

        required_text = [
            "# Shop Query Performance Regression",
            "Final Status",
            "Fixed Load Model",
            "Baseline Metrics",
            "Candidate Metrics",
            "Regression Checks",
            "Environment Warnings",
            "Raw Artifact Policy",
            "209.205",
            "P95",
            "P99",
            "92%",
            "/mnt/wanping-performance",
        ]

        for text in required_text:
            with self.subTest(text=text):
                self.assertIn(text, report)


if __name__ == "__main__":
    unittest.main()
