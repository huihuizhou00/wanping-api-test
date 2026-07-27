from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class ModelSettings:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float


@dataclass(frozen=True)
class GeneratorSettings:
    total_cases: int
    temperature: float
    max_tokens: int
    max_retries: int
    module_quotas: Dict[str, int]


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"YAML根节点必须是对象: {path}")
    return data


def load_model_settings(project_dir: Path) -> ModelSettings:
    load_dotenv(project_dir / ".env")
    return ModelSettings(
        base_url=os.getenv("AI_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/"),
        api_key=os.getenv("AI_API_KEY", "ollama"),
        model=os.getenv("AI_MODEL", "qwen2.5:7b"),
        timeout_seconds=float(os.getenv("AI_TIMEOUT_SECONDS", "180")),
    )


def load_generator_settings(path: Path) -> GeneratorSettings:
    raw = load_yaml(path)
    quotas = raw.get("module_quotas")
    if not isinstance(quotas, dict) or not quotas:
        raise ValueError("generator.yaml缺少module_quotas")
    quotas = {str(key): int(value) for key, value in quotas.items()}
    total_cases = int(raw.get("total_cases", sum(quotas.values())))
    if sum(quotas.values()) != total_cases:
        raise ValueError("module_quotas之和必须等于total_cases")
    return GeneratorSettings(
        total_cases=total_cases,
        temperature=float(raw.get("temperature", 0.2)),
        max_tokens=int(raw.get("max_tokens", 12000)),
        max_retries=int(raw.get("max_retries", 2)),
        module_quotas=quotas,
    )
