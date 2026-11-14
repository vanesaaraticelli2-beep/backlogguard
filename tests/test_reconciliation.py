from datetime import date

import pytest

from backlogguard.agents.integracion import execute_approved_reconciliation
from backlogguard.board import Board, SourceType
from backlogguard.catalog import (
    Catalog,
    CatalogError,
    Draft,
    Evidence,
    Proposal,
    ProposalKind,
    RequirementStatus,
)
from backlogguard.integrations import (
    BacklogError,
    PublicationLedger,
    PublishService,
    ReconciliationService,
    SimulatedBacklog,
)


def _evidence(fragment: str = "meeting:1") -> Evidence:
    return Evidence(
        fragment_id=fragment,
        quote="El requisito fue acordado.",
        source_name="Reunión",
        source_type=SourceType.REUNION,
        source_date=date(2026, 1, 20),
        source_id="meeting",
        source_fingerprint="fingerprint",
    )


def _proposal(kind, key, *, targets=(), drafts=None, evidence=None):
    return Proposal(
        source_id="meeting",
        fingerprint="fingerprint",
        candidate_key=key,
        kind=kind,
        targets=list(targets),
        drafts=drafts or [Draft(title="Validar identidad", description="d")],
        evidence=evidence or [_evidence(key)],
    )


@pytest.fixture
def retired_requirement(tmp_path):
    catalog = Catalog(tmp_path / "catalog.sqlite")
    backlog = SimulatedBacklog()
    ledger = PublicationLedger(tmp_path / "publications.sqlite")
    first = catalog.propose(_proposal(ProposalKind.NUEVO, "first"))
    catalog.decide(first.id, approve=True, by="PO")
    rid = catalog.apply(first.id).affected[0]
    remote = backlog.create(
        type="User Story",
        title="Validar identidad",
        description="d",
        acceptance_criteria=[],
        tags=[f"bg-item:HU-{rid}", "bg-key:original"],
        parent_id=None,
    )
    catalog.mark_published(rid, remote.id)

    divide = catalog.propose(
        _proposal(
            ProposalKind.DIVIDE,
            "divide",
            targets=[rid],
            drafts=[Draft(title="Validar identidad personal"), Draft(title="Validar empresa")],
        )
    )
    catalog.decide(divide.id, approve=True, by="PO")
    catalog.apply(divide.id)
    service = ReconciliationService(catalog, backlog, ledger, "TP-ITBA")
    return catalog, backlog, ledger, service, rid, remote


def test_dry_run_propone_retiro_reversible_solo_para_requisito_publicado_propio(
    retired_requirement,
):
    _, backlog, _, service, rid, remote = retired_requirement

    preview = service.build()

    assert len(preview.items) == 1
    assert preview.items[0].requirement_id == rid
    assert preview.items[0].remote_id == remote.id
    assert preview.items[0].action == "omitido"
    assert preview.items[0].reason.startswith("elegible;")
    assert backlog.writes == 1


def test_el_retiro_se_ejecuta_por_tool_con_plan_aprobado_y_deja_historial(
    retired_requirement,
):
    catalog, backlog, ledger, reconciliation, rid, remote = retired_requirement
    plan = reconciliation.arm({rid})
    publication = PublishService(Board(), backlog, ledger, "TP-ITBA")

    report = execute_approved_reconciliation(
        plan.plan_hash,
        service=publication,
        reconciliation=reconciliation,
        approved_by="full_stack_ia_engineer",
    )

    assert report.ok
    assert report.results[0]["outcome"] == "retirado"
    assert backlog.get(remote.id).state == "Removed"
    assert catalog.requirement(rid).status is RequirementStatus.DIVIDIDO
    with ledger._connect() as connection:
        row = connection.execute(
            "SELECT approved_by FROM reconciliations WHERE hash = ?",
            (plan.plan_hash,),
        ).fetchone()
    assert row["approved_by"] == "full_stack_ia_engineer"


def test_un_cambio_concurrente_bloquea_el_plan_antes_de_escribir(retired_requirement):
    _, backlog, ledger, reconciliation, rid, remote = retired_requirement
    plan = reconciliation.arm({rid})
    backlog.update(
        remote.id,
        expected_rev=remote.rev,
        title="Editado fuera de BacklogGuard",
        description="d",
        acceptance_criteria=[],
        tags=remote.tags,
    )
    before_writes = backlog.writes
    publication = PublishService(Board(), backlog, ledger, "TP-ITBA")

    report = execute_approved_reconciliation(
        plan.plan_hash,
        service=publication,
        reconciliation=reconciliation,
        approved_by="full_stack_ia_engineer",
    )

    assert not report.ok
    assert "cambiaron" in report.error
    assert backlog.writes == before_writes


def test_no_retira_work_item_sin_marca_de_propiedad(retired_requirement):
    _, backlog, _, service, rid, remote = retired_requirement
    backlog.update(
        remote.id,
        expected_rev=remote.rev,
        title=remote.title,
        description=remote.description,
        acceptance_criteria=remote.acceptance_criteria,
        tags=["cargado-manualmente"],
    )

    plan = service.build()

    assert plan.items[0].action == "bloqueado"
    assert "marca de propiedad" in plan.items[0].reason
    with pytest.raises(ValueError, match="no contiene retiros elegibles"):
        service.arm({rid})


