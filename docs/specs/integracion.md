# Especificación · Agente de Integración (Azure DevOps simulado)

**Estado:** implementado (Día 9) · **Modelo:** `claude-haiku-5-5`, esfuerzo bajo · **Código:** `src/backlogguard/integrations/`, `agents/integracion/`, `tools/integracion.py`

## Propósito
Convertir los ítems sustentados del tablero en un **plan de publicación** para Azure DevOps, verificarlo contra el backlog actual y, solo con la aprobación de una persona, publicarlo sin duplicar nada. Es el único agente con permiso de escritura externa, y esa escritura depende de código, no del modelo.

## Diseño: qué decide el modelo y qué decide el código
| Decide el modelo (Integración) | Decide el código |
|---|---|
| Qué buscar en el backlog para detectar posibles duplicados y cómo resumir el plan. | Qué acción corresponde a cada ítem (crear, actualizar, vincular, omitir). |
| | El hash del plan, la revalidación, la clave de idempotencia y el orden de publicación. |
| | Quién puede escribir: solo la aplicación, con un plan aprobado cuyo hash coincide. |

El plan se garantiza en código: si el modelo no llega a armarlo, se arma igual. La publicación **no la ejecuta el modelo**: tras la aprobación humana (Día 10), la aplicación llama a `ejecutar_plan_aprobado` a través del `ToolRegistry` (`execute_approved_plan`), con el contexto de ejecución aprobado.

## Acceso al backlog
`BacklogGateway` es la única puerta al backlog (buscar, leer, crear, actualizar, vincular). Hoy hay una implementación:
- **Simulada** (`AZDO_MODE=simulated`, por defecto): se comporta como Azure DevOps (ids numerados desde 1001, versión por work item, etiquetas, padre-hijo), persiste en un archivo JSON y puede inyectar fallos para las pruebas.
- **Real (MCP):** **diferida**. El modo `real` falla con un mensaje claro. La interfaz está pensada para enchufar el cliente MCP después de las clases de noviembre.

## Entradas y salidas
- **Tools (4):** `buscar_en_backlog` (`read`), `armar_plan_dry_run` (`draft`), `revalidar_plan` (`read`), `ejecutar_plan_aprobado` (`write`).
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
| IN-10 | El backlog simulado cumple el contrato de la interfaz y el modo real, aún no disponible, falla con un mensaje claro. | `test_el_gateway_simulado_cumple_el_contrato`, `test_el_modo_real_no_esta_disponible_todavia` |
| IN-11 | El agente arma y revalida el plan con sus tools; si el modelo falla, el plan se arma igual. | `test_el_agente_arma_y_revalida_el_plan`, `test_el_plan_se_arma_aunque_el_modelo_falle` |
| IN-12 | El texto de los ítems, que proviene de reuniones, es dato: una orden dentro de un título no altera el plan y el modelo no puede ejecutarlo. | `test_inyeccion_en_un_item_no_altera_el_plan` |
| IN-13 | La corrida arma el plan al final y termina en `plan_pendiente_de_aprobacion`: el grafo no publica. Con una aprobación posterior, el plan se publica. | `test_el_grafo_arma_el_plan_y_no_publica` |
| IN-14 | El plan no publica dos ítems casi iguales (aunque usen otras palabras) ni uno equivalente a un work item cargado a mano: los omite y explica por qué. | `test_titulos_casi_iguales_con_otras_palabras_son_duplicados`, `test_el_plan_no_publica_dos_items_casi_iguales` |
| IN-15 | Se puede seguir a los agentes en vivo: cada paso (decisión, tool, resultado) se emite como evento y se formatea en una línea. | `test_la_vista_en_vivo_formatea_los_eventos_de_los_agentes` |
| IN-16 | Un `AZDO_PROJECT` vacío en el `.env` usa el valor por defecto. | `test_un_proyecto_vacio_en_el_env_usa_el_valor_por_defecto` |

## Fuera del curso (decisiones propias)
- Todo el módulo de integración: `BacklogGateway`, backlog simulado, registro de publicaciones, etiquetas de idempotencia y plan con hash.
- **MCP diferido:** la clase 11 lo menciona como tema de "clases posteriores" y todavía no se dictó; el servidor oficial de Microsoft además exige una cuenta con Entra ID.
- Vínculo opcional `parent_id` en `BacklogItem` (cambio al contrato del Día 1) y en `redactar_historia`.
- Similitud de títulos compartida entre el Crítico y el plan (raíz de 5 letras y coeficiente de solapamiento).

## Límites conocidos
- El modo real no existe todavía; lo publicado solo llega al backlog simulado.
- No hay reversión: ante un fallo parcial se reporta, pero lo ya publicado queda publicado.
- Los ítems se publican como work items; no se cargan adjuntos ni se gestionan iteraciones.
- La detección de duplicados es por título; dos ítems con otro título y el mismo significado no se detectan.
- El hash incluye la versión observada de cada work item: cualquier edición ajena invalida el plan y obliga a armarlo de nuevo.
