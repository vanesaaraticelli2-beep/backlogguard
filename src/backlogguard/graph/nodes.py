"""Nodos del grafo. Cada uno recibe el estado, hace una cosa y devuelve solo lo que cambia.

Las reglas (orden, topes, escalaciones) viven acá y en las rutas del `builder`, no en los prompts.
Un error de un agente se registra en `errors` y la corrida sigue con el resto.
"""
from __future__ import annotations

import time
from collections import Counter
from typing import Callable

from backlogguard.agents.auditor import apply_report, run_auditor
from backlogguard.agents.auditor.entrega import corrections_by_item, deliver_corrections
from backlogguard.agents.critico import review_item
from backlogguard.agents.integracion import execute_approved_plan, run_integracion
from backlogguard.agents.negociacion import negotiate_item
from backlogguard.agents.requerimientos import revise_item, run_requerimientos
from backlogguard.agents.supervisor import plan_run, summarize_run
from backlogguard.board import AgentRole, Board, ItemState
from backlogguard.graph.budgets import over_budget
from backlogguard.graph.deps import RunDeps
from backlogguard.graph.state import RunState
from backlogguard.hitl import (
    DecisionRecord,
    DecisionRequest,
    HumanDecision,
    apply_item_decision,
    apply_scope_decision,
    group_findings,
    request_for_group,
    request_for_item,
    request_for_plan,
    validate_decision,
)
from backlogguard.integrations import BacklogError, PublishService
from backlogguard.llm.errors import LLMError
from langgraph.types import interrupt
from pydantic import ValidationError
from backlogguard.tools import ExecutionContext, ToolCall, ToolPolicy, build_catalog_registry
from backlogguard.tools.supervisor import Escalation, SupervisorToolkit

Node = Callable[[RunState], dict]


def _board(state: RunState) -> Board:
    return Board.model_validate(state["board"])


def _dump(board: Board) -> dict:
    return board.model_dump(mode="json")


def _error(node: str, exc: Exception, ref: str | None = None) -> dict:
    return {"node": node, "ref": ref, "error": f"{type(exc).__name__}: {exc}"}


