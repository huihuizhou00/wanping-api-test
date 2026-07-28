from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.failure_diagnosis import evaluate_diagnoses, load_json, load_jsonl
from src.failure_diagnosis_runner import (
    generate_diagnoses,
    render_evaluation_markdown,
)
from src.model_client import OpenAICompatibleClient
from src.settings import load_generator_settings, load_model_settings


SYSTEM_PROMPT = (
    "你只能输出符合JSON Schema的合法JSON对象。"
    "你只能依据用户提供的可观察事实进行故障诊断，"
    "不得引用未提供的Gold答案、人工根因或修复结论。"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="调用OpenAI Compatible模型生成并评估万评失败诊断"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/failure-diagnosis"),
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
    )
    return parser.parse_args()


def write_jsonl(path: Path, records) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    output_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else PROJECT_DIR / args.output_dir
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    gold_path = (
        PROJECT_DIR / "data/failure-diagnosis/gold-failures.jsonl"
    )
    input_path = output_dir / "diagnosis-inputs.jsonl"
    prompt_path = PROJECT_DIR / "prompts/failure-diagnosis.txt"
    schema_path = PROJECT_DIR / "schemas/failure-diagnosis.schema.json"
    raw_dir = output_dir / "raw"

    gold_records = load_jsonl(gold_path)
    diagnosis_inputs = load_jsonl(input_path)
    template = prompt_path.read_text(encoding="utf-8")
    schema = load_json(schema_path)
    model = load_model_settings(PROJECT_DIR)
    generator = load_generator_settings(PROJECT_DIR / "config/generator.yaml")

    client = OpenAICompatibleClient(
        model,
        generator,
        schema,
        schema_name="wanping_failure_diagnosis",
        system_prompt=SYSTEM_PROMPT,
    )

    predictions, events = generate_diagnoses(
        diagnosis_inputs,
        template,
        schema,
        client,
        raw_dir,
        max_retries=args.max_retries,
    )

    prediction_path = output_dir / "ai-diagnoses.jsonl"
    event_path = output_dir / "generation-events.json"
    evaluation_json_path = output_dir / "diagnosis-evaluation.json"
    evaluation_md_path = output_dir / "diagnosis-evaluation.md"

    write_jsonl(prediction_path, predictions)
    event_path.write_text(
        json.dumps(events, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = evaluate_diagnoses(gold_records, predictions, schema)
    summary["model"] = model.model

    evaluation_json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    evaluation_md_path.write_text(
        render_evaluation_markdown(summary, model.model),
        encoding="utf-8",
    )

    total = summary["total_cases"]
    print("MODEL =", model.model)
    print("DIAGNOSIS_COUNT =", len(predictions))
    print(
        "SCHEMA_PASS =",
        f"{summary['schema_pass_count']}/{total}",
    )
    print(
        "FAILURE_LAYER_ACCURACY =",
        f"{summary['failure_layer_match_count']}/{total}",
        f"({summary['failure_layer_accuracy']:.4f})",
    )
    print(
        "ROOT_CAUSE_TAG_ACCURACY =",
        f"{summary['root_cause_tag_match_count']}/{total}",
        f"({summary['root_cause_tag_accuracy']:.4f})",
    )
    print(
        "FULL_MATCH_RATE =",
        f"{summary['full_match_count']}/{total}",
        f"({summary['full_match_rate']:.4f})",
    )
    print(
        "EVIDENCE_KEYWORD_RECALL =",
        f"{summary['average_evidence_keyword_recall']:.4f}",
    )
    print("PREDICTION_FILE =", prediction_path)
    print("EVALUATION_JSON =", evaluation_json_path)
    print("EVALUATION_MD =", evaluation_md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
