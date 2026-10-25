"""Retrieval (clase 5 del curso).

`SearchResult` e `InMemoryRetriever` siguen el curso; `QdrantRetriever` es la versión
reducida del curso (Qdrant local, sin servidor). Adaptación: ambos agregan `get(chunk_id)`
para resolver una cita a su fragmento.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence
from uuid import NAMESPACE_URL, uuid5

import numpy as np

from backlogguard.rag.embeddings import EmbeddingProvider
from backlogguard.rag.lexical import BM25, RRF_K, rrf, stems


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    document_id: str
    text: str
    score: float
    source: str
    page: int | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)


def _cosine(a, b) -> float:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return 0.0 if denominator == 0 else float(np.dot(a, b) / denominator)


def _check_query(query: str, top_k: int) -> None:
    if not str(query).strip():
        raise ValueError("La consulta no puede estar vacía")
    if top_k < 1:
        raise ValueError("top_k debe ser al menos 1")


def _result(item: dict, score: float) -> SearchResult:
    return SearchResult(
        chunk_id=item["chunk_id"],
        document_id=item["document_id"],
        text=item["text"],
        score=score,
        source=item["source"],
        page=item.get("page"),
        metadata=item.get("metadata", {}),
    )


class InMemoryRetriever:
    backend_name = "in-memory"

    def __init__(self, embedding_provider: EmbeddingProvider):
        self.embedding_provider = embedding_provider
        self._items: dict[str, dict] = {}

    def index(self, chunks: Sequence[dict]) -> None:
        chunks = list(chunks)
        if not chunks:
            return
        # Reemplaza lo anterior del mismo documento para no dejar versiones obsoletas.
        replaced = {item["document_id"] for item in chunks}
        self._items = {k: v for k, v in self._items.items() if v["document_id"] not in replaced}
        vectors = self.embedding_provider.embed_documents([item["text"] for item in chunks])
        for item, vector in zip(chunks, vectors, strict=True):
            self._items[item["chunk_id"]] = {**item, "vector": vector}

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: dict | None = None,
        min_score: float | None = None,
    ) -> list[SearchResult]:
        _check_query(query, top_k)
        vector = self.embedding_provider.embed_query(query)
        scored = []
        for item in self._items.values():
            metadata = item.get("metadata", {})
            if filters and any(metadata.get(key) != value for key, value in filters.items()):
                continue
            score = _cosine(vector, item["vector"])
            if min_score is None or score >= min_score:
                scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["chunk_id"]))
        return [_result(item, score) for score, item in scored[:top_k]]

    def hybrid_search(self, query: str, top_k: int = 5, filters: dict | None = None) -> list[SearchResult]:
        """Embeddings + BM25 fusionados con RRF (clase 8). `score` va de 0 a 1: 1 es el primero en ambos rankings."""
        _check_query(query, top_k)
        items = sorted(self._items.values(), key=lambda item: item["chunk_id"])
        candidates = [
            item for item in items
            if not filters or all(item.get("metadata", {}).get(key) == value for key, value in filters.items())
        ]
        if not candidates:
            return []
        vector = self.embedding_provider.embed_query(query)
        dense = sorted(range(len(candidates)), key=lambda i: -_cosine(vector, candidates[i]["vector"]))
        lexical_scores = BM25([stems(item["text"]) for item in items]).scores(stems(query))
        by_id = {item["chunk_id"]: score for item, score in zip(items, lexical_scores)}
        lexical = sorted(range(len(candidates)), key=lambda i: -by_id[candidates[i]["chunk_id"]])
        lexical = [i for i in lexical if by_id[candidates[i]["chunk_id"]] > 0]  # sin coincidencia de palabras no puntúa
        fused = rrf([dense, lexical])
        best = 2.0 / (RRF_K + 1)
        order = sorted(fused, key=lambda i: (-fused[i], candidates[i]["chunk_id"]))[:top_k]
        return [_result(candidates[i], round(fused[i] / best, 4)) for i in order]

    def all_chunks(self, filters: dict | None = None) -> list[SearchResult]:
        """Todos los fragmentos (opcionalmente filtrados), en orden estable."""
        return [
            _result(item, 1.0)
            for item in sorted(self._items.values(), key=lambda i: i["chunk_id"])
            if not filters or all(item.get("metadata", {}).get(k) == v for k, v in filters.items())
        ]

    def get(self, chunk_id: str) -> SearchResult | None:
        item = self._items.get(chunk_id)
        return _result(item, 1.0) if item else None

    def count(self) -> int:
        return len(self._items)


def _point_id(chunk_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, chunk_id))


class QdrantRetriever:
    backend_name = "qdrant-local"
    _RESERVED = {"chunk_id", "document_id", "text", "source", "page", "embedding_model"}

    def __init__(
        self,
        path: str | Path,
        *,
        embedding_provider: EmbeddingProvider,
        collection_name: str = "backlogguard_fuentes",
    ):
        try:
            from qdrant_client import QdrantClient, models
        except ImportError as exc:
            raise RuntimeError('Instalá el extra rag: pip install -e ".[rag]"') from exc

        self._models = models
        self.embedding_provider = embedding_provider
        self.collection_name = collection_name
        if str(path) == ":memory:":
            self.client = QdrantClient(":memory:")
        else:
            Path(path).mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(path))

        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_provider.dimension, distance=models.Distance.COSINE
                ),
            )
        size = int(self.client.get_collection(collection_name).config.params.vectors.size)
        if size != int(embedding_provider.dimension):
            raise RuntimeError(
                f"Dimensión incompatible: collection={size}, provider={embedding_provider.dimension}"
            )

    def _filter(self, filters: dict | None):
        if not filters:
            return None
        models = self._models
        return models.Filter(
            must=[
                models.FieldCondition(key=key, match=models.MatchValue(value=value))
                for key, value in filters.items()
            ]
        )

    def delete_document(self, document_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=self._models.FilterSelector(filter=self._filter({"document_id": document_id})),
            wait=True,
        )

    def index(self, chunks: Sequence[dict], batch_size: int = 32) -> None:
        chunks = list(chunks)
        if not chunks:
            return
        for document_id in sorted({item["document_id"] for item in chunks}):
            self.delete_document(document_id)
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors = self.embedding_provider.embed_documents([item["text"] for item in batch])
            points = [
                self._models.PointStruct(
                    id=_point_id(item["chunk_id"]),
                    vector=vector,
                    payload={
                        "chunk_id": item["chunk_id"],
                        "document_id": item["document_id"],
                        "text": item["text"],
                        "source": item["source"],
                        "page": item.get("page"),
                        **item.get("metadata", {}),
                        "embedding_model": self.embedding_provider.model_name,
                    },
                )
                for item, vector in zip(batch, vectors, strict=True)
            ]
            self.client.upsert(collection_name=self.collection_name, points=points, wait=True)

    def _from_payload(self, payload: dict, score: float) -> SearchResult:
        item = {
            **{k: payload.get(k) for k in ("chunk_id", "document_id", "text", "source", "page")},
            "metadata": {k: v for k, v in payload.items() if k not in self._RESERVED},
        }
        return _result(item, score)

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: dict | None = None,
        min_score: float | None = None,
    ) -> list[SearchResult]:
        _check_query(query, top_k)
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=self.embedding_provider.embed_query(query),
            query_filter=self._filter(filters),
            limit=top_k,
            score_threshold=min_score,
            with_payload=True,
            with_vectors=False,
        )
        return [self._from_payload(point.payload, float(point.score)) for point in response.points]

    def hybrid_search(self, query: str, top_k: int = 5, filters: dict | None = None) -> list[SearchResult]:
        """Qdrant local solo ordena por embeddings; la fusión con BM25 está en el retriever en memoria."""
        return self.search(query, top_k=top_k, filters=filters)

    def get(self, chunk_id: str) -> SearchResult | None:
        points = self.client.retrieve(
            collection_name=self.collection_name, ids=[_point_id(chunk_id)], with_payload=True
        )
        return self._from_payload(points[0].payload, 1.0) if points else None

    def all_chunks(self, filters: dict | None = None) -> list[SearchResult]:
        results, offset = [], None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=self._filter(filters),
                limit=128,
                offset=offset,
                with_payload=True,
            )
            results.extend(self._from_payload(point.payload, 1.0) for point in points)
            if offset is None:
                return sorted(results, key=lambda r: r.chunk_id)

    def count(self) -> int:
        return int(self.client.count(collection_name=self.collection_name, exact=True).count)

    def close(self) -> None:
        self.client.close()


def build_retriever(
    *, use_qdrant: bool, path: str | Path, embedding_provider: EmbeddingProvider
) -> InMemoryRetriever | QdrantRetriever:
    if use_qdrant:
        return QdrantRetriever(path, embedding_provider=embedding_provider)
    return InMemoryRetriever(embedding_provider)
