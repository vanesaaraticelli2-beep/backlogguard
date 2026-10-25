"""Nodos del grafo. Cada uno recibe el estado, hace una cosa y devuelve solo lo que cambia.

Las reglas (orden, topes, escalaciones) viven acá y en las rutas del `builder`, no en los prompts.
Un error de un agente se registra en `errors` y la corrida sigue con el resto.
"""
from __future__ import annotations

import time
from collections import Counter
from typing import Callable

from backlogguard.agents.auditor import apply_report, run_auditor
from backlogguard.agents.auditor.entrega import PAUSE_CONDITION, corrections_by_item, deliver_corrections
from backlogguard.agents.critico import review_item
from backlogguard.agents.negociacion import negotiate_item
from backlogguard.agents.requerimientos import revise_item, run_requerimientos
from backlogguard.agents.supervisor import plan_run, summarize_run
from backlogguard.board import AgentRole, Board, ItemState
from backlogguard.graph.budgets import over_budget
from backlogguard.graph.deps import RunDeps
from backlogguard.graph.state import RunState
from backlogguard.llm.errors import LLMError
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
    def plan(state: RunState) -> dict:
        result = plan_run(
            state["objective"],
            provider=deps.providers.supervisor,
            library=deps.library,
            policy=deps.policy,
            run_id=state.get("run_id", "run-local"),
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
            outcome = review_item(ref, provider=deps.providers.critico, retriever=deps.retriever, board=board)
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
        board = _board(state)
        toolkit = SupervisorToolkit(deps.library, deps.policy, [Escalation(**e) for e in state.get("escalations", [])])
        registry = build_catalog_registry(toolkit.implementations())
        context = ExecutionContext(user_id="factory", role=AgentRole.SUPERVISOR, run_id=state.get("run_id", "run-local"))
        gate = ToolPolicy()

        def register(reason: str, ref: str, detail: str) -> None:
            registry.run(
                ToolCall(tool_name="escalar_a_persona", arguments={"reason": reason, "ref": ref, "detail": detail[:400]}),
                context=context,
                policy=gate,
            )

        for item_id, info in state.get("reviewed", {}).items():
            if info["outcome"] == "sin_consenso":
                register("desacuerdo_sin_consenso", item_id, "; ".join(info.get("objections", [])))
        for finding in board.findings:
            reason = PAUSE_CONDITION.get(finding.kind)
            if reason and finding.addressee is AgentRole.SUPERVISOR:
                register(reason, finding.id, finding.description)

        stop = state.get("stop_reason") or over_budget(state, deps.budget)
        if stop:
            status = "presupuesto_agotado"
        elif toolkit.escalations:
            status = "esperando_decision"
        elif state.get("errors"):
            status = "completada_con_errores"
        else:
            status = "completada"
        return {
            "escalations": [e.model_dump() for e in toolkit.escalations],
            "status": status,
            "stop_reason": stop,
            "trace": [{"node": "escalate", "escalations": len(toolkit.escalations), "status": status}],
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
            "corte": state.get("stop_reason"),
        }
        exhausted = state.get("tokens", 0) >= deps.budget.max_tokens
        if exhausted:
            text, spent = f"Corrida {facts['status']} (presupuesto de tokens agotado): {facts['items']} ítems.", 0
        else:
            text, spent = summarize_run(facts, provider=deps.providers.supervisor)
        return {"summary": text, "tokens": state.get("tokens", 0) + spent, "trace": [{"node": "summarize"}]}

    return {"plan": plan, "produce": produce, "review": review, "audit": audit, "escalate": escalate, "summarize": summarize}
