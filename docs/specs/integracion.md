# Especificación · Agente de Integración (Azure DevOps)

**Estado:** gateway MCP implementado sobre el adaptador REST; validación en el tenant real y autenticación productiva pendientes · **Código:** `src/backlogguard/integrations/`, `agents/integracion/`, `tools/integracion.py`

## Propósito
Convertir los ítems sustentados del tablero en un **plan de publicación** para Azure DevOps, verificarlo contra el backlog actual y, solo con la aprobación de una persona, publicarlo sin duplicar nada. Es el único agente con permiso de escritura externa, y esa escritura depende de código, no del modelo.

## Diseño: qué decide el modelo y qué decide el código
| Decide el modelo (Integración) | Decide el código |
|---|---|
| Qué buscar en el backlog para detectar posibles duplicados y cómo resumir el plan. | Qué acción corresponde a cada ítem (crear, actualizar, vincular, omitir). |
| | El hash del plan, la revalidación, la clave de idempotencia y el orden de publicación. |
| | Quién puede escribir: solo la aplicación, con un plan aprobado cuyo hash coincide. |

El plan se garantiza en código: si el modelo no llega a armarlo, se arma igual. La publicación **no la ejecuta el modelo**: tras la aprobación humana (Día 10), la aplicación llama a `ejecutar_plan_aprobado` a través del `ToolRegistry` (`execute_approved_plan`), con el contexto de ejecución aprobado.

Para work items existentes, el dry-run compara título, descripción y criterios de aceptación con el contenido revisado (normalizando formato HTML y espacios de Azure). Si encuentra diferencias, marca `actualizar` y muestra el contenido actual y el propuesto lado a lado antes de permitir aprobar. La actualización conserva el ID del work item; usa su revisión observada para evitar pisar una edición concurrente.

### Reconciliación final de requisitos reemplazados
Al final del flujo de backlog, una etapa separada analiza los requisitos del catálogo en estado retirado explícitamente, reemplazado, dividido o fusionado que ya tienen una publicación registrada. Un retiro explícito se registra en el catálogo con responsable, motivo y fecha. Presenta un dry-run y requiere una segunda aprobación explícita del rol Full Stack IA Engineer; no reutiliza la aprobación del plan de publicación. La acción conserva el work item y sus relaciones, y cambia su estado a uno cuya categoría Azure sea `Removed`. Nunca llama al endpoint DELETE. La mera ausencia de un requisito en una nueva versión de un PDF no genera un retiro.

La reconciliación solo propone ítems con la etiqueta exacta de propiedad `bg-item:HU-<id>`. Bloquea ítems manuales, procesos sin categoría `Removed` y padres con hijos cuyo estado no sea `Completed` o `Removed`. Antes de ejecutar, vuelve a leer los ítems, hijos y estados; utiliza la revisión esperada de Azure para detectar ediciones concurrentes. Si una ejecución se interrumpe, el mismo plan puede reintentarse: los ítems ya retirados se reconocen y no reciben una transición duplicada. Los resultados parciales quedan registrados en el ledger.

## Acceso al backlog
`BacklogGateway` es la única puerta al backlog (buscar, leer, crear, actualizar, vincular). Hay dos implementaciones para la aplicación:
- **Simulada** (`AZDO_MODE=simulated`, por defecto): se comporta como Azure DevOps (ids numerados desde 1001, versión por work item, etiquetas, padre-hijo), persiste en un archivo JSON y puede inyectar fallos para las pruebas.
- **Azure DevOps vía MCP** (`AZDO_MODE=real`): la aplicación usa un cliente MCP síncrono que conserva el contrato `BacklogGateway`; por defecto conecta con un servidor MCP en proceso. El servidor expone Tools para probar conexión, listar proyectos, descubrir tipos, leer y buscar work items, publicar cambios y descubrir estados/hijos para reconciliar; además publica el Resource `backlogguard://azure/configuration` y el Prompt `prepare_backlog_plan`. El adaptador REST Work Item Tracking 7.1 vive detrás del servidor MCP y descubre tipos/campos del proceso, mapea User Story a Product Backlog Item cuando corresponde y envía JSON Patch con enlaces jerárquicos.
- **MCP por HTTP** (opcional): `AZDO_MCP_ENDPOINT` conecta con un servidor Streamable HTTP. El servidor ejecutable (`python -m backlogguard.integrations.mcp_server`) queda ligado a `127.0.0.1`, publica los mismos Tools/Resource/Prompt para interoperabilidad y deshabilita escrituras. La app solo hace operaciones de escritura por el servidor en proceso, tras pasar por `ToolRegistry`, la aprobación humana, el hash y la revalidación del plan; el cliente transmite una capacidad aleatoria privada únicamente dentro de ese flujo. No habilitar una ruta remota de escritura sin autenticación y propagación verificable de esa aprobación.

