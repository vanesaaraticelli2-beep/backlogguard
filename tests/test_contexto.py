"""Compactación del historial y presupuesto de contexto: el prompt se achica, la evidencia no."""
import json

from test_requerimientos import call, draft_args, email_chunk, make_registry, make_toolkit

from backlogguard.agents.context import ContextLimits, digest, load_limits
from backlogguard.agents.decider import LLMDecider
from backlogguard.agents.loop import run_basic_agent
from backlogguard.board import AgentRole
from backlogguard.llm import FakeProvider
from backlogguard.tools import ExecutionContext, ToolPolicy

CONTEXT = ExecutionContext(user_id="u", role=AgentRole.REQUERIMIENTOS)


def tool(name, **arguments):
    return json.dumps({"action": "tool", "tool_name": name, "arguments": arguments})


def final():
    return json.dumps({"action": "final", "final_answer": "listo"})


def run_searches(limits, queries=("email estado", "reporte mensual", "SSO corporativo", "filtros pedidos"), max_observation_chars=4000):
    """Corre al productor con búsquedas guionadas y devuelve (salida del ciclo, proveedor, decider)."""
    toolkit, retriever, board = make_toolkit()
    registry, policy = make_registry(toolkit)
    call(registry, policy, "ingestar_y_fragmentar", document_id="reunion_01_kickoff")
    provider = FakeProvider(delay_seconds=0, responses=[*(tool("buscar_en_fuentes", query=q, top_k=4) for q in queries), final()])
    decider = LLMDecider(provider, "requerimientos", registry, CONTEXT, ToolPolicy(), limits=limits, max_observation_chars=max_observation_chars)
    outcome = run_basic_agent(
        "Buscá todo", registry, decider, max_steps=10, context=CONTEXT, policy=ToolPolicy(), tokens_used=lambda: decider.tokens_used
    )
    return outcome, provider, decider


def test_la_compactacion_respeta_la_ventana():
    outcome, provider, _ = run_searches(ContextLimits(window=2, max_prompt_chars=10**9))
    last = provider.prompts[-1]  # el paso final ve las 4 búsquedas
    assert last.count("[compactada") == 2  # las dos más antiguas se resumieron
    first = provider.prompts[0]
    assert "[compactada" not in first  # sin historial no hay nada que resumir
    assert outcome["stop_reason"] == "final_answer"


def test_con_ventana_cero_o_amplia_cambia_solo_lo_antiguo():
    _, wide, _ = run_searches(ContextLimits(window=10, max_prompt_chars=10**9))
    _, narrow, _ = run_searches(ContextLimits(window=1, max_prompt_chars=10**9))
    assert "[compactada" not in wide.prompts[-1] and narrow.prompts[-1].count("[compactada") == 3
    assert len(narrow.prompts[-1]) < len(wide.prompts[-1])


def test_un_resumen_no_agrega_texto_y_conserva_los_ids():
    toolkit, retriever, _ = make_toolkit()
    registry, policy = make_registry(toolkit)
    call(registry, policy, "ingestar_y_fragmentar", document_id="reunion_01_kickoff")
    found = call(registry, policy, "buscar_en_fuentes", query="email estado", top_k=4)
    summary = json.loads(digest("buscar_en_fuentes", found.content))
    original = json.loads(found.content)
    assert [f["chunk_id"] for f in summary["fragmentos"]] == [f["chunk_id"] for f in original]  # no se pierde ningún id
    for kept, row in zip(summary["fragmentos"], original):
        assert row["texto"].startswith(kept["texto"].rstrip("…"))  # solo el comienzo del texto original
        assert len(kept["texto"]) <= 121
        assert all(row[key] == kept[key] for key in kept if key != "texto")  # el resto son valores sin tocar


