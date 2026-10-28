"""Pantalla de BacklogGuard (Streamlit): la corrida en vivo y las decisiones de cada persona.

    .venv\\Scripts\\streamlit run src/backlogguard/ui/app.py

Con LIVE_MODE=1 usa los modelos reales; con LIVE_MODE=0 reproduce la corrida grabada en
`evals/recordings/demo_acme.json` (sin red ni costo). No hay autenticación: la persona se elige en la
barra lateral y solo ve los pedidos que le corresponden por su rol.
"""
from __future__ import annotations

import re
from datetime import date

import streamlit as st

from backlogguard.board import Board, SourceType
from backlogguard.catalog.ingest import estimate_ingest, ingest_meeting
from backlogguard.graph.setup import baseline_dir, has_user_sources, user_sources_dir
from backlogguard.graph.tasks import KIND_TITLES, PARTIES, summarize_tasks
from backlogguard.llm.metering import load_pricing
from backlogguard.rag import SourceLibrary, build_chunks
from backlogguard.rag.compromisos import BaselineStore, estimate_extraction, extract_commitments
from backlogguard.rag.importers import SourceImportError, estimate, import_pdf, import_transcript
from backlogguard.rag.sources import SourceChangeNeedsConfirmation, SourceMetadata, SourceUnchanged, slugify
from backlogguard.ui.controller import DEFAULT_OBJECTIVE, RunController
from backlogguard.ui.conversation_view import live_conversation, tab_conversation
from backlogguard.ui.guide import ADVANCED_TABS, AVANZADO, CORRIDA, DECISIONES, FUENTES, HELP, HISTORIAS, REVISION, TABS, render_guide
from backlogguard.ui.revision import KIND_LABELS, tab_catalog, tab_review
from backlogguard.ui.runtime import make_controller
from backlogguard.ui.story_view import current_baseline, is_story, render_story
from backlogguard.ui.theme import apply_theme, top_band

SOURCE_LABELS = {"preventa": "Línea base (preventa)", "reunion": "Evidencia (reunión)", "minuta": "Evidencia (minuta)"}
ROLE_LABELS = {"linea_base": "Línea base", "evidencia": "Evidencia"}
STATE_LABELS = {
    "borrador": "borrador", "objetado": "objetado", "sustentado": "sustentado", "aprobado": "aprobado", "excluido": "excluido",
}
STATUS_TEXT = {
    "en_curso": "en curso",
    "esperando_decision": "esperando una decisión de una persona (mirá «Qué sigue», arriba)",
    "plan_pendiente_de_aprobacion": "esperando que se apruebe el plan de publicación",
    "publicada": "plan publicado en el backlog",
    "plan_rechazado": "plan rechazado: no se publicó nada",
    "publicacion_detenida": "publicación detenida",
    "completada": "completada",
    "completada_con_errores": "completada con errores",
    "presupuesto_agotado": "presupuesto agotado",
}
TASK_STATUS = {
    "hecha": "hecha", "con_aviso": "hecha con aviso", "incompleta": "incompleta", "fallida": "falló",
    "sin_correccion": "sin corrección", "escalada": "escalada a una persona",
}
NODE_ORDER = ["plan", "produce", "review", "audit", "escalate", "decide", "integrate", "approve_plan", "summarize"]
NODE_NAMES = {
    "plan": "Plan", "produce": "Redacción", "review": "Revisión", "audit": "Auditoría", "escalate": "Pedidos",
    "decide": "Decisiones", "integrate": "Plan de publicación", "approve_plan": "Aprobación", "summarize": "Resumen",
}


# ---- piezas ----


def date_from_filename(name: str) -> date | None:
    """«2026-08-21 Daily …vtt» propone 2026-08-21; la persona lo confirma o lo corrige."""
    found = re.search(r"(\d{4})-(\d{2})-(\d{2})", name)
    try:
        return date(int(found[1]), int(found[2]), int(found[3])) if found else None
    except ValueError:
        return None


def render_status(controller: RunController) -> None:
    state = controller.state()
    status = state.get("status", "sin corrida")
    if controller.running:
        st.info(f"Los agentes están trabajando… ({len(controller.events)} eventos)")
    elif controller.error:
        st.error(f"La corrida falló: {controller.error}")
    else:
        if status in ("publicada", "completada"):
            st.success(f"Estado: {STATUS_TEXT.get(status, status)}")
        else:
            st.write(f"**Estado:** {STATUS_TEXT.get(status, status)}")
    visited = [event["node"] for event in state.get("trace", [])]
    if visited:
        steps = [("✔ " if node in visited else "· ") + NODE_NAMES[node] for node in NODE_ORDER]
        st.caption("  →  ".join(steps))


