"""Controlador de una corrida para la pantalla: corre el grafo en un hilo y expone su estado.

No depende de Streamlit (así se prueba sin pantalla). Una corrida a la vez por proceso: el hilo trabaja
mientras la pantalla consulta; cuando la corrida se pausa en un pedido de decisión, el hilo termina y
la pantalla puede mostrar el pedido. Decidir lanza otro hilo que retoma la corrida.
"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from backlogguard.graph import RunDeps, load_state, pending_request, resume_pipeline, run_pipeline
from backlogguard.graph.live import format_event
from backlogguard.graph.setup import build_run_deps, open_graph
from backlogguard.llm import Settings

DEFAULT_OBJECTIVE = "Armá el backlog del portal de autoservicio de ACME a partir de las reuniones y auditalo contra la preventa."
MAX_EVENTS = 3000


class RunController:
    def __init__(self, root: Path, settings: Settings, data_dir: Path, replay: Path | None = None):
        self.root, self.settings, self.data_dir, self.replay = root, settings, data_dir, replay
        self._lock = threading.Lock()
        self._build()

    # ---- armado ----

    def _build(self) -> None:
        self.events: list[dict] = []
        self.thread: threading.Thread | None = None
        self.thread_id: str | None = None
        self.error: str | None = None
        self.backlog_before: list[dict] = []
        self.deps: RunDeps = build_run_deps(
            self.root, self.settings, data_dir=self.data_dir, replay=self.replay, on_event=self._on_event
        )
        self.graph = open_graph(self.deps, self.data_dir)

    def _on_event(self, event: dict) -> None:
        with self._lock:
            self.events.append(event)
            del self.events[:-MAX_EVENTS]

    @property
    def mode(self) -> str:
        return "demo" if self.replay else ("real" if self.settings.live_mode else "simulado")

    # ---- ejecución en segundo plano ----

    @property
    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def _spawn(self, work, *args) -> None:
        def target() -> None:
            try:
                work(*args)
            except Exception as exc:  # se muestra en la pantalla; no debe matar el proceso
                self.error = f"{type(exc).__name__}: {exc}"

        self.error = None
        self.thread = threading.Thread(target=target, daemon=True)
        self.thread.start()

    def start(self, objective: str = DEFAULT_OBJECTIVE, *, seed: bool = True) -> str:
        if self.running:
            raise RuntimeError("Ya hay una corrida en curso.")
        self.reset_demo(seed=seed)
        self.thread_id = f"corrida-{uuid.uuid4().hex[:8]}"
        self.backlog_before = [w.model_dump() for w in self.deps.backlog.search()]
        self._spawn(run_pipeline, self.graph, objective, self.thread_id)
        return self.thread_id

    def decide(self, decision: dict) -> None:
        if self.running or self.thread_id is None:
            raise RuntimeError("No hay una corrida pausada esperando una decisión.")
        self._spawn(resume_pipeline, self.graph, self.thread_id, decision)

    def wait(self, timeout: float = 30.0) -> bool:
        """Espera a que termine el hilo en curso (útil en pruebas). Devuelve si ya terminó."""
        if self.thread is not None:
            self.thread.join(timeout)
        return not self.running

    def reset_demo(self, *, seed: bool = True) -> None:
        """Deja el backlog simulado, la memoria de decisiones y los registros como al comienzo."""
        if self.running:
            raise RuntimeError("No se puede reiniciar con una corrida en curso.")
        for name in ("publicaciones.sqlite", "memoria.sqlite", "backlog_simulado.json"):
            (self.data_dir / name).unlink(missing_ok=True)
        self._build()
        if seed:
            self.deps.backlog.seed_demo()

    # ---- consulta ----

    def pending(self) -> dict | None:
        """Pedido en el que está pausada la corrida (con `request` y `last_error`), o `None`."""
        if self.running or self.thread_id is None:
            return None
        return pending_request(self.graph, self.thread_id)

    def state(self) -> dict:
        if self.thread_id is None:
            return {}
        return load_state(self.graph, self.thread_id) or {}

    def activity(self, limit: int = 400) -> list[str]:
        with self._lock:
            events = list(self.events[-limit:])
        return [line for event in events if (line := format_event(event))]

    def close(self) -> None:
        self.graph.checkpointer.conn.close()

