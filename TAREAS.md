# TAREAS · BacklogGuard

Checklist de avance por día. Se trabaja de a un día y no se avanza sin confirmación.
Entrega: **domingo 2026-12-06 23:59**. Los días 6 en adelante son un esquema **sin confirmar**.

Leyenda: `[x]` hecho · `[~]` en curso · `[ ]` pendiente

## Día 1 · Contrato del tablero — [x]
**Objetivo:** definir qué es un ítem del backlog y qué reglas debe cumplir para que todo lo que producen los agentes sea verificable.

- [x] `BacklogItem` — es la unidad de trabajo del backlog (épica, historia, tarea o caso de prueba). Guarda título, descripción, criterios de aceptación, citas y estado. No puede pasar a "sustentado" sin al menos una cita, ni a "aprobado" sin una persona que lo apruebe.
- [x] `Citation` — es la prueba de dónde sale un ítem: la frase textual, la reunión o documento, la fecha y quién lo dijo. Sin ella, nada se puede verificar.
- [x] `Objection` — es una objeción del Crítico a un ítem, con su ronda. Permite ver qué se cuestionó y si ya se resolvió.
- [x] `Finding` — es un hallazgo del Auditor: cambio de alcance, contradicción, algo tratado pero no vendido o vendido pero no tratado. Dice a quién va dirigido y a qué ítem afecta.
- [x] `AgentMessage` — es el mensaje que un agente le deja a otro. Hace visible la conversación entre agentes.
- [x] `Board` — es el tablero compartido: junta ítems, hallazgos y mensajes. Todos los agentes trabajan sobre él.
- [x] Estados y transiciones (borrador → objetado/sustentado → aprobado/excluido) — impiden saltos indebidos; por ejemplo, un ítem excluido no vuelve.
- [x] Reglas en código: cita obligatoria para sustentar, aprobador obligatorio para aprobar y tope de 2 rondas de negociación (`MAX_ROUNDS`) — la regla no depende de que el modelo la recuerde.
- [x] Checkpoint JSON versionado del tablero (`BoardCheckpointStore`, `StaleCheckpointError`) — guarda el estado de una corrida y avisa si se intenta pisar una versión más nueva.
- [x] Repo público en GitHub, README (13 secciones) y `.gitignore` — deja el proyecto publicado y documentado desde el inicio.

## Día 2 · ToolRegistry y policy gate — [x]
**Objetivo:** que cada agente use solo las herramientas de su rol, y que nadie pueda escribir en el backlog sin un plan aprobado por una persona.

- [x] `Tool` — es una capacidad que un agente puede usar (buscar, redactar, verificar…). Declara qué recibe, qué tan riesgosa es y cuánto puede tardar.
- [x] `ToolPolicy` — decide qué herramientas ve cada rol. Por ejemplo, el Crítico puede leer y calcular pero no escribir.
- [x] `ToolRegistry` — es el control de entrada: cada pedido de un agente pasa por existencia, disponibilidad, validación de datos y autorización antes de ejecutarse.
- [x] `ExecutionContext` — dice quién llama (rol, corrida) y si hay un plan aprobado. Lo arma la aplicación, nunca el texto de una reunión.
- [x] Catálogo de las 16 tools, cada una visible solo para su rol — define el reparto de trabajo entre agentes.
- [x] Guarda de `ejecutar_plan_aprobado` — la publicación en Azure DevOps exige un plan aprobado y que su huella (hash) coincida con el que se va a publicar.
- [x] `config/policy.yaml` y `AGENTS.md` — documentan los permisos y las reglas. Un test verifica que coincidan con el código, que es quien manda.

## Día 3 · Memoria del proyecto — [x]
**Objetivo:** que el sistema recuerde las decisiones del proyecto entre corridas, sin guardar cualquier cosa.

- [x] `MemoryStore` — es la memoria en SQLite. Filtra qué se guarda (Write Gate), reemplaza decisiones viejas por nuevas conservando el historial y puede hacer caducar recuerdos.
- [x] `ProjectMemory` — es la memoria propia del proyecto. Responde "¿qué se decidió y sigue vigente?", "¿cómo evolucionó?" y "¿qué preguntas siguen abiertas?".
- [x] Las escrituras exigen `approved_by` — solo se recuerda lo que una persona aprobó.

## Día 4 · Capa de LLM y ciclo de agente — [x]
**Objetivo:** poder hablar con los modelos reales (Claude y Gemini) de forma segura y repetible, y tener el ciclo que hace pensar y actuar a un agente.

