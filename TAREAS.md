# TAREAS · BacklogGuard

Checklist de avance por día. Se trabaja de a un día y no se avanza sin confirmación.
Entrega: **domingo 2026-12-06 23:59**. Los días 6 en adelante son un esquema **sin confirmar**.

Leyenda: `[x]` hecho · `[~]` en curso · `[ ]` pendiente

## Día 1 · Contrato del tablero — [x]
- [x] Modelos Pydantic: `BacklogItem`, `Citation`, `Objection`, `Finding`, `AgentMessage`, `Board`
- [x] Estados y transiciones válidas (borrador → objetado/sustentado → aprobado/excluido)
- [x] Reglas en código: cita obligatoria para sustentar, `approved_by` para aprobar, `MAX_ROUNDS = 2`
- [x] Checkpoint JSON versionado del tablero (`StaleCheckpointError`)
- [x] Repo público en GitHub, README (13 secciones) y `.gitignore`

## Día 2 · ToolRegistry y policy gate — [x]
- [x] `Tool`, `ToolPolicy`, `ToolRegistry`, `ExecutionContext` (clase 9)
- [x] Control en orden: Registry → Availability → Validation → Authorization → Execution
- [x] Catálogo de las 16 tools, cada una visible solo para su rol
- [x] Guarda `ejecutar_plan_aprobado`: exige plan aprobado y hash coincidente
- [x] `config/policy.yaml` validado contra el código, y `AGENTS.md`

## Día 3 · Memoria del proyecto — [x]
- [x] `MemoryStore` SQLite con Write Gate, supersede y TTL (clase 10)
- [x] `ProjectMemory`: decisiones vigentes/historial y preguntas pendientes
- [x] Las escrituras exigen `approved_by`

## Día 4 · Capa de LLM y ciclo de agente — [x]
- [x] `Settings`, jerarquía `LLMError`, `FakeProvider`, `GeminiProvider`, `AnthropicProvider`
- [x] Resiliencia: reintentos con backoff, sin reintentos apilados del SDK
- [x] `config/models.yaml` y regla de independencia del Crítico
- [x] `run_basic_agent` con presupuesto de pasos, tiempo, tool calls y tokens
- [x] `LLMDecider`: decisión en JSON validado y observaciones como dato no confiable
- [x] Humo en vivo de los 5 agentes (`scripts/smoke_live.py`)
- [x] 130 tests; commit `9e46d3d`

## Día 5 · Agente de Requerimientos (productor) — [x] (falta commit)
- [x] Plan aprobado (embeddings determinísticos ahora; reales en la evaluación)
- [x] `rag/`: chunking (clase 5) por turnos de orador, embeddings determinísticos, retrievers en memoria y Qdrant local
- [x] Biblioteca de fuentes con metadata (reunión, fecha, tipo) y corpus sintético en `evals/fixtures/` (3 reuniones + preventa)
- [x] Tools reales: `ingestar_y_fragmentar`, `buscar_en_fuentes`, `redactar_historia`
- [x] Agente de Requerimientos con su `agent.md` y `scripts/run_requerimientos.py`
- [x] Tests sin red (161 en total) incluido el de inyección en el texto de reunión
- [x] Corrida en vivo con Gemini: 4 historias citadas, tomó lo más reciente (Excel) e ignoró la inyección
- [ ] Commit y push (cuando se pida)
- [ ] Pendiente detectado: historias casi duplicadas (dos de SSO con títulos distintos) → lo cubren el Crítico y el Supervisor
- [ ] Pendiente detectado: cuota gratuita de Gemini = 20 pedidos/día por modelo → activar facturación o definir modelo de respaldo antes de la evaluación

## Día 6 · Crítico (esquema)
- [ ] Tools: `verificar_cita`, `buscar_contraevidencia`, `evaluar_dor_invest`
- [ ] Verificación textual determinística de citas
- [ ] Objeciones y tope de 2 rondas de negociación

## Día 7 · Auditor de Proyecto (esquema)
- [ ] Tools: `comparar_con_preventa`, `detectar_contradicciones`, `consultar_decisiones_vigentes`, `registrar_decision_aprobada`
- [ ] Cambio de alcance y decisiones que evolucionaron

## Día 8 · Supervisor y grafo (esquema)
- [ ] Grafo de LangGraph, planificación, `delegar_tarea` y `escalar_a_persona`
- [ ] Presupuestos por agente aplicados desde el grafo

## Día 9 · Integración y Azure DevOps (esquema)
- [ ] Decisión MCP vs. cliente REST (esperar las clases de noviembre)
- [ ] Modo simulado y modo real; plan en dry-run con hash
- [ ] `revalidar_plan`, idempotencia por ítem y publicación solo del plan aprobado

## Día 10 · Human-in-the-Loop (esquema)
- [ ] `interrupt` con `SqliteSaver`: cambio de alcance, desacuerdo sin consenso y plan de publicación
- [ ] Acciones aprobar / editar / rechazar con `args_hash`

## Día 11 · Skills y contexto (esquema)
- [ ] Cinco skills en formato Agent Skills (`SKILL.md`, references, scripts, assets)
- [ ] `context_budget.yaml` y context builder

## Día 12 · Interfaz (esquema)
- [ ] App Streamlit con tablero, trazas y pantallas de aprobación

## Día 13 · Evaluación (esquema)
- [ ] Dataset con errores sembrados, métricas y trazabilidad
- [ ] A/B de modelos por agente (incluye embeddings reales con el extra `rag`)
- [ ] Modelo de respaldo para el productor (p. ej. `gemini-3.1-flash-lite`)

## Día 14 · Entrega (esquema)
- [ ] Docker y docker-compose reproducibles, con `LIVE_MODE=0` como demo estable
- [ ] Diagrama de arquitectura y decisiones técnicas en `docs/`
- [ ] README completo (quitar los ⚠️ A COMPLETAR), integrantes y limitaciones
- [ ] Video de respaldo de 3 a 5 minutos (grabar temprano)

## Decisiones abiertas
- [ ] MCP para Azure DevOps o Jira: esperar las clases de noviembre
- [ ] Embeddings reales (`sentence-transformers`): decidir en la evaluación
- [ ] Modelo de respaldo de Gemini ante 503
