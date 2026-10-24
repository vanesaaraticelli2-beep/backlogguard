"""Embeddings (clase 5 del curso).

El contrato `EmbeddingProvider` y el proveedor determinístico siguen el curso.
Adaptación: se quitó la tabla de sinónimos y los tópicos del dominio de ejemplo del curso;
el vector es solo léxico (palabras y pares de palabras sin acentos). Los embeddings reales
(`sentence-transformers`) quedan para la evaluación.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Protocol, Sequence

import numpy as np


class EmbeddingProvider(Protocol):
    model_name: str
    dimension: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def tokenize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.findall(r"[a-z0-9]+", text)


class DeterministicLexicalEmbeddings:
    """Vectores reproducibles por hashing de palabras y bigramas, normalizados con L2."""

    model_name = "deterministic-lexical-v1"
    dimension = 256
    normalization = "l2"

    def _embed(self, text: str) -> list[float]:
        tokens = tokenize(text)
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        vector = np.zeros(self.dimension, dtype=float)
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0 if "_" not in feature else 0.5
        norm = float(np.linalg.norm(vector))
        return (vector / norm).tolist() if norm else vector.tolist()

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
