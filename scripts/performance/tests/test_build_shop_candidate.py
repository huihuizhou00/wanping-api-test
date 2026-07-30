from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]

MODULE_PATH = (
    REPO_ROOT
    / "scripts"
    / "performance"
    / "build_shop_candidate.py"
)


def load_candidate_module() -> ModuleType:
    """从固定路径加载待测试模块。"""

    if not MODULE_PATH.is_file():
        raise AssertionError(
            "缺少生产文件："
            "scripts/performance/build_shop_candidate.py"
        )

    spec = importlib.util.spec_from_file_location(
        "build_shop_candidate",
        MODULE_PATH,
    )

    if spec is None or spec.loader is None:
        raise AssertionError(
            f"无法加载模块：{MODULE_PATH}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def candidate_round(
    *,
    throughput_rps: float,
    mean_ms: float,
    median_ms: float,
    p90_ms: int,
    p95_ms: int,
    p99_ms: int,
    max_ms: int,
) -> dict:
    """构造一轮合法的 Candidate 指标。"""

    return {
        "schema_version": "1.0",
        "scenario": "shop-query",
        "run_type": "candidate",
        "metrics": {
            "sample_count": 400,
            "success_count": 400,
            "error_count": 0,
            "error_rate": 0.0,
            "duration_seconds": 2.0,
            "throughput_rps": throughput_rps,
            "min_ms": 3,
            "mean_ms": mean_ms,
            "median_ms": median_ms,
            "p90_ms": p90_ms,
            "p95_ms": p95_ms,
            "p99_ms": p99_ms,
            "max_ms": max_ms,
            "response_codes": {
                "200": 400,
            },
        },
    }