@st.fragment(run_every=1.5)
def live_status(controller: RunController) -> None:
    was_running = st.session_state.get("_was_running", False)
    st.session_state["_was_running"] = controller.running
    render_status(controller)
    if was_running and not controller.running:
        st.rerun()  # terminó el trabajo: se refrescan las pestañas (decisiones, tablero, backlog)


def evidence_cards(evidence: list[dict]) -> None:
    for entry in evidence:
        st.markdown(f"> {entry['quote']}")
        where = f" · p. {entry['page']}" if entry.get("page") else ""
        label = SOURCE_LABELS.get(entry.get("source_type") or "", "")
        st.caption(f"{label + ' · ' if label else ''}{entry['source_name']} · {entry['source_date']}{where} · {entry.get('speaker') or 's/d'}")


def decision_payload(request: dict, who, action: str, comment: str, edited: dict | None) -> dict:
    return {
        "decision": action, "actor": who.name, "actor_role": who.role, "request_id": request["request_id"],
        "request_version": request["version"], "args_hash": request["args_hash"], "edited": edited, "comment": comment,
    }


def edit_fields(request: dict) -> tuple[dict, dict]:
    """Campos editables según el tipo de pedido. Devuelve (valores actuales, valores ingresados)."""
    key = f"{request['request_id']}-v{request['version']}"
    payload = request["payload"]
    if request["kind"] == "alcance":
        current = {"decision_text": payload["decision_text"]}
        typed = {"decision_text": st.text_area("Texto de la decisión", current["decision_text"], key=f"{key}-texto")}
    elif request["kind"] == "item":
        current = {
            "title": payload["title"], "description": payload["description"],
            "acceptance_criteria": list(payload["acceptance_criteria"]),
        }
        criteria = st.text_area("Criterios de aceptación (uno por línea)", "\n".join(current["acceptance_criteria"]), key=f"{key}-criterios")
        typed = {
            "title": st.text_input("Título", current["title"], key=f"{key}-titulo"),
            "description": st.text_area("Descripción", current["description"], key=f"{key}-descripcion"),
            "acceptance_criteria": [line.strip() for line in criteria.splitlines() if line.strip()],
        }
    else:
        options = [item["item_id"] for item in payload["items"] if item["action"] != "omitir"]
        titles = {item["item_id"]: item["title"] for item in payload["items"]}
        current = {"exclude": list(payload["exclude"])}
        typed = {"exclude": st.multiselect("Excluir del plan", options, default=current["exclude"], format_func=lambda i: titles[i], key=f"{key}-excluir")}
    return current, typed


def decision_form(controller: RunController, who, payload: dict) -> None:
    request = payload["request"]
    st.subheader(request["title"])
    if payload.get("last_error"):
        st.warning(f"Tu última decisión no se aplicó: {payload['last_error']}")
    st.caption(f"Pedido {request['request_id']} · versión {request['version']} · lo decide: {request['decides']}")
    st.text(request["summary"])
    if request["evidence"]:
        st.markdown("**Evidencia**")
        evidence_cards(request["evidence"])
    with st.form(f"form-{request['request_id']}-v{request['version']}"):
        current, typed = edit_fields(request)
        comment = st.text_input("Comentario (opcional)", key=f"{request['request_id']}-v{request['version']}-comentario")
        approve, edit, reject = st.columns(3)
        approved = approve.form_submit_button("Aprobar", type="primary", key="aprobar", width="stretch")
        edited = edit.form_submit_button("Guardar edición (nueva versión)", key="editar", width="stretch")
        rejected = reject.form_submit_button("Rechazar", key="rechazar", width="stretch")
    if approved or rejected:
        controller.decide(decision_payload(request, who, "approve" if approved else "reject", comment, None))
        st.rerun()
    if edited:
        changes = {name: value for name, value in typed.items() if value != current[name]}
        if not changes:
            st.warning("No cambiaste nada: no hay nada que editar.")
        else:
            controller.decide(decision_payload(request, who, "edit", comment, changes))
            st.rerun()


