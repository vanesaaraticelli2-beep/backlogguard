"""Un requisito, una historia: duplicados frenados al crear y excluidos sin gastar rondas."""
import json

from test_critico import add_item, citation_for, GHERKIN
from test_requerimientos import call, draft_args, email_chunk, make_registry, make_toolkit

from backlogguard.agents.negociacion import negotiate_item
from backlogguard.agents.critico import CriticVerdict
from backlogguard.board import Board, ItemState
from backlogguard.board.similarity import repeat_requirement, repeats
from backlogguard.rag import DeterministicLexicalEmbeddings, InMemoryRetriever, SourceLibrary, build_chunks
from test_critico import FIXTURES

HISTORIAL = "Como analista quiero conservar el historial de cada reintento de una factura para saber cuántas veces fue reprocesada."


def test_dos_redacciones_del_mismo_requisito_se_reconocen_aunque_el_titulo_cambie():
    # caso de la corrida con Infobae: mismo fragmento citado, títulos distintos, textos que dicen casi lo mismo
    assert repeat_requirement(
        "Conservar historial de reprocesos de facturas con cada intento como evento independiente", HISTORIAL, {"f1"},
        "Historial de reintentos de factura y visualización de su línea de tiempo completa",
        "Como analista quiero ver el historial de cada reintento de una factura para saber cuántas veces fue reprocesada.", {"f1"},
    )


def test_dos_historias_distintas_no_se_confunden_aunque_citen_el_mismo_fragmento():
    assert not repeat_requirement(
        "Conservar historial de reprocesos de facturas", HISTORIAL, {"f1"},
        "Parametrizar vigencia del score crediticio", "Como administrador quiero definir la vigencia del score para reconsultar al vencer.", {"f1"},
    )
    # y el mismo texto parecido pero en fuentes distintas no cuenta como repetido
    assert not repeat_requirement("Historial de reprocesos", HISTORIAL, {"f1"}, "Reintentos con registro", HISTORIAL, {"f2"})


def test_el_productor_no_puede_redactar_otra_vez_el_mismo_requisito():
    toolkit, retriever, board = make_toolkit()
    registry, policy = make_registry(toolkit)
    call(registry, policy, "ingestar_y_fragmentar", document_id="reunion_01_kickoff")
    chunk = email_chunk(retriever)
    assert call(registry, policy, "redactar_historia", **draft_args(chunk)).ok
    again = call(
        registry, policy, "redactar_historia",
        **draft_args(chunk, title="Aviso por email cuando cambia el estado", description="Como cliente quiero un email para saber el estado del pedido."),
    )
    assert not again.ok and again.metadata["error_type"] == "posible_duplicado" and "Una historia por requisito" in again.content
    assert len(board.items) == 1


def test_la_busqueda_le_muestra_al_productor_lo_que_ya_redacto():
    toolkit, retriever, board = make_toolkit()
    registry, policy = make_registry(toolkit)
    call(registry, policy, "ingestar_y_fragmentar", document_id="reunion_01_kickoff")
    call(registry, policy, "redactar_historia", **draft_args(email_chunk(retriever)))
    found = call(registry, policy, "buscar_en_fuentes", query="reporte mensual", top_k=2)
    assert [d["titulo"] for d in found.metadata["ya_redactadas"]] == ["Notificación por email"]


def test_un_duplicado_se_excluye_sin_pedir_ni_gastar_rondas():
    retriever = InMemoryRetriever(DeterministicLexicalEmbeddings())
    library = SourceLibrary(FIXTURES)
    for document_id in library.list_ids():
        retriever.index(build_chunks(document_id, library.load(document_id).text, library.load(document_id).metadata.model_dump(mode="json")))
    board = Board()
    citation = citation_for(retriever, "reunion_01_kickoff", "email nuevo estado")
    first = add_item(board, citation, item_id="HU-1", title="Aviso por email al cambiar el estado")
    twin = add_item(board, citation, item_id="HU-2", title="Notificación por email del cambio de estado", description=first.description)
    assert repeats(first, twin)
    calls = []

    def review(item_id):
        calls.append(item_id)
        return CriticVerdict(item_id=item_id, verdict="sustentado")

    result = negotiate_item("HU-2", board=board, retriever=retriever, review=review, revise=lambda *_: calls.append("revise"))
    assert result.outcome == "excluido_duplicado" and calls == []  # ni Crítico ni productor
    assert board.items["HU-2"].state is ItemState.EXCLUIDO and "Duplicado de HU-1" in result.objections[-1]
    # el ítem más viejo sigue su camino normal
    assert negotiate_item("HU-1", board=board, retriever=retriever, review=review, revise=lambda *_: None).outcome == "sustentado"


def test_una_historia_que_se_muestra_distinto_no_se_excluye_aunque_comparta_fuente_y_una_frase():
    # corrida 91ad5002: registrar cada reintento vs visualizar la línea de tiempo (mismo fragmento, resultado visible distinto)
    assert not repeat_requirement(
        "Registrar cada reintento de una factura como evento independiente",
        "Como responsable de facturación quiero que cada reintento de una factura quede registrado como un evento independiente, "
        "incluso si el reproceso termina siendo exitoso, para saber cuántas veces fue reprocesada.", {"f1"},
        "Visualizar la línea de tiempo completa de una factura, con todos sus intentos",
        "Como usuario de negocio quiero visualizar la línea de tiempo completa de una factura, incluyendo cada intento de "
        "procesamiento registrado como evento independiente, para saber cuántas veces fue reprocesada.", {"f1"},
    )
