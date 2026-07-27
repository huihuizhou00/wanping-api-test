from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from .validators import ValidationReport


OUTPUT_FIELDS = [
    "case_id", "module", "title", "priority", "test_type", "endpoint", "method",
    "preconditions", "request", "expected_http_status", "expected_business_result",
    "redis_assertions", "mysql_assertions", "risk_tags", "source_rules",
    "schema_valid", "business_valid", "validation_errors",
    "business_review_status", "review_comment",
]


def enrich_scenarios(batch: Dict[str, Any], report: ValidationReport) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for scenario in batch.get("scenarios", []):
        item = dict(scenario)
        case_id = str(item.get("case_id", ""))
        schema_errors = report.schema_case_errors.get(case_id, [])
        business_errors = report.case_errors.get(case_id, [])
        item["schema_valid"] = not schema_errors
        item["business_valid"] = not business_errors
        item["validation_errors"] = schema_errors + business_errors
        item["business_review_status"] = "pending"
        item["review_comment"] = ""
        enriched.append(item)
    return enriched


def write_outputs(output_dir: Path, batch: Dict[str, Any], report: ValidationReport) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    enriched = enrich_scenarios(batch, report)

    (output_dir / "generated-cases.json").write_text(
        json.dumps({"scenarios": enriched}, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with (output_dir / "generated-cases.jsonl").open("w", encoding="utf-8") as handle:
        for item in enriched:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    with (output_dir / "generated-cases.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for item in enriched:
            row: Dict[str, Any] = {}
            for field in OUTPUT_FIELDS:
                value = item.get(field)
                if isinstance(value, (dict, list)):
                    row[field] = json.dumps(value, ensure_ascii=False)
                else:
                    row[field] = value
            writer.writerow(row)

    total = len(enriched)
    schema_pass = sum(1 for item in enriched if item["schema_valid"])
    business_pass = sum(1 for item in enriched if item["business_valid"])
    summary = {
        "total_cases": total,
        "schema_pass_count": schema_pass,
        "schema_pass_rate": round(schema_pass / total, 4) if total else 0,
        "business_pass_count": business_pass,
        "business_pass_rate": round(business_pass / total, 4) if total else 0,
        "global_errors": report.global_errors,
    }
    (output_dir / "validation-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
