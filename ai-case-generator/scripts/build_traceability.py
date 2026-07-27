from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_ROOT = PROJECT_ROOT / "ai-case-generator"
OUTPUT_DIR = GENERATOR_ROOT / "output"

GENERATED_CASES = OUTPUT_DIR / "generated-cases.json"
SELECTED_CASES = OUTPUT_DIR / "selected-automation-cases.json"
TRACEABILITY_CSV = OUTPUT_DIR / "ai-case-traceability.csv"


MAPPINGS = {
    "AI-SECKILL-001": {
        "java_file": (
            "src/test/java/com/wanping/api/tests/"
            "VoucherOrderApiTest.java"
        ),
        "anchor": "seckillPlusWithoutToken(",
        "support_components": (
            "VoucherOrderClient|ResultAssertions"
        ),
        "implementation_status": "existing",
    },
    "AI-SECKILL-002": {
        "java_file": (
            "src/test/java/com/wanping/api/tests/"
            "VoucherOrderApiTest.java"
        ),
        "anchor": "seckillPlusWithRawVoucherId(",
        "support_components": (
            "VoucherOrderClient|ResultAssertions"
        ),
        "implementation_status": "existing",
    },
    "AI-SECKILL-003": {
        "java_file": (
            "src/test/java/com/wanping/api/tests/"
            "VoucherOrderApiTest.java"
        ),
        "anchor": "秒杀库存未初始化",
        "support_components": (
            "VoucherOrderClient|SeckillRedisSupport|"
            "ResultAssertions"
        ),
        "implementation_status": "existing",
    },
    "AI-SECKILL-004": {
        "java_file": (
            "src/test/java/com/wanping/api/tests/"
            "VoucherOrderApiTest.java"
        ),
        # 当前源码中成功下单核心请求位于约275行。
        "approximate_line": 275,
        "support_components": (
            "VoucherOrderClient|VoucherOrderRepository|"
            "SeckillRedisSupport|OrderAwaiter|"
            "AllureEvidenceSupport"
        ),
        "implementation_status": "existing",
    },
    "AI-SECKILL-005": {
        "java_file": (
            "src/test/java/com/wanping/api/tests/"
            "VoucherOrderApiTest.java"
        ),
        "anchor": "不能重复下单",
        "support_components": (
            "VoucherOrderClient|VoucherOrderRepository|"
            "SeckillRedisSupport|AllureEvidenceSupport"
        ),
        "implementation_status": "existing",
    },
    "AI-CONCURRENCY-001": {
        "java_file": (
            "src/test/java/com/wanping/api/tests/"
            "VoucherOversellConcurrencyTest.java"
        ),
        "anchor": "ExecutorService executor",
        "support_components": (
            "ConcurrentUserSessionProvider|VoucherOrderClient|"
            "VoucherOrderRepository|SeckillRedisSupport|"
            "AllureEvidenceSupport"
        ),
        "implementation_status": "existing",
    },
}


METHOD_PATTERN = re.compile(
    r"^\s*(?:public\s+|protected\s+|private\s+)?"
    r"(?:static\s+)?void\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
)

DISPLAY_NAME_PATTERN = re.compile(
    r'^\s*@DisplayName\("(.+)"\)\s*$'
)


def load_case_titles() -> Dict[str, str]:
    source = (
        SELECTED_CASES
        if SELECTED_CASES.exists()
        else GENERATED_CASES
    )

    data = json.loads(
        source.read_text(encoding="utf-8")
    )

    scenarios = data.get("scenarios", [])

    return {
        str(item.get("case_id")): str(
            item.get("title", "")
        )
        for item in scenarios
        if isinstance(item, dict)
    }


def find_anchor_line(
    lines: List[str],
    mapping: Dict[str, object],
) -> int:
    anchor = mapping.get("anchor")

    if isinstance(anchor, str):
        matches = [
            index
            for index, line in enumerate(lines)
            if anchor in line
        ]

        if not matches:
            raise RuntimeError(
                f"找不到代码锚点：{anchor}"
            )

        return matches[0]

    approximate_line = mapping.get(
        "approximate_line"
    )

    if isinstance(approximate_line, int):
        index = approximate_line - 1

        if not 0 <= index < len(lines):
            raise RuntimeError(
                f"近似行号越界：{approximate_line}"
            )

        return index

    raise RuntimeError(
        "映射必须提供anchor或approximate_line"
    )


