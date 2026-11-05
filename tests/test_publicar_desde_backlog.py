"""Elegir desde el backlog simulado qué se envía a Azure DevOps: publicar lo marcado, rechazar o dejar todo igual."""
from streamlit.testing.v1 import AppTest

from backlogguard.ui import plan_view

ITEMS = [
    {"item_id": "EP-1", "action": "crear", "type": "Epic", "title": "Portal", "reason": "no existe en el backlog", "parent_item_id": None, "remote_id": None},
    {"item_id": "HU-1", "action": "crear", "type": "User Story", "title": "Acceso con SSO", "reason": "no existe en el backlog", "parent_item_id": "EP-1", "remote_id": None},
    {"item_id": "HU-2", "action": "actualizar", "type": "User Story", "title": "Email de estado", "reason": "el contenido cambió", "parent_item_id": "EP-1", "remote_id": 7},
    {"item_id": "HU-3", "action": "omitir", "type": "User Story", "title": "Reporte", "reason": "ya publicado en #9, sin cambios", "parent_item_id": "EP-1", "remote_id": 9},
]


def test_las_funciones_puras_de_la_seleccion():
    assert plan_view.selectable_ids(ITEMS) == ["EP-1", "HU-1", "HU-2"]  # el omitido no se puede elegir
    assert plan_view.exclusions_for(ITEMS, {"EP-1", "HU-1", "HU-2"}) == []
    assert plan_view.exclusions_for(ITEMS, {"EP-1", "HU-1"}) == ["HU-2"]
    assert plan_view.exclusions_for(ITEMS, set()) == ["EP-1", "HU-1", "HU-2"]
    assert plan_view.selection_line(ITEMS, {"EP-1"}) == "Se enviarán **1** de 3 · quedan afuera **2** · 1 omitido(s) por el plan (ya publicados o posibles duplicados)"


def test_avisa_si_se_manda_un_hijo_sin_su_padre():
    assert plan_view.orphan_warnings(ITEMS, {"HU-1", "HU-2"}) == [
        "«Acceso con SSO» se publicaría sin su padre «Portal» y quedaría suelto en Azure.",
        "«Email de estado» se publicaría sin su padre «Portal» y quedaría suelto en Azure.",
    ]
    assert plan_view.orphan_warnings(ITEMS, {"EP-1", "HU-1"}) == []
    assert plan_view.orphan_warnings(ITEMS, {"HU-1"}) != []


def page(role="full_stack_ia_engineer", pending=True, drift=False):
    import streamlit as st
    from types import SimpleNamespace

    from backlogguard.ui.app import plan_selector

    state = st.session_state
    state.setdefault("calls", [])
    state.setdefault("version", 1)
    state.setdefault("exclude", [])
    items = [
        {"item_id": "EP-1", "action": "crear", "type": "Epic", "title": "Portal", "reason": "no existe en el backlog", "parent_item_id": None, "remote_id": None},
        {"item_id": "HU-1", "action": "crear", "type": "User Story", "title": "Acceso con SSO", "reason": "no existe en el backlog", "parent_item_id": "EP-1", "remote_id": None},
        {"item_id": "HU-2", "action": "actualizar", "type": "User Story", "title": "Email de estado", "reason": "el contenido cambió", "parent_item_id": "EP-1", "remote_id": 7},
        {"item_id": "HU-3", "action": "omitir", "type": "User Story", "title": "Reporte", "reason": "ya publicado en #9, sin cambios", "parent_item_id": "EP-1", "remote_id": 9},
    ]

    def request():
        shown = [i for i in items if i["item_id"] not in state.exclude]
        if drift and state.version > 1:
            shown = [i for i in shown if i["item_id"] != "HU-1"]  # el plan nuevo trae menos de lo marcado
        return {
            "request_id": "R-plan", "version": state.version, "args_hash": f"h{state.version}", "kind": "plan", "decides": "full_stack_ia_engineer",
            "title": "Plan", "summary": "", "evidence": [], "payload": {"items": shown, "exclude": list(state.exclude)},
        }

    def decide(decision):
        state.calls.append((decision["decision"], decision["request_version"], (decision.get("edited") or {}).get("exclude")))
        if decision["decision"] == "edit":
            state.exclude, state.version = decision["edited"]["exclude"], state.version + 1
        else:
            state.pending_done = True

    controller = SimpleNamespace(
        running=False, error=None, wait=lambda timeout=0: True, decide=decide,
        pending=lambda: None if (not pending or state.get("pending_done")) else {"request": request(), "last_error": None},
        state=lambda: {"status": "publicada"},
        deps=SimpleNamespace(people=SimpleNamespace(with_role=lambda r: [SimpleNamespace(display="ingeniero de IA")])),
    )
    plan_selector(controller, SimpleNamespace(name="Vane", role=role))


