from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from .settings import GeneratorSettings, ModelSettings


class ModelOutputError(RuntimeError):
    pass


def build_response_format(schema: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "wanping_test_case_batch",
            "schema": schema,
        },
    }


class OpenAICompatibleClient:
    def __init__(
        self,
        model: ModelSettings,
        generator: GeneratorSettings,
        schema: Dict[str, Any],
    ) -> None:
        self._model = model
        self._generator = generator
        self._schema = schema
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "缺少openai依赖，请先执行pip install -r requirements.txt"
            ) from exc
        self._client = OpenAI(
            base_url=model.base_url,
            api_key=model.api_key,
            timeout=model.timeout_seconds,
        )

    def generate(self, prompt: str) -> Dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self._model.model,
            temperature=self._generator.temperature,
            max_tokens=self._generator.max_tokens,
            response_format=build_response_format(self._schema),
            messages=[
                {
                    "role": "system",
                    "content": "你只能输出合法JSON，且只能使用用户提供的已验证业务规则。",
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ModelOutputError("模型返回空内容")
        return extract_json_object(content)


def extract_json_object(content: str) -> Dict[str, Any]:
    text = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ModelOutputError("模型输出中未找到JSON对象")
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ModelOutputError(f"模型输出不是合法JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ModelOutputError("模型输出根节点必须是JSON对象")
    return value


def ensure_module_batch(batch: Dict[str, Any], module: str, expected_count: int) -> List[str]:
    errors: List[str] = []
    scenarios = batch.get("scenarios")
    if not isinstance(scenarios, list):
        return ["顶层scenarios必须是数组"]
    if len(scenarios) != expected_count:
        errors.append(f"模块{module}要求{expected_count}条，实际{len(scenarios)}条")
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            errors.append(f"scenarios[{index}]必须是对象")
            continue
        if scenario.get("module") != module:
            errors.append(
                f"scenarios[{index}].module应为{module}，实际为{scenario.get('module')}"
            )
    return errors