def find_enclosing_method(
    lines: List[str],
    anchor_index: int,
) -> Tuple[Optional[str], Optional[str], int]:
    method_name: Optional[str] = None
    method_line = -1

    for index in range(anchor_index, -1, -1):
        match = METHOD_PATTERN.match(lines[index])

        if match:
            method_name = match.group(1)
            method_line = index
            break

    if method_name is None:
        return None, None, -1

    display_name: Optional[str] = None

    for index in range(method_line - 1, -1, -1):
        stripped = lines[index].strip()

        display_match = DISPLAY_NAME_PATTERN.match(
            lines[index]
        )

        if display_match:
            display_name = display_match.group(1)
            break

        if stripped.startswith(
            ("void ", "public ", "private ", "protected ")
        ):
            break

        if method_line - index > 12:
            break

    return (
        method_name,
        display_name,
        method_line + 1,
    )


def main() -> None:
    titles = load_case_titles()
    rows = []

    for case_id, mapping in MAPPINGS.items():
        relative_java_file = str(
            mapping["java_file"]
        )
        java_path = (
            PROJECT_ROOT / relative_java_file
        )

        if not java_path.exists():
            rows.append(
                {
                    "ai_case_id": case_id,
                    "ai_case_title": titles.get(
                        case_id, ""
                    ),
                    "implementation_status":
                        "java_file_missing",
                    "java_test_class":
                        java_path.stem,
                    "java_test_method": "",
                    "display_name": "",
                    "java_file":
                        relative_java_file,
                    "method_line": "",
                    "evidence_anchor": str(
                        mapping.get(
                            "anchor",
                            mapping.get(
                                "approximate_line",
                                "",
                            ),
                        )
                    ),
                    "support_components":
                        mapping[
                            "support_components"
                        ],
                    "execution_status": "not_run",
                    "execution_result": "",
                    "review_comment":
                        "Java测试文件不存在",
                }
            )
            continue

        lines = java_path.read_text(
            encoding="utf-8"
        ).splitlines()

        anchor_index = find_anchor_line(
            lines,
            mapping,
        )

        (
            method_name,
            display_name,
            method_line,
        ) = find_enclosing_method(
            lines,
            anchor_index,
        )

        status = (
            str(mapping["implementation_status"])
            if method_name
            else "needs_manual_mapping"
        )

        rows.append(
            {
                "ai_case_id": case_id,
                "ai_case_title": titles.get(
                    case_id, ""
                ),
                "implementation_status": status,
                "java_test_class": java_path.stem,
                "java_test_method":
                    method_name or "",
                "display_name":
                    display_name or "",
                "java_file":
                    relative_java_file,
                "method_line":
                    method_line if method_line >= 0 else "",
                "evidence_anchor":
                    str(
                        mapping.get(
                            "anchor",
                            mapping.get(
                                "approximate_line",
                                "",
                            ),
                        )
                    ),
                "support_components":
                    mapping["support_components"],
                "execution_status": "not_run",
                "execution_result": "",
                "review_comment": (
                    "已发现现有JUnit测试方法"
                    if method_name
                    else "未自动识别方法名，需人工确认"
                ),
            }
        )

    fieldnames = [
        "ai_case_id",
        "ai_case_title",
        "implementation_status",
        "java_test_class",
        "java_test_method",
        "display_name",
        "java_file",
        "method_line",
        "evidence_anchor",
        "support_components",
        "execution_status",
        "execution_result",
        "review_comment",
    ]

    with TRACEABILITY_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)

    mapped_count = sum(
        row["implementation_status"] == "existing"
        for row in rows
    )

    print(f"TOTAL_CASES={len(rows)}")
    print(f"MAPPED_CASES={mapped_count}")
    print(
        "NEEDS_MANUAL_MAPPING="
        f"{len(rows) - mapped_count}"
    )
    print(f"TRACEABILITY_FILE={TRACEABILITY_CSV}")

    for row in rows:
        print(
            row["ai_case_id"],
            "->",
            row["java_test_class"],
            "#",
            row["java_test_method"]
            or "<NOT_FOUND>",
        )


if __name__ == "__main__":
    main()
