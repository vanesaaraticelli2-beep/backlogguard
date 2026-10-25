"""Plan de publicación: armado (dry-run), revalidación y ejecución idempotente.

Todo es código determinístico. El plan se arma comparando los ítems sustentados del tablero con el
backlog; su hash cubre el contenido de cada ítem y lo observado en el backlog, pero no el estado
del ítem, de modo que aprobar los ítems no cambia el hash que se aprobó.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backlogguard.board import BacklogItem, Board, ItemKind, ItemState
from backlogguard.board.similarity import similar_titles
from backlogguard.integrations.gateway import BacklogError, BacklogGateway, WorkItem
from backlogguard.integrations.ledger import PublicationLedger

WORK_ITEM_TYPE = {
    ItemKind.EPICA: "Epic",
    ItemKind.HISTORIA: "User Story",
    ItemKind.TAREA: "Task",
    ItemKind.CASO_DE_PRUEBA: "Test Case",
}
KIND_RANK = {ItemKind.EPICA: 0, ItemKind.HISTORIA: 1, ItemKind.TAREA: 2, ItemKind.CASO_DE_PRUEBA: 3}
PUBLISHABLE = (ItemState.SUSTENTADO, ItemState.APROBADO)
KEY_PREFIX, ITEM_PREFIX = "bg-key:", "bg-item:"

Action = Literal["crear", "actualizar", "vincular", "omitir"]


class PlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    kind: ItemKind
    work_item_type: str
    action: Action
    reason: str
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    idempotency_key: str
    parent_item_id: str | None = None
    remote_id: int | None = None
    expected_rev: int | None = None

    @property
    def item_tag(self) -> str:
        return f"{ITEM_PREFIX}{self.item_id}"

    @property
    def key_tag(self) -> str:
        return f"{KEY_PREFIX}{self.idempotency_key}"


class PublishPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: str
    items: list[PlanItem] = Field(default_factory=list)

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)

    @property
    def plan_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()[:16]

    def counts(self) -> dict[str, int]:
        counts = {"crear": 0, "actualizar": 0, "vincular": 0, "omitir": 0}
        for item in self.items:
            counts[item.action] += 1
        return counts

    @property
    def has_changes(self) -> bool:
        return any(item.action != "omitir" for item in self.items)


class ItemOutcome(BaseModel):
    item_id: str
    action: str
    outcome: Literal["publicado", "actualizado", "vinculado", "recuperado", "omitido", "ya_publicado", "error", "no_publicado"]
    remote_id: int | None = None
    detail: str = ""


class ExecutionReport(BaseModel):
    ok: bool
    error: str | None = None
    results: list[ItemOutcome] = Field(default_factory=list)

    @property
    def written(self) -> int:
        return sum(1 for r in self.results if r.outcome in ("publicado", "actualizado", "vinculado"))


def content_hash(item: BacklogItem) -> str:
    payload = [item.kind.value, item.title, item.description, item.acceptance_criteria]
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()


def idempotency_key(project: str, item: BacklogItem) -> str:
    return hashlib.sha1(f"{project}|{item.id}|{content_hash(item)}".encode("utf-8")).hexdigest()[:16]


def _equivalent(title: str, work_item_type: str, candidates: list[WorkItem]) -> WorkItem | None:
    """Work item cargado a mano que parece el mismo ítem (mismo tipo y título casi igual)."""
    for other in candidates:
        if other.type != work_item_type or any(tag.startswith(ITEM_PREFIX) for tag in other.tags):
            continue
        if similar_titles(title, other.title):
            return other
    return None


def _publish_order(items: list[PlanItem]) -> list[PlanItem]:
    """Padres antes que hijos; dentro de lo posible, épicas, historias, tareas y casos de prueba."""
    by_id = {item.item_id: item for item in items}
    ordered: list[PlanItem] = []
    seen: set[str] = set()

    def visit(item: PlanItem) -> None:
        if item.item_id in seen:
            return
        seen.add(item.item_id)
        if item.parent_item_id in by_id:
            visit(by_id[item.parent_item_id])
        ordered.append(item)

    for item in sorted(items, key=lambda i: (KIND_RANK[i.kind], i.item_id)):
        visit(item)
    return ordered


class PublishService:
    def __init__(
        self,
        board: Board,
        backlog: BacklogGateway,
        ledger: PublicationLedger,
        project: str,
        excluded: frozenset[str] = frozenset(),
    ):
        self.excluded = excluded  # ítems que una persona sacó del plan
        self.board = board
        self.backlog = backlog
        self.ledger = ledger
        self.project = project

    # ---- armado ----

    def build(self) -> PublishPlan:
        publishable = {
            item.id: item for item in self.board.items.values() if item.state in PUBLISHABLE and item.id not in self.excluded
        }
        everything = self.backlog.search()
        plan_items: list[PlanItem] = []
        kept: list[BacklogItem] = []  # ítems a crear en este plan, para no publicar dos casi iguales
        for item in sorted(publishable.values(), key=lambda i: i.id):
            wi_type, key = WORK_ITEM_TYPE[item.kind], idempotency_key(self.project, item)
            tag, key_tag = f"{ITEM_PREFIX}{item.id}", f"{KEY_PREFIX}{key}"
            parent = item.parent_id if item.parent_id in publishable else None
            remote = next(iter(self.backlog.search(tag=tag)), None)
            base = dict(
                item_id=item.id, kind=item.kind, work_item_type=wi_type, title=item.title, description=item.description,
                acceptance_criteria=list(item.acceptance_criteria), idempotency_key=key, parent_item_id=parent,
            )
            if remote is None:
                twin = _equivalent(item.title, wi_type, everything)
                if twin:
                    plan_items.append(PlanItem(**base, action="omitir", remote_id=twin.id, expected_rev=twin.rev,
                                               reason=f"posible duplicado del work item #{twin.id} cargado a mano: revisar antes de crear"))
                elif sibling := next((k for k in kept if k.kind is item.kind and similar_titles(item.title, k.title)), None):
                    plan_items.append(PlanItem(**base, action="omitir",
                                               reason=f"posible duplicado del ítem {sibling.id} de este mismo plan: revisar antes de crear"))
                else:
                    kept.append(item)
                    plan_items.append(PlanItem(**base, action="crear", reason="no existe en el backlog"))
            elif key_tag not in remote.tags:
                plan_items.append(PlanItem(**base, action="actualizar", remote_id=remote.id, expected_rev=remote.rev,
                                           reason=f"el contenido cambió desde la versión publicada en #{remote.id}"))
            else:
                wanted = next(iter(self.backlog.search(tag=f"{ITEM_PREFIX}{parent}")), None) if parent else None
                if parent and (wanted is None or remote.parent_id != wanted.id):
                    plan_items.append(PlanItem(**base, action="vincular", remote_id=remote.id, expected_rev=remote.rev,
                                               reason=f"falta vincular #{remote.id} con su padre"))
                else:
                    plan_items.append(PlanItem(**base, action="omitir", remote_id=remote.id, expected_rev=remote.rev,
                                               reason=f"ya publicado en #{remote.id}, sin cambios"))
        return PublishPlan(project=self.project, items=_publish_order(plan_items))

    def arm(self) -> PublishPlan:
        plan = self.build()
        self.ledger.save_plan(plan.plan_hash, plan.canonical_json())
        return plan

    # ---- revalidación ----

    def stored_plan(self, plan_hash: str) -> PublishPlan | None:
        raw = self.ledger.load_plan(plan_hash)
        return PublishPlan.model_validate_json(raw) if raw else None

    def drift(self, plan: PublishPlan) -> list[dict]:
        """Diferencias entre el plan aprobado y lo que se armaría hoy, salvo ítems ya intentados."""
        now = {item.item_id: item for item in self.build().items}
        diffs = []
        for item in plan.items:
            if item.action in ("crear", "actualizar") and self.ledger.get(item.idempotency_key):
                continue  # ya se intentó publicar: lo resuelve la recuperación, no es deriva
            current = now.get(item.item_id)
            if item.action == "vincular" and current and current.action == "omitir" and current.remote_id == item.remote_id:
                continue  # el vínculo ya se aplicó
            if current is None:
                diffs.append({"item_id": item.item_id, "plan": item.action, "ahora": "fuera del plan"})
            elif current.model_dump() != item.model_dump():
                diffs.append({"item_id": item.item_id, "plan": item.action, "ahora": current.action, "motivo": current.reason})
        planned = {item.item_id for item in plan.items}
        diffs.extend({"item_id": i, "plan": "no estaba", "ahora": now[i].action} for i in now if i not in planned)
        return diffs

    # ---- ejecución ----

    def execute(self, plan_hash: str) -> ExecutionReport:
        plan = self.stored_plan(plan_hash)
        if plan is None:
            return ExecutionReport(ok=False, error="No existe un plan armado con ese hash.")
        if plan.plan_hash != plan_hash:
            return ExecutionReport(ok=False, error="El plan guardado no coincide con su hash.")
        if diffs := self.drift(plan):
            return ExecutionReport(ok=False, error=f"El backlog o el tablero cambiaron desde que se armó el plan: {diffs}")

        remote_ids: dict[str, int] = {item.item_id: item.remote_id for item in plan.items if item.remote_id}
        results: list[ItemOutcome] = []
        for position, item in enumerate(plan.items):
            try:
                outcome = self._publish(item, remote_ids)
            except BacklogError as exc:
                results.append(ItemOutcome(item_id=item.item_id, action=item.action, outcome="error", detail=str(exc)))
                results.extend(
                    ItemOutcome(item_id=rest.item_id, action=rest.action, outcome="no_publicado")
                    for rest in plan.items[position + 1 :]
                )
                return ExecutionReport(ok=False, error=f"Se detuvo en {item.item_id}: {exc}", results=results)
            if outcome.remote_id:
                remote_ids[item.item_id] = outcome.remote_id
            results.append(outcome)
        return ExecutionReport(ok=True, results=results)

    def _publish(self, item: PlanItem, remote_ids: dict[str, int]) -> ItemOutcome:
        def done(outcome: str, remote_id: int | None, detail: str = "") -> ItemOutcome:
            return ItemOutcome(item_id=item.item_id, action=item.action, outcome=outcome, remote_id=remote_id, detail=detail)

        if item.action == "omitir":
            return done("omitido", item.remote_id, item.reason)
        if item.action == "vincular":  # idempotente por estado: se compara con el padre actual
            parent_remote = remote_ids.get(item.parent_item_id) if item.parent_item_id else None
            if parent_remote is None:
                raise BacklogError(f"no se pudo vincular {item.item_id}: su padre todavía no existe en el backlog")
            current = self.backlog.get(item.remote_id)
            if current and current.parent_id == parent_remote:
                return done("ya_publicado", current.id, "ya estaba vinculado")
            linked = self.backlog.link_parent(item.remote_id, parent_remote, expected_rev=item.expected_rev)
            return done("vinculado", linked.id)

        previous = self.ledger.get(item.idempotency_key)
        if previous and previous["status"] == "done":
            return done("ya_publicado", previous["remote_id"], "ya figuraba como publicado")

        self.ledger.record_intent(item.idempotency_key, item.item_id)
        applied = next(iter(self.backlog.search(tag=item.key_tag)), None)  # ¿ya se aplicó antes (resultado ambiguo)?
        if applied and item.action in ("crear", "actualizar"):
            self.ledger.mark_done(item.idempotency_key, applied.id)
            return done("recuperado", applied.id, "la operación anterior sí se había aplicado")

        parent_remote = remote_ids.get(item.parent_item_id) if item.parent_item_id else None
        if item.action == "crear":
            created = self.backlog.create(
                type=item.work_item_type, title=item.title, description=item.description,
                acceptance_criteria=item.acceptance_criteria, tags=[item.item_tag, item.key_tag], parent_id=parent_remote,
            )
            self.ledger.mark_done(item.idempotency_key, created.id)
            return done("publicado", created.id)
        if item.action == "actualizar":
            current = self.backlog.get(item.remote_id)
            tags = [t for t in (current.tags if current else []) if not t.startswith(KEY_PREFIX)] + [item.key_tag]
            updated = self.backlog.update(
                item.remote_id, expected_rev=item.expected_rev, title=item.title, description=item.description,
                acceptance_criteria=item.acceptance_criteria, tags=tags,
            )
            self.ledger.mark_done(item.idempotency_key, updated.id)
            return done("actualizado", updated.id)
        raise BacklogError(f"acción desconocida: {item.action}")  # pragma: no cover
