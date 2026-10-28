"""La historia de usuario lista para mostrar o exportar: id «US-003», Feature, Como/Quiero/Para y sus criterios.

El Feature no lo adivina un modelo: sale del área de la línea base a la que pertenecen los compromisos vendidos del requisito.
Las citas y los datos de la reunión no forman parte de la historia exportada; se ven solo en la pantalla.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from backlogguard.board import BacklogItem
from backlogguard.catalog import Catalog
from backlogguard.rag.compromisos import Baseline
from backlogguard.tools.requerimientos import is_gherkin

_STORY = re.compile(r"^\s*como\s+(?P<como>.+?)\s+quiero\s+(?P<quiero>.+?)\s+para\s+(?P<para>.+?)\.?\s*$", re.IGNORECASE | re.DOTALL)
_CONNECTORS = re.compile(r"\s*,?\s+(cuando|entonces)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Story:
    us_id: str
    title: str
    feature: str | None
    feature_number: int | None
    como: str
    quiero: str
    para: str
    criteria: tuple[str, ...]
    state: str = ""

    @property
    def file_name(self) -> str:
        title = re.sub(r'[\\/:*?"<>|]+', " ", self.title).strip()
        return f"{self.us_id} - {title[:70].strip()}.docx"


def split_story(description: str) -> tuple[str, str, str] | None:
    """«Como X quiero Y para Z» en sus tres partes, o None si la descripción no tiene esa forma."""
    found = _STORY.match(description or "")
    return (found["como"].strip(), found["quiero"].strip(), found["para"].strip()) if found else None


def format_criterion(text: str) -> str:
    """Un escenario se lee en una frase: «Dado X, cuando Y, entonces Z.»; una regla se deja como está."""
    flat = " ".join(text.split())
    if is_gherkin(flat):
        flat = _CONNECTORS.sub(lambda m: f", {m.group(1).lower()}", flat)
    flat = flat[:1].upper() + flat[1:]
    return flat if flat.endswith((".", "!", "?")) else flat + "."


def us_id(item: BacklogItem) -> str:
    """«US-003» para la historia del requisito RQ-003; sin requisito se muestra el id del ítem."""
    found = re.search(r"(\d+)$", item.requirement_id or "")
    return f"US-{int(found.group(1)):03d}" if found else item.id


def feature_of(item: BacklogItem, catalog: Catalog | None, baseline: Baseline | None) -> tuple[str | None, int | None]:
    """El área de la línea base con más compromisos vendidos ligados al requisito, y su número de orden."""
    if not (item.requirement_id and catalog is not None and baseline is not None):
        return None, None
    try:
        linked = catalog.requirement(item.requirement_id).current.draft.commitment_ids
    except KeyError:
        return None, None
    by_id = {c.id: c.epic for c in baseline.commitments}
    epics = Counter(by_id[i] for i in linked if i in by_id)
    if not epics:
        return None, None
    name = epics.most_common(1)[0][0]
    return name, list(baseline.by_epic()).index(name) + 1


def story_of(item: BacklogItem | dict, catalog: Catalog | None = None, baseline: Baseline | None = None) -> Story:
    item = item if isinstance(item, BacklogItem) else BacklogItem.model_validate(item)
    parts = (item.como, item.quiero, item.para) if item.como and item.quiero and item.para else split_story(item.description)
    como, quiero, para = parts or ("", item.description, "")
    feature, number = feature_of(item, catalog, baseline)
    return Story(
        us_id=us_id(item), title=item.title, feature=feature, feature_number=number, como=como, quiero=quiero, para=para,
        criteria=tuple(format_criterion(c) for c in item.acceptance_criteria), state=item.state.value,
    )
