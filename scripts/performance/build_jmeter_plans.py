from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

REFERENCE_PLAN = (
    REPO_ROOT
    / "performance"
    / "jmeter"
    / "reference"
    / "seckill-plus-original.jmx"
)

PLAN_ROOT = (
    REPO_ROOT
    / "performance"
    / "jmeter"
    / "plans"
)


def set_properties(
    root: ET.Element,
    name: str,
    value: str,
) -> int:
    count = 0

    for element in root.iter():
        if element.attrib.get("name") != name:
            continue

        # JMeter的intProp、longProp会在加载JMX时
        # 立即执行数值解析，不能保存__P表达式。
        # 参数化属性必须序列化为stringProp，
        # 运行时再由JMeter解析属性值。
        if "${" in value:
            element.tag = "stringProp"

        element.text = value
        count += 1

    return count


def set_property_in(
    parent: ET.Element,
    name: str,
    value: str,
) -> None:
    matches = [
        element
        for element in parent.iter()
        if element.attrib.get("name")
        == name
    ]

    if not matches:
        raise ValueError(
            f"未找到属性{name}"
        )

    for element in matches:
        element.text = value


def first_element(
    root: ET.Element,
    tag: str,
) -> ET.Element:
    element = next(root.iter(tag), None)

    if element is None:
        raise ValueError(
            f"原始JMX中不存在{tag}"
        )

    return element


def configure_common(
    root: ET.Element,
    plan_name: str,
    loops_default: int,
) -> None:
    test_plan = first_element(
        root,
        "TestPlan",
    )
    test_plan.attrib["testname"] = plan_name

    replacements = {
        "HTTPSampler.protocol":
            "${__P(protocol,http)}",
        "HTTPSampler.domain":
            "${__P(host,127.0.0.1)}",
        "HTTPSampler.port":
            "${__P(port,8082)}",
        "ThreadGroup.num_threads":
            "${__P(threads,5)}",
        "ThreadGroup.ramp_time":
            "${__P(ramp_up,5)}",
        "LoopController.loops":
            (
                "${__P(loops,"
                f"{loops_default}"
                ")}"
            ),
        "LoopController.continue_forever":
            "false",
        "ThreadGroup.scheduler":
            "false",
        "ThreadGroup.duration":
            "0",
        "ThreadGroup.delay":
            "0",
    }

    for name, value in replacements.items():
        set_properties(
            root,
            name,
            value,
        )

    for listener in root.iter(
        "ResultCollector"
    ):
        listener.attrib["enabled"] = "false"


def set_or_add_string_property(
    parent: ET.Element,
    name: str,
    value: str,
) -> None:
    matches = [
        element
        for element in parent.iter()
        if element.attrib.get("name")
        == name
    ]

    if matches:
        for element in matches:
            element.text = value
        return

    property_element = ET.SubElement(
        parent,
        "stringProp",
        {
            "name": name,
        },
    )
    property_element.text = value


def configure_sampler_common(
    sampler: ET.Element,
) -> None:
    # protocol、domain和port由HTTP Request
    # Defaults统一提供，Sampler只配置超时。
    for name, value in {
        "HTTPSampler.connect_timeout":
            "${__P(connect_timeout_ms,3000)}",
        "HTTPSampler.response_timeout":
            "${__P(response_timeout_ms,10000)}",
    }.items():
        set_or_add_string_property(
            sampler,
            name,
            value,
        )


def find_arguments_collection(
    sampler: ET.Element,
) -> ET.Element:
    arguments = next(
        (
            element
            for element in sampler.iter(
                "elementProp"
            )
            if element.attrib.get("name")
            == "HTTPsampler.Arguments"
        ),
        None,
    )

    if arguments is None:
        raise ValueError(
            "未找到HTTPsampler.Arguments"
        )

    collection = next(
        arguments.iter("collectionProp"),
        None,
    )

    if collection is None:
        raise ValueError(
            "未找到Arguments.arguments"
        )

    return collection


