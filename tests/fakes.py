from typing import TypeVar

from pydantic import BaseModel

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class FakePipelineLLM:
    def __init__(self, *, invalid_source: bool = False) -> None:
        self.invalid_source = invalid_source
        self.prompts: list[tuple[str, str, str]] = []

    def generate_structured(
        self,
        system: str,
        user: str,
        response_model: type[StructuredModel],
    ) -> tuple[StructuredModel, str]:
        self.prompts.append((system, user, response_model.__name__))
        if response_model.__name__ == "ClassificationDraft":
            data = {
                "feature": "General Ledger",
                "intent": "Correct an unbalanced journal entry",
                "task_type": "Troubleshooting",
                "error_type": "Unbalanced journal",
                "help_topics": ["journal entries", "posting"],
                "search_query": "correct unbalanced General Ledger journal entry",
                "confidence": 0.93,
            }
        elif response_model.__name__ == "ScriptDraft":
            data = {
                "title": "Correct an unbalanced journal entry",
                "narration": "Review the journal totals and correct the affected line.",
                "scenes": [
                    {
                        "action": "Open the journal entry.",
                        "visual": "Show the journal entry totals described in official help.",
                        "voiceover": "Open the journal entry and compare total debits and credits.",
                        "help_asset": "",
                        "source_ids": [
                            "unknown-source" if self.invalid_source else "chunk-1"
                        ],
                    }
                ],
            }
        elif response_model.__name__ == "FollowUpPlan":
            data = {"additional_queries": ["General Ledger journal entry totals"]}
        elif response_model.__name__ == "AnswerDraft":
            data = {
                "summary": "Correct unbalanced journal totals before posting.",
                "steps": [
                    {
                        "instruction": "Open the journal entry.",
                        "detail": "Compare total debits and total credits.",
                        "source_ids": ["chunk-1"],
                    }
                ],
                "notes": ["Use only official Help steps for posting corrections."],
                "coverage_sufficient": True,
                "coverage_gap": "",
            }
        else:
            raise AssertionError(f"Unexpected response model {response_model.__name__}")
        return response_model.model_validate(data), "fake-local-model"

    def embed(self, _text: str) -> list[float]:
        return [1.0, 0.0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _text in texts]


class FakeVectorStore:
    def __init__(self, *, score: float = 0.9) -> None:
        self.score = score
        self.queries: list[tuple[list[float], int]] = []

    def query(
        self,
        embedding: list[float],
        top_k: int = 5,
        where: dict[str, str] | None = None,
    ) -> list[dict[str, object]]:
        self.queries.append((embedding, top_k))
        return [
            {
                "id": "chunk-1",
                "document": (
                    "Open the journal entry. Compare total debits and total credits. "
                    "Correct the affected line and save the entry."
                ),
                "metadata": {
                    "source_url": "https://www.intacct.com/help/gl-journal.htm",
                    "title": "Correct an unbalanced journal entry",
                    "heading_path": "Correct the entry",
                    "asset_urls": "",
                },
                "distance": 1 - self.score,
                "score": self.score,
            }
        ]

    def upsert(self, _chunks, _embeddings) -> None:
        raise NotImplementedError

    def replace_source(self, _source_url, _chunks, _embeddings) -> None:
        raise NotImplementedError

    def delete_source(self, _source_url) -> None:
        raise NotImplementedError


class FakeVideoGenerator:
    def __init__(self, *, configured: bool = True) -> None:
        self._configured = configured
        self.payloads = []
        self.waited: list[str] = []
        self.downloads: list[tuple[str, object]] = []
        self.wait_kwargs: list[dict] = []

    @property
    def configured(self) -> bool:
        return self._configured

    def generate(self, payload):
        self.payloads.append(payload)
        scene_count = max(1, len(payload.scenes or []))
        if scene_count >= 2:
            job_ids = [f"video-test-{index}" for index in range(1, scene_count + 1)]
            return {
                "id": job_ids[0],
                "generation_id": job_ids[0],
                "generation_job_ids": job_ids,
                "mode": "scene_chunked",
                "aspect_ratio": "16:9",
                "scene_count": scene_count,
            }
        return {
            "id": "video-test-1",
            "generation_id": "video-test-1",
            "generation_job_ids": ["video-test-1"],
            "mode": "single",
            "aspect_ratio": "16:9",
            "scene_count": 1,
        }

    def wait_for_result(
        self,
        generation_id: str,
        *,
        timeout_seconds: int = 600,
        scene_job_ids: list[str] | None = None,
        aspect_ratio: str = "16:9",
    ):
        self.waited.append(generation_id)
        self.wait_kwargs.append(
            {
                "timeout_seconds": timeout_seconds,
                "scene_job_ids": scene_job_ids,
                "aspect_ratio": aspect_ratio,
            }
        )
        stitch_id = (
            "video-stitch-1"
            if scene_job_ids and len(scene_job_ids) >= 2
            else generation_id
        )
        return {
            "id": stitch_id,
            "result_url": "https://example.com/videos/test.mp4",
            "scene_job_ids": scene_job_ids or [generation_id],
            "mode": "scene_chunked" if scene_job_ids and len(scene_job_ids) >= 2 else "single",
        }

    def download_video(self, source_url: str, destination):
        from pathlib import Path

        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake-mp4")
        self.downloads.append((source_url, path))
        return path
