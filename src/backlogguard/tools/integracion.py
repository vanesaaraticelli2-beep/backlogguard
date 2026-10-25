"""Tools de Integración: buscar en el backlog, armar el plan, revalidarlo y ejecutarlo.

Armar y revalidar no escriben. `ejecutar_plan_aprobado` es la única escritura externa: el catálogo
le agrega la guarda del plan aprobado y la política exige además el permiso de escritura externa.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field

from backlogguard.integrations import PublishService
from backlogguard.tools.catalog import ExecutePlanArgs
from backlogguard.tools.models import ToolResult


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchBacklogArgs(_Args):
    text: str | None = Field(default=None, min_length=2, max_length=200, description="Fragmento del título")
    tag: str | None = Field(default=None, min_length=2, max_length=120)


class ArmPlanArgs(_Args):
    pass


class RevalidateArgs(_Args):
    plan_hash: str = Field(min_length=8, max_length=64)


def _fail(content: str, error_type: str) -> ToolResult:
    return ToolResult(ok=False, content=content, metadata={"error_type": error_type})


class IntegrationToolkit:
    def __init__(self, service: PublishService):
        self.service = service
        self.last_plan_hash: str | None = None

    def buscar_en_backlog(self, args: dict) -> ToolResult:
        if not args.get("text") and not args.get("tag"):
            return _fail("Indicá un texto o una etiqueta para buscar.", "empty_query")
        found = self.service.backlog.search(text=args.get("text"), tag=args.get("tag"))
        rows = [{"id": w.id, "tipo": w.type, "titulo": w.title, "etiquetas": w.tags, "version": w.rev} for w in found]
        return ToolResult(ok=True, content=json.dumps(rows, ensure_ascii=False), metadata={"results": len(rows)})

    def armar_plan_dry_run(self, args: dict) -> ToolResult:
        plan = self.service.arm()
        self.last_plan_hash = plan.plan_hash
        summary = {
            "plan_hash": plan.plan_hash,
            "acciones": plan.counts(),
            "items": [
                {"item_id": i.item_id, "accion": i.action, "tipo": i.work_item_type, "titulo": i.title, "motivo": i.reason}
                for i in plan.items
            ],
        }
        return ToolResult(
            ok=True,
            content=json.dumps(summary, ensure_ascii=False),
            metadata={"plan_hash": plan.plan_hash, "has_changes": plan.has_changes},
        )

    def revalidar_plan(self, args: dict) -> ToolResult:
        plan = self.service.stored_plan(args["plan_hash"])
        if plan is None:
            return _fail("No existe un plan armado con ese hash.", "unknown_plan")
        diffs = self.service.drift(plan)
        return ToolResult(
            ok=True,
            content=json.dumps({"vigente": not diffs, "diferencias": diffs}, ensure_ascii=False),
            metadata={"vigente": not diffs},
        )

    def ejecutar_plan_aprobado(self, args: dict) -> ToolResult:
        report = self.service.execute(args["plan_hash"])
        content = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
        if report.ok:
            return ToolResult(ok=True, content=content, metadata={"written": report.written})
        kind = "plan_drift" if report.error and "cambiaron" in report.error else "execution_failed"
        return ToolResult(ok=False, content=content, metadata={"error_type": kind, "written": report.written})

    def implementations(self) -> dict:
        return {
            "buscar_en_backlog": (self.buscar_en_backlog, SearchBacklogArgs, True),
            "armar_plan_dry_run": (self.armar_plan_dry_run, ArmPlanArgs, True),
            "revalidar_plan": (self.revalidar_plan, RevalidateArgs, True),
            "ejecutar_plan_aprobado": (self.ejecutar_plan_aprobado, ExecutePlanArgs, False),
        }
