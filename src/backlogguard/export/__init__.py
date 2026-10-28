"""Salidas de BacklogGuard fuera de la pantalla (fuera del curso): hoy, la historia de usuario en Word."""
from backlogguard.export.story import Story, format_criterion, split_story, story_of
from backlogguard.export.word import story_to_docx

__all__ = ["Story", "format_criterion", "split_story", "story_of", "story_to_docx"]