El PAT se configura como `AZDO_TOKEN` en `.env` local ignorado por Git o en un secret store; solo el servidor que contiene el adaptador REST lo recibe. `Settings.safe_dict()` lo oculta y el adaptador rechaza el modo real fuera de `APP_ENV=development`. No se realizan llamadas de escritura reales en tests ni durante esta implementación; las pruebas usan Azure simulado y servidor MCP local. No ingresar el secreto en el chat ni en el frontend. Para producción se requiere acordar y configurar un mecanismo empresarial, como Microsoft Entra ID.

## Entradas y salidas
- **Tools de publicación (4):** `buscar_en_backlog` (`read`), `armar_plan_dry_run` (`draft`), `revalidar_plan` (`read`), `ejecutar_plan_aprobado` (`write`). La reconciliación final agrega `ejecutar_retiros_aprobados` (`write`), bajo el mismo gate de policy y hash de plan aprobado.
- **Salida:** un `PublishPlan` validado con Pydantic (acción por ítem, motivo, clave de idempotencia, tipo de work item, padre, versión observada) y su hash. Al ejecutar, un `ExecutionReport` con el resultado por ítem.
- **Registro de publicaciones** (SQLite): intención y resultado de cada ítem, y los planes armados.

## Requisitos

| ID | Requisito | Test que lo verifica |
|---|---|---|
| IN-01 | Solo Integración ve estas tools; armar el plan exige el permiso de borrador y `ejecutar_plan_aprobado` exige permiso de escritura externa y un plan aprobado. | `test_las_tools_de_integracion_son_solo_de_integracion`, `test_sin_permiso_de_escritura_no_se_ejecuta_nada` |
| IN-02 | El plan en dry-run compara con el backlog y asigna `crear`, `actualizar`, `vincular` u `omitir` a cada ítem, sin escribir. | `test_el_plan_asigna_la_accion_correcta`, `test_vincular_cuando_falta_el_padre`, `test_el_dry_run_no_escribe` |
| IN-03 | Solo entran al plan los ítems sustentados o aprobados; nunca borradores, objetados ni excluidos. | `test_solo_los_items_sustentados_entran_al_plan` |
| IN-04 | El hash del plan es determinístico, cambia si cambia cualquier ítem y no cambia al aprobar los ítems. | `test_el_hash_es_estable_y_sensible_al_contenido`, `test_aprobar_los_items_no_cambia_el_hash` |
| IN-05 | `revalidar_plan` detecta que el backlog cambió desde que se armó el plan (por ejemplo, un work item equivalente creado por otra persona). | `test_revalidar_detecta_cambios_en_el_backlog` |
| IN-06 | `ejecutar_plan_aprobado` exige que el hash coincida con el aprobado y revalida antes de escribir; si hay deriva o el plan no existe, no escribe. | `test_ejecutar_exige_el_hash_aprobado`, `test_la_deriva_del_backlog_bloquea_la_ejecucion`, `test_ejecutar_un_plan_inexistente_falla` |
| IN-07 | Cada ítem tiene una clave de idempotencia; ejecutar dos veces el mismo plan no duplica nada. | `test_repetir_la_ejecucion_no_duplica` |
| IN-08 | Si una creación tuvo éxito pero la respuesta se perdió, el reintento busca primero por la etiqueta de la clave y no crea otro. | `test_resultado_ambiguo_no_duplica` |
| IN-09 | Los padres se publican antes que los hijos; ante un fallo se detiene, reporta qué se publicó y qué no, y el reintento retoma desde donde quedó. | `test_los_padres_van_antes_que_los_hijos`, `test_un_fallo_parcial_se_detiene_y_se_reporta`, `test_un_fallo_a_mitad_conserva_lo_ya_publicado` |
| IN-10 | El backlog simulado cumple el contrato de la interfaz y el servidor MCP solo activa el adaptador REST con organización, proyecto y PAT de desarrollo configurados. | `test_el_gateway_simulado_cumple_el_contrato`, `test_el_modo_real_exige_configuracion_antes_de_conectar`, `test_real_mode_exige_configuracion_y_restringe_pat_a_desarrollo` |
| IN-11 | El agente arma y revalida el plan con sus tools; si el modelo falla, el plan se arma igual. | `test_el_agente_arma_y_revalida_el_plan`, `test_el_plan_se_arma_aunque_el_modelo_falle` |
| IN-12 | El texto de los ítems, que proviene de reuniones, es dato: una orden dentro de un título no altera el plan y el modelo no puede ejecutarlo. | `test_inyeccion_en_un_item_no_altera_el_plan` |
| IN-13 | La corrida arma el plan al final y termina en `plan_pendiente_de_aprobacion`: el grafo no publica. Con una aprobación posterior, el plan se publica. | `test_el_grafo_arma_el_plan_y_no_publica` |
| IN-14 | El plan no publica dos ítems casi iguales (aunque usen otras palabras) ni uno equivalente a un work item cargado a mano: los omite y explica por qué. | `test_titulos_casi_iguales_con_otras_palabras_son_duplicados`, `test_el_plan_no_publica_dos_items_casi_iguales` |
| IN-15 | Se puede seguir a los agentes en vivo: cada paso (decisión, tool, resultado) se emite como evento y se formatea en una línea. | `test_la_vista_en_vivo_formatea_los_eventos_de_los_agentes` |
| IN-16 | Un `AZDO_PROJECT` vacío en el `.env` usa el valor por defecto. | `test_un_proyecto_vacio_en_el_env_usa_el_valor_por_defecto` |
| REC-01 | El dry-run solo considera requisitos no activos con publicación registrada y protege ítems sin etiqueta exacta de propiedad. | `test_dry_run_propone_retiro_reversible_solo_para_requisito_publicado_propio`, `test_no_retira_work_item_sin_marca_de_propiedad` |
| REC-02 | El estado objetivo se descubre por categoría `Removed`; hijos no terminales bloquean el retiro. | `test_tipo_sin_categoria_removed_no_asume_un_estado_alternativo`, `test_un_hijo_activo_bloquea_el_retiro_del_padre` |
| REC-03 | La ejecución exige el hash aprobado, detecta cambios concurrentes y permite reanudar fallos parciales sin repetir transiciones ya completadas. | `test_el_retiro_se_ejecuta_por_tool_con_plan_aprobado_y_deja_historial`, `test_un_cambio_concurrente_bloquea_el_plan_antes_de_escribir`, `test_fallo_parcial_se_reanuda_con_el_mismo_plan_sin_repetir_retiros` |
| MCP-01 | El servidor publica Tools, un Resource y un Prompt; el cliente en proceso conserva el contrato del gateway. | `test_mcp_publica_tools_resource_y_prompt_y_cliente_en_proceso`, `test_gateway_mcp_en_proceso_conserva_el_contrato_y_el_plan_de_escritura` |
| MCP-02 | El cliente Streamable HTTP consume el servidor MCP local y las escrituras HTTP son rechazadas. | `test_cliente_http_streamable_mcp_conecta_al_servidor_read_only`, `test_servidor_http_read_only_rechaza_escrituras` |