def tab_run(controller: RunController) -> None:
    live_conversation(controller)
    waiting = controller.pending() is not None
    st.write(f"Modo: **{controller.mode}**" + (" (reproduce una corrida grabada, sin costo)" if controller.mode == "demo" else ""))
    if controller.mode == "simulado":
        st.warning("Sin modelos reales ni grabación: los agentes no van a producir nada útil. Activá LIVE_MODE=1 o grabá una demo.")
    own = controller.using_own_sources
    objective = st.text_area("Objetivo de la corrida", DEFAULT_OBJECTIVE, key="objetivo")
    if own:
        summary = controller.catalog_summary()
        if summary["active"]:
            st.info(
                f"La corrida parte de los **{summary['active']} requisitos aprobados** del catálogo: {summary['to_publish']} por redactar y publicar "
                f"(nuevos o con versión nueva), {summary['published']} ya publicados. Las fuentes (pestaña «Fuentes») sirven de respaldo."
            )
        else:
            st.warning(
                "Todavía no hay requisitos aprobados, y la corrida parte de ellos. Leé una reunión contra el catálogo en «Fuentes» "
                "y aprobá sus propuestas en «Revisión»."
            )
        needs_models = controller.mode != "real" or not summary["active"]
        if controller.mode != "real":
            st.error("Con fuentes propias hace falta LIVE_MODE=1 (modelos reales): la corrida grabada no sabe responder a documentos nuevos.")
        elif summary["active"]:
            st.warning(
                "Esta corrida usa modelos reales y **gasta tokens**. "
                f"Tope por corrida: {controller.deps.budget.max_tokens:,} tokens. Los textos se envían a los proveedores de los modelos."
            )
        seed = False
    else:
        needs_models = False
        seed = st.checkbox("Cargar work items de ejemplo cargados a mano (sirven para ver un posible duplicado)", value=True, key="semilla")
    if st.button("Iniciar corrida", type="primary", key="iniciar", disabled=controller.running or waiting or needs_models):
        controller.start(objective, seed=seed)
        st.rerun()
    if waiting:
        st.caption("La corrida está pausada: falta una decisión. Seguí desde «Mis decisiones».")
    state = controller.state()
    if state.get("summary"):
        st.markdown("**Resumen del Supervisor**")
        st.write(state["summary"])
    if state:
        st.caption(f"Tokens usados: {state.get('tokens', 0)}")
    incomplete = [t for t in state.get("tasks", []) if t["kind"] == "redactar" and t["status"] == "incompleta"]
    if incomplete:
        st.warning(
            "Redacción incompleta: el productor se quedó sin pasos o tokens antes de terminar "
            f"({incomplete[0]['stop_reason']}). Puede haber requisitos sin cubrir."
        )
    if state.get("stop_reason"):
        st.warning(f"La corrida se cortó por presupuesto agotado ({state['stop_reason']}): puede haber ítems sin revisar.")
    for error in state.get("errors", []):
        st.error(f"{error['node']} ({error.get('ref')}): {error['error']}")
    sources = state.get("sources")
    if sources:
        st.markdown("**Fuentes usadas en esta corrida**")
        checks = {True: "sí", False: "NO", None: "—"}
        st.dataframe(
            [{"rol": ROLE_LABELS.get(s["role"], s["role"]), "fuente": s["name"], "tipo": s["type"], "fecha": s["date"],
              "huella": s["fingerprint"], "verificada": checks[s["fingerprint_ok"]], "palabras": s["words"]} for s in sources],
            width="stretch", hide_index=True,
        )
        if any(s["fingerprint_ok"] is False for s in sources):
            st.warning("Alguna fuente se editó a mano después de importarla: su huella no coincide con la que se guardó.")


def tab_runs(controller: RunController) -> None:
    st.caption(
        "Corridas guardadas, de esta pantalla o de un script. Al abrir una se muestra su tablero, sus hallazgos, "
        "las decisiones y el backlog resultante. Es de solo lectura."
    )
    runs = controller.list_runs()
    if not runs:
        st.info("Todavía no hay corridas guardadas.")
        return
    st.dataframe(
        [{"corrida": r["thread_id"], "momento": r["created_at"], "estado": STATUS_TEXT.get(r["status"], r["status"]),
          "ítems": r["items"], "tareas": r["tasks"], "correcciones": r["corrections"], "tokens": r["tokens"], "espera una decisión": "sí" if r["waiting"] else ""} for r in runs],
        width="stretch", hide_index=True,
    )
    chosen = st.selectbox("Corrida a abrir", [r["thread_id"] for r in runs], key="corrida_guardada")
    if st.button("Abrir (solo lectura)", key="abrir_corrida", disabled=controller.running):
        controller.open_run(chosen)
        st.rerun()
    waiting = {r["thread_id"] for r in runs if r["waiting"]}
    if st.button("Retomar y decidir lo pendiente", key="retomar_corrida", disabled=controller.running or chosen not in waiting):
        controller.resume_run(chosen)
        st.rerun()
    if waiting:
        st.caption("Una corrida que espera una decisión se retoma desde acá; los pedidos aparecen en «Mis decisiones», de a uno y cada uno para el rol que le corresponde.")
    if controller.read_only:
        st.info(f"Estás viendo la corrida **{controller.thread_id}** (solo lectura). «Iniciar corrida» vuelve al modo normal.")


