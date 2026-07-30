from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN_ROOT = (
    REPO_ROOT
    / "performance"
    / "jmeter"
    / "plans"
)


def property_values(
    root: ET.Element,
    property_name: str,
) -> list[str]:
    return [
        (element.text or "").strip()
        for element in root.iter()
        if element.attrib.get("name")
        == property_name
    ]


def first_sampler(
    root: ET.Element,
) -> ET.Element:
    sampler = next(
        root.iter("HTTPSamplerProxy"),
        None,
    )

    if sampler is None:
        raise AssertionError(
            "JMX中不存在HTTPSamplerProxy"
        )

    return sampler


def first_element(
    root: ET.Element,
    tag: str,
) -> ET.Element:
    element = next(root.iter(tag), None)

    if element is None:
        raise AssertionError(
            f"JMX中不存在{tag}"
        )

    return element


def sampler_arguments(
    sampler: ET.Element,
) -> dict[str, str]:
    result: dict[str, str] = {}

    for element in sampler.iter(
        "elementProp"
    ):
        names = property_values(
            element,
            "Argument.name",
        )

        values = property_values(
            element,
            "Argument.value",
        )

        if names and values:
            result[names[0]] = values[0]

    return result


class JMeterPlanContractTest(
    unittest.TestCase
):
    def load_plan(
        self,
        filename: str,
    ) -> tuple[Path, ET.Element]:
        path = PLAN_ROOT / filename

        self.assertTrue(
            path.is_file(),
            f"缺少JMeter计划：{path}",
        )

        return path, ET.parse(path).getroot()

    def assert_common_defaults(
        self,
        root: ET.Element,
    ) -> None:
        self.assertIn(
            "${__P(protocol,http)}",
            property_values(
                root,
                "HTTPSampler.protocol",
            ),
        )
        self.assertIn(
            "${__P(host,127.0.0.1)}",
            property_values(
                root,
                "HTTPSampler.domain",
            ),
        )
        self.assertIn(
            "${__P(port,8082)}",
            property_values(
                root,
                "HTTPSampler.port",
            ),
        )

        self.assert_parameter_properties_are_strings(
            root
        )

    def assert_parameter_properties_are_strings(
        self,
        root: ET.Element,
    ) -> None:
        parameter_names = {
            "ThreadGroup.num_threads",
            "ThreadGroup.ramp_time",
            "LoopController.loops",
        }

        for property_name in parameter_names:
            matches = [
                element
                for element in root.iter()
                if element.attrib.get("name")
                == property_name
            ]

            self.assertTrue(
                matches,
                f"缺少参数属性：{property_name}",
            )

            for element in matches:
                self.assertEqual(
                    element.tag,
                    "stringProp",
                    (
                        f"{property_name}必须使用"
                        "stringProp承载__P表达式，"
                        f"实际为{element.tag}"
                    ),
                )

    def assert_sampler_timeouts(
        self,
        sampler: ET.Element,
    ) -> None:
        self.assertIn(
            "${__P(connect_timeout_ms,3000)}",
            property_values(
                sampler,
                "HTTPSampler.connect_timeout",
            ),
        )
        self.assertIn(
            "${__P(response_timeout_ms,10000)}",
            property_values(
                sampler,
                "HTTPSampler.response_timeout",
            ),
        )

    def test_shop_query_plan_is_parameterized(
        self,
    ) -> None:
        path, root = self.load_plan(
            "shop-query.jmx"
        )

        self.assert_common_defaults(root)

        raw_text = path.read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "/tmp/seckill_tokens.csv",
            raw_text,
        )

        dataset = first_element(
            root,
            "CSVDataSet",
        )

        self.assertEqual(
            dataset.attrib.get("enabled"),
            "false",
        )

        self.assertIn(
            "${__P(threads,5)}",
            property_values(
                root,
                "ThreadGroup.num_threads",
            ),
        )
        self.assertIn(
            "${__P(ramp_up,5)}",
            property_values(
                root,
                "ThreadGroup.ramp_time",
            ),
        )
        self.assertIn(
            "${__P(loops,2)}",
            property_values(
                root,
                "LoopController.loops",
            ),
        )

        sampler = first_sampler(root)

        self.assert_sampler_timeouts(
            sampler
        )

        self.assertIn(
            "GET",
            property_values(
                sampler,
                "HTTPSampler.method",
            ),
        )
        self.assertIn(
            "/shop/of/type",
            property_values(
                sampler,
                "HTTPSampler.path",
            ),
        )

        arguments = sampler_arguments(
            sampler
        )

        self.assertEqual(
            arguments["typeId"],
            "${__P(type_id,1)}",
        )
        self.assertEqual(
            arguments["current"],
            "${__P(current,1)}",
        )

        self.assertGreaterEqual(
            len(
                list(
                    root.iter(
                        "ResponseAssertion"
                    )
                )
            ),
            1,
        )
        self.assertGreaterEqual(
            len(
                list(
                    root.iter(
                        "JSONPathAssertion"
                    )
                )
            ),
            1,
        )

    def test_seckill_plan_uses_unique_tokens(
        self,
    ) -> None:
        path, root = self.load_plan(
            "seckill-plus-regression.jmx"
        )

        self.assert_common_defaults(root)

        self.assertIn(
            "${__P(threads,5)}",
            property_values(
                root,
                "ThreadGroup.num_threads",
            ),
        )
        self.assertIn(
            "${__P(ramp_up,5)}",
            property_values(
                root,
                "ThreadGroup.ramp_time",
            ),
        )
        self.assertIn(
            "${__P(loops,1)}",
            property_values(
                root,
                "LoopController.loops",
            ),
        )

        sampler = first_sampler(root)

        self.assert_sampler_timeouts(
            sampler
        )

        self.assertIn(
            "POST",
            property_values(
                sampler,
                "HTTPSampler.method",
            ),
        )
        self.assertIn(
            (
                "/voucher-order/"
                "seckill-plus/"
                "${__P(voucher_id,13)}"
            ),
            property_values(
                sampler,
                "HTTPSampler.path",
            ),
        )

        dataset = first_element(
            root,
            "CSVDataSet",
        )

        self.assertEqual(
            dataset.attrib.get("enabled"),
            "true",
        )
        self.assertIn(
            (
                "${__P("
                "token_csv,"
                "performance/jmeter/data/"
                "seckill_tokens.csv"
                ")}"
            ),
            property_values(
                dataset,
                "filename",
            ),
        )
        self.assertIn(
            "false",
            property_values(
                dataset,
                "recycle",
            ),
        )
        self.assertIn(
            "true",
            property_values(
                dataset,
                "stopThread",
            ),
        )

        header_names = property_values(
            root,
            "Header.name",
        )
        header_values = property_values(
            root,
            "Header.value",
        )

        self.assertIn(
            "authorization",
            [
                name.lower()
                for name in header_names
            ],
        )
        self.assertIn(
            "${token}",
            header_values,
        )

        raw_text = path.read_text(
            encoding="utf-8"
        )

        for forbidden in [
            "<stringProp "
            'name="ThreadGroup.num_threads">'
            "4000</stringProp>",
            "localhost",
            (
                "<stringProp "
                'name="HTTPSampler.port">'
                "8081</stringProp>"
            ),
            "/tmp/seckill_tokens.csv",
        ]:
            self.assertNotIn(
                forbidden,
                raw_text,
            )


if __name__ == "__main__":
    unittest.main()
