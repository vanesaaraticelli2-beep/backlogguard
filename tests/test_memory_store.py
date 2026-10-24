from datetime import datetime, timedelta, timezone

import pytest

from backlogguard.memory import MemoryCandidate, MemoryScope, MemoryStore, evaluate_write


def candidate(**overrides) -> MemoryCandidate:
    data = dict(
        kind="decision",
        key="formato-reporte",
        value={"decision": "Exportar a Excel"},
        source="Reunión kickoff",
        confirmed=True,
        durable=True,
    )
    data.update(overrides)
    return MemoryCandidate(**data)


@pytest.fixture
def store(tmp_path):
    return MemoryStore(tmp_path / "memory.sqlite")


SCOPE = MemoryScope(user_id="factory", project_id="p1")


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"confirmed": False}, "dato no confirmado"),
        ({"durable": False}, "dato transitorio"),
        ({"sensitive": True}, "dato sensible"),
        ({"key": "api_key-cliente"}, "dato sensible"),
        ({"persist_allowed": False}, "persistencia no permitida"),
        ({"kind": "tool_result"}, "tipo no apto para memoria estable"),
    ],
)
def test_write_gate_rechaza(overrides, reason):
    decision = evaluate_write(candidate(**overrides))
    assert not decision.accepted and decision.reason == reason


def test_write_gate_acepta():
    assert evaluate_write(candidate()).accepted


def test_escribir_y_recuperar(store):
    store.write(scope=SCOPE, candidate=candidate())
    items = store.retrieve(scope=SCOPE, query="excel")
    assert len(items) == 1 and items[0]["value"]["decision"] == "Exportar a Excel"


def test_rechazado_no_modifica_la_base(store):
    with pytest.raises(ValueError):
        store.write(scope=SCOPE, candidate=candidate(confirmed=False))
    assert store.list_scope(SCOPE) == []


def test_aislamiento_por_proyecto(store):
    store.write(scope=SCOPE, candidate=candidate())
    otro = MemoryScope(user_id="factory", project_id="p2")
    assert store.retrieve(scope=otro) == []


def test_supersede_deja_una_vigente_y_conserva_historia(store):
    old_id = store.write(scope=SCOPE, candidate=candidate())
    new_id = store.write(
        scope=SCOPE,
        candidate=candidate(value={"decision": "Exportar a PDF"}),
        supersedes=old_id,
    )
    active = store.list_scope(SCOPE)
    assert [item["memory_id"] for item in active] == [new_id]
    assert active[0]["supersedes"] == old_id
    statuses = {item["memory_id"]: item["status"] for item in store.list_scope(SCOPE, include_inactive=True)}
    assert statuses == {old_id: "superseded", new_id: "active"}


def test_supersede_de_inexistente_falla_sin_cambios(store):
    with pytest.raises(KeyError):
        store.supersede("mem_no_existe", scope=SCOPE, candidate=candidate())
    assert store.list_scope(SCOPE, include_inactive=True) == []


def test_ttl_expirado_no_se_recupera(store):
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    store.write(
        scope=SCOPE,
        candidate=candidate(expires_at=now - timedelta(days=1)),
        now=now - timedelta(days=2),
    )
    assert store.retrieve(scope=SCOPE, now=now) == []


def test_soft_delete(store):
    memory_id = store.write(scope=SCOPE, candidate=candidate())
    store.delete(memory_id, scope=SCOPE)
    assert store.list_scope(SCOPE) == []
    assert store.list_scope(SCOPE, include_inactive=True)[0]["status"] == "deleted"


def test_persiste_entre_reaperturas(tmp_path):
    path = tmp_path / "memory.sqlite"
    MemoryStore(path).write(scope=SCOPE, candidate=candidate())
    assert len(MemoryStore(path).list_scope(SCOPE)) == 1
