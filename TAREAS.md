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

## Día 7 · Auditor de Proyecto — [x] (falta commit)
**Objetivo:** comparar lo que se trató con lo que se vendió, y detectar cambios de alcance y contradicciones entre reuniones.

- [x] `comparar_con_preventa` — reúne la evidencia en ambos sentidos: qué reuniones e ítems cubren cada punto vendido, y qué temas de reunión tienen respaldo en la preventa. El modelo clasifica.
- [x] `detectar_contradicciones` — pares de fragmentos parecidos ordenados por fecha, con orador y marca de "misma fecha". El modelo distingue evolución de contradicción.
- [x] `consultar_decisiones_vigentes` — lee la memoria del proyecto para no volver a discutir lo ya decidido.
- [x] `registrar_decision_aprobada` — guarda una decisión en la memoria solo si la aplicación entrega la aprobación humana (`approved_by` del contexto, nunca del modelo) y la frase citada existe en la fuente.
- [x] Agente Auditor y su `agent.md` — entrega un `AuditReport` validado; si viene mal formado se repara una vez (ayudante compartido con el Crítico).
- [x] `apply_report` — verifica cada cita, descarta lo que no se puede verificar, decide a quién va cada hallazgo y reabre los ítems que el productor debe corregir.
- [x] `entrega.py` — un mensaje por ítem afectado al productor; lo que exige decisión humana va al Supervisor con quién decide según la política.
- [x] Corpus: líneas nuevas del ERP (vendido y no tratado) y de la frecuencia de notificaciones (contradicción).
- [x] Tablero: transición `sustentado → objetado`. Política: pausas para `contradiccion` y `vendido_no_tratado`.
- [x] Corrida real con Opus: 6 hallazgos con citas verificadas (ERP, app móvil, cambio de alcance, PDF→Excel, contradicción de frecuencia, filtro de fecha) y la inyección informada como dato.
- [x] Tests sin red (205 en total) y especificación `docs/specs/auditor.md` al día.
- [ ] Commit y push (cuando se pida)
- [ ] Observación: el Auditor suma citas de la preventa a sus hallazgos; a medir en la evaluación (Día 13).

## Día 8 · Supervisor y grafo — [x]
**Objetivo:** coordinar a los agentes en un flujo único que se puede guardar y consultar desde otra instancia.

- [x] `delegar_tarea` — el Supervisor registra a quién le asigna qué: valida el agente, la tarea y que las fuentes existan. No ejecuta nada.
- [x] `escalar_a_persona` — registra una escalación; quién decide lo fija la política, no el modelo, y no se duplica.
- [x] Agente Supervisor y su `agent.md` — elige las fuentes y la instrucción del productor; si su plan es inválido, se usa el plan por defecto. La preventa nunca se usa para redactar.
- [x] Grafo de LangGraph (`graph/`) — recorrido fijo: plan → producir → revisar (un ítem por vuelta) → auditar → [revisar los reabiertos, una vez] → escalar → resumir. El Crítico y el Auditor corren siempre.
- [x] Escalaciones por código — sin consenso y contradicción al PO; cambio de alcance y vendido o tratado sin vender al service manager.
- [x] `config/budgets.yaml` — tope de tokens, ítems y tiempo por corrida; al agotarse, la corrida corta con `presupuesto_agotado`.
- [x] Estado guardado en `SqliteSaver` por `thread_id`; otra instancia del grafo lee el mismo estado.
- [x] Un error de un agente queda registrado y la corrida sigue (`completada_con_errores`).
- [x] `scripts/run_pipeline.py` — corrida completa; verificada en modo simulado.
- [x] Tests sin red (232 en total) y especificación `docs/specs/supervisor.md` al día. Dependencias: extra `graph` (`langgraph`, `langgraph-checkpoint-sqlite`).
- [x] Corrida real completa (≈104 mil tokens): Haiku produjo 3 historias, el Crítico las sustentó en la ronda 1, el Auditor registró 7 hallazgos y se generaron 5 escalaciones (4 al service manager, 1 al PO). Sin errores.
- [ ] Observación: Haiku no redactó la historia de notificaciones por email (Gemini sí lo había hecho). A medir en la evaluación del Día 13.
- [ ] Observación: escalaciones redundantes — la app móvil y el cambio PDF→Excel generan cada uno dos hallazgos (`tratado_no_vendido` + `cambio_de_alcance`, `decision_evolucionada` + `cambio_de_alcance`) y por tanto dos escalaciones. Agrupar por tema antes de pedir una decisión humana (Día 10).
- [x] Commit y push.

