from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

MODULE_PATH = (
    REPO_ROOT
    / "scripts"
    / "performance"
    / "extract_jmeter_metrics.py"
)

FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "sample-result.jtl"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "extract_jmeter_metrics",
        MODULE_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "无法加载指标提取模块"
        )

    module = importlib.util.module_from_spec(
        spec
    )
    spec.loader.exec_module(module)

    return module


class ExtractJMeterMetricsTest(
    unittest.TestCase
):
    def test_extracts_core_metrics(
        self,
    ) -> None:
        module = load_module()

        rows = module.load_rows(
            FIXTURE_PATH
        )
        metrics = module.extract_metrics(
            rows
        )

        self.assertEqual(
            metrics["sample_count"],
            4,
        )
        self.assertEqual(
            metrics["success_count"],
            3,
        )
        self.assertEqual(
            metrics["error_count"],
            1,
        )
        self.assertEqual(
            metrics["error_rate"],
            0.25,
        )
        self.assertEqual(
            metrics["mean_ms"],
            25.0,
        )
        self.assertEqual(
            metrics["p95_ms"],
            40,
        )
        self.assertEqual(
            metrics["p99_ms"],
            40,
        )
        self.assertEqual(
            metrics["response_codes"],
            {
                "200": 3,
                "500": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