def make_nodes(deps: RunDeps) -> dict[str, Node]:
    def sink(agent: str):
        """Callback que anota qué agente emite cada evento (para seguirlos en vivo)."""
        if deps.on_event is None:
            return None
        return lambda event: deps.on_event({**event, "agent": agent})

    def plan(state: RunState) -> dict:
        result = plan_run(
            state["objective"],
            provider=deps.providers.supervisor,
            library=deps.library,
            policy=deps.policy,
            run_id=state.get("run_id", "run-local"),
            on_event=sink("supervisor"),
        )
        plan_data = {
            "sources": result.sources,
            "instruction": result.instruction,
            "delegations": [d.model_dump() for d in result.delegations],
            "used_default": result.used_default,
        }
        return {
            "plan": plan_data,
            "started_at": time.time(),
            "tokens": state.get("tokens", 0) + result.tokens,
            "trace": [{"node": "plan", "used_default": result.used_default, "sources": result.sources, "error": result.error}],
        }

    def produce(state: RunState) -> dict:
        if reason := over_budget(state, deps.budget):
            return {"stop_reason": reason, "pending": [], "trace": [{"node": "produce", "stop": reason}]}
        board = _board(state)
        plan_data = state["plan"]
        goal = (
            f"{plan_data['instruction']}\n"
            f"Redactá solo a partir de estas fuentes: {', '.join(plan_data['sources'])}. "
            "No redactes a partir de la preventa."
        )
        outcome = run_requerimientos(
            goal,
            provider=deps.providers.requerimientos,
            library=deps.library,
            retriever=deps.retriever,
            board=board,
            run_id=state.get("run_id", "run-local"),
            on_event=sink("requerimientos"),
        )
        pending = [item.id for item in board.items.values() if item.state is ItemState.BORRADOR]
        return {
            "board": _dump(board),
            "pending": pending,
            "tokens": state.get("tokens", 0) + outcome["tokens"],
            "trace": [{"node": "produce", "stop_reason": outcome["stop_reason"], "items": len(pending)}],
        }

    def review(state: RunState) -> dict:
        pending = list(state.get("pending", []))
        if not pending:
            return {}
        if reason := over_budget(state, deps.budget):
            return {"stop_reason": reason, "pending": [], "trace": [{"node": "review", "stop": reason}]}
        item_id, rest = pending[0], pending[1:]
        board = _board(state)
        spent = [0]

        def critic_review(ref: str):
            outcome = review_item(
                ref, provider=deps.providers.critico, retriever=deps.retriever, board=board, on_event=sink("critico")
            )
            spent[0] += outcome.tokens
            return outcome.verdict

        def producer_revise(ref: str, objections: list[str]) -> None:
            outcome = revise_item(
                ref,
                objections,
                provider=deps.providers.requerimientos,
                library=deps.library,
                retriever=deps.retriever,
                board=board,
                on_event=sink("requerimientos"),
            )
            spent[0] += outcome["tokens"]

        errors: list[dict] = []
        try:
            result = negotiate_item(item_id, board=board, retriever=deps.retriever, review=critic_review, revise=producer_revise)
            info = {"outcome": result.outcome, "rounds": result.rounds, "objections": result.objections[-3:]}
        except LLMError as exc:
            info = {"outcome": "error", "rounds": 0, "objections": []}
            errors.append(_error("review", exc, item_id))
        return {
            "board": _dump(board),
            "pending": rest,
            "reviewed": {**state.get("reviewed", {}), item_id: info},
            "tokens": state.get("tokens", 0) + spent[0],
            "errors": errors,
            "trace": [{"node": "review", "item": item_id, **{k: info[k] for k in ("outcome", "rounds")}}],
        }

    def audit(state: RunState) -> dict:
        if reason := over_budget(state, deps.budget):
            return {"stop_reason": reason, "audit_passes": 1, "pending": [], "trace": [{"node": "audit", "stop": reason}]}
        board = _board(state)
        tokens, errors, reopened, applied_ids = state.get("tokens", 0), [], [], []
        try:
            run = run_auditor(
                provider=deps.providers.auditor,
                retriever=deps.retriever,
                board=board,
                memory=deps.memory,
                run_id=state.get("run_id", "run-local"),
                on_event=sink("auditor"),
            )
            tokens += run.tokens
            result = apply_report(run.report, board, deps.retriever)
            deliver_corrections(board, result.applied)
            applied_ids = [finding.id for finding in result.applied]
            for item_id, corrections in corrections_by_item(result.applied).items():
                try:
                    outcome = revise_item(
                        item_id,
                        corrections,
                        provider=deps.providers.requerimientos,
                        library=deps.library,
                        retriever=deps.retriever,
                        board=board,
                        on_event=sink("requerimientos"),
                    )
                    tokens += outcome["tokens"]
                    reopened.append(item_id)
                except LLMError as exc:
                    errors.append(_error("audit", exc, item_id))
            discarded = len(result.discarded)
        except LLMError as exc:
            errors.append(_error("audit", exc))
            discarded = 0
        return {
            "board": _dump(board),
            "audit": {"findings": applied_ids, "discarded": discarded, "reopened": reopened},
            "audit_passes": 1,
            "pending": reopened,
            "tokens": tokens,
            "errors": errors,
            "trace": [{"node": "audit", "findings": len(applied_ids), "reopened": reopened}],
        }

    def escalate(state: RunState) -> dict:
        """Convierte los desacuerdos y los hallazgos en pedidos de decisión, agrupando los del mismo asunto."""
        board = _board(state)
        toolkit = SupervisorToolkit(deps.library, deps.policy, [Escalation(**e) for e in state.get("escalations", [])])
        registry = build_catalog_registry(toolkit.implementations())
        context = ExecutionContext(user_id="factory", role=AgentRole.SUPERVISOR, run_id=state.get("run_id", "run-local"))
        gate = ToolPolicy()

        def register(reason: str, ref: str, detail: str, related: list[str] | None = None) -> None:
            registry.run(
                ToolCall(
                    tool_name="escalar_a_persona",
                    arguments={"reason": reason, "ref": ref, "detail": detail[:800], "related": related or []},
                ),
                context=context,
                policy=gate,
            )

        requests: list[dict] = []
        for item_id, info in state.get("reviewed", {}).items():
            item = board.items.get(item_id)
            if info["outcome"] == "sin_consenso" and item is not None and item.state is ItemState.OBJETADO:
                register("desacuerdo_sin_consenso", item_id, "; ".join(info.get("objections", [])))
                requests.append(request_for_item(item, deps.policy).model_dump(mode="json"))
        decided = {entry["key"] for entry in deps.memory.current_decisions()}
        skipped = []
        for group in group_findings(board.findings):
            if group.topic_key in decided:  # una decisión vigente ya resuelve este asunto
                skipped.append(group.group_id)
                continue
            register(group.reason, group.group_id, group.summary, [f.id for f in group.findings])
            requests.append(request_for_group(group, deps.policy).model_dump(mode="json"))

        stop = state.get("stop_reason") or over_budget(state, deps.budget)
        if stop:
            status = "presupuesto_agotado"
        elif requests:
            status = "esperando_decision"
        elif state.get("errors"):
            status = "completada_con_errores"
        else:
            status = "completada"
        return {
            "escalations": [e.model_dump() for e in toolkit.escalations],
            "requests": requests,
            "status": status,
            "stop_reason": stop,
            "trace": [{"node": "escalate", "requests": len(requests), "ya_decididos": skipped, "status": status}],
        }

    def _ask(state: RunState, request: DecisionRequest) -> dict:
        """Pausa la corrida hasta que una persona decida. Nada se ejecuta antes de la pausa."""
        return interrupt({"request": request.model_dump(mode="json"), "last_error": state.get("decision_error")})

    def _judge(request: DecisionRequest, raw: dict) -> tuple[HumanDecision | None, DecisionRecord, str | None]:
        """Valida la respuesta de la persona y arma su registro de auditoría."""
        try:
            decision = HumanDecision.model_validate(raw)
        except ValidationError as exc:
            error = f"La decisión no tiene el formato esperado: {exc.errors()[0]['msg']}"
            record = DecisionRecord(
                request_id=request.request_id, version=request.version, args_hash="", decision="?", actor="?",
                actor_role="?", accepted=False, error=error,
            )
            return None, record, error
        error = validate_decision(request, decision, deps.people)
        record = DecisionRecord(
            request_id=request.request_id, version=decision.request_version, args_hash=decision.args_hash,
            decision=decision.decision, actor=decision.actor, actor_role=decision.actor_role,
            comment=decision.comment, accepted=error is None, error=error,
        )
        return decision, record, error

    def decide(state: RunState) -> dict:
        """Una pausa por pedido de decisión (alcance, contradicción o desacuerdo sobre un ítem)."""
        requests = list(state.get("requests", []))
        if not requests:
            return {"status": "en_curso"}
        request = DecisionRequest.model_validate(requests[0])
        raw = _ask(state, request)  # <- la corrida se detiene acá; lo de abajo corre al reanudar
        decision, record, error = _judge(request, raw)
        if error:
            return {"decisions": [record.model_dump()], "decision_error": error, "trace": [{"node": "decide", "rechazada": error}]}
        if decision.decision == "edit":  # una edición crea una versión nueva que hay que aprobar otra vez
            revised = request.next_version(decision.edited)
            return {
                "requests": [revised.model_dump(mode="json"), *requests[1:]],
                "decisions": [record.model_dump()],
                "decision_error": None,
                "trace": [{"node": "decide", "request": request.request_id, "edit": f"v{revised.version}"}],
            }
        update: dict = {}
        if request.kind == "alcance":
            effect = apply_scope_decision(request, decision, deps.memory)
        else:
            board = _board(state)
            effect = apply_item_decision(request, decision, board)
            update["board"] = _dump(board)
            update["reviewed"] = {
                **state.get("reviewed", {}),
                request.ref: {**state["reviewed"][request.ref], "outcome": f"{effect.outcome}_por_persona"},
            }
        remaining = requests[1:]
        return {
            **update,
            "requests": remaining,
            "decisions": [record.model_dump()],
            "decision_error": None,
            "status": "esperando_decision" if remaining else "en_curso",
            "trace": [{"node": "decide", "request": request.request_id, "decision": decision.decision, "efecto": effect.outcome}],
        }

    def _plan_summary(plan, summary: str) -> dict:
        return {
            "hash": plan.plan_hash,
            "project": plan.project,
            "counts": plan.counts(),
            "has_changes": plan.has_changes,
            "items": [
                {"item_id": i.item_id, "action": i.action, "type": i.work_item_type, "title": i.title, "reason": i.reason}
                for i in plan.items
            ],
            "summary": summary,
        }

    def integrate(state: RunState) -> dict:
        """Arma el plan de publicación en dry-run, con los ítems que quedaron sustentados tras las decisiones."""
        if reason := state.get("stop_reason") or over_budget(state, deps.budget, check_time=False):
            return {"trace": [{"node": "integrate", "stop": reason}]}
        excluded = frozenset(state.get("plan_exclusions", []))
        service = PublishService(_board(state), deps.backlog, deps.ledger, deps.project, excluded)
        try:
            run = run_integracion(
                provider=deps.providers.integracion,
                service=service,
                run_id=state.get("run_id", "run-local"),
                on_event=sink("integracion"),
            )
        except BacklogError as exc:
            return {"errors": [_error("integrate", exc)], "trace": [{"node": "integrate", "error": str(exc)}]}
        plan = run.plan
        summary = _plan_summary(plan, run.summary)
        update: dict = {
            "publish_plan": summary,
            "tokens": state.get("tokens", 0) + run.tokens,
            "trace": [{"node": "integrate", "plan_hash": plan.plan_hash, "counts": plan.counts()}],
        }
        if plan.has_changes:
            update["status"] = "plan_pendiente_de_aprobacion"
            update["plan_request"] = request_for_plan(summary, deps.policy).model_dump(mode="json")
        else:
            update["status"] = "completada_con_errores" if state.get("errors") else "completada"
            update["plan_request"] = None
        return update

    def approve_plan(state: RunState) -> dict:
        """Pausa hasta que se apruebe, edite (excluyendo ítems) o rechace el plan exacto que se mostró."""
        request = DecisionRequest.model_validate(state["plan_request"])
        raw = _ask(state, request)
        decision, record, error = _judge(request, raw)
        if error:
            return {"decisions": [record.model_dump()], "decision_error": error, "trace": [{"node": "approve_plan", "rechazada": error}]}
        board = _board(state)
        if decision.decision == "reject":
            return {
                "plan_request": None, "status": "plan_rechazado", "decisions": [record.model_dump()], "decision_error": None,
                "publication": {"ok": False, "error": "El plan fue rechazado: no se publicó nada.", "results": []},
                "trace": [{"node": "approve_plan", "decision": "reject"}],
            }
        if decision.decision == "edit":
            excluded = frozenset(decision.edited["exclude"])
            plan = PublishService(board, deps.backlog, deps.ledger, deps.project, excluded).arm()
            summary = _plan_summary(plan, state.get("publish_plan", {}).get("summary", ""))
            revised = request_for_plan(summary, deps.policy).model_copy(update={"version": request.version + 1})
            revised = revised.model_copy(update={"payload": {**revised.payload, "exclude": sorted(excluded)}}).sealed()
            return {
                "publish_plan": summary, "plan_exclusions": sorted(excluded), "plan_request": revised.model_dump(mode="json"),
                "decisions": [record.model_dump()], "decision_error": None,
                "trace": [{"node": "approve_plan", "edit": f"v{revised.version}", "plan_hash": plan.plan_hash}],
            }
        service = PublishService(board, deps.backlog, deps.ledger, deps.project, frozenset(state.get("plan_exclusions", [])))
        approved_plan = service.stored_plan(request.ref)
        for planned in approved_plan.items if approved_plan else []:
            item = board.items.get(planned.item_id)
            if planned.action != "omitir" and item is not None and item.state is ItemState.SUSTENTADO:
                item.transition_to(ItemState.APROBADO, actor=decision.actor)
        report = execute_approved_plan(request.ref, service=service, approved_by=decision.actor, run_id=state.get("run_id", "run-local"))
        return {
            "board": _dump(board),
            "plan_request": None,
            "status": "publicada" if report.ok else "publicacion_detenida",
            "publication": report.model_dump(mode="json"),
            "decisions": [record.model_dump()],
            "decision_error": None,
            "trace": [{"node": "approve_plan", "decision": "approve", "publicado": report.written, "ok": report.ok}],
        }

    def summarize(state: RunState) -> dict:
        board = _board(state)
        facts = {
            "status": state["status"],
            "items": len(board.items),
            "estados": dict(Counter(item.state.value for item in board.items.values())),
            "revision": {item_id: info["outcome"] for item_id, info in state.get("reviewed", {}).items()},
            "hallazgos": len(board.findings),
            "escalations": [
                {"razon": e["reason"], "decide": e["decides"], "ref": e["ref"]} for e in state.get("escalations", [])
            ],
            "errors": [{"nodo": e["node"], "ref": e["ref"]} for e in state.get("errors", [])],
            "decisiones": [
                {"pedido": d["request_id"], "accion": d["decision"], "por": d["actor"]}
                for d in state.get("decisions", [])
                if d["accepted"]
            ],
            "publicacion": (
                {
                    "ok": state["publication"]["ok"],
                    "publicados": sum(
                        1 for r in state["publication"]["results"] if r["outcome"] in ("publicado", "actualizado", "vinculado")
                    ),
                }
                if state.get("publication")
                else None
            ),
            "corte": state.get("stop_reason"),
            "plan_de_publicacion": state.get("publish_plan", {}).get("counts"),
        }
        exhausted = state.get("tokens", 0) >= deps.budget.max_tokens
        if exhausted:
            text, spent = f"Corrida {facts['status']} (presupuesto de tokens agotado): {facts['items']} ítems.", 0
        else:
            text, spent = summarize_run(facts, provider=deps.providers.supervisor)
        return {"summary": text, "tokens": state.get("tokens", 0) + spent, "trace": [{"node": "summarize"}]}

    nodes = {
        "plan": plan, "produce": produce, "review": review, "audit": audit, "escalate": escalate,
        "decide": decide, "integrate": integrate, "approve_plan": approve_plan, "summarize": summarize,
    }

    def announce(name: str, node: Node) -> Node:
        def wrapped(state: RunState) -> dict:
            if deps.on_event:
                deps.on_event({"agent": "grafo", "event": "node_start", "node": name})
            update = node(state)
            if deps.on_event:
                deps.on_event({"agent": "grafo", "event": "node_end", "node": name, "status": update.get("status")})
            return update

        return wrapped

    return {name: announce(name, node) for name, node in nodes.items()}
