"""Helpers to make Pydantic JSON Schema acceptable to Ollama grammar parsing."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# These keywords commonly break Ollama/llama.cpp grammar compilation.
_UNSUPPORTED_KEYWORDS = {
    "description",
    "default",
    "examples",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "pattern",
    "format",
    "uniqueItems",
}


def ollama_compatible_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline $refs and strip keywords that break Ollama grammars."""
    defs = schema.get("$defs") or schema.get("definitions") or {}
    resolved = _resolve(deepcopy(schema), defs, set())
    resolved.pop("$defs", None)
    resolved.pop("definitions", None)
    return _strip_unsupported(resolved)


def _resolve(node: Any, defs: dict[str, Any], stack: set[str]) -> Any:
    if isinstance(node, list):
        return [_resolve(item, defs, stack) for item in node]
    if not isinstance(node, dict):
        return node

    if "$ref" in node:
        ref = str(node["$ref"])
        name = ref.rsplit("/", 1)[-1]
        if name in stack:
            raise ValueError(f"Circular schema reference: {ref}")
        if name not in defs:
            raise ValueError(f"Unresolved schema reference: {ref}")
        return _resolve(deepcopy(defs[name]), defs, stack | {name})

    if set(node.keys()) <= {"anyOf", "title", "default", "description"} and "anyOf" in node:
        options = node["anyOf"]
        non_null = [option for option in options if option != {"type": "null"}]
        if len(options) == 2 and len(non_null) == 1:
            return _resolve(deepcopy(non_null[0]), defs, stack)

    return {key: _resolve(value, defs, stack) for key, value in node.items()}


def _strip_unsupported(node: Any) -> Any:
    if isinstance(node, list):
        return [_strip_unsupported(item) for item in node]
    if not isinstance(node, dict):
        return node

    cleaned: dict[str, Any] = {}
    for key, value in node.items():
        # Preserve property names under "properties"; only strip schema annotations.
        if key in _UNSUPPORTED_KEYWORDS or key == "title":
            # "title" is an annotation on schema nodes, never a JSON Schema keyword we need.
            # Property names live as keys inside the "properties" object and are preserved below.
            continue
        if key == "properties" and isinstance(value, dict):
            cleaned[key] = {
                prop_name: _strip_unsupported(prop_schema)
                for prop_name, prop_schema in value.items()
            }
            continue
        cleaned[key] = _strip_unsupported(value)
    return cleaned
