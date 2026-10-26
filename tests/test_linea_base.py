"""Línea base de la preventa: huella, registro por corrida, búsqueda separada y regla de citas (docs/specs/linea-base-y-contexto.md)."""
import json
import time
from datetime import date
from pathlib import Path

import pytest
from test_graph import EMAIL, NO_FINDINGS, PLAN, World, final, item_id, verdict

from backlogguard.board import AgentRole, BacklogItem, Board, Citation, ItemState
from backlogguard.graph import index_library
from backlogguard.hitl import request_for_item
from backlogguard.rag import DeterministicLexicalEmbeddings, InMemoryRetriever, QdrantRetriever, SourceLibrary, build_chunks
from backlogguard.rag.sources import (
    SourceChangeNeedsConfirmation,
    SourceMetadata,
    SourceUnchanged,
    fingerprint,
)
from backlogguard.tools import ExecutionContext, ToolCall, ToolPolicy, build_catalog_registry
from backlogguard.tools.critico import CriticToolkit
from backlogguard.tools.requerimientos import RequirementsToolkit

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "evals" / "fixtures"
GHERKIN = "Dado un cliente Cuando ocurre algo Entonces ve el resultado"
STORY = "Como cliente quiero esta función para trabajar mejor."


def meta(name="Propuesta", kind="preventa", when=date(2025, 10, 1), layout="paginas"):
    return SourceMetadata(source_name=name, source_type=kind, source_date=when, layout=layout)


def fixture_world():
    library = SourceLibrary(FIXTURES)
    retriever = InMemoryRetriever(DeterministicLexicalEmbeddings())
    index_library(library, retriever)
    return library, retriever


def run_tool(registry, name, role=AgentRole.REQUERIMIENTOS, **arguments):
    context = ExecutionContext(user_id="u", role=role)
    return registry.run(ToolCall(tool_name=name, arguments=arguments), context=context, policy=ToolPolicy())


def chunk(retriever, document_id, fragment):
    return next(c for c in retriever.all_chunks({"document_id": document_id}) if fragment in c.text)


def draft(retriever, *sources, title="Reporte mensual", **extra):
    return {
        "kind": "historia", "title": title, "description": STORY, "acceptance_criteria": [GHERKIN],
        "citations": [{"chunk_id": chunk(retriever, doc, text).chunk_id, "quote": text} for doc, text in sources], **extra,
    }


# ---- LB-01: huella ----


def test_la_huella_es_estable_y_detecta_cambios():
    assert fingerprint("hola mundo") == fingerprint("  hola mundo \n") and len(fingerprint("x")) == 16
    assert fingerprint("hola mundo") != fingerprint("hola mundos")


def test_la_fuente_guarda_su_huella_y_se_verifica_al_cargar(tmp_path):
    library = SourceLibrary(tmp_path)
    path = library.write("propuesta", meta(), "[[página 1]]\nTexto original.\n")
    assert f"fingerprint: {fingerprint('[[página 1]]' + chr(10) + 'Texto original.')}" in path.read_text(encoding="utf-8")
    assert library.load("propuesta").fingerprint_ok is True
    path.write_text(path.read_text(encoding="utf-8").replace("Texto original", "Texto EDITADO a mano"), encoding="utf-8")
    edited = library.load("propuesta")
    assert edited.fingerprint_ok is False and edited.fingerprint != edited.metadata.fingerprint
    assert SourceLibrary(FIXTURES).load("preventa_acme").fingerprint_ok is None  # las de ejemplo no guardan huella


def test_reimportar_igual_no_escribe_y_distinto_pide_confirmacion(tmp_path):
    library = SourceLibrary(tmp_path)
    assert library.save("propuesta", meta(), "Texto uno.\n").status == "nueva"
    path = tmp_path / "propuesta.md"
    before = path.stat().st_mtime_ns
    time.sleep(0.02)
    with pytest.raises(SourceUnchanged, match="Sin cambios"):
        library.save("propuesta", meta(), "Texto uno.\n")
    assert path.stat().st_mtime_ns == before  # no se escribió nada

    with pytest.raises(SourceChangeNeedsConfirmation, match="contenido") as changed:
        library.save("propuesta", meta(), "Texto dos.\n")
    assert fingerprint("Texto uno.") in str(changed.value) and fingerprint("Texto dos.") in str(changed.value)
    assert "Texto uno" in path.read_text(encoding="utf-8")  # sigue la versión anterior
    status = library.save("propuesta", meta(), "Texto dos.\n", replace=True)
    assert status.status == "cambio" and status.changes == ["contenido"] and "Texto dos" in path.read_text(encoding="utf-8")