## Día 9 · Integración con Azure DevOps simulado — [x] (falta commit)
**Objetivo:** convertir lo aprobado en un plan de publicación seguro y poder publicarlo sin duplicar, sobre un backlog simulado realista; y ver a los agentes trabajar en vivo.

- [x] `BacklogGateway` y backlog simulado — ids numerados, versiones, etiquetas y padre-hijo; persiste en archivo entre corridas; inyecta fallos para pruebas. El modo real (MCP) queda diferido y avisa con un mensaje claro.
- [x] Plan de publicación (`PublishPlan`) — acción por ítem (crear, actualizar, vincular, omitir) con su motivo, clave de idempotencia y hash determinístico; omite posibles duplicados (incluso entre ítems del mismo plan).
- [x] `buscar_en_backlog`, `armar_plan_dry_run`, `revalidar_plan` — leen o preparan; no escriben.
- [x] `ejecutar_plan_aprobado` — única escritura: exige hash aprobado y permiso de escritura, revalida antes de escribir, publica padres antes que hijos, es idempotente, recupera resultados ambiguos y se detiene ante un fallo parcial.
- [x] Registro de publicaciones (SQLite) — intención, resultado y planes armados.
- [x] Agente de Integración y su `agent.md` — arma y revalida el plan; la publicación la dispara la aplicación (`execute_approved_plan`). El plan se arma aunque el modelo falle.
- [x] Nodo del grafo — arma el plan al final de la corrida y termina en `plan_pendiente_de_aprobacion`; no publica.
- [x] Vista en vivo — cada paso de cada agente se emite como evento (`on_event`) y se muestra en una línea (`graph/live.py`).
- [x] `scripts/run_pipeline.py` — levanta todos los agentes con modelos reales, muestra el trabajo en vivo, el plan y el backlog antes y después (`--reset`, `--seed`, `--aprobar`).
- [x] Corrida real completa (≈158 mil tokens): 3 historias sustentadas, 6 hallazgos, 5 escalaciones, plan de 2 por crear y 1 omitida por duplicado de un work item manual; tras la aprobación simulada, 2 work items publicados.
- [x] Defectos encontrados en esa corrida y corregidos: `AZDO_PROJECT` vacío pisaba el valor por defecto, y dos historias casi iguales (otro verbo, otro orden) pasaban como distintas.
- [x] Tests sin red (259 en total) y especificación `docs/specs/integracion.md` al día.
- [ ] Repetir la corrida real para ver el efecto de la corrección de duplicados (≈US$1).
- [ ] Commit y push (cuando se pida)
- [ ] Observación: el productor corrige una historia pero deja otra equivalente (dos versiones del mismo requisito). Mejorar en la evaluación del Día 13.

## Día 10 · Human-in-the-Loop y pantalla de decisiones — [x] (10a subida; 10b falta commit)
**Objetivo:** que el sistema se detenga y espere a la persona correcta, que su decisión quede ligada a la versión exacta que vio y que la corrida continúe hasta publicar lo aprobado.