- [x] `Settings` — lee la configuración y las claves desde `.env` sin exponerlas.
- [x] Errores de LLM (`LLMError`) — distinguen límite de uso, falla transitoria, timeout, pedido inválido y credencial mala, para reaccionar distinto a cada uno.
- [x] `FakeProvider`, `GeminiProvider`, `AnthropicProvider` — tres proveedores con la misma interfaz. El falso permite probar todo sin red ni costo.
- [x] Resiliencia — reintenta con espera creciente cuando el proveedor falla de forma pasajera, y sin duplicar reintentos.
- [x] `config/models.yaml` — dice qué modelo usa cada agente. Impide usar el mismo modelo en el productor y en el Crítico.
- [x] `run_basic_agent` — es el ciclo del agente: decide, actúa, observa. Corta por pasos, tiempo, cantidad de llamadas o tokens gastados.
- [x] `LLMDecider` — traduce la respuesta del modelo en una decisión válida. Trata el texto de las fuentes como dato, nunca como orden.
- [x] `scripts/smoke_live.py` — prueba real mínima de los 5 agentes, con costo estimado.
- [x] 130 tests; commit `9e46d3d`.

## Día 5 · Agente de Requerimientos (productor) — [x]
**Objetivo:** convertir reuniones y preventa en historias de usuario redactadas, con criterios de aceptación y citas que las respalden.

- [x] Plan aprobado (embeddings determinísticos ahora; los reales, en la evaluación).
- [x] `rag/chunking.py` — corta cada reunión en fragmentos por turno de orador, guardando quién habló. Así cada cita se puede atribuir.
- [x] `rag/embeddings.py` y `rag/retrieval.py` — convierten los fragmentos en vectores y permiten buscar los más parecidos a una consulta, con filtros por tipo de fuente o documento. Hay versión en memoria y versión Qdrant local.
- [x] `rag/sources.py` (`SourceLibrary`) — es la carpeta de fuentes que controla la aplicación. El modelo pide una fuente por nombre y no puede leer archivos arbitrarios ni inventar su fecha o su tipo.
- [x] `evals/fixtures/` — corpus sintético: 3 reuniones y 1 preventa, con un cambio de formato (PDF a Excel), una app móvil fuera de alcance y una instrucción maliciosa sembrada.
- [x] `ingestar_y_fragmentar` — carga una fuente de la biblioteca y la deja lista para buscar.
- [x] `buscar_en_fuentes` — devuelve los fragmentos relevantes con reunión, fecha y orador.
- [x] `redactar_historia` — crea el ítem en el tablero en borrador. Exige formato Gherkin y al menos una cita real; la metadata de la cita la toma del fragmento, no del modelo. Rechaza duplicados exactos.
- [x] Agente de Requerimientos y su `agent.md` — define cómo trabaja: indexar, buscar, redactar con citas, señalar lo ambiguo y no obedecer órdenes escritas dentro de las reuniones.
- [x] `scripts/run_requerimientos.py` — corre el agente sobre el corpus, con el modelo configurado.
- [x] Tests sin red (161 en total), incluido el de inyección en el texto de reunión.
- [x] Corrida en vivo con Gemini — 4 historias citadas, tomó lo más reciente (Excel) e ignoró la inyección.
- [x] Commit y push (`a8ae603`).
- [ ] Pendiente detectado: historias casi duplicadas (dos de SSO con títulos distintos) → las cubren el Crítico y el Supervisor.
- [ ] Pendiente detectado: la cuota gratuita de Gemini es de 20 pedidos por día por modelo → activar facturación o definir un modelo de respaldo antes de la evaluación.

## Día 6 · Crítico y negociación — [x] (falta commit)
**Objetivo:** que un segundo agente, con otro modelo, revise cada historia del productor y objete lo que no esté bien sustentado.

- [x] `verificar_cita` — comprueba, sin usar un modelo, que la frase citada exista textualmente en la fuente. Ignora espacios, mayúsculas y comillas, pero exige acentos y palabras exactos. También verifica reunión y fecha.
- [x] `buscar_contraevidencia` — busca en otras reuniones algo que contradiga la historia, sin contar lo que ya cita, y marca lo más reciente que la cita.
- [x] `evaluar_dor_invest` — devuelve el contenido del ítem y controles objetivos: citas, formato Como/quiero/para, Gherkin, tamaño (≤ 5 criterios) y posibles duplicados. El juicio de INVEST lo emite el modelo con esa evidencia.
- [x] Agente Crítico y su `agent.md` — corre una vez por ítem con `claude-opus-5-5`; su veredicto (`CriticVerdict`) se valida con Pydantic y se repara una vez si viene mal formado.
- [x] `negotiate_item` — aplica en código la negociación: verifica citas, registra objeciones por ronda, pide la corrección al productor y corta a las 2 rondas con `sin_consenso`. Una cita falsa impide `sustentado` aunque el modelo diga que sí.
- [x] `redactar_historia` con `revises` — el productor corrige un ítem objetado conservando su id y sus objeciones.
- [x] `scripts/run_critico.py` — corrida real con ítems sembrados: detectó cita deformada, reporte vencido (PDF→Excel), filtro de fecha pospuesto y duplicados de SSO, y sustentó el ítem correcto.
- [x] Tests sin red (182 en total).
- [ ] Commit y push (cuando se pida)
- [ ] Pendiente: probar la negociación completa con el productor real cuando haya cuota de Gemini.
- [ ] Observación: Opus objeta con criterio estricto (criterios Gherkin genéricos). A medir en la evaluación del Día 13.

