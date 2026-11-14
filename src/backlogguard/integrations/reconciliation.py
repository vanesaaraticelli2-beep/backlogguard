"""Dry-run and approval-gated retirement of superseded, BacklogGuard-owned work items."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backlogguard.catalog import Catalog, RequirementStatus
from backlogguard.integrations.gateway import BacklogError, BacklogGateway
from backlogguard.integrations.ledger import PublicationLedger

OWNER_TAG_PREFIX = "bg-item:HU-"
REMOVED_CATEGORY = "Removed"
TERMINAL_CATEGORIES = {"Removed", "Completed"}


class RetirementPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    remote_id: int
    title: str
    current_state: str
    expected_rev: int
    target_state: str | None = None
    action: Literal["retirar", "omitido", "bloqueado"]
    reason: str


class RetirementPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: str
    selected_ids: list[str] = Field(default_factory=list)
    items: list[RetirementPlanItem] = Field(default_factory=list)

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)

    @property
    def plan_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()[:16]

    @property
    def selected_items(self) -> list[RetirementPlanItem]:
        return [item for item in self.items if item.action == "retirar"]


class RetirementReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    plan_hash: str
    error: str | None = None
    results: list[dict] = Field(default_factory=list)


class ReconciliationService:
    def __init__(
        self,
        catalog: Catalog,
        backlog: BacklogGateway,
        ledger: PublicationLedger,
        project: str,
    ):
        self.catalog = catalog
        self.backlog = backlog
        self.ledger = ledger
        self.project = project

    def build(self, selected_ids: set[str] | None = None) -> RetirementPlan:
        selected = selected_ids or set()
        candidates = []
        for requirement in self.catalog.requirements():
            if requirement.status is RequirementStatus.ACTIVO:
                continue
            publication = self.catalog.publication(requirement.id)
            if publication and publication["remote_id"]:
                candidates.append((requirement, int(publication["remote_id"])))

        known_ids = {requirement.id for requirement, _ in candidates}
        if not selected <= known_ids:
            raise ValueError(f"Selección de requisitos desconocidos: {sorted(selected - known_ids)}")

        items = []
        states_by_type: dict[str, list[dict[str, str]]] = {}

        def states_for(work_item_type: str) -> list[dict[str, str]]:
            if work_item_type not in states_by_type:
                states_by_type[work_item_type] = self.backlog.list_work_item_states(
                    work_item_type
                )
            return states_by_type[work_item_type]

        for requirement, remote_id in candidates:
            item = self.backlog.get(remote_id)
            reason = ""
            target_state = None
            action: Literal["retirar", "omitido", "bloqueado"] = "omitido"
            if item is None:
                reason = "el work item publicado ya no existe en el proyecto"
                action = "bloqueado"
            elif f"{OWNER_TAG_PREFIX}{requirement.id}" not in item.tags:
                reason = "no se encontró la marca de propiedad de BacklogGuard; requiere revisión manual"
                action = "bloqueado"
            else:
                states = states_for(item.type)
                category_by_name = {
                    state["name"]: state["category"] for state in states
                }
                current_category = category_by_name.get(item.state)
                if current_category == REMOVED_CATEGORY:
                    reason = "ya está retirado en Azure"
                else:
                    target_state = next(
                        (
                            state["name"]
                            for state in states
                            if state["category"] == REMOVED_CATEGORY
                        ),
                        None,
                    )
                    if target_state is None:
                        reason = f"el proceso Azure no ofrece un estado de categoría {REMOVED_CATEGORY}"
                        action = "bloqueado"
                    else:
                        active_children = []
                        for child in self.backlog.get_children(remote_id):
                            child_states = states_for(child.type)
                            child_categories = {
                                state["name"]: state["category"] for state in child_states
                            }
                            if child_categories.get(child.state) not in TERMINAL_CATEGORIES:
                                active_children.append(f"#{child.id} {child.title}")
                        if active_children:
                            reason = (
                                "tiene hijos no retirados o no completados: "
                                + ", ".join(active_children)
                            )
                            action = "bloqueado"
                        elif requirement.id in selected:
                            reason = (
                                f"requisito {requirement.status.value}; se propone cambiar "
                                f"el estado a {target_state}"
                            )
                            action = "retirar"
                        else:
                            reason = "elegible; todavía no seleccionado para retirar"
            items.append(
                RetirementPlanItem(
                    requirement_id=requirement.id,
                    remote_id=remote_id,
                    title=item.title if item else requirement.current.draft.title,
                    current_state=item.state if item else "desconocido",
                    expected_rev=item.rev if item else 0,
                    target_state=target_state,
                    action=action,
                    reason=reason,
                )
            )
        return RetirementPlan(
            project=self.project,
            selected_ids=sorted(selected),
            items=items,
        )

    def arm(self, selected_ids: set[str]) -> RetirementPlan:
        plan = self.build(selected_ids)
        if not plan.selected_items:
            raise ValueError("El plan no contiene retiros elegibles.")
        self.ledger.save_plan(f"retire-{plan.plan_hash}", plan.canonical_json())
        return plan

    def execute(self, plan_hash: str) -> RetirementReport:
        saved = self.ledger.load_plan(f"retire-{plan_hash}")
        if saved is None:
            return RetirementReport(
                ok=False, plan_hash=plan_hash, error="No existe el plan de retiro aprobado."
            )
        plan = RetirementPlan.model_validate_json(saved)
        if plan.plan_hash != plan_hash:
            return RetirementReport(
                ok=False, plan_hash=plan_hash, error="El plan no coincide con su hash."
            )
        try:
            current = self.build(set(plan.selected_ids))
        except (BacklogError, ValueError) as exc:
            return RetirementReport(ok=False, plan_hash=plan_hash, error=str(exc))

        current_items = {item.requirement_id: item for item in current.items}
        for planned in plan.selected_items:
            observed = current_items.get(planned.requirement_id)
            already_retired = (
                observed is not None
                and observed.action == "omitido"
                and observed.reason == "ya está retirado en Azure"
            )
            if already_retired:
                continue
            if observed is None or observed.model_dump() != planned.model_dump():
                return RetirementReport(
                    ok=False,
                    plan_hash=plan_hash,
                    error=(
                        f"El work item #{planned.remote_id} o su jerarquía cambiaron "
                        "desde el dry-run. Armá un plan nuevo."
                    ),
                )

        results: list[dict] = []
        for position, planned in enumerate(plan.selected_items):
            try:
                current_item = self.backlog.get(planned.remote_id)
                if current_item is None:
                    raise BacklogError(f"El work item #{planned.remote_id} ya no existe.")
                if f"{OWNER_TAG_PREFIX}{planned.requirement_id}" not in current_item.tags:
                    raise BacklogError(
                        f"El work item #{planned.remote_id} ya no conserva la marca de propiedad."
                    )
                if self._is_removed(current_item):
                    result = "ya_retirado"
                else:
                    retired = self.backlog.transition_state(
                        current_item.id,
                        expected_rev=planned.expected_rev,
                        state=planned.target_state or "",
                    )
                    result = "retirado"
                    current_item = retired
                results.append(
                    {
                        "requirement_id": planned.requirement_id,
                        "remote_id": planned.remote_id,
                        "outcome": result,
                        "state": current_item.state,
                    }
                )
            except BacklogError as exc:
                results.append(
                    {
                        "requirement_id": planned.requirement_id,
                        "remote_id": planned.remote_id,
                        "outcome": "error",
                        "detail": str(exc),
                    }
                )
                results.extend(
                    {
                        "requirement_id": remaining.requirement_id,
                        "remote_id": remaining.remote_id,
                        "outcome": "no_publicado",
                    }
                    for remaining in plan.selected_items[position + 1 :]
                )
                return RetirementReport(
                    ok=False,
                    plan_hash=plan_hash,
                    error=f"Se detuvo en #{planned.remote_id}: {exc}",
                    results=results,
                )
        return RetirementReport(ok=True, plan_hash=plan_hash, results=results)

    def _is_removed(self, item) -> bool:
        return any(
            state["name"] == item.state and state["category"] == REMOVED_CATEGORY
            for state in self.backlog.list_work_item_states(item.type)
        )

    def record_approval(self, plan_hash: str, approved_by: str, report: RetirementReport) -> None:
        self.ledger.record_reconciliation(plan_hash, approved_by, report.model_dump_json())