**Etapa 10a · núcleo del HITL — [x]**
- [x] Contratos (`hitl/models.py`) — `DecisionRequest` (con versión y hash del contenido), `HumanDecision` (aprobar, editar o rechazar, con persona, rol, versión y hash) y `DecisionRecord` (registro de auditoría).
- [x] Roles (`config/people.yaml`) — service manager, product owner y full stack IA engineer. Es genérico: sin nombres de personas y sin autenticación real (se declara como limitación).
- [x] Agrupación de hallazgos (`hitl/grouping.py`) — los que comparten citas son un único pedido; si el grupo mezcla razones prima la del service manager. En la última corrida real, 5 pedidos de decisión habrían sido 3.
- [x] Validación (`hitl/logic.py`) — solo decide el rol de la política, la decisión debe llevar la versión y el hash vigentes, y solo se editan los campos permitidos con datos válidos.
- [x] Efectos idempotentes — desacuerdo sobre un ítem (aprobar → sustentado, rechazar → excluido, editar → ítem corregido) y decisiones de alcance (se registran en la memoria del proyecto con quién las aprobó).
- [x] Pausas con `interrupt` en el grafo — una por pedido; el estado queda en SQLite y otra instancia del grafo retoma la corrida con `Command(resume=...)`. Una decisión inválida deja el estado intacto y la pausa se ofrece de nuevo con el motivo.
- [x] Una decisión vigente en la memoria evita volver a escalar el mismo asunto en una corrida posterior.
- [x] Plan de publicación con aprobación — aprobar publica (los ítems pasan a aprobados), editar excluye ítems y genera un plan nuevo con otro hash, rechazar no publica; un cambio del backlog tras aprobar bloquea la publicación.
- [x] `scripts/run_pipeline.py` (pausa y `--auto`) y `scripts/decidir.py` — correr y decidir desde la terminal.
- [x] Regresión corregida: títulos cortos idénticos ("Notificación por email") dejaron de detectarse como duplicados al unificar la similitud; detectado por un test.
- [x] Tests sin red (284 en total) y especificación `docs/specs/hitl.md` al día.
- [ ] Commit y push de la etapa 10a (cuando se pida).

**Etapa 10b · pantalla y modo demo — [x]**
- [x] Pantalla de Streamlit (`ui/`) — elegir persona (solo ve los pedidos de su rol), pedido con resumen, evidencia con citas y los botones aprobar, editar (crea versión nueva) y rechazar con comentario; estado de la corrida en vivo, tablero con ítems, citas y objeciones, hallazgos, backlog simulado antes y ahora, resultado de la publicación y registro de decisiones.
- [x] Controlador de la corrida (`ui/controller.py`) — corre el grafo en un hilo y expone el estado; se prueba sin pantalla. Una corrida a la vez por proceso.
- [x] Modo demo sin costo (`llm/recording.py`) — grabar las respuestas de cada modelo y reproducirlas con proveedores guionados: mismo recorrido, sin red ni claves.
- [x] Corrida real grabada (`evals/recordings/demo_acme.json`, ≈145 mil tokens): 3 historias, auditoría, 4 pedidos de decisión y un plan de 3 work items publicados. La grabación se reproduce de punta a punta en un test.
- [x] Pruebas de la pantalla con el probador integrado de Streamlit (`AppTest`) y comprobación de que el servidor arranca (health ok).
- [x] README: variables de entorno, archivos de configuración y comandos de ejecución locales.
- [x] Tests sin red (296 en total) y especificación `docs/specs/hitl.md` al día.
- [ ] Commit y push de la etapa 10b (cuando se pida).
- [ ] Pendiente: ver la pantalla en un navegador real (las pruebas automáticas cubren el comportamiento, no el aspecto).
- [ ] Observación: el agente de Integración llamó una vez a `buscar_en_backlog` sin parámetros (error controlado y se recuperó); a medir en la evaluación.


## Extra · Carga de fuentes propias (preventa en PDF y transcripción) — [x] (falta commit)
**Objetivo:** correr el sistema con documentos reales en lugar de los de ejemplo.

