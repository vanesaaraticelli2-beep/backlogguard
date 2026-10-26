import json
from datetime import date
from pathlib import Path

import pytest

from backlogguard.agents.critico import CriticVerdict, parse_verdict, review_item
from backlogguard.agents.negociacion import negotiate_item
from backlogguard.board import (
    AgentRole,
    BacklogItem,
    Board,
    Citation,
    ItemState,
)
from backlogguard.llm import FakeProvider, InvalidProviderResponseError
from backlogguard.rag import DeterministicLexicalEmbeddings, InMemoryRetriever, SourceLibrary, build_chunks
from backlogguard.tools import ExecutionContext, ToolCall, ToolPolicy, build_catalog_registry
from backlogguard.tools.critico import CriticToolkit, _normalize_quote, check_citations

FIXTURES = Path(__file__).resolve().parent.parent / "evals" / "fixtures"
GHERKIN = "Dado un cliente Cuando ocurre algo Entonces ve el resultado"
STORY = "Como cliente quiero ver mis pedidos para seguirlos."


@pytest.fixture
def world():
    retriever = InMemoryRetriever(DeterministicLexicalEmbeddings())
    library = SourceLibrary(FIXTURES)
    for document_id in library.list_ids():
        document = library.load(document_id)
        retriever.index(build_chunks(document_id, document.text, document.metadata.model_dump(mode="json")))
    return retriever, Board()


def citation_for(retriever, document_id, query, quote=None, **overrides):
    chunk = retriever.search(query, top_k=1, filters={"document_id": document_id})[0]
    data = {
        "fragment_id": chunk.chunk_id,
        "quote": quote or chunk.text,
        "source_name": chunk.metadata["source_name"],
        "source_type": chunk.metadata["source_type"],
        "source_date": chunk.metadata["source_date"],
        "speaker": chunk.metadata["speaker"],
    }
    return Citation(**{**data, **overrides})


def add_item(board, citation, item_id="HU-1", title="Reporte mensual en PDF", **overrides):
    data = {
        "id": item_id,
        "kind": "historia",
        "title": title,
        "description": STORY,
        "acceptance_criteria": [GHERKIN],
        "citations": [citation],
    }
    item = BacklogItem(**{**data, **overrides})
    board.add_item(item)
    return item


# ---- verificación determinística de citas ----


def test_normalizacion_ignora_formato_pero_no_acentos_ni_palabras():
    assert _normalize_quote("  “Hola”   MUNDO ") == _normalize_quote('"hola" mundo')
    assert _normalize_quote("Reunión") != _normalize_quote("Reunion")
    assert _normalize_quote("el reporte") != _normalize_quote("un reporte")


def test_cita_textual_pasa_aunque_cambien_espacios_y_mayusculas(world):
    retriever, board = world
    citation = citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF", quote="  EL REPORTE   mensual lo necesitamos en pdf ")
    (check,) = check_citations(add_item(board, citation), retriever)
    assert check.ok


@pytest.mark.parametrize(
    "quote",
    ["El reporte mensual lo necesitamos en Word", "El reporte anual lo necesitamos en PDF para el comité"],
)
def test_cita_deformada_falla(world, quote):
    retriever, board = world
    citation = citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF", quote=quote)
    (check,) = check_citations(add_item(board, citation), retriever)
    assert not check.ok and "textualmente" in check.reason


def test_cita_con_fragmento_inexistente_o_metadata_distinta(world):
    retriever, board = world
    real = citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF")
    ghost = real.model_copy(update={"fragment_id": "inventado"})
    wrong_date = real.model_copy(update={"source_date": date(2026, 1, 1)})
    first, second = (check_citations(add_item(board, c, item_id=f"HU-{i}", title=f"Titulo {i} distinto"), retriever)[0] for i, c in enumerate((ghost, wrong_date)))
    assert "no existe" in first.reason and not second.ok and "fecha" in second.reason


