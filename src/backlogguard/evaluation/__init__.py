"""Evaluación (fuera del curso): mide con respuestas conocidas qué tan bien trabaja el sistema.

Sin modelos como juez: las respuestas esperadas se emparejan con reglas de palabras (ver `scoring`), así la medición es
reproducible y no cuesta nada. Lo único que gasta es correr el sistema o el agente único con modelos reales.
"""
from backlogguard.evaluation.scoring import Cita, Elemento, Salida, puntuar
from backlogguard.evaluation.truth import Verdad, cargar_verdad

__all__ = ["Cita", "Elemento", "Salida", "Verdad", "cargar_verdad", "puntuar"]