- [x] Importador de PDF (`rag/importers.py`) — texto por página con el número de página; rechaza PDF escaneados, dañados, protegidos o demasiado grandes. Limpia el ruido que dejan las presentaciones («Icono / Descripción generada automáticamente»).
- [x] Importador de transcripciones — UTF-8 o Latin-1; formatos `Nombre: texto`, `[00:12:30] Nombre: texto` y `Nombre 00:12` con el texto debajo; lee el bloque «Participantes» para darle rol a cada orador; el encabezado no se confunde con la conversación; las notas del que tomó la minuta se conservan como «Nota de la minuta».
- [x] Fragmentado por páginas (preventa) y por diálogo (reunión) — la preventa no se divide por «orador» y las citas muestran la página.
- [x] Búsqueda híbrida BM25 + embeddings con fusión RRF (clase 8) — la búsqueda del productor y del Crítico ahora encuentra lo relevante con documentos reales.
- [x] Pestaña «Fuentes» en la pantalla y `scripts/importar_fuentes.py` por terminal; fuentes en `data/fuentes/` (no se suben a git).
- [x] Con fuentes propias: sin work items de ejemplo, tope de historias (12 por defecto), aviso de costo y bloqueo si no hay modelos reales.
- [x] Presupuestos ajustados para documentos reales (productor, Auditor y corrida) y salida del Auditor recortada para que quepa en lo que puede leer.
- [x] Tests (321 en total), incluidos los que usan los archivos reales si están en `entrada/`; especificación `docs/specs/fuentes.md` al día.
- [x] Pestaña «Corridas guardadas»: lista las corridas de `data/corridas.sqlite` (de la pantalla o de un script) y abre una en solo lectura, con el backlog resultante actualizado. Error corregido: la lista fallaba si el archivo existía pero no había corridas.
- [x] Roles genéricos (sin nombres de personas) y objetivo genérico (sin «portal de ACME»).
- [x] Corrida real con la preventa y la transcripción de Infobae (2026-10-25, `corrida-2571a98b`, 12,7 min, 564 mil tokens de un tope de 600 mil, estado `publicada`): 4 historias con citas verificadas (3 publicadas, 1 omitida por duplicada), 6 hallazgos reales del Auditor y 8 pedidos de decisión (aprobados automáticamente por el script).
- [ ] Hallazgos de esa corrida a resolver: (1) el productor (Haiku) redactó solo 4 historias de al menos 8 requisitos distintos de la reunión; (2) los cambios de alcance que detecta el Auditor (domicilio comercial, roles y permisos, historial de reintentos, destinatarios parametrizables) se aprueban pero nadie los convierte en historias; (3) dos historias casi iguales no se fusionaron tras 2 rondas; (4) la cita de un diálogo lista a todos los oradores del fragmento en lugar de quien dijo la frase; (5) el productor reescribía una historia varias veces seguidas (acotado en `revise_item`).
- [ ] Commit y push (cuando se pida).

## Bloque 1A · Línea base de la preventa — [x] (falta commit)
**Objetivo:** tratar la preventa como línea base (lo vendido) y no mezclarla con la evidencia de las reuniones (lo acordado).

- [x] Huella de cada fuente — se guarda al importar y se verifica al cargar; una fuente editada a mano se señala. Reimportar lo mismo no escribe; reimportar algo distinto (contenido, nombre, fecha, tipo o formato) pide confirmación y muestra las huellas.
- [x] Registro de fuentes por corrida — cada corrida guarda id, tipo, fecha, huella, palabras y rol (línea base o evidencia) de lo que usó; se ve en «Corrida» y en «Corridas guardadas».
- [x] La búsqueda del productor deja la preventa afuera por defecto; entra si se la pide con `incluir_linea_base`, por tipo o por documento. Cada resultado indica su rol.
- [x] Regla de citas — una historia (o su corrección) necesita al menos una cita de una reunión o minuta; la preventa puede acompañar pero no sustentar sola.
- [x] El Crítico comprueba el respaldo acordado con un control más en DoR/INVEST.
- [x] La pantalla etiqueta «Línea base (preventa)» y «Evidencia (reunión/minuta)» en los pedidos de decisión y en el tablero.
- [x] Verificado con los archivos reales de Infobae, sin costo: reimportar da «sin cambios», una fecha distinta pide confirmación y la búsqueda por defecto ya no trae fragmentos de la preventa.
- [x] 338 tests; la grabación de la demo sigue reproduciéndose; especificación `docs/specs/linea-base-y-contexto.md` al día.
- [ ] Siguiente: Bloque A restante del punto 4 (medición, tope de reescrituras y expedientes del Crítico y del Auditor) y luego el Bloque B.
- [ ] Commit y push (cuando se pida).

## Bloque A (parcial) · Tareas entre agentes, tope de correcciones y expediente — [x] (falta commit)
**Objetivo:** ver qué se pasan los agentes y cuánto cuesta, y bajar el gasto sin tocar la trazabilidad.

