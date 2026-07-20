from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection

from src.rag.chunker import HelpChunk


class ChromaVectorStore:
    def __init__(
        self,
        persist_path: Path,
        collection_name: str = "intacct_help",
    ) -> None:
        persist_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(persist_path))
        self.collection: Collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: list[HelpChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Each chunk must have exactly one embedding")
        if not chunks:
            return
        unique_chunks: list[HelpChunk] = []
        unique_embeddings: list[list[float]] = []
        seen: set[str] = set()
        for ordinal, (chunk, embedding) in enumerate(
            zip(chunks, embeddings, strict=True)
        ):
            chunk_id = chunk.chunk_id
            if chunk_id in seen:
                chunk_id = f"{chunk.chunk_id}:{ordinal}"
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            if chunk_id != chunk.chunk_id:
                chunk = HelpChunk(
                    chunk_id=chunk_id,
                    text=chunk.text,
                    source_url=chunk.source_url,
                    source_hash=chunk.source_hash,
                    title=chunk.title,
                    heading_path=chunk.heading_path,
                    asset_urls=chunk.asset_urls,
                    token_estimate=chunk.token_estimate,
                )
            unique_chunks.append(chunk)
            unique_embeddings.append(embedding)
        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in unique_chunks],
            documents=[chunk.text for chunk in unique_chunks],
            metadatas=[chunk.metadata() for chunk in unique_chunks],
            embeddings=unique_embeddings,
        )

    def replace_source(
        self,
        source_url: str,
        chunks: list[HelpChunk],
        embeddings: list[list[float]],
    ) -> None:
        self.delete_source(source_url)
        self.upsert(chunks, embeddings)

    def delete_source(self, source_url: str) -> None:
        self.collection.delete(where={"source_url": source_url})

    def query(
        self,
        embedding: list[float],
        top_k: int = 5,
        where: dict[str, str] | None = None,
    ) -> list[dict[str, object]]:
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = result["ids"][0]
        documents = result["documents"][0] if result["documents"] else []
        metadatas = result["metadatas"][0] if result["metadatas"] else []
        distances = result["distances"][0] if result["distances"] else []
        return [
            {
                "id": item_id,
                "document": document,
                "metadata": metadata,
                "distance": distance,
                "score": 1.0 - float(distance),
            }
            for item_id, document, metadata, distance in zip(
                ids, documents, metadatas, distances, strict=True
            )
        ]

    def count(self) -> int:
        return self.collection.count()
