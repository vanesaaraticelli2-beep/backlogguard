"""Auditoría de vínculos con la preventa (fuera del curso).

Cada requisito (aprobado) o propuesta (pendiente) está ligado a compromisos de la preventa. Acá se verifica cada par con la
misma segunda pasada que se usa al leer una reunión, y se corrigen los vínculos que el modelo juzga «distinto». Los textos de los
requisitos no se tocan: solo cambia a qué compromisos están ligados.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from backlogguard.catalog.ingest import LINK_BATCH, _verify_links
from backlogguard.catalog.models import MEETING_TYPES, ProposalState, RequirementStatus
from backlogguard.catalog.store import Catalog
from backlogguard.llm.errors import InvalidProviderResponseError
from backlogguard.llm.providers import LLMProvider
from backlogguard.rag.compromisos import Baseline


@dataclass
class Link:
    kind: str  # "requisito" | "propuesta"
    target: str  # RQ-nnn o P-nnn
    title: str
    commitment: str  # C-nnn
    relation: str  # "mismo" | "distinto" | "sin verificar"
    difference: str = ""
    reason: str = ""


def collect(catalog: Catalog, baseline: Baseline, *, requirements: bool = True, proposals: bool = True) -> list[tuple[Link, tuple[str, str, object]]]:
    """Los pares (vínculo, (texto, cita, compromiso)) a verificar. Un vínculo a un compromiso que ya no existe se descarta solo."""
    by_id = {c.id: c for c in baseline.commitments}
    pairs: list[tuple[Link, tuple[str, str, object]]] = []

    def add(kind: str, target: str, title: str, text: str, quote: str, ids: list[str]) -> None:
        for cid in dict.fromkeys(ids):
            if cid in by_id:
                pairs.append((Link(kind, target, title, cid, "sin verificar"), (text, quote, by_id[cid])))
            else:
                pairs.append((Link(kind, target, title, cid, "distinto", reason="el compromiso ya no existe en la línea base"), None))

    if requirements:
        for req in catalog.requirements(RequirementStatus.ACTIVO):
            draft = req.current.draft
            meeting = next((e for e in req.current.evidence if e.source_type in MEETING_TYPES), None)
            add("requisito", req.id, draft.title, f"{draft.title}. {draft.description}".strip(), meeting.quote if meeting else draft.description or draft.title, draft.commitment_ids)
    if proposals:
        for prop in catalog.proposals(state=ProposalState.PENDIENTE):
            if not prop.drafts:
                continue
            draft = prop.drafts[0]
            meeting = next((e for e in prop.evidence if e.source_type in MEETING_TYPES), None)
            add("propuesta", prop.id, draft.title, f"{draft.title}. {draft.description}".strip(), meeting.quote if meeting else draft.title, draft.commitment_ids)
    return pairs


def audit(provider: LLMProvider, pairs: list[tuple[Link, tuple[str, str, object] | None]]) -> list[Link]:
    """Verifica los pares con el modelo (de a LINK_BATCH). Los que no se pudieron verificar quedan «sin verificar» y no se tocan."""
    todo = [(link, pair) for link, pair in pairs if pair is not None]
    for start in range(0, len(todo), LINK_BATCH):
        chunk = todo[start : start + LINK_BATCH]
        try:
            found = _verify_links(provider, [pair for _, pair in chunk])
        except (InvalidProviderResponseError, ValueError):
            continue
        for index, (link, _) in enumerate(chunk, 1):
            if verdict := found.get(index):
                link.relation, link.difference, link.reason = verdict.relacion, verdict.diferencia.strip(), verdict.motivo.strip()
    return [link for link, _ in pairs]


def corrections(links: list[Link]) -> dict[tuple[str, str], list[str]]:
    """Por cada requisito o propuesta, los compromisos que quedan (los «mismo» y los «sin verificar»). Solo los que cambian."""
    kept: dict[tuple[str, str], list[str]] = {}
    changed: set[tuple[str, str]] = set()
    for link in links:
        key = (link.kind, link.target)
        kept.setdefault(key, [])
        if link.relation == "distinto":
            changed.add(key)
        else:
            kept[key].append(link.commitment)
    return {key: ids for key, ids in kept.items() if key in changed}


def apply(catalog: Catalog, links: list[Link]) -> dict[str, list[str]]:
    """Guarda los vínculos corregidos. Devuelve, por id, cómo quedaron."""
    done: dict[str, list[str]] = {}
    for (kind, target), ids in corrections(links).items():
        if kind == "requisito":
            catalog.set_requirement_links(target, ids)
        else:
            draft = catalog.proposal(target).drafts[0]
            catalog.edit(target, draft.model_copy(update={"commitment_ids": ids}))
        done[target] = ids
    return done


def save(links: list[Link], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps([asdict(link) for link in links], ensure_ascii=False, indent=2), encoding="utf-8")


def load(path: str | Path) -> list[Link]:
    return [Link(**row) for row in json.loads(Path(path).read_text(encoding="utf-8"))]


def report(links: list[Link], titles: dict[str, str] | None = None) -> str:
    """El informe para leer: por cada requisito o propuesta, qué vínculos se confirman y cuáles se descartan, con el motivo."""
    lines = ["# Auditoría de vínculos con la preventa", ""]
    groups: dict[tuple[str, str], list[Link]] = {}
    for link in links:
        groups.setdefault((link.kind, link.target), []).append(link)
    counts = {rel: sum(1 for l in links if l.relation == rel) for rel in ("mismo", "distinto", "sin verificar")}
    lines += [f"- Vínculos revisados: {len(links)} · confirmados: {counts['mismo']} · a descartar: {counts['distinto']} · sin verificar: {counts['sin verificar']}", ""]
    for (kind, target), rows in groups.items():
        marks = "".join({"mismo": "✔", "distinto": "✘"}.get(r.relation, "?") for r in rows)
        lines.append(f"## {target} ({kind}) {marks} — {rows[0].title}")
        for r in rows:
            detail = f" · difiere: {r.difference}" if r.difference else ""
            lines.append(f"- {r.commitment}: **{r.relation}**{detail}" + (f" · {r.reason}" if r.reason else ""))
        lines.append("")
    return "\n".join(lines)


def override(links: list[Link], *, keep: set[tuple[str, str]] = frozenset(), drop: set[tuple[str, str]] = frozenset()) -> list[Link]:
    """La decisión de una persona manda sobre el modelo: `keep` conserva un vínculo juzgado «distinto» y `drop` descarta uno juzgado «mismo».

    Cada par es (requisito o propuesta, compromiso). Un par que no existe es un error: así un id mal escrito no pasa en silencio."""
    known = {(link.target, link.commitment) for link in links}
    if unknown := sorted((keep | drop) - known):
        raise ValueError("No hay ese vínculo en el informe: " + ", ".join(f"{t}:{c}" for t, c in unknown))
    for link in links:
        key = (link.target, link.commitment)
        if key in keep and link.relation == "distinto":
            link.relation, link.reason = "mismo", f"conservado por una persona (el modelo dijo «distinto»: {link.reason})"
        elif key in drop:
            link.relation, link.reason = "distinto", f"descartado por una persona (el modelo dijo «{link.relation}»: {link.reason})"
    return links


def parse_pairs(text: str | None) -> set[tuple[str, str]]:
    """«RQ-004:C-014,RQ-005:C-014» → {("RQ-004", "C-014"), ("RQ-005", "C-014")}."""
    pairs = set()
    for part in (text or "").replace(";", ",").split(","):
        if part.strip():
            target, _, commitment = part.strip().partition(":")
            if not target or not commitment:
                raise ValueError(f"No entiendo «{part.strip()}»: usá el formato RQ-004:C-014.")
            pairs.add((target.strip().upper(), commitment.strip().upper()))
    return pairs