def test_un_hijo_activo_bloquea_el_retiro_del_padre(retired_requirement):
    _, backlog, _, service, rid, remote = retired_requirement
    backlog.create(
        type="Task",
        title="Tarea activa",
        description="",
        acceptance_criteria=[],
        tags=[],
        parent_id=remote.id,
    )

    plan = service.build({rid})

    assert plan.items[0].action == "bloqueado"
    assert "hijos no retirados" in plan.items[0].reason


def test_tipo_sin_categoria_removed_no_asume_un_estado_alternativo(retired_requirement):
    _, backlog, _, service, rid, remote = retired_requirement

    def only_open_states(_):
        return [
            {"name": "New", "category": "Proposed"},
            {"name": "Active", "category": "InProgress"},
        ]

    backlog.list_work_item_states = only_open_states
    plan = service.build()

    assert plan.items[0].action == "bloqueado"
    assert "no ofrece un estado de categoría Removed" in plan.items[0].reason


def test_retiro_explicito_del_catalogo_se_convierte_en_un_plan_azure(
    tmp_path,
):
    catalog = Catalog(tmp_path / "catalog.sqlite")
    backlog = SimulatedBacklog()
    ledger = PublicationLedger(tmp_path / "publications.sqlite")
    proposal = catalog.propose(_proposal(ProposalKind.NUEVO, "approved"))
    catalog.decide(proposal.id, approve=True, by="PO")
    requirement_id = catalog.apply(proposal.id).affected[0]
    remote = backlog.create(
        type="User Story",
        title="Validar identidad",
        description="d",
        acceptance_criteria=[],
        tags=[f"bg-item:HU-{requirement_id}"],
        parent_id=None,
    )
    catalog.mark_published(requirement_id, remote.id)

    catalog.retire_requirement(
        requirement_id,
        by="full_stack_ia_engineer",
        reason="Fuera del alcance aprobado",
    )
    plan = ReconciliationService(catalog, backlog, ledger, "TP-ITBA").build(
        {requirement_id}
    )

    assert catalog.requirement(requirement_id).status is RequirementStatus.RETIRADO
    assert plan.selected_items[0].remote_id == remote.id
    assert plan.selected_items[0].target_state == "Removed"
    assert "se propone cambiar el estado a Removed" in plan.selected_items[0].reason
    assert backlog.get(remote.id).state != "Removed"


def test_retiro_explicito_exige_responsable_motivo_y_un_requisito_activo(tmp_path):
    catalog = Catalog(tmp_path / "catalog.sqlite")
    proposal = catalog.propose(_proposal(ProposalKind.NUEVO, "active"))
    catalog.decide(proposal.id, approve=True, by="PO")
    requirement_id = catalog.apply(proposal.id).affected[0]

    with pytest.raises(CatalogError, match="persona responsable"):
        catalog.retire_requirement(requirement_id, by=" ", reason="Fuera de alcance")
    with pytest.raises(CatalogError, match="motivo"):
        catalog.retire_requirement(requirement_id, by="ingeniero", reason=" ")

    retired = catalog.retire_requirement(
        requirement_id, by="ingeniero", reason="Fuera de alcance"
    )
    reopened = Catalog(tmp_path / "catalog.sqlite")
    assert retired.status is RequirementStatus.RETIRADO
    assert reopened.retirement_decision(requirement_id)["reason"] == "Fuera de alcance"
    with pytest.raises(CatalogError, match="no está activo"):
        reopened.retire_requirement(
            requirement_id, by="ingeniero", reason="Repetido"
        )


def test_fallo_parcial_se_reanuda_con_el_mismo_plan_sin_repetir_retiros(
    retired_requirement,
):
    catalog, backlog, ledger, reconciliation, first_id, _ = retired_requirement
    proposal = catalog.propose(_proposal(ProposalKind.NUEVO, "second"))
    catalog.decide(proposal.id, approve=True, by="PO")
    second_id = catalog.apply(proposal.id).affected[0]
    second_remote = backlog.create(
        type="User Story",
        title="Validar identidad",
        description="d",
        acceptance_criteria=[],
        tags=[f"bg-item:HU-{second_id}", "bg-key:second"],
        parent_id=None,
    )
    catalog.mark_published(second_id, second_remote.id)
    split = catalog.propose(
        _proposal(
            ProposalKind.DIVIDE,
            "split-second",
            targets=[second_id],
            drafts=[Draft(title="Validar persona"), Draft(title="Validar empresa")],
        )
    )
    catalog.decide(split.id, approve=True, by="PO")
    catalog.apply(split.id)
    plan = reconciliation.arm({first_id, second_id})
    original_transition = backlog.transition_state
    failed = False

    def fail_once(work_item_id, *, expected_rev, state):
        nonlocal failed
        if work_item_id == second_remote.id and not failed:
            failed = True
            raise BacklogError("Fallo transitorio.")
        return original_transition(
            work_item_id, expected_rev=expected_rev, state=state
        )

    backlog.transition_state = fail_once
    publication = PublishService(Board(), backlog, ledger, "TP-ITBA")
    partial = execute_approved_reconciliation(
        plan.plan_hash,
        service=publication,
        reconciliation=reconciliation,
        approved_by="full_stack_ia_engineer",
    )
    assert not partial.ok
    assert [result["outcome"] for result in partial.results] == ["retirado", "error"]

    backlog.transition_state = original_transition
    retried = execute_approved_reconciliation(
        plan.plan_hash,
        service=publication,
        reconciliation=reconciliation,
        approved_by="full_stack_ia_engineer",
    )

    assert retried.ok
    assert [result["outcome"] for result in retried.results] == [
        "ya_retirado",
        "retirado",
    ]
