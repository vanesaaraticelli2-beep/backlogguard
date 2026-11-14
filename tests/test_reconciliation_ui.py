from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

from backlogguard.board import BacklogItem, Board, Citation, ItemKind, ItemState, SourceType
from backlogguard.catalog import Catalog, Draft, Evidence, Proposal, ProposalKind
from backlogguard.integrations import PublicationLedger, SimulatedBacklog
from backlogguard.llm import Settings


def _controller(tmp_path: Path):
    catalog = Catalog(tmp_path / "catalog.sqlite")
    evidence = Evidence(
        fragment_id="meeting:1",
        quote="Se acordó el requisito.",
        source_name="Reunión",
        source_type=SourceType.REUNION,
        source_date=date(2026, 1, 20),
        source_id="meeting",
        source_fingerprint="fingerprint",
    )
    proposal = catalog.propose(
        Proposal(
            source_id="meeting",
            fingerprint="fingerprint",
            candidate_key="requirement",
            kind=ProposalKind.NUEVO,
            drafts=[Draft(title="Validar identidad")],
            evidence=[evidence],
        )
    )
    catalog.decide(proposal.id, approve=True, by="PO")
    requirement_id = catalog.apply(proposal.id).affected[0]
    backlog = SimulatedBacklog()
    remote = backlog.create(
        type="User Story",
        title="Validar identidad",
        description="",
        acceptance_criteria=[],
        tags=[f"bg-item:HU-{requirement_id}"],
        parent_id=None,
    )
    catalog.mark_published(requirement_id, remote.id)
    split = catalog.propose(
        Proposal(
            source_id="meeting",
            fingerprint="fingerprint",
            candidate_key="split",
            kind=ProposalKind.DIVIDE,
            targets=[requirement_id],
            drafts=[Draft(title="Validar persona"), Draft(title="Validar empresa")],
            evidence=[evidence],
        )
    )
    catalog.decide(split.id, approve=True, by="PO")
    catalog.apply(split.id)
    deps = SimpleNamespace(
        catalog=catalog,
        backlog=backlog,
        ledger=PublicationLedger(tmp_path / "publications.sqlite"),
        project="TP-ITBA",
    )
    processed_board = Board(
        items={
            "HU-001": BacklogItem(
                id="HU-001",
                kind=ItemKind.HISTORIA,
                title="Historia previamente procesada",
                requirement_id=requirement_id,
                requirement_version=1,
                citations=[
                    Citation(
                        fragment_id="meeting:1",
                        quote="Se acordó el requisito.",
                        source_name="Reunión",
                        source_type=SourceType.REUNION,
                        source_date=date(2026, 1, 20),
                    )
                ],
                state=ItemState.SUSTENTADO,
            )
        }
    )
    return SimpleNamespace(
        deps=deps,
        read_only=False,
        running=False,
        settings=Settings(azdo_mode="simulated"),
        thread_id="run-ui",
        pending=lambda: None,
        state=lambda: {},
        list_runs=lambda: [
            {"thread_id": "run-processed", "status": "completada", "items": 1, "waiting": False}
        ],
        saved_run_state=lambda thread_id: {"board": processed_board.model_dump(mode="json")},
    )


def _page():
    import streamlit as st

    from backlogguard.ui.app import tab_reconciliation

    tab_reconciliation(st.session_state["controller"], st.session_state["person"])


def _sync_page():
    import streamlit as st

    from backlogguard.ui.app import tab_azure_sync

    tab_azure_sync(st.session_state["controller"], st.session_state["person"])


def test_pestana_de_sincronizacion_reune_el_plan_y_la_etapa_de_retiro(tmp_path):
    controller = _controller(tmp_path)
    at = streamlit_testing.AppTest.from_function(_sync_page, default_timeout=30)
    at.session_state["controller"] = controller
    at.session_state["person"] = SimpleNamespace(
        role="full_stack_ia_engineer", name="full_stack_ia_engineer"
    )

    at.run()

    assert not at.exception
    assert any("Aplicar a Azure el resultado ya revisado" in item.value for item in at.markdown)
    assert at.button(key="reconciliation_TP-ITBA_analyze")


