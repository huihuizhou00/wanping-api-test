#!/usr/bin/env python3
"""检查静态质量站点的完整性和敏感信息。"""

from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


REQUIRED_FILES = (
    "index.html",
    "assets/style.css",
    "build-metadata.json",
)

TEXT_SUFFIXES = {
    ".html",
    ".css",
    ".md",
    ".json",
    ".txt",
    ".csv",
}

CREDENTIAL_PATTERNS = (
    re.compile(
        r"authorization\s*:\s*bearer\s+\S+",
        re.IGNORECASE,
    ),
    re.compile(
        (
            r"\b(password|api_key|secret|"
            r"access_token|refresh_token)"
            r"\s*[:=]\s*[\"']?"
            r"[A-Za-z0-9_./+=-]{8,}"
        ),
        re.IGNORECASE,
    ),
)


class LinkCollector(HTMLParser):

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        for name, value in attrs:
            if (
                name in {"href", "src"}
                and value
            ):
                self.links.append(value)


def is_forbidden_file(path: Path) -> bool:
    name = path.name.lower()

    if path.suffix.lower() == ".jtl":
        return True

    if name in {
        "jmeter.log",
        "console.log",
        ".env",
    }:
        return True

    if name.startswith(".env."):
        return True

    if path.suffix.lower() in {
        ".pem",
        ".key",
    }:
        return True

    if (
        "token" in name
        and path.suffix.lower() == ".csv"
    ):
        return True

    return False


def check_local_links(
    site_root: Path,
    html_file: Path,
) -> list[str]:
    errors = []

    parser = LinkCollector()
    parser.feed(
        html_file.read_text(
            encoding="utf-8"
        )
    )

    for raw_link in parser.links:
        parsed = urlsplit(raw_link)

        if parsed.scheme in {
            "http",
            "https",
            "mailto",
        }:
            continue

        if parsed.scheme:
            errors.append(
                f"{html_file}: 非法链接协议："
                f"{raw_link}"
            )
            continue

        if not parsed.path:
            continue

        relative = Path(
            unquote(parsed.path)
        )

        if relative.is_absolute():
            errors.append(
                f"{html_file}: 站内链接不能是"
                f"绝对路径：{raw_link}"
            )
            continue

        target = (
            html_file.parent / relative
        ).resolve()

        try:
            target.relative_to(site_root)
        except ValueError:
            errors.append(
                f"{html_file}: 链接越过站点目录："
                f"{raw_link}"
            )
            continue

        if not target.is_file():
            errors.append(
                f"{html_file}: 链接目标不存在："
                f"{raw_link}"
            )

    return errors


def check_site(
    site_directory: Path,
) -> list[str]:
    errors = []

    try:
        root = site_directory.resolve(
            strict=True
        )
    except FileNotFoundError:
        return [
            f"站点目录不存在：{site_directory}"
        ]

    if not root.is_dir():
        return [
            f"站点路径不是目录：{root}"
        ]

    for relative in REQUIRED_FILES:
        path = root / relative

        if not path.is_file():
            errors.append(
                f"缺少必需文件：{relative}"
            )

    for path in root.rglob("*"):
        if path.is_symlink():
            errors.append(
                f"站点中存在符号链接：{path}"
            )
            continue

        if not path.is_file():
            continue

        if is_forbidden_file(path):
            errors.append(
                f"发现禁止发布的文件：{path}"
            )

        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue

        try:
            text = path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            errors.append(
                f"文本文件不是UTF-8：{path}"
            )
            continue

        for pattern in CREDENTIAL_PATTERNS:
            if pattern.search(text):
                errors.append(
                    f"发现疑似真实凭证：{path}"
                )
                break

        if path.suffix.lower() == ".html":
            errors.extend(
                check_local_links(
                    root,
                    path,
                )
            )

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "检查万评静态质量站点"
        )
    )
    parser.add_argument(
        "--site",
        required=True,
        type=Path,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = check_site(args.site)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("QUALITY_SITE_CHECK = PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