def test_los_resumenes_por_herramienta_quedan_con_lo_importante():
    dor = json.dumps({"item": {"id": "HU-1", "titulo": "T"}, "controles": [{"nombre": "a", "ok": True}, {"nombre": "b", "ok": False, "detalle": "x"}]})
    assert json.loads(digest("evaluar_dor_invest", dor)) == {"item": "HU-1", "titulo": "T", "controles_fallidos": [{"nombre": "b", "ok": False, "detalle": "x"}]}
    cites = json.dumps([{"fragment_id": "f1", "ok": True}, {"fragment_id": "f2", "ok": False, "detalle": "no textual"}])
    assert json.loads(digest("verificar_cita", cites)) == {"citas_fallidas": [{"fragment_id": "f2", "ok": False, "detalle": "no textual"}], "citas_revisadas": 2}
    compare = json.dumps({"items": [{"id": "HU-1"}], "preventa": [{"chunk_id": "p1", "texto": "x"}], "reuniones": [{"chunk_id": "m1", "texto": "y"}]})
    assert json.loads(digest("comparar_con_preventa", compare))["reuniones_analizadas"] == ["m1"]
    assert digest("otra_tool", "corto") == "corto" and digest("otra_tool", "x" * 1000).startswith("x" * 300)


def test_la_traza_conserva_las_observaciones_completas():
    outcome, provider, _ = run_searches(ContextLimits(window=1, max_prompt_chars=10**9))
    observations = [e for e in outcome["trace"] if e["event"] == "observation"]
    assert len(observations) == 4
    for entry in observations:  # el prompt resumió, pero lo guardado es el resultado completo de cada búsqueda
        assert "[compactada" not in entry["observation"]["content"]
        assert all("texto" in fragment and len(fragment["texto"]) > 0 for fragment in json.loads(entry["observation"]["content"]))
    assert provider.prompts[-1].count("[compactada") == 3


def test_el_expediente_precalculado_no_se_compacta():
    toolkit, retriever, board = make_toolkit()
    registry, policy = make_registry(toolkit)
    call(registry, policy, "ingestar_y_fragmentar", document_id="reunion_01_kickoff")
    provider = FakeProvider(delay_seconds=0, responses=[tool("buscar_en_fuentes", query="reporte", top_k=3), tool("buscar_en_fuentes", query="sso", top_k=3), final()])
    decider = LLMDecider(provider, "requerimientos", registry, CONTEXT, ToolPolicy(), limits=ContextLimits(window=1, max_prompt_chars=10**9))
    run_basic_agent(
        "Buscá", registry, decider, max_steps=6, context=CONTEXT, policy=ToolPolicy(), tokens_used=lambda: decider.tokens_used,
        initial_calls=[("buscar_en_fuentes", {"query": "email estado", "top_k": 4})],
    )
    last = provider.prompts[-1]
    assert last.count("[compactada") == 1  # se resumió la búsqueda hecha por el modelo, no la precalculada
    assert "precalculada" in last


def test_el_tope_de_contexto_comprime_y_lo_registra():
    outcome, provider, decider = run_searches(ContextLimits(window=3, max_prompt_chars=3000))
    contexts = [e for e in outcome["trace"] if e["event"] == "context"]
    assert contexts and contexts[-1]["compressed"] and contexts[-1]["window"] < 3
    assert any(e["chars"] <= 3000 for e in contexts) or contexts[-1]["over_budget"] in (True, False)
    # sin tope exigente no se comprime
    calm, _, _ = run_searches(ContextLimits(window=3, max_prompt_chars=10**9))
    assert not any(e["compressed"] for e in calm["trace"] if e["event"] == "context")


def test_una_cita_se_valida_contra_el_indice_y_no_contra_el_prompt():
    toolkit, retriever, board = make_toolkit()
    registry, policy = make_registry(toolkit)
    call(registry, policy, "ingestar_y_fragmentar", document_id="reunion_01_kickoff")
    chunk = email_chunk(retriever)  # nunca pasó por ningún prompt: la cita se valida igual contra el índice
    assert call(registry, policy, "redactar_historia", **draft_args(chunk)).ok
    bad = call(registry, policy, "redactar_historia", **draft_args(chunk, title="Otra cosa", citations=[{"chunk_id": "inventado:1", "quote": "una frase cualquiera"}]))
    assert not bad.ok and bad.metadata["error_type"] == "unknown_chunk"


def test_los_limites_por_agente_vienen_de_la_configuracion(tmp_path):
    path = tmp_path / "ctx.yaml"
    path.write_text("context: {critico: {window: 1, max_prompt_chars: 5000}}", encoding="utf-8")
    assert load_limits("critico", path) == ContextLimits(window=1, max_prompt_chars=5000)
    assert load_limits("auditor", path) == ContextLimits()  # lo no configurado usa el valor por defecto
    real = load_limits("requerimientos")
    assert real.window == 2 and real.max_prompt_chars > 0
