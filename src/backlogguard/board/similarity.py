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
    if mine and mine == theirs:  # mismas palabras: es el mismo título, sea corto o largo
        return True
    smaller = min(len(mine), len(theirs))
    return smaller >= MIN_TOKENS and len(mine & theirs) / smaller >= DUPLICATE_OVERLAP


# Calibrado con dos corridas reales: las historias repetidas dieron 0,68 a 0,84 y una distinta que comparte fragmento, 0,65.
# Son pocos datos: es una heurística a revisar con la evaluación.
REQUIREMENT_OVERLAP = 0.7


def repeat_requirement(title: str, description: str, fragments: set[str], other_title: str, other_description: str, other_fragments: set[str]) -> bool:
    """¿Son dos redacciones del mismo requisito? Títulos parecidos, o la misma fuente citada y textos que dicen casi lo mismo.

    Los títulos solos no alcanzan: cuatro historias sobre el mismo tema pueden titularse distinto. Por eso también cuenta
    compartir al menos un fragmento citado junto con un solapamiento alto de título y descripción.
    """
    if similar_titles(title, other_title):
        return True
    if not fragments & other_fragments:
        return False
    mine, theirs = title_tokens(f"{title} {description}"), title_tokens(f"{other_title} {other_description}")
    smaller = min(len(mine), len(theirs))
    return smaller >= MIN_TOKENS and len(mine & theirs) / smaller >= REQUIREMENT_OVERLAP


def repeats(item, other) -> bool:
    """`repeat_requirement` entre dos ítems del tablero (mismo tipo)."""
    return item.kind is other.kind and repeat_requirement(
        item.title, item.description, {c.fragment_id for c in item.citations},
        other.title, other.description, {c.fragment_id for c in other.citations},
    )
