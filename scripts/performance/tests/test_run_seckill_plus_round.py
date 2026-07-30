from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

SCRIPT_PATH = (
    REPO_ROOT
    / "scripts"
    / "performance"
    / "run_seckill_plus_round.sh"
)


class RunSeckillPlusRoundContractTest(
    unittest.TestCase,
):

    @classmethod
    def setUpClass(cls) -> None:
        if not SCRIPT_PATH.is_file():
            raise AssertionError(
                "缺少生产文件："
                "scripts/performance/"
                "run_seckill_plus_round.sh"
            )

        cls.script = SCRIPT_PATH.read_text(
            encoding="utf-8"
        )

        cls.normalized = re.sub(
            r"\\\s*\n\s*",
            " ",
            cls.script,
        )
        cls.normalized = re.sub(
            r"\s+",
            " ",
            cls.normalized,
        )

    def test_accepts_only_baseline_or_candidate(
        self,
    ) -> None:
        self.assertIn(
            'RUN_TYPE="${1:-}"',
            self.script,
        )
        self.assertRegex(
            self.script,
            re.compile(
                r'baseline\|candidate',
            ),
        )

    def test_uses_dedicated_voucher_and_load(
        self,
    ) -> None:
        required = [
            "VOUCHER_ID=900013",
            "USER_COUNT=20",
            "USER_ID_BASE=9000000000",
            "REDIS_DB=1",
            'RAMP_UP_SECONDS=2',
            'LOOPS_PER_THREAD=1',
        ]

        for value in required:
            with self.subTest(value=value):
                self.assertIn(
                    value,
                    self.script,
                )

    def test_prepares_same_voucher_and_users(
        self,
    ) -> None:
        required = [
            "prepare_seckill_plus_pilot.sh",
            '--voucher-id "$VOUCHER_ID"',
            '--user-count "$USER_COUNT"',
            '--user-id-base "$USER_ID_BASE"',
            "--apply",
            "ALLOW_DESTRUCTIVE_SECKILL_TEST=YES",
        ]

        for value in required:
            with self.subTest(value=value):
                self.assertIn(
                    value,
                    self.script,
                )

    def test_validates_token_sessions_and_auth(
        self,
    ) -> None:
        self.assertIn(
            "UNIQUE_TOKEN_COUNT",
            self.script,
        )
        self.assertIn(
            "login:token:",
            self.script,
        )
        self.assertIn(
            "/user/me",
            self.script,
        )
        self.assertIn(
            "AUTH_SMOKE_CHECK = PASS",
            self.script,
        )

    def test_runs_fixed_jmeter_load(
        self,
    ) -> None:
        required = [
            '-Jthreads="$USER_COUNT"',
            '-Jramp_up="$RAMP_UP_SECONDS"',
            '-Jloops="$LOOPS_PER_THREAD"',
            '-Jvoucher_id="$VOUCHER_ID"',
            '-Jtoken_csv="$TOKEN_CSV"',
        ]

        for value in required:
            with self.subTest(value=value):
                self.assertIn(
                    value,
                    self.script,
                )

    def test_checks_business_consistency(
        self,
    ) -> None:
        required = [
            '[[ "$DB_STOCK" == "0" ]]',
            '[[ "$ORDER_COUNT" == "$USER_COUNT" ]]',
            (
                '[[ "$DISTINCT_USER_COUNT" '
                '== "$USER_COUNT" ]]'
            ),
            (
                '[[ "$DUPLICATE_USER_COUNT" '
                '== "0" ]]'
            ),
            (
                '[[ "$REDIS_STOCK" '
                '== "0" ]]'
            ),
            (
                '[[ "$REDIS_ORDER_COUNT" '
                '== "$USER_COUNT" ]]'
            ),
            (
                '[[ "$REDIS_TRACE_COUNT" '
                '== "$USER_COUNT" ]]'
            ),
        ]

        for value in required:
            with self.subTest(value=value):
                self.assertIn(
                    value,
                    self.script,
                )

    def test_keeps_raw_artifacts_on_mount(
        self,
    ) -> None:
        self.assertIn(
            "/mnt/wanping-performance/runs",
            self.script,
        )
        self.assertIn(
            "performance/baselines/runs",
            self.script,
        )
        self.assertIn(
            "performance/candidates/runs",
            self.script,
        )

    def test_does_not_print_token_values(
        self,
    ) -> None:
        forbidden = [
            'cat "$TOKEN_CSV"',
            'echo "$token"',
            'printf \'%s\\n\' "$token"',
        ]

        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(
                    value,
                    self.script,
                )


if __name__ == "__main__":
    unittest.main()
