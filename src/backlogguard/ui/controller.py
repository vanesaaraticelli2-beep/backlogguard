"""Controlador de una corrida para la pantalla: corre el grafo en un hilo y expone su estado.

No depende de Streamlit (así se prueba sin pantalla). Una corrida a la vez por proceso: el hilo trabaja
mientras la pantalla consulta; cuando la corrida se pausa en un pedido de decisión, el hilo termina y
la pantalla puede mostrar el pedido. Decidir lanza otro hilo que retoma la corrida.
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import closing
from pathlib import Path

from backlogguard.catalog import RequirementStatus
from backlogguard.graph import RunDeps, load_state, pending_request, resume_pipeline, run_pipeline
from backlogguard.graph.live import format_event, format_trace
from backlogguard.graph.setup import build_run_deps, has_user_sources, open_graph, user_sources_dir
from backlogguard.llm import Settings

DEFAULT_OBJECTIVE = "Armá el backlog a partir de las reuniones y auditalo contra la preventa."
MAX_EVENTS = 3000
COVERAGE_GOAL = (
    "Cubrí todos los requisitos distintos de las reuniones, sin un número fijo de historias: una historia por requisito, "
    "con el detalle que pida la reunión."
)


class RunController:
    def __init__(self, root: Path, settings: Settings, data_dir: Path, replay: Path | None = None):
        self.root, self.settings, self.data_dir, self.replay = root, settings, data_dir, replay
        self._lock = threading.Lock()
        self._build()

    # ---- armado ----

    def _build(self) -> None:
        self.events: list[dict] = []
        self.read_only = False  # True mientras se mira una corrida guardada
        self.thread: threading.Thread | None = None
        self.thread_id: str | None = None
        self.error: str | None = None
        self.backlog_before: list[dict] = []
        own = user_sources_dir(self.data_dir)
        self.sources_dir: Path | None = own if has_user_sources(own) else None
        self.deps: RunDeps = build_run_deps(
            self.root, self.settings, data_dir=self.data_dir, replay=self.replay, sources_dir=self.sources_dir,
            on_event=self._on_event,
        )
        self.graph = open_graph(self.deps, self.data_dir)

    def _on_event(self, event: dict) -> None:
        with self._lock:
            self.events.append(event)
            del self.events[:-MAX_EVENTS]

    @property
    def using_own_sources(self) -> bool:
        """¿La corrida usa las fuentes que cargó la persona (y no las de ejemplo)?"""
        return self.sources_dir is not None

    def refresh_sources(self) -> None:
        """Vuelve a elegir la biblioteca después de cargar o borrar fuentes."""
        if self.running:
            raise RuntimeError("No se pueden cambiar las fuentes con una corrida en curso.")
        self._build()

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
        own = has_user_sources(user_sources_dir(self.data_dir))
        if own and self.mode != "real":
            raise RuntimeError(
                "Con fuentes propias hace falta LIVE_MODE=1: la corrida grabada no sabe responder a documentos nuevos."
            )
        if own and not self.catalog_summary()["active"]:
            raise RuntimeError(
                "No hay requisitos aprobados: la corrida parte del catálogo. Leé una reunión contra el catálogo (pestaña «Fuentes») "
                "y aprobá sus propuestas en «Revisión»."
            )
        if own:  # documentos reales: sin work items de ejemplo; el límite es el costo de la corrida, no un número de historias
            seed = False
            objective = f"{objective}\n{COVERAGE_GOAL}"
        if own:  # la memoria durable (catálogo, decisiones, publicaciones) sigue de una corrida a la siguiente
            self._build()
        else:
            self.reset_demo(seed=seed)
        self.thread_id = f"corrida-{uuid.uuid4().hex[:8]}"
        self.backlog_before = [w.model_dump() for w in self.deps.backlog.search()]
        self._spawn(run_pipeline, self.graph, objective, self.thread_id)
        return self.thread_id

    def catalog_summary(self) -> dict:
        """Cuántos requisitos aprobados hay, cuántos esperan redacción y publicación y cuántos ya están publicados."""
        catalog = self.deps.catalog
        if catalog is None:
            return {"active": 0, "to_publish": 0, "published": 0}
        active = catalog.requirements(RequirementStatus.ACTIVO)
        waiting = catalog.to_publish()
        return {"active": len(active), "to_publish": len(waiting), "published": len(active) - len(waiting)}

    def decide(self, decision: dict) -> None:
        if self.read_only:
            raise RuntimeError("Estás viendo una corrida guardada: es de solo lectura.")
        if self.running or self.thread_id is None:
            raise RuntimeError("No hay una corrida pausada esperando una decisión.")
        self._spawn(resume_pipeline, self.graph, self.thread_id, decision)

    def wait(self, timeout: float = 30.0) -> bool:
        """Espera a que termine el hilo en curso (útil en pruebas). Devuelve si ya terminó."""
        if self.thread is not None:
            self.thread.join(timeout)
        return not self.running

    DURABLE_FILES = ("publicaciones.sqlite", "memoria.sqlite", "backlog_simulado.json")

    def reset_demo(self, *, seed: bool = True) -> None:
        """Deja el backlog simulado, la memoria de decisiones y los registros como al comienzo (con las fuentes de ejemplo)."""
        if self.running:
            raise RuntimeError("No se puede reiniciar con una corrida en curso.")
        for name in self.DURABLE_FILES:
            (self.data_dir / name).unlink(missing_ok=True)
        self._build()
        if not self.using_own_sources:  # con documentos propios el catálogo solo se vacía con «Empezar proyecto nuevo»
            self.deps.catalog.clear()
        if seed:
            self.deps.backlog.seed_demo()

    def new_project(self) -> None:
        """Empieza un proyecto nuevo: vacía el catálogo, la memoria de decisiones, las publicaciones y el backlog simulado.

        Conserva las fuentes cargadas y la línea base de la preventa (cuesta dinero volver a extraerla)."""
        if self.running:
            raise RuntimeError("No se puede empezar un proyecto nuevo con una corrida en curso.")
        for name in self.DURABLE_FILES:
            (self.data_dir / name).unlink(missing_ok=True)
        self._build()
        self.deps.catalog.clear()
        self.thread_id, self.read_only = None, False

    # ---- consulta ----

    def pending(self) -> dict | None:
        """Pedido en el que está pausada la corrida (con `request` y `last_error`), o `None`."""
        if self.running or self.thread_id is None or self.read_only:
            return None
        return pending_request(self.graph, self.thread_id)

    def state(self) -> dict:
        if self.thread_id is None:
            return {}
        return load_state(self.graph, self.thread_id) or {}

    def list_runs(self) -> list[dict]:
        """Corridas guardadas en `data/corridas.sqlite` (de esta pantalla o de un script), la más reciente primero."""
        path = self.data_dir / "corridas.sqlite"
        if not path.exists():
            return []
        try:
            with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as conn:
                rows = conn.execute(
                    "SELECT thread_id FROM checkpoints GROUP BY thread_id ORDER BY MAX(checkpoint_id) DESC"
                ).fetchall()
        except sqlite3.OperationalError:  # el archivo existe pero todavía no se guardó ninguna corrida
            return []
        runs = []
        for (thread_id,) in rows:
            snapshot = self.graph.get_state({"configurable": {"thread_id": thread_id}})
            values = snapshot.values or {}
            runs.append(
                {
                    "thread_id": thread_id,
                    "status": values.get("status", "?"),
                    "tokens": values.get("tokens", 0),
                    "items": len((values.get("board") or {}).get("items", {})),
                    "tasks": len(values.get("tasks", [])),
                    "corrections": sum(1 for task in values.get("tasks", []) if task["kind"] == "corregir"),
                    "waiting": any(task.interrupts for task in snapshot.tasks),
                    "created_at": (snapshot.created_at or "")[:19].replace("T", " "),
                }
            )
        return runs

    def open_run(self, thread_id: str) -> None:
        """Muestra una corrida guardada, solo para leer: no se puede decidir ni reanudar desde acá."""
        if self.running:
            raise RuntimeError("No se puede abrir otra corrida mientras hay una en curso.")
        if not (self.graph.get_state({"configurable": {"thread_id": thread_id}}).values or {}):
            raise KeyError(f"No existe la corrida {thread_id}.")
        self.thread_id, self.read_only = thread_id, True
        self.events, self.backlog_before, self.error = [], [], None
        self.deps.backlog.reload()

    def resume_run(self, thread_id: str) -> None:
        """Retoma una corrida guardada que quedó esperando una decisión (por ejemplo, si se reinició la aplicación)."""
        if self.running:
            raise RuntimeError("No se puede retomar otra corrida mientras hay una en curso.")
        if not any(run["thread_id"] == thread_id and run["waiting"] for run in self.list_runs()):
            raise KeyError(f"La corrida {thread_id} no existe o no está esperando una decisión.")
        self.thread_id, self.read_only = thread_id, False
        self.events, self.backlog_before, self.error = [], [], None
        self.deps.backlog.reload()

    def activity(self, limit: int = 400) -> list[str]:
        if self.read_only:
            return format_trace(self.state().get("trace", []))
        with self._lock:
            events = list(self.events[-limit:])
        return [line for event in events if (line := format_event(event))]

    def close(self) -> None:
        self.graph.checkpointer.conn.close()

