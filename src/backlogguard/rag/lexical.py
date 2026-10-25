"""Búsqueda léxica BM25 y fusión RRF (clase 8 del curso), adaptadas al español.

Adaptaciones: implementación propia (sin `rank-bm25`), sin acentos, con una lista de palabras vacías en español y
una raíz tosca de 5 letras, para que «parametrizar» y «parametrizable» o «filtro» y «filtrar» coincidan.
La fusión RRF combina el orden de los embeddings con el del BM25: lo que uno ordena mal, lo suele ordenar bien el otro.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

from backlogguard.rag.embeddings import tokenize

STEM_LENGTH = 5
RRF_K = 60
STOPWORDS = {
    "a", "al", "algo", "ante", "con", "como", "cual", "cuando", "de", "del", "desde", "donde", "e", "el", "ella", "en",
    "entre", "es", "esa", "ese", "eso", "esta", "este", "esto", "hay", "la", "las", "le", "les", "lo", "los", "mas", "me",
    "mi", "muy", "no", "nos", "o", "para", "pero", "por", "que", "se", "ser", "si", "sin", "sobre", "son", "su", "sus",
    "te", "un", "una", "uno", "unos", "unas", "y", "ya",
}


def stems(text: str) -> list[str]:
    return [token[:STEM_LENGTH] for token in tokenize(text) if token not in STOPWORDS]


class BM25:
    def __init__(self, documents: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75):
        self.docs = [list(doc) for doc in documents]
        self.k1, self.b = k1, b
        self.avg_len = (sum(len(doc) for doc in self.docs) / len(self.docs)) if self.docs else 0.0
        frequency: Counter[str] = Counter()
        for doc in self.docs:
            frequency.update(set(doc))
        total = len(self.docs)
        self.idf = {term: math.log(1 + (total - count + 0.5) / (count + 0.5)) for term, count in frequency.items()}
        self.counts = [Counter(doc) for doc in self.docs]

    def scores(self, query: Sequence[str]) -> list[float]:
        result = []
        for doc, counts in zip(self.docs, self.counts):
            score = 0.0
            for term in set(query):
                tf = counts.get(term, 0)
                if tf:
                    norm = tf + self.k1 * (1 - self.b + self.b * len(doc) / (self.avg_len or 1))
                    score += self.idf[term] * tf * (self.k1 + 1) / norm
            result.append(score)
        return result


def rrf(rankings: Sequence[Sequence[int]], k: int = RRF_K) -> dict[int, float]:
    """Fusión por rango recíproco: suma 1/(k + posición) de cada ranking (posiciones desde 1)."""
    fused: dict[int, float] = {}
    for ranking in rankings:
        for position, index in enumerate(ranking, 1):
            fused[index] = fused.get(index, 0.0) + 1.0 / (k + position)
    return fused