class BuildShopCandidateTest(unittest.TestCase):

    def test_builds_metric_medians_from_three_rounds(
        self,
    ) -> None:
        module = load_candidate_module()

        rounds = [
            candidate_round(
                throughput_rps=205.0,
                mean_ms=7.0,
                median_ms=6.0,
                p90_ms=9,
                p95_ms=9,
                p99_ms=18,
                max_ms=50,
            ),
            candidate_round(
                throughput_rps=210.0,
                mean_ms=6.5,
                median_ms=6.0,
                p90_ms=8,
                p95_ms=8,
                p99_ms=16,
                max_ms=60,
            ),
            candidate_round(
                throughput_rps=208.0,
                mean_ms=6.8,
                median_ms=6.0,
                p90_ms=8,
                p95_ms=8,
                p99_ms=20,
                max_ms=55,
            ),
        ]

        candidate = module.build_candidate(rounds)
        metrics = candidate["metrics"]

        self.assertEqual(
            candidate["scenario"],
            "shop-query",
        )
        self.assertEqual(
            candidate["run_type"],
            "candidate",
        )
        self.assertEqual(
            candidate["round_count"],
            3,
        )
        self.assertEqual(
            candidate["candidate_method"],
            "median_of_three_rounds",
        )

        self.assertEqual(
            metrics["sample_count"],
            400,
        )
        self.assertEqual(
            metrics["error_count"],
            0,
        )
        self.assertEqual(
            metrics["error_rate"],
            0.0,
        )

        self.assertEqual(
            metrics["throughput_rps"],
            208.0,
        )
        self.assertEqual(
            metrics["mean_ms"],
            6.8,
        )
        self.assertEqual(
            metrics["median_ms"],
            6.0,
        )
        self.assertEqual(
            metrics["p90_ms"],
            8,
        )
        self.assertEqual(
            metrics["p95_ms"],
            8,
        )
        self.assertEqual(
            metrics["p99_ms"],
            18,
        )
        self.assertEqual(
            metrics["max_ms"],
            55,
        )


    def test_rejects_round_with_wrong_sample_count(
        self,
    ) -> None:
        module = load_candidate_module()

        rounds = [
            candidate_round(
                throughput_rps=205.0,
                mean_ms=7.0,
                median_ms=6.0,
                p90_ms=9,
                p95_ms=9,
                p99_ms=18,
                max_ms=50,
            ),
            candidate_round(
                throughput_rps=210.0,
                mean_ms=6.5,
                median_ms=6.0,
                p90_ms=8,
                p95_ms=8,
                p99_ms=16,
                max_ms=60,
            ),
            candidate_round(
                throughput_rps=208.0,
                mean_ms=6.8,
                median_ms=6.0,
                p90_ms=8,
                p95_ms=8,
                p99_ms=20,
                max_ms=55,
            ),
        ]

        rounds[1]["metrics"]["sample_count"] = 399

        with self.assertRaisesRegex(
            ValueError,
            "sample_count",
        ):
            module.build_candidate(rounds)


    def test_rejects_round_with_errors(
        self,
    ) -> None:
        module = load_candidate_module()

        rounds = [
            candidate_round(
                throughput_rps=205.0,
                mean_ms=7.0,
                median_ms=6.0,
                p90_ms=9,
                p95_ms=9,
                p99_ms=18,
                max_ms=50,
            ),
            candidate_round(
                throughput_rps=210.0,
                mean_ms=6.5,
                median_ms=6.0,
                p90_ms=8,
                p95_ms=8,
                p99_ms=16,
                max_ms=60,
            ),
            candidate_round(
                throughput_rps=208.0,
                mean_ms=6.8,
                median_ms=6.0,
                p90_ms=8,
                p95_ms=8,
                p99_ms=20,
                max_ms=55,
            ),
        ]

        rounds[2]["metrics"]["error_count"] = 1
        rounds[2]["metrics"]["success_count"] = 399
        rounds[2]["metrics"]["error_rate"] = 0.0025

        with self.assertRaisesRegex(
            ValueError,
            "error_count",
        ):
            module.build_candidate(rounds)

    def test_rejects_wrong_round_count(
        self,
    ) -> None:
        module = load_candidate_module()

        rounds = [
            candidate_round(
                throughput_rps=205.0,
                mean_ms=7.0,
                median_ms=6.0,
                p90_ms=9,
                p95_ms=9,
                p99_ms=18,
                max_ms=50,
            ),
            candidate_round(
                throughput_rps=210.0,
                mean_ms=6.5,
                median_ms=6.0,
                p90_ms=8,
                p95_ms=8,
                p99_ms=16,
                max_ms=60,
            ),
        ]

        with self.assertRaisesRegex(
            ValueError,
            "round_count",
        ):
            module.build_candidate(rounds)

    def test_rejects_wrong_scenario(
        self,
    ) -> None:
        module = load_candidate_module()

        rounds = [
            candidate_round(
                throughput_rps=205.0,
                mean_ms=7.0,
                median_ms=6.0,
                p90_ms=9,
                p95_ms=9,
                p99_ms=18,
                max_ms=50,
            ),
            candidate_round(
                throughput_rps=210.0,
                mean_ms=6.5,
                median_ms=6.0,
                p90_ms=8,
                p95_ms=8,
                p99_ms=16,
                max_ms=60,
            ),
            candidate_round(
                throughput_rps=208.0,
                mean_ms=6.8,
                median_ms=6.0,
                p90_ms=8,
                p95_ms=8,
                p99_ms=20,
                max_ms=55,
            ),
        ]

        rounds[0]["scenario"] = "other-scenario"

        with self.assertRaisesRegex(
            ValueError,
            "scenario",
        ):
            module.build_candidate(rounds)

    def test_rejects_wrong_run_type(
        self,
    ) -> None:
        module = load_candidate_module()

        rounds = [
            candidate_round(
                throughput_rps=205.0,
                mean_ms=7.0,
                median_ms=6.0,
                p90_ms=9,
                p95_ms=9,
                p99_ms=18,
                max_ms=50,
            ),
            candidate_round(
                throughput_rps=210.0,
                mean_ms=6.5,
                median_ms=6.0,
                p90_ms=8,
                p95_ms=8,
                p99_ms=16,
                max_ms=60,
            ),
            candidate_round(
                throughput_rps=208.0,
                mean_ms=6.8,
                median_ms=6.0,
                p90_ms=8,
                p95_ms=8,
                p99_ms=20,
                max_ms=55,
            ),
        ]

        rounds[1]["run_type"] = "baseline"

        with self.assertRaisesRegex(
            ValueError,
            "run_type",
        ):
            module.build_candidate(rounds)


if __name__ == "__main__":
    unittest.main()