def test_cambiar_solo_la_fecha_el_nombre_o_el_tipo_tambien_pide_confirmacion(tmp_path):
    library = SourceLibrary(tmp_path)
    library.save("propuesta", meta(), "Mismo texto.\n")
    for other, label in ((meta(when=date(2025, 11, 1)), "fecha"), (meta(name="Otro nombre"), "nombre"), (meta(kind="minuta"), "tipo")):
        status = library.import_status("propuesta", other, "Mismo texto.\n")
        assert status.status == "cambio" and status.changes == [label]


# ---- LB-02: registro por corrida ----


def test_el_inventario_marca_el_rol_de_cada_fuente():
    rows = {row["id"]: row for row in SourceLibrary(FIXTURES).inventory()}
    assert rows["preventa_acme"]["role"] == "linea_base" and rows["reunion_01_kickoff"]["role"] == "evidencia"
    assert all(len(row["fingerprint"]) == 16 and row["words"] > 0 and row["fingerprint_ok"] is None for row in rows.values())


def test_la_corrida_registra_las_fuentes_y_sus_huellas(tmp_path):
    title = "Notificación por email"
    world = World(tmp_path, supervisor=PLAN, producer=[], critic=[], auditor=NO_FINDINGS)
    world.providers.requerimientos.responses[:] = [world.draft(title, EMAIL), final("ok")]
    world.providers.critico.responses[:] = [verdict(title, "sustentado")]
    state = world.run()
    registered = {row["id"]: row for row in state["sources"]}
    assert set(registered) == set(SourceLibrary(FIXTURES).list_ids())
    assert registered["preventa_acme"]["role"] == "linea_base" and registered["preventa_acme"]["type"] == "preventa"
    assert registered["preventa_acme"]["fingerprint"] == fingerprint(SourceLibrary(FIXTURES).load("preventa_acme").text)


# ---- LB-03: la búsqueda del productor deja afuera la línea base ----


@pytest.fixture(params=["memoria", "qdrant"])
def retrievers(request):
    library = SourceLibrary(FIXTURES)
    embeddings = DeterministicLexicalEmbeddings()
    retriever = InMemoryRetriever(embeddings) if request.param == "memoria" else QdrantRetriever(":memory:", embedding_provider=embeddings)
    index_library(library, retriever)
    return retriever


def test_el_retriever_puede_excluir_por_metadata(retrievers):
    everything = {r.metadata["source_type"] for r in retrievers.hybrid_search("reporte mensual PDF", top_k=8)}
    assert "preventa" in everything
    kept = retrievers.hybrid_search("reporte mensual PDF", top_k=8, exclude={"source_type": "preventa"})
    assert kept and {r.metadata["source_type"] for r in kept} == {"reunion"}


def test_el_productor_no_ve_la_preventa_salvo_que_la_pida():
    library, retriever = fixture_world()
    registry = build_catalog_registry(RequirementsToolkit(library, retriever, Board()).implementations())

    def search(**args):
        result = run_tool(registry, "buscar_en_fuentes", query="reporte mensual PDF", top_k=8, **args)
        assert result.ok, result.content
        return json.loads(result.content)

    default = search()
    assert default and {f["tipo"] for f in default} == {"reunion"} and {f["rol"] for f in default} == {"evidencia"}
    with_baseline = search(incluir_linea_base=True)
    assert {f["rol"] for f in with_baseline} == {"evidencia", "linea_base"}
    assert {f["tipo"] for f in search(source_type="preventa")} == {"preventa"}  # pedirla expresamente alcanza
    assert {f["tipo"] for f in search(document_id="preventa_acme")} == {"preventa"}


# ---- LB-04: una historia necesita respaldo de una reunión ----


def test_una_historia_solo_con_preventa_se_rechaza():
    library, retriever = fixture_world()
    board = Board()
    registry = build_catalog_registry(RequirementsToolkit(library, retriever, board).implementations())
    only_baseline = draft(retriever, ("preventa_acme", "reporte mensual de pedidos exportable en PDF"))
    result = run_tool(registry, "redactar_historia", **only_baseline)
    assert not result.ok and result.metadata["error_type"] == "sin_respaldo_acordado" and "reunión o minuta" in result.content
    assert board.items == {}