def run(**kwargs) -> AppTest:
    return AppTest.from_function(page, kwargs=kwargs, default_timeout=30).run()


def calls(at):
    return list(at.session_state["calls"])


def test_muestra_todo_marcado_y_el_omitido_no_se_puede_elegir():
    at = run()
    assert not at.exception
    labels = {c.key: (c.value, c.disabled) for c in at.checkbox}
    assert labels["pub-R-plan-v1-EP-1"] == (True, False) and labels["pub-R-plan-v1-HU-2"] == (True, False)
    assert labels["pub-R-plan-v1-HU-3-omitido"] == (False, True)
    assert at.button(key="plan-publicar").label == "Publicar 3 en Azure DevOps"
    assert any("quedan afuera **0**" in m.value for m in at.markdown)


def test_publicar_todo_aprueba_el_plan_mostrado_sin_editarlo():
    at = run()
    at.button(key="plan-publicar").click().run()
    assert calls(at) == [("approve", 1, None)]


def test_publicar_lo_marcado_primero_excluye_el_resto_y_despues_aprueba_la_version_nueva():
    at = run()
    at.checkbox(key="pub-R-plan-v1-HU-2").uncheck().run()
    assert at.button(key="plan-publicar").label == "Publicar 2 en Azure DevOps"
    at.button(key="plan-publicar").click().run()
    assert calls(at) == [("edit", 1, ["HU-2"]), ("approve", 2, None)]


def test_si_el_plan_nuevo_no_coincide_con_lo_marcado_no_aprueba():
    at = run(drift=True)
    at.checkbox(key="pub-R-plan-v1-HU-2").uncheck().run()
    at.button(key="plan-publicar").click().run()
    assert calls(at) == [("edit", 1, ["HU-2"])]  # nunca llegó a aprobar
    assert any("no coincide" in e.value for e in at.error)


def test_rechazar_toda_la_publicacion():
    at = run()
    at.button(key="plan-rechazar").click().run()
    assert calls(at) == [("reject", 1, None)]


def test_desmarcar_todo_deshabilita_publicar_y_cancelar_los_cambios_vuelve_a_lo_original():
    at = run()
    at.button(key="pub-nada-R-plan-v1").click().run()
    assert at.button(key="plan-publicar").disabled and at.button(key="plan-publicar").label == "Publicar 0 en Azure DevOps"
    at.button(key="pub-deshacer-R-plan-v1").click().run()
    assert at.button(key="plan-publicar").label == "Publicar 3 en Azure DevOps" and not at.button(key="plan-publicar").disabled


def test_avisa_si_se_deja_afuera_el_padre_de_lo_que_se_envia():
    at = run()
    at.checkbox(key="pub-R-plan-v1-EP-1").uncheck().run()
    assert any("sin su padre «Portal»" in w.value for w in at.warning)


def test_otro_rol_ve_el_plan_pero_no_puede_decidir():
    at = run(role="product_owner")
    assert any("ingeniero de IA" in i.value for i in at.info)
    assert all(c.disabled for c in at.checkbox) and at.button(key="plan-publicar").disabled and at.button(key="plan-rechazar").disabled


def test_sin_plan_pendiente_explica_por_que_no_hay_nada_para_elegir():
    at = run(pending=False)
    assert not at.exception and len(at.checkbox) == 0 and len(at.button) == 0
    assert any("ya se publicó" in i.value for i in at.info)


def test_el_aviso_distingue_publicado_rechazado_y_en_curso():
    assert "ya se publicó" in plan_view.no_pending_plan_text("publicada", False)
    assert "rechazado" in plan_view.no_pending_plan_text("plan_rechazado", False)
    assert "sigue trabajando" in plan_view.no_pending_plan_text("en_curso", True)


def test_volver_a_armar_el_plan_pide_una_version_nueva_con_las_mismas_exclusiones():
    at = run()
    at.button(key="plan-rearmar").click().run()
    assert calls(at) == [("edit", 1, [])]
    assert not at.exception and "pub-R-plan-v2-EP-1" in {c.key for c in at.checkbox}  # se muestra la versión nueva
