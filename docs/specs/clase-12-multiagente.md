# Correspondencia con la clase 12 · Sistemas multiagente

Qué enseña `Curso ITBA/clase12_sistemas_multiagente.ipynb` y dónde está (o por qué no) en BacklogGuard. Describe el código que existe hoy.

**Idea de la clase:** la pregunta no es «¿cuántos agentes puedo crear?», sino si separar responsabilidades mejora contexto, permisos, calidad, trazabilidad o paralelismo lo suficiente como para justificar la complejidad.

## Los siete patrones

| Patrón de la clase | Estado | Dónde está |
|---|---|---|
| 01 · Router | **No, por diseño** | El recorrido es fijo y el Supervisor no puede alterarlo ([SU-04, SU-05](supervisor.md)): que Crítico y Auditor participen siempre es una regla de AGENTS.md, no una decisión del modelo. |
| 02 · Pipeline secuencial | **Sí** | `plan → producir → revisar → auditar → escalar → decidir → integrar` en [graph/builder.py](../../src/backlogguard/graph/builder.py). |
| 03 · Fan-out / Fan-in | **Sí** | Revisión del Crítico por olas: `triage` → `Send` a `review_one` → `merge_reviews`, con el reducer `collect_results` ([graph/state.py](../../src/backlogguard/graph/state.py)). Requisitos SU-14 a SU-18. |
| 04 · Supervisor–Workers | **Parcial** | El Supervisor planifica y delega con `delegar_tarea` (valida agente, tarea y fuentes), pero la ejecución la ordena el grafo, no un plan de tareas con dependencias. |
| 05 · Agents as Tools | **Parcial** | Cada agente tiene su registry y sus tools ([tools/registry.py](../../src/backlogguard/tools/registry.py)); los nodos los invocan como funciones, no son tools de otro agente. |
| 06 · Handoff | **Parcial** | Cada traspaso queda como tarea `T-nnn` (origen, destino, ítem, costo) en [graph/tasks.py](../../src/backlogguard/graph/tasks.py); no hay un paquete de contexto mínimo para el destino. |
| 07 · Generator–Critic | **Sí** | Productor ↔ Crítico con tope de 2 rondas en [agents/negociacion.py](../../src/backlogguard/agents/negociacion.py). |

## Mecanismos técnicos

| Mecanismo de la clase | Estado | Dónde |
|---|---|---|
| `Send` (routing dinámico a ramas) | **Sí** | `dispatch_wave` en [graph/builder.py](../../src/backlogguard/graph/builder.py) |
| Reducer (`Annotated[list, operator.add]`) | **Sí** | `trace`, `tasks`, `errors`, `decisions` y `review_results` en [graph/state.py](../../src/backlogguard/graph/state.py) |
| Fan-in en un nodo consolidador (el reducer no consolida) | **Sí** | `merge_reviews` en [graph/nodes.py](../../src/backlogguard/graph/nodes.py) |
| Aislamiento de contexto | **Sí** | Cada rama trabaja sobre su copia del tablero; cada agente ve solo sus tools y su presupuesto de contexto ([agents/context.py](../../src/backlogguard/agents/context.py)). |
| Falla parcial visible | **Sí** | SU-12 y SU-16: un error no tumba la corrida ni a las demás ramas. |
| Supervisor elige con salida estructurada y el código valida | **Sí** | SU-02 y SU-04. |
| Contrato de tarea y de resultado (`WorkerTask`, `WorkerOutput` con `success/partial/failed`) | **No todavía** | Hay un registro de tareas con estado (`hecha`, `incompleta`, `fallida`) pero no el contrato tipado de la clase. |
| `validate_plan` sobre un grafo de dependencias | **No** | La delegación valida agente, tarea y fuentes; no hay dependencias entre tareas. |
| Comparación contra un agente único | **No todavía** | Día 13. |
| Evaluación de la delegación (¿cada rol hizo su tarea?) | **No todavía** | Día 13. |
| `requires_human` no equivale a una aprobación | **Sí** | Toda publicación exige un plan aprobado por una persona y con el mismo hash ([hitl.md](hitl.md)). |

## Decisiones propias (fuera de la clase)
- Revisión **por olas** de hasta N ítems en vez de lanzar todas las ramas juntas: el presupuesto se controla entre olas.
- `max_parallel_reviews` configurable; con 1 el recorrido es el de siempre. La demo grabada y las pruebas guionadas fuerzan 1, porque consumen las respuestas en orden por agente.
- Medición de gasto por rama (`Meter` propio) y numeración de tareas en el fan-in, en el orden de la ola.
- Triage determinístico de duplicados antes de la ola.

## Pendiente
Contrato tipado de tarea y de resultado, evaluación de la delegación y comparación con un agente único (Día 13), y la clase 13 (MCP), cuyo archivo todavía no está en la carpeta del curso.
