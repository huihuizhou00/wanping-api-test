from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

SCRIPT_PATH = (
    REPO_ROOT
    / "scripts"
    / "performance"
    / "prepare_seckill_plus_pilot.sh"
)


class PrepareSeckillPlusPilotScriptTest(
    unittest.TestCase,
):

    @classmethod
    def setUpClass(cls) -> None:
        if not SCRIPT_PATH.is_file():
            raise AssertionError(
                "缺少生产文件："
                "scripts/performance/"
                "prepare_seckill_plus_pilot.sh"
            )

        cls.script = SCRIPT_PATH.read_text(
            encoding="utf-8"
        )

    def test_defaults_to_dry_run_and_requires_apply_gate(
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
            "ALLOW_DESTRUCTIVE_SECKILL_TEST",
            self.script,
        )
        self.assertIn(
            '!= "YES"',
            self.script,
        )

    def test_uses_high_test_user_id_range(
        self,
    ) -> None:
        self.assertIn(
            "USER_ID_BASE=9000000000",
            self.script,
        )
        self.assertIn(
            "USER_ID_MIN",
            self.script,
        )
        self.assertIn(
            "USER_ID_MAX",
            self.script,
        )

    def test_never_uses_blocking_redis_keys_command(
        self,
    ) -> None:
        blocking_pattern = re.compile(
            r"redis-cli[^\n]*\bkeys\b",
            re.IGNORECASE,
        )

        self.assertIsNone(
            blocking_pattern.search(
                self.script
            )
        )

    def test_all_database_deletes_are_scoped(
        self,
    ) -> None:
        scoped_deletes = [
            (
                "DELETE FROM tb_voucher_order "
                "WHERE voucher_id = ${VOUCHER_ID} "
                "AND user_id BETWEEN "
                "${USER_ID_MIN} AND ${USER_ID_MAX};"
            ),
            (
                "DELETE FROM tb_voucher_reconcile_log "
                "WHERE voucher_id = ${VOUCHER_ID} "
                "AND user_id BETWEEN "
                "${USER_ID_MIN} AND ${USER_ID_MAX};"
            ),
            (
                "DELETE FROM tb_order_create_verify_task "
                "WHERE voucher_id = ${VOUCHER_ID} "
                "AND user_id BETWEEN "
                "${USER_ID_MIN} AND ${USER_ID_MAX};"
            ),
            (
                "DELETE FROM tb_order_create_recovery_task "
                "WHERE voucher_id = ${VOUCHER_ID} "
                "AND user_id BETWEEN "
                "${USER_ID_MIN} AND ${USER_ID_MAX};"
            ),
            (
                "DELETE FROM tb_seckill_reconcile_task "
                "WHERE voucher_id = ${VOUCHER_ID} "
                "AND user_id BETWEEN "
                "${USER_ID_MIN} AND ${USER_ID_MAX};"
            ),
        ]

        for statement in scoped_deletes:
            with self.subTest(
                statement=statement
            ):
                self.assertIn(
                    statement,
                    self.script,
                )

        self.assertNotIn(
            "DELETE FROM "
            "tb_order_create_verify_task;",
            self.script,
        )

    def test_does_not_change_activity_time(
        self,
    ) -> None:
        self.assertNotRegex(
            self.script,
            re.compile(
                r"UPDATE\s+tb_seckill_voucher"
                r"[\s\S]{0,200}"
                r"(begin_time|end_time)",
                re.IGNORECASE,
            ),
        )

    def test_writes_token_csv_to_ignored_directory(
        self,
    ) -> None:
        self.assertIn(
            "performance/jmeter/data/"
            "seckill-pilot-tokens.csv",
            self.script,
        )
        self.assertIn(
            "chmod 600",
            self.script,
        )



    def test_counters_use_arithmetic_expansion(
        self,
    ) -> None:
        broken_outside_counter = re.compile(
            r"OUTSIDE_REDIS_USERS=\$\(\s*"
            r"\(OUTSIDE_REDIS_USERS \+ 1\)\s*"
            r"\)",
            re.MULTILINE,
        )

        self.assertNotRegex(
            self.script,
            broken_outside_counter,
        )

        # OUTSIDE_REDIS_USERS 现在由 Redis Lua
        # 直接返回 invalid_count，不再由 Bash 累加。
        self.assertIn(
            'OUTSIDE_REDIS_USERS="$(',
            self.script,
        )
        self.assertIn(
            "return invalid_count",
            self.script,
        )

        # Token 会话数量仍由 Bash 循环统计。
        self.assertIn(
            "TOKEN_SESSION_COUNT="
            "$((TOKEN_SESSION_COUNT + 1))",
            self.script,
        )


    def test_redis_order_members_are_validated_inside_lua(
        self,
    ) -> None:
        self.assertNotIn(
            "mapfile -t scan_result",
            self.script,
        )

        # 允许 redis.call 和 SSCAN 分行书写，
        # 不把测试绑定到具体排版格式。
        self.assertRegex(
            self.script,
            re.compile(
                r'redis\.call\(\s*"SSCAN"',
                re.MULTILINE,
            ),
        )

        self.assertIn(
            'member == ""',
            self.script,
        )
        self.assertIn(
            "tonumber(",
            self.script,
        )
        self.assertIn(
            "numeric_user_id < minimum_user_id",
            self.script,
        )
        self.assertIn(
            "numeric_user_id > maximum_user_id",
            self.script,
        )
        self.assertIn(
            "return invalid_count",
            self.script,
        )

if __name__ == "__main__":
    unittest.main()
