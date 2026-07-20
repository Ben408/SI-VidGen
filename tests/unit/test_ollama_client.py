import httpx
import pytest
from pydantic import BaseModel

from src.llm.client import LLMResponseError, OllamaClient


def test_embed_many_uses_configured_model(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return httpx.Response(
            200,
            json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = OllamaClient("http://localhost:11434/", "gemma3:12b", "nomic-embed-text")

    assert client.embed_many(["one", "two"]) == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"] == "http://localhost:11434/api/embed"
    assert captured["json"] == {"model": "nomic-embed-text", "input": ["one", "two"]}


class ExampleResponse(BaseModel):
    answer: str


def test_structured_generation_falls_back_after_invalid_primary(monkeypatch) -> None:
    calls: list[str] = []

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        payload = kwargs["json"]
        assert isinstance(payload, dict)
        assert "$defs" not in payload["format"]
        model = str(payload["model"])
        calls.append(model)
        content = "not-json" if model == "primary" else '{"answer":"valid"}'
        return httpx.Response(
            200,
            json={"message": {"content": content}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = OllamaClient(
        "http://localhost:11434",
        "primary",
        "nomic-embed-text",
        fallback_model="fallback",
    )

    response, model = client.generate_structured("system", "user", ExampleResponse)

    assert response.answer == "valid"
    assert model == "fallback"
    assert calls == ["primary", "primary", "fallback"]


def test_structured_generation_reports_total_failure(monkeypatch) -> None:
    def fake_post(url: str, **_kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"content": "{}"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = OllamaClient("http://localhost:11434", "primary", "nomic-embed-text")

    with pytest.raises(LLMResponseError, match="failed to return valid"):
        client.generate_structured("system", "user", ExampleResponse)
