import json
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from src.llm.schema import ollama_compatible_schema

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class StructuredLLM(Protocol):
    def generate_structured(
        self,
        system: str,
        user: str,
        response_model: type[StructuredModel],
    ) -> tuple[StructuredModel, str]: ...


class LLMResponseError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        chat_model: str,
        embed_model: str,
        fallback_model: str | None = None,
        timeout_seconds: float = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.fallback_model = fallback_model
        self.embed_model = embed_model
        self.timeout_seconds = timeout_seconds

    def available_models(self) -> list[str]:
        response = httpx.get(f"{self.base_url}/api/tags", timeout=self.timeout_seconds)
        response.raise_for_status()
        return [model["name"] for model in response.json().get("models", [])]

    def generate_structured(
        self,
        system: str,
        user: str,
        response_model: type[StructuredModel],
    ) -> tuple[StructuredModel, str]:
        models = [self.chat_model]
        if self.fallback_model and self.fallback_model != self.chat_model:
            models.append(self.fallback_model)
        schema = ollama_compatible_schema(response_model.model_json_schema())
        failures: list[str] = []
        for model in models:
            for attempt in range(2):
                repair = (
                    "\nYour previous response was invalid. Return only JSON matching the schema."
                    if attempt
                    else ""
                )
                try:
                    response = httpx.post(
                        f"{self.base_url}/api/chat",
                        json={
                            "model": model,
                            "stream": False,
                            "format": schema,
                            "messages": [
                                {"role": "system", "content": system},
                                {"role": "user", "content": f"{user}{repair}"},
                            ],
                            "options": {"temperature": 0.1},
                        },
                        timeout=self.timeout_seconds,
                    )
                    if response.is_error:
                        detail = response.text[:300].replace("\n", " ")
                        failures.append(
                            f"{model}:HTTPStatusError({response.status_code}:{detail})"
                        )
                        continue
                    content = response.json()["message"]["content"]
                    return response_model.model_validate(json.loads(content)), model
                except (
                    httpx.HTTPError,
                    KeyError,
                    TypeError,
                    json.JSONDecodeError,
                    ValidationError,
                ) as error:
                    failures.append(f"{model}:{type(error).__name__}")
        raise LLMResponseError(
            "Local LLM failed to return valid structured output: " + ", ".join(failures)
        )

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = httpx.post(
            f"{self.base_url}/api/embed",
            json={"model": self.embed_model, "input": texts},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        embeddings = response.json().get("embeddings", [])
        if len(embeddings) != len(texts):
            raise ValueError("Ollama returned an unexpected embedding count")
        return embeddings