## Fuera del curso (decisiones propias)
- Todo el módulo de integración: `BacklogGateway`, backlog simulado, registro de publicaciones, etiquetas de idempotencia y plan con hash.
- REST se conserva únicamente como adaptador privado del servidor MCP, con PAT solo para desarrollo controlado. OAuth/Entra ID para producción sigue pendiente.
- Vínculo opcional `parent_id` en `BacklogItem` (cambio al contrato del Día 1) y en `redactar_historia`.
- Similitud de títulos compartida entre el Crítico y el plan (raíz de 5 letras y coeficiente de solapamiento).

## Límites conocidos
- La conexión real todavía no se validó contra `TP-ITBA`; no se ejecutaron escrituras reales.
- La autenticación PAT es solo para desarrollo; no usarla en producción.
- Los tipos y campos se descubren del proceso, pero los mapeos configurables solo cubren épica, historia y tarea; otros tipos requieren configuración/código adicional.
- No hay reversión: ante un fallo parcial se reporta, pero lo ya publicado queda publicado.
- Los ítems se publican como work items; no se cargan adjuntos ni se gestionan iteraciones.
- La detección de duplicados es por título; dos ítems con otro título y el mismo significado no se detectan.
- El hash incluye la versión observada de cada work item: cualquier edición ajena invalida el plan y obliga a armarlo de nuevo.