def test_la_preventa_como_cita_adicional_se_acepta():
    library, retriever = fixture_world()
    board = Board()
    registry = build_catalog_registry(RequirementsToolkit(library, retriever, board).implementations())
    both = draft(
        retriever, ("reunion_01_kickoff", "El reporte mensual lo necesitamos en PDF"),
        ("preventa_acme", "reporte mensual de pedidos exportable en PDF"),
    )
    created = run_tool(registry, "redactar_historia", **both)
    assert created.ok, created.content
    assert {c.source_type.value for c in board.items[created.metadata["item_id"]].citations} == {"reunion", "preventa"}


def test_corregir_una_historia_tampoco_puede_quedar_solo_con_preventa():
    library, retriever = fixture_world()
    board = Board()
    registry = build_catalog_registry(RequirementsToolkit(library, retriever, board).implementations())
    created = run_tool(registry, "redactar_historia", **draft(retriever, ("reunion_01_kickoff", "El reporte mensual lo necesitamos en PDF")))
    item = board.items[created.metadata["item_id"]]
    item.transition_to(ItemState.OBJETADO)
    revision = draft(retriever, ("preventa_acme", "reporte mensual de pedidos exportable en PDF"), revises=item.id, title="Reporte mensual v2")
    result = run_tool(registry, "redactar_historia", **revision)
    assert result.metadata["error_type"] == "sin_respaldo_acordado" and item.title == "Reporte mensual"


# ---- LB-05: el Crítico lo comprueba ----


def cited_item(retriever, item_id_, document_id, fragment, title):
    found = chunk(retriever, document_id, fragment)
    citation = Citation(
        fragment_id=found.chunk_id, quote=fragment, source_name=found.metadata["source_name"],
        source_type=found.metadata["source_type"], source_date=found.metadata["source_date"], speaker=found.metadata.get("speaker"),
    )
    return BacklogItem(
        id=item_id_, kind="historia", title=title, description=STORY, acceptance_criteria=[GHERKIN], citations=[citation]
    )


def test_el_critico_marca_la_historia_sin_respaldo_acordado():
    _, retriever = fixture_world()
    board = Board()
    board.add_item(cited_item(retriever, "HU-BASE", "preventa_acme", "reporte mensual de pedidos exportable en PDF", "Algo solo vendido"))
    board.add_item(cited_item(retriever, "HU-ACORDADA", "reunion_01_kickoff", "El reporte mensual lo necesitamos en PDF", "Reporte pedido en reunión"))
    registry = build_catalog_registry(CriticToolkit(retriever, board).implementations())

    def checks(item):
        report = json.loads(run_tool(registry, "evaluar_dor_invest", role=AgentRole.CRITICO, item_id=item).content)
        return {c["nombre"]: c["ok"] for c in report["controles"]}

    assert checks("HU-BASE")["respaldo_acordado"] is False and checks("HU-ACORDADA")["respaldo_acordado"] is True


# ---- LB-06: la evidencia distingue línea base de evidencia ----


def test_la_evidencia_de_un_pedido_lleva_el_tipo_de_fuente():
    _, retriever = fixture_world()
    item = cited_item(retriever, "HU-1", "preventa_acme", "reporte mensual de pedidos exportable en PDF", "Reporte")
    item.state = ItemState.OBJETADO
    from backlogguard.tools import load_policy_config

    request = request_for_item(item, load_policy_config(ROOT / "config" / "policy.yaml"))
    assert [e.source_type for e in request.evidence] == ["preventa"]


def test_una_fuente_anterior_a_las_huellas_recibe_la_suya_sin_cambiar_su_contenido(tmp_path):
    library = SourceLibrary(tmp_path)
    old_file = tmp_path / "propuesta.md"
    old_file.write_text(
        "---\nsource_name: Propuesta\nsource_type: preventa\nsource_date: 2025-10-01\nlayout: paginas\n---\nTexto viejo.\n",
        encoding="utf-8",
    )
    assert library.load("propuesta").fingerprint_ok is None
    with pytest.raises(SourceUnchanged, match="se registró la suya"):
        library.save("propuesta", meta(), "Texto viejo.\n")
    loaded = library.load("propuesta")
    assert loaded.fingerprint_ok is True and loaded.text.strip() == "Texto viejo."