# ---- tools ----


def run_tool(registry, name, role=AgentRole.CRITICO, **arguments):
    context = ExecutionContext(user_id="u", role=role)
    return registry.run(ToolCall(tool_name=name, arguments=arguments), context=context, policy=ToolPolicy())


def critic_registry(retriever, board):
    return build_catalog_registry(CriticToolkit(retriever, board).implementations())


def test_verificar_cita_como_tool(world):
    retriever, board = world
    add_item(board, citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF"))
    result = run_tool(critic_registry(retriever, board), "verificar_cita", item_id="HU-1")
    assert result.ok and result.metadata["all_ok"] is True
    assert run_tool(critic_registry(retriever, board), "verificar_cita", item_id="nada").metadata["error_type"] == "unknown_item"


def test_contraevidencia_encuentra_la_reunion_posterior_y_excluye_lo_citado(world):
    retriever, board = world
    citation = citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF")
    add_item(board, citation)
    result = run_tool(critic_registry(retriever, board), "buscar_contraevidencia", item_id="HU-1", query="reporte mensual formato")
    fragments = json.loads(result.content)
    assert citation.fragment_id not in {f["chunk_id"] for f in fragments}
    newer = [f for f in fragments if f["mas_reciente_que_la_cita"]]
    assert any("Excel" in f["texto"] for f in newer)


def test_dor_invest_aprueba_un_item_bien_formado(world):
    retriever, board = world
    add_item(board, citation_for(retriever, "reunion_01_kickoff", "listado pedidos filtros"), title="Listado de pedidos con filtros")
    result = run_tool(critic_registry(retriever, board), "evaluar_dor_invest", item_id="HU-1")
    report = json.loads(result.content)
    assert result.metadata["dor_ok"] is True and report["item"]["titulo"] == "Listado de pedidos con filtros"
    assert report["item"]["citas"][0]["fragment_id"]


def test_dor_invest_marca_formato_gherkin_tamano_y_duplicados(world):
    retriever, board = world
    citation = citation_for(retriever, "reunion_03_refinamiento", "SSO falla mensaje")
    add_item(board, citation, item_id="HU-1", title="Autenticación mediante SSO corporativo")
    add_item(
        board,
        citation,
        item_id="HU-2",
        title="Autenticación en el portal mediante SSO corporativo",
        description="Quiero entrar.",
        acceptance_criteria=["debería andar bien"] + [GHERKIN] * 5,
    )
    report = json.loads(run_tool(critic_registry(retriever, board), "evaluar_dor_invest", item_id="HU-2").content)
    failed = {c["nombre"] for c in report["controles"] if not c["ok"]}
    assert failed == {"formato_como_quiero_para", "criterios_gherkin", "tamano_acotado", "sin_duplicados"}


def test_las_tools_del_critico_son_solo_del_critico_y_no_escriben(world):
    retriever, board = world
    add_item(board, citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF"))
    registry = critic_registry(retriever, board)
    for role in (AgentRole.REQUERIMIENTOS, AgentRole.AUDITOR, AgentRole.INTEGRACION):
        assert run_tool(registry, "verificar_cita", role=role, item_id="HU-1").metadata["error_type"] == "unavailable_tool"
    visible = {t.name for t in ToolPolicy().allowed_tools(registry, ExecutionContext(user_id="u", role=AgentRole.CRITICO))}
    assert visible == {"verificar_cita", "buscar_contraevidencia", "evaluar_dor_invest"}


# ---- veredicto y agente ----


def test_veredicto_exige_coherencia():
    with pytest.raises(ValueError):
        CriticVerdict(item_id="HU-1", verdict="objetado")
    with pytest.raises(ValueError):
        CriticVerdict(item_id="HU-1", verdict="sustentado", objections=["x"])
    with pytest.raises(ValueError, match="no de HU-1"):
        parse_verdict('{"item_id": "HU-9", "verdict": "sustentado"}', "HU-1")


def tool(name, **arguments):
    return json.dumps({"action": "tool", "tool_name": name, "arguments": arguments})


def final(**verdict):
    return json.dumps({"action": "final", "final_answer": json.dumps(verdict)})


def test_agente_critico_devuelve_un_veredicto_validado(world):
    retriever, board = world
    add_item(board, citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF"))
    provider = FakeProvider(
        delay_seconds=0,
        responses=[
            tool("evaluar_dor_invest", item_id="HU-1"),
            tool("verificar_cita", item_id="HU-1"),
            tool("buscar_contraevidencia", item_id="HU-1"),
            final(item_id="HU-1", verdict="objetado", objections=["Hay una reunión posterior que pasa el reporte a Excel."]),
        ],
    )
    review = review_item("HU-1", provider=provider, retriever=retriever, board=board, precompute=False)
    assert review.verdict.verdict == "objetado" and review.tokens > 0
    assert "Dado" not in provider.prompts[0] and "HU-1" in provider.prompts[0]
    assert "verificador adversarial" in provider.systems[0]


def test_el_critico_recibe_el_expediente_y_la_traza_lo_registra(world):
    retriever, board = world
    add_item(board, citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF"))
    events = []
    provider = FakeProvider(
        delay_seconds=0,
        responses=[final(item_id="HU-1", verdict="objetado", objections=["Hay una reunión posterior que pasa el reporte a Excel."])],
    )
    review = review_item("HU-1", provider=provider, retriever=retriever, board=board, on_event=events.append)
    assert len(provider.prompts) == 1  # un solo paso del modelo en lugar de cuatro
    assert "Dado" in provider.prompts[0] and "controles" in provider.prompts[0]
    marked = [e["tool"] for e in events if e.get("precalculada")]
    assert marked == ["evaluar_dor_invest", "verificar_cita", "buscar_contraevidencia"]
    assert review.verdict.verdict == "objetado"


def test_el_critico_da_el_mismo_veredicto_con_y_sin_expediente(world):
    retriever, board = world
    add_item(board, citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF"))
    answer = final(item_id="HU-1", verdict="objetado", objections=["Hay una reunión posterior que pasa el reporte a Excel."])
    steps = [tool("evaluar_dor_invest", item_id="HU-1"), tool("verificar_cita", item_id="HU-1"), tool("buscar_contraevidencia", item_id="HU-1")]
    without = review_item("HU-1", provider=FakeProvider(delay_seconds=0, responses=[*steps, answer]), retriever=retriever, board=board, precompute=False)
    with_dossier = review_item("HU-1", provider=FakeProvider(delay_seconds=0, responses=[answer]), retriever=retriever, board=board, precompute=True)
    assert with_dossier.verdict == without.verdict


def test_el_interruptor_de_config_apaga_el_expediente(tmp_path):
    from backlogguard.agents.dossier import dossier_enabled

    path = tmp_path / "ctx.yaml"
    path.write_text("precalculated_dossier: {critico: false}", encoding="utf-8")
    assert dossier_enabled("critico", path=path) is False and dossier_enabled("auditor", path=path) is True
    assert dossier_enabled("critico", True, path=path) is True and dossier_enabled("critico", path=tmp_path / "no.yaml") is True


def test_veredicto_invalido_se_repara_una_vez_y_luego_falla(world):
    retriever, board = world
    add_item(board, citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF"))
    ok = json.dumps({"item_id": "HU-1", "verdict": "sustentado", "objections": [], "reasoning": "ok"})
    bad_final = json.dumps({"action": "final", "final_answer": "me parece bien"})
    repaired = FakeProvider(delay_seconds=0, responses=[bad_final, ok])
    assert review_item("HU-1", provider=repaired, retriever=retriever, board=board).verdict.verdict == "sustentado"
    broken = FakeProvider(delay_seconds=0, responses=[bad_final, "sigue sin ser JSON"])
    with pytest.raises(InvalidProviderResponseError):
        review_item("HU-1", provider=broken, retriever=retriever, board=board)


def test_el_critico_no_llega_a_veredicto_si_agota_pasos(world):
    retriever, board = world
    add_item(board, citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF"))
    provider = FakeProvider(delay_seconds=0, responses=[tool("verificar_cita", item_id="HU-1")] * 5)
    with pytest.raises(InvalidProviderResponseError):
        review_item("HU-1", provider=provider, retriever=retriever, board=board, max_tool_calls=2)


# ---- negociación ----


def verdict(kind, *objections):
    return CriticVerdict(item_id="HU-1", verdict=kind, objections=list(objections))


def scripted_review(*verdicts):
    queue = list(verdicts)
    return lambda item_id: queue.pop(0)


def test_aprobado_en_la_primera_ronda(world):
    retriever, board = world
    item = add_item(board, citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF"))
    result = negotiate_item(
        "HU-1", board=board, retriever=retriever, review=scripted_review(verdict("sustentado")), revise=lambda *a: pytest.fail()
    )
    assert (result.outcome, result.rounds) == ("sustentado", 1) and item.state is ItemState.SUSTENTADO


def test_objecion_correccion_y_acuerdo_en_la_segunda_ronda(world):
    retriever, board = world
    add_item(board, citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF"))
    fixed = citation_for(retriever, "reunion_02_seguimiento", "reporte mensual Excel")
    revised = []

    def revise(item_id, objections):
        revised.append(objections)
        board.items[item_id] = board.items[item_id].model_copy(
            update={"title": "Reporte mensual en Excel", "citations": [fixed]}
        )

    result = negotiate_item(
        "HU-1",
        board=board,
        retriever=retriever,
        review=scripted_review(verdict("objetado", "El reporte ahora es en Excel."), verdict("sustentado")),
        revise=revise,
    )
    item = board.items["HU-1"]
    assert (result.outcome, result.rounds) == ("sustentado", 2) and item.state is ItemState.SUSTENTADO
    assert revised == [["El reporte ahora es en Excel."]]
    assert [o.round for o in item.objections] == [1] and item.objections[0].resolved


def test_sin_consenso_tras_dos_rondas_no_hay_tercera(world):
    retriever, board = world
    add_item(board, citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF"))
    calls = []
    result = negotiate_item(
        "HU-1",
        board=board,
        retriever=retriever,
        review=scripted_review(verdict("objetado", "Falta evidencia."), verdict("objetado", "Sigue sin evidencia.")),
        revise=lambda item_id, objections: calls.append(item_id),
    )
    item = board.items["HU-1"]
    assert (result.outcome, result.rounds) == ("sin_consenso", 2) and item.state is ItemState.OBJETADO
    assert calls == ["HU-1"] and [o.round for o in item.objections] == [1, 2]
    assert not any(o.resolved for o in item.objections)


def test_una_cita_falsa_anula_el_sustentado_del_modelo(world):
    retriever, board = world
    forged = citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF", quote="El reporte mensual lo necesitamos en Word")
    add_item(board, forged)
    result = negotiate_item(
        "HU-1", board=board, retriever=retriever, review=scripted_review(verdict("sustentado")) , revise=lambda *a: None, max_rounds=1
    )
    item = board.items["HU-1"]
    assert result.outcome == "sin_consenso" and item.state is ItemState.OBJETADO
    assert "Cita no verificable" in item.objections[0].text


def test_el_tope_de_rondas_no_se_puede_superar(world):
    retriever, board = world
    add_item(board, citation_for(retriever, "reunion_01_kickoff", "reporte mensual PDF"))
    for rounds in (0, 3):
        with pytest.raises(ValueError):
            negotiate_item("HU-1", board=board, retriever=retriever, review=lambda i: None, revise=lambda *a: None, max_rounds=rounds)