- [x] Registro de tareas entre agentes — cada encargo (planificar, redactar, revisar, corregir, auditar, armar el plan, resumir, decisión de una persona) queda con origen, destino, ítem, ronda, estado, tokens y modelo.
- [x] Solapa «Tareas entre agentes» — totales, gasto por agente, quién le pasa tareas a quién y el backlog completo con filtro; «Corridas guardadas» suma tareas y correcciones.
- [x] Tope de corrección — dentro de una tarea, un ítem se corrige con éxito una sola vez; el segundo intento se rechaza y un intento fallido no cuenta.
- [x] Expediente precalculado — los controles fijos del Crítico y del Auditor los corre el código antes del primer paso del modelo, pasan por el ToolRegistry, quedan en la traza como «precalculada» y se pueden apagar en `config/context_budget.yaml`.
- [x] Medición con costo estimado — cada llamada a un modelo se mide (entrada/salida) y se reparte entre las tareas; precios en `config/pricing.yaml`; un modelo sin precio se avisa en lugar de inventar el costo. Se ve en la solapa «Tareas entre agentes».
- [x] Prueba de calidad con Opus real (`scripts/comparar_expediente.py`, 5 ítems sembrados): mismo veredicto en 5 de 5; llamadas 17 → 5, tokens de entrada 41.369 → 17.948, costo ~US$ 0,28 → ~US$ 0,14.

## Bloque 1B · Compromisos de la preventa (línea base extraída) — [x] (subido; corrida real: 80 compromisos, 0 descartados, US$ 0,61)
**Objetivo:** resumir la preventa una sola vez en compromisos verificables, agrupados por épica, para compararlos después contra las reuniones.

- [x] Extracción explícita — `scripts/extraer_linea_base.py` o el botón de «Fuentes». Muestra el gasto estimado antes, exige confirmarlo y necesita un modelo real; nunca corre sola. Usa el modelo del Auditor.
- [x] Cada compromiso lleva épica, capacidad, alcance (incluido, excluido o condición), página y una cita literal verificada por código contra el texto de esa página. Los que no se verifican se descartan y se informan con el motivo.
- [x] Se guardan en `data/linea_base/` ligados a la huella de la preventa: se reutilizan mientras no cambie y quedan «desactualizados» si cambia.
- [x] La pantalla lista los compromisos por épica, con página y cita, y los descartados aparte. La épica es solo una agrupación, no un ítem del tablero.
- [ ] Siguiente: el Bloque 2 (catálogo persistente y continuidad entre reuniones); el Auditor usará estos compromisos en el Bloque 3.

## Bloque 2A · Catálogo persistente de requisitos — [x] (falta commit)
- [x] `src/backlogguard/catalog/`: modelos (requisito `RQ-nnn` con id estable, versiones con relación nuevo/refina/reemplaza/divide/fusiona, evidencias, propuestas) y almacén SQLite `data/catalogo.sqlite`.
- [x] Reglas en código: nada cambia sin propuesta aprobada con nombre; la preventa sola no alcanza como evidencia; reprocesar la misma fuente (id + huella) no duplica; «ya cubierto» solo suma evidencia; clave de publicación por requisito y versión.
- [x] «Iniciar corrida» con fuentes propias ya no borra la memoria; botón «Empezar proyecto nuevo» con confirmación (conserva fuentes y línea base).
- [x] `tests/test_catalogo.py` (21 tests). Suite completa: 405.
- [ ] 2C redacción, revisión por lote y publicación · 2D solapa Catálogo y docs.

## Bloque 2B · Lectura de una reunión contra el catálogo — [x] (corrida real repetida: 19 candidatos, US$ 0,19; falta revisar las propuestas con la persona usuaria)
- [x] `catalog/ingest.py`: enumera los requisitos de la reunión (productor, cita verificada por código y deduplicada), busca parecidos del catálogo (búsqueda híbrida), el Auditor clasifica en lotes de 8 viendo el mapa completo de compromisos, el código baja a «incierto» lo que no se sostiene (destino inexistente, confianza < 0,7, forma inválida, sin clasificar).
- [x] Idempotente por fuente + huella + candidato; si falla a la mitad no queda procesada y al reintentar solo clasifica lo que falta; «ya cubierto» suma evidencia sola; reunión anterior a otra ya leída: todo a revisión.
- [x] `scripts/clasificar_reunion.py` (estima; `--confirmar` corre; `--ver`) y sección «Reuniones contra el catálogo» en Fuentes.
- [x] `tests/test_continuidad.py` (21 tests). Suite completa: 426.
- [x] Corrida real 1 (reunión de Infobae): 21 candidatos, 1 descartado, US$ 0,10. Ajustes después: mapa completo de compromisos al Auditor, confianza baja también para «nuevo», estimación recalibrada.
- [x] Segundo intento para citas parafraseadas (una sola pasada extra). Corrida real 2: 19 candidatos, 1 descartado, US$ 0,187. Varía de una corrida a otra (21 vs 19): revisar determinismo en la evaluación.
- Aún no conectado al grafo (2C, paso siguiente).

