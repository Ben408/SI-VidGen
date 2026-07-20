from pydantic import BaseModel, Field

from src.llm.schema import ollama_compatible_schema
from src.scriptgen.script_builder import ScriptDraft


class NestedItem(BaseModel):
    label: str
    note: str | None = None


class NestedResponse(BaseModel):
    title: str
    items: list[NestedItem] = Field(min_length=1)


def test_ollama_schema_inlines_refs_and_drops_null_unions() -> None:
    schema = ollama_compatible_schema(NestedResponse.model_json_schema())

    assert "$defs" not in schema
    assert "$ref" not in str(schema)
    item_schema = schema["properties"]["items"]["items"]
    assert item_schema["properties"]["note"] == {"type": "string"}
    assert "minLength" not in schema["properties"]["title"]


def test_script_draft_schema_is_ollama_compatible() -> None:
    schema = ollama_compatible_schema(ScriptDraft.model_json_schema())

    assert "$defs" not in schema
    assert "$ref" not in str(schema)
    assert "minItems" not in schema["properties"]["scenes"]
    assert "maxLength" not in schema["properties"]["title"]
    scene = schema["properties"]["scenes"]["items"]
    assert scene["properties"]["help_asset"] == {"type": "string"}
    assert "anyOf" not in scene["properties"]["help_asset"]
