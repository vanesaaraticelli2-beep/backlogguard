"""Similitud entre títulos de ítems, compartida por el Crítico y el plan de publicación.

Cada palabra se reduce a sus primeras letras para que "filtrar" y "filtro" cuenten como la misma:
es una raíz tosca, pero alcanza para detectar historias casi duplicadas redactadas con otras palabras.
"""
from __future__ import annotations

from backlogguard.rag.embeddings import tokenize

STEM_LENGTH = 5
DUPLICATE_OVERLAP = 0.8
MIN_TOKENS = 3
_STOPWORDS = {"de", "del", "la", "el", "los", "las", "en", "un", "una", "y", "a", "al", "por", "para", "con", "mediante", "que"}


def title_tokens(title: str) -> set[str]:
    return {token[:STEM_LENGTH] for token in tokenize(title) if token not in _STOPWORDS}


def similar_titles(first: str, second: str) -> bool:
    """¿Los títulos parecen el mismo ítem? (coeficiente de solapamiento sobre las raíces)."""
    mine, theirs = title_tokens(first), title_tokens(second)
    smaller = min(len(mine), len(theirs))
    return smaller >= MIN_TOKENS and len(mine & theirs) / smaller >= DUPLICATE_OVERLAP
