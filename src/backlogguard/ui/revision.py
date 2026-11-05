"""Pestañas «Revisión» y «Catálogo»: decidir las propuestas de cada reunión y consultar la memoria del proyecto.

La regla de quién decide y qué entra en un lote vive en `catalog/review.py`; acá solo se dibuja y se llama a esas funciones.
"""
from __future__ import annotations

import re
from html import escape

import streamlit as st
from pydantic import ValidationError

from backlogguard.board import SourceType
from backlogguard.catalog.coverage import build_coverage
from backlogguard.catalog import CatalogError, Draft, Proposal, ProposalKind, ProposalState
from backlogguard.catalog.review import decide_batch, decide_one, decider_role, pending_batch, pending_individual
from backlogguard.graph.setup import baseline_dir, user_sources_dir
from backlogguard.rag import SourceLibrary
from backlogguard.rag.compromisos import BaselineStore
from backlogguard.ui.controller import RunController
from backlogguard.ui.scroll import REVIEW, anchor, apply_scroll, request_scroll

KIND_LABELS = {
    "nuevo": "nuevo", "refina": "refina uno existente", "cubierto": "ya cubierto", "contradice": "contradice uno existente",
    "divide": "divide uno existente", "fusiona": "fusiona existentes", "incierto": "incierto (lo decide una persona)",
}
SHORT = {"nuevo": "Nuevo", "refina": "Refina", "cubierto": "Cubierto", "contradice": "Contradice", "divide": "Divide", "fusiona": "Fusiona", "incierto": "Incierto"}
ROLE_NAMES = {"product_owner": "product owner", "service_manager": "service manager", "full_stack_ia_engineer": "ingeniero"}
ALL = "Todas"
MEETING_TYPES = (SourceType.REUNION, SourceType.MINUTA)
BATCH_THRESHOLDS = (0.9, 0.8, 0.7)


def _tag(kind: str) -> str:
    return f'<span class="bg-tag {kind}">{SHORT[kind]}</span>'


def _role(role: str) -> str:
    return ROLE_NAMES.get(role, role)


