"""El historial junta lo decidido en las propuestas, en el alcance y en las corridas, con el rol de quien decidió."""
from test_catalogo import approve_and_apply, draft, evidence

from backlogguard.catalog import Proposal, ProposalKind
from backlogguard.ui.decision_history import history

SCOPE = {"created_at": "2026-10-28T11:06:39+00:00", "value": {"decision": "Se aprueba: Alianza inactiva bloquea cambios.", "approved_by": "service_manager"}}
RUN = {
    "requests": [{"request_id": "R-1", "title": "Desacuerdo sobre HU-RQ-002"}],
    "decisions": [
        {"request_id": "R-1", "decision": "approve", "actor_role": "product_owner", "at": "2026-10-28T12:00:00+00:00", "accepted": True, "comment": "ok"},
        {"request_id": "R-1", "decision": "edit", "actor_role": "product_owner", "at": "2026-10-28T11:59:00+00:00", "accepted": False, "comment": ""},
    ],
}


def test_junta_las_tres_fuentes_ordenadas_y_sin_los_intentos_rechazados(tmp_path):
    from backlogguard.catalog import Catalog

    catalog = Catalog(tmp_path / "c.sqlite")
    proposal = Proposal(source_id="r1", fingerprint="fp", candidate_key="k", kind=ProposalKind.NUEVO, drafts=[draft("Vigencia del score")], evidence=[evidence(source_id="r1", fp="fp")])
    approve_and_apply(catalog, catalog.propose(proposal))
    rows = history(catalog.proposals(), [SCOPE], [RUN])
    assert {r["tipo"] for r in rows} == {"Revisión de propuesta", "Cambio de alcance", "Pedido de la corrida"}
    run = next(r for r in rows if r["tipo"] == "Pedido de la corrida")
    assert run["qué"] == "Desacuerdo sobre HU-RQ-002" and run["resultado"] == "Aprobado" and run["rol"] == "product owner"
    assert len([r for r in rows if r["tipo"] == "Pedido de la corrida"]) == 1  # el intento rechazado no cuenta
    scope = next(r for r in rows if r["tipo"] == "Cambio de alcance")
    assert scope["rol"] == "service manager" and scope["resultado"] == "Aprobado" and scope["qué"] == "Alianza inactiva bloquea cambios."
    assert [r["momento"] for r in rows] == sorted((r["momento"] for r in rows), reverse=True)


def test_sin_decisiones_no_hay_filas():
    assert history([], [], [{}]) == []


def test_los_pedidos_sin_titulo_guardado_tienen_un_nombre_legible():
    state = {"decisions": [
        {"request_id": "R-plan", "decision": "approve", "actor_role": "full_stack_ia_engineer", "at": "2026-10-28T22:05:00+00:00"},
        {"request_id": "R-item-HU-RQ-004", "decision": "reject", "actor_role": "product_owner", "at": "2026-10-28T22:04:00+00:00"},
    ]}
    rows = history([], [], [state])
    assert [r["qué"] for r in rows] == ["Plan de publicación", "Desacuerdo sobre la historia HU-RQ-004"]
    assert [r["rol"] for r in rows] == ["ingeniero", "product owner"]
