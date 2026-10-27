"""La conversación entre agentes: sale solo de hechos de la corrida, en lenguaje de usuario y sin datos técnicos."""
import re

from backlogguard.graph.conversation import build_conversation
from backlogguard.ui.conversation_view import chat_html, message_html

TITLE = "Validar el CUIT antes de crear la cuenta"
QUOTE = "Sin CUIT válido no se puede dar de alta a nadie."


def task(n, origin, target, kind, ref=None, detail="", status="hecha", round=None):
    return {"id": f"T-{n:03d}", "origin": origin, "target": target, "kind": kind, "ref": ref, "detail": detail, "status": status,
            "round": round, "tokens": 999, "model": "claude-x", "steps": 4}


def state(tasks, **extra):
    item = {"title": TITLE, "citations": [{"quote": QUOTE, "speaker": "Ana (PO)", "source_name": "Reunión de inicio"}]}
    return {"board": {"items": {"US-001": item}, "findings": []}, "plan": {"sources": ["reunion_01"]}, "tasks": tasks, **extra}


def texts(messages):
    return [m.text for m in messages]


def test_sin_corrida_no_hay_conversacion():
    assert build_conversation({}) == []


def test_el_supervisor_cuenta_el_plan_y_el_productor_avisa_cuanto_redacto():
    messages = build_conversation(state([
        task(1, "persona", "supervisor", "planificar", detail="Armá el backlog"),
        task(2, "supervisor", "requerimientos", "redactar", detail="Fuentes: reunion_01. Ítems redactados: 3."),
    ]))
    assert [(m.sender, m.receiver) for m in messages] == [
        ("persona", "supervisor"), ("supervisor", "equipo"), ("supervisor", "requerimientos"), ("requerimientos", "supervisor"),
    ]
    assert "3 elementos" in messages[-1].text and "«Armá el backlog»" in messages[0].text


def test_una_objecion_del_critico_se_lista_y_la_cita_se_atribuye_a_la_fuente_no_a_las_personas():
    messages = build_conversation(state([
        task(1, "requerimientos", "critico", "revisar", "US-001", "objetado: el criterio 2 no es verificable; falta la cita del rol", round=1),
        task(2, "critico", "requerimientos", "corregir", "US-001", "el criterio 2 no es verificable; falta la cita del rol"),
        task(3, "requerimientos", "critico", "revisar", "US-001", "sustentado", round=2),
    ]))
    sent, objection, fixed, resent, ok = messages
    assert sent.quote == QUOTE and sent.quote_from == "Reunión de inicio" and "Ana" not in sent.quote_from
    assert objection.sender == "critico" and objection.points == ("el criterio 2 no es verificable", "falta la cita del rol")
    assert fixed.tone == "ok" and "corregida (ronda 2)" in resent.text and resent.quote == ""
    assert ok.tone == "ok" and "Sustentado" in ok.text


def test_el_auditor_informa_hallazgos_y_pide_una_sola_decision_con_la_lista():
    finding = {"kind": "cambio_de_alcance", "addressee": "supervisor", "description": "La reunión pide modificar clientes; la preventa lo excluyó.",
               "item_id": "US-001", "citations": [{"quote": "podrá modificar el domicilio"}]}
    s = state([
        task(1, "supervisor", "auditor", "auditar", detail="Hallazgos aplicados: 1; descartados: 2."),
        task(2, "auditor", "persona", "decidir", "G1", status="escalada"),
        task(3, "auditor", "persona", "decidir", "G2", status="escalada"),
    ], escalations=[
        {"ref": "G1", "reason": "cambio_de_alcance", "decides": "service_manager", "detail": "- Cambio uno"},
        {"ref": "G2", "reason": "vendido_no_tratado", "decides": "service_manager", "detail": "- Falta tratar los filtros"},
    ])
    s["board"]["findings"] = [finding]
    messages = build_conversation(s)
    found, hallazgo, discarded, ask = messages[1:]
    assert "1 hallazgo" in found.text and "Cambio de alcance" in hallazgo.text and hallazgo.quote == "podrá modificar el domicilio"
    assert "Descarté 2 hallazgos" in discarded.text
    assert ask.tone == "wait" and "service manager" in ask.text and ask.points == ("Un cambio de alcance: Cambio uno", "Algo que se vendió y no se trató: Falta tratar los filtros")


def test_las_decisiones_idénticas_seguidas_se_cuentan_juntas_y_el_plan_tiene_sus_palabras():
    record = {"request_id": "R-G1", "decision": "approve", "actor_role": "service_manager", "accepted": True, "comment": ""}
    plan = {"request_id": "R-plan", "decision": "approve", "actor_role": "product_owner", "accepted": True, "comment": ""}
    messages = build_conversation(state(
        [task(1, "supervisor", "integracion", "armar_plan")], decisions=[record, {**record, "request_id": "R-G2"}, {**record, "request_id": "R-G3"}, plan],
        publish_plan={"counts": {"crear": 2, "omitir": 0}}, publication={"ok": True, "results": [{"outcome": "publicado"}, {"outcome": "publicado"}]},
    ))
    assert texts(messages) == [
        "Aprobados los 3 pedidos.",
        "Armá el plan de publicación con lo que quedó sustentado. Todavía no escribas nada en el backlog.",
        "Plan listo: 2 para crear. No se escribe nada hasta que una persona lo apruebe.",
        "Plan aprobado.",
        "Publiqué 2 en el backlog, con la misma versión que aprobaron.",
    ]
    assert messages[0].sender == "Service manager" and messages[3].sender == "Product owner"


def test_una_corrida_en_pausa_dice_quien_tiene_que_decidir():
    messages = build_conversation(state([], status="esperando_decision", requests=[{"decides": "product_owner", "title": "Desacuerdo sin consenso: algo"}]))
    assert messages[-1].tone == "wait" and "product owner" in messages[-1].text


def test_no_aparecen_datos_tecnicos_en_ningun_mensaje():
    messages = build_conversation(state([
        task(1, "persona", "supervisor", "planificar", detail="Objetivo"),
        task(2, "supervisor", "requerimientos", "redactar", detail="Ítems redactados: 1."),
        task(3, "requerimientos", "critico", "revisar", "US-001", "sustentado", round=1),
        task(4, "supervisor", "auditor", "auditar", detail="Hallazgos aplicados: 0; descartados: 0."),
    ]))
    everything = " ".join(m.text + " ".join(m.points) for m in messages)
    assert not re.search(r"T-\d{3}|US-\d{3}|R-G|tokens|claude|ToolPolicy|\bhash\b", everything)


def test_el_html_escapa_el_texto_pero_respeta_el_negrita_del_resumen():
    messages = build_conversation(state([task(1, "persona", "supervisor", "resumir")], summary="**Listo** <script>alert(1)</script>"))
    html = message_html(messages[-1])
    assert "<script>" not in html and "<b>Listo</b>" in html and "&lt;script&gt;" in html
    assert chat_html(messages).startswith('<div class="bg-chat">')