def _fmt(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def confidence_level(value: float) -> tuple[str, str]:
    """Color y nivel de la barra de confianza: rojo bajo el mínimo (0,70), amarillo hasta 0,79, verde desde 0,80."""
    if value < 0.70:
        return "#b3261e", "baja"
    if value < 0.80:
        return "#e0a100", "media"
    return "#3f7d12", "alta"


def _baseline(controller: RunController, library: SourceLibrary):
    presales = [i for i, m in library.describe() if m.source_type is SourceType.PREVENTA]
    if len(presales) != 1:
        return None
    return BaselineStore(baseline_dir(controller.data_dir)).current(library.load(presales[0]))


def _resolved_label(p: Proposal) -> tuple[str, str]:
    if p.state is ProposalState.RECHAZADA:
        return "Rechazada", "no"
    return ("Cubierto, automático" if p.decided_by == "automático" else "Aprobada"), "ok"


def _select(proposal_id: str) -> None:
    st.session_state["rev_sel"] = proposal_id


# ---- Revisión ----


def tab_review(controller: RunController, who) -> None:
    catalog = controller.deps.catalog
    library = SourceLibrary(user_sources_dir(controller.data_dir))
    meetings = [i for i, m in library.describe() if m.source_type in MEETING_TYPES] if library.root.is_dir() else []
    with_proposals = [i for i in meetings if catalog is not None and catalog.proposals(source_id=i)]
    if not with_proposals:
        st.info("Todavía no hay propuestas para revisar. Leé una reunión contra el catálogo en la pestaña «Fuentes».")
        return
    names = {i: m for i, m in library.describe()}
    if st.session_state.get("rev_reunion") not in with_proposals:  # al entrar, la primera reunión que tiene pendientes (después se respeta lo que elija la persona)
        st.session_state["rev_reunion"] = next(
            (i for i in with_proposals if catalog.proposals(state=ProposalState.PENDIENTE, source_id=i)), with_proposals[0]
        )
    meeting = st.selectbox(
        "Reunión", with_proposals, key="rev_reunion",
        format_func=lambda i: f"{names[i].source_name} · {names[i].source_date}",
    )
    all_props = catalog.proposals(source_id=meeting)
    open_props = [p for p in all_props if p.state is ProposalState.PENDIENTE]
    done_props = [p for p in all_props if p.state is not ProposalState.PENDIENTE]
    ok_count = sum(1 for p in done_props if p.state is not ProposalState.RECHAZADA)
    with st.container(key="rev_metrics"):
        columns = st.columns(3)
        columns[0].metric("Pendientes", len(open_props))
        columns[1].metric("Aprobadas", ok_count)
        columns[2].metric("Rechazadas", len(done_props) - ok_count)
    st.markdown(
        f'<span class="bg-role">Actuás como {escape(_role(who.role))}</span>'
        '<div class="bg-role-note">Cada propuesta la decide el rol que le corresponde; se guarda el rol, no el nombre.</div>',
        unsafe_allow_html=True,
    )
    if st.session_state.get("rev_msg"):
        st.success(st.session_state.pop("rev_msg"))

    batch_section(catalog, meeting, who)

    kinds = [k for k in KIND_LABELS if any(p.kind.value == k for p in open_props)]
    picked = st.pills("Tipo", [ALL] + [SHORT[k] for k in kinds], default=ALL, key="rev_filtro", label_visibility="collapsed") or ALL
    shown = [p for p in open_props if picked == ALL or SHORT[p.kind.value] == picked]
    if st.session_state.get("rev_sel") not in {p.id for p in all_props}:
        st.session_state["rev_sel"] = (shown or all_props)[0].id
    baseline = _baseline(controller, library)
    commitments = {c.id: c for c in baseline.commitments} if baseline else {}

    left, right = st.columns([1, 1.7], gap="large")
    with left:
        if not shown:
            st.info("No quedan propuestas pendientes con este filtro.")
        for p in shown:
            conf = f" · {_fmt(p.confidence)}" if p.confidence is not None else ""
            title = p.drafts[0].title if p.drafts else p.evidence[0].quote
            st.button(
                f"{p.id} · {SHORT[p.kind.value]}{conf}\n\n{title[:90]}", key=f"sel-{p.id}", width="stretch",
                type="primary" if st.session_state["rev_sel"] == p.id else "secondary", on_click=_select, args=(p.id,),
            )
        if done_props:
            with st.expander(f"Resueltas · {len(done_props)}"):
                for p in done_props:
                    label, _ = _resolved_label(p)
                    st.button(f"{p.id} · {label}", key=f"sel-{p.id}", width="stretch", on_click=_select, args=(p.id,))
    with right:
        anchor(REVIEW)
        chosen = next(p for p in all_props if p.id == st.session_state["rev_sel"])
        detail(catalog, chosen, who, commitments, shown)
    apply_scroll(REVIEW)


def batch_section(catalog, meeting: str, who) -> None:
    eligible_all = pending_batch(catalog, meeting)
    if not eligible_all:
        return
    with st.expander("Aprobar varias a la vez"):
        threshold = st.selectbox("Nuevos y refinamientos con confianza de al menos", BATCH_THRESHOLDS, index=1, format_func=_fmt, key="rev_umbral")
        eligible = [p for p in eligible_all if p.confidence is not None and p.confidence >= threshold]
        pending_total = len(catalog.proposals(state=ProposalState.PENDIENTE, source_id=meeting))
        st.write(f"**{len(eligible)} de {pending_total}** pendientes entran en este lote.")
        st.caption(
            f"Quedan fuera y se deciden una por una: {pending_total - len(eligible)} (contradicciones, inciertos, reuniones fuera de orden y confianza menor). "
            "Nada se aprueba hasta que confirmes."
        )
        can = who.role == "product_owner"
        if not can:
            st.warning(f"El lote lo decide el product owner. Estás como {_role(who.role)}.")
        if st.button("Aprobar ese lote", key="rev_lote", type="primary", disabled=not eligible or not can):
            try:
                result = decide_batch(catalog, [p.id for p in eligible], approve=True, role=who.role)
            except CatalogError as exc:
                st.error(str(exc))
                return
            st.session_state["rev_msg"] = f"{len(result.applied)} propuestas aprobadas en lote y aplicadas al catálogo."
            st.rerun()


def _advance(catalog, proposal: Proposal, shown: list[Proposal]) -> None:
    """Pasa a la siguiente pendiente de la lista (la que sigue a la decidida; si no hay, la primera que quede)."""
    ids = [p.id for p in shown]
    position = ids.index(proposal.id) + 1 if proposal.id in ids else 0
    order = shown[position:] + shown[:position]
    remaining = [p for p in order if p.id != proposal.id and catalog.proposal(p.id).state is ProposalState.PENDIENTE]
    st.session_state["rev_sel"] = remaining[0].id if remaining else proposal.id
    request_scroll(REVIEW)  # la pantalla sube hasta el título de la siguiente


CONFIDENCE_IN = {"nuevo": "es nuevo", "refina": "refina uno existente", "cubierto": "ya está cubierto", "contradice": "contradice lo aprobado"}
LINKS_MARK = " | Vínculos con la propuesta:"


def reason_parts(p: Proposal, commitments: dict | None = None) -> tuple[str, list[str]]:
    """El motivo separado en lo que se comparó con el catálogo y lo que se comparó con la preventa (una línea por vínculo, con el título del compromiso)."""
    catalog_text = (p.rationale or "").split(LINKS_MARK, 1)[0].strip()
    lines = []
    for l in p.links:
        found = (commitments or {}).get(l.commitment_id)
        name = f"**{l.commitment_id}** «{found.capability}»" if found else f"**{l.commitment_id}**"
        if l.relation == "mismo":
            lines.append(f"{name} confirmado" + (f" · difiere: {l.difference}" if l.difference else " · dice lo mismo que se vendió"))
        elif l.relation == "distinto":
            lines.append(f"{name} descartado · {l.reason or 'es de otro tema'}")
        else:
            lines.append(f"{name} sin verificar")
    if not lines and LINKS_MARK in (p.rationale or ""):  # propuestas viejas, sin los vínculos guardados
        lines.append((p.rationale or "").split(LINKS_MARK, 1)[1].strip())
    return catalog_text, lines


def link_difference(p: Proposal, commitment_id: str) -> str:
    """Qué difiere entre lo que se dijo y el compromiso vendido, o que no difiere. Las propuestas viejas la sacan del motivo."""
    for l in p.links:
        if l.commitment_id == commitment_id:
            if l.relation == "mismo":
                return l.difference or "ninguna detectada: la reunión pide lo mismo que se vendió."
            return "sin verificar." if l.relation == "sin verificar" else "no es el mismo compromiso."
    match = re.search(rf"{re.escape(commitment_id)} confirmado(?: \(([^)]*)\))?", p.rationale or "")
    if match and match.group(1):
        return match.group(1).removeprefix("difiere: ").strip() or "ninguna detectada."
    return "ninguna detectada." if match else "sin verificar."


def detail(catalog, p: Proposal, who, commitments: dict, shown: list[Proposal]) -> None:
    title = p.drafts[0].title if p.drafts else p.evidence[0].quote[:120]
    with st.container(border=True):
        target = f" · sobre {', '.join(p.targets)}" if p.targets else ""
        st.markdown(f"### {escape(title)}")
        st.markdown(f'<b>{p.id}</b> {_tag(p.kind.value)}{escape(target)}' + (" · reunión fuera de orden" if p.out_of_order else ""), unsafe_allow_html=True)

        first = p.evidence[0]
        st.markdown('<div class="bg-label">Qué se dijo</div>', unsafe_allow_html=True)
        st.markdown(f'<blockquote class="bg-quote">«{escape(first.quote)}»</blockquote>', unsafe_allow_html=True)
        st.caption(f"{first.speaker or 'sin orador'} · {first.source_name} · {first.source_date}")

        linked = [commitments[c] for c in (p.drafts[0].commitment_ids if p.drafts else []) if c in commitments]
        if linked:
            st.markdown('<div class="bg-label">Compromiso vendido al que se liga</div>', unsafe_allow_html=True)
            for c in linked:
                where = f"preventa, p. {c.page}" if c.page else "preventa"
                st.markdown(f'<div class="bg-commit"><b>{escape(c.id)}</b>{escape(c.capability)} <span style="color:#5d5b7a">· {where}</span></div>', unsafe_allow_html=True)
                st.markdown(f'<blockquote class="bg-quote">«{escape(c.quote)}»</blockquote>', unsafe_allow_html=True)
                st.markdown(f"**Diferencia con lo dicho:** {link_difference(p, c.id)}")
        dropped = [l for l in p.links if l.relation == "distinto"]
        if dropped:
            with st.expander(f"Vínculos que se descartaron · {len(dropped)}"):
                for l in dropped:
                    capability = commitments[l.commitment_id].capability if l.commitment_id in commitments else ""
                    st.markdown(f"- **{l.commitment_id}** {escape(capability)}: {escape(l.reason or 'es de otro tema')}")

        if p.confidence is not None:
            about = CONFIDENCE_IN.get(p.kind.value)
            st.markdown(f'<div class="bg-label">{"Confianza en que " + about if about else "Confianza del clasificador"}</div>', unsafe_allow_html=True)
            color, level = confidence_level(p.confidence)
            ok = p.confidence >= 0.70
            text = f"{_fmt(p.confidence)} · {level} · " + ("supera el mínimo de 0,70" if ok else "por debajo del mínimo de 0,70: por eso se propone como incierto")
            st.markdown(
                f'<div style="background:#e4e2f2;border-radius:6px;height:12px;overflow:hidden">'
                f'<div style="width:{p.confidence * 100:.0f}%;background:{color};height:100%"></div></div>'
                f'<div style="font-size:14px;margin-top:4px">{escape(text)}</div>',
                unsafe_allow_html=True,
            )
        if p.rationale:
            catalog_text, preventa_lines = reason_parts(p, commitments)
            st.markdown('<div class="bg-label">Por qué</div>', unsafe_allow_html=True)
            if preventa_lines:
                st.markdown(f"**Frente al catálogo:** {catalog_text}")
                st.markdown("**Frente a la preventa:**\n" + "\n".join(f"- {line}" for line in preventa_lines))
            else:
                st.write(catalog_text)

        if p.state is not ProposalState.PENDIENTE:
            label, style = _resolved_label(p)
            who_ = "automáticamente" if p.decided_by == "automático" else f"por el {_role(p.decided_by or '')}"
            note = f" Nota: {p.note}" if p.note else ""
            (st.success if style == "ok" else st.error)(f"{label} {who_}." + (f" Quedó en {', '.join(p.affected)}." if p.affected else "") + note)
            if p.state is ProposalState.RECHAZADA:
                needed = decider_role(p)
                can = who.role == needed
                if not can:
                    st.caption(f"Reabrirla lo decide el {_role(needed)}. Estás como {_role(who.role)}.")
                if st.button("Reabrir (volver a dejarla pendiente)", key=f"reabrir-{p.id}", disabled=not can):
                    catalog.reopen(p.id, by=who.role)
                    st.session_state["rev_msg"] = f"{p.id} reabierta: quedó pendiente para decidirla de nuevo."
                    st.rerun()
            return
        decision_controls(catalog, p, who, shown)


def decision_controls(catalog, p: Proposal, who, shown: list[Proposal]) -> None:
    needed = decider_role(p)
    can = who.role == needed
    try:
        if p.kind is ProposalKind.INCIERTO:
            incierto_controls(catalog, p, can, shown)
        else:
            edited = None
            if p.kind in (ProposalKind.NUEVO, ProposalKind.REFINA) and p.drafts:
                st.markdown('<div class="bg-label">Requisito que se guardaría</div>', unsafe_allow_html=True)
                title = st.text_input("Título", p.drafts[0].title, key=f"titulo-{p.id}")
                description = st.text_area("Descripción", p.drafts[0].description, key=f"desc-{p.id}")
                if (title, description) != (p.drafts[0].title, p.drafts[0].description):
                    edited = Draft(title=title, description=description, acceptance_criteria=p.drafts[0].acceptance_criteria, commitment_ids=p.drafts[0].commitment_ids)
            note = st.text_input("Nota de la decisión (opcional)", key=f"nota-{p.id}")
            if not can:
                st.warning(f"Lo decide el {_role(needed)}. Estás como {_role(who.role)}.")
            ok, no, _ = st.columns([1.2, 1, 2])
            approve_label = "Aprobar el cambio de alcance" if p.kind is ProposalKind.CONTRADICE else "Aprobar"
            if ok.button(approve_label, key=f"aprobar-{p.id}", type="primary", disabled=not can):
                if edited:
                    catalog.edit(p.id, edited)
                decide_one(catalog, p.id, approve=True, role=who.role, note=note)
                st.session_state["rev_msg"] = f"{p.id} aprobada y aplicada al catálogo."
                _advance(catalog, p, shown)
                st.rerun()
            if no.button("Rechazar", key=f"rechazar-{p.id}", disabled=not can):
                decide_one(catalog, p.id, approve=False, role=who.role, note=note)
                st.session_state["rev_msg"] = f"{p.id} rechazada."
                _advance(catalog, p, shown)
                st.rerun()
    except (CatalogError, ValidationError) as exc:
        st.error(str(exc))


def incierto_controls(catalog, p: Proposal, can: bool, shown: list[Proposal]) -> None:
    st.markdown('<div class="bg-label">Resolver</div>', unsafe_allow_html=True)
    st.caption("Un incierto no se aprueba tal cual: decidí qué es, o descartalo.")
    option = st.radio(
        "Resolver como", ["nuevo", "refina", "cubierto"], horizontal=True, key=f"como-{p.id}", label_visibility="collapsed",
        format_func=lambda k: {"nuevo": "Es un requisito nuevo", "refina": "Refina uno existente", "cubierto": "Ya está cubierto"}[k],
    )
    target = None
    if option != "nuevo":
        active = {r.id: r.current.draft.title for r in catalog.requirements() if r.status.value == "activo"}
        if active:
            target = st.selectbox("Requisito destino", list(active), key=f"destino-{p.id}", format_func=lambda rid: f"{rid} · {active[rid]}")
        else:
            st.info("Todavía no hay requisitos activos a los que ligarlo.")
    if not can:
        st.warning(f"Lo decide el {_role(decider_role(p))}.")
    left, right, _ = st.columns([1, 1, 2])
    if left.button("Reclasificar", key=f"reclasificar-{p.id}", type="primary", disabled=not can or (option != "nuevo" and not target)):
        catalog.reclassify(p.id, ProposalKind(option), target=target)
        st.session_state["rev_msg"] = f"{p.id} reclasificada como «{option}»: ahora la podés aprobar."
        st.rerun()
    if right.button("Descartar", key=f"descartar-{p.id}", disabled=not can):
        decide_one(catalog, p.id, approve=False, role=decider_role(p))
        st.session_state["rev_msg"] = f"{p.id} descartada."
        _advance(catalog, p, shown)
        st.rerun()


# ---- Catálogo ----


def coverage_section(controller: RunController, catalog) -> None:
    """Lo vendido frente a lo tratado, solo lectura. Es lo mismo que recibe el Auditor: cada lista es un candidato, no un hallazgo."""
    baseline = _baseline(controller, SourceLibrary(user_sources_dir(controller.data_dir)))
    if baseline is None:
        return
    coverage = build_coverage(baseline, catalog)
    with st.expander(f"Cobertura de lo vendido · {len(baseline.commitments)} compromisos"):
        st.caption("Cruce de los compromisos de la preventa con los requisitos aprobados. Son candidatos para el Auditor, no hallazgos.")
        for warning in coverage.warnings:
            st.warning(warning)
        columns = st.columns(4)
        columns[0].metric("Cubiertos", len(coverage.covered))
        columns[1].metric("Vendido sin tratar", len(coverage.vendido_sin_requisito))
        columns[2].metric("Pedido y no vendido", len(coverage.requisitos_sin_compromiso))
        columns[3].metric("Vendido como excluido", len(coverage.excluidos_con_requisito))
        sections = (
            ("Vendido y sin requisito", [(r["id"], r["epica"], r["capacidad"], f"pág. {r['pagina']}") for r in coverage.vendido_sin_requisito]),
            ("Pedido en reuniones y no figura en la preventa", [(r["id"], r["titulo"], f"v{r['version']}", "") for r in coverage.requisitos_sin_compromiso]),
            ("La preventa lo excluía y hay un requisito", [(r["id"], r["epica"], r["capacidad"], ", ".join(x["id"] for x in r["requisitos"])) for r in coverage.excluidos_con_requisito]),
            ("Lo cubría una versión que ya no rige", [(r["id"], r["epica"], r["capacidad"], ", ".join(x["id"] for x in r["antes"])) for r in coverage.cobertura_perdida]),
        )
        for title, rows in sections:
            if rows:
                st.markdown(f'<div class="bg-label">{title}</div>', unsafe_allow_html=True)
                st.dataframe([{"id": a, "detalle": b, "descripción": c, "ref.": d} for a, b, c, d in rows], width="stretch", hide_index=True)
        if coverage.condiciones:
            st.caption(f"{len(coverage.condiciones)} supuestos o dependencias de la propuesta no se cuentan como «vendido y no tratado».")


def tab_catalog(controller: RunController) -> None:
    catalog = controller.deps.catalog
    if catalog is None:
        st.info("Esta corrida no tiene catálogo.")
        return
    st.caption("La memoria del proyecto: cada requisito tiene un identificador que no cambia, sus versiones y las citas que lo sostienen. Se conserva entre corridas.")
    requirements = catalog.requirements()
    columns = st.columns(4)
    columns[0].metric("Requisitos activos", sum(1 for r in requirements if r.status.value == "activo"))
    columns[1].metric("Versiones", sum(len(r.versions) for r in requirements))
    columns[2].metric("Evidencias", sum(len(r.current.evidence) + len(r.conflicts) for r in requirements))
    columns[3].metric("Propuestas pendientes", len(catalog.proposals(state=ProposalState.PENDIENTE)))
    coverage_section(controller, catalog)
    if not requirements:
        st.info("Todavía no hay requisitos. Se crean cuando aprobás propuestas en «Revisión».")
        return
    st.dataframe(
        [
            {
                "id": r.id, "estado": r.status.value, "versión": f"v{r.current.number}", "requisito": r.current.draft.title,
                "compromisos": ", ".join(r.current.draft.commitment_ids) or "—", "evidencias": len(r.current.evidence),
            }
            for r in requirements
        ],
        width="stretch", hide_index=True,
    )
    for r in requirements:
        with st.expander(f"{r.id} · v{r.current.number} · {r.current.draft.title}"):
            if r.replaced_by:
                st.caption(f"Estado: {r.status.value}. Lo reemplaza: {', '.join(r.replaced_by)}.")
            st.markdown('<div class="bg-label">Historial</div>', unsafe_allow_html=True)
            for v in reversed(r.versions):
                st.markdown(f"**v{v.number}** · {v.relation.value} · aprobada por el {_role(v.approved_by)} · {v.created_at[:10]}")
                if v.draft.description:
                    st.caption(v.draft.description)
            st.markdown('<div class="bg-label">Evidencia</div>', unsafe_allow_html=True)
            for e in r.current.evidence:
                st.markdown(f'<blockquote class="bg-quote">«{escape(e.quote)}»</blockquote>', unsafe_allow_html=True)
                st.caption(f"{e.speaker or 'sin orador'} · {e.source_name} · {e.source_date} · {e.role.value}")
            for e in r.conflicts:
                st.markdown(f'<blockquote class="bg-quote" style="border-left-color:#b3261e">«{escape(e.quote)}»</blockquote>', unsafe_allow_html=True)
                st.caption(f"Contradice · {e.speaker or 'sin orador'} · {e.source_name} · {e.source_date}")
