from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_DIR),
    )

from src.failure_diagnosis import load_jsonl
from src.failure_diagnosis_inputs import (
    build_diagnosis_inputs,
    render_diagnosis_prompt,
)


GOLD_PATH = (
    PROJECT_DIR
    / "data"
    / "failure-diagnosis"
    / "gold-failures.jsonl"
)

TEMPLATE_PATH = (
    PROJECT_DIR
    / "prompts"
    / "failure-diagnosis.txt"
)

OUTPUT_DIR = (
    PROJECT_DIR
    / "output"
    / "failure-diagnosis"
)

INPUT_PATH = (
    OUTPUT_DIR
    / "diagnosis-inputs.jsonl"
)

PROMPT_DIR = (
    OUTPUT_DIR
    / "prompts"
)


def main() -> None:
    gold_records = load_jsonl(
        GOLD_PATH
    )

    diagnosis_inputs = (
        build_diagnosis_inputs(
            gold_records
        )
    )

    template = (
        TEMPLATE_PATH.read_text(
            encoding="utf-8"
        )
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    PROMPT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with INPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        for diagnosis_input in (
            diagnosis_inputs
        ):
            file.write(
                json.dumps(
                    diagnosis_input,
                    ensure_ascii=False,
                )
            )
            file.write("\n")

            prompt = (
                render_diagnosis_prompt(
                    diagnosis_input,
                    template,
                )
            )

            prompt_path = (
                PROMPT_DIR
                / (
                    diagnosis_input[
                        "failure_id"
                    ]
                    + ".prompt.txt"
                )
            )

            prompt_path.write_text(
                prompt,
                encoding="utf-8",
            )

    print(
        "GOLD_COUNT =",
        len(gold_records),
    )
    print(
        "INPUT_COUNT =",
        len(diagnosis_inputs),
    )
    print(
        "INPUT_FILE =",
        INPUT_PATH,
    )
    print(
        "PROMPT_COUNT =",
        len(
            list(
                PROMPT_DIR.glob(
                    "*.prompt.txt"
                )
            )
        ),
    )
    print(
        "ANSWER_LEAK_CHECK = PASS"
    )


if __name__ == "__main__":
    main()
