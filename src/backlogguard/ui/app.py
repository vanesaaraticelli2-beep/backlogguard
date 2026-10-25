"""Pantalla de BacklogGuard (Streamlit): la corrida en vivo y las decisiones de cada persona.

    .venv\\Scripts\\streamlit run src/backlogguard/ui/app.py

Con LIVE_MODE=1 usa los modelos reales; con LIVE_MODE=0 reproduce la corrida grabada en
`evals/recordings/demo_acme.json` (sin red ni costo). No hay autenticación: la persona se elige en la
barra lateral y solo ve los pedidos que le corresponden por su rol.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from backlogguard.board import Board, SourceType
from backlogguard.graph.setup import has_user_sources, user_sources_dir
from backlogguard.rag import SourceLibrary, build_chunks
from backlogguard.rag.importers import SourceImportError, estimate, import_pdf, import_transcript
from backlogguard.rag.sources import SourceMetadata, slugify
from backlogguard.ui.controller import DEFAULT_MAX_STORIES, DEFAULT_OBJECTIVE, RunController
from backlogguard.ui.runtime import make_controller

STATE_LABELS = {
    "borrador": "borrador", "objetado": "objetado", "sustentado": "sustentado", "aprobado": "aprobado", "excluido": "excluido",
}
STATUS_TEXT = {
    "en_curso": "en curso",
    "esperando_decision": "esperando una decisión",
    "plan_pendiente_de_aprobacion": "esperando que se apruebe el plan de publicación",
    "publicada": "plan publicado en el backlog",
    "plan_rechazado": "plan rechazado: no se publicó nada",
    "publicacion_detenida": "publicación detenida",
    "completada": "completada",
    "completada_con_errores": "completada con errores",
    "presupuesto_agotado": "presupuesto agotado",
}
NODE_ORDER = ["plan", "produce", "review", "audit", "escalate", "decide", "integrate", "approve_plan", "summarize"]
NODE_NAMES = {
    "plan": "Plan", "produce": "Redacción", "review": "Revisión", "audit": "Auditoría", "escalate": "Pedidos",
    "decide": "Decisiones", "integrate": "Plan de publicación", "approve_plan": "Aprobación", "summarize": "Resumen",
}


# ---- piezas ----


def render_status(controller: RunController) -> None:
    state = controller.state()
    status = state.get("status", "sin corrida")
    if controller.running:
        st.info(f"Los agentes están trabajando… ({len(controller.events)} eventos)")
    elif controller.error:
        st.error(f"La corrida falló: {controller.error}")
    else:
        st.success(f"Estado: {STATUS_TEXT.get(status, status)}") if status in ("publicada", "completada") else st.write(f"**Estado:** {STATUS_TEXT.get(status, status)}")
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
        st.caption(f"{entry['source_name']} · {entry['source_date']}{where} · {entry.get('speaker') or 's/d'}")


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
    waiting = controller.pending() is not None
    st.write(f"Modo: **{controller.mode}**" + (" (reproduce una corrida grabada, sin costo)" if controller.mode == "demo" else ""))
    if controller.mode == "simulado":
        st.warning("Sin modelos reales ni grabación: los agentes no van a producir nada útil. Activá LIVE_MODE=1 o grabá una demo.")
    own = controller.using_own_sources
    objective = st.text_area("Objetivo de la corrida", DEFAULT_OBJECTIVE, key="objetivo")
    if own:
        st.info("La corrida usa **tus fuentes** (pestaña «Fuentes»), sin work items de ejemplo.")
        max_stories = st.number_input("Máximo de historias a redactar", 1, 30, DEFAULT_MAX_STORIES, key="maximo_historias")
        needs_models = controller.mode != "real"
        if needs_models:
            st.error("Con fuentes propias hace falta LIVE_MODE=1 (modelos reales): la corrida grabada no sabe responder a documentos nuevos.")
        else:
            st.warning(
                "Esta corrida usa modelos reales y **gasta tokens**. "
                f"Tope por corrida: {controller.deps.budget.max_tokens:,} tokens. Los textos se envían a los proveedores de los modelos."
            )
        seed = False
    else:
        needs_models, max_stories = False, None
        seed = st.checkbox("Cargar work items de ejemplo cargados a mano (sirven para ver un posible duplicado)", value=True, key="semilla")
    if st.button("Iniciar corrida", type="primary", key="iniciar", disabled=controller.running or waiting or needs_models):
        controller.start(objective, seed=seed, max_stories=int(max_stories) if max_stories else None)
        st.rerun()
    if waiting:
        st.caption("Hay una corrida pausada esperando una decisión (pestaña «Mis decisiones»).")
    state = controller.state()
    if state.get("summary"):
        st.markdown("**Resumen del Supervisor**")
        st.write(state["summary"])
    if state:
        st.caption(f"Tokens usados: {state.get('tokens', 0)}")
    for error in state.get("errors", []):
        st.error(f"{error['node']} ({error.get('ref')}): {error['error']}")


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
          "ítems": r["items"], "tokens": r["tokens"], "espera una decisión": "sí" if r["waiting"] else ""} for r in runs],
        width="stretch", hide_index=True,
    )
    chosen = st.selectbox("Corrida a abrir", [r["thread_id"] for r in runs], key="corrida_guardada")
    if st.button("Abrir (solo lectura)", key="abrir_corrida", disabled=controller.running):
        controller.open_run(chosen)
        st.rerun()
    if controller.read_only:
        st.info(f"Estás viendo la corrida **{controller.thread_id}** (solo lectura). «Iniciar corrida» vuelve al modo normal.")


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
        st.info(f"No tenés pedidos pendientes. El pedido actual lo decide el rol **{decider}**.")
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
    for item in board.items.values():
        with st.expander(f"{item.id} · {item.state.value} · {item.title}"):
            st.write(item.description)
            for criterion in item.acceptance_criteria:
                st.markdown(f"- {criterion}")
            for citation in item.citations:
                st.markdown(f"> {citation.quote}")
                where = f" · p. {citation.page}" if citation.page else ""
                st.caption(f"{citation.source_name} · {citation.source_date.isoformat()}{where} · {citation.speaker or 's/d'}")
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
    upload = st.file_uploader("Archivo", type=["pdf"] if is_pdf else ["txt", "md"], key=f"archivo-{kind}")
    name = st.text_input("Nombre de la fuente", key=f"nombre-{kind}")
    when = st.date_input("Fecha del documento", value=date.today(), key=f"fecha-{kind}")
    overwrite = st.checkbox("Reemplazar si ya existe una fuente con ese nombre", key=f"reemplazar-{kind}")
    if st.button("Importar y guardar", key="importar", disabled=busy or upload is None or not name.strip()):
        try:
            imported = import_pdf(upload.getvalue()) if is_pdf else import_transcript(upload.getvalue())
            source_type = SourceType.PREVENTA if is_pdf else (SourceType.MINUTA if kind.startswith("Minuta") else SourceType.REUNION)
            metadata = SourceMetadata(source_name=name.strip(), source_type=source_type, source_date=when, layout=imported.layout)
            document_id = slugify(name)
            library.write(document_id, metadata, imported.text, overwrite=overwrite)
        except (SourceImportError, FileExistsError) as exc:
            st.error(str(exc))
        else:
            chunks = build_chunks(document_id, imported.text, metadata.model_dump(mode="json"))
            st.success(f"Importado «{name.strip()}»: {imported.words:,} palabras (~{estimate(imported.words)['tokens']:,} tokens), {len(chunks)} fragmentos.")
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
            [{"id": i, "tipo": m.source_type.value, "fecha": m.source_date.isoformat(), "formato": m.layout, "nombre": m.source_name} for i, m in entries],
            width="stretch", hide_index=True,
        )
        victim = st.selectbox("Borrar una fuente", [""] + [i for i, _ in entries], key="borrar_fuente")
        if st.button("Borrar", key="borrar", disabled=busy or not victim):
            library.delete(victim)
            controller.refresh_sources()
            st.rerun()
    ready = has_user_sources(library.root)
    st.info(
        "Las corridas usan: **tus fuentes propias**." if ready
        else "Las corridas usan: **las fuentes de ejemplo** (faltan una preventa y una reunión propias)."
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
    if st.sidebar.button("Reiniciar demo", key="reiniciar", disabled=controller.running):
        controller.reset_demo()
        st.rerun()

    st.title("Del dicho al backlog")
    live_status(controller)
    run, sources, saved, decisions, board, backlog, activity = st.tabs(
        ["Corrida", "Fuentes", "Corridas guardadas", "Mis decisiones", "Tablero", "Backlog simulado", "Actividad"]
    )
    with run:
        tab_run(controller)
    with sources:
        tab_sources(controller)
    with saved:
        tab_runs(controller)
    with decisions:
        tab_decisions(controller, who)
    with board:
        tab_board(controller)
    with backlog:
        tab_backlog(controller)
    with activity:
        tab_activity(controller)


if __name__ == "__main__":  # Streamlit ejecuta el script como __main__; importar el módulo no dibuja nada
    main()