def tab_tasks(controller: RunController) -> None:
    st.caption(
        "El backlog de la corrida: cada tarea que un agente le pasa a otro (o a una persona), en orden, con lo que costó en tokens. "
        "Mirá una corrida guardada abriéndola en «Corridas guardadas»."
    )
    tasks = controller.state().get("tasks", [])
    if not tasks:
        st.info("Esta corrida todavía no tiene tareas registradas (o es anterior a este registro).")
        return
    totals = summarize_tasks(tasks)
    columns = st.columns(6)
    columns[0].metric("Tareas", totals["tasks"])
    columns[1].metric("Pedidos de corrección", totals["corrections"])
    columns[2].metric("Correcciones logradas", totals["corrections_ok"])
    columns[3].metric("Reintentos frenados por el tope", totals["rejected"])
    columns[4].metric("Tokens (entrada + salida)", f"{totals['tokens']:,}".replace(",", "."))
    columns[5].metric("Costo estimado", f"US$ {totals['cost']:.2f}")
    if totals["unpriced_models"]:
        st.caption("Sin precio en config/pricing.yaml, no se suman al costo: " + ", ".join(totals["unpriced_models"]))
    left, right = st.columns(2)
    with left:
        st.markdown("**Gasto por agente que hizo la tarea**")
        st.dataframe(
            [{"agente": r["agente"], "tareas": r["tareas"], "entrada": r["entrada"], "salida": r["salida"], "tokens": r["tokens"],
              "% del gasto": f"{r['parte']:.0%}", "US$": r["costo"]} for r in totals["by_agent"]],
            width="stretch", hide_index=True,
        )
    with right:
        st.markdown("**Quién le pasa tareas a quién**")
        st.dataframe(totals["by_pair"], width="stretch", hide_index=True)
    kinds = ["(todas)"] + sorted({KIND_TITLES.get(t["kind"], t["kind"]) for t in tasks})
    agents = ["(todos)"] + sorted({PARTIES.get(t["target"], t["target"]) for t in tasks})
    pick_kind, pick_agent = st.columns(2)
    only = pick_kind.selectbox("Tipo de tarea", kinds, key="filtro_tareas")
    agent = pick_agent.selectbox("Agente que la hizo", agents, key="filtro_agente_tareas")
    shown = [
        t for t in tasks
        if only in ("(todas)", KIND_TITLES.get(t["kind"], t["kind"])) and agent in ("(todos)", PARTIES.get(t["target"], t["target"]))
    ]
    rows = [
        {
            "tarea": t["id"],
            "de": PARTIES.get(t["origin"], t["origin"]),
            "para": PARTIES.get(t["target"], t["target"]),
            "qué": KIND_TITLES.get(t["kind"], t["kind"]),
            "ítem": t["ref"] or "",
            "ronda": t["round"] or "",
            "estado": TASK_STATUS.get(t["status"], t["status"]),
            "entrada": t.get("input_tokens", 0),
            "salida": t.get("output_tokens", 0),
            "tokens": t["tokens"],
            "llamadas": t.get("llm_calls", 0),
            "modelo": t["model"],
            "pasos": t["steps"] or "",
            "correcciones": t["corrections"] or "",
            "frenadas": t["rejected"] or "",
            "detalle": t["detail"],
        }
        for t in shown
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
    if not shown:
        return
    chosen = st.selectbox(
        "Ver el detalle de una tarea", [t["id"] for t in shown], key="detalle_tarea",
        format_func=lambda task_id: next(
            f"{t['id']} · {PARTIES.get(t['origin'], t['origin'])} → {PARTIES.get(t['target'], t['target'])} · "
            f"{KIND_TITLES.get(t['kind'], t['kind'])}" + (f" · {t['ref']}" if t["ref"] else "") for t in shown if t["id"] == task_id
        ),
    )
    task = next(t for t in shown if t["id"] == chosen)
    st.markdown(
        f"**{KIND_TITLES.get(task['kind'], task['kind'])}** · de {PARTIES.get(task['origin'], task['origin'])} "
        f"para {PARTIES.get(task['target'], task['target'])}" + (f" · ítem `{task['ref']}`" if task["ref"] else "")
        + (f" · ronda {task['round']}" if task["round"] else "")
    )
    st.caption(
        f"Estado: {TASK_STATUS.get(task['status'], task['status'])} · modelo: {task['model'] or '—'} · "
        f"entrada {task.get('input_tokens', 0):,} · salida {task.get('output_tokens', 0):,} · llamadas {task.get('llm_calls', 0)}"
        + (f" · pasos {task['steps']}" if task["steps"] else "") + (f" · cierre: {task['stop_reason']}" if task["stop_reason"] else "")
    )
    st.text_area("Detalle (objeciones, veredicto o resultado)", task["detail"] or "(sin detalle)", height=180, disabled=True, key=f"txt_{chosen}")


def tab_decisions(controller: RunController, who) -> None:
    payload = controller.pending()
    state = controller.state()
    if controller.read_only:
        st.info("Estás viendo una corrida guardada (solo lectura): acá no se puede decidir. Mirá el registro de decisiones en «Actividad».")
    elif controller.running:
        st.info("Los agentes están trabajando. Cuando necesiten una decisión, aparecerá acá.")
    elif payload is None:
        st.info("No hay pedidos pendientes." + (" La corrida terminó." if state.get("summary") else ""))
    elif payload["request"]["decides"] != who.role:
        decider = controller.deps.people.with_role(payload["request"]["decides"])[0].display
        st.info(f"Este pedido lo decide el rol **{decider}**. Cambiá el rol en la barra lateral para decidirlo.")
    else:
        decision_form(controller, who, payload)


def tab_board(controller: RunController) -> None:
    state = controller.state()
    if not state.get("board"):
        st.info("Todavía no hay tablero.")
        return
    board = Board.model_validate(state["board"])
    st.dataframe(
        [{"id": i.id, "tipo": i.kind.value, "estado": i.state.value, "título": i.title, "citas": len(i.citations),
          "aprobó": i.approved_by or ""} for i in board.items.values()],
        width="stretch", hide_index=True,
    )
    baseline = current_baseline(controller)
    for item in board.items.values():
        with st.expander(f"{item.id} · {item.state.value} · {item.title}"):
            if is_story(item):
                render_story(controller, item, baseline)
            else:
                st.write(item.description)
                for criterion in item.acceptance_criteria:
                    st.markdown(f"- {criterion}")
            if item.citations:
                st.markdown("**Trazabilidad**")
            for citation in item.citations:
                st.markdown(f"> {citation.quote}")
                where = f" · p. {citation.page}" if citation.page else ""
                label = SOURCE_LABELS.get(citation.source_type.value, "")
                st.caption(f"{label} · {citation.source_name} · {citation.source_date.isoformat()}{where} · {citation.speaker or 's/d'}")
            for objection in item.objections:
                st.caption(f"Objeción de {objection.raised_by.value} (ronda {objection.round}, {'resuelta' if objection.resolved else 'vigente'}): {objection.text}")
    if board.findings:
        st.markdown("**Hallazgos del Auditor**")
        st.dataframe(
            [{"tipo": f.kind.value, "para": f.addressee.value, "descripción": f.description} for f in board.findings],
            width="stretch", hide_index=True,
        )


def tab_backlog(controller: RunController) -> None:
    if not controller.running:
        controller.deps.backlog.reload()  # otro proceso pudo haber publicado
    before, after = st.columns(2)
    rows = lambda items: [{"#": w["id"] if isinstance(w, dict) else w.id, "tipo": (w["type"] if isinstance(w, dict) else w.type),
                           "título": (w["title"] if isinstance(w, dict) else w.title),
                           "origen": "BacklogGuard" if any(t.startswith("bg-item:") for t in (w["tags"] if isinstance(w, dict) else w.tags)) else "manual"}
                          for w in items]
    with before:
        st.markdown("**Antes de la corrida**")
        if controller.read_only:
            st.caption("No se guardó cómo estaba el backlog antes de una corrida abierta desde el historial.")
        else:
            st.dataframe(rows(controller.backlog_before), width="stretch", hide_index=True)
    with after:
        st.markdown("**Ahora**")
        st.dataframe(rows(controller.deps.backlog.search()), width="stretch", hide_index=True)
    publication = controller.state().get("publication")
    if publication:
        st.markdown("**Resultado de la publicación**")
        st.dataframe(
            [{"ítem": r["item_id"], "resultado": r["outcome"], "work item": r["remote_id"], "detalle": r["detail"]} for r in publication["results"]]
            or [{"ítem": "—", "resultado": publication.get("error", ""), "work item": "", "detalle": ""}],
            width="stretch", hide_index=True,
        )


def tab_activity(controller: RunController) -> None:
    lines = controller.activity()
    st.code("\n".join(lines) if lines else "Todavía no hay actividad.", language="text")
    decisions = controller.state().get("decisions", [])
    if decisions:
        st.markdown("**Registro de decisiones**")
        st.dataframe(
            [{"momento": d["at"][:19], "pedido": d["request_id"], "versión": d["version"], "acción": d["decision"],
              "persona": d["actor"], "rol": d["actor_role"], "aceptada": d["accepted"], "motivo del rechazo": d["error"] or "",
              "comentario": d["comment"]} for d in decisions],
            width="stretch", hide_index=True,
        )


def tab_sources(controller: RunController) -> None:
    library = SourceLibrary(user_sources_dir(controller.data_dir))
    st.caption(
        "Cargá tu preventa (PDF) y la transcripción de una reunión (texto). Se guardan en `data/fuentes/` (no se suben a git). "
        "Mientras haya al menos una preventa y una reunión, las corridas usan estas fuentes en lugar de las de ejemplo."
    )
    busy = controller.running
    kind = st.radio("¿Qué vas a cargar?", ["Preventa (PDF)", "Reunión (texto)", "Minuta (texto)"], horizontal=True, key="tipo_fuente")
    is_pdf = kind.startswith("Preventa")
    upload = st.file_uploader("Archivo", type=["pdf"] if is_pdf else ["txt", "md", "vtt"], key=f"archivo-{kind}")
    name = st.text_input("Nombre de la fuente", key=f"nombre-{kind}")
    when = st.date_input(
        "Fecha del documento", value=date_from_filename(upload.name) if upload else None, key=f"fecha-{kind}-{upload.name if upload else ''}",
        help="La fecha ordena las reuniones: usá la de la reunión, no la de hoy. Si el nombre del archivo empieza con una fecha, se propone esa.",
    )
    overwrite = st.checkbox("Reemplazar si ya existe una fuente con ese nombre", key=f"reemplazar-{kind}")
    if st.button("Importar y guardar", key="importar", disabled=busy or upload is None or not name.strip() or when is None):
        try:
            imported = import_pdf(upload.getvalue()) if is_pdf else import_transcript(upload.getvalue())
            source_type = SourceType.PREVENTA if is_pdf else (SourceType.MINUTA if kind.startswith("Minuta") else SourceType.REUNION)
            metadata = SourceMetadata(source_name=name.strip(), source_type=source_type, source_date=when, layout=imported.layout)
            document_id = slugify(name)
            saved = library.save(document_id, metadata, imported.text, replace=overwrite)
        except SourceUnchanged as exc:
            st.info(str(exc))
        except SourceChangeNeedsConfirmation as exc:
            st.warning(f"{exc} Marcá «Reemplazar si ya existe…» y volvé a importar.")
        except SourceImportError as exc:
            st.error(str(exc))
        else:
            chunks = build_chunks(document_id, imported.text, metadata.model_dump(mode="json"))
            st.success(f"{'Reemplazada' if saved.status == 'cambio' else 'Importada'} «{name.strip()}» (huella {saved.new_fingerprint}): {imported.words:,} palabras (~{estimate(imported.words)['tokens']:,} tokens), {len(chunks)} fragmentos.")
            if imported.speakers:
                st.caption("Oradores: " + "; ".join(imported.speakers))
            for warning in imported.warnings:
                st.warning(warning)
            with st.expander("Vista previa"):
                st.text(imported.text[:1800])
            controller.refresh_sources()
            st.session_state["fuentes_importadas"] = st.session_state.get("fuentes_importadas", 0) + 1
    entries = library.describe() if library.root.is_dir() else []
    st.markdown(f"**Fuentes propias: {len(entries)}**")
    if entries:
        st.dataframe(
            [{"id": r["id"], "rol": ROLE_LABELS[r["role"]], "tipo": r["type"], "fecha": r["date"], "formato": r["layout"],
              "huella": r["fingerprint"], "verificada": {True: "sí", False: "NO", None: "—"}[r["fingerprint_ok"]], "nombre": r["name"]}
             for r in library.inventory()],
            width="stretch", hide_index=True,
        )
        victim = st.selectbox("Borrar una fuente", [""] + [i for i, _ in entries], key="borrar_fuente")
        if st.button("Borrar", key="borrar", disabled=busy or not victim):
            library.delete(victim)
            if controller.deps.catalog is not None:
                controller.deps.catalog.forget_source(victim)  # su fecha ya no cuenta para ordenar las reuniones
            controller.refresh_sources()
            st.rerun()
    baseline_section(controller, library)
    meetings_section(controller, library)
    ready = has_user_sources(library.root)
    st.info(
        "Las corridas usan: **tus fuentes propias**." if ready
        else "Las corridas usan: **las fuentes de ejemplo** (faltan una preventa y una reunión propias)."
    )


SCOPE_LABELS = {"incluido": "incluido", "excluido": "excluido (no se hace)", "condicion": "condición o supuesto"}


def baseline_section(controller: RunController, library: SourceLibrary) -> None:
    """Compromisos de la preventa: se extraen una sola vez, con el gasto confirmado, y quedan ligados a su huella."""
    presales = [i for i, m in library.describe() if m.source_type is SourceType.PREVENTA] if library.root.is_dir() else []
    if not presales:
        return
    st.markdown("**Línea base: compromisos de la preventa**")
    st.caption(
        "Se extraen una sola vez con el modelo del Auditor y se reutilizan mientras la preventa no cambie. "
        "Cada compromiso lleva su página y una cita literal verificada por código; los que no se verifican se descartan y se informan."
    )
    store = BaselineStore(baseline_dir(controller.data_dir))
    for presale in presales:
        document = library.load(presale)
        status = store.status(document)
        label = {"sin_extraer": "sin extraer", "vigente": "vigente", "desactualizada": "desactualizada (la preventa cambió)"}[status]
        st.markdown(f"«{document.metadata.source_name}» · huella `{document.fingerprint}` · compromisos: **{label}**")
        if status != "vigente":
            model = getattr(controller.deps.providers.auditor, "model", "?")
            estimate = estimate_extraction(document.text, model, load_pricing())
            cost = f"~US$ {estimate['cost_usd']:.2f}" if estimate["cost_usd"] is not None else "sin precio configurado"
            st.caption(
                f"Estimación con {model}: {estimate['calls']} llamada(s), ~{estimate['input_tokens']:,} tokens de entrada y "
                f"~{estimate['output_tokens']:,} de salida, {cost}. Los textos se envían al proveedor del modelo."
            )
            if controller.mode != "real":
                st.info("La extracción necesita modelos reales (LIVE_MODE=1).")
            sure = st.checkbox("Confirmo el gasto", key=f"confirmar-linea-base-{presale}")
            if st.button("Extraer compromisos", key=f"extraer-{presale}", disabled=controller.running or controller.mode != "real" or not sure):
                with st.spinner("Extrayendo y verificando las citas…"):
                    extract_commitments(document, controller.deps.providers.auditor, store, confirmed=True, pricing=load_pricing())
                st.rerun()
        baseline = store.current(document)
        if baseline is None:
            continue
        real = f"~US$ {baseline.cost_usd:.3f}" if baseline.cost_usd is not None else "sin precio"
        st.caption(
            f"{len(baseline.commitments)} compromisos verificados, {len(baseline.discarded)} descartados · {baseline.model} · "
            f"{baseline.input_tokens:,} tokens de entrada y {baseline.output_tokens:,} de salida ({real}) · {baseline.extracted_at}"
        )
        for epic, rows in baseline.by_epic().items():
            with st.expander(f"{epic} · {len(rows)}"):
                st.dataframe(
                    [{"id": c.id, "alcance": SCOPE_LABELS[c.scope], "compromiso": c.capability, "página": c.page, "cita": c.quote} for c in rows],
                    width="stretch", hide_index=True,
                )
        if baseline.discarded:
            with st.expander(f"Descartados · {len(baseline.discarded)}"):
                st.dataframe(
                    [{"compromiso": d.capability, "página": d.page, "motivo": d.reason, "cita": d.quote} for d in baseline.discarded],
                    width="stretch", hide_index=True,
                )


MEETING_TYPES = (SourceType.REUNION, SourceType.MINUTA)


def meetings_section(controller: RunController, library: SourceLibrary) -> None:
    """Continuidad entre reuniones: cada reunión nueva se lee contra el catálogo y genera propuestas, sin aplicar nada sola."""
    meetings = [i for i, m in library.describe() if m.source_type in MEETING_TYPES] if library.root.is_dir() else []
    catalog = controller.deps.catalog
    if not meetings or catalog is None:
        return
    st.markdown("**Reuniones contra el catálogo**")
    st.caption(
        "Cada reunión se lee una sola vez: se listan sus requisitos con una cita verificada por código, se comparan con el catálogo "
        "y con la línea base, y quedan como propuestas pendientes. Solo «ya cubierto» suma evidencia sin esperar a una persona."
    )
    presales = [i for i, m in library.describe() if m.source_type is SourceType.PREVENTA]
    presale = library.load(presales[0]) if len(presales) == 1 else None
    baseline = BaselineStore(baseline_dir(controller.data_dir)).current(presale) if presale else None
    providers = controller.deps.providers
    for meeting_id in meetings:
        document = library.load(meeting_id)
        status = catalog.source_status(meeting_id, document.fingerprint)
        label = {"nueva": "sin leer", "procesada": "leída", "cambiada": "cambió desde que se leyó"}[status]
        st.markdown(f"«{document.metadata.source_name}» · {document.metadata.source_date} · huella `{document.fingerprint}` · **{label}**")
        if status != "procesada":
            models = (getattr(providers.requerimientos, "model", "?"), getattr(providers.auditor, "model", "?"))
            estimate_ = estimate_ingest(document, baseline, models[0], models[1], load_pricing())
            cost = f"~US$ {estimate_['cost_usd']:.2f}" if estimate_["cost_usd"] is not None else "sin precio configurado"
            st.caption(
                f"Estimación (enumera {models[0]}, clasifica {models[1]}): ~{estimate_['candidates']} candidatos, ~{estimate_['calls']} llamadas, "
                f"~{estimate_['input_tokens']:,} tokens de entrada y ~{estimate_['output_tokens']:,} de salida, {cost}. Los textos se envían al proveedor del modelo."
            )
            if baseline is None:
                st.warning("Sin la línea base de la preventa, los candidatos no se enlazan a lo vendido. Extraela primero.")
            if controller.mode != "real":
                st.info("Leer la reunión necesita modelos reales (LIVE_MODE=1).")
            sure = st.checkbox("Confirmo el gasto", key=f"confirmar-reunion-{meeting_id}")
            if st.button("Leer reunión contra el catálogo", key=f"leer-{meeting_id}", disabled=controller.running or controller.mode != "real" or not sure):
                with st.spinner("Enumerando, clasificando y verificando las citas…"):
                    result = ingest_meeting(
                        document, catalog=catalog, enumerator=providers.requerimientos, classifier=providers.auditor, confirmed=True,
                        baseline=baseline, presale=presale, pricing=load_pricing(),
                    )
                st.session_state["ultima_lectura"] = {
                    "reunion": meeting_id, "descartados": [(r.text, r.reason) for r in result.rejected], "fuera_de_orden": result.out_of_order,
                    "vacia": result.nothing_found,
                }
                st.rerun()
        last = st.session_state.get("ultima_lectura")
        if last and last["reunion"] == meeting_id:
            if last["vacia"]:
                st.warning(
                    "No se encontró ningún requisito con cita verificada en esta reunión" + (f" ({len(last['descartados'])} candidatos descartados)" if last["descartados"] else "")
                    + ". No se marcó como leída: revisá el contenido del archivo, o volvé a leerla si querés."
                )
            if last["fuera_de_orden"]:
                st.warning("Esta reunión es anterior a otra ya leída: todas sus propuestas quedan para revisión humana.")
            if last["descartados"]:
                with st.expander(f"Candidatos descartados · {len(last['descartados'])}"):
                    st.dataframe([{"candidato": t, "motivo": m} for t, m in last["descartados"]], width="stretch", hide_index=True)
        proposals = catalog.proposals(source_id=meeting_id)
        if proposals:
            with st.expander(f"Propuestas · {len(proposals)}"):
                st.dataframe(
                    [
                        {
                            "id": p.id, "tipo": KIND_LABELS[p.kind.value], "sobre": ", ".join(p.targets) or "—",
                            "propuesta": p.drafts[0].title if p.drafts else "—", "estado": p.state.value,
                            "confianza": f"{p.confidence:.2f}" if p.confidence is not None else "—",
                            "cita": p.evidence[0].quote, "orador": p.evidence[0].speaker or "—", "motivo": p.rationale,
                        }
                        for p in proposals
                    ],
                    width="stretch", hide_index=True,
                )


def main() -> None:
    st.set_page_config(page_title="BacklogGuard", page_icon="🛡️", layout="wide")
    controller = make_controller()
    people = controller.deps.people
    display = {p.name: p.display for p in people.people}

    st.sidebar.title("BacklogGuard")
    name = st.sidebar.selectbox("¿Con qué rol actuás?", list(display), format_func=display.get, key="persona")
    who = people.get(name)
    st.sidebar.caption(f"Rol: {who.role}")
    st.sidebar.caption(f"Modo: {controller.mode}")
    if controller.using_own_sources:
        st.sidebar.divider()
        st.sidebar.caption("El catálogo, las decisiones y lo publicado se conservan entre corridas.")
        sure = st.sidebar.checkbox("Confirmo: se borra todo lo guardado del proyecto", key="confirmar-proyecto-nuevo")
        if st.sidebar.button("Empezar proyecto nuevo", key="proyecto-nuevo", disabled=controller.running or not sure):
            controller.new_project()
            st.rerun()
    elif st.sidebar.button("Reiniciar demo", key="reiniciar", disabled=controller.running):
        controller.reset_demo()
        st.rerun()

    apply_theme()
    top_band("Del dicho al backlog")
    live_status(controller)
    render_guide(controller, who)
    sources, review, run, board, decisions, advanced = st.tabs(TABS, key="nav", on_change="rerun")
    with sources:
        st.caption(HELP[FUENTES])
        tab_sources(controller)
    with review:
        st.caption(HELP[REVISION])
        tab_review(controller, who)
    with run:
        st.caption(HELP[CORRIDA])
        tab_run(controller)
    with board:
        st.caption(HELP[HISTORIAS])
        tab_board(controller)
    with decisions:
        st.caption(HELP[DECISIONES])
        tab_decisions(controller, who)
    with advanced:
        st.caption(HELP[AVANZADO])
        talk, catalog, saved, tasks, backlog, activity = st.tabs(ADVANCED_TABS)
        with talk:
            tab_conversation(controller)
        with catalog:
            tab_catalog(controller)
        with saved:
            tab_runs(controller)
        with tasks:
            tab_tasks(controller)
        with backlog:
            tab_backlog(controller)
        with activity:
            tab_activity(controller)


if __name__ == "__main__":  # Streamlit ejecuta el script como __main__; importar el módulo no dibuja nada
    main()
