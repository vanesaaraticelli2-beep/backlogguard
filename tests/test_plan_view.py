from backlogguard.ui import plan_view

ITEMS = [
    {"item_id": "EP-1", "action": "crear", "type": "Epic", "title": "Alianzas", "reason": "no existe en el backlog",
     "description": "Épica de alianzas", "acceptance_criteria": [], "parent_item_id": None, "remote_id": None},
    {"item_id": "US-001", "action": "crear", "type": "User Story", "title": "Alta de alianza", "reason": "no existe en el backlog",
     "description": "Como gestor quiero crear alianzas para operar",
     "acceptance_criteria": ["Dado A\nCuando B\nEntonces C"], "parent_item_id": "EP-1", "remote_id": None},
    {"item_id": "US-002", "action": "omitir", "type": "User Story", "title": "Baja", "reason": "ya publicado en #7, sin cambios",
     "description": "", "acceptance_criteria": [], "parent_item_id": None, "remote_id": 7},
]


def test_counts_line_only_lists_what_exists():
    assert plan_view.counts_line(ITEMS) == "2 para crear · 1 omitido(s)"
    assert plan_view.counts_line([]) == "sin ítems"


def test_rows_show_parent_by_title_and_remote_id():
    rows = plan_view.plan_rows(ITEMS)
    assert rows[1]["Padre"] == "Alianzas" and rows[1]["En Azure"] == "nuevo"
    assert rows[0]["Padre"] == "—"
    assert rows[2]["En Azure"] == "#7" and rows[2]["Acción"].endswith("Omitir")


def test_item_markdown_has_description_and_criteria():
    text = plan_view.item_markdown(ITEMS[1], "Alianzas")
    assert "**Padre:** Alianzas" in text
    assert "Como gestor quiero crear alianzas para operar" in text
    assert "- Dado A" in text and "Entonces C" in text


def test_item_markdown_without_description_or_criteria():
    text = plan_view.item_markdown(ITEMS[2])
    assert "Descripción" not in text and "Criterios" not in text and "#7" in text
    assert plan_view.item_heading(ITEMS[1]).endswith("US-001 — Alta de alianza")