def http_argument(
    name: str,
    value: str,
) -> ET.Element:
    element = ET.Element(
        "elementProp",
        {
            "name": name,
            "elementType": "HTTPArgument",
        },
    )

    ET.SubElement(
        element,
        "boolProp",
        {
            "name":
                "HTTPArgument.always_encode",
        },
    ).text = "false"

    ET.SubElement(
        element,
        "stringProp",
        {
            "name": "Argument.value",
        },
    ).text = value

    ET.SubElement(
        element,
        "stringProp",
        {
            "name": "Argument.metadata",
        },
    ).text = "="

    ET.SubElement(
        element,
        "boolProp",
        {
            "name":
                "HTTPArgument.use_equals",
        },
    ).text = "true"

    ET.SubElement(
        element,
        "stringProp",
        {
            "name": "Argument.name",
        },
    ).text = name

    return element


def build_seckill_plan(
    original_root: ET.Element,
) -> ET.Element:
    root = copy.deepcopy(original_root)

    configure_common(
        root,
        "Seckill Plus Performance Regression",
        loops_default=1,
    )

    sampler = first_element(
        root,
        "HTTPSamplerProxy",
    )
    sampler.attrib["testname"] = (
        "Seckill Plus Request"
    )

    set_property_in(
        sampler,
        "HTTPSampler.method",
        "POST",
    )
    set_property_in(
        sampler,
        "HTTPSampler.path",
        (
            "/voucher-order/"
            "seckill-plus/"
            "${__P(voucher_id,13)}"
        ),
    )
    configure_sampler_common(sampler)

    dataset = first_element(
        root,
        "CSVDataSet",
    )
    dataset.attrib["enabled"] = "true"

    set_property_in(
        dataset,
        "filename",
        (
            "${__P("
            "token_csv,"
            "performance/jmeter/data/"
            "seckill_tokens.csv"
            ")}"
        ),
    )
    set_property_in(
        dataset,
        "variableNames",
        "token",
    )
    set_property_in(
        dataset,
        "recycle",
        "false",
    )
    set_property_in(
        dataset,
        "stopThread",
        "true",
    )

    header_manager = first_element(
        root,
        "HeaderManager",
    )
    header_manager.attrib["enabled"] = "true"

    return root


def build_shop_plan(
    original_root: ET.Element,
) -> ET.Element:
    root = copy.deepcopy(original_root)

    configure_common(
        root,
        "Shop Query Performance Regression",
        loops_default=2,
    )

    sampler = first_element(
        root,
        "HTTPSamplerProxy",
    )
    sampler.attrib["testname"] = (
        "Shop Query Request"
    )

    set_property_in(
        sampler,
        "HTTPSampler.method",
        "GET",
    )
    set_property_in(
        sampler,
        "HTTPSampler.path",
        "/shop/of/type",
    )
    configure_sampler_common(sampler)

    collection = find_arguments_collection(
        sampler
    )

    for child in list(collection):
        collection.remove(child)

    collection.append(
        http_argument(
            "typeId",
            "${__P(type_id,1)}",
        )
    )
    collection.append(
        http_argument(
            "current",
            "${__P(current,1)}",
        )
    )

    for dataset in root.iter(
        "CSVDataSet"
    ):
        dataset.attrib["enabled"] = "false"

        set_or_add_string_property(
            dataset,
            "filename",
            "",
        )
        set_or_add_string_property(
            dataset,
            "variableNames",
            "",
        )

    for manager in root.iter(
        "HeaderManager"
    ):
        manager.attrib["enabled"] = "false"

    return root


def write_plan(
    root: ET.Element,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    ET.indent(
        root,
        space="  ",
    )

    ET.ElementTree(root).write(
        output_path,
        encoding="UTF-8",
        xml_declaration=True,
    )


def main() -> int:
    if not REFERENCE_PLAN.is_file():
        raise FileNotFoundError(
            "缺少本地参考JMX："
            f"{REFERENCE_PLAN}"
        )

    original_root = ET.parse(
        REFERENCE_PLAN
    ).getroot()

    write_plan(
        build_shop_plan(original_root),
        PLAN_ROOT / "shop-query.jmx",
    )

    write_plan(
        build_seckill_plan(original_root),
        (
            PLAN_ROOT
            / "seckill-plus-regression.jmx"
        ),
    )

    print(
        "SHOP_PLAN =",
        PLAN_ROOT / "shop-query.jmx",
    )
    print(
        "SECKILL_PLAN =",
        (
            PLAN_ROOT
            / "seckill-plus-regression.jmx"
        ),
    )
    print("PLAN_BUILD_COUNT = 2")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