## Bloque 2C · Revisión por lote — [~] paso 1 hecho (revisar y aprobar en el catálogo); falta redacción, grafo y publicación
- [x] `catalog/review.py`: lote solo para «nuevo» y «refina» pendientes de una reunión en orden; contradice/divide/fusiona/incierto/fuera de orden, una por una; cambio de alcance (contradice) lo decide el service manager, el resto el product owner. Se registra el **rol**, no el nombre (decisión de la persona usuaria). Un lote con una propuesta que no corresponde falla entero sin cambiar nada.
- [x] `Catalog.edit` (corregir el borrador antes de decidir) y `Catalog.reclassify` (un «incierto» se resuelve como nuevo, refina o cubierto; no se aprueba tal cual, o se descarta). Fuera del curso.
- [x] Interfaz rediseñada a partir del prototipo aprobado (`docs/prototipos/revision_propuestas.html`): pestañas nuevas **Revisión** (lista a la izquierda, detalle con cita, compromiso vendido, confianza y motivo a la derecha; lote opcional por umbral de confianza, sin nada preseleccionado; botones deshabilitados con el motivo si el rol no decide; «Resueltas» plegadas) y **Catálogo** (requisitos, versiones, evidencia). La revisión salió de «Fuentes».
- [x] Identidad de CFOTech (colores sacados de la preventa): `.streamlit/config.toml` + `ui/theme.py` (franja superior, títulos en índigo, subrayado verde).
- [x] `tests/test_revision.py` (12 tests) y `tests/test_ui_revision.py` (6, con el probador de Streamlit y un catálogo temporal).
- Limitaciones de Streamlit frente al prototipo: sin globo de pendientes en la pestaña (cambiar el rótulo reinicia la pestaña activa), solo tema claro.
- [ ] Redacción de historias solo para las aprobadas, Crítico, conexión con el grafo, «crear o actualizar» con clave por requisito.

## Día 11 · Skills y contexto — [x] (falta commit; falta medir el ahorro con una corrida real)
**Objetivo:** darle a cada agente solo el conocimiento y el contexto que necesita, sin sobrecargarlo.

- [x] Cinco skills en formato Agent Skills (`skills/<nombre>/SKILL.md`) — una por rol: redacción de historias, revisión adversarial, auditoría de alcance, delegación de tareas y plan de publicación. Explican cómo hacer algo y no dan permisos (un `allowed-tools` se rechaza); el procedimiento y los criterios pasaron del `agent.md` a la skill, y el `agent.md` conserva el rol y las reglas duras.
- [x] `SkillLoader` (clase 10) — nivel 1 (encabezado), nivel 2 (cuerpo) y nivel 3 (recursos sin salir de la carpeta). Adaptación fuera del curso: cada skill declara su rol y la asigna el código, no un selector léxico. Los recursos de nivel 3 (`references/`) todavía no se usan: se agregan cuando haya una forma de leerlos bajo demanda.
- [x] Compactación del historial — solo las últimas 2 observaciones viajan completas; las antiguas se resumen con una regla fija por herramienta (sin modelo, sin agregar texto, conservando los ids). El expediente precalculado no se compacta. La traza guarda siempre el contenido completo.
- [x] Presupuesto de contexto por agente (`config/context_budget.yaml`) — tope de caracteres de prompt por agente; si se supera, se compacta más y el paso queda registrado en la traza y en la vista en vivo.
- [ ] Medir el ahorro con una corrida real (productor, que reenviaba todo en cada paso).

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
- [x] **Productor con Sonnet (2026-10-25):** reemplaza a Haiku (que cubrió 4 de al menos 8 requisitos en la prueba real) y a Gemini (cuota gratuita). Productor y Crítico siguen siendo del mismo proveedor (distinto modelo): revisar la independencia y comparar modelos en la evaluación (Día 13).
- [~] MCP para Azure DevOps: **diferido** (2026-10-25). Se avanza con el modo simulado, detrás de una interfaz (`BacklogGateway`) para enchufar MCP después de las clases de noviembre. El servidor oficial (`@azure-devops/mcp`) exige una cuenta con Entra ID.
- [ ] Embeddings reales (`sentence-transformers`): decidir en la evaluación
