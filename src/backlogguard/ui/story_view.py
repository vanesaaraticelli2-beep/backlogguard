"""La historia de usuario en pantalla, con el formato de la plantilla, y su botón de descarga en Word.

Las citas y la trazabilidad se muestran acá, en la pantalla; el Word lleva solo la historia.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from backlogguard.board import BacklogItem, ItemKind
from backlogguard.export import Story, story_of, story_to_docx
from backlogguard.graph.setup import baseline_dir, user_sources_dir
from backlogguard.rag import SourceLibrary
from backlogguard.rag.compromisos import BaselineStore
from backlogguard.board import SourceType
from backlogguard.ui.controller import RunController

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def story_html(story: Story) -> str:
    banner = f"Feature {story.feature_number}: {story.feature}" if story.feature and story.feature_number else (story.feature or "Historia de usuario")
    rows = [
        f'<div class="us-banner">{escape(banner)}</div>',
        f'<div class="us-head"><span class="us-id">{escape(story.us_id)}</span><span class="us-title">{escape(story.title)}</span></div>',
    ]
    if story.feature:
        rows.append(f'<div class="us-row us-feature"><b>Feature:</b> {escape(story.feature)}</div>')
    for label, text in (("Como...", story.como), ("Quiero...", story.quiero), ("Para...", story.para)):
        rows.append(f'<div class="us-row"><span class="us-label">{label}</span><span class="us-text">{escape(text)}</span></div>')
    rows.append('<div class="us-criteria">Criterios de Aceptación</div>')
    rows += [f'<div class="us-row us-crit"><span class="us-check">✔</span><span class="us-text">{escape(c)}</span></div>' for c in story.criteria]
    return f'<div class="us">{"".join(rows)}</div>'


def current_baseline(controller: RunController):
    library = SourceLibrary(user_sources_dir(controller.data_dir))
    if not library.root.is_dir():
        return None
    presales = [i for i, m in library.describe() if m.source_type is SourceType.PREVENTA]
    return BaselineStore(baseline_dir(controller.data_dir)).current(library.load(presales[0])) if len(presales) == 1 else None


def render_story(controller: RunController, item: BacklogItem, baseline) -> None:
    """La historia completa y el botón para bajarla; solo para historias."""
    story = story_of(item, controller.deps.catalog, baseline)
    st.markdown(story_html(story), unsafe_allow_html=True)
    st.download_button(
        "Descargar Word", data=story_to_docx(story), file_name=story.file_name, mime=DOCX, key=f"word-{controller.thread_id}-{item.id}",
    )
    if item.requirement_id:
        st.caption(f"Sale del requisito {item.requirement_id}, versión {item.requirement_version}.")


def is_story(item: BacklogItem) -> bool:
    return item.kind is ItemKind.HISTORIA
