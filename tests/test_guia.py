"""La guía del flujo: qué sigue según el estado, y que la pantalla arme sus pestañas con el orden nuevo."""
from backlogguard.ui.guide import (
    CORRIDA, DECISIONES, FUENTES, HISTORIAS, REVISION, Snapshot, next_step, steps_html, steps_of,
)


def snap(**extra) -> Snapshot:
    base = dict(
        running=False, read_only=False, sources_processed=1, proposals_mine=0, proposals_others=(), active=0, to_publish=0, published=0,
        request_title=None, request_role=None, role="product_owner", stories=0,
    )
    return Snapshot(**{**base, **extra})


def test_sin_fuentes_leidas_manda_a_fuentes():
    step = next_step(snap(sources_processed=0, role="full_stack_ia_engineer"))
    assert (step.tab, step.step) == (FUENTES, FUENTES)


def test_una_decision_propia_lleva_a_decisiones_y_una_ajena_pide_cambiar_de_rol():
    mine = next_step(snap(request_title="Cambiar alcance", request_role="product_owner"))
    assert mine.tab == DECISIONES and "Cambiar alcance" in mine.text
    other = next_step(snap(request_title="Cambiar alcance", request_role="service_manager"))
    assert other.tab is None and "service manager" in other.text and "barra lateral" in other.text


def test_las_propuestas_pendientes_van_a_revision_segun_el_rol():
    assert next_step(snap(proposals_mine=3)).tab == REVISION
    elsewhere = next_step(snap(proposals_others=("service_manager",)))
    assert elsewhere.tab is None and "service manager" in elsewhere.text


def test_requisitos_sin_historia_llevan_a_la_corrida_y_las_publicadas_a_las_historias():
    assert next_step(snap(active=5, to_publish=5, role="full_stack_ia_engineer")).tab == CORRIDA
    assert next_step(snap(active=5, published=5)).tab == HISTORIAS


def test_mientras_trabajan_no_hay_boton_y_la_corrida_guardada_vuelve_a_la_corrida():
    assert next_step(snap(running=True)).tab is None
    assert next_step(snap(read_only=True)).tab == CORRIDA


def test_la_barra_de_pasos_marca_lo_hecho_y_el_paso_actual():
    state = snap(active=5, published=5, proposals_mine=0)
    html = steps_html(steps_of(state), HISTORIAS)
    assert html.count("bg-step now") == 1 and "5 listas" in html and "✔" in html
    pending = steps_of(snap(proposals_mine=2))
    assert next(s for s in pending if s.key == REVISION).detail == "pendiente"


def test_la_corrida_la_puede_iniciar_cualquier_rol_y_las_fuentes_las_carga_el_ingeniero():
    for role in ("product_owner", "service_manager", "full_stack_ia_engineer"):
        assert next_step(snap(role=role, active=5, to_publish=5)).tab == CORRIDA
    assert next_step(snap(role="product_owner", sources_processed=0)).tab is None
    assert next_step(snap(role="full_stack_ia_engineer", sources_processed=0)).tab == FUENTES


def test_los_pendientes_propios_dependen_del_rol():
    from backlogguard.ui.guide import mine

    assert mine(snap(role="service_manager", active=5, to_publish=5)) == "Tus pendientes como service manager: nada por ahora."
    busy = snap(role="product_owner", proposals_mine=3, request_title="x", request_role="product_owner")
    assert mine(busy) == "Tus pendientes como product owner: 3 propuesta(s) por revisar · 1 decisión de la corrida."
