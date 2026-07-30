from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPORTS_DIR))

import check_quality_site


class QualitySiteCheckTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.site = Path(self.temp_dir.name)

        assets = self.site / "assets"
        assets.mkdir()

        reports = self.site / "reports"
        reports.mkdir()

        (assets / "style.css").write_text(
            "body {}\n",
            encoding="utf-8",
        )
        (reports / "detail.md").write_text(
            "# 明细\n",
            encoding="utf-8",
        )
        (
            self.site / "build-metadata.json"
        ).write_text(
            '{"overall_status":"PASS"}\n',
            encoding="utf-8",
        )
        (self.site / "index.html").write_text(
            (
                '<link rel="stylesheet" '
                'href="assets/style.css">'
                '<a href="reports/detail.md">'
                "明细</a>"
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_site_passes(self) -> None:
        self.assertEqual(
            check_quality_site.check_site(
                self.site
            ),
            [],
        )

    def test_missing_link_fails(self) -> None:
        (self.site / "index.html").write_text(
            '<a href="reports/missing.md">缺失</a>',
            encoding="utf-8",
        )

        errors = check_quality_site.check_site(
            self.site
        )

        self.assertTrue(
            any(
                "链接目标不存在" in error
                for error in errors
            )
        )

    def test_jtl_file_fails(self) -> None:
        (self.site / "result.jtl").write_text(
            "secret",
            encoding="utf-8",
        )

        errors = check_quality_site.check_site(
            self.site
        )

        self.assertTrue(
            any(
                "禁止发布的文件" in error
                for error in errors
            )
        )

    def test_bearer_credential_fails(self) -> None:
        (self.site / "index.html").write_text(
            (
                "Authorization: Bearer "
                "abc123456789secret"
            ),
            encoding="utf-8",
        )

        errors = check_quality_site.check_site(
            self.site
        )

        self.assertTrue(
            any(
                "疑似真实凭证" in error
                for error in errors
            )
        )

    def test_symlink_fails(self) -> None:
        source = self.site / "source.txt"
        source.write_text(
            "source",
            encoding="utf-8",
        )

        link = self.site / "link.txt"

        try:
            link.symlink_to(source)
        except OSError:
            self.skipTest(
                "当前平台不支持符号链接"
            )

        errors = check_quality_site.check_site(
            self.site
        )

        self.assertTrue(
            any(
                "符号链接" in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