def test_sincronizacion_prepara_dry_run_de_una_corrida_guardada_sin_escrituras(tmp_path):
    controller = _controller(tmp_path)
    at = streamlit_testing.AppTest.from_function(_sync_page, default_timeout=30)
    at.session_state["controller"] = controller
    at.session_state["person"] = SimpleNamespace(
        role="full_stack_ia_engineer", name="full_stack_ia_engineer"
    )

    at.run()
    assert at.button(key="azure_backfill_build").label == "Comparar historias con Azure"
    writes_before = controller.deps.backlog.writes
    at.button(key="azure_backfill_build").click().run()

    assert not at.exception
    assert any("1 para crear" in item.value for item in at.markdown)
    assert controller.deps.backlog.writes == writes_before


def test_sincronizacion_solo_publica_el_dry_run_tras_aprobacion_explicita(tmp_path):
    controller = _controller(tmp_path)
    controller.settings = Settings(azdo_mode="real")
    at = streamlit_testing.AppTest.from_function(_sync_page, default_timeout=30)
    at.session_state["controller"] = controller
    at.session_state["person"] = SimpleNamespace(
        role="full_stack_ia_engineer", name="full_stack_ia_engineer"
    )

    at.run()
    writes_before = controller.deps.backlog.writes
    at.button(key="azure_backfill_build").click().run()
    assert controller.deps.backlog.writes == writes_before

    at.checkbox(key="azure_publication_TP-ITBA_real_run-processed_approve").check().run()
    at.button(key="azure_publication_TP-ITBA_real_run-processed_execute").click().run()

    assert not at.exception
    assert controller.deps.backlog.writes == writes_before + 1
    assert any("Publicación completada" in item.value for item in at.success)
    remote = controller.deps.backlog.search(tag="bg-item:HU-001")[0]
    requirement = controller.deps.catalog.requirements()[0]
    assert controller.deps.catalog.publication(requirement.id)["remote_id"] == remote.id


def test_reconciliation_ui_muestra_preview_y_exige_aprobacion_del_ingeniero(tmp_path):
    controller = _controller(tmp_path)
    at = streamlit_testing.AppTest.from_function(_page, default_timeout=30)
    at.session_state["controller"] = controller
    at.session_state["person"] = SimpleNamespace(
        role="full_stack_ia_engineer", name="full_stack_ia_engineer"
    )
    at.run()
    at.button(key="reconciliation_TP-ITBA_analyze").click().run()
    assert not at.exception
    assert any("Requisito" in str(table.value) for table in at.dataframe)
    labels = at.multiselect(key="reconciliation_TP-ITBA_selection").options
    at.multiselect(key="reconciliation_TP-ITBA_selection").select(labels[0]).run()
    at.button(key="reconciliation_TP-ITBA_arm").click().run()
    assert any("Dry-run" in element.value for element in at.markdown)
    execute_button = next(
        button
        for button in at.button
        if button.key.startswith("reconciliation_TP-ITBA_")
        and button.key.endswith("_execute")
    )
    assert execute_button.disabled


def test_ingeniero_puede_aprobar_un_retiro_simulado_tras_el_dry_run(tmp_path):
    controller = _controller(tmp_path)
    at = streamlit_testing.AppTest.from_function(_page, default_timeout=30)
    at.session_state["controller"] = controller
    at.session_state["person"] = SimpleNamespace(
        role="full_stack_ia_engineer", name="full_stack_ia_engineer"
    )
    at.run()
    at.button(key="reconciliation_TP-ITBA_analyze").click().run()
    labels = at.multiselect(key="reconciliation_TP-ITBA_selection").options
    at.multiselect(key="reconciliation_TP-ITBA_selection").select(labels[0]).run()
    at.button(key="reconciliation_TP-ITBA_arm").click().run()
    checkbox = next(
        element for element in at.checkbox if "Confirmo retirar" in element.label
    )
    checkbox.check().run()
    execute_button = next(
        button
        for button in at.button
        if button.key.startswith("reconciliation_TP-ITBA_")
        and button.key.endswith("_execute")
    )
    execute_button.click().run()

    assert not at.exception
    assert any("Reconciliación completada" in element.value for element in at.success)
    item = controller.deps.catalog.requirements()[0]
    remote_id = controller.deps.catalog.publication(item.id)["remote_id"]
    assert controller.deps.backlog.get(remote_id).state == "Removed"
