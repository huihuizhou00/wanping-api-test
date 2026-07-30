from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

SCRIPT_PATH = (
    REPO_ROOT
    / "scripts"
    / "performance"
    / "bootstrap_seckill_test_voucher.sh"
)


class BootstrapSeckillTestVoucherTest(
    unittest.TestCase,
):

    @classmethod
    def setUpClass(cls) -> None:
        if not SCRIPT_PATH.is_file():
            raise AssertionError(
                "缺少生产文件："
                "scripts/performance/"
                "bootstrap_seckill_test_voucher.sh"
            )

        cls.script = SCRIPT_PATH.read_text(
            encoding="utf-8"
        )

    def test_defaults_to_dry_run(
        self,
    ) -> None:
        self.assertIn(
            "DRY_RUN=1",
            self.script,
        )
        self.assertIn(
            "--apply",
            self.script,
        )
        self.assertIn(
            "ALLOW_TEST_VOUCHER_BOOTSTRAP",
            self.script,
        )

    def test_uses_dedicated_high_voucher_id(
        self,
    ) -> None:
        self.assertIn(
            "VOUCHER_ID=900013",
            self.script,
        )
        self.assertIn(
            "[PERF-ONLY] Seckill Plus",
            self.script,
        )

    def test_never_deletes_business_data(
        self,
    ) -> None:
        self.assertNotIn(
            "DELETE FROM",
            self.script.upper(),
        )

    def test_guards_existing_id_collision(
        self,
    ) -> None:
        self.assertIn(
            "existing voucher id is not owned "
            "by performance test",
            self.script,
        )

    def test_bootstraps_both_voucher_tables(
        self,
    ) -> None:
        self.assertIn(
            "INSERT INTO tb_voucher",
            self.script,
        )
        self.assertIn(
            "INSERT INTO tb_seckill_voucher",
            self.script,
        )
        self.assertIn(
            "START TRANSACTION",
            self.script,
        )
        self.assertIn(
            "COMMIT",
            self.script,
        )


if __name__ == "__main__":
    unittest.main()
