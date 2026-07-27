from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Tuple


NormalizationChange = Dict[str, Any]


def normalize_structural_defaults(
    batch: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[NormalizationChange]]:
    """Fill deterministic structural defaults without inventing business facts.

    The current schema requires request.body to exist for every scenario. For
    endpoints without a request body, the only valid value is ``null``. Local
    models may omit this field even when explicitly instructed, so we fill
    only this non-semantic default and leave endpoint, method, status, rules,
    assertions, and request parameters untouched.
    """

    normalized = deepcopy(batch)
    changes: List[NormalizationChange] = []

    scenarios = normalized.get("scenarios")
    if not isinstance(scenarios, list):
        return normalized, changes

    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue

        request = scenario.get("request")
        if not isinstance(request, dict) or "body" in request:
            continue

        request["body"] = None
        changes.append(
            {
                "case_id": str(scenario.get("case_id", "")),
                "path": "request.body",
                "action": "filled_default",
                "value": None,
            }
        )

    return normalized, changes
