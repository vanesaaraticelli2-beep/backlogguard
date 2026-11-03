"""Referencia de siglas para la barra lateral: qué es cada id que aparece en las pantallas."""
from __future__ import annotations

IDS = [
    ("C-nnn", "Compromiso de la preventa: lo vendido, con su página y cita."),
    ("RQ-nnn", "Requisito del catálogo; sigue entre reuniones y tiene versión (v1, v2…)."),
    ("P-nnn", "Propuesta de una reunión sobre el catálogo (nuevo, refina, contradice…). La decide una persona."),
    ("EP-nnn", "Épica."),
    ("HU-nnn", "Historia de usuario del tablero. La de un requisito es HU-RQ-nnn."),
    ("US-nnn", "La misma historia como se muestra y se descarga en Word (User Story)."),
    ("TA-nnn", "Tarea."),
    ("CP-nnn", "Caso de prueba."),
    ("T-nnn", "Tarea entre agentes de la corrida (quién le pidió qué a quién). No es del backlog."),
    ("F-xxxx", "Hallazgo del Auditor."),
    ("G-xxxxxxxx", "Grupo de hallazgos del mismo tema, para pedir una sola decisión."),
    ("R-…", "Pedido de decisión a una persona. R-plan es el plan de publicación."),
]

TERMS = [
    ("DoR", "Definition of Ready: cuándo una historia está lista para trabajarse."),
    ("INVEST", "Criterios de una buena historia: independiente, negociable, valiosa, estimable, pequeña y testeable."),
    ("Gherkin", "Formato Dado / Cuando / Entonces de los criterios de aceptación."),
    ("HITL", "Human-in-the-Loop: las pausas donde decide una persona."),
    ("PO", "Product owner."),
]


def glossary_markdown() -> str:
    def block(title: str, rows: list[tuple[str, str]]) -> str:
        return f"**{title}**\n\n" + "\n".join(f"- `{sigla}` {meaning}" for sigla, meaning in rows)

    return block("Ids", IDS) + "\n\n" + block("Términos", TERMS)
