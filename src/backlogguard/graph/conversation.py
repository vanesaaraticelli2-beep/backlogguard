"""La corrida contada como una conversación entre agentes, en lenguaje de usuario (fuera del curso).

Cada mensaje sale de un hecho que quedó registrado en el estado de la corrida (tareas, tablero, hallazgos, decisiones);
no se inventa nada y no interviene ningún modelo: son plantillas con los datos reales. Como solo lee el estado guardado,
sirve igual para una corrida en vivo y para una guardada.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from backlogguard.graph.live import NODE_TITLES

SENDER_LABELS = {
    "persona": "Persona", "supervisor": "Supervisor", "requerimientos": "Requerimientos", "critico": "Crítico",
    "auditor": "Auditor", "integracion": "Integración", "equipo": "Equipo",
}
HUMAN_ROLES = {"product_owner": "Product owner", "service_manager": "Service manager", "full_stack_ia_engineer": "Ingeniero"}
REASON_PHRASES = {
    "cambio_de_alcance": "un cambio de alcance",
    "vendido_no_tratado": "algo que se vendió y no se trató",
    "contradiccion": "una contradicción entre reuniones",
    "desacuerdo_sin_consenso": "un desacuerdo que el equipo no pudo resolver",
}
FINDING_LABELS = {
    "cambio_de_alcance": "Cambio de alcance", "contradiccion": "Contradicción", "tratado_no_vendido": "Tratado y no vendido",
    "vendido_no_tratado": "Vendido y no tratado", "decision_evolucionada": "Decisión que cambió",
}
DECISION_WORDS = {"approve": "Aprobado.", "reject": "Rechazado.", "edit": "Se editó el pedido y se reenvía."}
PLAN_WORDS = {"approve": "Plan aprobado.", "reject": "Plan rechazado: no se publica nada.", "edit": "Se editó el plan: se excluyeron algunos elementos y se reenvía."}
MAX_QUOTE = 220


@dataclass(frozen=True)
class Message:
    sender: str
    receiver: str
    text: str
    quote: str = ""
    quote_from: str = ""
    points: tuple[str, ...] = ()
    tone: str = ""  # "", "ok", "warn" o "wait"
    task: str = ""
    ref: str = ""  # id de la historia de la que se habla, si hay una en el tablero


def _clip(text: str, limit: int) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _human(role: str) -> str:
    return HUMAN_ROLES.get(role, role.replace("_", " ").capitalize() if role else "Persona")


def _points(detail: str) -> tuple[str, ...]:
    return tuple(p.strip() for p in detail.split(";") if p.strip())


class _Facts:
    """Títulos y citas del tablero, y quién decide cada pedido, para nombrar las cosas como las conoce una persona."""

    def __init__(self, state: dict):
        self.items = (state.get("board") or {}).get("items", {})
        self.findings = (state.get("board") or {}).get("findings", [])
        self.escalations = {e["ref"]: e for e in state.get("escalations", [])}

    def title(self, ref: str | None) -> str:
        item = self.items.get(ref or "")
        return f"«{item['title']}»" if item else "una historia"

    def quote(self, ref: str | None) -> tuple[str, str]:
        citations = (self.items.get(ref or "") or {}).get("citations") or []
        if not citations:
            return "", ""
        first = citations[0]
        return _clip(first["quote"], MAX_QUOTE), first.get("source_name") or ""


def build_conversation(state: dict) -> list[Message]:
    """Los mensajes de la corrida en orden. Devuelve una lista vacía si todavía no empezó."""
    if not state:
        return []
    facts = _Facts(state)
    decisions = list(state.get("decisions", []))
    before_plan = [d for d in decisions if d["request_id"] != "R-plan"]
    plan_decisions = [d for d in decisions if d["request_id"] == "R-plan"]
    out: list[Message] = []
    decisions_said = False

    def say_decisions(records: list[dict]) -> None:
        grouped: list[list[dict]] = []
        for d in records:  # decisiones seguidas e idénticas se cuentan juntas
            key = (d["actor_role"], d["decision"], d.get("comment"), d["accepted"], d["request_id"] == "R-plan")
            if grouped and grouped[-1][0]["_key"] == key:
                grouped[-1].append(d)
            else:
                grouped.append([{**d, "_key": key}])
        for group in grouped:
            d, count = group[0], len(group)
            who = _human(d["actor_role"]) if d["actor_role"] != "?" else "Persona"
            if not d["accepted"]:
                out.append(Message(who, "supervisor", f"La decisión no pudo registrarse: {d.get('error') or 'formato inválido'}", tone="warn"))
                continue
            words = (PLAN_WORDS if d["request_id"] == "R-plan" else DECISION_WORDS).get(d["decision"], d["decision"])
            if count > 1 and d["decision"] in ("approve", "reject"):
                words = f"{'Aprobados' if d['decision'] == 'approve' else 'Rechazados'} los {count} pedidos."
            text = words + (f" {d['comment']}" if d.get("comment") else "")
            out.append(Message(who, "supervisor", text, tone="ok"))

    asked: set[str] = set()
    for task in state.get("tasks", []):
        kind, ref = task["kind"], task.get("ref")
        if kind == "decidir":
            if task["id"] not in asked:
                batch = _decision_batch(state["tasks"], task)
                asked.update(t["id"] for t in batch)
                out.extend(_ask_messages(batch, facts))
            continue
        if kind == "armar_plan" and not decisions_said:
            say_decisions(before_plan)
            decisions_said = True
        item = ref if ref in facts.items else ""
        out.extend(replace(m, ref=item) for m in _task_messages(task, kind, ref, facts, state))
        if kind == "armar_plan":
            out.extend(_plan_messages(state))
            say_decisions(plan_decisions)
            out.extend(_publication_messages(state))
    if not decisions_said:
        say_decisions(before_plan)
        say_decisions(plan_decisions)
        if plan_decisions:
            out.extend(_publication_messages(state))
    out.extend(_waiting(state, facts))
    out.extend(_problems(state))
    return out


def _task_messages(task: dict, kind: str, ref: str | None, facts: _Facts, state: dict) -> list[Message]:
    t, detail, tid = facts.title(ref), task.get("detail") or "", task["id"]
    status = task.get("status", "hecha")
    if kind == "planificar":
        plan = state.get("plan") or {}
        sources = ", ".join(plan.get("sources", [])) or "las fuentes cargadas"
        order = "redacción (Requerimientos), revisión (Crítico) y auditoría (Auditor)"
        plan_text = (
            f"Fuentes de trabajo: {sources}. Orden previsto: {order}."
            if not plan.get("used_default") else f"No fue posible armar un plan propio; se sigue el plan por defecto: {order}."
        )
        return [Message("persona", "supervisor", f"Objetivo de la corrida: «{_clip(detail, 300)}»", task=tid), Message("supervisor", "equipo", plan_text, task=tid)]
    if kind == "redactar":
        sources = (state.get("plan") or {}).get("sources", [])
        approved = re.search(r"Requisitos aprobados por redactar: (\d+)(?: \(quedan (\d+) para la próxima corrida\))?", detail)
        if approved:
            rest = f" Quedan {approved.group(2)} para la próxima corrida." if approved.group(2) else ""
            ask = Message("supervisor", "requerimientos", f"Redactar una historia por cada requisito aprobado: son {approved.group(1)}. Cada historia hereda las citas ya verificadas.{rest}", task=tid)
            if approved.group(1) == "0":
                return [ask, Message("requerimientos", "supervisor", "No hay elementos nuevos para redactar: todo lo aprobado ya está publicado.", tone="ok", task=tid)]
        else:
            ask = Message("supervisor", "requerimientos", "Redactar las historias solo a partir de lo tratado en "
                          + (", ".join(sources) if sources else "las reuniones")
                          + ". La preventa indica lo vendido, pero no cuenta como evidencia.", task=tid)
        found = re.search(r"Ítems redactados: (\d+)", detail)
        count = int(found.group(1)) if found else len(facts.items)
        if status == "incompleta":
            return [ask, Message("requerimientos", "supervisor", "La redacción quedó incompleta por falta de pasos o presupuesto. Puede haber requisitos sin cubrir.", tone="warn", task=tid)]
        return [ask, Message("requerimientos", "supervisor", f"Redacción finalizada: {count} {'elemento' if count == 1 else 'elementos'}, cada uno con su cita.", tone="ok", task=tid)]
    if kind == "revisar":
        quote, quote_from = facts.quote(ref)
        round_ = task.get("round") or 1
        send = Message("requerimientos", "critico", f"Se remite {t} para su revisión." if round_ == 1 else f"Se remite {t} corregida (ronda {round_}).",
                       quote=quote if round_ == 1 else "", quote_from=quote_from if round_ == 1 else "", task=tid)
        if status == "fallida":
            return [send, Message("critico", "requerimientos", f"No fue posible completar la revisión de {t}.", tone="warn", task=tid)]
        if detail.startswith("sustentado"):
            return [send, Message("critico", "requerimientos", f"{t}: la cita respalda el contenido. Resultado: sustentada.", tone="ok", task=tid)]
        return [send, Message("critico", "requerimientos", f"Se formulan objeciones sobre {t}:", points=_points(detail.partition(":")[2]), tone="warn", task=tid)]
    if kind == "corregir":
        origin = task["origin"]
        asks = [Message(origin, "requerimientos", f"Se solicita corregir {t}:", points=_points(detail), task=tid)] if origin == "auditor" else []
        if status == "fallida":
            return [*asks, Message("requerimientos", origin, f"No fue posible corregir {t}.", tone="warn", task=tid)]
        if status == "sin_correccion":
            return [*asks, Message("requerimientos", origin, f"Se intentó corregir {t}, pero los cambios no pudieron aplicarse.", tone="warn", task=tid)]
        return [*asks, Message("requerimientos", origin, f"Se corrigió {t} según las observaciones recibidas.", tone="ok", task=tid)]
    if kind == "auditar":
        ask = Message("supervisor", "auditor", "Auditar lo redactado contra lo vendido y lo ya acordado.", task=tid)
        if status == "fallida":
            return [ask, Message("auditor", "supervisor", "No fue posible completar la auditoría.", tone="warn", task=tid)]
        found = re.search(r"aplicados: (\d+); descartados: (\d+)", detail)
        applied, discarded = (int(found.group(1)), int(found.group(2))) if found else (len(facts.findings), 0)
        if not applied:
            return [ask, Message("auditor", "supervisor", "No se detectaron diferencias entre lo vendido y lo conversado.", tone="ok", task=tid)]
        reply = [Message("auditor", "supervisor", f"Se detectaron {applied} {'hallazgo' if applied == 1 else 'hallazgos'} para atender.", tone="warn", task=tid)]
        for f in facts.findings:
            where = facts.title(f.get("item_id")) if f.get("item_id") else ""
            quote = _clip(f["citations"][0]["quote"], MAX_QUOTE) if f.get("citations") else ""
            reply.append(Message("auditor", f["addressee"], f"{FINDING_LABELS.get(f['kind'], f['kind'])}" + (f" en {where}" if where else "") + f": {_clip(f['description'], 260)}",
                                 quote=quote, task=tid))
        if discarded:
            reply.append(Message("auditor", "supervisor", f"Se {'descartó' if discarded == 1 else 'descartaron'} {discarded} {'hallazgo' if discarded == 1 else 'hallazgos'} que no se sostenían (sin cita válida o repetidos).", task=tid))
        return [ask, *reply]
    if kind == "armar_plan":
        return [Message("supervisor", "integracion", "Armar el plan de publicación con lo sustentado. No escribir todavía en el backlog.", task=tid)]
    if kind == "resumir":
        return [Message("supervisor", "persona", state.get("summary") or "La corrida finalizó.", tone="ok", task=tid)]
    return []


def _decision_batch(tasks: list[dict], first: dict) -> list[dict]:
    """Los pedidos de decisión seguidos del mismo agente se piden juntos."""
    index = tasks.index(first)
    batch = [first]
    for later in tasks[index + 1:]:
        if later["kind"] != "decidir" or later["origin"] != first["origin"]:
            break
        batch.append(later)
    return batch


def _ask_messages(batch: list[dict], facts: _Facts) -> list[Message]:
    by_role: dict[str, list[dict]] = {}
    for task in batch:
        esc = facts.escalations.get(task.get("ref") or "", {})
        by_role.setdefault(esc.get("decides", ""), []).append(esc | {"task": task["id"]})
    out = []
    for role, escs in by_role.items():
        who = _human(role).lower()
        lines = []
        for esc in escs:
            phrase = REASON_PHRASES.get(esc.get("reason", ""), "una decisión").capitalize()
            what = facts.title(esc.get("ref")) if esc.get("ref") in facts.items else _clip(esc.get("detail", "").lstrip("- "), 150)
            lines.append(f"{phrase}: {what}" if what else phrase)
        text = f"Se requiere la decisión del {who} sobre {len(lines)} {'asunto' if len(lines) == 1 else 'asuntos'}:"
        out.append(Message(batch[0]["origin"], "persona", text, points=tuple(lines), tone="wait", task=batch[0]["id"]))
    return out


def _plan_messages(state: dict) -> list[Message]:
    plan = state.get("publish_plan") or {}
    counts = plan.get("counts") or {}
    if not plan:
        return [Message("integracion", "supervisor", "No fue posible armar el plan de publicación.", tone="warn")]
    parts = ", ".join(f"{n} para {action}" for action, n in counts.items() if n) or "nada para publicar"
    return [Message("integracion", "supervisor", f"Plan listo: {parts}. No se escribe nada hasta que una persona lo apruebe.", tone="ok")]


def _publication_messages(state: dict) -> list[Message]:
    publication = state.get("publication")
    if not publication:
        return []
    if publication.get("error") and not publication.get("results"):
        return [Message("integracion", "supervisor", publication["error"], tone="warn")]
    written = sum(1 for r in publication.get("results", []) if r["outcome"] in ("publicado", "actualizado", "vinculado"))
    if publication.get("ok"):
        return [Message("integracion", "supervisor", f"Se {'publicó' if written == 1 else 'publicaron'} {written} {'elemento' if written == 1 else 'elementos'} en el backlog, con la misma versión aprobada.", tone="ok")]
    return [Message("integracion", "supervisor", f"La publicación se detuvo después de {written} {'elemento' if written == 1 else 'elementos'}. El detalle figura en «Backlog simulado».", tone="warn")]


def _waiting(state: dict, facts: _Facts) -> list[Message]:
    status = state.get("status")
    if status == "plan_pendiente_de_aprobacion":
        return [Message("supervisor", "persona", "El plan está listo y espera aprobación en la pestaña «Corrida».", tone="wait")]
    requests = state.get("requests") or []
    if status == "esperando_decision" and requests:
        first = requests[0]
        return [Message("supervisor", "persona", f"Falta la decisión del {_human(first['decides']).lower()} sobre «{_clip(first['title'], 140)}». La corrida continúa cuando se decida (se responde en «Corrida»).", tone="wait")]
    return []


def _problems(state: dict) -> list[Message]:
    stop = state.get("stop_reason")
    out = [Message("supervisor", "persona", "La corrida se detuvo por presupuesto agotado. Puede haber elementos sin revisar.", tone="warn")] if stop else []
    out += [
        Message("supervisor", "persona", f"Una etapa tuvo un problema y quedó registrada: {NODE_TITLES.get(e['node'], e['node']).lower()}.", tone="warn")
        for e in state.get("errors", [])
    ]
    return out