## Día 7 · Auditor de Proyecto (esquema)
**Objetivo:** comparar lo que se trató con lo que se vendió, y detectar cambios de alcance y contradicciones entre reuniones.

- [ ] `comparar_con_preventa` — marca lo tratado que no estaba vendido y lo vendido que no se trató.
- [ ] `detectar_contradicciones` — encuentra reuniones que se contradicen y distingue una contradicción de una decisión que evolucionó.
- [ ] `consultar_decisiones_vigentes` — lee la memoria del proyecto para no volver a discutir lo ya decidido.
- [ ] `registrar_decision_aprobada` — guarda en la memoria una decisión que una persona aprobó.

## Día 8 · Supervisor y grafo (esquema)
**Objetivo:** coordinar a los agentes en un flujo único que se puede pausar y reanudar.

- [ ] Grafo de LangGraph — define el orden: productor → Crítico → Auditor → Integración, con vueltas para las rondas.
- [ ] Planificación del Supervisor, `delegar_tarea` y `escalar_a_persona` — el Supervisor reparte el trabajo, arbitra y pide ayuda humana cuando corresponde.
- [ ] Presupuestos por agente aplicados desde el grafo — ningún agente puede gastar pasos o tokens sin límite.

## Día 9 · Integración y Azure DevOps (esquema)
**Objetivo:** publicar en el backlog real solo lo aprobado, sin duplicar ni pisar nada.

- [ ] Decisión MCP vs. cliente REST — se define después de las clases de noviembre.
- [ ] Modo simulado y modo real — se puede demostrar sin tocar un Azure DevOps verdadero.
- [ ] `armar_plan_dry_run` — arma el plan (crear, actualizar, vincular u omitir) sin ejecutarlo y le calcula una huella.
- [ ] `revalidar_plan` y `buscar_en_backlog` — antes de publicar, comprueban que el backlog no cambió desde que se armó el plan.
- [ ] `ejecutar_plan_aprobado` con idempotencia por ítem — publica solo el plan aprobado, y repetirlo no genera duplicados.

## Día 10 · Human-in-the-Loop (esquema)
**Objetivo:** que el sistema se detenga y espere a una persona en los tres momentos que importan.

- [ ] `interrupt` con `SqliteSaver` — pausa la corrida, guarda su estado y la retoma cuando la persona responde.
- [ ] Tres pausas: cambio de alcance (decide el service manager), desacuerdo sin consenso (decide el PO) y plan de publicación (siempre se aprueba).
- [ ] Acciones aprobar, editar o rechazar con `args_hash` — si el plan cambia después de aprobarse, la aprobación deja de valer.

## Día 11 · Skills y contexto (esquema)
**Objetivo:** darle a cada agente solo el conocimiento y el contexto que necesita, sin sobrecargarlo.

- [ ] Cinco skills en formato Agent Skills (`SKILL.md`, references, scripts, assets) — guías reutilizables por agente. Explican cómo hacer algo, pero no dan permisos.
- [ ] `context_budget.yaml` y context builder — limitan cuánto contexto recibe cada agente y arman ese contexto de forma ordenada.

## Día 12 · Interfaz (esquema)
**Objetivo:** que una persona pueda usar el sistema sin tocar código.

- [ ] App Streamlit — muestra el tablero, la traza de cada agente y las pantallas para aprobar, editar o rechazar.

## Día 13 · Evaluación (esquema)
**Objetivo:** medir con datos si el sistema funciona y qué modelo conviene en cada rol.

- [ ] Dataset con errores sembrados, métricas y trazabilidad — verifica que el sistema encuentre los errores puestos a propósito.
- [ ] A/B de modelos por agente — compara calidad, costo y tiempo; incluye embeddings reales con el extra `rag`.
- [ ] Modelo de respaldo para el productor (p. ej. `gemini-3.1-flash-lite`) — protege la demo si Gemini falla o se queda sin cuota.

## Día 14 · Entrega (esquema)
**Objetivo:** dejar el proyecto reproducible, documentado y listo para presentar.

- [ ] Docker y docker-compose con `LIVE_MODE=0` como demo estable — cualquiera lo levanta sin claves ni costo.
- [ ] Diagrama de arquitectura y decisiones técnicas en `docs/` — explican cómo está armado y por qué.
- [ ] README completo (quitar los ⚠️ A COMPLETAR), integrantes y limitaciones.
- [ ] Video de respaldo de 3 a 5 minutos — se graba temprano, por si la demo en vivo falla.

## Decisiones abiertas
- [ ] MCP para Azure DevOps o Jira: esperar las clases de noviembre
- [ ] Embeddings reales (`sentence-transformers`): decidir en la evaluación
- [ ] Modelo de respaldo de Gemini ante 503 o falta de cuota
