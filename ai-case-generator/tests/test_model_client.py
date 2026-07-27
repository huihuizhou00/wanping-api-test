import json
import unittest
from pathlib import Path

from src.model_client import build_response_format


ROOT = Path(__file__).resolve().parents[1]


class StructuredOutputRequestTest(unittest.TestCase):
    def test_response_format_contains_full_json_schema(self):
        schema = json.loads(
            (ROOT / "schemas/test-case-batch.schema.json").read_text(
                encoding="utf-8"
            )
        )

        response_format = build_response_format(schema)

        self.assertEqual("json_schema", response_format["type"])
        contract = response_format["json_schema"]
        self.assertEqual("wanping_test_case_batch", contract["name"])
        self.assertNotIn("strict", contract)
        self.assertEqual(schema, contract["schema"])

    def test_response_format_supports_custom_schema_name(self):
        schema = {"type": "object"}

        response_format = build_response_format(
            schema,
            "wanping_failure_diagnosis",
        )

        self.assertEqual(
            "wanping_failure_diagnosis",
            response_format["json_schema"]["name"],
        )
        self.assertEqual(
            schema,
            response_format["json_schema"]["schema"],
        )


if __name__ == "__main__":
    unittest.main()
