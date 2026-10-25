from pathlib import Path

import pytest

from backlogguard.rag import (
    DeterministicLexicalEmbeddings,
    InMemoryRetriever,
    QdrantRetriever,
    SourceLibrary,
    SourceNotFound,
    build_chunks,
    recursive_chunks,
)
from backlogguard.rag.chunking import split_turns, stable_chunk_id

FIXTURES = Path(__file__).resolve().parent.parent / "evals" / "fixtures"
META = {"source_name": "Reunión X", "source_type": "reunion", "source_date": "2026-03-16"}


def test_turnos_conservan_orador_y_posicion():
    text = "Ana: Primero esto.\nLuis: Segundo turno.\nsigue el segundo.\n"
    turns = split_turns(text)
    assert [t["speaker"] for t in turns] == ["Ana", "Luis"]
    assert turns[1]["text"] == "Segundo turno. sigue el segundo."
    assert text[turns[0]["start"] : turns[0]["end"]].startswith("Ana:")


def test_texto_sin_orador_es_un_turno_anonimo():
    assert split_turns("Solo una frase.")[0]["speaker"] is None


def test_chunks_con_metadata_e_ids_estables():
    text = "Ana: Hola equipo.\nLuis: Nos vemos mañana.\n"
    first = build_chunks("doc", text, META)
    second = build_chunks("doc", text, META)
    assert [c["chunk_id"] for c in first] == [c["chunk_id"] for c in second]
    assert first[0]["metadata"]["speaker"] == "Ana" and first[0]["metadata"]["source_name"] == "Reunión X"
    assert first[0]["chunk_id"] == stable_chunk_id("doc", "turnos", 0, "Hola equipo.")


def test_turno_largo_se_parte_sin_perder_orador():
    sentence = "Esta frase tiene bastantes palabras para ocupar espacio en el turno."
    chunks = build_chunks("doc", "Ana: " + " ".join([sentence] * 12), META, target_words=30)
    assert len(chunks) > 1 and {c["metadata"]["speaker"] for c in chunks} == {"Ana"}


def test_recursive_chunks_respeta_oraciones():
    assert recursive_chunks("Uno dos. Tres cuatro.", target_words=3, overlap_words=0) == ["Uno dos.", "Tres cuatro."]


def test_embeddings_deterministicos_normalizados_y_sin_acentos():
    embeddings = DeterministicLexicalEmbeddings()
    a, b = embeddings.embed_query("Notificación por email"), embeddings.embed_query("notificacion POR email")
    assert a == b and abs(sum(x * x for x in a) - 1) < 1e-9
    assert len(a) == embeddings.dimension
    assert embeddings.embed_query("") == [0.0] * embeddings.dimension


@pytest.fixture(params=["memoria", "qdrant"])
def retriever(request):
    embeddings = DeterministicLexicalEmbeddings()
    if request.param == "memoria":
        return InMemoryRetriever(embeddings)
    client = QdrantRetriever(":memory:", embedding_provider=embeddings)
    request.addfinalizer(client.close)
    return client


def index_fixtures(retriever):
    library = SourceLibrary(FIXTURES)
    for document_id in library.list_ids():
        document = library.load(document_id)
        retriever.index(build_chunks(document_id, document.text, document.metadata.model_dump(mode="json")))


def test_busqueda_devuelve_lo_relevante_con_metadata(retriever):
    index_fixtures(retriever)
    best = retriever.search("email cuando cambia el estado del pedido", top_k=3)[0]
    assert "email" in best.text and best.metadata["source_name"] and best.metadata["speaker"]


def test_filtros_por_metadata(retriever):
    index_fixtures(retriever)
    results = retriever.search("reporte mensual", top_k=8, filters={"source_type": "preventa"})
    assert results and {r.metadata["source_type"] for r in results} == {"preventa"}
    assert retriever.search("reporte", filters={"document_id": "no_existe"}) == []


def test_get_y_reindexado_reemplaza_el_documento(retriever):
    index_fixtures(retriever)
    total = retriever.count()
    found = retriever.search("SSO corporativo", top_k=1)[0]
    assert retriever.get(found.chunk_id).text == found.text
    assert retriever.get("no-existe") is None
    retriever.index(build_chunks(found.document_id, "Ana: Algo totalmente nuevo.", META))
    assert retriever.get(found.chunk_id) is None and retriever.count() < total


def test_consulta_vacia_o_top_k_invalido(retriever):
    with pytest.raises(ValueError):
        retriever.search("   ")
    with pytest.raises(ValueError):
        retriever.search("algo", top_k=0)


def test_biblioteca_carga_fuentes_con_metadata():
    library = SourceLibrary(FIXTURES)
    assert "preventa_acme" in library.list_ids()
    document = library.load("reunion_02_seguimiento")
    assert document.metadata.source_type == "reunion" and document.metadata.source_date.isoformat() == "2026-03-30"


@pytest.mark.parametrize("document_id", ["../README", "..\\x", "no_existe", "A/b", ""])
def test_biblioteca_rechaza_ids_invalidos_o_inexistentes(document_id):
    with pytest.raises(SourceNotFound):
        SourceLibrary(FIXTURES).load(document_id)


def test_all_chunks_lista_y_filtra_en_orden_estable(retriever):
    index_fixtures(retriever)
    everything = retriever.all_chunks()
    assert len(everything) == retriever.count()
    assert [c.chunk_id for c in everything] == sorted(c.chunk_id for c in everything)
    presale = retriever.all_chunks({"source_type": "preventa"})
    assert presale and {c.metadata["source_type"] for c in presale} == {"preventa"}
